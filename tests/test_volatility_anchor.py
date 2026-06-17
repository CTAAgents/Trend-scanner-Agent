"""
波动幅度止损锚点测试模块

测试 VolatilityAnchor 类。
覆盖：
1. 中位数计算
2. 锚点生成
3. 持仓止损计算
4. 边界条件

创建日期：2026-06-17
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import numpy as np
import pandas as pd
from scripts.trend_scanner.volatility_anchor import (
    VolatilityAnchor,
    volatility_anchor
)


class TestVolatilityAnchor:
    """测试波动幅度止损锚点"""
    
    def test_anchor_initialization(self):
        """测试锚点计算器初始化"""
        anchor = VolatilityAnchor()
        
        assert anchor.window == 20
        assert anchor.multiplier == 2.0
    
    def test_custom_config(self):
        """测试自定义配置"""
        anchor = VolatilityAnchor(window=10, multiplier=1.5)
        
        assert anchor.window == 10
        assert anchor.multiplier == 1.5
    
    def test_calculate_basic(self):
        """测试基本的锚点计算"""
        # 创建测试数据（确保 high > low）
        np.random.seed(42)
        n = 100
        base = np.cumsum(np.random.randn(n) * 0.5) + 100
        df = pd.DataFrame({
            'high': base + 1,
            'low': base - 1
        })
        
        anchor = VolatilityAnchor(window=20, multiplier=2.0)
        result = anchor.calculate(df)
        
        assert isinstance(result, pd.Series)
        assert len(result) == n
        # 前 window-1 个值应该是 NaN
        assert result.iloc[:19].isna().all()
        # 后续值应该是正数
        assert (result.iloc[19:] > 0).all()
    
    def test_calculate_with_different_windows(self):
        """测试不同窗口大小的计算"""
        # 创建测试数据
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            'high': np.cumsum(np.random.randn(n) * 0.5) + 100,
            'low': np.cumsum(np.random.randn(n) * 0.5) + 98
        })
        
        # 测试不同窗口
        for window in [5, 10, 20, 50]:
            anchor = VolatilityAnchor(window=window)
            result = anchor.calculate(df)
            
            assert isinstance(result, pd.Series)
            assert len(result) == n
            # 前 window-1 个值应该是 NaN
            assert result.iloc[:window-1].isna().all()
    
    def test_calculate_with_different_multipliers(self):
        """测试不同系数的计算"""
        # 创建测试数据
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            'high': np.cumsum(np.random.randn(n) * 0.5) + 100,
            'low': np.cumsum(np.random.randn(n) * 0.5) + 98
        })
        
        # 测试不同系数
        for multiplier in [1.0, 1.5, 2.0, 3.0]:
            anchor = VolatilityAnchor(multiplier=multiplier)
            result = anchor.calculate(df)
            
            assert isinstance(result, pd.Series)
            assert len(result) == n
    
    def test_calculate_for_long_position(self):
        """测试多头持仓的止损计算"""
        # 创建测试数据
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            'high': np.cumsum(np.random.randn(n) * 0.5) + 100,
            'low': np.cumsum(np.random.randn(n) * 0.5) + 98
        })
        
        anchor = VolatilityAnchor(window=20, multiplier=2.0)
        entry_price = 100.0
        
        stop_loss = anchor.calculate_for_position(df, entry_price, 'long')
        
        assert isinstance(stop_loss, float)
        # 多头止损应该低于入场价
        assert stop_loss < entry_price
    
    def test_calculate_for_short_position(self):
        """测试空头持仓的止损计算"""
        # 创建测试数据
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            'high': np.cumsum(np.random.randn(n) * 0.5) + 100,
            'low': np.cumsum(np.random.randn(n) * 0.5) + 98
        })
        
        anchor = VolatilityAnchor(window=20, multiplier=2.0)
        entry_price = 100.0
        
        stop_loss = anchor.calculate_for_position(df, entry_price, 'short')
        
        assert isinstance(stop_loss, float)
        # 空头止损应该高于入场价
        assert stop_loss > entry_price


class TestConvenienceFunction:
    """测试便捷函数"""
    
    def test_volatility_anchor_basic(self):
        """测试基本的便捷函数"""
        # 创建测试数据
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            'high': np.cumsum(np.random.randn(n) * 0.5) + 100,
            'low': np.cumsum(np.random.randn(n) * 0.5) + 98
        })
        
        result = volatility_anchor(df, window=20, multiplier=2.0)
        
        assert isinstance(result, pd.DataFrame)
        assert 'anchor' in result.columns
        assert 'candle_height' in result.columns
    
    def test_volatility_anchor_with_config(self):
        """测试带配置的便捷函数"""
        # 创建测试数据
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            'high': np.cumsum(np.random.randn(n) * 0.5) + 100,
            'low': np.cumsum(np.random.randn(n) * 0.5) + 98
        })
        
        result = volatility_anchor(df, window=10, multiplier=1.5)
        
        assert isinstance(result, pd.DataFrame)
        assert 'anchor' in result.columns
        assert 'candle_height' in result.columns


class TestEdgeCases:
    """测试边界条件"""
    
    def test_empty_dataframe(self):
        """测试空 DataFrame"""
        anchor = VolatilityAnchor()
        
        df = pd.DataFrame(columns=['high', 'low'])
        result = anchor.calculate(df)
        
        assert isinstance(result, pd.Series)
        assert len(result) == 0
    
    def test_single_row(self):
        """测试单行数据"""
        anchor = VolatilityAnchor(window=5)
        
        df = pd.DataFrame({
            'high': [100.0],
            'low': [98.0]
        })
        result = anchor.calculate(df)
        
        assert isinstance(result, pd.Series)
        assert len(result) == 1
        # 单行数据，窗口不足，应该是 NaN
        assert result.iloc[0] is np.nan or pd.isna(result.iloc[0])
    
    def test_constant_prices(self):
        """测试常数价格"""
        anchor = VolatilityAnchor(window=5)
        
        df = pd.DataFrame({
            'high': [100.0] * 20,
            'low': [98.0] * 20
        })
        result = anchor.calculate(df)
        
        assert isinstance(result, pd.Series)
        assert len(result) == 20
        # 常数价格，波动幅度应该等于 high - low
        assert (result.iloc[4:] == 4.0).all()  # (100 - 98) * 2.0 = 4.0
    
    def test_high_volatility(self):
        """测试高波动数据"""
        anchor = VolatilityAnchor(window=10)
        
        # 创建高波动数据
        np.random.seed(42)
        n = 50
        df = pd.DataFrame({
            'high': np.cumsum(np.random.randn(n) * 5) + 100,
            'low': np.cumsum(np.random.randn(n) * 5) + 90
        })
        
        result = anchor.calculate(df)
        
        assert isinstance(result, pd.Series)
        assert len(result) == n
        # 高波动数据，锚点值应该较大
        assert (result.iloc[9:] > 0).all()


class TestReasonerIntegration:
    """测试 Reasoner 集成"""
    
    def test_anchor_as_reference(self):
        """测试锚点作为参考值"""
        # 创建测试数据
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            'high': np.cumsum(np.random.randn(n) * 0.5) + 100,
            'low': np.cumsum(np.random.randn(n) * 0.5) + 98
        })
        
        anchor = VolatilityAnchor(window=20, multiplier=2.0)
        entry_price = 100.0
        
        # 计算多头止损
        stop_loss_long = anchor.calculate_for_position(df, entry_price, 'long')
        
        # 计算空头止损
        stop_loss_short = anchor.calculate_for_position(df, entry_price, 'short')
        
        # 验证止损位置
        assert stop_loss_long < entry_price
        assert stop_loss_short > entry_price
        
        # 验证止损距离
        distance_long = entry_price - stop_loss_long
        distance_short = stop_loss_short - entry_price
        
        # 止损距离应该大于0
        assert distance_long > 0
        assert distance_short > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
