"""
REITs策略

分红收益率、NAV折溢价
"""

import logging
from typing import Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class REITsStrategy:
    """
    REITs策略

    基于分红收益率和NAV折溢价
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化REITs策略

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.min_yield = self.config.get("min_yield", 0.04)

    def generate_signal(self, data: pd.DataFrame) -> float:
        """
        生成交易信号

        Args:
            data: 包含 distribution_yield, nav_premium 列的 DataFrame

        Returns:
            float: 交易信号 (-1 到 1)
        """
        if "distribution_yield" not in data.columns:
            return 0.0

        distribution_yield = data["distribution_yield"].iloc[-1]

        # 分红收益率 > 4% 为买入信号
        if distribution_yield > self.min_yield:
            signal = 0.5
        elif distribution_yield < 0.02:
            signal = -0.5
        else:
            signal = 0.0

        return signal

    def check_nav_premium(self, price: float, nav: float) -> Dict[str, Any]:
        """
        检查NAV折溢价

        Args:
            price: REITs价格
            nav: REITs净资产

        Returns:
            Dict: NAV折溢价信息
        """
        if nav <= 0:
            return {
                "nav_premium": 0.0,
                "is_premium": False,
                "is_discount": False,
                "warning": "",
            }

        nav_premium = (price - nav) / nav

        is_premium = nav_premium > 0.1
        is_discount = nav_premium < -0.1

        warning = ""
        if is_premium:
            warning = f"溢价{nav_premium:.2%}，价格可能偏高"
        elif is_discount:
            warning = f"折价{nav_premium:.2%}，可能存在价值洼地"

        return {
            "nav_premium": nav_premium,
            "is_premium": is_premium,
            "is_discount": is_discount,
            "warning": warning,
        }
