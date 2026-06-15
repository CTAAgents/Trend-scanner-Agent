"""
Benchmark 共享 fixtures

为性能基准测试提供：
- 真实 OHLCV 期货数据生成（GBM 模型）
- 技术指标 DataFrame（已计算所有指标）
- 因子知识库数据
- 模拟交易历史

创建日期：2026-06-15
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import pandas as pd
import pytest

# ── 项目根目录 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# OHLCV 数据生成
# ============================================================

def _generate_ohlcv_gbm(
    n_rows: int,
    initial_price: float = 4000.0,
    annual_vol: float = 0.25,
    annual_drift: float = 0.02,
    seed: int = 42,
) -> pd.DataFrame:
    """
    用几何布朗运动生成逼真的期货 OHLCV 数据。

    Args:
        n_rows: K线根数
        initial_price: 起始价格
        annual_vol: 年化波动率（默认 25%）
        annual_drift: 年化漂移率（默认 2%）
        seed: 随机种子，保证可复现

    Returns:
        pd.DataFrame: 包含 open, high, low, close, volume, date 列
    """
    rng = np.random.RandomState(seed)
    dt = 1 / 252  # 每根 K 线 = 1 个交易日

    # GBM 收益率
    returns = (annual_drift - 0.5 * annual_vol**2) * dt \
              + annual_vol * np.sqrt(dt) * rng.randn(n_rows)

    close = initial_price * np.exp(np.cumsum(returns))

    # 从 close 派生 open / high / low
    noise = rng.uniform(0.002, 0.012, n_rows)  # 0.2% ~ 1.2% 的盘中波动
    open_prices = close * (1 + rng.uniform(-0.005, 0.005, n_rows))
    high = np.maximum(open_prices, close) * (1 + noise)
    low = np.minimum(open_prices, close) * (1 - noise)

    # 成交量：对数正态 + 与价格变化正相关
    base_volume = rng.lognormal(mean=15.0, sigma=0.5, size=n_rows)
    volume_factor = 1 + np.abs(returns) * 20
    volume = (base_volume * volume_factor).astype(int)

    # 日期序列
    dates = pd.bdate_range(start="2024-01-02", periods=n_rows, freq="B")

    df = pd.DataFrame({
        "date": dates,
        "open": np.round(open_prices, 1),
        "high": np.round(high, 1),
        "low": np.round(low, 1),
        "close": np.round(close, 1),
        "volume": volume,
    })
    return df


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def ohlcv_120() -> pd.DataFrame:
    """120 根 K 线的 OHLCV 期货数据（标准测试规模）"""
    return _generate_ohlcv_gbm(n_rows=120)


@pytest.fixture
def ohlcv_200() -> pd.DataFrame:
    """200 根 K 线的 OHLCV 数据（覆盖更多指标的 lookback）"""
    return _generate_ohlcv_gbm(n_rows=200)


@pytest.fixture
def ohlcv_500() -> pd.DataFrame:
    """500 根 K 线的 OHLCV 数据（压力测试）"""
    return _generate_ohlcv_gbm(n_rows=500)


@pytest.fixture
def indicator_df_120() -> pd.DataFrame:
    """120 根 K 线 + 全部技术指标的 DataFrame（用于 TrendPhaseDetector 等）"""
    from scripts.trend_scanner.indicators import IndicatorEngine
    df = _generate_ohlcv_gbm(n_rows=120)
    engine = IndicatorEngine(df)
    return engine.compute_all()


@pytest.fixture
def indicator_df_200() -> pd.DataFrame:
    """200 根 K 线 + 全部技术指标"""
    from scripts.trend_scanner.indicators import IndicatorEngine
    df = _generate_ohlcv_gbm(n_rows=200)
    engine = IndicatorEngine(df)
    return engine.compute_all()


@pytest.fixture
def trade_history_50() -> List[Dict[str, Any]]:
    """50 笔模拟交易历史（用于 TrajectoryAnalyzer）"""
    rng = np.random.RandomState(123)
    records: List[Dict[str, Any]] = []
    market_states = ["trending", "ranging", "volatile"]
    trend_phases = ["DEVELOPING", "MATURE", "EXHAUSTING"]
    vol_levels = ["low", "medium", "high"]
    failure_reasons = ["止损过紧", "入场过早", "趋势反转", "假突破", None]

    for i in range(50):
        is_win = rng.random() > 0.4  # 60% 胜率
        entry_price = 1500.0 + rng.uniform(-200, 200)
        if is_win:
            pnl_pct = rng.uniform(1.0, 6.0)
            exit_price = entry_price * (1 + pnl_pct / 100)
            pnl = exit_price - entry_price
            failure_reason = None
        else:
            pnl_pct = rng.uniform(-5.0, -0.5)
            exit_price = entry_price * (1 + pnl_pct / 100)
            pnl = exit_price - entry_price
            failure_reason = failure_reasons[rng.randint(0, len(failure_reasons) - 1)]

        records.append({
            "trade_id": f"B{i:04d}",
            "symbol": "CZCE.SR509",
            "direction": "LONG" if i % 2 == 0 else "SHORT",
            "entry_price": round(entry_price, 1),
            "exit_price": round(exit_price, 1),
            "entry_time": f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T09:00:00",
            "exit_time": f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T15:00:00",
            "pnl": round(pnl, 2),
            "pnl_percent": round(pnl_pct, 2),
            "holding_period": rng.randint(1, 10),
            "market_state": market_states[i % 3],
            "trend_phase": trend_phases[i % 3],
            "volatility": vol_levels[i % 3],
            "er": round(rng.uniform(0.2, 0.9), 2),
            "tsi": round(rng.uniform(-40, 40), 2),
            "rsi": round(rng.uniform(25, 75), 1),
            "adx": round(rng.uniform(12, 45), 1),
            "max_drawdown": round(rng.uniform(0.5, 5.0), 2),
            "sharpe_ratio": round(rng.uniform(-1.0, 2.5), 2),
            "failure_reason": failure_reason,
        })
    return records


@pytest.fixture
def factor_code() -> str:
    """
    一个可执行的因子代码字符串（动量突破因子）。

    从 data/factor_knowledge.json 的 factor_001 复制，
    保证 benchmark 不依赖文件 I/O。
    """
    return (
        'def factor(df: pd.DataFrame) -> pd.Series:\n'
        '    """动量突破因子"""\n'
        '    import pandas as pd\n'
        '    returns = df["close"].pct_change(5)\n'
        '    volume_ratio = df["volume"] / df["volume"].rolling(20).mean()\n'
        '    factor_value = returns * volume_ratio\n'
        '    max_abs = factor_value.abs().max()\n'
        '    if max_abs > 0:\n'
        '        factor_value = factor_value / max_abs\n'
        '    return factor_value\n'
    )
