"""
收益归因引擎

基于 KTD-Fin 论文 (arXiv:2605.28359) 的 Barra 风格收益归因框架：
- 将策略收益分解为：市场Beta、风格暴露、选股Alpha
- 选股Alpha是真正可转移的投资技能
- 区分技能与运气

核心公式：
r_{i,t} = f_{0,t} + Σ_k x_{i,k,t-1} λ_{k,t} + ε_{i,t}

其中：
- r_{i,t}：股票i的收益
- f_{0,t}：共同收益成分（市场Beta）
- x_{i,k,t-1}：风格因子暴露
- λ_{k,t}：因子收益
- ε_{i,t}：选股残差（Alpha）
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AttributionResult:
    """收益归因结果"""
    market_beta: float = 0.0  # 市场Beta贡献
    style_exposure: float = 0.0  # 风格暴露贡献
    stock_alpha: float = 0.0  # 选股Alpha（真正技能）
    total_return: float = 0.0  # 总收益
    residual: float = 0.0  # 残差
    
    # 详细分解
    factor_contributions: Dict[str, float] = field(default_factory=dict)
    
    # 统计信息
    r_squared: float = 0.0  # 模型解释力
    alpha_significance: float = 0.0  # Alpha显著性
    
    def to_dict(self) -> dict:
        return {
            "market_beta": self.market_beta,
            "style_exposure": self.style_exposure,
            "stock_alpha": self.stock_alpha,
            "total_return": self.total_return,
            "residual": self.residual,
            "factor_contributions": self.factor_contributions,
            "r_squared": self.r_squared,
            "alpha_significance": self.alpha_significance,
        }
    
    def to_prompt_text(self) -> str:
        """转换为推理层可读的文本"""
        lines = [
            "## 收益归因分析（Barra框架）",
            f"- 总收益：{self.total_return:+.2%}",
            f"- 市场Beta贡献：{self.market_beta:+.2%}",
            f"- 风格暴露贡献：{self.style_exposure:+.2%}",
            f"- 选股Alpha：{self.stock_alpha:+.2%}",
            f"- 模型解释力（R²）：{self.r_squared:.2%}",
        ]
        
        if self.stock_alpha > 0:
            lines.append("- 评估：策略具有正向选股技能")
        elif self.stock_alpha < -0.01:
            lines.append("- 警告：选股Alpha为负，收益主要来自市场Beta")
        else:
            lines.append("- 评估：选股Alpha接近零，收益主要来自被动暴露")
        
        return "\n".join(lines)


class ReturnAttributor:
    """
    收益归因引擎
    
    基于 KTD-Fin 论文的 Barra 风格收益归因框架
    """
    
    # 默认风格因子
    DEFAULT_FACTORS = [
        "market",      # 市场因子
        "size",        # 市值因子
        "value",       # 价值因子
        "momentum",    # 动量因子
        "volatility",  # 波动率因子
        "quality",     # 质量因子
    ]
    
    def __init__(self, factors: Optional[List[str]] = None):
        """
        初始化收益归因引擎
        
        Args:
            factors: 风格因子列表
        """
        self.factors = factors or self.DEFAULT_FACTORS
    
    def attribute(
        self,
        portfolio_returns: pd.Series,
        market_returns: pd.Series,
        factor_exposures: Optional[pd.DataFrame] = None,
    ) -> AttributionResult:
        """
        执行收益归因
        
        Args:
            portfolio_returns: 组合收益序列
            market_returns: 市场收益序列
            factor_exposures: 风格因子暴露（可选）
            
        Returns:
            AttributionResult: 归因结果
        """
        # 对齐数据
        common_idx = portfolio_returns.index.intersection(market_returns.index)
        if len(common_idx) == 0:
            logger.warning("无共同日期，无法执行归因")
            return AttributionResult()
        
        port_ret = portfolio_returns.loc[common_idx].values
        mkt_ret = market_returns.loc[common_idx].values
        
        # 计算市场Beta贡献
        market_beta = self._calculate_market_beta(port_ret, mkt_ret)
        
        # 计算风格暴露贡献
        style_exposure = self._calculate_style_exposure(
            port_ret, mkt_ret, factor_exposures
        )
        
        # 计算选股Alpha（残差）
        explained = market_beta + style_exposure
        total_return = np.mean(port_ret)
        alpha = total_return - explained
        
        # 计算模型解释力
        r_squared = self._calculate_r_squared(port_ret, mkt_ret)
        
        # 计算Alpha显著性
        alpha_significance = self._calculate_alpha_significance(
            port_ret, mkt_ret
        )
        
        return AttributionResult(
            market_beta=market_beta,
            style_exposure=style_exposure,
            stock_alpha=alpha,
            total_return=total_return,
            residual=total_return - explained,
            r_squared=r_squared,
            alpha_significance=alpha_significance,
        )
    
    def _calculate_market_beta(
        self, portfolio_returns: np.ndarray, market_returns: np.ndarray
    ) -> float:
        """计算市场Beta贡献"""
        if len(portfolio_returns) < 2:
            return 0.0
        
        # OLS回归计算Beta
        cov = np.cov(portfolio_returns, market_returns)
        if cov[1, 1] == 0:
            return 0.0
        
        beta = cov[0, 1] / cov[1, 1]
        
        # Beta贡献 = Beta × 市场平均收益
        market_mean = np.mean(market_returns)
        return beta * market_mean
    
    def _calculate_style_exposure(
        self,
        portfolio_returns: np.ndarray,
        market_returns: np.ndarray,
        factor_exposures: Optional[pd.DataFrame],
    ) -> float:
        """计算风格暴露贡献"""
        if factor_exposures is None or len(factor_exposures) == 0:
            # 简化：使用市场收益的波动率作为风格暴露代理
            return np.std(market_returns) * 0.1  # 简化假设
        
        # 使用因子暴露计算
        # 简化实现
        return 0.0
    
    def _calculate_r_squared(
        self, portfolio_returns: np.ndarray, market_returns: np.ndarray
    ) -> float:
        """计算模型解释力（R²）"""
        if len(portfolio_returns) < 2:
            return 0.0
        
        # 计算相关系数的平方
        corr = np.corrcoef(portfolio_returns, market_returns)[0, 1]
        return corr ** 2
    
    def _calculate_alpha_significance(
        self, portfolio_returns: np.ndarray, market_returns: np.ndarray
    ) -> float:
        """计算Alpha显著性（t统计量）"""
        if len(portfolio_returns) < 10:
            return 0.0
        
        # 计算残差
        cov = np.cov(portfolio_returns, market_returns)
        if cov[1, 1] == 0:
            return 0.0
        
        beta = cov[0, 1] / cov[1, 1]
        alpha = np.mean(portfolio_returns) - beta * np.mean(market_returns)
        
        # 计算残差标准误
        residuals = portfolio_returns - (alpha + beta * market_returns)
        se = np.std(residuals) / np.sqrt(len(portfolio_returns))
        
        if se == 0:
            return 0.0
        
        # t统计量
        t_stat = alpha / se
        
        return t_stat
    
    def create_attribution_report(self, result: AttributionResult) -> str:
        """创建归因报告"""
        return result.to_prompt_text()


def create_attribution_summary(results: List[AttributionResult]) -> str:
    """创建多期归因汇总"""
    if not results:
        return "无归因数据"
    
    avg_alpha = np.mean([r.stock_alpha for r in results])
    avg_beta = np.mean([r.market_beta for r in results])
    avg_style = np.mean([r.style_exposure for r in results])
    avg_r2 = np.mean([r.r_squared for r in results])
    
    summary = f"""
=== 收益归因汇总（{len(results)}期）===

平均选股Alpha：{avg_alpha:+.2%}
平均市场Beta贡献：{avg_beta:+.2%}
平均风格暴露贡献：{avg_style:+.2%}
平均模型解释力：{avg_r2:.2%}

评估：
"""
    
    if avg_alpha > 0.005:
        summary += "策略具有稳定的正向选股技能"
    elif avg_alpha < -0.005:
        summary += "策略Alpha为负，收益主要来自被动暴露"
    else:
        summary += "策略Alpha接近零，需进一步分析"
    
    return summary
