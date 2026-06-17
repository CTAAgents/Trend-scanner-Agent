"""
RL 网络模块

提供 Actor-Critic 网络架构，借鉴 ElegantRL 的设计：
1. 状态归一化层（内置）
2. 正交初始化
3. DenseNet 可选

版本：v1.0
创建日期：2026-06-17
"""

import torch as th
import torch.nn as nn
import numpy as np
from typing import List, Tuple, Optional


def build_mlp(dims: List[int], 
              if_raw_out: bool = True,
              activation: nn.Module = None) -> nn.Sequential:
    """
    构建 MLP 网络
    
    Args:
        dims: 各层维度 [input_dim, hidden1, hidden2, ..., output_dim]
        if_raw_out: 输出层是否使用激活函数（True=不使用，False=使用）
        activation: 激活函数，默认 ReLU
    
    Returns:
        nn.Sequential 模型
    """
    if activation is None:
        activation = nn.ReLU
    
    layers = []
    for i in range(len(dims) - 1):
        layers.append(nn.Linear(dims[i], dims[i + 1]))
        # 隐藏层使用激活函数，输出层根据 if_raw_out 决定
        if i < len(dims) - 2:
            layers.append(activation())
        elif not if_raw_out:
            layers.append(activation())
    
    return nn.Sequential(*layers)


def layer_init_with_orthogonal(layer: nn.Linear, std: float = 1.0, bias_const: float = 1e-6):
    """
    正交初始化
    
    借鉴 ElegantRL 的初始化策略：
    - Critic 最后一层 std=0.5（保守估计）
    - Actor 最后一层 std=0.1（谨慎输出）
    
    Args:
        layer: 线性层
        std: 权重标准差
        bias_const: 偏置常数
    """
    th.nn.init.orthogonal_(layer.weight, std)
    th.nn.init.constant_(layer.bias, bias_const)


class StateNormalizer(nn.Module):
    """
    状态归一化层
    
    借鉴 ElegantRL 的设计，在网络内部维护状态统计量：
    - 在线更新均值和标准差
    - 避免外部预计算的麻烦
    
    对期货数据至关重要：
    - 螺纹钢价格 3000+，焦煤价格 1500+，原油价格 500+
    - 不同品种价格量级差异巨大
    """
    
    def __init__(self, state_dim: int, if_update: bool = True):
        super().__init__()
        
        self.state_dim = state_dim
        self.if_update = if_update
        self._initialized = False
        
        # 可学习的统计量（不参与梯度计算）
        self.state_avg = nn.Parameter(th.zeros(state_dim), requires_grad=False)
        self.state_std = nn.Parameter(th.ones(state_dim), requires_grad=False)
        
        # 在线统计
        self.register_buffer('running_mean', th.zeros(state_dim))
        self.register_buffer('running_var', th.ones(state_dim))
        self.register_buffer('count', th.tensor(0, dtype=th.long))
    
    def forward(self, state: th.Tensor) -> th.Tensor:
        """
        归一化状态
        
        Args:
            state: 状态张量 (batch_size, state_dim)
        
        Returns:
            归一化后的状态
        """
        # 动态调整维度（如果输入维度与初始化维度不同）
        if state.shape[-1] != self.state_dim:
            self._adjust_dimensions(state.shape[-1])
        
        if self.training and self.if_update:
            self._update_statistics(state)
        
        return (state - self.state_avg) / (self.state_std + 1e-8)
    
    def _adjust_dimensions(self, new_dim: int):
        """动态调整维度"""
        if not self._initialized:
            self.state_dim = new_dim
            self.state_avg = nn.Parameter(th.zeros(new_dim), requires_grad=False)
            self.state_std = nn.Parameter(th.ones(new_dim), requires_grad=False)
            self.running_mean = th.zeros(new_dim)
            self.running_var = th.ones(new_dim)
            self.count = th.tensor(0, dtype=th.long)
            self._initialized = True
    
    def _update_statistics(self, state: th.Tensor):
        """在线更新统计量"""
        batch_mean = state.mean(dim=0)
        batch_var = state.var(dim=0, unbiased=False)
        batch_count = state.shape[0]
        
        # Welford 在线算法
        delta = batch_mean - self.running_mean
        total_count = self.count + batch_count
        
        self.running_mean += delta * batch_count / total_count
        self.running_var = (
            self.running_var * self.count + 
            batch_var * batch_count + 
            delta ** 2 * self.count * batch_count / total_count
        ) / total_count
        
        self.count = total_count
        
        # 更新参数
        self.state_avg.data.copy_(self.running_mean)
        self.state_std.data.copy_(self.running_var.sqrt())


