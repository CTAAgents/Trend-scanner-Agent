"""
RL 基础模块

提供 AgentBase 基类和 ReplayBuffer，借鉴 ElegantRL 的设计模式。

设计原则：
1. AgentBase 定义统一的 Agent 生命周期（perceive → reason → act → reflect）
2. ReplayBuffer 支持向量化环境和优先经验回放
3. 所有 RL 算法继承 AgentBase，只需实现抽象方法

版本：v1.0
创建日期：2026-06-17
"""

import logging
import torch as th
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RLState:
    """RL 状态"""
    observation: np.ndarray
    position: float
    step: int
    done: bool
    info: Dict[str, Any]


@dataclass
class RLAction:
    """RL 动作"""
    action: float  # [-1, 1] 表示仓位方向和大小
    log_prob: Optional[float] = None
    value: Optional[float] = None


@dataclass
class RLExperience:
    """RL 经验"""
    state: np.ndarray
    action: float
    reward: float
    next_state: np.ndarray
    done: bool
    log_prob: float
    value: float


class AgentBase(ABC):
    """
    Agent 基类
    
    借鉴 ElegantRL 的 AgentBase 设计，定义统一的 Agent 生命周期：
    - perceive: 感知环境状态
    - reason: 基于状态做出决策
    - act: 执行动作
    - reflect: 评估结果，更新策略
    
    使用方式：
        class MyAgent(AgentBase):
            def perceive(self, env_state):
                # 处理环境状态
                return processed_state
            
            def reason(self, state):
                # 选择动作
                return action
            
            def act(self, env, action):
                # 执行动作
                return next_state, reward, done
            
            def reflect(self, experience):
                # 更新策略
                pass
    """
    
    def __init__(self, 
                 state_dim: int,
                 action_dim: int = 1,
                 gpu_id: int = -1,
                 **kwargs):
        """
        初始化 Agent
        
        Args:
            state_dim: 状态维度
            action_dim: 动作维度（期货交易为 1：仓位大小）
            gpu_id: GPU ID，-1 表示使用 CPU
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # 设备选择
        if gpu_id >= 0 and th.cuda.is_available():
            self.device = th.device(f"cuda:{gpu_id}")
        else:
            self.device = th.device("cpu")
        
        logger.info(f"Agent 初始化: state_dim={state_dim}, action_dim={action_dim}, device={self.device}")
    
    @abstractmethod
    def perceive(self, env_state: Dict[str, Any]) -> np.ndarray:
        """
        感知：从环境中获取信息并处理为状态向量
        
        Args:
            env_state: 环境原始状态
        
        Returns:
            处理后的状态向量
        """
        pass
    
    @abstractmethod
    def reason(self, state: np.ndarray) -> RLAction:
        """
        推理：基于状态选择动作
        
        Args:
            state: 状态向量
        
        Returns:
            动作
        """
        pass
    
    @abstractmethod
    def execute_action(self, env: Any, action: RLAction) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        执行动作：在环境中执行动作
        
        Args:
            env: Gym 环境
            action: 动作
        
        Returns:
            (next_state, reward, done, info)
        """
        pass
    
    @abstractmethod
    def reflect(self, experiences: List[RLExperience]) -> Dict[str, float]:
        """
        反思：基于经验更新策略
        
        Args:
            experiences: 经验列表
        
        Returns:
            训练指标（loss 等）
        """
        pass
    
    def explore(self, env: Any, horizon_len: int) -> List[RLExperience]:
        """
        探索：收集经验数据
        
        Args:
            env: Gym 环境
            horizon_len: 收集步数
        
        Returns:
            经验列表
        """
        experiences = []
        
        state, _ = env.reset()
        
        for _ in range(horizon_len):
            # 感知
            processed_state = self.perceive({"observation": state})
            
            # 推理
            action = self.reason(processed_state)
            
            # 执行动作
            next_state, reward, terminated, truncated, info = self.execute_action(env, action)
            done = terminated or truncated
            
            # 记录经验
            experience = RLExperience(
                state=processed_state,
                action=action.action,
                reward=reward,
                next_state=self.perceive({"observation": next_state}),
                done=done,
                log_prob=action.log_prob or 0.0,
                value=action.value or 0.0
            )
            experiences.append(experience)
            
            if done:
                state, _ = env.reset()
            else:
                state = next_state
        
        return experiences
    
    def save(self, path: str):
        """保存模型"""
        raise NotImplementedError("子类需要实现 save 方法")
    
    def load(self, path: str):
        """加载模型"""
        raise NotImplementedError("子类需要实现 load 方法")


