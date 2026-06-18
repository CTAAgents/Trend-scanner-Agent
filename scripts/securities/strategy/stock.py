"""
股票策略

价值投资、成长股、动量策略
"""

import logging
from typing import Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class StockStrategy:
    """
    股票策略

    支持价值投资、成长股、动量策略
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化股票策略

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.strategy_type = self.config.get("strategy_type", "value")

    def generate_signal(self, data: pd.DataFrame) -> float:
        """
        生成交易信号

        Args:
            data: 包含 pe, pb, roe, close 等列的 DataFrame

        Returns:
            float: 交易信号 (-1 到 1)
        """
        if self.strategy_type == "value":
            return self._value_signal(data)
        elif self.strategy_type == "growth":
            return self._growth_signal(data)
        elif self.strategy_type == "momentum":
            return self._momentum_signal(data)
        else:
            return 0.0

    def _value_signal(self, data: pd.DataFrame) -> float:
        """
        价值投资信号

        低PE、低PB、高ROE
        """
        if "pe" not in data.columns or "pb" not in data.columns:
            return 0.0

        pe = data["pe"].iloc[-1]
        pb = data["pb"].iloc[-1]

        # PE < 15 且 PB < 2 为买入信号
        if pe < 15 and pb < 2:
            signal = 0.5
        elif pe > 25 or pb > 3:
            signal = -0.5
        else:
            signal = 0.0

        return signal

    def _growth_signal(self, data: pd.DataFrame) -> float:
        """
        成长股信号

        高营收增速、高净利润增速
        """
        if "revenue_growth" not in data.columns:
            return 0.0

        revenue_growth = data["revenue_growth"].iloc[-1]

        # 营收增速 > 20% 为买入信号
        if revenue_growth > 0.2:
            signal = 0.5
        elif revenue_growth < 0:
            signal = -0.5
        else:
            signal = 0.0

        return signal

    def _momentum_signal(self, data: pd.DataFrame) -> float:
        """
        动量信号

        价格动量
        """
        if "close" not in data.columns or len(data) < 20:
            return 0.0

        close = data["close"]
        ma20 = close.rolling(20).mean().iloc[-1]

        # 价格在MA20上方为多头信号
        if close.iloc[-1] > ma20:
            signal = 0.5
        else:
            signal = -0.5

        return signal
