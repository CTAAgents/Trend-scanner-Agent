"""
添加多周期 VGRSI 一致性因子到种子因子池

基于论文 "Visibility Graphs Can Make Money in Financial Markets" (arXiv:2605.01300)
将 MultiTimeframeVGRSIFactor 添加到系统的种子因子池中。

创建日期：2026-06-17
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.trend_scanner.seed_factor_pool import SeedFactorPool


def add_multi_timeframe_vgrsi_factor():
    """添加多周期 VGRSI 一致性因子到种子因子池"""
    
    # 初始化种子因子池
    pool = SeedFactorPool()
    
    # 多周期 VGRSI 一致性因子代码
    factor_code = '''
import numpy as np
import pandas as pd

def factor(df, window_m1=50, window_m5=100, window_m30=150, 
           threshold_upper=70, threshold_lower=30):
    """
    多周期 VGRSI 一致性因子
    
    基于可见图的多时间框架 RSI 变体，使用 M1、M5、M30 三个时间周期同时确认信号，
    只有三个周期同向才产生最终信号。
    
    Args:
        df: DataFrame with 'close' column
        window_m1: M1 时间框架窗口大小
        window_m5: M5 时间框架窗口大小
        window_m30: M30 时间框架窗口大小
        threshold_upper: 买入信号阈值
        threshold_lower: 卖出信号阈值
    
    Returns:
        pd.Series: 共识因子值 (1=多, -1=空, 0=无共识)
    """
    from scripts.trend_scanner.visibility_graph import MultiTimeframeVGRSIFactor
    
    # 构建多时间框架数据
    # 注意：这里使用单时间框架数据模拟多时间框架
    # 实际使用时需要提供真正的多时间框架数据
    prices_dict = {
        'M1': df['close'],
        'M5': df['close'].resample('5D').last().dropna(),
        'M30': df['close'].resample('30D').last().dropna()
    }
    
    # 配置各时间框架
    timeframe_configs = {
        'M1': {'window_size': window_m1, 'aggregation_mode': 'A0'},
        'M5': {'window_size': window_m5, 'aggregation_mode': 'A0'},
        'M30': {'window_size': window_m30, 'aggregation_mode': 'A0'}
    }
    
    # 计算共识因子
    factor = MultiTimeframeVGRSIFactor(
        timeframe_configs=timeframe_configs,
        threshold_upper=threshold_upper,
        threshold_lower=threshold_lower
    )
    
    consensus_values = factor.calculate(prices_dict)
    
    # 对齐到原始数据的索引
    result = pd.Series(0, index=df.index)
    for idx in consensus_values.index:
        if idx in result.index:
            result[idx] = consensus_values[idx]
    
    return result
'''
    
    # 添加因子到种子因子池
    pool.add_seed(
        name='MultiTimeframeVGRSI',
        code=factor_code,
        logic='基于可见图的多时间框架 RSI 变体，使用 M1、M5、M30 三个时间周期同时确认信号，只有三个周期同向才产生最终信号。',
        economic_rationale='多时间框架一致性可以有效过滤噪声信号，提高信号的可靠性。只有当所有时间框架都确认趋势时，才产生交易信号。',
        source='arXiv:2605.01300 - Visibility Graphs Can Make Money in Financial Markets',
        category='composite'
    )
    
    # 打印摘要
    summary = pool.get_summary()
    print(f"种子因子池摘要:")
    print(f"  总因子数: {summary['total']}")
    print(f"  分类: {summary['categories']}")
    print(f"  状态: {summary['statuses']}")
    
    # 获取待验证的种子
    pending = pool.get_pending_seeds()
    print(f"\n待验证的种子因子 ({len(pending)}):")
    for seed in pending:
        print(f"  - {seed.name}: {seed.logic[:50]}...")


if __name__ == '__main__':
    add_multi_timeframe_vgrsi_factor()
