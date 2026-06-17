"""
RL 训练器

提供标准化的训练循环，借鉴 ElegantRL 的设计：
1. 单进程训练
2. 训练日志
3. 模型保存
4. 早停机制

版本：v1.0
创建日期：2026-06-17
"""

import logging
import time
import json
import numpy as np
from typing import Dict, Any, Optional, List
from pathlib import Path

from .base import AgentBase, Evaluator
from .agent_ppo import AgentPPO, AgentPPOShared
from ..trend_scanner_config import RLConfig, TrendScannerConfig

logger = logging.getLogger(__name__)


class TrainingLogger:
    """训练日志记录器"""
    
    def __init__(self, log_dir: str = "logs/rl"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.history = []
        self.start_time = time.time()
    
    def log(self, step: int, metrics: Dict[str, Any]):
        """记录训练指标"""
        metrics['step'] = step
        metrics['time'] = time.time() - self.start_time
        self.history.append(metrics)
        
        # 打印日志
        log_str = f"Step {step}: " + ", ".join(f"{k}={v:.4f}" for k, v in metrics.items() if isinstance(v, (int, float)))
        logger.info(log_str)
    
    def save(self, filename: str = "training_log.json"):
        """保存训练日志"""
        log_path = self.log_dir / filename
        with open(log_path, 'w') as f:
            json.dump(self.history, f, indent=2)
        logger.info(f"训练日志已保存到: {log_path}")


class RLTrainer:
    """
    RL 训练器
    
    借鉴 ElegantRL 的训练循环设计，提供：
    1. 标准化的训练流程
    2. 定期评估
    3. 模型保存
    4. 训练日志
    
    使用方式：
        config = TrendScannerConfig.from_json("config/config.json")
        trainer = RLTrainer(config)
        trainer.train(env, eval_env)
    """
    
    def __init__(self,
                 config: TrendScannerConfig,
                 agent: Optional[AgentBase] = None,
                 save_dir: str = "models/rl"):
        """
        初始化训练器
        
        Args:
            config: 统一配置
            agent: Agent 实例（可选，否则自动创建）
            save_dir: 模型保存目录
        """
        self.config = config
        self.rl_config = config.rl
        
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建 Agent
        if agent is None:
            self.agent = self._create_agent()
        else:
            self.agent = agent
        
        # 创建评估器
        self.evaluator = Evaluator(
            eval_times=self.rl_config.eval_times,
            eval_per_step=self.rl_config.eval_per_step,
            save_path=str(self.save_dir)
        )
        
        # 创建日志记录器
        self.logger = TrainingLogger()
        
        # 训练状态
        self.total_steps = 0
        self.best_reward = -np.inf
        
        logger.info(f"RLTrainer 初始化: algorithm={self.rl_config.algorithm}, save_dir={save_dir}")
    
    def _create_agent(self) -> AgentBase:
        """创建 Agent"""
        state_dim = self._get_state_dim()
        
        if self.rl_config.algorithm == "ppo":
            return AgentPPO(
                state_dim=state_dim,
                rl_config=self.rl_config
            )
        else:
            raise ValueError(f"不支持的算法: {self.rl_config.algorithm}")
    
    def _get_state_dim(self) -> int:
        """获取状态维度"""
        # 从配置中获取，或使用默认值
        return 10  # 需要根据实际情况调整
    
    def train(self,
              env: Any,
              eval_env: Optional[Any] = None,
              max_steps: int = 100000,
              log_interval: int = 1000,
              eval_interval: int = 5000,
              save_interval: int = 10000):
        """
        训练循环
        
        Args:
            env: 训练环境
            eval_env: 评估环境（可选）
            max_steps: 最大训练步数
            log_interval: 日志间隔
            eval_interval: 评估间隔
            save_interval: 保存间隔
        """
        logger.info(f"开始训练: max_steps={max_steps}")
        
        # 训练循环
        while self.total_steps < max_steps:
            # 收集经验
            experiences = self.agent.explore(env, self.rl_config.horizon_len)
            
            # 更新策略
            metrics = self.agent.reflect(experiences)
            
            self.total_steps += len(experiences)
            
            # 记录日志
            if self.total_steps % log_interval < self.rl_config.horizon_len:
                metrics['total_steps'] = self.total_steps
                self.logger.log(self.total_steps, metrics)
            
            # 评估
            if eval_env is not None and self.total_steps % eval_interval < self.rl_config.horizon_len:
                mean_reward, std_reward = self.evaluator.evaluate(self.agent, eval_env)
                
                if mean_reward > self.best_reward:
                    self.best_reward = mean_reward
                    self.save("best_model.pth")
                
                logger.info(f"评估: mean_reward={mean_reward:.4f}, std_reward={std_reward:.4f}")
            
            # 定期保存
            if self.total_steps % save_interval < self.rl_config.horizon_len:
                self.save(f"checkpoint_{self.total_steps}.pth")
        
        # 保存最终模型
        self.save("final_model.pth")
        
        # 保存训练日志
        self.logger.save()
        
        logger.info(f"训练完成: total_steps={self.total_steps}, best_reward={self.best_reward:.4f}")
    
    def save(self, filename: str):
        """保存模型"""
        save_path = self.save_dir / filename
        self.agent.save(str(save_path))
    
    def load(self, filename: str):
        """加载模型"""
        load_path = self.save_dir / filename
        self.agent.load(str(load_path))
    
    def get_training_summary(self) -> Dict[str, Any]:
        """获取训练摘要"""
        return {
            'total_steps': self.total_steps,
            'best_reward': self.best_reward,
            'algorithm': self.rl_config.algorithm,
            'net_dims': self.rl_config.net_dims,
            'gamma': self.rl_config.gamma,
            'learning_rate': self.rl_config.learning_rate,
        }


def train_ppo(config: TrendScannerConfig,
              env: Any,
              eval_env: Optional[Any] = None,
              max_steps: int = 100000,
              save_dir: str = "models/rl") -> Dict[str, Any]:
    """
    训练 PPO 策略的便捷函数
    
    Args:
        config: 统一配置
        env: 训练环境
        eval_env: 评估环境
        max_steps: 最大训练步数
        save_dir: 模型保存目录
    
    Returns:
        训练摘要
    """
    trainer = RLTrainer(config, save_dir=save_dir)
    trainer.train(env, eval_env, max_steps)
    return trainer.get_training_summary()


def evaluate_agent(agent: AgentBase,
                   env: Any,
                   n_episodes: int = 10) -> Dict[str, float]:
    """
    评估 Agent 的便捷函数
    
    Args:
        agent: Agent 实例
        env: 评估环境
        n_episodes: 评估 episode 数
    
    Returns:
        评估指标
    """
    rewards = []
    trade_counts = []
    
    for _ in range(n_episodes):
        state, _ = env.reset()
        episode_reward = 0
        done = False
        
        while not done:
            action = agent.reason(state)
            state, reward, terminated, truncated, _ = agent.execute_action(env, action)
            episode_reward += reward
            done = terminated or truncated
        
        rewards.append(episode_reward)
        trade_counts.append(len(env.trades))
    
    return {
        'mean_reward': np.mean(rewards),
        'std_reward': np.std(rewards),
        'min_reward': np.min(rewards),
        'max_reward': np.max(rewards),
        'mean_trades': np.mean(trade_counts),
    }
