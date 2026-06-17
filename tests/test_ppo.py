"""
PPO 训练器单元测试

测试内容：
1. ActorPPO 网络
2. CriticPPO 网络
3. AgentPPO 算法
4. RLTrainer 训练循环

版本：v1.0
创建日期：2026-06-17
"""

import numpy as np
import pytest
import torch as th
from typing import Dict, Any, List, Tuple

from scripts.trend_scanner.rl.base import RLAction
from scripts.trend_scanner.rl.networks import (
    ActorPPO,
    CriticPPO,
    ActorCriticPPO,
    CriticEnsemble,
    StateNormalizer,
    build_mlp,
)
from scripts.trend_scanner.rl.agent_ppo import AgentPPO, AgentPPOShared
from scripts.trend_scanner.rl.futures_env import FuturesTradingEnv
from scripts.trend_scanner.rl.trainer import RLTrainer, evaluate_agent
from scripts.trend_scanner.trend_scanner_config import RLConfig, TrendScannerConfig


class TestBuildMLP:
    """build_mlp 函数测试"""
    
    def test_basic_mlp(self):
        """测试基本 MLP 构建"""
        mlp = build_mlp(dims=[10, 64, 32, 1])
        
        assert isinstance(mlp, th.nn.Sequential)
        # 检查层数
        linear_count = sum(1 for m in mlp.modules() if isinstance(m, th.nn.Linear))
        assert linear_count == 3
    
    def test_mlp_output_activation(self):
        """测试输出层激活函数"""
        # with raw output
        mlp_raw = build_mlp(dims=[10, 64, 1], if_raw_out=True)
        assert isinstance(mlp_raw[-1], th.nn.Linear)
        
        # without raw output
        mlp_no_raw = build_mlp(dims=[10, 64, 1], if_raw_out=False)
        assert isinstance(mlp_no_raw[-1], th.nn.ReLU)


class TestStateNormalizer:
    """StateNormalizer 测试"""
    
    def test_initialization(self):
        """测试初始化"""
        normalizer = StateNormalizer(state_dim=10)
        
        assert normalizer.state_dim == 10
        assert th.all(normalizer.state_avg == 0)
        assert th.all(normalizer.state_std == 1)
    
    def test_forward(self):
        """测试前向传播"""
        normalizer = StateNormalizer(state_dim=5)
        
        state = th.randn(32, 5)
        normalized = normalizer(state)
        
        assert normalized.shape == (32, 5)
    
    def test_online_update(self):
        """测试在线更新"""
        normalizer = StateNormalizer(state_dim=5, if_update=True)
        
        # 训练模式
        normalizer.train()
        
        # 多次前向传播
        for _ in range(10):
            state = th.randn(16, 5) + 100  # 均值为 100
            normalizer(state)
        
        # 统计量应该更新
        assert normalizer.count > 0
        assert th.abs(normalizer.running_mean.mean() - 100) < 10  # 大约 100


class TestActorPPO:
    """ActorPPO 测试"""
    
    def test_initialization(self):
        """测试初始化"""
        actor = ActorPPO(state_dim=10, action_dim=1, net_dims=[64, 32])
        
        assert actor.state_dim == 10
        assert actor.action_dim == 1
    
    def test_forward(self):
        """测试前向传播"""
        actor = ActorPPO(state_dim=10, action_dim=1, net_dims=[64, 32])
        
        state = th.randn(16, 10)
        action = actor(state)
        
        assert action.shape == (16, 1)
        assert th.all(action >= -1) and th.all(action <= 1)  # tanh 输出
    
    def test_get_action(self):
        """测试获取随机动作"""
        actor = ActorPPO(state_dim=10, action_dim=1, net_dims=[64, 32])
        
        state = th.randn(16, 10)
        action, log_prob = actor.get_action(state)
        
        assert action.shape == (16, 1)
        assert log_prob.shape == (16,)
    
    def test_get_action_logprob(self):
        """测试计算 log 概率"""
        actor = ActorPPO(state_dim=10, action_dim=1, net_dims=[64, 32])
        
        state = th.randn(16, 10)
        action = th.randn(16, 1).tanh()
        log_prob = actor.get_action_logprob(state, action)
        
        assert log_prob.shape == (16,)


