"""
策略池模块

提供多策略并行生成信号和投票聚合：
- StrategyPool: 策略池，运行多个子策略并聚合信号
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


class StrategyPool:
    """策略池：并行运行多个子策略，输出投票"""

    def __init__(self, df: pd.DataFrame, weights: Optional[Dict[str, float]] = None):
        self.df = df
        self.votes = {}
        self.weights = weights or {
            'DONCHIAN': 0.25, 'MA_CROSS': 0.20, 'MACD': 0.15,
            'TRIPLE_MA': 0.10, 'SWING_STRUCT': 0.15, 'BB_SQUEEZE': 0.10,
            'ADX_PCT': 0.05  # ADX 相对位置策略
        }

    def strategy_ma_cross(self, fast: int = 20, slow: int = 60) -> int:
        if len(self.df) < slow + 2:
            return 0
        ema_fast = self.df[f'ema{fast}']
        ema_slow = self.df[f'ema{slow}']
        curr = ema_fast.iloc[-1] > ema_slow.iloc[-1]
        prev = ema_fast.iloc[-2] > ema_slow.iloc[-2]
        if curr and not prev:
            return 1
        elif not curr and prev:
            return -1
        return 0

    def strategy_triple_ma(self) -> int:
        """
        三均线策略（已简化为双均线 + 高低点结构）

        原策略使用 EMA20/60/200 三重排列，但 EMA200 反应太慢，
        已移除。现在使用 EMA20/60 排列 + 高低点结构确认。
        """
        if len(self.df) < 3:
            return 0
        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        ema20, ema60 = latest['ema20'], latest['ema60']
        p20, p60 = prev['ema20'], prev['ema60']

        # 均线排列确认
        aligned_now = ema20 > ema60 or ema20 < ema60
        aligned_prev = p20 > p60 or p20 < p60

        if not aligned_now:
            return 0

        # 检查高低点结构确认
        swing = latest.get('swing_structure', 'NEUTRAL')

        # 多头：EMA20上穿EMA60 + 高低点结构为BULLISH
        if ema20 > ema60 and not (p20 > p60):
            if swing == 'BULLISH':
                return 1  # 强信号：均线金叉 + 高低点确认
            return 1  # 普通信号：均线金叉

        # 空头：EMA20下穿EMA60 + 高低点结构为BEARISH
        if ema20 < ema60 and not (p20 < p60):
            if swing == 'BEARISH':
                return -1  # 强信号：均线死叉 + 高低点确认
            return -1  # 普通信号：均线死叉

        # 已排列：保持方向
        if ema20 > ema60:
            return 1
        else:
            return -1

    def strategy_donchian(self, period: int = 20) -> int:
        if len(self.df) < period + 2:
            return 0
        upper = self.df['high'].rolling(period).max()
        lower = self.df['low'].rolling(period).min()
        close = self.df['close']
        if close.iloc[-1] >= upper.iloc[-1] and close.iloc[-2] < upper.iloc[-2]:
            return 1
        if close.iloc[-1] <= lower.iloc[-1] and close.iloc[-2] > lower.iloc[-2]:
            return -1
        return 0

    def strategy_macd(self) -> int:
        if len(self.df) < 3 or 'macd' not in self.df.columns:
            return 0
        macd = self.df['macd']
        signal = self.df['macd_signal']
        curr_cross = macd.iloc[-1] > signal.iloc[-1]
        prev_cross = macd.iloc[-2] > signal.iloc[-2]
        above_zero = macd.iloc[-1] > 0
        if curr_cross and not prev_cross and above_zero:
            return 1
        if not curr_cross and prev_cross and not above_zero:
            return -1
        return 0

    def strategy_swing_structure(self, lookback: int = 20) -> int:
        if len(self.df) < lookback * 2:
            return 0
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']
        recent_high = high.iloc[-lookback:].max()
        recent_low = low.iloc[-lookback:].min()
        prev_high = high.iloc[-lookback * 2:-lookback].max()
        prev_low = low.iloc[-lookback * 2:-lookback].min()
        if close.iloc[-1] > recent_high and recent_low > prev_low:
            return 1
        if close.iloc[-1] < recent_low and recent_high < prev_high:
            return -1
        return 0

    def strategy_bollinger_squeeze(self, squeeze_threshold: float = 0.05) -> int:
        if 'bb_width' not in self.df.columns or len(self.df) < 120:
            return 0
        bw = self.df['bb_width']
        close = self.df['close']
        upper = self.df['bb_upper']
        lower = self.df['bb_lower']
        is_squeeze = bw.iloc[-1] < squeeze_threshold
        is_lowest = bw.iloc[-1] == bw.iloc[-120:].min()
        if is_squeeze and is_lowest:
            if close.iloc[-1] > upper.iloc[-1]:
                return 1
            elif close.iloc[-1] < lower.iloc[-1]:
                return -1
        return 0

    def strategy_adx_pct(self, entry_threshold: float = 0.65, exit_threshold: float = 0.5) -> int:
        """
        ADX 相对位置策略（滚动历史分位数）

        核心逻辑：
        1. ADX_Pct >= 0.65 且 +DI > -DI → 多头趋势确认
        2. ADX_Pct >= 0.65 且 -DI > +DI → 空头趋势确认
        3. ADX_Pct < 0.5 → 趋势强度衰减，离场信号

        参数:
            entry_threshold: 入场阈值（默认0.65）
            exit_threshold: 离场阈值（默认0.5）
        """
        if 'adx_pct' not in self.df.columns or 'plus_di' not in self.df.columns:
            return 0

        latest = self.df.iloc[-1]
        adx_pct = latest.get('adx_pct', 0)
        adx = latest.get('adx', 0)
        plus_di = latest.get('plus_di', 0)
        minus_di = latest.get('minus_di', 0)

        if pd.isna(adx_pct) or pd.isna(adx):
            return 0

        # 双重过滤：相对位置 + 绝对值保底
        if adx_pct >= entry_threshold and adx >= 18:
            if plus_di > minus_di:
                return 1  # 多头趋势确认
            elif minus_di > plus_di:
                return -1  # 空头趋势确认

        # 趋势衰减离场
        if adx_pct < exit_threshold:
            return 0  # 观望/离场信号

        return 0

    def run_all(self) -> Tuple[str, int, Dict[str, str], List[str]]:
        strategies = {
            'MA_CROSS': self.strategy_ma_cross(),
            'TRIPLE_MA': self.strategy_triple_ma(),
            'DONCHIAN': self.strategy_donchian(),
            'MACD': self.strategy_macd(),
            'SWING_STRUCT': self.strategy_swing_structure(),
            'BB_SQUEEZE': self.strategy_bollinger_squeeze(),
            'ADX_PCT': self.strategy_adx_pct(),  # ADX 相对位置策略
        }

        # 加权投票
        weighted_buy = sum(self.weights.get(k, 0) for k, v in strategies.items() if v == 1)
        weighted_sell = sum(self.weights.get(k, 0) for k, v in strategies.items() if v == -1)

        buy_votes = sum(1 for v in strategies.values() if v == 1)
        sell_votes = sum(1 for v in strategies.values() if v == -1)
        total_active = sum(1 for v in strategies.values() if v != 0)

        vote_labels = {k: ('看多' if v == 1 else ('看空' if v == -1 else '观望'))
                       for k, v in strategies.items()}

        evidence = []
        for name, vote in strategies.items():
            if vote != 0:
                evidence.append(f"{name}: {'做多' if vote == 1 else '做空'}")

        # 加权信号判定（使用权重阈值）
        if weighted_buy >= 0.40 and sell_votes <= 1:
            return "BUY", 90, vote_labels, evidence
        elif weighted_buy >= 0.30 and sell_votes <= 1:
            return "BUY", 70, vote_labels, evidence
        elif weighted_sell >= 0.40 and buy_votes <= 1:
            return "SELL", 90, vote_labels, evidence
        elif weighted_sell >= 0.30 and buy_votes <= 1:
            return "SELL", 70, vote_labels, evidence
        elif total_active >= 4 and abs(buy_votes - sell_votes) <= 1:
            return "HOLD", 30, vote_labels, evidence + ["策略分歧大，观望"]
        else:
            return "HOLD", 20, vote_labels, evidence


# ===========================================================================
