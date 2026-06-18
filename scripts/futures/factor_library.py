"""
期货因子库

完全独立的期货因子计算
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FuturesFactorLibrary:
    """
    期货因子库

    计算期货特有的因子：基差、库存、持仓量、期限结构
    """

    def __init__(self):
        """初始化期货因子库"""
        pass

    def calculate_basis_factors(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算基差因子

        Args:
            data: 包含 close 和 spot 列的 DataFrame

        Returns:
            Dict: 基差因子
        """
        factors = {}

        if "close" in data.columns and "spot" in data.columns:
            # 基差
            basis = data["spot"].iloc[-1] - data["close"].iloc[-1]
            factors["basis"] = basis

            # 基差率
            if data["close"].iloc[-1] != 0:
                factors["basis_rate"] = basis / data["close"].iloc[-1]
            else:
                factors["basis_rate"] = 0.0

            # 基差变化率
            if len(data) > 1 and data["close"].iloc[-2] != 0:
                prev_basis = data["spot"].iloc[-2] - data["close"].iloc[-2]
                prev_close = data["close"].iloc[-2]
                factors["basis_change_rate"] = (basis / data["close"].iloc[-1]) - (prev_basis / prev_close)
            else:
                factors["basis_change_rate"] = 0.0
        else:
            factors["basis"] = 0.0
            factors["basis_rate"] = 0.0
            factors["basis_change_rate"] = 0.0

        return factors

    def calculate_inventory_factors(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算库存因子

        Args:
            data: 包含 inventory 列的 DataFrame

        Returns:
            Dict: 库存因子
        """
        factors = {}

        if "inventory" in data.columns and len(data) > 1:
            # 库存变化
            inventory_change = data["inventory"].iloc[-1] - data["inventory"].iloc[-2]
            factors["inventory_change"] = inventory_change

            # 库存变化率
            if data["inventory"].iloc[-2] != 0:
                factors["inventory_change_rate"] = inventory_change / data["inventory"].iloc[-2]
            else:
                factors["inventory_change_rate"] = 0.0

            # 库存趋势（20日均线）
            if len(data) >= 20:
                factors["inventory_ma20"] = data["inventory"].rolling(20).mean().iloc[-1]
                factors["inventory_vs_ma20"] = data["inventory"].iloc[-1] / factors["inventory_ma20"]
            else:
                factors["inventory_ma20"] = data["inventory"].iloc[-1]
                factors["inventory_vs_ma20"] = 1.0
        else:
            factors["inventory_change"] = 0.0
            factors["inventory_change_rate"] = 0.0
            factors["inventory_ma20"] = 0.0
            factors["inventory_vs_ma20"] = 1.0

        return factors

    def calculate_oi_factors(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算持仓量因子

        Args:
            data: 包含 open_interest 列的 DataFrame

        Returns:
            Dict: 持仓量因子
        """
        factors = {}

        if "open_interest" in data.columns and len(data) > 1:
            # 持仓量变化
            oi_change = data["open_interest"].iloc[-1] - data["open_interest"].iloc[-2]
            factors["oi_change"] = oi_change

            # 持仓量变化率
            if data["open_interest"].iloc[-2] != 0:
                factors["oi_change_rate"] = oi_change / data["open_interest"].iloc[-2]
            else:
                factors["oi_change_rate"] = 0.0

            # 持仓量与价格的关系
            price_change = data["close"].iloc[-1] - data["close"].iloc[-2]
            if price_change > 0 and oi_change > 0:
                factors["oi_price_signal"] = 1.0  # 价涨仓增，多头强势
            elif price_change < 0 and oi_change > 0:
                factors["oi_price_signal"] = -1.0  # 价跌仓增，空头强势
            elif price_change > 0 and oi_change < 0:
                factors["oi_price_signal"] = 0.5  # 价涨仓减，空头平仓
            else:
                factors["oi_price_signal"] = -0.5  # 价跌仓减，多头平仓
        else:
            factors["oi_change"] = 0.0
            factors["oi_change_rate"] = 0.0
            factors["oi_price_signal"] = 0.0

        return factors

    def calculate_term_structure_factors(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算期限结构因子

        Args:
            data: 包含 near_price 和 far_price 列的 DataFrame

        Returns:
            Dict: 期限结构因子
        """
        factors = {}

        if "near_price" in data.columns and "far_price" in data.columns:
            near = data["near_price"].iloc[-1]
            far = data["far_price"].iloc[-1]

            # 期限结构价差
            factors["term_spread"] = far - near

            # 期限结构比率
            if near != 0:
                factors["term_ratio"] = far / near
            else:
                factors["term_ratio"] = 1.0

            # Contango/Backwardation
            if far > near:
                factors["term_structure_type"] = 1.0  # Contango
            else:
                factors["term_structure_type"] = -1.0  # Backwardation
        else:
            factors["term_spread"] = 0.0
            factors["term_ratio"] = 1.0
            factors["term_structure_type"] = 0.0

        return factors

    def calculate_trend_factors(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        计算趋势因子

        Args:
            data: 包含 close 列的 DataFrame

        Returns:
            Dict: 趋势因子
        """
        factors = {}

        if "close" in data.columns and len(data) >= 20:
            close = data["close"]
            
            # EMA20
            ema20 = close.ewm(span=20, adjust=False).mean()
            factors["ema20"] = ema20.iloc[-1]
            
            # EMA60
            if len(data) >= 60:
                ema60 = close.ewm(span=60, adjust=False).mean()
                factors["ema60"] = ema60.iloc[-1]
                factors["ema_cross"] = 1.0 if factors["ema20"] > factors["ema60"] else -1.0
            else:
                factors["ema60"] = factors["ema20"]
                factors["ema_cross"] = 0.0
            
            # 价格相对于EMA20的位置
            factors["price_vs_ema20"] = (close.iloc[-1] - factors["ema20"]) / factors["ema20"]
        else:
            factors["ema20"] = 0.0
            factors["ema60"] = 0.0
            factors["ema_cross"] = 0.0
            factors["price_vs_ema20"] = 0.0

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

        if "close" in data.columns and len(data) >= 20:
            close = data["close"]
            
            # 20日动量
            if close.iloc[-20] != 0:
                factors["momentum_20d"] = (close.iloc[-1] / close.iloc[-20]) - 1
            else:
                factors["momentum_20d"] = 0.0
            
            # 60日动量
            if len(data) >= 60 and close.iloc[-60] != 0:
                factors["momentum_60d"] = (close.iloc[-1] / close.iloc[-60]) - 1
            else:
                factors["momentum_60d"] = 0.0
            
            # RSI
            if len(data) >= 15:
                factors["rsi"] = self._calculate_rsi(close, 14)
            else:
                factors["rsi"] = 50.0
        else:
            factors["momentum_20d"] = 0.0
            factors["momentum_60d"] = 0.0
            factors["rsi"] = 50.0

        return factors

    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> float:
        """
        计算RSI

        Args:
            close: 收盘价序列
            period: 周期

        Returns:
            float: RSI值
        """
        deltas = close.diff()
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi
