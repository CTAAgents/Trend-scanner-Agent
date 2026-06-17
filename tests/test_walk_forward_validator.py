"""
Walk-Forward 验证框架测试模块

测试 Walk-Forward 验证器的实现。
覆盖：
1. 配置初始化
2. 窗口计算
3. 验证逻辑
4. 边界条件

创建日期：2026-06-17
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import numpy as np
import pandas as pd
from scripts.trend_scanner.walk_forward_validator import (
    WalkForwardConfig,
    WalkForwardValidator,
    WalkForwardResult,
    WindowResult,
    walk_forward_validate
)


class TestWalkForwardConfig:
    """测试 Walk-Forward 配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = WalkForwardConfig()
        assert config.optimization_window == 30
        assert config.test_window == 7
        assert config.step_size == 7
        assert config.min_trades == 5
        assert config.min_sharpe == 0.5
        assert config.max_drawdown == 0.2
        assert config.min_win_rate == 0.4
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = WalkForwardConfig(
            optimization_window=20,
            test_window=5,
            step_size=5,
            min_trades=3,
            min_sharpe=0.3,
            max_drawdown=0.3,
            min_win_rate=0.5
        )
        assert config.optimization_window == 20
        assert config.test_window == 5
        assert config.step_size == 5
        assert config.min_trades == 3
        assert config.min_sharpe == 0.3
        assert config.max_drawdown == 0.3
        assert config.min_win_rate == 0.5


class TestWalkForwardValidator:
    """测试 Walk-Forward 验证器"""
    
    def test_validator_initialization(self):
        """测试验证器初始化"""
        config = WalkForwardConfig()
        validator = WalkForwardValidator(config)
        assert validator.config == config
    
    def test_validator_default_config(self):
        """测试默认配置初始化"""
        validator = WalkForwardValidator()
        assert validator.config.optimization_window == 30
        assert validator.config.test_window == 7
    
    def test_evaluate_window(self):
        """测试窗口评估"""
        validator = WalkForwardValidator()
        
        # 创建测试数据
        np.random.seed(42)
        prices = pd.Series(np.cumsum(np.random.randn(100) * 0.1) + 100)
        
        # 定义简单的因子函数
        def simple_factor(prices, **params):
            return prices.pct_change(5) * 100
        
        # 评估窗口
        metrics = validator._evaluate_window(prices, simple_factor, {})
        
        # 检查指标
        assert 'sharpe' in metrics
        assert 'win_rate' in metrics
        assert 'max_drawdown' in metrics
        assert 'trades' in metrics
    
    def test_generate_signals(self):
        """测试信号生成"""
        validator = WalkForwardValidator()
        
        # 创建因子值
        factor_values = pd.Series([50, 60, 75, 80, 70, 60, 25, 20, 30, 40])
        
        signals = validator._generate_signals(factor_values)
        
        # 检查信号
        assert len(signals) == len(factor_values)
        # 应该有买入信号（从70到75）
        assert signals.iloc[2] == 1
        # 应该有卖出信号（从70到25）
        assert signals.iloc[6] == -1
    
    def test_calculate_returns(self):
        """测试收益计算"""
        validator = WalkForwardValidator()
        
        # 创建价格和信号
        prices = pd.Series([100, 101, 102, 103, 102, 101, 100, 99, 98, 97])
        signals = pd.Series([0, 0, 1, 0, 0, 0, -1, 0, 0, 0])
        
        returns = validator._calculate_returns(prices, signals)
        
        # 检查收益
        assert len(returns) > 0
    
    def test_calculate_sharpe(self):
        """测试夏普比率计算"""
        validator = WalkForwardValidator()
        
        # 创建正收益序列
        positive_returns = pd.Series([0.01, 0.02, 0.01, 0.02, 0.01])
        sharpe = validator._calculate_sharpe(positive_returns)
        assert sharpe > 0
        
        # 创建负收益序列
        negative_returns = pd.Series([-0.01, -0.02, -0.01, -0.02, -0.01])
        sharpe = validator._calculate_sharpe(negative_returns)
        assert sharpe < 0
        
        # 空序列
        empty_returns = pd.Series([])
        sharpe = validator._calculate_sharpe(empty_returns)
        assert sharpe == 0.0
    
    def test_calculate_win_rate(self):
        """测试胜率计算"""
        validator = WalkForwardValidator()
        
        # 创建收益序列
        returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
        win_rate = validator._calculate_win_rate(returns)
        assert win_rate == 0.6  # 3/5
        
        # 空序列
        empty_returns = pd.Series([])
        win_rate = validator._calculate_win_rate(empty_returns)
        assert win_rate == 0.0
    
    def test_calculate_max_drawdown(self):
        """测试最大回撤计算"""
        validator = WalkForwardValidator()
        
        # 创建有回撤的收益序列
        returns = pd.Series([0.01, 0.02, -0.05, 0.03, -0.02, 0.01])
        max_drawdown = validator._calculate_max_drawdown(returns)
        assert max_drawdown > 0
        
        # 空序列
        empty_returns = pd.Series([])
        max_drawdown = validator._calculate_max_drawdown(empty_returns)
        assert max_drawdown == 0.0
    
    def test_count_trades(self):
        """测试交易次数计算"""
        validator = WalkForwardValidator()
        
        # 创建信号序列
        signals = pd.Series([0, 0, 1, 0, 0, -1, 0, 0, 1, 0])
        trades = validator._count_trades(signals)
        assert trades == 3
    
    def test_check_pass_criteria(self):
        """测试验证标准检查"""
        validator = WalkForwardValidator()
        
        # 通过的情况
        is_metrics = {
            'sharpe': 1.0,
            'win_rate': 0.6,
            'max_drawdown': 0.1,
            'trades': 10
        }
        oos_metrics = {
            'sharpe': 0.8,
            'win_rate': 0.5,
            'max_drawdown': 0.15,
            'trades': 8
        }
        assert validator._check_pass_criteria(is_metrics, oos_metrics) == True
        
        # 不通过的情况（OOS Sharpe 太低）
        oos_metrics_low_sharpe = {
            'sharpe': 0.2,
            'win_rate': 0.5,
            'max_drawdown': 0.15,
            'trades': 8
        }
        assert validator._check_pass_criteria(is_metrics, oos_metrics_low_sharpe) == False
        
        # 不通过的情况（OOS 回撤太大）
        oos_metrics_high_drawdown = {
            'sharpe': 0.8,
            'win_rate': 0.5,
            'max_drawdown': 0.3,
            'trades': 8
        }
        assert validator._check_pass_criteria(is_metrics, oos_metrics_high_drawdown) == False
        
        # 不通过的情况（交易次数太少）
        oos_metrics_few_trades = {
            'sharpe': 0.8,
            'win_rate': 0.5,
            'max_drawdown': 0.15,
            'trades': 2
        }
        assert validator._check_pass_criteria(is_metrics, oos_metrics_few_trades) == False


