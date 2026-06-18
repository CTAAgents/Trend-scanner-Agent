"""
可转债策略

双低策略、转股套利
"""

import logging
from typing import Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class ConvertibleBondStrategy:
    """
    可转债策略

    双低策略：低转股溢价率 + 低纯债溢价率
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化可转债策略

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.max_conversion_premium = self.config.get("max_conversion_premium", 0.2)

    def generate_signal(self, data: pd.DataFrame) -> float:
        """
        生成交易信号

        Args:
            data: 包含 conversion_premium, pure_bond_value, current_price 列的 DataFrame

        Returns:
            float: 交易信号 (-1 到 1)
        """
        if "conversion_premium" not in data.columns:
            return 0.0

        conversion_premium = data["conversion_premium"].iloc[-1]

        # 转股溢价率 < 20% 为买入信号
        if conversion_premium < self.max_conversion_premium:
            signal = 0.5
        elif conversion_premium > 0.5:
            signal = -0.5
        else:
            signal = 0.0

        return signal

    def calculate_double_low_score(
        self,
        conversion_premium: float,
        bond_premium: float,
    ) -> float:
        """
        计算双低分数

        Args:
            conversion_premium: 转股溢价率
            bond_premium: 纯债溢价率

        Returns:
            float: 双低分数（越低越好）
        """
        # 双低分数 = 转股溢价率 + 纯债溢价率
        return conversion_premium + bond_premium
