"""
PPO Agent 实现

借鉴 ElegantRL 的 AgentPPO 设计，实现 PPO 算法：
1. GAE (Generalized Advantage Estimation)
2. Ratio Clipping
3. 熵正则化
4. 状态归一化

版本：v1.0
创建日期：2026-06-17
"""

import logging
import torch as th
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from copy import deepcopy

from .base import AgentBase, RLAction, RLExperience, ReplayBuffer
from .networks import ActorPPO, CriticPPO, ActorCriticPPO
from ..trend_scanner_config import RLConfig

logger = logging.getLogger(__name__)


class AgentPPO(AgentBase):
    """
    PPO Agent
    
    借鉴 ElegantRL 的 AgentPPO 设计，包含以下关键特性：
    1. GAE (λ=0.95): 平衡短期奖励与长期趋势
    2. Ratio Clipping (0.2): 防止策略突变
    3. 熵正则化 (0.001): 保持探索性
    4. 状态归一化: 处理期货价格量级差异
    
    适合 CTA 趋份跟踪的原因：
    - On-policy: 每次用最新策略收集数据，适应非平稳市场
    - 连续动作: 天然支持仓位大小输出
    - 稳定性: clipping 机制防止策略剧烈波动
    """
    
    def __init__(self,
                 state_dim: int,
                 action_dim: int = 1,
                 rl_config: Optional[RLConfig] = None,
                 gpu_id: int = -1,
                 **kwargs):
        """
        初始化 PPO Agent
        
        Args:
            state_dim: 状态维度
            action_dim: 动作维度
            rl_config: RL 配置
            gpu_id: GPU ID
        """
        super().__init__(state_dim=state_dim, action_dim=action_dim, gpu_id=gpu_id)
        
        # 配置
        if rl_config is None:
            rl_config = RLConfig()
        
        self.gamma = rl_config.gamma  # 折扣因子
        self.lambda_gae = rl_config.lambda_gae  # GAE 参数
        self.learning_rate = rl_config.learning_rate
        self.batch_size = rl_config.batch_size
        self.horizon_len = rl_config.horizon_len
        self.repeat_times = rl_config.repeat_times
        self.ratio_clip = rl_config.ratio_clip
        self.entropy_weight = rl_config.entropy_weight
        
        # 网络
        net_dims = rl_config.net_dims or [128, 128]
        
        self.act = ActorPPO(state_dim, action_dim, net_dims).to(self.device)
        self.cri = CriticPPO(state_dim, net_dims).to(self.device)
        
        # 优化器
        self.act_optimizer = th.optim.Adam(self.act.parameters(), lr=self.learning_rate)
        self.cri_optimizer = th.optim.Adam(self.cri.parameters(), lr=self.learning_rate)
        
        # 损失函数
        self.criterion = th.nn.SmoothL1Loss()
        
        logger.info(f"AgentPPO 初始化: state_dim={state_dim}, net_dims={net_dims}, gamma={self.gamma}")
    
    def perceive(self, env_state: Dict[str, Any]) -> np.ndarray:
        """
        感知环境状态
        
        Args:
            env_state: 包含 'observation' 的字典
        
        Returns:
            状态向量
        """
        return env_state["observation"]
    
    def reason(self, state: np.ndarray) -> RLAction:
        """
        推理选择动作
        
        Args:
            state: 状态向量
        
        Returns:
            动作
        """
        with th.no_grad():
            state_tensor = th.FloatTensor(state).unsqueeze(0).to(self.device)
            action, log_prob = self.act.get_action(state_tensor)
            
            # 计算价值
            value = self.cri(state_tensor).squeeze(-1)
        
        return RLAction(
            action=float(action.cpu().item()),
            log_prob=float(log_prob.cpu().item()),
            value=float(value.cpu().item())
        )
    
    def execute_action(self, env: Any, action: RLAction) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        在环境中执行动作
        
        Args:
            env: Gym 环境
            action: 动作
        
        Returns:
            (next_state, reward, done, info)
        """
        next_state, reward, terminated, truncated, info = env.step(action.action)
        return next_state, reward, terminated, truncated, info
    
    def reflect(self, experiences: List[RLExperience]) -> Dict[str, float]:
        """
        基于经验更新策略
        
        Args:
            experiences: 经验列表
        
        Returns:
            训练指标
        """
        if len(experiences) == 0:
            return {'loss_actor': 0.0, 'loss_critic': 0.0}
        
        # 转换为张量
        states = th.FloatTensor(np.array([e.state for e in experiences])).to(self.device)
        actions = th.FloatTensor(np.array([e.action for e in experiences])).to(self.device)
        rewards = th.FloatTensor(np.array([e.reward for e in experiences])).to(self.device)
        undones = th.FloatTensor(np.array([1 - e.done for e in experiences])).to(self.device)
        old_log_probs = th.FloatTensor(np.array([e.log_prob for e in experiences])).to(self.device)
        old_values = th.FloatTensor(np.array([e.value for e in experiences])).to(self.device)
        
        # 计算 GAE
        advantages = self._compute_gae(rewards, undones, old_values)
        returns = advantages + old_values
        
        # 归一化优势
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO 更新
        total_loss_actor = 0.0
        total_loss_critic = 0.0
        
        for _ in range(self.repeat_times):
            # 随机打乱
            indices = th.randperm(len(experiences))
            
            for start in range(0, len(experiences), self.batch_size):
                end = min(start + self.batch_size, len(experiences))
                batch_indices = indices[start:end]
                
                batch_states = states[batch_indices]
                batch_actions = actions[batch_indices]
                batch_advantages = advantages[batch_indices]
                batch_returns = returns[batch_indices]
                batch_old_log_probs = old_log_probs[batch_indices]
                
                # 计算新的 log 概率
                new_log_probs = self.act.get_action_logprob(batch_states, batch_actions)
                
                # 计算 ratio
                ratio = (new_log_probs - batch_old_log_probs).exp()
                
                # Clipped surrogate loss
                surrogate1 = ratio * batch_advantages
                surrogate2 = th.clamp(ratio, 1 - self.ratio_clip, 1 + self.ratio_clip) * batch_advantages
                loss_actor = -th.min(surrogate1, surrogate2).mean()
                
                # 熵正则化
                entropy = -new_log_probs.mean()
                loss_actor += self.entropy_weight * entropy
                
                # 更新 Actor
                self.act_optimizer.zero_grad()
                loss_actor.backward()
                th.nn.utils.clip_grad_norm_(self.act.parameters(), 0.5)
                self.act_optimizer.step()
                
                # Critic 损失
                values = self.cri(batch_states).squeeze(-1)
                loss_critic = self.criterion(values, batch_returns)
                
                # 更新 Critic
                self.cri_optimizer.zero_grad()
                loss_critic.backward()
                th.nn.utils.clip_grad_norm_(self.cri.parameters(), 0.5)
                self.cri_optimizer.step()
                
                total_loss_actor += loss_actor.item()
                total_loss_critic += loss_critic.item()
        
        n_updates = self.repeat_times * max(1, len(experiences) // self.batch_size)
        
        return {
            'loss_actor': total_loss_actor / n_updates,
            'loss_critic': total_loss_critic / n_updates,
        }
    
    def _compute_gae(self, 
                     rewards: th.Tensor, 
                     undones: th.Tensor,
                     values: th.Tensor) -> th.Tensor:
        """
        计算 GAE (Generalized Advantage Estimation)
        
        GAE 公式：
        A_t = Σ_{l=0}^{∞} (γλ)^l δ_{t+l}
        其中 δ_t = r_t + γV(s_{t+1}) - V(s_t)
        
        Args:
            rewards: 奖励序列 (T,)
            undones: 未完成标志 (T,)
            values: 价值序列 (T,)
        
        Returns:
            优势函数 (T,)
        """
        T = len(rewards)
        advantages = th.zeros_like(rewards)
        
        # 从后向前计算
        next_value = 0
        next_advantage = 0
        
        for t in reversed(range(T)):
            if t == T - 1:
                next_value = 0
            else:
                next_value = values[t + 1]
            
            # TD 误差
            delta = rewards[t] + self.gamma * next_value * undones[t] - values[t]
            
            # GAE
            advantages[t] = delta + self.gamma * self.lambda_gae * undones[t] * next_advantage
            next_advantage = advantages[t]
        
        return advantages
    
    def explore(self, env: Any, horizon_len: int = None) -> List[RLExperience]:
        """
        收集经验数据
        
        Args:
            env: Gym 环境
            horizon_len: 收集步数
        
        Returns:
            经验列表
        """
        if horizon_len is None:
            horizon_len = self.horizon_len
        
        return super().explore(env, horizon_len)
    
    def save(self, path: str):
        """保存模型"""
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        th.save({
            'act_state_dict': self.act.state_dict(),
            'cri_state_dict': self.cri.state_dict(),
            'act_optimizer': self.act_optimizer.state_dict(),
            'cri_optimizer': self.cri_optimizer.state_dict(),
        }, path)
        logger.info(f"PPO 模型已保存到: {path}")
    
    def load(self, path: str):
        """加载模型"""
        checkpoint = th.load(path, map_location=self.device)
        
        self.act.load_state_dict(checkpoint['act_state_dict'])
        self.cri.load_state_dict(checkpoint['cri_state_dict'])
        self.act_optimizer.load_state_dict(checkpoint['act_optimizer'])
        self.cri_optimizer.load_state_dict(checkpoint['cri_optimizer'])
        
        logger.info(f"PPO 模型已从 {path} 加载")


class AgentPPOShared(AgentPPO):
    """
    PPO Agent（共享特征提取）
    
    Actor 和 Critic 共享底层特征提取网络
    """
    
    def __init__(self,
                 state_dim: int,
                 action_dim: int = 1,
                 rl_config: Optional[RLConfig] = None,
                 gpu_id: int = -1,
                 **kwargs):
        """
        初始化共享 PPO Agent
        """
        # 不调用 super().__init__，因为我们要使用不同的网络
        AgentBase.__init__(self, state_dim=state_dim, action_dim=action_dim, gpu_id=gpu_id)
        
        # 配置
        if rl_config is None:
            rl_config = RLConfig()
        
        self.gamma = rl_config.gamma
        self.lambda_gae = rl_config.lambda_gae
        self.learning_rate = rl_config.learning_rate
        self.batch_size = rl_config.batch_size
        self.horizon_len = rl_config.horizon_len
        self.repeat_times = rl_config.repeat_times
        self.ratio_clip = rl_config.ratio_clip
        self.entropy_weight = rl_config.entropy_weight
        
        # 共享网络
        net_dims = rl_config.net_dims or [128, 128]
        self.ac = ActorCriticPPO(state_dim, action_dim, net_dims).to(self.device)
        
        # 优化器
        self.optimizer = th.optim.Adam(self.ac.parameters(), lr=self.learning_rate)
        
        # 损失函数
        self.criterion = th.nn.SmoothL1Loss()
        
        logger.info(f"AgentPPOShared 初始化: state_dim={state_dim}, net_dims={net_dims}")
    
    def reason(self, state: np.ndarray) -> RLAction:
        """
        推理选择动作
        """
        with th.no_grad():
            state_tensor = th.FloatTensor(state).unsqueeze(0).to(self.device)
            action, log_prob, value = self.ac.get_action(state_tensor)
        
        return RLAction(
            action=float(action.cpu().item()),
            log_prob=float(log_prob.cpu().item()),
            value=float(value.cpu().item())
        )
    
    def reflect(self, experiences: List[RLExperience]) -> Dict[str, float]:
        """
        基于经验更新策略
        """
        if len(experiences) == 0:
            return {'loss_actor': 0.0, 'loss_critic': 0.0}
        
        # 转换为张量
        states = th.FloatTensor(np.array([e.state for e in experiences])).to(self.device)
        actions = th.FloatTensor(np.array([e.action for e in experiences])).to(self.device)
        rewards = th.FloatTensor(np.array([e.reward for e in experiences])).to(self.device)
        undones = th.FloatTensor(np.array([1 - e.done for e in experiences])).to(self.device)
        old_log_probs = th.FloatTensor(np.array([e.log_prob for e in experiences])).to(self.device)
        old_values = th.FloatTensor(np.array([e.value for e in experiences])).to(self.device)
        
        # 计算 GAE
        advantages = self._compute_gae(rewards, undones, old_values)
        returns = advantages + old_values
        
        # 归一化优势
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO 更新
        total_loss_actor = 0.0
        total_loss_critic = 0.0
        
        for _ in range(self.repeat_times):
            # 随机打乱
            indices = th.randperm(len(experiences))
            
            for start in range(0, len(experiences), self.batch_size):
                end = min(start + self.batch_size, len(experiences))
                batch_indices = indices[start:end]
                
                batch_states = states[batch_indices]
                batch_actions = actions[batch_indices]
                batch_advantages = advantages[batch_indices]
                batch_returns = returns[batch_indices]
                batch_old_log_probs = old_log_probs[batch_indices]
                
                # 前向传播
                _, new_log_probs, values = self.ac.get_action(batch_states)
                
                # 计算 ratio
                ratio = (new_log_probs - batch_old_log_probs).exp()
                
                # Clipped surrogate loss
                surrogate1 = ratio * batch_advantages
                surrogate2 = th.clamp(ratio, 1 - self.ratio_clip, 1 + self.ratio_clip) * batch_advantages
                loss_actor = -th.min(surrogate1, surrogate2).mean()
                
                # 熵正则化
                entropy = -new_log_probs.mean()
                loss_actor += self.entropy_weight * entropy
                
                # Critic 损失
                loss_critic = self.criterion(values, batch_returns)
                
                # 总损失
                loss = loss_actor + 0.5 * loss_critic
                
                # 更新
                self.optimizer.zero_grad()
                loss.backward()
                th.nn.utils.clip_grad_norm_(self.ac.parameters(), 0.5)
                self.optimizer.step()
                
                total_loss_actor += loss_actor.item()
                total_loss_critic += loss_critic.item()
        
        n_updates = self.repeat_times * max(1, len(experiences) // self.batch_size)
        
        return {
            'loss_actor': total_loss_actor / n_updates,
            'loss_critic': total_loss_critic / n_updates,
        }
    
    def save(self, path: str):
        """保存模型"""
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        th.save({
            'ac_state_dict': self.ac.state_dict(),
            'optimizer': self.optimizer.state_dict(),
        }, path)
        logger.info(f"PPO Shared 模型已保存到: {path}")
    
    def load(self, path: str):
        """加载模型"""
        checkpoint = th.load(path, map_location=self.device)
        
        self.ac.load_state_dict(checkpoint['ac_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        
        logger.info(f"PPO Shared 模型已从 {path} 加载")
