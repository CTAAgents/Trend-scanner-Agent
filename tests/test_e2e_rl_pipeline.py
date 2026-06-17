"""
RL 端到端流程测试

测试完整的 RL 训练+评估+集成流程：
1. 数据准备
2. RL Agent 训练
3. Walk-Forward 验证
4. 信号生成
5. Scanner 集成
6. Reasoner 集成

版本：v1.0
创建日期：2026-06-17
"""

import numpy as np
import pytest
from typing import Dict, Any

from scripts.trend_scanner.rl import (
    AgentPPO,
    FuturesTradingEnv,
    RLSignalGenerator,
    RLEnsembleSignalGenerator,
    integrate_rl_signal_to_scanner,
    evaluate_agent,
    walk_forward_validate_rl,
)
from scripts.trend_scanner.rl.walk_forward_rl import RLWalkForwardValidator
from scripts.trend_scanner.trend_scanner_config import RLConfig


class TestE2ERLPipeline:
    """端到端 RL 流程测试"""
    
    @pytest.fixture
    def sample_data(self):
        """生成样本数据"""
        np.random.seed(42)
        n_steps = 200
        
        # 生成价格数据（带趋势）
        trend = np.linspace(0, 0.5, n_steps)
        noise = np.random.randn(n_steps) * 0.02
        returns = trend + noise
        prices = 100 * np.exp(np.cumsum(returns))
        
        # 生成 OHLCV 数据
        data = np.zeros((n_steps, 5))
        data[:, 0] = prices * (1 + np.random.randn(n_steps) * 0.001)  # open
        data[:, 1] = prices * (1 + np.abs(np.random.randn(n_steps)) * 0.005)  # high
        data[:, 2] = prices * (1 - np.abs(np.random.randn(n_steps)) * 0.005)  # low
        data[:, 3] = prices  # close
        data[:, 4] = np.random.randint(1000, 10000, n_steps)  # volume
        
        return data
    
    @pytest.fixture
    def state_features(self, sample_data):
        """生成状态特征"""
        n_steps = len(sample_data)
        
        # 简单的技术指标
        returns = np.diff(sample_data[:, 3], prepend=sample_data[0, 3]) / sample_data[:, 3]
        rsi = np.clip(50 + np.cumsum(returns) * 100, 0, 100) / 100
        volatility = np.abs(returns)
        volume_change = np.diff(sample_data[:, 4], prepend=sample_data[0, 4]) / sample_data[:, 4]
        
        features = np.column_stack([returns, rsi, volatility, volume_change])
        
        # 标准化
        mean = np.mean(features, axis=0)
        std = np.std(features, axis=0) + 1e-8
        features = (features - mean) / std
        
        return features
    
    def test_train_and_evaluate(self, sample_data):
        """测试训练和评估流程"""
        state_dim = 6  # 4 技术指标 + 2 (position + pnl)
        
        # 创建环境
        env = FuturesTradingEnv(data=sample_data, state_dim=4)
        
        # 创建 Agent
        rl_config = RLConfig(
            net_dims=[32, 16],
            horizon_len=64,
            batch_size=32,
            repeat_times=2,
        )
        agent = AgentPPO(state_dim=state_dim, rl_config=rl_config)
        
        # 训练
        for _ in range(3):
            experiences = agent.explore(env, horizon_len=64)
            metrics = agent.reflect(experiences)
        
        # 评估
        results = evaluate_agent(agent, env, n_episodes=2)
        
        assert 'mean_reward' in results
        assert 'std_reward' in results
        assert isinstance(results['mean_reward'], float)
    
    def test_walk_forward_validation(self, sample_data):
        """测试 Walk-Forward 验证"""
        from scripts.trend_scanner.walk_forward_validator import WalkForwardConfig
        
        state_dim = 6
        
        # 配置
        wf_config = WalkForwardConfig(
            optimization_window=50,
            test_window=20,
            step_size=20,
        )
        rl_config = RLConfig(
            net_dims=[32, 16],
            horizon_len=32,
            batch_size=16,
            repeat_times=1,
        )
        
        # 运行验证
        result = walk_forward_validate_rl(
            data=sample_data,
            state_dim=state_dim,
            rl_config=rl_config,
            wf_config=wf_config,
            train_steps_per_window=100,
        )
        
        assert result.total_windows > 0
        assert 0 <= result.pass_rate <= 1
        assert len(result.window_results) > 0
    
    def test_signal_generation(self, sample_data, state_features):
        """测试信号生成"""
        state_dim = 6
        
        # 创建环境并训练
        env = FuturesTradingEnv(data=sample_data, state_dim=4)
        rl_config = RLConfig(net_dims=[32, 16])
        agent = AgentPPO(state_dim=state_dim, rl_config=rl_config)
        
        # 简单训练
        for _ in range(2):
            experiences = agent.explore(env, horizon_len=32)
            agent.reflect(experiences)
        
        # 创建信号生成器
        generator = RLSignalGenerator.__new__(RLSignalGenerator)
        generator.state_dim = state_dim
        generator.agent = agent
        
        # 生成信号
        features = state_features[0]
        signal = generator.generate_signal(features, current_position=0.0)
        
        assert 'direction' in signal
        assert 'strength' in signal
        assert 'confidence' in signal
        assert signal['direction'] in ['LONG', 'SHORT', 'NEUTRAL']
    
    def test_scanner_integration(self, sample_data, state_features):
        """测试 Scanner 集成"""
        state_dim = 6
        
        # 创建环境并训练
        env = FuturesTradingEnv(data=sample_data, state_dim=4)
        rl_config = RLConfig(net_dims=[32, 16])
        agent = AgentPPO(state_dim=state_dim, rl_config=rl_config)
        
        # 简单训练
        for _ in range(2):
            experiences = agent.explore(env, horizon_len=32)
            agent.reflect(experiences)
        
        # 创建信号生成器
        generator = RLSignalGenerator.__new__(RLSignalGenerator)
        generator.state_dim = state_dim
        generator.agent = agent
        
        # 生成 RL 信号
        features = state_features[0]
        rl_signal = generator.generate_signal(features, current_position=0.0)
        
        # 模拟 Scanner 结果
        scanner_result = {
            'symbol': 'RB',
            'direction': 'LONG',
            'strength': 0.7,
            'signal_strength': 'MEDIUM',
        }
        
        # 集成
        final_result = integrate_rl_signal_to_scanner(
            scanner_result, rl_signal, rl_weight=0.3
        )
        
        assert 'rl_signal' in final_result
        assert 'combined_score' in final_result
        assert 'direction' in final_result
    
    def test_ensemble_signal(self, sample_data, state_features):
        """测试集成信号"""
        state_dim = 6
        
        # 创建环境并训练多个 Agent
        env = FuturesTradingEnv(data=sample_data, state_dim=4)
        
        agents = []
        for _ in range(2):
            rl_config = RLConfig(net_dims=[32, 16])
            agent = AgentPPO(state_dim=state_dim, rl_config=rl_config)
            
            # 简单训练
            for _ in range(2):
                experiences = agent.explore(env, horizon_len=32)
                agent.reflect(experiences)
            
            agents.append(agent)
        
        # 创建集成信号生成器
        ensemble = RLEnsembleSignalGenerator.__new__(RLEnsembleSignalGenerator)
        ensemble.state_dim = state_dim
        ensemble.agents = agents
        
        # 生成信号
        features = state_features[0]
        signal = ensemble.generate_signal(features, current_position=0.0)
        
        assert signal['source'] == 'rl_ensemble'
        assert 'consistency' in signal
        assert 'n_models' in signal
        assert signal['n_models'] == 2
    
    def test_full_pipeline(self, sample_data, state_features):
        """测试完整流程"""
        from scripts.trend_scanner.walk_forward_validator import WalkForwardConfig
        
        state_dim = 6
        
        # 1. 训练 Agent
        env = FuturesTradingEnv(data=sample_data, state_dim=4)
        rl_config = RLConfig(
            net_dims=[32, 16],
            horizon_len=64,
            batch_size=32,
            repeat_times=2,
        )
        agent = AgentPPO(state_dim=state_dim, rl_config=rl_config)
        
        for _ in range(3):
            experiences = agent.explore(env, horizon_len=64)
            agent.reflect(experiences)
        
        # 2. Walk-Forward 验证
        wf_config = WalkForwardConfig(
            optimization_window=50,
            test_window=20,
            step_size=20,
        )
        
        wf_result = walk_forward_validate_rl(
            data=sample_data,
            state_dim=state_dim,
            rl_config=rl_config,
            wf_config=wf_config,
            train_steps_per_window=100,
        )
        
        # 3. 信号生成
        generator = RLSignalGenerator.__new__(RLSignalGenerator)
        generator.state_dim = state_dim
        generator.agent = agent
        
        features = state_features[0]
        rl_signal = generator.generate_signal(features, current_position=0.0)
        
        # 4. Scanner 集成
        scanner_result = {
            'symbol': 'RB',
            'direction': 'LONG',
            'strength': 0.7,
        }
        
        final_result = integrate_rl_signal_to_scanner(
            scanner_result, rl_signal, rl_weight=0.3
        )
        
        # 验证
        assert wf_result.total_windows > 0
        assert rl_signal['direction'] in ['LONG', 'SHORT', 'NEUTRAL']
        assert 'rl_signal' in final_result
        
        # 打印结果摘要
        print("\n" + "=" * 60)
        print("端到端流程测试结果")
        print("=" * 60)
        print(f"Walk-Forward 通过率: {wf_result.pass_rate:.2%}")
        print(f"RL 信号方向: {rl_signal['direction']}")
        print(f"RL 信号强度: {rl_signal['strength']:.2f}")
        print(f"最终方向: {final_result['direction']}")
        print("=" * 60)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
