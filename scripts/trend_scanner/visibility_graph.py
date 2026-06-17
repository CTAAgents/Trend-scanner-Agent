"""
可见图技术指标模块 (Visibility Graph Indicators)

基于论文 "Visibility Graphs Can Make Money in Financial Markets" (arXiv: 2605.01300)
实现 VGRSI (Visibility Graph Relative Strength Index) 因子。

核心思想：
将金融时间序列转换为可见图网络，利用价格点之间的几何可见关系
替代传统 RSI 的简单价格变化，构造新型技术指标。

两种聚合模式：
- A0 (均值聚合): 趋势持续性指标，类似趋势滤波器
- A1 (比率聚合): 突破脉冲指标，类似突破信号

版本：v1.0
创建日期：2026-06-17
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class VisibilityGraph:
    """
    可见图计算器
    
    实现向后可见性关系判断和聚合函数。
    """
    
    @staticmethod
    def backward_visibility(prices: np.ndarray, i: int, j: int) -> bool:
        """
        判断价格点 j 是否从点 i 可见（向后可见性关系）
        
        根据论文公式 (1):
        p[k] < p[j] + (p[i] - p[j]) * (j - k) / (j - i)
        对所有 k ∈ (i, j)
        
        Args:
            prices: 价格序列
            i: 起始点索引
            j: 目标点索引 (j > i)
            
        Returns:
            bool: j 是否从 i 可见
        """
        if j <= i:
            return False
        
        p_i = prices[i]
        p_j = prices[j]
        
        # 检查所有中间点 k
        for k in range(i + 1, j):
            # 可见性条件: p[k] < p[j] + (p[i] - p[j]) * (j - k) / (j - i)
            threshold = p_j + (p_i - p_j) * (j - k) / (j - i)
            if prices[k] >= threshold:
                return False
        
        return True
    
    @staticmethod
    def compute_visibility_matrix(prices: np.ndarray, window_size: int = 100) -> Dict[int, list]:
        """
        计算可见性关系矩阵
        
        对每个时间点 i，找出所有从 i 可见的后续点 j。
        
        Args:
            prices: 价格序列
            window_size: 回看窗口大小
            
        Returns:
            Dict[int, list]: 可见性关系字典 {i: [j1, j2, ...]}
        """
        n = len(prices)
        visibility = {}
        
        for i in range(max(0, n - window_size), n):
            visible_points = []
            # 向后查找可见点
            for j in range(i + 1, n):
                if VisibilityGraph.backward_visibility(prices, i, j):
                    visible_points.append(j)
            visibility[i] = visible_points
        
        return visibility


class VGRSI:
    """
    VGRSI (Visibility Graph Relative Strength Index) 计算器
    
    基于可见图的 RSI 变体，有两种聚合模式：
    - A0: 均值聚合，捕捉趋势持续性
    - A1: 比率聚合，捕捉突破脉冲
    """
    
    def __init__(self, 
                 window_size: int = 100,
                 aggregation_mode: str = 'A0',
                 threshold_upper: float = 70.0,
                 threshold_lower: float = 30.0):
        """
        初始化 VGRSI 计算器
        
        Args:
            window_size: 可见性计算的回看窗口
            aggregation_mode: 聚合模式 ('A0' 或 'A1')
            threshold_upper: 买入信号阈值
            threshold_lower: 卖出信号阈值
        """
        self.window_size = window_size
        self.aggregation_mode = aggregation_mode
        self.threshold_upper = threshold_upper
        self.threshold_lower = threshold_lower
    
    def _aggregate_A0(self, prices: np.ndarray, i: int, visible_points: list) -> Tuple[float, float]:
        """
        A0 聚合模式（均值聚合）
        
        计算 VGRSI+ 和 VGRSI-:
        - VGRSI+ = mean(f(i,j)) for j where f(i,j) > 0
        - VGRSI- = mean(|f(i,j)|) for j where f(i,j) < 0
        
        其中 f(i,j) = (p[j] - p[i]) / p[i]
        
        Args:
            prices: 价格序列
            i: 当前时间点
            visible_points: 从 i 可见的点列表
            
        Returns:
            Tuple[float, float]: (VGRSI+, VGRSI-)
        """
        if not visible_points:
            return 0.0, 0.0
        
        p_i = prices[i]
        positive_values = []
        negative_values = []
        
        for j in visible_points:
            # 避免除零
            if abs(p_i) < 1e-10:
                f_ij = 0.0
            else:
                f_ij = (prices[j] - p_i) / p_i
            if f_ij > 0:
                positive_values.append(f_ij)
            elif f_ij < 0:
                negative_values.append(abs(f_ij))
        
        vgrsi_pos = np.mean(positive_values) if positive_values else 0.0
        vgrsi_neg = np.mean(negative_values) if negative_values else 0.0
        
        return vgrsi_pos, vgrsi_neg
    
    def _aggregate_A1(self, prices: np.ndarray, i: int, visible_points: list) -> Tuple[float, float]:
        """
        A1 聚合模式（比率聚合）
        
        计算 VGRSI+ 和 VGRSI-:
        - VGRSI+ = count(j where f(i,j) > 0) / count(j where f(i,j) < 0)
        - VGRSI- = 1 (归一化)
        
        Args:
            prices: 价格序列
            i: 当前时间点
            visible_points: 从 i 可见的点列表
            
        Returns:
            Tuple[float, float]: (VGRSI+, VGRSI-)
        """
        if not visible_points:
            return 0.0, 0.0
        
        p_i = prices[i]
        positive_count = 0
        negative_count = 0
        
        for j in visible_points:
            # 避免除零
            if abs(p_i) < 1e-10:
                f_ij = 0.0
            else:
                f_ij = (prices[j] - p_i) / p_i
            if f_ij > 0:
                positive_count += 1
            elif f_ij < 0:
                negative_count += 1
        
        # 避免除零
        if negative_count == 0:
            vgrsi_pos = float(positive_count)
        else:
            vgrsi_pos = positive_count / negative_count
        
        return vgrsi_pos, 1.0
    
    def calculate(self, prices: np.ndarray) -> np.ndarray:
        """
        计算 VGRSI 指标
        
        Args:
            prices: 价格序列
            
        Returns:
            np.ndarray: VGRSI 值序列
        """
        n = len(prices)
        vgrsi_values = np.full(n, np.nan)
        
        for i in range(self.window_size, n):
            # 获取回看窗口内的价格
            window_start = max(0, i - self.window_size)
            window_prices = prices[window_start:i + 1]
            
            # 计算可见性关系
            visibility = VisibilityGraph.compute_visibility_matrix(window_prices, self.window_size)
            
            # 获取当前点的可见点
            current_idx = i - window_start
            if current_idx not in visibility:
                continue
            
            visible_points = visibility[current_idx]
            if not visible_points:
                continue
            
            # 根据聚合模式计算 VGRSI
            if self.aggregation_mode == 'A0':
                vgrsi_pos, vgrsi_neg = self._aggregate_A0(window_prices, current_idx, visible_points)
            else:
                vgrsi_pos, vgrsi_neg = self._aggregate_A1(window_prices, current_idx, visible_points)
            
            # 计算 VGRSI 值（类似 RSI 公式）
            if vgrsi_pos + vgrsi_neg > 0:
                vgrsi_values[i] = 100 * vgrsi_pos / (vgrsi_pos + vgrsi_neg)
            else:
                vgrsi_values[i] = 50.0  # 中性值
        
        return vgrsi_values
    
    def generate_signals(self, vgrsi_values: np.ndarray) -> np.ndarray:
        """
        根据 VGRSI 值生成交易信号
        
        Args:
            vgrsi_values: VGRSI 值序列
            
        Returns:
            np.ndarray: 信号序列 (1=买入, -1=卖出, 0=无信号)
        """
        signals = np.zeros_like(vgrsi_values)
        
        for i in range(1, len(vgrsi_values)):
            if np.isnan(vgrsi_values[i]) or np.isnan(vgrsi_values[i-1]):
                continue
            
            # 买入信号: VGRSI 从下方穿越上阈值
            if vgrsi_values[i] > self.threshold_upper and vgrsi_values[i-1] <= self.threshold_upper:
                signals[i] = 1
            # 卖出信号: VGRSI 从上方穿越下阈值
            elif vgrsi_values[i] < self.threshold_lower and vgrsi_values[i-1] >= self.threshold_lower:
                signals[i] = -1
        
        return signals


class MultiTimeframeVGRSI:
    """
    多时间框架 VGRSI 信号确认器
    
    在 M1、M5、M30 三个时间周期上同时确认信号，
    只有三个周期同向才产生最终信号。
    """
    
    def __init__(self, 
                 timeframe_configs: Dict[str, Dict[str, Any]] = None,
                 threshold_upper: float = 70.0,
                 threshold_lower: float = 30.0):
        """
        初始化多时间框架 VGRSI
        
        Args:
            timeframe_configs: 各时间框架的配置 {timeframe: {window_size, aggregation_mode}}
            threshold_upper: 买入信号阈值
            threshold_lower: 卖出信号阈值
        """
        if timeframe_configs is None:
            timeframe_configs = {
                'M1': {'window_size': 50, 'aggregation_mode': 'A0'},
                'M5': {'window_size': 100, 'aggregation_mode': 'A0'},
                'M30': {'window_size': 150, 'aggregation_mode': 'A0'}
            }
        
        self.timeframe_configs = timeframe_configs
        self.threshold_upper = threshold_upper
        self.threshold_lower = threshold_lower
        
        # 为每个时间框架创建 VGRSI 计算器
        self.vgrsi_calculators = {}
        for tf, config in timeframe_configs.items():
            self.vgrsi_calculators[tf] = VGRSI(
                window_size=config.get('window_size', 100),
                aggregation_mode=config.get('aggregation_mode', 'A0'),
                threshold_upper=threshold_upper,
                threshold_lower=threshold_lower
            )
    
    def calculate_multi_timeframe(self, prices_dict: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """
        计算多个时间框架的 VGRSI 值
        
        Args:
            prices_dict: 各时间框架的价格数据 {timeframe: prices}
            
        Returns:
            Dict[str, np.ndarray]: 各时间框架的 VGRSI 值
        """
        results = {}
        for tf, calculator in self.vgrsi_calculators.items():
            if tf in prices_dict:
                results[tf] = calculator.calculate(prices_dict[tf])
        return results
    
    def generate_consensus_signals(self, prices_dict: Dict[str, np.ndarray]) -> np.ndarray:
        """
        生成多时间框架共识信号
        
        只有当所有时间框架都产生同向信号时，才输出最终信号。
        
        Args:
            prices_dict: 各时间框架的价格数据
            
        Returns:
            np.ndarray: 共识信号序列 (1=买入, -1=卖出, 0=无信号)
        """
        # 计算各时间框架的 VGRSI
        vgrsi_values = self.calculate_multi_timeframe(prices_dict)
        
        if not vgrsi_values:
            return np.array([])
        
        # 找到最短的时间框架作为基准
        min_len = min(len(v) for v in vgrsi_values.values())
        
        # 生成各时间框架的信号
        signals_dict = {}
        for tf, values in vgrsi_values.items():
            # 截取到最短长度
            truncated = values[-min_len:]
            signals_dict[tf] = self.vgrsi_calculators[tf].generate_signals(truncated)
        
        # 计算共识信号
        consensus_signals = np.zeros(min_len)
        timeframes = list(signals_dict.keys())
        
        for i in range(min_len):
            # 检查所有时间框架是否都有信号
            all_signals = [signals_dict[tf][i] for tf in timeframes]
            
            # 只有所有时间框架都产生同向信号时才输出
            if all(s == 1 for s in all_signals):
                consensus_signals[i] = 1
            elif all(s == -1 for s in all_signals):
                consensus_signals[i] = -1
        
        return consensus_signals


def calculate_vgrsi(prices: pd.Series, 
                    window_size: int = 100,
                    aggregation_mode: str = 'A0',
                    threshold_upper: float = 70.0,
                    threshold_lower: float = 30.0) -> pd.DataFrame:
    """
    便捷函数：计算 VGRSI 指标
    
    Args:
        prices: 价格序列 (pandas Series)
        window_size: 可见性计算的回看窗口
        aggregation_mode: 聚合模式 ('A0' 或 'A1')
        threshold_upper: 买入信号阈值
        threshold_lower: 卖出信号阈值
        
    Returns:
        pd.DataFrame: 包含 VGRSI 值和信号的 DataFrame
    """
    calculator = VGRSI(
        window_size=window_size,
        aggregation_mode=aggregation_mode,
        threshold_upper=threshold_upper,
        threshold_lower=threshold_lower
    )
    
    vgrsi_values = calculator.calculate(prices.values)
    signals = calculator.generate_signals(vgrsi_values)
    
    result = pd.DataFrame({
        'vgrsi': vgrsi_values,
        'signal': signals
    }, index=prices.index)
    
    return result


def calculate_vgrsi_multi_timeframe(prices_dict: Dict[str, pd.Series],
                                    timeframe_configs: Dict[str, Dict[str, Any]] = None,
                                    threshold_upper: float = 70.0,
                                    threshold_lower: float = 30.0) -> pd.DataFrame:
    """
    便捷函数：计算多时间框架 VGRSI 共识信号
    
    Args:
        prices_dict: 各时间框架的价格数据 {timeframe: pd.Series}
        timeframe_configs: 各时间框架的配置
        threshold_upper: 买入信号阈值
        threshold_lower: 卖出信号阈值
        
    Returns:
        pd.DataFrame: 包含各时间框架 VGRSI 和共识信号的 DataFrame
    """
    calculator = MultiTimeframeVGRSI(
        timeframe_configs=timeframe_configs,
        threshold_upper=threshold_upper,
        threshold_lower=threshold_lower
    )
    
    # 计算各时间框架的 VGRSI
    vgrsi_values = calculator.calculate_multi_timeframe(
        {tf: prices.values for tf, prices in prices_dict.items()}
    )
    
    # 生成共识信号
    consensus_signals = calculator.generate_consensus_signals(
        {tf: prices.values for tf, prices in prices_dict.items()}
    )
    
    # 构建结果 DataFrame
    result_data = {}
    for tf, values in vgrsi_values.items():
        result_data[f'vgrsi_{tf}'] = values[-len(consensus_signals):]
    
    result_data['consensus_signal'] = consensus_signals
    
    # 使用最短时间框架的索引
    min_len_idx = min(len(prices) for prices in prices_dict.values())
    result = pd.DataFrame(result_data, index=prices_dict[list(prices_dict.keys())[0]].index[-min_len_idx:])
    
    return result