class TestCriticPPO:
    """CriticPPO 测试"""
    
    def test_initialization(self):
        """测试初始化"""
        critic = CriticPPO(state_dim=10, net_dims=[64, 32])
        
        assert critic.state_dim == 10
    
    def test_forward(self):
        """测试前向传播"""
        critic = CriticPPO(state_dim=10, net_dims=[64, 32])
        
        state = th.randn(16, 10)
        value = critic(state)
        
        assert value.shape == (16, 1)


class TestActorCriticPPO:
    """ActorCriticPPO 测试"""
    
    def test_initialization(self):
        """测试初始化"""
        ac = ActorCriticPPO(state_dim=10, action_dim=1, net_dims=[64, 32])
        
        assert ac.state_dim == 10
        assert ac.action_dim == 1
    
    def test_forward(self):
        """测试前向传播"""
        ac = ActorCriticPPO(state_dim=10, action_dim=1, net_dims=[64, 32])
        
        state = th.randn(16, 10)
        action_mean, value = ac(state)
        
        assert action_mean.shape == (16, 1)
        assert value.shape == (16, 1)
    
    def test_get_action(self):
        """测试获取随机动作"""
        ac = ActorCriticPPO(state_dim=10, action_dim=1, net_dims=[64, 32])
        
        state = th.randn(16, 10)
        action, log_prob, value = ac.get_action(state)
        
        assert action.shape == (16, 1)
        assert log_prob.shape == (16,)
        assert value.shape == (16,)


class TestCriticEnsemble:
    """CriticEnsemble 测试"""
    
    def test_initialization(self):
        """测试初始化"""
        critic = CriticEnsemble(state_dim=10, action_dim=1, net_dims=[64, 32], num_ensembles=4)
        
        assert critic.num_ensembles == 4
    
    def test_forward(self):
        """测试前向传播"""
        critic = CriticEnsemble(state_dim=10, action_dim=1, net_dims=[64, 32], num_ensembles=4)
        
        state = th.randn(16, 10)
        action = th.randn(16, 1)
        q_values = critic(state, action)
        
        assert q_values.shape == (16, 4)
    
    def test_get_min_q(self):
        """测试获取最小 Q 值"""
        critic = CriticEnsemble(state_dim=10, action_dim=1, net_dims=[64, 32], num_ensembles=4)
        
        state = th.randn(16, 10)
        action = th.randn(16, 1)
        min_q = critic.get_min_q(state, action)
        
        assert min_q.shape == (16,)


