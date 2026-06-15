"""
组合管理模块

提供多品种仓位管理、组合风险控制等功能：
- PortfolioManager: 组合管理器
- PositionSizer: 仓位计算器
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


class PortfolioManager:
    """
    组合管理器（7.3）

    管理多品种仓位，控制组合风险：
    - 品种间仓位上限
    - 总敞口帽
    - 波动率调整
    """

    def __init__(self, max_gross: float = 2.0,
                 max_single: float = 0.3,
                 target_vol: float = 0.20):
        """
        参数:
            max_gross: 最大总敞口（sum(|pos_i|)）
            max_single: 单品种最大仓位
            target_vol: 目标年化波动率
        """
        self.max_gross = max_gross
        self.max_single = max_single
        self.target_vol = target_vol

    def calc_position_sizes(self, signals: Dict[str, float],
                            volatilities: Dict[str, float],
                            correlations: pd.DataFrame = None) -> Dict[str, float]:
        """
        计算各品种仓位大小

        参数:
            signals: 各品种信号 {symbol: signal}
            volatilities: 各品种波动率 {symbol: volatility}
            correlations: 相关性矩阵（可选）

        返回:
            各品种仓位 {symbol: position_size}
        """
        positions = {}

        # 第一步：基于信号计算原始仓位
        for symbol, signal in signals.items():
            vol = volatilities.get(symbol, 0.20)
            if vol > 0:
                # 波动率调整
                vol_factor = self.target_vol / vol
                raw_position = signal * min(vol_factor, 2.0)
            else:
                raw_position = signal

            # 单品种仓位上限
            positions[symbol] = np.clip(raw_position, -self.max_single, self.max_single)

        # 第二步：总敞口限制
        total_exposure = sum(abs(p) for p in positions.values())
        if total_exposure > self.max_gross:
            # 按比例缩减
            scale_factor = self.max_gross / total_exposure
            for symbol in positions:
                positions[symbol] *= scale_factor

        # 第三步：相关性调整（如果有）
        if correlations is not None and len(signals) > 1:
            positions = self._adjust_for_correlation(positions, correlations)

        return {k: round(v, 4) for k, v in positions.items()}

    def _adjust_for_correlation(self, positions: Dict[str, float],
                                correlations: pd.DataFrame) -> Dict[str, float]:
        """
        相关性调整

        高相关品种的仓位应降低

        参数:
            positions: 各品种仓位
            correlations: 相关性矩阵

        返回:
            调整后的仓位
        """
        adjusted = positions.copy()
        symbols = list(positions.keys())

        for i, sym_i in enumerate(symbols):
            if sym_i not in correlations.columns:
                continue

            # 计算与其他品种的平均相关性
            avg_corr = 0
            count = 0
            for j, sym_j in enumerate(symbols):
                if i != j and sym_j in correlations.columns:
                    avg_corr += abs(correlations.loc[sym_i, sym_j])
                    count += 1

            if count > 0:
                avg_corr /= count
                # 高相关品种仓位降低
                if avg_corr > 0.7:
                    adjusted[sym_i] *= 0.7
                elif avg_corr > 0.5:
                    adjusted[sym_i] *= 0.85

        return adjusted

    def get_portfolio_stats(self, positions: Dict[str, float],
                            returns: pd.DataFrame) -> Dict:
        """
        计算组合统计

        参数:
            positions: 各品种仓位
            returns: 各品种收益率DataFrame

        返回:
            组合统计
        """
        if not positions or returns.empty:
            return {}

        # 计算组合收益
        portfolio_returns = pd.Series(0.0, index=returns.index)
        for symbol, pos in positions.items():
            if symbol in returns.columns:
                portfolio_returns += pos * returns[symbol]

        # 计算统计量
        total_return = portfolio_returns.sum()
        volatility = portfolio_returns.std() * np.sqrt(252)
        sharpe = portfolio_returns.mean() / (portfolio_returns.std() + 1e-10) * np.sqrt(252)
        max_drawdown = self._calc_max_drawdown(portfolio_returns.values)

        return {
            'total_return': round(float(total_return), 4),
            'volatility': round(float(volatility), 4),
            'sharpe_ratio': round(float(sharpe), 3),
            'max_drawdown': round(float(max_drawdown), 4),
            'n_positions': len(positions),
            'gross_exposure': round(sum(abs(p) for p in positions.values()), 4),
        }

    def _calc_max_drawdown(self, returns: np.ndarray) -> float:
        """计算最大回撤"""
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        return float(np.max(drawdown)) if len(drawdown) > 0 else 0.0


class PositionSizer:
    """
    仓位计算器

    基于凯利公式和风险预算计算最优仓位
    """

    def __init__(self, risk_free_rate: float = 0.02,
                 max_leverage: float = 2.0):
        """
        参数:
            risk_free_rate: 无风险利率
            max_leverage: 最大杠杆
        """
        self.risk_free_rate = risk_free_rate
        self.max_leverage = max_leverage

    def kelly_criterion(self, win_rate: float, avg_win: float,
                        avg_loss: float) -> float:
        """
        凯利公式计算最优仓位

        参数:
            win_rate: 胜率
            avg_win: 平均盈利
            avg_loss: 平均亏损（正数）

        返回:
            最优仓位比例
        """
        if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0

        # 凯利公式：f* = (p * b - q) / b
        # p = 胜率, q = 1-p, b = 平均盈利/平均亏损
        b = avg_win / avg_loss
        q = 1 - win_rate
        kelly = (win_rate * b - q) / b

        # 限制在合理范围内
        return max(0, min(kelly, self.max_leverage))

    def risk_budget_position(self, equity: float, risk_per_trade: float,
                             entry_price: float, stop_loss: float,
                             point_value: float = 10.0) -> Tuple[int, float, float]:
        """
        风险预算法计算仓位

        参数:
            equity: 账户权益
            risk_per_trade: 每笔交易风险比例
            entry_price: 入场价
            stop_loss: 止损价
            point_value: 合约乘数

        返回:
            lots: 手数
            actual_risk: 实际风险
            margin_used: 使用保证金
        """
        if entry_price <= 0 or stop_loss <= 0 or point_value <= 0:
            return 0, 0.0, 0.0

        # 计算每手风险
        risk_per_lot = abs(entry_price - stop_loss) * point_value

        if risk_per_lot <= 0:
            return 0, 0.0, 0.0

        # 计算最大可承受风险
        max_risk = equity * risk_per_trade

        # 计算手数
        lots = int(max_risk / risk_per_lot)

        # 计算实际风险和保证金
        actual_risk = lots * risk_per_lot
        margin_used = lots * entry_price * point_value * 0.1  # 假设10%保证金

        return lots, actual_risk, margin_used

    def progressive_position(self, entry_price: float, atr: float,
                             direction: int, phase: str,
                             confirmation_level: int = 0,
                             point_value: float = 10.0,
                             margin_per_lot: float = 5000.0,
                             equity: float = 1_000_000,
                             risk_pct: float = 0.01) -> Tuple[int, float, float]:
        """
        渐进式仓位管理（1/3法则）

        参数:
            entry_price: 入场价
            atr: ATR
            direction: 方向（1=多，-1=空）
            phase: 趋势阶段
            confirmation_level: 确认级别（0=初始，1=确认，2=强势确认）
            point_value: 合约乘数
            margin_per_lot: 每手保证金
            equity: 账户权益
            risk_pct: 风险比例

        返回:
            lots: 手数
            actual_risk: 实际风险
            margin_used: 使用保证金
        """
        # 基础止损
        stop_distance = atr * 2  # 2倍ATR止损

        # 计算基础手数
        risk_amount = equity * risk_pct
        risk_per_lot = stop_distance * point_value

        if risk_per_lot <= 0:
            return 0, 0.0, 0.0

        base_lots = int(risk_amount / risk_per_lot)

        # 根据确认级别调整
        if confirmation_level == 0:
            # 初始试探：1/3仓位
            lots = max(1, base_lots // 3)
        elif confirmation_level == 1:
            # 确认：2/3仓位
            lots = max(1, base_lots * 2 // 3)
        else:
            # 强势确认：满仓位
            lots = base_lots

        # 根据阶段调整
        if phase in ('FATIGUING', 'REVERSING'):
            lots = max(1, lots // 2)  # 衰竭/反转阶段减半
        elif phase == 'CONSOLIDATING':
            lots = max(1, lots // 3)  # 震荡阶段1/3

        actual_risk = lots * risk_per_lot
        margin_used = lots * margin_per_lot

        return lots, actual_risk, margin_used