class ReplayBuffer:
    """
    经验回放缓冲区
    
    借鉴 ElegantRL 的 ReplayBuffer 设计：
    1. 支持向量化环境的多序列存储
    2. 支持优先经验回放（PER）
    3. 高效的 GPU 张量存储
    
    使用方式：
        buffer = ReplayBuffer(max_size=100000, state_dim=10)
        buffer.update(states, actions, rewards, undones)
        batch = buffer.sample(batch_size=256)
    """
    
    def __init__(self,
                 max_size: int,
                 state_dim: int,
                 action_dim: int = 1,
                 gpu_id: int = -1,
                 num_seqs: int = 1,
                 if_use_per: bool = False):
        """
        初始化 ReplayBuffer
        
        Args:
            max_size: 最大容量
            state_dim: 状态维度
            action_dim: 动作维度
            gpu_id: GPU ID，-1 表示使用 CPU
            num_seqs: 序列数量（向量化环境数）
            if_use_per: 是否使用优先经验回放
        """
        self.max_size = max_size
        self.num_seqs = num_seqs
        self.if_use_per = if_use_per
        
        # 设备选择
        if gpu_id >= 0 and th.cuda.is_available():
            self.device = th.device(f"cuda:{gpu_id}")
        else:
            self.device = th.device("cpu")
        
        # 存储张量
        self.states = th.empty((max_size, num_seqs, state_dim), dtype=th.float32, device=self.device)
        self.actions = th.empty((max_size, num_seqs, action_dim), dtype=th.float32, device=self.device)
        self.rewards = th.empty((max_size, num_seqs), dtype=th.float32, device=self.device)
        self.undones = th.empty((max_size, num_seqs), dtype=th.float32, device=self.device)
        
        # 指针和大小
        self.p = 0  # 写指针
        self.cur_size = 0
        self.if_full = False
        
        # 采样索引
        self.ids0 = None
        self.ids1 = None
        
        logger.info(f"ReplayBuffer 初始化: max_size={max_size}, state_dim={state_dim}, device={self.device}")
    
    def update(self, 
               states: th.Tensor,
               actions: th.Tensor,
               rewards: th.Tensor,
               undones: th.Tensor):
        """
        更新缓冲区
        
        Args:
            states: 状态张量 (add_size, num_seqs, state_dim)
            actions: 动作张量 (add_size, num_seqs, action_dim)
            rewards: 奖励张量 (add_size, num_seqs)
            undones: 未完成标志 (add_size, num_seqs)
        """
        add_size = rewards.shape[0]
        
        p = self.p + add_size
        
        if p > self.max_size:
            self.if_full = True
            p0 = self.p
            p1 = self.max_size
            p2 = self.max_size - self.p
            p = p - self.max_size
            
            self.states[p0:p1], self.states[0:p] = states[:p2], states[-p:]
            self.actions[p0:p1], self.actions[0:p] = actions[:p2], actions[-p:]
            self.rewards[p0:p1], self.rewards[0:p] = rewards[:p2], rewards[-p:]
            self.undones[p0:p1], self.undones[0:p] = undones[:p2], undones[-p:]
        else:
            self.states[self.p:p] = states
            self.actions[self.p:p] = actions
            self.rewards[self.p:p] = rewards
            self.undones[self.p:p] = undones
        
        self.p = p
        self.cur_size = self.max_size if self.if_full else self.p
    
    def sample(self, batch_size: int) -> Tuple[th.Tensor, ...]:
        """
        采样批次数据
        
        Args:
            batch_size: 批次大小
        
        Returns:
            (states, actions, rewards, undones, next_states)
        """
        sample_len = self.cur_size - 1
        
        ids = th.randint(sample_len * self.num_seqs, size=(batch_size,), device=self.device)
        self.ids0 = ids0 = th.fmod(ids, sample_len)
        self.ids1 = ids1 = th.div(ids, sample_len, rounding_mode='floor')
        
        return (
            self.states[ids0, ids1],
            self.actions[ids0, ids1],
            self.rewards[ids0, ids1],
            self.undones[ids0, ids1],
            self.states[ids0 + 1, ids1],  # next_state
        )
    
    def save(self, path: str):
        """保存缓冲区"""
        th.save({
            'states': self.states[:self.cur_size],
            'actions': self.actions[:self.cur_size],
            'rewards': self.rewards[:self.cur_size],
            'undones': self.undones[:self.cur_size],
            'p': self.p,
            'cur_size': self.cur_size,
            'if_full': self.if_full,
        }, path)
        logger.info(f"ReplayBuffer 已保存到: {path}")
    
    def load(self, path: str):
        """加载缓冲区"""
        data = th.load(path, map_location=self.device)
        
        size = data['cur_size']
        self.states[:size] = data['states']
        self.actions[:size] = data['actions']
        self.rewards[:size] = data['rewards']
        self.undones[:size] = data['undones']
        self.p = data['p']
        self.cur_size = data['cur_size']
        self.if_full = data['if_full']
        
        logger.info(f"ReplayBuffer 已从 {path} 加载，大小: {self.cur_size}")


