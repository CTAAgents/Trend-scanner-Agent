"""
期货 Carry 策略

基于期限结构的套利策略
"""

import logging
from typing import Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class CarryStrategy:
    """
    期货 Carry 策略

    基于 Contango/Backwardation 的展期收益
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化 Carry 策略

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.threshold = self.config.get("threshold", 0.02)

    def generate_signal(
        self,
        near_price: float,
        far_price: float,
    ) -> float:
        """
        生成交易信号

        Args:
            near_price: 近月价格
            far_price: 远月价格

        Returns:
            float: 交易信号 (-1 到 1)
        """
        # 计算展期收益率
        if near_price == 0:
            return 0.0

        roll_yield = (far_price - near_price) / near_price

        # Contango（远月升水）：做空近月，做多远月
        # Backwardation（远月贴水）：做多近月，做空远月
        if roll_yield > self.threshold:
            # Contango，预期价格下跌
            signal = -0.5
        elif roll_yield < -self.threshold:
            # Backwardation，预期价格上涨
            signal = 0.5
        else:
            signal = 0.0

        return signal
