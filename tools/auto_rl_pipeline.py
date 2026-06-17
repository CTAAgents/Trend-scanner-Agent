"""
RL 自动化流程脚本

实现从扫描到训练到信号生成的完整自动化流程：
1. 数据同步
2. 技术指标计算
3. RL 训练
4. Walk-Forward 验证
5. 模型保存
6. 信号生成
7. Scanner 集成

使用方式：
    python tools/auto_rl_pipeline.py --symbol RB --full
    python tools/auto_rl_pipeline.py --symbol RB --train-only
    python tools/auto_rl_pipeline.py --symbol RB --validate-only

版本：v1.0
创建日期：2026-06-17
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from trend_scanner.storage.duckdb_store import DuckDBStore
from trend_scanner.rl import (
    AgentPPO,
    FuturesTradingEnv,
    RLSignalGenerator,
    evaluate_agent,
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


class RLPipeline:
    """
    RL 自动化流程
    
    完整的 RL 策略开发流程：
    1. 数据加载和预处理
    2. RL Agent 训练
    3. Walk-Forward 验证
    4. 模型保存和评估
    5. 信号生成器创建
    """
    
    def __init__(self, 
                 symbol: str,
                 days: int = 200,
                 save_dir: str = "models/rl"):
        """
        初始化流程
        
        Args:
            symbol: 品种代码
            days: 数据天数
            save_dir: 模型保存目录
        """
        self.symbol = symbol
        self.days = days
        self.save_dir = save_dir
        
        # 创建保存目录
        os.makedirs(save_dir, exist_ok=True)
        
        # 数据
        self.price_data = None
        self.state_features = None
        self.state_dim = None
        
        # 模型
        self.agent = None
        self.signal_generator = None
        
        logger.info(f"RL 流程初始化: symbol={symbol}, days={days}")
    
    def load_data(self) -> bool:
        """
        加载数据
        
        Returns:
            是否成功
        """
        logger.info(f"加载 {self.symbol} 数据...")
        
        db_path = "data/market.db"
        if not os.path.exists(db_path):
            logger.error(f"DuckDB 数据库不存在: {db_path}")
            return False
        
        store = DuckDBStore(db_path)
        df = store.get_klines(self.symbol, days=self.days, timeframe='daily')
        
        if df is None or df.empty:
            logger.error(f"无法获取 {self.symbol} 的数据")
            return False
        
        logger.info(f"加载 {len(df)} 条记录")
        
        # 计算技术指标
        df = self._calculate_indicators(df)
        
        # 准备数据
        self.state_features = self._prepare_state_features(df)
        self.price_data = self._prepare_price_data(df)
        
        # 状态维度 = 技术指标数量 + 2（持仓 + 未实现盈亏）
        self.state_dim = self.state_features.shape[1] + 2
        
        logger.info(f"数据准备完成: state_dim={self.state_dim}")
        
        return True
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = df.copy()
        
        # 价格变化
        df['return'] = df['close'].pct_change()
        
        # RSI (14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR (14) - Average True Range
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        df['atr'] = true_range.rolling(14).mean()
        df['atr_pct'] = df['atr'] / df['close']  # ATR 占价格的百分比
        
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # 布林带
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * bb_std
        df['bb_lower'] = df['bb_middle'] - 2 * bb_std
        df['bb_width'] = (4 * bb_std) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 成交量变化
        df['volume_change'] = df['volume'].pct_change()
        df['volume_ma_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        
        # 价格动量
        df['momentum_5'] = df['close'].pct_change(5)
        df['momentum_10'] = df['close'].pct_change(10)
        
        # 填充 NaN
        df = df.ffill().fillna(0)
        
        return df
    
    def _prepare_state_features(self, df: pd.DataFrame) -> np.ndarray:
        """准备状态特征"""
        feature_columns = [
            'return', 'rsi', 'atr_pct', 
            'macd_hist', 'bb_position', 'bb_width',
            'volume_change', 'volume_ma_ratio',
            'momentum_5', 'momentum_10'
        ]
        features = df[feature_columns].values
        
        # 标准化
        mean = np.mean(features, axis=0)
        std = np.std(features, axis=0) + 1e-8
        features = (features - mean) / std
        
        return features
    
    def _prepare_price_data(self, df: pd.DataFrame) -> np.ndarray:
        """准备价格数据"""
        price_columns = ['open', 'high', 'low', 'close', 'volume']
        return df[price_columns].values
    
    def train(self, 
              train_steps: int = 10000,
              rl_config: RLConfig = None) -> dict:
        """
        训练 RL Agent
        
        Args:
            train_steps: 训练步数
            rl_config: RL 配置
        
        Returns:
            训练结果
        """
        if self.price_data is None:
            raise ValueError("请先调用 load_data()")
        
        logger.info(f"开始训练: train_steps={train_steps}")
        
        # 创建环境
        env = FuturesTradingEnv(data=self.price_data, state_dim=self.state_features.shape[1])
        env.set_indicators(self.state_features)
        
        # 创建 Agent
        if rl_config is None:
            rl_config = RLConfig(
                net_dims=[128, 128],
                gamma=0.99,
                lambda_gae=0.95,
                learning_rate=2e-4,
                batch_size=64,
                horizon_len=256,
                repeat_times=4,
            )
        
        self.agent = AgentPPO(state_dim=self.state_dim, rl_config=rl_config)
        
        # 训练循环
        total_steps = 0
        best_reward = -np.inf
        
        while total_steps < train_steps:
            # 收集经验
            experiences = self.agent.explore(env, horizon_len=rl_config.horizon_len)
            
            # 更新策略
            metrics = self.agent.reflect(experiences)
            
            total_steps += len(experiences)
            
            # 评估
            if total_steps % 1000 < rl_config.horizon_len:
                eval_results = evaluate_agent(self.agent, env, n_episodes=3)
                mean_reward = eval_results['mean_reward']
                
                logger.info(f"Step {total_steps}: reward={mean_reward:.4f}")
                
                if mean_reward > best_reward:
                    best_reward = mean_reward
                    # 保存最优模型
                    self.agent.save(f"{self.save_dir}/{self.symbol}_best.pth")
        
        # 保存最终模型
        self.agent.save(f"{self.save_dir}/{self.symbol}_final.pth")
        
        # 评估最终性能
        final_results = evaluate_agent(self.agent, env, n_episodes=10)
        
        logger.info(f"训练完成: final_reward={final_results['mean_reward']:.4f}")
        
        return {
            'total_steps': total_steps,
            'best_reward': best_reward,
            'final_results': final_results,
        }
    
    def validate(self, rl_config: RLConfig = None) -> dict:
        """
        Walk-Forward 验证
        
        Args:
            rl_config: RL 配置
        
        Returns:
            验证结果
        """
        if self.price_data is None:
            raise ValueError("请先调用 load_data()")
        
        logger.info("开始 Walk-Forward 验证...")
        
        # 配置
        wf_config = WalkForwardConfig(
            optimization_window=30,
            test_window=7,
            step_size=7,
        )
        
        if rl_config is None:
            rl_config = RLConfig(
                net_dims=[64, 32],
                gamma=0.99,
                lambda_gae=0.95,
                learning_rate=2e-4,
            )
        
        # 运行验证
        validator = RLWalkForwardValidator(config=wf_config, rl_config=rl_config)
        
        result = validator.validate(
            data=self.price_data,
            state_dim=self.state_dim,
            train_steps_per_window=1000,
        )
        
        # 保存结果
        validator.save_result(result, f"{self.save_dir}/{self.symbol}_wf_result.json")
        
        logger.info(f"Walk-Forward 验证完成: pass_rate={result.pass_rate:.2%}")
        
        return {
            'pass_rate': result.pass_rate,
            'avg_oos_reward': result.avg_oos_reward,
            'avg_reward_ratio': result.avg_reward_ratio,
            'recommendations': result.recommendations,
        }
    
    def create_signal_generator(self) -> RLSignalGenerator:
        """
        创建信号生成器
        
        Returns:
            RLSignalGenerator 实例
        """
        if self.agent is None:
            # 尝试加载模型
            model_path = f"{self.save_dir}/{self.symbol}_best.pth"
            if os.path.exists(model_path):
                self.agent = AgentPPO(state_dim=self.state_dim)
                self.agent.load(model_path)
            else:
                raise ValueError("未找到训练好的模型，请先调用 train()")
        
        # 创建信号生成器
        self.signal_generator = RLSignalGenerator.__new__(RLSignalGenerator)
        self.signal_generator.state_dim = self.state_dim
        self.signal_generator.agent = self.agent
        
        logger.info("信号生成器创建完成")
        
        return self.signal_generator
    
    def run_full_pipeline(self, train_steps: int = 10000) -> dict:
        """
        运行完整流程
        
        Args:
            train_steps: 训练步数
        
        Returns:
            完整结果
        """
        results = {
            'symbol': self.symbol,
            'start_time': datetime.now().isoformat(),
        }
        
        # 1. 加载数据
        if not self.load_data():
            results['error'] = '数据加载失败'
            return results
        
        # 2. 训练
        train_result = self.train(train_steps=train_steps)
        results['train'] = train_result
        
        # 3. 验证
        validate_result = self.validate()
        results['validate'] = validate_result
        
        # 4. 创建信号生成器
        try:
            generator = self.create_signal_generator()
            results['signal_generator'] = 'created'
        except Exception as e:
            results['signal_generator'] = f'failed: {e}'
        
        results['end_time'] = datetime.now().isoformat()
        
        # 保存结果
        result_file = f"{self.save_dir}/{self.symbol}_pipeline_result.json"
        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"完整流程结果已保存到: {result_file}")
        
        return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='RL 自动化流程脚本')
    
    parser.add_argument('--symbol', type=str, default='RB',
                        help='品种代码')
    parser.add_argument('--days', type=int, default=500,
                        help='数据天数')
    parser.add_argument('--train-steps', type=int, default=20000,
                        help='训练步数')
    parser.add_argument('--full', action='store_true',
                        help='运行完整流程')
    parser.add_argument('--train-only', action='store_true',
                        help='仅训练')
    parser.add_argument('--validate-only', action='store_true',
                        help='仅验证')
    parser.add_argument('--save-dir', type=str, default='models/rl',
                        help='模型保存目录')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("RL 自动化流程")
    logger.info("=" * 60)
    logger.info(f"品种: {args.symbol}")
    logger.info(f"数据天数: {args.days}")
    logger.info(f"训练步数: {args.train_steps}")
    logger.info("=" * 60)
    
    # 创建流程
    pipeline = RLPipeline(
        symbol=args.symbol,
        days=args.days,
        save_dir=args.save_dir,
    )
    
    # 加载数据
    if not pipeline.load_data():
        logger.error("数据加载失败，退出")
        return
    
    # 执行流程
    if args.full:
        # 完整流程
        results = pipeline.run_full_pipeline(train_steps=args.train_steps)
        logger.info("完整流程执行完成")
    elif args.train_only:
        # 仅训练
        train_result = pipeline.train(train_steps=args.train_steps)
        logger.info("训练完成")
    elif args.validate_only:
        # 仅验证
        validate_result = pipeline.validate()
        logger.info("验证完成")
    else:
        # 默认运行完整流程
        results = pipeline.run_full_pipeline(train_steps=args.train_steps)
        logger.info("完整流程执行完成")


if __name__ == '__main__':
    main()
