"""
Walk-Forward 验证框架

基于论文 "Visibility Graphs Can Make Money in Financial Markets" (arXiv: 2605.01300)
实现的滚动前向优化验证机制。

核心思想：
- 30 天优化窗口（In-Sample, IS）
- 7 天测试窗口（Out-of-Sample, OOS）
- 每 7 天滚动一次
- 只有 OOS 表现达标的参数才被采纳

这与贝叶斯优化（Phase 3）互补：
- 贝叶斯负责搜索最优参数
- Walk-Forward 负责验证参数的泛化能力

版本：v1.0
创建日期：2026-06-17
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardConfig:
    """Walk-Forward 验证配置"""
    optimization_window: int = 30  # 优化窗口大小（天）
    test_window: int = 7  # 测试窗口大小（天）
    step_size: int = 7  # 步长（天）
    min_trades: int = 5  # 最小交易次数
    min_sharpe: float = 0.5  # 最小夏普比率
    max_drawdown: float = 0.2  # 最大回撤阈值
    min_win_rate: float = 0.4  # 最小胜率


@dataclass
class WindowResult:
    """单个窗口的验证结果"""
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp
    is_sharpe: float
    oos_sharpe: float
    is_win_rate: float
    oos_win_rate: float
    is_max_drawdown: float
    oos_max_drawdown: float
    is_trades: int
    oos_trades: int
    params: Dict[str, Any]
    passed: bool


@dataclass
class WalkForwardResult:
    """Walk-Forward 验证的完整结果"""
    total_windows: int
    passed_windows: int
    pass_rate: float
    avg_oos_sharpe: float
    avg_oos_win_rate: float
    max_oos_drawdown: float
    window_results: List[WindowResult]
    final_params: Optional[Dict[str, Any]]


class WalkForwardValidator:
    """
    Walk-Forward 验证器
    
    实现滚动前向优化验证，确保参数的泛化能力。
    """
    
    def __init__(self, config: WalkForwardConfig = None):
        """
        初始化 Walk-Forward 验证器
        
        Args:
            config: Walk-Forward 配置
        """
        self.config = config or WalkForwardConfig()
        logger.info(f"WalkForwardValidator 初始化: "
                   f"优化窗口={self.config.optimization_window}天, "
                   f"测试窗口={self.config.test_window}天, "
                   f"步长={self.config.step_size}天")
    
    def validate(self, 
                 prices: pd.Series,
                 factor_func: Callable,
                 param_space: Dict[str, Any],
                 optimize_func: Callable) -> WalkForwardResult:
        """
        执行 Walk-Forward 验证
        
        Args:
            prices: 价格序列
            factor_func: 因子计算函数
            param_space: 参数空间
            optimize_func: 参数优化函数
            
        Returns:
            WalkForwardResult: 验证结果
        """
        logger.info(f"开始 Walk-Forward 验证, 数据长度: {len(prices)}")
        
        # 计算窗口数量
        total_days = len(prices)
        window_size = self.config.optimization_window + self.config.test_window
        
        if total_days < window_size:
            logger.warning(f"数据长度 {total_days} 不足一个窗口 {window_size}")
            return WalkForwardResult(
                total_windows=0,
                passed_windows=0,
                pass_rate=0.0,
                avg_oos_sharpe=0.0,
                avg_oos_win_rate=0.0,
                max_oos_drawdown=0.0,
                window_results=[],
                final_params=None
            )
        
        # 计算窗口起始位置
        window_starts = list(range(0, total_days - window_size + 1, self.config.step_size))
        
        window_results = []
        
        for i, start_idx in enumerate(window_starts):
            logger.info(f"处理窗口 {i+1}/{len(window_starts)}")
            
            # 计算窗口边界
            is_start_idx = start_idx
            is_end_idx = start_idx + self.config.optimization_window
            oos_start_idx = is_end_idx
            oos_end_idx = min(oos_start_idx + self.config.test_window, total_days)
            
            # 提取数据
            is_prices = prices.iloc[is_start_idx:is_end_idx]
            oos_prices = prices.iloc[oos_start_idx:oos_end_idx]
            
            # 在 IS 窗口优化参数
            best_params = optimize_func(is_prices, param_space)
            
            # 在 IS 和 OOS 窗口评估
            is_metrics = self._evaluate_window(is_prices, factor_func, best_params)
            oos_metrics = self._evaluate_window(oos_prices, factor_func, best_params)
            
            # 判断是否通过验证
            passed = self._check_pass_criteria(is_metrics, oos_metrics)
            
            # 记录结果
            window_result = WindowResult(
                window_start=prices.index[start_idx],
                window_end=prices.index[min(oos_end_idx - 1, total_days - 1)],
                is_start=prices.index[is_start_idx],
                is_end=prices.index[is_end_idx - 1],
                oos_start=prices.index[oos_start_idx],
                oos_end=prices.index[min(oos_end_idx - 1, total_days - 1)],
                is_sharpe=is_metrics['sharpe'],
                oos_sharpe=oos_metrics['sharpe'],
                is_win_rate=is_metrics['win_rate'],
                oos_win_rate=oos_metrics['win_rate'],
                is_max_drawdown=is_metrics['max_drawdown'],
                oos_max_drawdown=oos_metrics['max_drawdown'],
                is_trades=is_metrics['trades'],
                oos_trades=oos_metrics['trades'],
                params=best_params,
                passed=passed
            )
            
            window_results.append(window_result)
            
            logger.info(f"窗口 {i+1}: IS Sharpe={is_metrics['sharpe']:.3f}, "
                       f"OOS Sharpe={oos_metrics['sharpe']:.3f}, "
                       f"通过={passed}")
        
        # 汇总结果
        passed_windows = sum(1 for r in window_results if r.passed)
        pass_rate = passed_windows / len(window_results) if window_results else 0.0
        
        oos_sharpes = [r.oos_sharpe for r in window_results if not np.isnan(r.oos_sharpe)]
        oos_win_rates = [r.oos_win_rate for r in window_results if not np.isnan(r.oos_win_rate)]
        oos_drawdowns = [r.oos_max_drawdown for r in window_results if not np.isnan(r.oos_max_drawdown)]
        
        avg_oos_sharpe = np.mean(oos_sharpes) if oos_sharpes else 0.0
        avg_oos_win_rate = np.mean(oos_win_rates) if oos_win_rates else 0.0
        max_oos_drawdown = np.max(oos_drawdowns) if oos_drawdowns else 0.0
        
        # 选择最终参数（使用通过验证的窗口的参数）
        passed_params = [r.params for r in window_results if r.passed]
        final_params = passed_params[-1] if passed_params else None
        
        result = WalkForwardResult(
            total_windows=len(window_results),
            passed_windows=passed_windows,
            pass_rate=pass_rate,
            avg_oos_sharpe=avg_oos_sharpe,
            avg_oos_win_rate=avg_oos_win_rate,
            max_oos_drawdown=max_oos_drawdown,
            window_results=window_results,
            final_params=final_params
        )
        
        logger.info(f"Walk-Forward 验证完成: "
                   f"通过率={pass_rate:.2%}, "
                   f"平均 OOS Sharpe={avg_oos_sharpe:.3f}, "
                   f"最大 OOS 回撤={max_oos_drawdown:.2%}")
        
        return result
    
    def _evaluate_window(self, 
                        prices: pd.Series, 
                        factor_func: Callable, 
                        params: Dict[str, Any]) -> Dict[str, float]:
        """
        评估单个窗口的表现
        
        Args:
            prices: 价格序列
            factor_func: 因子计算函数
            params: 参数
            
        Returns:
            Dict[str, float]: 评估指标
        """
        # 计算因子值
        factor_values = factor_func(prices, **params)
        
        # 生成信号
        signals = self._generate_signals(factor_values)
        
        # 计算收益
        returns = self._calculate_returns(prices, signals)
        
        # 计算指标
        metrics = {
            'sharpe': self._calculate_sharpe(returns),
            'win_rate': self._calculate_win_rate(returns),
            'max_drawdown': self._calculate_max_drawdown(returns),
            'trades': self._count_trades(signals)
        }
        
        return metrics
    
    def _generate_signals(self, factor_values: pd.Series) -> pd.Series:
        """
        根据因子值生成交易信号
        
        Args:
            factor_values: 因子值序列
            
        Returns:
            pd.Series: 信号序列 (1=买入, -1=卖出, 0=无信号)
        """
        signals = pd.Series(0, index=factor_values.index)
        
        # 简单的阈值策略
        for i in range(1, len(factor_values)):
            if pd.isna(factor_values.iloc[i]) or pd.isna(factor_values.iloc[i-1]):
                continue
            
            # 买入信号: 因子值从下方穿越上阈值
            if factor_values.iloc[i] > 70 and factor_values.iloc[i-1] <= 70:
                signals.iloc[i] = 1
            # 卖出信号: 因子值从上方穿越下阈值
            elif factor_values.iloc[i] < 30 and factor_values.iloc[i-1] >= 30:
                signals.iloc[i] = -1
        
        return signals
    
    def _calculate_returns(self, prices: pd.Series, signals: pd.Series) -> pd.Series:
        """
        计算策略收益
        
        Args:
            prices: 价格序列
            signals: 信号序列
            
        Returns:
            pd.Series: 收益序列
        """
        # 计算价格变化
        price_changes = prices.pct_change()
        
        # 将信号转换为持仓
        positions = signals.replace(0, np.nan).ffill().fillna(0)
        
        # 计算策略收益
        returns = positions.shift(1) * price_changes
        
        return returns.dropna()
    
    def _calculate_sharpe(self, returns: pd.Series) -> float:
        """
        计算夏普比率
        
        Args:
            returns: 收益序列
            
        Returns:
            float: 夏普比率
        """
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        return returns.mean() / returns.std() * np.sqrt(252)
    
    def _calculate_win_rate(self, returns: pd.Series) -> float:
        """
        计算胜率
        
        Args:
            returns: 收益序列
            
        Returns:
            float: 胜率
        """
        if len(returns) == 0:
            return 0.0
        
        winning_trades = (returns > 0).sum()
        return winning_trades / len(returns)
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """
        计算最大回撤
        
        Args:
            returns: 收益序列
            
        Returns:
            float: 最大回撤
        """
        if len(returns) == 0:
            return 0.0
        
        # 计算累积收益
        cumulative = (1 + returns).cumprod()
        
        # 计算最大回撤
        peak = cumulative.expanding(min_periods=1).max()
        drawdown = (cumulative - peak) / peak
        
        return abs(drawdown.min())
    
    def _count_trades(self, signals: pd.Series) -> int:
        """
        计算交易次数
        
        Args:
            signals: 信号序列
            
        Returns:
            int: 交易次数
        """
        return (signals != 0).sum()
    
    def _check_pass_criteria(self, 
                           is_metrics: Dict[str, float], 
                           oos_metrics: Dict[str, float]) -> bool:
        """
        检查是否通过验证标准
        
        Args:
            is_metrics: IS 窗口指标
            oos_metrics: OOS 窗口指标
            
        Returns:
            bool: 是否通过
        """
        # 检查 OOS 窗口的最小交易次数
        if oos_metrics['trades'] < self.config.min_trades:
            return False
        
        # 检查 OOS 窗口的最小夏普比率
        if oos_metrics['sharpe'] < self.config.min_sharpe:
            return False
        
        # 检查 OOS 窗口的最大回撤
        if oos_metrics['max_drawdown'] > self.config.max_drawdown:
            return False
        
        # 检查 OOS 窗口的最小胜率
        if oos_metrics['win_rate'] < self.config.min_win_rate:
            return False
        
        # 检查 IS 和 OOS 的一致性（防止过拟合）
        # OOS Sharpe 不应该比 IS Sharpe 差太多
        if is_metrics['sharpe'] > 0 and oos_metrics['sharpe'] < is_metrics['sharpe'] * 0.5:
            return False
        
        return True
    
    def save_result(self, result: WalkForwardResult, filepath: str):
        """
        保存验证结果
        
        Args:
            result: 验证结果
            filepath: 文件路径
        """
        output = {
            'total_windows': result.total_windows,
            'passed_windows': result.passed_windows,
            'pass_rate': result.pass_rate,
            'avg_oos_sharpe': result.avg_oos_sharpe,
            'avg_oos_win_rate': result.avg_oos_win_rate,
            'max_oos_drawdown': result.max_oos_drawdown,
            'final_params': result.final_params,
            'windows': []
        }
        
        for window in result.window_results:
            output['windows'].append({
                'window_start': str(window.window_start),
                'window_end': str(window.window_end),
                'is_sharpe': window.is_sharpe,
                'oos_sharpe': window.oos_sharpe,
                'is_win_rate': window.is_win_rate,
                'oos_win_rate': window.oos_win_rate,
                'is_max_drawdown': window.is_max_drawdown,
                'oos_max_drawdown': window.oos_max_drawdown,
                'is_trades': window.is_trades,
                'oos_trades': window.oos_trades,
                'passed': window.passed
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"验证结果已保存到: {filepath}")


def walk_forward_validate(prices: pd.Series,
                         factor_func: Callable,
                         param_space: Dict[str, Any],
                         optimize_func: Callable,
                         config: WalkForwardConfig = None) -> WalkForwardResult:
    """
    便捷函数：执行 Walk-Forward 验证
    
    Args:
        prices: 价格序列
        factor_func: 因子计算函数
        param_space: 参数空间
        optimize_func: 参数优化函数
        config: Walk-Forward 配置
        
    Returns:
        WalkForwardResult: 验证结果
    """
    validator = WalkForwardValidator(config)
    return validator.validate(prices, factor_func, param_space, optimize_func)
