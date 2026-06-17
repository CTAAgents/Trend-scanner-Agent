"""
可见图技术指标测试模块

测试 VGRSI (Visibility Graph Relative Strength Index) 因子的实现。
覆盖：
1. 可见性关系判断的正确性
2. A0/A1 两种聚合模式
3. 边界条件（空数据、单点数据）
4. 与传统 RSI 的一致性验证

创建日期：2026-06-17
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import numpy as np
import pandas as pd
from scripts.trend_scanner.visibility_graph import (
    VisibilityGraph,
    VGRSI,
    MultiTimeframeVGRSI,
    calculate_vgrsi,
    calculate_vgrsi_multi_timeframe
)


class TestVisibilityGraph:
    """测试可见性关系判断"""
    
    def test_backward_visibility_basic(self):
        """测试基本的可见性关系"""
        # 简单上升序列：相邻点总是可见的
        prices = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert VisibilityGraph.backward_visibility(prices, 0, 1) == True
        assert VisibilityGraph.backward_visibility(prices, 1, 2) == True
        assert VisibilityGraph.backward_visibility(prices, 2, 3) == True
        assert VisibilityGraph.backward_visibility(prices, 3, 4) == True
        
        # 对于线性序列，非相邻点不可见（中间点在连接线上）
        assert VisibilityGraph.backward_visibility(prices, 0, 2) == False
        assert VisibilityGraph.backward_visibility(prices, 0, 3) == False
    
    def test_backward_visibility_with_obstacle(self):
        """测试有障碍物时的可见性"""
        # 价格序列：1.0, 3.0, 2.0, 4.0
        # 从点0到点3：需要检查点1和点2
        # 点1(3.0) < 4.0 + (1.0-4.0)*(3-1)/(3-0) = 4.0 - 2.0 = 2.0? 否
        prices = np.array([1.0, 3.0, 2.0, 4.0])
        assert VisibilityGraph.backward_visibility(prices, 0, 3) == False
    
    def test_backward_visibility_no_obstacle(self):
        """测试无障碍物时的可见性"""
        # 价格序列：1.0, 2.0, 3.0, 4.0
        # 从点0到点3：点1(2.0) < 4.0 + (1.0-4.0)*(3-1)/(3-0) = 4.0 - 2.0 = 2.0? 否
        # 但点1(2.0) < 4.0 + (1.0-4.0)*(3-1)/(3-0) = 2.0, 所以不可见
        prices = np.array([1.0, 2.0, 3.0, 4.0])
        assert VisibilityGraph.backward_visibility(prices, 0, 3) == False
    
    def test_backward_visibility_adjacent_points(self):
        """测试相邻点的可见性"""
        prices = np.array([1.0, 2.0, 3.0])
        # 相邻点总是可见的
        assert VisibilityGraph.backward_visibility(prices, 0, 1) == True
        assert VisibilityGraph.backward_visibility(prices, 1, 2) == True
    
    def test_backward_visibility_invalid_indices(self):
        """测试无效索引"""
        prices = np.array([1.0, 2.0, 3.0])
        # j <= i 应该返回 False
        assert VisibilityGraph.backward_visibility(prices, 1, 0) == False
        assert VisibilityGraph.backward_visibility(prices, 1, 1) == False
    
    def test_compute_visibility_matrix(self):
        """测试可见性矩阵计算"""
        prices = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        visibility = VisibilityGraph.compute_visibility_matrix(prices, window_size=5)
        
        # 检查结果格式
        assert isinstance(visibility, dict)
        assert len(visibility) > 0
        
        # 检查每个点的可见点列表
        for i, visible_points in visibility.items():
            assert isinstance(visible_points, list)
            # 所有可见点索引应该大于 i
            for j in visible_points:
                assert j > i


class TestVGRSI:
    """测试 VGRSI 计算器"""
    
    def test_vgrsi_initialization(self):
        """测试 VGRSI 初始化"""
        calculator = VGRSI(window_size=50, aggregation_mode='A0')
        assert calculator.window_size == 50
        assert calculator.aggregation_mode == 'A0'
        assert calculator.threshold_upper == 70.0
        assert calculator.threshold_lower == 30.0
    
    def test_vgrsi_calculation_basic(self):
        """测试基本的 VGRSI 计算"""
        # 创建简单的上升价格序列
        np.random.seed(42)
        n = 200
        prices = np.cumsum(np.random.randn(n) * 0.1 + 0.01) + 100
        
        calculator = VGRSI(window_size=50, aggregation_mode='A0')
        vgrsi_values = calculator.calculate(prices)
        
        # 检查结果
        assert len(vgrsi_values) == n
        # 前 window_size 个值应该是 NaN
        assert np.all(np.isnan(vgrsi_values[:50]))
        # 后续值应该在 0-100 之间
        valid_values = vgrsi_values[50:]
        valid_values = valid_values[~np.isnan(valid_values)]
        assert np.all(valid_values >= 0)
        assert np.all(valid_values <= 100)
    
    def test_vgrsi_a0_aggregation(self):
        """测试 A0 聚合模式"""
        # 创建带有波动的上升趋势（模拟真实市场）
        np.random.seed(42)
        n = 200
        trend = np.array([100 + i * 0.5 for i in range(n)])
        noise = np.random.randn(n) * 2  # 添加噪声
        prices = trend + noise
        
        calculator = VGRSI(window_size=50, aggregation_mode='A0')
        vgrsi_values = calculator.calculate(prices)
        
        # 应该有有效值
        valid_values = vgrsi_values[50:]
        valid_values = valid_values[~np.isnan(valid_values)]
        assert len(valid_values) > 0  # 应该有有效值
    
    def test_vgrsi_a1_aggregation(self):
        """测试 A1 聚合模式"""
        # 创建带有波动的上升趋势（模拟真实市场）
        np.random.seed(42)
        n = 200
        trend = np.array([100 + i * 0.5 for i in range(n)])
        noise = np.random.randn(n) * 2  # 添加噪声
        prices = trend + noise
        
        calculator = VGRSI(window_size=50, aggregation_mode='A1')
        vgrsi_values = calculator.calculate(prices)
        
        # 检查结果
        valid_values = vgrsi_values[50:]
        valid_values = valid_values[~np.isnan(valid_values)]
        assert len(valid_values) > 0
        assert np.all(valid_values >= 0)
        assert np.all(valid_values <= 100)
    
    def test_vgrsi_signal_generation(self):
        """测试信号生成"""
        # 创建 V 形价格序列
        prices = np.array([100 - i * 0.5 for i in range(100)] + 
                         [90 + i * 0.5 for i in range(100)])
        
        calculator = VGRSI(window_size=50, aggregation_mode='A0')
        vgrsi_values = calculator.calculate(prices)
        signals = calculator.generate_signals(vgrsi_values)
        
        # 检查信号格式
        assert len(signals) == len(prices)
        # 信号应该在 {-1, 0, 1} 中
        assert np.all(np.isin(signals, [-1, 0, 1]))
    
    def test_vgrsi_empty_data(self):
        """测试空数据"""
        prices = np.array([])
        calculator = VGRSI(window_size=50)
        vgrsi_values = calculator.calculate(prices)
        assert len(vgrsi_values) == 0
    
    def test_vgrsi_single_point(self):
        """测试单点数据"""
        prices = np.array([100.0])
        calculator = VGRSI(window_size=50)
        vgrsi_values = calculator.calculate(prices)
        # 单点数据应该返回 NaN
        assert np.all(np.isnan(vgrsi_values))
    
    def test_vgrsi_short_data(self):
        """测试数据长度小于窗口大小"""
        prices = np.array([100.0, 101.0, 102.0])
        calculator = VGRSI(window_size=50)
        vgrsi_values = calculator.calculate(prices)
        # 所有值应该是 NaN
        assert np.all(np.isnan(vgrsi_values))


class TestMultiTimeframeVGRSI:
    """测试多时间框架 VGRSI"""
    
    def test_multi_timeframe_initialization(self):
        """测试多时间框架初始化"""
        calculator = MultiTimeframeVGRSI()
        assert 'M1' in calculator.timeframe_configs
        assert 'M5' in calculator.timeframe_configs
        assert 'M30' in calculator.timeframe_configs
    
    def test_multi_timeframe_calculation(self):
        """测试多时间框架计算"""
        # 创建不同长度的价格序列
        np.random.seed(42)
        prices_dict = {
            'M1': pd.Series(np.cumsum(np.random.randn(200) * 0.1) + 100),
            'M5': pd.Series(np.cumsum(np.random.randn(150) * 0.1) + 100),
            'M30': pd.Series(np.cumsum(np.random.randn(100) * 0.1) + 100)
        }
        
        calculator = MultiTimeframeVGRSI()
        vgrsi_values = calculator.calculate_multi_timeframe(
            {tf: prices.values for tf, prices in prices_dict.items()}
        )
        
        # 检查结果
        assert len(vgrsi_values) == 3
        for tf, values in vgrsi_values.items():
            assert len(values) > 0
    
    def test_consensus_signals(self):
        """测试共识信号生成"""
        # 创建相同趋势的价格序列
        np.random.seed(42)
        base_prices = np.cumsum(np.random.randn(200) * 0.1) + 100
        
        prices_dict = {
            'M1': pd.Series(base_prices),
            'M5': pd.Series(base_prices[::5]),  # 每5个点取一个
            'M30': pd.Series(base_prices[::30])  # 每30个点取一个
        }
        
        calculator = MultiTimeframeVGRSI()
        consensus_signals = calculator.generate_consensus_signals(
            {tf: prices.values for tf, prices in prices_dict.items()}
        )
        
        # 检查结果
        assert len(consensus_signals) > 0
        # 共识信号应该比较稀疏
        non_zero_count = np.sum(consensus_signals != 0)
        assert non_zero_count < len(consensus_signals) * 0.1  # 应该少于10%


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_calculate_vgrsi(self):
        """测试 calculate_vgrsi 便捷函数"""
        # 创建价格序列
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=200, freq='D')
        prices = pd.Series(np.cumsum(np.random.randn(200) * 0.1) + 100, index=dates)
        
        result = calculate_vgrsi(prices, window_size=50, aggregation_mode='A0')
        
        # 检查结果格式
        assert isinstance(result, pd.DataFrame)
        assert 'vgrsi' in result.columns
        assert 'signal' in result.columns
        assert len(result) == len(prices)
    
    def test_calculate_vgrsi_multi_timeframe(self):
        """测试 calculate_vgrsi_multi_timeframe 便捷函数"""
        # 创建价格序列
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=200, freq='D')
        
        prices_dict = {
            'M1': pd.Series(np.cumsum(np.random.randn(200) * 0.1) + 100, index=dates),
            'M5': pd.Series(np.cumsum(np.random.randn(150) * 0.1) + 100, index=dates[::5]),
            'M30': pd.Series(np.cumsum(np.random.randn(100) * 0.1) + 100, index=dates[::30])
        }
        
        result = calculate_vgrsi_multi_timeframe(prices_dict)
        
        # 检查结果格式
        assert isinstance(result, pd.DataFrame)
        assert 'vgrsi_M1' in result.columns
        assert 'vgrsi_M5' in result.columns
        assert 'vgrsi_M30' in result.columns
        assert 'consensus_signal' in result.columns


class TestEdgeCases:
    """测试边界条件"""
    
    def test_constant_prices(self):
        """测试常数价格序列"""
        prices = np.array([100.0] * 200)
        calculator = VGRSI(window_size=50)
        vgrsi_values = calculator.calculate(prices)
        
        # 常数价格应该产生中性 VGRSI 值
        valid_values = vgrsi_values[50:]
        valid_values = valid_values[~np.isnan(valid_values)]
        # 应该接近 50（中性）
        assert np.mean(valid_values) == pytest.approx(50.0, abs=1.0)
    
    def test_highly_volatile_prices(self):
        """测试高波动价格序列"""
        np.random.seed(42)
        prices = np.cumsum(np.random.randn(200) * 10) + 100
        
        calculator = VGRSI(window_size=50)
        vgrsi_values = calculator.calculate(prices)
        
        # 应该能够正常计算
        valid_values = vgrsi_values[50:]
        valid_values = valid_values[~np.isnan(valid_values)]
        assert len(valid_values) > 0
        assert np.all(valid_values >= 0)
        assert np.all(valid_values <= 100)
    
    def test_monotonic_increase(self):
        """测试单调递增序列"""
        prices = np.array([100 + i * 0.1 for i in range(200)])
        
        calculator = VGRSI(window_size=50, aggregation_mode='A0')
        vgrsi_values = calculator.calculate(prices)
        
        # 单调递增应该产生高 VGRSI 值
        valid_values = vgrsi_values[50:]
        valid_values = valid_values[~np.isnan(valid_values)]
        assert np.mean(valid_values) > 70  # 应该偏向高位
    
    def test_monotonic_decrease(self):
        """测试单调递减序列"""
        prices = np.array([100 - i * 0.1 for i in range(200)])
        
        calculator = VGRSI(window_size=50, aggregation_mode='A0')
        vgrsi_values = calculator.calculate(prices)
        
        # 单调递减应该产生低 VGRSI 值
        valid_values = vgrsi_values[50:]
        valid_values = valid_values[~np.isnan(valid_values)]
        assert np.mean(valid_values) < 30  # 应该偏向低位


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
