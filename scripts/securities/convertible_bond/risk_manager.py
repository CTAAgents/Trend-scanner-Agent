"""
可转债风险管理器

提供可转债特有的风险管理功能，关联正股
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.core.base_risk_manager import BaseRiskManager, RiskLevel, RiskMetrics

logger = logging.getLogger(__name__)


class ConvertibleBondRiskManager(BaseRiskManager):
    """
    可转债风险管理器

    提供强赎监控、转股风险、下修风险等
    关联正股价格
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化可转债风险管理器

        Args:
            config: 配置字典
        """
        super().__init__(config)
        self.forced_redemption_threshold = config.get("forced_redemption_threshold", 0.3)
        self.conversion_price_change_threshold = config.get("conversion_price_change_threshold", 0.1)

    def calculate_position_size(
        self,
        signal: float,
        capital: float,
        current_price: float,
    ) -> float:
        """
        计算仓位大小

        Args:
            signal: 交易信号
            capital: 可用资金
            current_price: 当前价格

        Returns:
            float: 仓位大小
        """
        if current_price <= 0:
            return 0.0

        # 可转债最小交易单位为10张
        risk_capital = abs(signal) * capital * 0.1
        position_size = risk_capital / current_price
        position_size = (position_size // 10) * 10

        return position_size

    def calculate_stop_loss(
        self,
        entry_price: float,
        signal: float,
    ) -> float:
        """
        计算止损价格

        Args:
            entry_price: 入场价格
            signal: 交易信号

        Returns:
            float: 止损价格
        """
        # 可转债止损：入场价 - 5%
        return entry_price * 0.95

    def calculate_take_profit(
        self,
        entry_price: float,
        signal: float,
    ) -> float:
        """
        计算止盈价格

        Args:
            entry_price: 入场价格
            signal: 交易信号

        Returns:
            float: 止盈价格
        """
        # 可转债止盈：入场价 + 15%
        return entry_price * 1.15

    def check_stop_loss(
        self,
        position: Dict[str, Any],
        current_price: float,
    ) -> bool:
        """
        检查是否触发止损

        Args:
            position: 持仓信息
            current_price: 当前价格

        Returns:
            bool: 是否触发止损
        """
        stop_loss = position.get("stop_loss", 0)
        return current_price <= stop_loss

    def check_take_profit(
        self,
        position: Dict[str, Any],
        current_price: float,
    ) -> bool:
        """
        检查是否触发止盈

        Args:
            position: 持仓信息
            current_price: 当前价格

        Returns:
            bool: 是否触发止盈
        """
        take_profit = position.get("take_profit", float("inf"))
        return current_price >= take_profit

    def get_risk_metrics(
        self,
        position: Dict[str, Any],
        current_price: float,
    ) -> RiskMetrics:
        """
        获取风险指标

        Args:
            position: 持仓信息
            current_price: 当前价格

        Returns:
            RiskMetrics: 风险指标
        """
        position_size = position.get("position_size", 0)
        entry_price = position.get("entry_price", 0)
        stop_loss = position.get("stop_loss", 0)
        take_profit = position.get("take_profit", 0)

        # 计算风险收益比
        if entry_price > 0 and stop_loss > 0 and take_profit > 0:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
        else:
            risk_reward_ratio = 0

        # 计算当前盈亏
        pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0

        # 评估风险等级
        if pnl_pct < -0.05:
            risk_level = RiskLevel.CRITICAL
        elif pnl_pct < -0.03:
            risk_level = RiskLevel.HIGH
        elif pnl_pct < -0.01:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # 生成警告
        warnings = []
        if self.check_stop_loss(position, current_price):
            warnings.append("触发止损")
        if self.check_take_profit(position, current_price):
            warnings.append("触发止盈")

        return RiskMetrics(
            position_size=position_size,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            risk_reward_ratio=risk_reward_ratio,
            max_drawdown=abs(min(0, pnl_pct)),
            risk_level=risk_level,
            warnings=warnings,
        )

    def check_forced_redemption(
        self,
        bond_price: float,
        stock_price: float,
        conversion_price: float,
    ) -> Dict[str, Any]:
        """
        检查强赎风险

        Args:
            bond_price: 可转债价格
            stock_price: 正股价格
            conversion_price: 转股价

        Returns:
            Dict: 强赎风险信息
        """
        if conversion_price <= 0:
            return {"risk": False, "reason": "转股价无效"}

        # 转股价值
        conversion_value = stock_price / conversion_price * 100

        # 强赎条件：正股价格连续30天超过转股价的130%
        stock_ratio = stock_price / conversion_price

        if stock_ratio > self.forced_redemption_threshold + 1:
            return {
                "risk": True,
                "reason": f"正股价格是转股价的{stock_ratio:.2%}，可能触发强赎",
                "conversion_value": conversion_value,
            }

        return {
            "risk": False,
            "reason": "未触发强赎条件",
            "conversion_value": conversion_value,
        }

    def check_conversion_risk(
        self,
        stock_price: float,
        conversion_price: float,
    ) -> Dict[str, Any]:
        """
        检查转股风险

        Args:
            stock_price: 正股价格
            conversion_price: 转股价

        Returns:
            Dict: 转股风险信息
        """
        if conversion_price <= 0:
            return {"risk": False, "reason": "转股价无效"}

        # 转股溢价率
        conversion_premium = (conversion_price - stock_price) / stock_price

        if conversion_premium < 0:
            return {
                "risk": True,
                "reason": f"转股溢价率为负({conversion_premium:.2%})，建议转股",
                "conversion_premium": conversion_premium,
            }

        return {
            "risk": False,
            "reason": "转股溢价率为正",
            "conversion_premium": conversion_premium,
        }
