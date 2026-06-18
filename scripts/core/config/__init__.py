"""
配置模块

提供系统配置功能：
- ControlVariable: 控制变量
- TrendScannerConfig: 趋势扫描配置
"""

from .control_variable import ControlVariable
from .trend_scanner_config import TrendScannerConfig

__all__ = [
    "ControlVariable",
    "TrendScannerConfig",
]
