"""
期货趋势跟踪策略

基于技术指标的趋势跟踪
"""

import logging
from typing import Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class TrendStrategy:
    """
    期货趋势跟踪策略

    基于 EMA/ATR/ADX 的趋势跟踪
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化趋势策略

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.ema_fast = self.config.get("ema_fast", 20)
        self.ema_slow = self.config.get("ema_slow", 60)

    def generate_signal(self, data: pd.DataFrame) -> float:
        """
        生成交易信号

        Args:
            data: K线数据

        Returns:
            float: 交易信号 (-1 到 1)
        """
        if len(data) < self.ema_slow:
            return 0.0

        close = data["close"]

        # 计算EMA
        ema_fast = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.ema_slow, adjust=False).mean()

        # 信号：EMA快线上穿慢线为多头，下穿为空头
        if ema_fast.iloc[-1] > ema_slow.iloc[-1]:
            signal = 0.5
        elif ema_fast.iloc[-1] < ema_slow.iloc[-1]:
            signal = -0.5
        else:
            signal = 0.0

        return signal

    def calculate_stop_loss(
        self,
        entry_price: float,
        signal: float,
        atr: float,
    ) -> float:
        """
        计算止损

        Args:
            entry_price: 入场价格
            signal: 交易信号
            atr: ATR值

        Returns:
            float: 止损价格
        """
        if signal > 0:
            return entry_price - atr * 2
        else:
            return entry_price + atr * 2