class ActorPPO(nn.Module):
    """
    PPO Actor 网络（策略网络）
    
    借鉴 ElegantRL 的 ActorPPO 设计：
    1. 内置状态归一化
    2. 正交初始化
    3. 输出动作均值和标准差
    
    输出：
    - action_mean: 动作均值 (batch_size, action_dim)
    - action_std: 动作标准差 (batch_size, action_dim)
    """
    
    def __init__(self, 
                 state_dim: int,
                 action_dim: int,
                 net_dims: List[int] = None,
                 if_state_norm: bool = True):
        """
        初始化 Actor
        
        Args:
            state_dim: 状态维度
            action_dim: 动作维度
            net_dims: 隐藏层维度
            if_state_norm: 是否使用状态归一化
        """
        super().__init__()
        
        if net_dims is None:
            net_dims = [128, 128]
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # 状态归一化
        self.if_state_norm = if_state_norm
        if if_state_norm:
            self.state_norm = StateNormalizer(state_dim)
        
        # 特征提取网络
        self.net_s = build_mlp(dims=[state_dim, *net_dims], if_raw_out=False)
        
        # 动作均值和标准差
        self.net_a = nn.Linear(net_dims[-1], action_dim * 2)
        layer_init_with_orthogonal(self.net_a[-1] if isinstance(self.net_a, nn.Sequential) else self.net_a, std=0.1)
        
        # 重新初始化最后一层
        if isinstance(self.net_a, nn.Linear):
            layer_init_with_orthogonal(self.net_a, std=0.1)
    
    def forward(self, state: th.Tensor) -> th.Tensor:
        """
        前向传播（确定性动作）
        
        Args:
            state: 状态张量 (batch_size, state_dim)
        
        Returns:
            动作均值 (batch_size, action_dim)
        """
        if self.if_state_norm:
            state = self.state_norm(state)
        
        s_enc = self.net_s(state)
        a_avg = self.net_a(s_enc)[:, :self.action_dim]
        return a_avg.tanh()
    
    def get_action(self, state: th.Tensor) -> Tuple[th.Tensor, th.Tensor]:
        """
        获取随机动作（用于探索）
        
        Args:
            state: 状态张量 (batch_size, state_dim)
        
        Returns:
            (action, log_prob)
        """
        if self.if_state_norm:
            state = self.state_norm(state)
        
        s_enc = self.net_s(state)
        a_avg, a_std_log = self.net_a(s_enc).chunk(2, dim=1)
        a_std = a_std_log.clamp(-16, 2).exp()
        
        # 重参数化采样
        noise = th.randn_like(a_avg)
        action = a_avg + a_std * noise
        
        # 计算 log 概率
        log_prob = -0.5 * ((noise) ** 2 + 2 * a_std_log + np.log(2 * np.pi))
        log_prob = log_prob.sum(dim=1)
        
        return action.tanh(), log_prob
    
    def get_action_logprob(self, state: th.Tensor, action: th.Tensor) -> th.Tensor:
        """
        计算给定动作的 log 概率
        
        Args:
            state: 状态张量 (batch_size, state_dim)
            action: 动作张量 (batch_size, action_dim)
        
        Returns:
            log_prob (batch_size,)
        """
        if self.if_state_norm:
            state = self.state_norm(state)
        
        s_enc = self.net_s(state)
        a_avg, a_std_log = self.net_a(s_enc).chunk(2, dim=1)
        a_std = a_std_log.clamp(-16, 2).exp()
        
        # 反 tanh 变换
        action_raw = action.arctanh().clamp(-5, 5)
        
        # 计算 log 概率
        noise = (action_raw - a_avg) / (a_std + 1e-8)
        log_prob = -0.5 * ((noise) ** 2 + 2 * a_std_log + np.log(2 * np.pi))
        log_prob = log_prob.sum(dim=1)
        
        return log_prob


class CriticPPO(nn.Module):
    """
    PPO Critic 网络（价值网络）
    
    借鉴 ElegantRL 的 CriticPPO 设计：
    1. 内置状态归一化
    2. 正交初始化（std=0.5，保守估计）
    3. 输出状态价值 V(s)
    """
    
    def __init__(self, 
                 state_dim: int,
                 net_dims: List[int] = None,
                 if_state_norm: bool = True):
        """
        初始化 Critic
        
        Args:
            state_dim: 状态维度
            net_dims: 隐藏层维度
            if_state_norm: 是否使用状态归一化
        """
        super().__init__()
        
        if net_dims is None:
            net_dims = [128, 128]
        
        self.state_dim = state_dim
        
        # 状态归一化
        self.if_state_norm = if_state_norm
        if if_state_norm:
            self.state_norm = StateNormalizer(state_dim)
        
        # 价值网络
        self.net_s = build_mlp(dims=[state_dim, *net_dims], if_raw_out=False)
        self.net_v = nn.Linear(net_dims[-1], 1)
        layer_init_with_orthogonal(self.net_v, std=0.5)
    
    def forward(self, state: th.Tensor) -> th.Tensor:
        """
        前向传播
        
        Args:
            state: 状态张量 (batch_size, state_dim)
        
        Returns:
            状态价值 (batch_size, 1)
        """
        if self.if_state_norm:
            state = self.state_norm(state)
        
        s_enc = self.net_s(state)
        value = self.net_v(s_enc)
        return value


