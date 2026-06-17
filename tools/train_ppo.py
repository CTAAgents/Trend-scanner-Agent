"""
PPO 策略训练脚本

使用真实期货数据训练 PPO 策略，支持：
1. 从 DuckDB 加载历史数据
2. 计算技术指标作为状态特征
3. 训练 PPO Agent
4. Walk-Forward 验证
5. 保存训练好的模型

使用方式：
    python tools/train_ppo.py --symbol RB --days 200 --epochs 10
    python tools/train_ppo.py --symbol I,J,JM --days 200 --multi-asset

版本：v1.0
创建日期：2026-06-17
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.trend_scanner.storage.duckdb_store import DuckDBStore
from scripts.trend_scanner.rl import (
    AgentPPO,
    FuturesTradingEnv,
    MultiAssetVecEnv,
    RLTrainer,
    evaluate_agent,
    walk_forward_validate_rl,
)
from scripts.trend_scanner.rl.walk_forward_rl import RLWalkForwardValidator
from scripts.trend_scanner.trend_scanner_config import (
    TrendScannerConfig,
    RLConfig,
    WalkForwardConfig,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_data_from_duckdb(symbol: str, days: int = 200) -> pd.DataFrame | None:
    """
    从 DuckDB 加载期货数据
    
    Args:
        symbol: 品种代码（如 RB, I, J, JM）
        days: 加载天数
    
    Returns:
        DataFrame 或 None
    """
    db_path = "data/market.db"
    
    if not os.path.exists(db_path):
        logger.error(f"DuckDB 数据库不存在: {db_path}")
        logger.info("请先运行 python tools/sync_data.py sync --days 200 同步数据")
        return None
    
    store = DuckDBStore(db_path)
    df = store.get_klines(symbol, days=days, timeframe='daily')
    
    if df is None or df.empty:
        logger.warning(f"无法获取 {symbol} 的数据")
        return None
    
    logger.info(f"加载 {symbol} 数据: {len(df)} 条记录")
    logger.info(f"日期范围: {df['date'].min()} ~ {df['date'].max()}")
    
    return df


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算技术指标
    
    Args:
        df: K线数据
    
    Returns:
        包含技术指标的 DataFrame
    """
    df = df.copy()
    
    # 价格变化
    df['return'] = df['close'].pct_change()
    
    # 移动平均
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma10'] = df['close'].rolling(10).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 布林带
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * bb_std
    df['bb_lower'] = df['bb_middle'] - 2 * bb_std
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = np.maximum(high_low, np.maximum(high_close, low_close))
    df['atr'] = true_range.rolling(14).mean()
    
    # 成交量变化
    df['volume_change'] = df['volume'].pct_change()
    
    # 持仓量变化
    if 'open_interest' in df.columns:
        df['oi_change'] = df['open_interest'].pct_change()
    
    # 填充 NaN
    df = df.fillna(method='bfill').fillna(0)
    
    return df


def prepare_state_features(df: pd.DataFrame) -> np.ndarray:
    """
    准备状态特征
    
    Args:
        df: 包含技术指标的 DataFrame
    
    Returns:
        状态特征数组 (n_steps, n_features)
    """
    feature_columns = [
        'return', 'rsi', 'bb_width', 'volume_change',
    ]
    
    # 添加持仓量变化（如果存在）
    if 'oi_change' in df.columns:
        feature_columns.append('oi_change')
    
    # 提取特征
    features = df[feature_columns].values
    
    # 标准化
    mean = np.mean(features, axis=0)
    std = np.std(features, axis=0) + 1e-8
    features = (features - mean) / std
    
    return features


def prepare_price_data(df: pd.DataFrame) -> np.ndarray:
    """
    准备价格数据（用于 Gym 环境）
    
    Args:
        df: K线数据
    
    Returns:
        价格数组 (n_steps, 5) [open, high, low, close, volume]
    """
    price_columns = ['open', 'high', 'low', 'close', 'volume']
    return df[price_columns].values


