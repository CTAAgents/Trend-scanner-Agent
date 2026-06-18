"""
StrategyPortfolio — 多策略组合管理模块 v1.0

基于 Kevin J. Davey《构建盈利的算法交易系统》中的 Step 7：
结合多个不相关的系统，以平滑权益曲线、降低风险。

核心功能：
1. 策略间相关性控制
2. 策略权重动态调整
3. 组合权益曲线分析
4. 策略级风险预算
5. 分散化比率计算

使用方式：
    from strategy_portfolio import StrategyPortfolio
    portfolio = StrategyPortfolio()
    portfolio.add_strategy("trend_following", weight=0.4, equity_curve=eq1)
    portfolio.add_strategy("mean_reversion", weight=0.3, equity_curve=eq2)
    portfolio.add_strategy("breakout", weight=0.3, equity_curve=eq3)
    stats = portfolio.get_portfolio_stats()

版本：v1.0
创建日期：2026-06-17
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


# ===================== 数据模型 =====================


@dataclass
class StrategyInfo:
    """策略信息"""

    strategy_id: str
    weight: float
    equity_curve: pd.Series
    returns: pd.Series | None = None
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    annual_return: float = 0.0
    volatility: float = 0.0

    def __post_init__(self):
        """初始化后计算衍生指标"""
        if self.returns is None and len(self.equity_curve) > 1:
            self.returns = self.equity_curve.pct_change().dropna()

        if self.returns is not None and len(self.returns) > 0:
            self.sharpe = self._calc_sharpe()
            self.max_drawdown = self._calc_max_drawdown()
            self.volatility = float(self.returns.std() * np.sqrt(252))
            self.annual_return = float(self.returns.mean() * 252)
            self.win_rate = float((self.returns > 0).sum() / len(self.returns))

    def _calc_sharpe(self, risk_free_rate: float = 0.0) -> float:
        if self.returns is None or len(self.returns) < 2:
            return 0.0
        excess = self.returns - risk_free_rate
        std = excess.std()
        if std < 1e-10:
            return 0.0
        return float(excess.mean() / std * np.sqrt(252))

    def _calc_max_drawdown(self) -> float:
        if self.equity_curve is None or len(self.equity_curve) < 2:
            return 0.0
        running_max = self.equity_curve.cummax()
        drawdown = (running_max - self.equity_curve) / running_max.replace(0, np.nan)
        return float(drawdown.max()) if not drawdown.empty else 0.0


@dataclass
class PortfolioStats:
    """组合统计"""

    total_strategies: int
    weights_sum: float
    diversification_ratio: float
    portfolio_sharpe: float
    portfolio_max_drawdown: float
    portfolio_annual_return: float
    portfolio_volatility: float
    correlation_matrix: pd.DataFrame | None = None

    def to_dict(self) -> dict:
        return {
            "total_strategies": self.total_strategies,
            "weights_sum": round(self.weights_sum, 4),
            "diversification_ratio": round(self.diversification_ratio, 4),
            "portfolio_sharpe": round(self.portfolio_sharpe, 4),
            "portfolio_max_drawdown": round(self.portfolio_max_drawdown, 4),
            "portfolio_annual_return": round(self.portfolio_annual_return, 4),
            "portfolio_volatility": round(self.portfolio_volatility, 4),
        }


# ===================== 组合管理器 =====================


class StrategyPortfolio:
    """
    多策略组合管理器

    管理多个策略的权重、相关性、组合权益曲线。
    """

    def __init__(self, max_strategies: int = 10, max_correlation: float = 0.7, rebalance_frequency: int = 30):
        """
        参数:
            max_strategies: 最大策略数
            max_correlation: 策略间最大相关性
            rebalance_frequency: 再平衡频率（天）
        """
        self.max_strategies = max_strategies
        self.max_correlation = max_correlation
        self.rebalance_frequency = rebalance_frequency

        # 策略字典 {strategy_id: StrategyInfo}
        self._strategies: dict[str, StrategyInfo] = {}

    def add_strategy(self, strategy_id: str, weight: float, equity_curve: pd.Series) -> None:
        """
        添加策略到组合

        参数:
            strategy_id: 策略ID
            weight: 策略权重 (0-1)
            equity_curve: 策略权益曲线
        """
        if len(self._strategies) >= self.max_strategies:
            raise ValueError(f"策略数已达上限 {self.max_strategies}")

        if strategy_id in self._strategies:
            # 更新现有策略
            self._strategies[strategy_id].weight = weight
            self._strategies[strategy_id].equity_curve = equity_curve
            self._strategies[strategy_id].__post_init__()
        else:
            self._strategies[strategy_id] = StrategyInfo(
                strategy_id=strategy_id,
                weight=weight,
                equity_curve=equity_curve,
            )

        logger.info(f"添加策略 {strategy_id}，权重={weight:.2%}")

    def remove_strategy(self, strategy_id: str) -> None:
        """从组合中移除策略"""
        if strategy_id in self._strategies:
            del self._strategies[strategy_id]
            logger.info(f"移除策略 {strategy_id}")

    def get_strategy(self, strategy_id: str) -> StrategyInfo | None:
        """获取策略信息"""
        return self._strategies.get(strategy_id)

    def get_all_strategies(self) -> dict[str, StrategyInfo]:
        """获取所有策略"""
        return self._strategies.copy()

    def calculate_portfolio_equity(self) -> pd.Series:
        """
        计算组合权益曲线

        返回:
            组合权益曲线
        """
        if not self._strategies:
            return pd.Series(dtype=float)

        # 归一化权重
        total_weight = sum(s.weight for s in self._strategies.values())
        if total_weight <= 0:
            return pd.Series(dtype=float)

        # 获取所有策略的权益曲线，对齐时间
        equity_curves = {}
        for sid, strategy in self._strategies.items():
            equity_curves[sid] = strategy.equity_curve

        # 合并为DataFrame，用第一个策略的时间索引
        first_strategy = list(self._strategies.values())[0]
        index = first_strategy.equity_curve.index

        portfolio_equity = pd.Series(0.0, index=index)

        for sid, strategy in self._strategies.items():
            normalized_weight = strategy.weight / total_weight
            # 对齐到共同索引
            aligned = strategy.equity_curve.reindex(index, method="ffill")
            portfolio_equity += normalized_weight * aligned

        return portfolio_equity

    def calculate_diversification_ratio(self) -> float:
        """
        计算分散化比率

        分散化比率 = 组合波动率 / 加权平均波动率
        比率 > 1 表示分散化有效

        返回:
            分散化比率
        """
        if len(self._strategies) < 2:
            return 1.0

        # 加权平均波动率
        weighted_vol = sum(s.weight * s.volatility for s in self._strategies.values())

        # 组合波动率
        portfolio_equity = self.calculate_portfolio_equity()
        if len(portfolio_equity) < 2:
            return 1.0

        portfolio_returns = portfolio_equity.pct_change().dropna()
        if len(portfolio_returns) < 2 or portfolio_returns.std() < 1e-10:
            return 1.0

        portfolio_vol = float(portfolio_returns.std() * np.sqrt(252))

        if weighted_vol < 1e-10:
            return 1.0

        return portfolio_vol / weighted_vol

    def analyze_correlation(self) -> pd.DataFrame:
        """
        分析策略间相关性

        返回:
            相关性矩阵
        """
        if len(self._strategies) < 2:
            return pd.DataFrame()

        # 构建收益率DataFrame
        returns_dict = {}
        for sid, strategy in self._strategies.items():
            if strategy.returns is not None and len(strategy.returns) > 0:
                returns_dict[sid] = strategy.returns

        if len(returns_dict) < 2:
            return pd.DataFrame()

        returns_df = pd.DataFrame(returns_dict)
        return returns_df.corr()

    def optimize_weights(self, target_vol: float = 0.15, method: str = "equal_risk") -> dict[str, float]:
        """
        优化策略权重

        参数:
            target_vol: 目标年化波动率
            method: 优化方法
                - "equal_risk": 等风险贡献
                - "equal_weight": 等权重
                - "max_sharpe": 最大化夏普

        返回:
            优化后的权重 {strategy_id: weight}
        """
        if not self._strategies:
            return {}

        n = len(self._strategies)
        strategy_ids = list(self._strategies.keys())

        if method == "equal_weight":
            # 等权重
            weight = 1.0 / n
            return {sid: weight for sid in strategy_ids}

        elif method == "equal_risk":
            # 等风险贡献：波动率高的策略权重低
            vols = {sid: self._strategies[sid].volatility for sid in strategy_ids}
            total_inv_vol = sum(1.0 / max(v, 0.01) for v in vols.values())
            weights = {}
            for sid in strategy_ids:
                weights[sid] = (1.0 / max(vols[sid], 0.01)) / total_inv_vol
            return weights

        elif method == "max_sharpe":
            # 简化版：按夏普比率分配权重
            sharpes = {sid: max(self._strategies[sid].sharpe, 0.01) for sid in strategy_ids}
            total_sharpe = sum(sharpes.values())
            weights = {}
            for sid in strategy_ids:
                weights[sid] = sharpes[sid] / total_sharpe
            return weights

        else:
            # 默认等权重
            return {sid: 1.0 / n for sid in strategy_ids}

    def get_portfolio_stats(self) -> PortfolioStats:
        """获取组合统计"""
        if not self._strategies:
            return PortfolioStats(
                total_strategies=0,
                weights_sum=0,
                diversification_ratio=1.0,
                portfolio_sharpe=0,
                portfolio_max_drawdown=0,
                portfolio_annual_return=0,
                portfolio_volatility=0,
            )

        # 计算组合权益曲线
        portfolio_equity = self.calculate_portfolio_equity()

        if len(portfolio_equity) < 2:
            return PortfolioStats(
                total_strategies=len(self._strategies),
                weights_sum=sum(s.weight for s in self._strategies.values()),
                diversification_ratio=1.0,
                portfolio_sharpe=0,
                portfolio_max_drawdown=0,
                portfolio_annual_return=0,
                portfolio_volatility=0,
            )

        # 计算组合统计
        portfolio_returns = portfolio_equity.pct_change().dropna()

        if len(portfolio_returns) < 2:
            sharpe = 0.0
            max_dd = 0.0
            ann_return = 0.0
            vol = 0.0
        else:
            sharpe = float(portfolio_returns.mean() / (portfolio_returns.std() + 1e-10) * np.sqrt(252))
            max_dd = self._calc_max_drawdown(portfolio_equity)
            ann_return = float(portfolio_returns.mean() * 252)
            vol = float(portfolio_returns.std() * np.sqrt(252))

        return PortfolioStats(
            total_strategies=len(self._strategies),
            weights_sum=sum(s.weight for s in self._strategies.values()),
            diversification_ratio=self.calculate_diversification_ratio(),
            portfolio_sharpe=sharpe,
            portfolio_max_drawdown=max_dd,
            portfolio_annual_return=ann_return,
            portfolio_volatility=vol,
            correlation_matrix=self.analyze_correlation(),
        )

    def _calc_max_drawdown(self, equity: pd.Series) -> float:
        """计算最大回撤"""
        if len(equity) < 2:
            return 0.0
        running_max = equity.cummax()
        drawdown = (running_max - equity) / running_max.replace(0, np.nan)
        return float(drawdown.max()) if not drawdown.empty else 0.0

    def check_correlation_warning(self) -> list[tuple[str, str, float]]:
        """
        检查策略间相关性警告

        返回:
            高相关策略对列表 [(sid1, sid2, correlation), ...]
        """
        corr_matrix = self.analyze_correlation()
        if corr_matrix.empty:
            return []

        warnings = []
        strategy_ids = list(corr_matrix.columns)

        for i, sid1 in enumerate(strategy_ids):
            for j, sid2 in enumerate(strategy_ids):
                if i < j:
                    corr = corr_matrix.loc[sid1, sid2]
                    if abs(corr) > self.max_correlation:
                        warnings.append((sid1, sid2, float(corr)))

        return warnings