class Evaluator:
    """
    评估器
    
    借鉴 ElegantRL 的 Evaluator 设计：
    1. 定期评估 Agent 性能
    2. 保存最优模型
    3. 生成学习曲线
    """
    
    def __init__(self,
                 eval_times: int = 8,
                 eval_per_step: int = 1000,
                 save_path: str = "models"):
        """
        初始化评估器
        
        Args:
            eval_times: 每次评估的 episode 数
            eval_per_step: 评估间隔步数
            save_path: 模型保存路径
        """
        self.eval_times = eval_times
        self.eval_per_step = eval_per_step
        self.save_path = save_path
        
        self.best_reward = -np.inf
        self.eval_results = []
    
    def evaluate(self, agent: AgentBase, env: Any) -> Tuple[float, float]:
        """
        评估 Agent
        
        Args:
            agent: Agent 实例
            env: Gym 环境
        
        Returns:
            (平均奖励, 标准差)
        """
        rewards = []
        
        for _ in range(self.eval_times):
            state, _ = env.reset()
            episode_reward = 0
            done = False
            
            while not done:
                processed_state = agent.perceive({"observation": state})
                action = agent.reason(processed_state)
                state, reward, terminated, truncated, _ = agent.act(env, action)
                done = terminated or truncated
                episode_reward += reward
            
            rewards.append(episode_reward)
        
        mean_reward = np.mean(rewards)
        std_reward = np.std(rewards)
        
        # 保存最优模型
        if mean_reward > self.best_reward:
            self.best_reward = mean_reward
            agent.save(f"{self.save_path}/best_model.pth")
            logger.info(f"新的最优模型，奖励: {mean_reward:.4f}")
        
        self.eval_results.append({
            'mean_reward': mean_reward,
            'std_reward': std_reward,
            'best_reward': self.best_reward,
        })
        
        return mean_reward, std_reward
    
    def should_stop(self, step: int) -> bool:
        """判断是否应该停止训练"""
        # 可以添加早停逻辑
        return False
