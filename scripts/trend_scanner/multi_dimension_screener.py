"""
MultiDimensionScreener — 多维度筛选评分器 v1.0

将 IndicatorHub 输出的 90 个指标按五个维度分组，每个维度内的指标归一化后
加权合成维度得分，最终输出综合得分和方向信号。

五维度权重：
  趋势 30% + 动量 25% + 成交量 20% + 波动率 15% + 通道 10%

归一化规则：
  - 有界指标（RSI/MFI/VR）：线性映射到 (-1, +1)，以 50 为中性点
  - 方向性指标（DI+/DI-/MACD柱）：符号即信号，幅度做置信度
  - 通道/均线位置：价格在均线上方为正，下方为负
  - 成交量指标：背离扣分，同向加分

信号判定：
  overall_score > 0.3  → LONG  （看多）
  overall_score < -0.3 → SHORT （看空）
  其他                → NEUTRAL（中性）

使用方式：
    from indicator_hub import IndicatorHub
    from multi_dimension_screener import MultiDimensionScreener

    hub = IndicatorHub()
    df = hub.load('DCE.jm')
    screener = MultiDimensionScreener()
    result = screener.score('DCE.jm', df)
    print(f"综合得分: {result.overall_score:.3f}, 信号: {result.signal}")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


# ===================== 数据模型 =====================

@dataclass
class DimensionScore:
    """单维度评分"""
    name: str                           # 维度名称
    weight: float                       # 权重 (0-1)
    indicator_scores: Dict[str, float]  # 各指标归一化得分
    composite: float                    # 维度综合分 (-1 到 +1)
    direction: str                      # 方向: BULLISH / BEARISH / NEUTRAL
    confidence: float                   # 置信度 (0-1)，基于指标一致性


@dataclass
class MultiDimensionResult:
    """多维度筛选结果"""
    symbol: str
    timestamp: str = ""
    dimensions: List[DimensionScore] = field(default_factory=list)
    overall_score: float = 0.0          # 综合得分 (-1 到 +1)
    confidence: float = 0.0              # 整体置信度 (0-1)
    signal: str = "NEUTRAL"              # LONG / SHORT / NEUTRAL

    def to_dict(self) -> Dict:
        """转为字典（便于 JSON 序列化）"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 4),
            "confidence": round(self.confidence, 4),
            "signal": self.signal,
            "dimensions": [
                {
                    "name": d.name,
                    "weight": d.weight,
                    "composite": round(d.composite, 4),
                    "direction": d.direction,
                    "confidence": round(d.confidence, 4),
                    "top_indicators": dict(sorted(
                        d.indicator_scores.items(),
                        key=lambda x: abs(x[1]), reverse=True
                    )[:5]),
                }
                for d in self.dimensions
            ],
        }


# ===================== 维度配置 =====================

# 维度权重
DIMENSION_WEIGHTS = {
    "trend":      0.30,
    "momentum":   0.25,
    "volume":     0.20,
    "volatility": 0.15,
    "channel":    0.10,
}