class ActorCriticPPO(nn.Module):
    """
    Actor-Critic 组合网络
    
    共享特征提取层，分别输出动作和价值
    """
    
    def __init__(self, 
                 state_dim: int,
                 action_dim: int,
                 net_dims: List[int] = None,
                 if_state_norm: bool = True):
        """
        初始化 Actor-Critic
        
        Args:
            state_dim: 状态维度
            action_dim: 动作维度
            net_dims: 隐藏层维度
            if_state_norm: 是否使用状态归一化
        """
        super().__init__()
        
        if net_dims is None:
            net_dims = [128, 128]
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # 状态归一化
        self.if_state_norm = if_state_norm
        if if_state_norm:
            self.state_norm = StateNormalizer(state_dim)
        
        # 共享特征提取
        self.net_s = build_mlp(dims=[state_dim, *net_dims], if_raw_out=False)
        
        # Actor 头
        self.net_a = nn.Linear(net_dims[-1], action_dim * 2)
        layer_init_with_orthogonal(self.net_a, std=0.1)
        
        # Critic 头
        self.net_v = nn.Linear(net_dims[-1], 1)
        layer_init_with_orthogonal(self.net_v, std=0.5)
    
    def forward(self, state: th.Tensor) -> Tuple[th.Tensor, th.Tensor]:
        """
        前向传播
        
        Args:
            state: 状态张量 (batch_size, state_dim)
        
        Returns:
            (action_mean, state_value)
        """
        if self.if_state_norm:
            state = self.state_norm(state)
        
        s_enc = self.net_s(state)
        
        # Actor 输出
        a_avg = self.net_a(s_enc)[:, :self.action_dim].tanh()
        
        # Critic 输出
        value = self.net_v(s_enc)
        
        return a_avg, value
    
    def get_action(self, state: th.Tensor) -> Tuple[th.Tensor, th.Tensor, th.Tensor]:
        """
        获取随机动作（用于探索）
        
        Args:
            state: 状态张量 (batch_size, state_dim)
        
        Returns:
            (action, log_prob, value)
        """
        if self.if_state_norm:
            state = self.state_norm(state)
        
        s_enc = self.net_s(state)
        
        # Actor 输出
        a_avg, a_std_log = self.net_a(s_enc).chunk(2, dim=1)
        a_std = a_std_log.clamp(-16, 2).exp()
        
        # 重参数化采样
        noise = th.randn_like(a_avg)
        action = a_avg + a_std * noise
        
        # 计算 log 概率
        log_prob = -0.5 * ((noise) ** 2 + 2 * a_std_log + np.log(2 * np.pi))
        log_prob = log_prob.sum(dim=1)
        
        # Critic 输出
        value = self.net_v(s_enc).squeeze(-1)
        
        return action.tanh(), log_prob, value


class CriticEnsemble(nn.Module):
    """
    集成 Critic 网络
    
    借鉴 ElegantRL 的 CriticEnsemble 设计：
    - 使用多个 Critic 网络
    - 取最小值减少 Q 值过估计
    """
    
    def __init__(self, 
                 state_dim: int,
                 action_dim: int,
                 net_dims: List[int] = None,
                 num_ensembles: int = 4):
        """
        初始化集成 Critic
        
        Args:
            state_dim: 状态维度
            action_dim: 动作维度
            net_dims: 隐藏层维度
            num_ensembles: 集成数量
        """
        super().__init__()
        
        if net_dims is None:
            net_dims = [128, 128]
        
        self.num_ensembles = num_ensembles
        
        # 共享编码器
        self.encoder_sa = build_mlp(dims=[state_dim + action_dim, net_dims[0]], if_raw_out=False)
        
        # 多个 Critic 头
        self.decoder_qs = nn.ModuleList()
        for _ in range(num_ensembles):
            decoder_q = nn.Sequential(
                build_mlp(dims=[*net_dims, 1]),
            )
            # 重新初始化最后一层
            if isinstance(decoder_q[-1], nn.Linear):
                layer_init_with_orthogonal(decoder_q[-1], std=0.5)
            self.decoder_qs.append(decoder_q)
    
    def forward(self, state: th.Tensor, action: th.Tensor) -> th.Tensor:
        """
        前向传播
        
        Args:
            state: 状态张量 (batch_size, state_dim)
            action: 动作张量 (batch_size, action_dim)
        
        Returns:
            Q 值 (batch_size, num_ensembles)
        """
        sa = th.cat([state, action], dim=1)
        s_enc = self.encoder_sa(sa)
        
        q_values = th.cat([decoder_q(s_enc) for decoder_q in self.decoder_qs], dim=1)
        return q_values
    
    def get_min_q(self, state: th.Tensor, action: th.Tensor) -> th.Tensor:
        """
        获取最小 Q 值
        
        Args:
            state: 状态张量
            action: 动作张量
        
        Returns:
            最小 Q 值 (batch_size,)
        """
        q_values = self.forward(state, action)
        return q_values.min(dim=1)[0]
