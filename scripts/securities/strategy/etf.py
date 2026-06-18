"""
ETF策略

趋势跟踪，不做套利
"""

import logging
from typing import Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class ETFStrategy:
    """
    ETF策略

    趋势跟踪，不做套利
    推理时提示溢价折价风险
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化ETF策略

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.premium_threshold = self.config.get("premium_threshold", 0.02)

    def generate_signal(self, data: pd.DataFrame) -> float:
        """
        生成交易信号

        Args:
            data: 包含 close, nav 列的 DataFrame

        Returns:
            float: 交易信号 (-1 到 1)
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

    def check_premium_discount(self, price: float, nav: float) -> Dict[str, Any]:
        """
        检查折溢价风险

        Args:
            price: ETF价格
            nav: ETF净值

        Returns:
            Dict: 折溢价信息
        """
        if nav <= 0:
            return {
                "premium_discount": 0.0,
                "is_premium": False,
                "is_discount": False,
                "warning": "",
            }

        premium_discount = (price - nav) / nav

        is_premium = premium_discount > self.premium_threshold
        is_discount = premium_discount < -self.premium_threshold

        warning = ""
        if is_premium:
            warning = f"溢价{premium_discount:.2%}，建议等待折价时买入"
        elif is_discount:
            warning = f"折价{premium_discount:.2%}，可能存在套利机会"

        return {
            "premium_discount": premium_discount,
            "is_premium": is_premium,
            "is_discount": is_discount,
            "warning": warning,
        }