# 维度指标定义 (name, neutral_value, bounded_min, bounded_max, scaling)
# scaling: "bounded" | "directional" | "position" | "volume"
DIMENSION_INDICATORS: Dict[str, List[Tuple[str, float, float, float, str]]] = {
    "trend": [
        ("adx",        20, 0, 80,    "bounded"),       # ADX: 20以下弱趋势, 40以上强趋势
        ("plus_di",    20, 0, 60,    "directional"),   # +DI
        ("minus_di",   20, 0, 60,    "directional"),   # -DI (反转信号)
        ("sar",         0, 0, 0,     "position"),       # 价格 vs SAR
        ("dkx",         0, 0, 0,     "position"),       # 价格 vs DKX
        ("lon",        50, 0, 100,   "bounded"),       # 铁龙长线
        ("ma20_slope",  0, -5, 5,    "bounded"),       # MA20斜率
        ("ma60_slope",  0, -3, 3,    "bounded"),       # MA60斜率
        ("adxr",       20, 0, 80,    "bounded"),       # ADXR
        ("ema_slope_strength", 0, -2, 2, "bounded"),   # EMA斜率强度
        ("spread_ma20_ma60", 0, -5, 5, "bounded"),     # 均线间距
    ],
    "momentum": [
        ("macd",        0, -100, 100, "directional"),  # MACD 线
        ("macd_hist",   0, -50, 50,   "directional"),  # MACD 柱
        ("rsi",        50, 0, 100,   "bounded"),       # RSI
        ("kdj_k",      50, 0, 100,   "bounded"),       # KDJ_K
        ("roc",         0, -10, 10,  "bounded"),       # ROC
        ("mtm",         0, -50, 50,  "directional"),   # 动量
        ("wr",         50, 0, 100,   "bounded"),       # Williams %R (反转)
        ("cci",         0, -300, 300,"bounded"),       # CCI
        ("priceosc",    0, -10, 10,  "directional"),   # 价格振荡器
        ("b36",         0, -20, 20,  "directional"),   # 三减六乖离
        ("b612",        0, -30, 30,  "directional"),   # 六减十二乖离
    ],
    "volume": [
        ("mfi",        50, 0, 100,   "bounded"),       # 资金流量指数
        ("vr",         100, 40, 350, "bounded"),       # 成交量变异率（中立值~100）
        ("vroc",        0, -50, 50,  "directional"),   # 成交量变化率
        ("obv",         0, 0, 0,     "volume"),        # OBV 趋势（与价格同向确认）
    ],
    "volatility": [
        ("atr_ratio",   1.0, 0.5, 2.0, "bounded"),    # ATR 比率（>1 波动扩张）
        ("bb_width",    0, 0, 0,     "position"),      # 布林带宽度（价格在带中位置）
        ("mass",       27, 20, 30,   "bounded"),       # MASS 指数
    ],
    "channel": [
        # 价格在通道中的位置（通过 position 与收盘价比较）
        ("dc_upper",    0, 0, 0,     "channel_upper"),  # Donchian 上轨
        ("dc_lower",    0, 0, 0,     "channel_lower"),  # Donchian 下轨
        ("bb_upper",    0, 0, 0,     "channel_upper"),  # 布林上轨
        ("bb_lower",    0, 0, 0,     "channel_lower"),  # 布林下轨
        ("hcl_upper",   0, 0, 0,     "channel_upper"),  # HCL 上轨
        ("hcl_lower",   0, 0, 0,     "channel_lower"),  # HCL 下轨
        ("env_upper",   0, 0, 0,     "channel_upper"),  # ENV 上轨
        ("env_lower",   0, 0, 0,     "channel_lower"),  # ENV 下轨
    ],
}


