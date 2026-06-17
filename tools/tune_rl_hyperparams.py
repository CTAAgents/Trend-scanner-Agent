"""
RL 超参调优脚本

使用 Walk-Forward 验证框架优化 RL 超参：
1. 定义超参搜索空间
2. 网格搜索或随机搜索
3. Walk-Forward 验证每个配置
4. 输出最优配置

使用方式：
    python tools/tune_rl_hyperparams.py --symbol RB --days 200 --trials 20

版本：v1.0
创建日期：2026-06-17
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from trend_scanner.storage.duckdb_store import DuckDBStore
from trend_scanner.rl import (
    AgentPPO,
    FuturesTradingEnv,
    walk_forward_validate_rl,
)
from trend_scanner.rl.walk_forward_rl import RLWalkForwardValidator
from trend_scanner.trend_scanner_config import (
    TrendScannerConfig,
    RLConfig,
)
from trend_scanner.walk_forward_validator import WalkForwardConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_and_prepare_data(symbol: str, days: int = 200) -> tuple:
    """
    加载并准备数据
    
    Returns:
        (price_data, state_features, state_dim)
    """
    db_path = "data/market.db"
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"DuckDB 数据库不存在: {db_path}")
    
    store = DuckDBStore(db_path)
    df = store.get_klines(symbol, days=days, timeframe='daily')
    
    if df is None or df.empty:
        raise ValueError(f"无法获取 {symbol} 的数据")
    
    # 计算技术指标
    df['return'] = df['close'].pct_change()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 布林带宽度
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_width'] = (4 * bb_std) / df['bb_middle']
    
    # 成交量变化
    df['volume_change'] = df['volume'].pct_change()
    
    # 填充 NaN
    df = df.fillna(method='bfill').fillna(0)
    
    # 准备数据
    feature_columns = ['return', 'rsi', 'bb_width', 'volume_change']
    state_features = df[feature_columns].values
    
    # 标准化
    mean = np.mean(state_features, axis=0)
    std = np.std(state_features, axis=0) + 1e-8
    state_features = (state_features - mean) / std
    
    # 价格数据
    price_data = df[['open', 'high', 'low', 'close', 'volume']].values
    
    # 状态维度
    state_dim = state_features.shape[1] + 2  # +2 for position and pnl
    
    return price_data, state_features, state_dim


def define_search_space() -> List[Dict[str, Any]]:
    """
    定义超参搜索空间
    
    Returns:
        超参配置列表
    """
    # 定义搜索空间
    search_space = {
        'net_dims': [[64, 64], [128, 64], [128, 128], [256, 128]],
        'gamma': [0.95, 0.99],
        'lambda_gae': [0.9, 0.95],
        'learning_rate': [1e-4, 2e-4, 5e-4],
        'batch_size': [32, 64, 128],
        'ratio_clip': [0.1, 0.2, 0.3],
    }
    
    # 生成所有组合
    keys = list(search_space.keys())
    values = list(search_space.values())
    
    configs = []
    for combination in product(*values):
        config = dict(zip(keys, combination))
        configs.append(config)
    
    return configs


def evaluate_config(config: Dict[str, Any],
                    price_data: np.ndarray,
                    state_features: np.ndarray,
                    state_dim: int,
                    wf_config: WalkForwardConfig) -> Dict[str, Any]:
    """
    评估单个配置
    
    Args:
        config: 超参配置
        price_data: 价格数据
        state_features: 状态特征
        state_dim: 状态维度
        wf_config: Walk-Forward 配置
    
    Returns:
        评估结果
    """
    # 创建 RL 配置
    rl_config = RLConfig(
        net_dims=config['net_dims'],
        gamma=config['gamma'],
        lambda_gae=config['lambda_gae'],
        learning_rate=config['learning_rate'],
        batch_size=config['batch_size'],
        ratio_clip=config['ratio_clip'],
    )
    
    # 运行 Walk-Forward 验证
    validator = RLWalkForwardValidator(config=wf_config, rl_config=rl_config)
    
    result = validator.validate(
        data=price_data,
        state_dim=state_dim,
        train_steps_per_window=500,  # 减少训练步数以加快搜索
    )
    
    return {
        'config': config,
        'pass_rate': result.pass_rate,
        'avg_oos_reward': result.avg_oos_reward,
        'avg_reward_ratio': result.avg_reward_ratio,
        'max_oos_drawdown': result.max_oos_drawdown,
        'recommendations': result.recommendations,
    }


def grid_search(symbol: str,
                days: int = 200,
                max_trials: int = 50,
                save_dir: str = "models/rl/tuning") -> Dict[str, Any]:
    """
    网格搜索最优超参
    
    Args:
        symbol: 品种代码
        days: 数据天数
        max_trials: 最大试验次数
        save_dir: 结果保存目录
    
    Returns:
        最优配置
    """
    logger.info(f"开始超参调优: {symbol}")
    
    # 加载数据
    price_data, state_features, state_dim = load_and_prepare_data(symbol, days)
    
    # Walk-Forward 配置
    wf_config = WalkForwardConfig(
        optimization_window=30,
        test_window=7,
        step_size=7,
    )
    
    # 生成搜索空间
    all_configs = define_search_space()
    
    # 随机采样（如果配置太多）
    if len(all_configs) > max_trials:
        indices = np.random.choice(len(all_configs), max_trials, replace=False)
        configs = [all_configs[i] for i in indices]
    else:
        configs = all_configs
    
    logger.info(f"搜索空间大小: {len(configs)} 个配置")
    
    # 评估每个配置
    results = []
    best_score = -np.inf
    best_config = None
    
    for i, config in enumerate(configs):
        logger.info(f"评估配置 {i+1}/{len(configs)}: {config}")
        
        try:
            result = evaluate_config(config, price_data, state_features, state_dim, wf_config)
            results.append(result)
            
            # 计算综合分数
            # 通过率权重 0.4, OOS 奖励权重 0.3, Reward Ratio 权重 0.3
            score = (
                0.4 * result['pass_rate'] +
                0.3 * max(result['avg_oos_reward'], 0) +
                0.3 * result['avg_reward_ratio']
            )
            
            if score > best_score:
                best_score = score
                best_config = config
            
            logger.info(f"  结果: pass_rate={result['pass_rate']:.2%}, "
                       f"oos_reward={result['avg_oos_reward']:.4f}, "
                       f"ratio={result['avg_reward_ratio']:.2f}")
            
        except Exception as e:
            logger.error(f"  评估失败: {e}")
            continue
    
    # 保存结果
    os.makedirs(save_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"{save_dir}/{symbol}_tuning_{timestamp}.json"
    
    output = {
        'symbol': symbol,
        'days': days,
        'total_configs': len(configs),
        'evaluated_configs': len(results),
        'best_config': best_config,
        'best_score': best_score,
        'all_results': results,
    }
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    
    logger.info(f"调优结果已保存到: {result_file}")
    
    # 打印最优配置
    logger.info("=" * 60)
    logger.info("最优配置:")
    logger.info("=" * 60)
    for key, value in best_config.items():
        logger.info(f"  {key}: {value}")
    logger.info(f"  综合分数: {best_score:.4f}")
    logger.info("=" * 60)
    
    return {
        'best_config': best_config,
        'best_score': best_score,
        'result_file': result_file,
        'all_results': results,
    }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='RL 超参调优脚本')
    
    parser.add_argument('--symbol', type=str, default='RB',
                        help='品种代码')
    parser.add_argument('--days', type=int, default=200,
                        help='数据天数')
    parser.add_argument('--trials', type=int, default=20,
                        help='最大试验次数')
    parser.add_argument('--save-dir', type=str, default='models/rl/tuning',
                        help='结果保存目录')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("RL 超参调优")
    logger.info("=" * 60)
    logger.info(f"品种: {args.symbol}")
    logger.info(f"数据天数: {args.days}")
    logger.info(f"最大试验次数: {args.trials}")
    logger.info("=" * 60)
    
    # 运行调优
    result = grid_search(
        symbol=args.symbol,
        days=args.days,
        max_trials=args.trials,
        save_dir=args.save_dir,
    )
    
    logger.info("调优完成!")


if __name__ == '__main__':
    main()
