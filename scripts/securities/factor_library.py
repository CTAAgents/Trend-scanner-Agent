"""
证券因子库

完全独立的证券因子计算
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SecuritiesFactorLibrary:
    """
    证券因子库

    计算证券特有的因子：估值、质量、情绪、动量
    """

    def __init__(self):
        """初始化证券因子库"""
        pass

    def calculate_valuation_factors(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算估值因子

        Args:
            data: 包含 pe, pb, roe 列的 DataFrame

        Returns:
            Dict: 估值因子
        """
        factors = {}

        if "pe" in data.columns and len(data) > 0:
            # PE分位数
            pe = data["pe"].iloc[-1]
            pe_percentile = (data["pe"] < pe).mean()
            factors["pe_percentile"] = pe_percentile

            # PE变化率
            if len(data) > 1 and data["pe"].iloc[-2] != 0:
                factors["pe_change_rate"] = (pe - data["pe"].iloc[-2]) / data["pe"].iloc[-2]
            else:
                factors["pe_change_rate"] = 0.0
        else:
            factors["pe_percentile"] = 0.5
            factors["pe_change_rate"] = 0.0

        if "pb" in data.columns and len(data) > 0:
            # PB分位数
            pb = data["pb"].iloc[-1]
            pb_percentile = (data["pb"] < pb).mean()
            factors["pb_percentile"] = pb_percentile
        else:
            factors["pb_percentile"] = 0.5

        if "roe" in data.columns and len(data) > 0:
            # ROE趋势
            factors["roe"] = data["roe"].iloc[-1]
            if len(data) >= 4:
                factors["roe_trend"] = data["roe"].iloc[-1] - data["roe"].iloc[-4]
            else:
                factors["roe_trend"] = 0.0
        else:
            factors["roe"] = 0.0
            factors["roe_trend"] = 0.0

        return factors

    def calculate_quality_factors(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算质量因子

        Args:
            data: 包含 roe, debt_ratio, current_ratio 列的 DataFrame

        Returns:
            Dict: 质量因子
        """
        factors = {}

        if "roe" in data.columns and len(data) > 0:
            # ROE稳定性
            if len(data) >= 4:
                factors["roe_stability"] = 1.0 - data["roe"].iloc[-4:].std() / max(abs(data["roe"].iloc[-4:].mean()), 0.01)
            else:
                factors["roe_stability"] = 1.0
        else:
            factors["roe_stability"] = 0.5

        if "debt_ratio" in data.columns and len(data) > 0:
            # 资产负债率
            factors["debt_ratio"] = data["debt_ratio"].iloc[-1]
            # 低负债率更好
            factors["debt_quality"] = 1.0 - min(data["debt_ratio"].iloc[-1] / 100, 1.0)
        else:
            factors["debt_ratio"] = 0.5
            factors["debt_quality"] = 0.5

        if "current_ratio" in data.columns and len(data) > 0:
            # 流动比率
            factors["current_ratio"] = data["current_ratio"].iloc[-1]
            # 流动比率 > 1.5 更好
            factors["liquidity_quality"] = min(data["current_ratio"].iloc[-1] / 1.5, 1.0)
        else:
            factors["current_ratio"] = 1.0
            factors["liquidity_quality"] = 0.5

        return factors

    def calculate_sentiment_factors(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算情绪因子

        Args:
            data: 包含 turnover_rate, volume 列的 DataFrame

        Returns:
            Dict: 情绪因子
        """
        factors = {}

        if "turnover_rate" in data.columns and len(data) > 0:
            # 换手率
            factors["turnover_rate"] = data["turnover_rate"].iloc[-1]
            # 高换手率可能表示情绪过热
            factors["turnover_sentiment"] = min(data["turnover_rate"].iloc[-1] / 10, 1.0)
        else:
            factors["turnover_rate"] = 0.0
            factors["turnover_sentiment"] = 0.5

        if "volume" in data.columns and len(data) >= 20:
            # 成交量相对强度
            vol_ma20 = data["volume"].rolling(20).mean().iloc[-1]
            if vol_ma20 > 0:
                factors["volume_ratio"] = data["volume"].iloc[-1] / vol_ma20
            else:
                factors["volume_ratio"] = 1.0
        else:
            factors["volume_ratio"] = 1.0

        return factors

    def calculate_momentum_factors(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算动量因子

        Args:
            data: 包含 close 列的 DataFrame

        Returns:
            Dict: 动量因子
        """
        factors = {}

        if "close" in data.columns and len(data) >= 5:
            close = data["close"]

            # 5日动量
            if close.iloc[-5] != 0:
                factors["momentum_5d"] = (close.iloc[-1] / close.iloc[-5]) - 1
            else:
                factors["momentum_5d"] = 0.0

            # 20日动量
            if len(data) >= 20 and close.iloc[-20] != 0:
                factors["momentum_20d"] = (close.iloc[-1] / close.iloc[-20]) - 1
            else:
                factors["momentum_20d"] = 0.0

            # 60日动量
            if len(data) >= 60 and close.iloc[-60] != 0:
                factors["momentum_60d"] = (close.iloc[-1] / close.iloc[-60]) - 1
            else:
                factors["momentum_60d"] = 0.0
        else:
            factors["momentum_5d"] = 0.0
            factors["momentum_20d"] = 0.0
            factors["momentum_60d"] = 0.0

        return factors
