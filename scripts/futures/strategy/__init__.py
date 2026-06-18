"""
期货策略模块

提供期货市场的策略功能
"""

from .trend import TrendStrategy
from .carry import CarryStrategy
from .arbitrage import ArbitrageStrategy

__all__ = [
    "TrendStrategy",
    "CarryStrategy",
    "ArbitrageStrategy",
]
