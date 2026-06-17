"""
IndicatorHub — 统一指标加载层 v1.0

从 DuckDB indicators 表读取预计算指标（sync_indicators.py 产物），
与 IndicatorEngine 实时计算的高级指标合并，提供按维度分组的统一接口。

设计原则：
- 不替代 IndicatorEngine：Hub 只做加载+合并，IndicatorEngine 继续负责 C-class 高级指标
- 缓存优先：同一品种同一交易日缓存计算结果
- 字段名统一：提供 TqSdk 列名 ↔ IndicatorEngine 列名的双向映射

使用方式：
    hub = IndicatorHub(db_path='data/market.db')
    df = hub.load('DCE.jm')           # 宽表 DataFrame（所有指标列）
    dims = hub.get_dimensions('DCE.jm')  # {trend: DataFrame, momentum: DataFrame, ...}
"""

import os
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from functools import lru_cache

import duckdb
import pandas as pd
import numpy as np


# ===================== 维度分组定义 =====================

DIMENSION_GROUPS: Dict[str, List[str]] = {
    "trend": [
        "ma5", "ma10", "ma20", "ma60", "ma100",
        "ema20", "ema60", "adx", "adxr", "plus_di", "minus_di",
        "sar", "dkx", "madkx", "lon",
        "ma20_slope", "ma60_slope", "spread_ma20_ma60",
    ],
    "momentum": [
        "macd", "macd_signal", "macd_hist",
        "rsi", "kdj_k", "kdj_d", "kdj_j",
        "roc", "mtm", "mtm_ma",
        "adtm", "ddi", "wr", "cci", "priceosc",
        "dpo", "b36", "b612",
    ],
    "volume": [
        "obv", "ad", "mfi", "vr", "vroc",
        "wvad", "pvt", "ar", "br",
    ],
    "volatility": [
        "atr", "atr_ratio",
        "bb_upper", "bb_mid", "bb_lower", "bb_width",
        "bbiboll", "mass",
    ],
    "channel": [
        "dc_upper", "dc_mid", "dc_lower",
        "hcl_upper", "hcl_mid", "hcl_lower",
        "env_upper", "env_lower",
        "mike_wr1", "mike_ws1", "mike_wr2", "mike_ws2", "mike_wr3", "mike_ws3",
        "pubu_pb4", "pubu_pb6", "pubu_pb9", "pubu_pb13",
    ],
}


# ===================== 字段名映射 =====================

# TqSdk/sync_indicators 输出列名 → IndicatorEngine 标准列名
FIELD_NAME_MAP: Dict[str, str] = {
    # 均线类（一致，无需映射）
    # 趋势类
    "plus_di": "di_plus",
    "minus_di": "di_minus",
    # 震荡类
    "kdj_k": "stoch_k",
    "kdj_d": "stoch_d",
    "kdj_j": "stoch_j",
    "wr": "williams_r",
    "bias6": "bias_6",
    "bias12": "bias_12",
    "bias24": "bias_24",
    # 动量类
    "macd": "macd_line",
    "macd_signal": "macd_signal_line",
    "macd_hist": "macd_histogram",
    "mtm": "momentum",
    "mtm_ma": "momentum_ma",
    # 通道类
    "dc_upper": "donchian_upper",
    "dc_mid": "donchian_mid",
    "dc_lower": "donchian_lower",
    "bb_upper": "bollinger_upper",
    "bb_mid": "bollinger_mid",
    "bb_lower": "bollinger_lower",
    "bb_width": "bollinger_width",
}

# 反向映射：IndicatorEngine 列名 → sync_indicators 列名
REVERSE_FIELD_MAP: Dict[str, str] = {v: k for k, v in FIELD_NAME_MAP.items()}


class IndicatorHub:
    """
    统一指标加载层。

    从 DuckDB indicators 表读取预计算指标（sync_indicators.py 产物），
    运行 IndicatorEngine 计算高级指标（ER/R²/Hurst/TSI等），
    合并为统一宽表 DataFrame。

    缓存策略：同一品种同一交易日缓存，避免重复计算。
    """

    def __init__(self, db_path: str = "data/market.db",
                 cache_dir: Optional[str] = None):
        """
        Args:
            db_path: DuckDB 数据库路径
            cache_dir: 缓存目录，默认 data/indicator_cache/
        """
        self.db_path = db_path
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(db_path), "indicator_cache"
        )
        os.makedirs(self.cache_dir, exist_ok=True)

        # 内存缓存 {(symbol, latest_date_hash): DataFrame}
        self._mem_cache: Dict[Tuple[str, str], pd.DataFrame] = {}

    # ===================== 公共接口 =====================

    def load(self, symbol: str, force_refresh: bool = False) -> pd.DataFrame:
        """
        加载品种的全部指标（预计算 + 高级指标合并）。

        Args:
            symbol: 品种代码（如 'DCE.jm'）
            force_refresh: 是否强制刷新（忽略缓存）

        Returns:
            宽表 DataFrame，包含所有指标列 + open/high/low/close/volume
        """
        # 检查缓存
        cache_key = self._cache_key(symbol)
        if not force_refresh:
            cached = self._load_cache(symbol, cache_key)
            if cached is not None and len(cached) > 0:
                return cached

        # 1. 从 DuckDB 加载预计算指标
        wide_df = self._load_from_db(symbol)
        if wide_df is None or len(wide_df) == 0:
            raise ValueError(f"品种 {symbol} 无指标数据，请先运行 sync_indicators.py")

        # 2. 运行 IndicatorEngine 计算高级指标
        wide_df = self._compute_advanced(wide_df)

        # 3. 存储缓存
        self._save_cache(symbol, cache_key, wide_df)
        self._mem_cache[(symbol, cache_key)] = wide_df

        return wide_df

    def get_dimensions(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """
        按维度分组获取指标。

        Args:
            symbol: 品种代码

        Returns:
            {trend: DF, momentum: DF, volume: DF, volatility: DF, channel: DF}
        """
        df = self.load(symbol)

        result = {}
        for dim_name, dim_indicators in DIMENSION_GROUPS.items():
            # 只取该维度的指标列（保留 ohlcv 基准 + timestamp）
            cols = ["timestamp"] if "timestamp" in df.columns else []
            available = [c for c in dim_indicators if c in df.columns]
            if available:
                result[dim_name] = df[cols + available].copy()
            else:
                result[dim_name] = pd.DataFrame()

        return result

    def get_latest(self, symbol: str) -> Dict[str, float]:
        """
        获取最新一条记录的所有指标值（扁平字典）。

        Args:
            symbol: 品种代码

        Returns:
            {indicator_name: value} 字典
        """
        df = self.load(symbol)
        if len(df) == 0:
            return {}

        latest = df.iloc[-1]
        result = {}
        for col in df.columns:
            if col in ("timestamp", "symbol", "date"):
                val = latest[col]
                if isinstance(val, pd.Timestamp):
                    val = val.isoformat()
                result[f"_{col}"] = val
            elif col in ("open", "high", "low", "close", "volume"):
                result[col] = float(latest[col])
            else:
                v = latest[col]
                if pd.notna(v):
                    result[col] = float(v)

        return result

    def get_indicator_names(self) -> List[str]:
        """返回所有可用的指标名称列表"""
        all_names = set()
        for names in DIMENSION_GROUPS.values():
            all_names.update(names)
        return sorted(all_names)

    def clear_cache(self):
        """清除所有缓存"""
        self._mem_cache.clear()
        for f in Path(self.cache_dir).glob("*.parquet"):
            f.unlink()

    # ===================== 内部方法 =====================

    def _cache_key(self, symbol: str) -> str:
        """生成缓存键（基于最新数据日期）"""
        conn = duckdb.connect(self.db_path, read_only=True)
        try:
            result = conn.execute(f"""
                SELECT MAX(timestamp)
                FROM indicators
                WHERE symbol = '{symbol}'
            """).fetchone()
            latest_ts = result[0] if result and result[0] else ""
        except Exception:
            latest_ts = ""
        finally:
            conn.close()

        raw = f"{symbol}:{latest_ts}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _load_cache(self, symbol: str, cache_key: str) -> Optional[pd.DataFrame]:
        """尝试从缓存加载"""
        if (symbol, cache_key) in self._mem_cache:
            return self._mem_cache[(symbol, cache_key)]

        cache_file = os.path.join(self.cache_dir, f"{cache_key}.parquet")
        if os.path.exists(cache_file):
            try:
                return pd.read_parquet(cache_file)
            except Exception:
                pass
        return None

    def _save_cache(self, symbol: str, cache_key: str, df: pd.DataFrame):
        """存储缓存"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.parquet")
        try:
            df.to_parquet(cache_file, index=False)
        except Exception:
            pass

    def _load_from_db(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        从 DuckDB indicators 长表读取并转换为宽表。
        """
        conn = duckdb.connect(self.db_path, read_only=True)

        try:
            # 检查是否有 indicators 表
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='indicators'"
            ).fetchall()
            if not tables:
                # DuckDB 的表查询方式不同
                tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_name='indicators'").fetchall()

            if not tables:
                return None

            # 读取长表数据
            df_long = conn.execute(f"""
                SELECT timestamp, indicator_name, value
                FROM indicators
                WHERE symbol = '{symbol}'
                ORDER BY timestamp ASC, indicator_name ASC
            """).fetchdf()

            if len(df_long) == 0:
                return None

            # 长表 → 宽表 pivot
            df_wide = df_long.pivot(
                index='timestamp', columns='indicator_name', values='value'
            ).reset_index()
            df_wide.columns.name = None

            # 补充 K 线数据
            try:
                df_klines = conn.execute(f"""
                    SELECT timestamp, open, high, low, close, volume
                    FROM klines
                    WHERE symbol = '{symbol}'
                    ORDER BY timestamp ASC
                """).fetchdf()

                if len(df_klines) > 0:
                    df_wide = pd.merge(df_wide, df_klines, on='timestamp', how='left')
            except Exception:
                pass

            return df_wide

        except Exception:
            return None
        finally:
            conn.close()

    def _compute_advanced(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        使用 IndicatorEngine 计算 C-class 高级指标（ER/R²/Hurst/TSI等）。

        这些指标已由 sync_indicators.py 计算并存入 DuckDB，本方法作为兜底：
        如果 DB 中缺少某个高级指标，则在此补算。

        注意：sync_indicators.py v2.1 已覆盖全部 90 个指标，正常情况下本方法不需要补算。
        """
        # sync_indicators.py v2.1 已计算全部指标，无需额外补算。
        # 保留此方法作为扩展口，未来新增高级指标时可在此添加。
        return df


# ===================== 便捷函数 =====================

@lru_cache(maxsize=32)
def _get_hub_instance(db_path: str) -> IndicatorHub:
    """获取 IndicatorHub 单例（LRU 缓存）"""
    return IndicatorHub(db_path=db_path)


def load_indicators(symbol: str, db_path: str = "data/market.db") -> pd.DataFrame:
    """便捷函数：加载品种的全部指标"""
    hub = _get_hub_instance(db_path)
    return hub.load(symbol)


def get_dimensions(symbol: str, db_path: str = "data/market.db") -> Dict[str, pd.DataFrame]:
    """便捷函数：按维度获取指标"""
    hub = _get_hub_instance(db_path)
    return hub.get_dimensions(symbol)


def get_latest_indicators(symbol: str, db_path: str = "data/market.db") -> Dict[str, float]:
    """便捷函数：获取最新指标值"""
    hub = _get_hub_instance(db_path)
    return hub.get_latest(symbol)