class TestWalkForwardValidation:
    """测试完整的 Walk-Forward 验证流程"""
    
    def test_validate_insufficient_data(self):
        """测试数据不足的情况"""
        validator = WalkForwardValidator()
        
        # 创建太短的数据
        prices = pd.Series([100, 101, 102])
        
        # 定义简单的因子和优化函数
        def simple_factor(prices, **params):
            return prices.pct_change(5) * 100
        
        def simple_optimize(prices, param_space):
            return {}
        
        result = validator.validate(prices, simple_factor, {}, simple_optimize)
        
        assert result.total_windows == 0
        assert result.passed_windows == 0
        assert result.pass_rate == 0.0
    
    def test_validate_basic(self):
        """测试基本的 Walk-Forward 验证"""
        config = WalkForwardConfig(
            optimization_window=20,
            test_window=5,
            step_size=5,
            min_trades=2,
            min_sharpe=0.0,
            max_drawdown=1.0,
            min_win_rate=0.0
        )
        validator = WalkForwardValidator(config)
        
        # 创建足够的数据
        np.random.seed(42)
        prices = pd.Series(np.cumsum(np.random.randn(100) * 0.1) + 100)
        
        # 定义简单的因子和优化函数
        def simple_factor(prices, **params):
            return prices.pct_change(5) * 100
        
        def simple_optimize(prices, param_space):
            return {}
        
        result = validator.validate(prices, simple_factor, {}, simple_optimize)
        
        # 检查结果
        assert result.total_windows > 0
        assert isinstance(result.pass_rate, float)
        assert isinstance(result.avg_oos_sharpe, float)
        assert isinstance(result.avg_oos_win_rate, float)
        assert isinstance(result.max_oos_drawdown, float)
        assert len(result.window_results) > 0


class TestConvenienceFunction:
    """测试便捷函数"""
    
    def test_walk_forward_validate(self):
        """测试 walk_forward_validate 便捷函数"""
        config = WalkForwardConfig(
            optimization_window=20,
            test_window=5,
            step_size=5,
            min_trades=2,
            min_sharpe=0.0,
            max_drawdown=1.0,
            min_win_rate=0.0
        )
        
        # 创建足够的数据
        np.random.seed(42)
        prices = pd.Series(np.cumsum(np.random.randn(100) * 0.1) + 100)
        
        # 定义简单的因子和优化函数
        def simple_factor(prices, **params):
            return prices.pct_change(5) * 100
        
        def simple_optimize(prices, param_space):
            return {}
        
        result = walk_forward_validate(prices, simple_factor, {}, simple_optimize, config)
        
        # 检查结果
        assert isinstance(result, WalkForwardResult)
        assert result.total_windows > 0


class TestEdgeCases:
    """测试边界条件"""
    
    def test_constant_prices(self):
        """测试常数价格序列"""
        config = WalkForwardConfig(
            optimization_window=20,
            test_window=5,
            step_size=5,
            min_trades=2,
            min_sharpe=0.0,
            max_drawdown=1.0,
            min_win_rate=0.0
        )
        validator = WalkForwardValidator(config)
        
        # 常数价格序列
        prices = pd.Series([100.0] * 100)
        
        # 定义简单的因子和优化函数
        def simple_factor(prices, **params):
            return prices.pct_change(5) * 100
        
        def simple_optimize(prices, param_space):
            return {}
        
        result = validator.validate(prices, simple_factor, {}, simple_optimize)
        
        # 应该能够正常处理
        assert result.total_windows > 0
    
    def test_highly_volatile_prices(self):
        """测试高波动价格序列"""
        config = WalkForwardConfig(
            optimization_window=20,
            test_window=5,
            step_size=5,
            min_trades=2,
            min_sharpe=0.0,
            max_drawdown=1.0,
            min_win_rate=0.0
        )
        validator = WalkForwardValidator(config)
        
        # 高波动价格序列
        np.random.seed(42)
        prices = pd.Series(np.cumsum(np.random.randn(100) * 10) + 100)
        
        # 定义简单的因子和优化函数
        def simple_factor(prices, **params):
            return prices.pct_change(5) * 100
        
        def simple_optimize(prices, param_space):
            return {}
        
        result = validator.validate(prices, simple_factor, {}, simple_optimize)
        
        # 应该能够正常处理
        assert result.total_windows > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