class MultiDimensionScreener:
    """
    多维度筛选评分器。

    将指标按五维度分组，逐维度归一化、评分，输出综合信号。
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Args:
            weights: 维度权重字典，默认使用 DIMENSION_WEIGHTS
        """
        self.weights = weights or DIMENSION_WEIGHTS

        # 验证权重合计为 1.0
        wsum = sum(self.weights.values())
        if abs(wsum - 1.0) > 0.01:
            # 自动归一化
            self.weights = {k: v / wsum for k, v in self.weights.items()}

    def score(self, symbol: str, df: pd.DataFrame) -> MultiDimensionResult:
        """
        对单个品种的指标 DataFrame 进行多维度评分。

        Args:
            symbol: 品种代码
            df: IndicatorHub.load() 返回的宽表 DataFrame

        Returns:
            MultiDimensionResult 包含各维度得分和综合信号
        """
        if len(df) == 0:
            return MultiDimensionResult(symbol=symbol, signal="NEUTRAL")

        # 取最新一行（或最后 N 行平均，避免单点噪声）
        latest = df.iloc[-1]

        # 构建维度评分
        dimensions = []
        for dim_name, weight in self.weights.items():
            dim_score = self._score_dimension(dim_name, latest, df)
            dim_score.weight = weight
            dimensions.append(dim_score)

        # 综合得分
        overall = sum(d.composite * d.weight for d in dimensions)

        # 整体置信度：各维度置信度的加权均值 × 维度一致性
        avg_confidence = sum(d.confidence * d.weight for d in dimensions)
        consistency = self._dimension_consistency(dimensions)
        confidence = avg_confidence * consistency

        # 信号判定
        signal = self._classify_signal(overall, confidence)

        # 时间戳
        ts = ""
        if "timestamp" in df.columns and len(df) > 0:
            ts_val = df["timestamp"].iloc[-1]
            if isinstance(ts_val, pd.Timestamp):
                ts = ts_val.isoformat()
            else:
                ts = str(ts_val)

        return MultiDimensionResult(
            symbol=symbol,
            timestamp=ts,
            dimensions=dimensions,
            overall_score=overall,
            confidence=confidence,
            signal=signal,
        )

    # ===================== 维度评分 =====================

    def _score_dimension(self, dim_name: str,
                          latest: pd.Series,
                          df: pd.DataFrame) -> DimensionScore:
        """对单个维度的指标进行归一化并合成维度得分"""
        indicator_configs = DIMENSION_INDICATORS.get(dim_name, [])
        scores: Dict[str, float] = {}

        for name, neutral, lo, hi, scaling in indicator_configs:
            if name not in df.columns:
                continue

            val = latest.get(name, np.nan)
            if pd.isna(val):
                continue

            if scaling == "bounded":
                scores[name] = self._normalize_bounded(val, neutral, lo, hi)
            elif scaling == "directional":
                scores[name] = self._normalize_directional(val, lo, hi)
            elif scaling == "position":
                scores[name] = self._normalize_position(name, val, latest)
            elif scaling == "volume":
                scores[name] = self._normalize_volume(name, val, latest, df)
            elif scaling == "channel_upper":
                scores[name] = self._normalize_channel("upper", name, val, latest)
            elif scaling == "channel_lower":
                scores[name] = self._normalize_channel("lower", name, val, latest)

        if not scores:
            return DimensionScore(
                name=dim_name, weight=0, indicator_scores={},
                composite=0, direction="NEUTRAL", confidence=0
            )

        # 维度综合分 = 各指标得分均值
        composite = float(np.mean(list(scores.values())))
        composite = max(-1.0, min(1.0, composite))

        # 置信度 = 指标间一致性（标准差越小越一致）
        score_vals = list(scores.values())
        if len(score_vals) >= 2:
            std = float(np.std(score_vals))
            consistency = max(0.0, 1.0 - std)
        else:
            consistency = 0.5

        direction = self._classify_signal(composite, consistency)

        return DimensionScore(
            name=dim_name, weight=0,
            indicator_scores=scores,
            composite=composite,
            direction=direction,
            confidence=consistency,
        )

    # ===================== 归一化规则 =====================

    @staticmethod
    def _normalize_bounded(val: float, neutral: float,
                            lo: float, hi: float) -> float:
        """
        有界指标归一化：线性映射到 (-1, +1)。

        以 neutral 为中心点：
        - val > neutral → 线性映射到 (0, +1)
        - val < neutral → 线性映射到 (0, -1)
        """
        if val > neutral:
            return min(1.0, (val - neutral) / (hi - neutral)) if hi > neutral else 0
        elif val < neutral:
            return max(-1.0, (val - neutral) / (neutral - lo)) if neutral > lo else 0
        else:
            return 0.0

    @staticmethod
    def _normalize_directional(val: float, lo: float, hi: float) -> float:
        """
        方向性指标归一化：符号即信号，幅度做置信度。

        正值为多头信号，负值为空头信号。
        """
        if val > 0:
            return min(1.0, val / abs(hi)) if abs(hi) > 0 else 0
        elif val < 0:
            return max(-1.0, val / abs(lo)) if abs(lo) > 0 else 0
        else:
            return 0.0

    @staticmethod
    def _normalize_position(ind_name: str, val: float, latest: pd.Series) -> float:
        """
        位置类指标归一化：基于价格与指标的关系。

        价格在均线/指标上方 = 正，下方 = 负。
        """
        close = latest.get("close", np.nan)
        if pd.isna(close) or pd.isna(val) or val == 0:
            return 0.0

        # 反转类：SAR 在价格下方为多头
        if ind_name == "sar":
            ratio = (close - val) / abs(close) * 100 if abs(close) > 0 else 0
            return max(-1.0, min(1.0, ratio / 2.0))

        # 通用：价格在指标上方为正
        ratio = (close - val) / abs(val) * 100 if abs(val) > 0 else 0
        return max(-1.0, min(1.0, ratio / 3.0))

    @staticmethod
    def _normalize_volume(ind_name: str, val: float,
                           latest: pd.Series, df: pd.DataFrame) -> float:
        """
        成交量类指标归一化：检测量价背离。

        OBV 趋势与价格趋势同向 = 正分，背离 = 负分。
        """
        close = latest.get("close", np.nan)
        if pd.isna(val) or pd.isna(close) or len(df) < 10:
            return 0.0

        # 计算 OBV 短期趋势（最近5天变化率）
        if ind_name == "obv" and "obv" in df.columns:
            obv_vals = df["obv"].values[-10:]
            obv_trend = (obv_vals[-1] - obv_vals[-5]) / (abs(obv_vals[-5]) + 1)
            price_trend = (df["close"].values[-1] - df["close"].values[-5]) \
                          / (abs(df["close"].values[-5]) + 1)

            # 同向 = +1, 背离 = -1, 不变 = 0
            if obv_trend > 0.02 and price_trend > 0:
                return 0.7
            elif obv_trend < -0.02 and price_trend < 0:
                return 0.7
            elif obv_trend > 0.02 and price_trend < 0:
                return -0.7
            elif obv_trend < -0.02 and price_trend > 0:
                return -0.7
            else:
                return 0.0

        return 0.0

    @staticmethod
    def _normalize_channel(channel_type: str, ind_name: str,
                            val: float, latest: pd.Series) -> float:
        """
        通道类指标归一化：价格接近上轨 = 强势多头，接近下轨 = 弱势。

        channel_upper: 价格/上轨 比率 → 越接近上轨越强
        channel_lower: 价格/下轨 比率 → 越远离下轨越强
        """
        close = latest.get("close", np.nan)
        if pd.isna(close) or pd.isna(val) or val == 0:
            return 0.0

        ratio = close / val

        if channel_type == "upper":
            # 价格接近或突破上轨 → 强势 (0 → +1)
            return max(-1.0, min(1.0, (ratio - 0.95) / 0.15))
        else:
            # 价格远离下轨 → 强势 (0 → +1)
            return max(-1.0, min(1.0, (ratio - 1.0) / 0.15))

    # ===================== 辅助方法 =====================

    @staticmethod
    def _classify_signal(score: float, confidence: float) -> str:
        """根据得分和置信度判定信号"""
        if confidence < 0.3:
            return "NEUTRAL"
        if score > 0.3:
            return "LONG"
        elif score < -0.3:
            return "SHORT"
        else:
            return "NEUTRAL"

    @staticmethod
    def _dimension_consistency(dimensions: List[DimensionScore]) -> float:
        """
        维度间一致性：所有维度方向一致 = 高一致性。
        """
        directions = [d.direction for d in dimensions if d.direction != "NEUTRAL"]
        if len(directions) < 2:
            return 0.5

        bullish = directions.count("BULLISH")
        bearish = directions.count("BEARISH")

        # 方向一致比例
        agreement = max(bullish, bearish) / len(directions)

        return agreement


# ===================== 便捷函数 =====================

def score_symbol(symbol: str, df: pd.DataFrame,
                  weights: Optional[Dict[str, float]] = None) -> MultiDimensionResult:
    """便捷函数：对单个品种进行多维度评分"""
    screener = MultiDimensionScreener(weights=weights)
    return screener.score(symbol, df)


def batch_score(symbols_dfs: List[Tuple[str, pd.DataFrame]],
                 weights: Optional[Dict[str, float]] = None) -> List[MultiDimensionResult]:
    """便捷函数：批量评分"""
    screener = MultiDimensionScreener(weights=weights)
    results = []
    for symbol, df in symbols_dfs:
        results.append(screener.score(symbol, df))
    return results