def train_single_asset(symbol: str, 
                       days: int = 200,
                       train_steps: int = 10000,
                       save_dir: str = "models/rl") -> dict:
    """
    训练单个品种的 PPO 策略
    
    Args:
        symbol: 品种代码
        days: 数据天数
        train_steps: 训练步数
        save_dir: 模型保存目录
    
    Returns:
        训练结果
    """
    logger.info(f"开始训练 {symbol} 的 PPO 策略")
    
    # 加载数据
    df = load_data_from_duckdb(symbol, days)
    if df is None:
        return {'error': f'无法加载 {symbol} 数据'}
    
    # 计算技术指标
    df = calculate_technical_indicators(df)
    
    # 准备数据
    state_features = prepare_state_features(df)
    price_data = prepare_price_data(df)
    
    # 状态维度 = 技术指标数量 + 2（持仓 + 未实现盈亏）
    state_dim = state_features.shape[1] + 2
    
    # 创建环境
    env = FuturesTradingEnv(data=price_data, state_dim=state_features.shape[1])
    env.set_indicators(state_features)
    
    # 创建 Agent
    rl_config = RLConfig(
        net_dims=[128, 128],
        gamma=0.99,
        lambda_gae=0.95,
        learning_rate=2e-4,
        batch_size=64,
        horizon_len=256,
        repeat_times=4,
    )
    
    agent = AgentPPO(state_dim=state_dim, rl_config=rl_config)
    
    # 训练
    logger.info(f"开始训练: train_steps={train_steps}")
    
    total_steps = 0
    best_reward = -np.inf
    
    while total_steps < train_steps:
        # 收集经验
        experiences = agent.explore(env, horizon_len=rl_config.horizon_len)
        
        # 更新策略
        metrics = agent.reflect(experiences)
        
        total_steps += len(experiences)
        
        # 评估
        if total_steps % 1000 < rl_config.horizon_len:
            eval_results = evaluate_agent(agent, env, n_episodes=3)
            mean_reward = eval_results['mean_reward']
            
            logger.info(f"Step {total_steps}: reward={mean_reward:.4f}, loss_actor={metrics['loss_actor']:.4f}")
            
            if mean_reward > best_reward:
                best_reward = mean_reward
                # 保存最优模型
                os.makedirs(save_dir, exist_ok=True)
                agent.save(f"{save_dir}/{symbol}_best.pth")
    
    # 保存最终模型
    agent.save(f"{save_dir}/{symbol}_final.pth")
    
    # 评估最终性能
    final_results = evaluate_agent(agent, env, n_episodes=10)
    
    logger.info(f"训练完成 {symbol}:")
    logger.info(f"  最终平均奖励: {final_results['mean_reward']:.4f}")
    logger.info(f"  最终胜率: {final_results.get('win_rate', 0):.2%}")
    logger.info(f"  最大回撤: {final_results.get('max_drawdown', 0):.2%}")
    
    return {
        'symbol': symbol,
        'total_steps': total_steps,
        'best_reward': best_reward,
        'final_results': final_results,
        'model_path': f"{save_dir}/{symbol}_best.pth",
    }


