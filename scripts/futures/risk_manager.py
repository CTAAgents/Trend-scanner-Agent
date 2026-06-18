"""
期货风险管理器

提供期货市场的风险管理功能
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.core.base_risk_manager import BaseRiskManager, RiskLevel, RiskMetrics

logger = logging.getLogger(__name__)


class FuturesRiskManager(BaseRiskManager):
    """
    期货风险管理器

    提供保证金、杠杆、T+0交易的风险管理
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化期货风险管理器

        Args:
            config: 配置字典，包含 margin_rate, leverage 等
        """
        super().__init__(config)
        self.margin_rate = config.get("margin_rate", 0.1)
        self.leverage = config.get("leverage", 10)
        self.atr_stop_multiplier = config.get("atr_stop_multiplier", 2.0)

    def calculate_position_size(
        self,
        signal: float,
        capital: float,
        current_price: float,
    ) -> float:
        """
        计算仓位大小（考虑保证金）

        Args:
            signal: 交易信号 (-1 到 1)
            capital: 可用资金
            current_price: 当前价格

        Returns:
            float: 仓位大小（手数）
        """
        if current_price <= 0:
            return 0.0

        # 每手保证金
        margin_per_lot = current_price * self.margin_rate * 10  # 假设每手10吨

        # 风险资金（信号强度 × 可用资金 × 10%）
        risk_capital = abs(signal) * capital * 0.1

        # 仓位大小（手数）
        position_size = risk_capital / margin_per_lot if margin_per_lot > 0 else 0

        return position_size

    def calculate_stop_loss(
        self,
        entry_price: float,
        signal: float,
        atr: float = None,
    ) -> float:
        """
        计算止损价格

        Args:
            entry_price: 入场价格
            signal: 交易信号 (-1 到 1)
            atr: ATR值（可选）

        Returns:
            float: 止损价格
        """
        if atr is None:
            # 默认使用2%作为止损
            atr = entry_price * 0.02

        # 多头止损：入场价 - ATR × 倍数
        # 空头止损：入场价 + ATR × 倍数
        if signal > 0:
            stop_loss = entry_price - atr * self.atr_stop_multiplier
        else:
            stop_loss = entry_price + atr * self.atr_stop_multiplier

        return stop_loss

    def calculate_take_profit(
        self,
        entry_price: float,
        signal: float,
        atr: float = None,
    ) -> float:
        """
        计算止盈价格

        Args:
            entry_price: 入场价格
            signal: 交易信号 (-1 到 1)
            atr: ATR值（可选）

        Returns:
            float: 止盈价格
        """
        if atr is None:
            # 默认使用3%作为止盈
            atr = entry_price * 0.03

        # 多头止盈：入场价 + ATR × 倍数
        # 空头止盈：入场价 - ATR × 倍数
        if signal > 0:
            take_profit = entry_price + atr * self.atr_stop_multiplier * 1.5
        else:
            take_profit = entry_price - atr * self.atr_stop_multiplier * 1.5

        return take_profit

    def check_stop_loss(
        self,
        position: Dict[str, Any],
        current_price: float,
    ) -> bool:
        """
        检查是否触发止损

        Args:
            position: 持仓信息，包含 stop_loss 和 direction
            current_price: 当前价格

        Returns:
            bool: 是否触发止损
        """
        stop_loss = position.get("stop_loss", 0)
        direction = position.get("direction", 0)

        if direction > 0:  # 多头
            return current_price <= stop_loss
        else:  # 空头
            return current_price >= stop_loss

    def check_take_profit(
        self,
        position: Dict[str, Any],
        current_price: float,
    ) -> bool:
        """
        检查是否触发止盈

        Args:
            position: 持仓信息，包含 take_profit 和 direction
            current_price: 当前价格

        Returns:
            bool: 是否触发止盈
        """
        take_profit = position.get("take_profit", float("inf"))
        direction = position.get("direction", 0)

        if direction > 0:  # 多头
            return current_price >= take_profit
        else:  # 空头
            return current_price <= take_profit

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
        direction = position.get("direction", 0)

        # 计算风险收益比
        if entry_price > 0 and stop_loss > 0 and take_profit > 0:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
        else:
            risk_reward_ratio = 0

        # 计算当前盈亏
        if direction > 0:
            pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0
        else:
            pnl_pct = (entry_price - current_price) / entry_price if entry_price > 0 else 0

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

    def check_margin(
        self,
        position: Dict[str, Any],
        current_price: float,
    ) -> bool:
        """
        检查保证金是否充足

        Args:
            position: 持仓信息
            current_price: 当前价格

        Returns:
            bool: 保证金是否充足
        """
        # 简化实现：检查当前价格是否超过止损价的110%
        stop_loss = position.get("stop_loss", 0)
        direction = position.get("direction", 0)

        if direction > 0:  # 多头
            # 如果价格跌破止损价的90%，保证金可能不足
            return current_price > stop_loss * 0.9
        else:  # 空头
            # 如果价格涨破止损价的110%，保证金可能不足
            return current_price < stop_loss * 1.1

    def check_delivery_month(
        self,
        symbol: str,
        current_date: str,
    ) -> bool:
        """
        检查是否接近交割月

        Args:
            symbol: 品种代码
            current_date: 当前日期

        Returns:
            bool: 是否接近交割月
        """
        # 简化实现：返回False
        # TODO: 实现真实的交割月检查
        return False
