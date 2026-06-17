"""
交易层模块

提供交易信号生成、执行和仓位管理功能：
- 信号生成（TrendScanner, SignalGenerator）
- 执行引擎（ExecutionEngine, RiskGuard）
- 仓位管理（PositionSizer, StopLossCalculator）
"""

from .signals import TrendScanner, SignalGenerator
from .execution import ExecutionEngine, RiskGuard
from .position import PositionSizer, StopLossCalculator

__all__ = [
    "TrendScanner",
    "SignalGenerator",
    "ExecutionEngine",
    "RiskGuard",
    "PositionSizer",
    "StopLossCalculator",
]
