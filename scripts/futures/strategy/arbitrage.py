"""
期货套利策略

跨期套利和跨品种套利
"""

import logging
from typing import Dict, Any, List

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class ArbitrageStrategy:
    """
    期货套利策略

    跨期套利：不同月份合约价差交易
    跨品种套利：相关品种价差交易
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化套利策略

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.zscore_threshold = self.config.get("zscore_threshold", 2.0)

    def generate_spread_signal(
        self,
        spread_series: pd.Series,
    ) -> float:
        """
        生成价差信号

        Args:
            spread_series: 价差序列

        Returns:
            float: 交易信号 (-1 到 1)
        """
        if len(spread_series) < 20:
            return 0.0

        # 计算Z-score
        mean = spread_series.mean()
        std = spread_series.std()

        if std == 0:
            return 0.0

        zscore = (spread_series.iloc[-1] - mean) / std

        # 信号：Z-score超过阈值时反向操作
        if zscore > self.zscore_threshold:
            signal = -0.5  # 价差过高，做空价差
        elif zscore < -self.zscore_threshold:
            signal = 0.5  # 价差过低，做多价差
        else:
            signal = 0.0

        return signal

    def calculate_hedge_ratio(
        self,
        price_series_1: pd.Series,
        price_series_2: pd.Series,
    ) -> float:
        """
        计算对冲比率

        Args:
            price_series_1: 品种1价格序列
            price_series_2: 品种2价格序列

        Returns:
            float: 对冲比率
        """
        # 使用OLS回归计算对冲比率
        if len(price_series_1) < 2 or len(price_series_2) < 2:
            return 1.0

        # 计算收益率
        returns_1 = price_series_1.pct_change().dropna()
        returns_2 = price_series_2.pct_change().dropna()

        # 对齐数据
        min_len = min(len(returns_1), len(returns_2))
        returns_1 = returns_1.iloc[-min_len:]
        returns_2 = returns_2.iloc[-min_len:]

        # OLS回归
        cov = np.cov(returns_1, returns_2)
        if cov[1, 1] == 0:
            return 1.0

        hedge_ratio = cov[0, 1] / cov[1, 1]

        return hedge_ratio