class TestAgentPPO:
    """AgentPPO 测试"""
    
    def test_initialization(self):
        """测试初始化"""
        rl_config = RLConfig(net_dims=[64, 32])
        agent = AgentPPO(state_dim=10, rl_config=rl_config)
        
        assert agent.state_dim == 10
        assert agent.gamma == 0.99
        assert agent.lambda_gae == 0.95
    
    def test_perceive(self):
        """测试感知"""
        agent = AgentPPO(state_dim=10)
        
        env_state = {"observation": np.random.randn(10)}
        state = agent.perceive(env_state)
        
        assert state.shape == (10,)
    
    def test_reason(self):
        """测试推理"""
        agent = AgentPPO(state_dim=10)
        
        state = np.random.randn(10)
        action = agent.reason(state)
        
        assert -1 <= action.action <= 1
        assert action.log_prob is not None
        assert action.value is not None
    
    def test_reflect(self):
        """测试反思"""
        agent = AgentPPO(state_dim=10)
        
        # 创建模拟经验
        experiences = []
        for _ in range(32):
            exp = type('Experience', (), {
                'state': np.random.randn(10),
                'action': np.random.uniform(-1, 1),
                'reward': np.random.randn(),
                'done': False,
                'log_prob': np.random.randn(),
                'value': np.random.randn(),
            })()
            experiences.append(exp)
        
        metrics = agent.reflect(experiences)
        
        assert 'loss_actor' in metrics
        assert 'loss_critic' in metrics
    
    def test_execute_action(self):
        """测试执行动作"""
        data = np.random.randn(100, 5)
        env = FuturesTradingEnv(data=data, state_dim=8)
        
        agent = AgentPPO(state_dim=10)
        
        obs, _ = env.reset()
        action = RLAction(action=0.5, log_prob=0.0, value=0.0)
        
        next_state, reward, terminated, truncated, info = agent.execute_action(env, action)
        
        assert next_state.shape == (10,)
        assert isinstance(reward, float)
    
    def test_explore(self):
        """测试探索"""
        data = np.random.randn(100, 5)
        env = FuturesTradingEnv(data=data, state_dim=8)  # 实际状态维度 = 8 + 2 = 10
        
        agent = AgentPPO(state_dim=10)  # 与环境状态维度一致
        
        experiences = agent.explore(env, horizon_len=32)
        
        assert len(experiences) == 32
    
    def test_save_load(self, tmp_path):
        """测试保存和加载"""
        agent = AgentPPO(state_dim=10)
        
        # 保存
        save_path = str(tmp_path / "ppo_model.pth")
        agent.save(save_path)
        
        # 加载
        new_agent = AgentPPO(state_dim=10)
        new_agent.load(save_path)
        
        # 验证参数一致性
        for p1, p2 in zip(agent.act.parameters(), new_agent.act.parameters()):
            th.testing.assert_close(p1, p2)


class TestAgentPPOShared:
    """AgentPPOShared 测试"""
    
    def test_initialization(self):
        """测试初始化"""
        rl_config = RLConfig(net_dims=[64, 32])
        agent = AgentPPOShared(state_dim=10, rl_config=rl_config)
        
        assert agent.state_dim == 10
    
    def test_reason(self):
        """测试推理"""
        agent = AgentPPOShared(state_dim=10)
        
        state = np.random.randn(10)
        action = agent.reason(state)
        
        assert -1 <= action.action <= 1
    
    def test_reflect(self):
        """测试反思"""
        agent = AgentPPOShared(state_dim=10)
        
        # 创建模拟经验
        experiences = []
        for _ in range(32):
            exp = type('Experience', (), {
                'state': np.random.randn(10),
                'action': np.random.uniform(-1, 1),
                'reward': np.random.randn(),
                'done': False,
                'log_prob': np.random.randn(),
                'value': np.random.randn(),
            })()
            experiences.append(exp)
        
        metrics = agent.reflect(experiences)
        
        assert 'loss_actor' in metrics
        assert 'loss_critic' in metrics


class TestRLTrainer:
    """RLTrainer 测试"""
    
    def test_initialization(self):
        """测试初始化"""
        config = TrendScannerConfig()
        config.rl.enabled = True
        config.rl.net_dims = [64, 32]
        
        trainer = RLTrainer(config, save_dir="test_models/rl")
        
        assert trainer.rl_config.algorithm == "ppo"
        assert trainer.total_steps == 0
    
    def test_create_agent(self):
        """测试创建 Agent"""
        config = TrendScannerConfig()
        config.rl.enabled = True
        
        trainer = RLTrainer(config)
        
        assert isinstance(trainer.agent, AgentPPO)


class TestEvaluateAgent:
    """evaluate_agent 函数测试"""
    
    def test_evaluate(self):
        """测试评估"""
        data = np.random.randn(100, 5)
        env = FuturesTradingEnv(data=data, state_dim=8)  # 实际状态维度 = 8 + 2 = 10
        
        agent = AgentPPO(state_dim=10)  # 与环境状态维度一致
        
        results = evaluate_agent(agent, env, n_episodes=2)
        
        assert 'mean_reward' in results
        assert 'std_reward' in results
        assert 'mean_trades' in results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