def train_multi_asset(symbols: list[str],
                      days: int = 200,
                      train_steps: int = 10000,
                      save_dir: str = "models/rl") -> dict:
    """
    多品种并行训练
    
    Args:
        symbols: 品种代码列表
        days: 数据天数
        train_steps: 训练步数
        save_dir: 模型保存目录
    
    Returns:
        训练结果
    """
    logger.info(f"开始多品种并行训练: {symbols}")
    
    # 加载所有品种数据
    envs = []
    state_dims = []
    
    for symbol in symbols:
        df = load_data_from_duckdb(symbol, days)
        if df is None:
            logger.warning(f"跳过 {symbol}: 无法加载数据")
            continue
        
        # 计算技术指标
        df = calculate_technical_indicators(df)
        
        # 准备数据
        state_features = prepare_state_features(df)
        price_data = prepare_price_data(df)
        
        # 创建环境
        env = FuturesTradingEnv(data=price_data, state_dim=state_features.shape[1])
        env.set_indicators(state_features)
        
        envs.append(env)
        state_dims.append(state_features.shape[1] + 2)
    
    if not envs:
        return {'error': '没有有效的环境'}
    
    # 创建多品种环境
    vec_env = MultiAssetVecEnv(envs)
    
    # 使用统一的状态维度
    state_dim = max(state_dims)
    
    # 创建 Agent
    rl_config = RLConfig(
        net_dims=[256, 128],
        gamma=0.99,
        lambda_gae=0.95,
        learning_rate=1e-4,
        batch_size=128,
        horizon_len=512,
        repeat_times=4,
    )
    
    agent = AgentPPO(state_dim=state_dim, rl_config=rl_config)
    
    # 训练循环
    logger.info(f"开始多品种训练: train_steps={train_steps}")
    
    total_steps = 0
    
    while total_steps < train_steps:
        # 多品种并行收集经验
        all_experiences = []
        
        for i, env in enumerate(envs):
            experiences = agent.explore(env, horizon_len=rl_config.horizon_len // len(envs))
            all_experiences.extend(experiences)
        
        # 更新策略
        metrics = agent.reflect(all_experiences)
        
        total_steps += len(all_experiences)
        
        # 评估
        if total_steps % 2000 < rl_config.horizon_len:
            rewards = []
            for env in envs:
                results = evaluate_agent(agent, env, n_episodes=2)
                rewards.append(results['mean_reward'])
            
            avg_reward = np.mean(rewards)
            logger.info(f"Step {total_steps}: avg_reward={avg_reward:.4f}")
    
    # 保存模型
    os.makedirs(save_dir, exist_ok=True)
    agent.save(f"{save_dir}/multi_asset_best.pth")
    
    # 评估每个品种
    results = {}
    for symbol, env in zip(symbols[:len(envs)], envs):
        eval_results = evaluate_agent(agent, env, n_episodes=5)
        results[symbol] = eval_results
        logger.info(f"{symbol}: reward={eval_results['mean_reward']:.4f}")
    
    return {
        'symbols': symbols[:len(envs)],
        'total_steps': total_steps,
        'results': results,
        'model_path': f"{save_dir}/multi_asset_best.pth",
    }


def run_walk_forward_validation(symbol: str,
                                days: int = 200,
                                save_dir: str = "models/rl") -> dict:
    """
    运行 Walk-Forward 验证
    
    Args:
        symbol: 品种代码
        days: 数据天数
        save_dir: 模型保存目录
    
    Returns:
        验证结果
    """
    logger.info(f"开始 Walk-Forward 验证: {symbol}")
    
    # 加载数据
    df = load_data_from_duckdb(symbol, days)
    if df is None:
        return {'error': f'无法加载 {symbol} 数据'}
    
    # 计算技术指标
    df = calculate_technical_indicators(df)
    
    # 准备数据
    state_features = prepare_state_features(df)
    price_data = prepare_price_data(df)
    
    # 状态维度
    state_dim = state_features.shape[1] + 2
    
    # Walk-Forward 配置
    wf_config = WalkForwardConfig(
        optimization_window=30,
        test_window=7,
        step_size=7,
    )
    
    rl_config = RLConfig(
        net_dims=[64, 32],
        gamma=0.99,
        lambda_gae=0.95,
        learning_rate=2e-4,
    )
    
    # 运行验证
    validator = RLWalkForwardValidator(config=wf_config, rl_config=rl_config)
    
    result = validator.validate(
        data=price_data,
        state_dim=state_dim,
        train_steps_per_window=1000,
    )
    
    # 保存结果
    os.makedirs(save_dir, exist_ok=True)
    validator.save_result(result, f"{save_dir}/{symbol}_wf_result.json")
    
    # 打印结果
    logger.info(f"Walk-Forward 验证结果:")
    logger.info(f"  通过率: {result.pass_rate:.2%}")
    logger.info(f"  平均 OOS 奖励: {result.avg_oos_reward:.4f}")
    logger.info(f"  平均 Reward Ratio: {result.avg_reward_ratio:.2f}")
    logger.info(f"  建议:")
    for rec in result.recommendations:
        logger.info(f"    - {rec}")
    
    return {
        'symbol': symbol,
        'pass_rate': result.pass_rate,
        'avg_oos_reward': result.avg_oos_reward,
        'avg_reward_ratio': result.avg_reward_ratio,
        'recommendations': result.recommendations,
    }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PPO 策略训练脚本')
    
    parser.add_argument('--symbol', type=str, default='RB',
                        help='品种代码，多个用逗号分隔（如 I,J,JM）')
    parser.add_argument('--days', type=int, default=500,
                        help='数据天数')
    parser.add_argument('--train-steps', type=int, default=20000,
                        help='训练步数')
    parser.add_argument('--multi-asset', action='store_true',
                        help='多品种并行训练')
    parser.add_argument('--walk-forward', action='store_true',
                        help='运行 Walk-Forward 验证')
    parser.add_argument('--save-dir', type=str, default='models/rl',
                        help='模型保存目录')
    
    args = parser.parse_args()
    
    # 解析品种列表
    symbols = [s.strip() for s in args.symbol.split(',')]
    
    logger.info("=" * 60)
    logger.info("PPO 策略训练")
    logger.info("=" * 60)
    logger.info(f"品种: {symbols}")
    logger.info(f"数据天数: {args.days}")
    logger.info(f"训练步数: {args.train_steps}")
    logger.info(f"多品种并行: {args.multi_asset}")
    logger.info(f"Walk-Forward 验证: {args.walk_forward}")
    logger.info("=" * 60)
    
    results = {}
    
    if args.walk_forward:
        # Walk-Forward 验证
        for symbol in symbols:
            results[symbol] = run_walk_forward_validation(
                symbol=symbol,
                days=args.days,
                save_dir=args.save_dir,
            )
    elif args.multi_asset or len(symbols) > 1:
        # 多品种并行训练
        results = train_multi_asset(
            symbols=symbols,
            days=args.days,
            train_steps=args.train_steps,
            save_dir=args.save_dir,
        )
    else:
        # 单品种训练
        results[symbols[0]] = train_single_asset(
            symbol=symbols[0],
            days=args.days,
            train_steps=args.train_steps,
            save_dir=args.save_dir,
        )
    
    # 打印最终结果
    logger.info("=" * 60)
    logger.info("训练完成")
    logger.info("=" * 60)
    
    for symbol, result in results.items():
        if 'error' in result:
            logger.error(f"{symbol}: {result['error']}")
        else:
            logger.info(f"{symbol}: {result}")


if __name__ == '__main__':
    main()
