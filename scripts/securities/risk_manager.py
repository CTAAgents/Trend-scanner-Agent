"""
证券风险管理器

提供证券市场的风险管理功能
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


class SecuritiesRiskManager(BaseRiskManager):
    """
    证券风险管理器

    提供T+1交割、涨跌停、流动性等风险管理
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化证券风险管理器

        Args:
            config: 配置字典
        """
        super().__init__(config)
        self.t_plus_1 = config.get("t_plus_1", True)
        self.limit_up_pct = config.get("limit_up_pct", 0.1)
        self.min_trade_unit = config.get("min_trade_unit", 100)

    def calculate_position_size(
        self,
        signal: float,
        capital: float,
        current_price: float,
    ) -> float:
        """
        计算仓位大小（全额资金）

        Args:
            signal: 交易信号 (-1 到 1)
            capital: 可用资金
            current_price: 当前价格

        Returns:
            float: 仓位大小（股数）
        """
        if current_price <= 0:
            return 0.0

        # 风险资金（信号强度 × 可用资金 × 10%）
        risk_capital = abs(signal) * capital * 0.1

        # 仓位大小（股数，取整到100股）
        position_size = risk_capital / current_price
        position_size = (position_size // self.min_trade_unit) * self.min_trade_unit

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
            # 默认使用5%作为止损
            atr = entry_price * 0.05

        # 多头止损：入场价 - ATR
        # 空头止损：入场价 + ATR
        if signal > 0:
            stop_loss = entry_price - atr
        else:
            stop_loss = entry_price + atr

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
            # 默认使用10%作为止盈
            atr = entry_price * 0.1

        # 多头止盈：入场价 + 2×ATR
        # 空头止盈：入场价 - 2×ATR
        if signal > 0:
            take_profit = entry_price + atr * 2
        else:
            take_profit = entry_price - atr * 2

        return take_profit

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
            position: 持仓信息
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

    def check_t_plus_1(self, trade_date: str) -> bool:
        """
        检查T+1限制

        Args:
            trade_date: 交易日期

        Returns:
            bool: 是否允许T+1交易
        """
        # 简化实现：返回True（允许交易）
        # TODO: 实现真实的T+1检查
        return True

    def check_limit(self, price: float, prev_close: float) -> bool:
        """
        检查涨跌停

        Args:
            price: 当前价格
            prev_close: 昨收价

        Returns:
            bool: 是否涨停
        """
        if prev_close <= 0:
            return False

        change_pct = (price - prev_close) / prev_close
        return change_pct >= self.limit_up_pct
