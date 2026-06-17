"""
AgentBase 单元测试

测试内容：
1. AgentConfig 配置
2. AgentState 状态
3. AgentResult 结果
4. AgentBase 抽象基类
5. 具体 Agent 实现示例

版本：v1.0
创建日期：2026-06-17
"""

import pytest
from typing import Any, Dict

from scripts.trend_scanner.core.agent_base import (
    AgentBase,
    AgentConfig,
    AgentState,
    AgentResult,
)


class TestAgentConfig:
    """AgentConfig 测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = AgentConfig()
        
        assert config.agent_id == "default"
        assert config.agent_type == "generic"
        assert config.learning_rate == 1e-4
        assert config.batch_size == 64
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = AgentConfig(
            agent_id="scanner_001",
            agent_type="scanner",
            learning_rate=2e-4,
            custom_params={"symbol": "RB"}
        )
        
        assert config.agent_id == "scanner_001"
        assert config.agent_type == "scanner"
        assert config.custom_params["symbol"] == "RB"


class TestAgentState:
    """AgentState 测试"""
    
    def test_default_state(self):
        """测试默认状态"""
        state = AgentState()
        
        assert state.step == 0
        assert state.episode == 0
        assert state.total_reward == 0.0
        assert state.is_training is False
        assert state.is_exploring is True
    
    def test_state_update(self):
        """测试状态更新"""
        state = AgentState()
        state.step = 10
        state.episode = 5
        state.total_reward = 100.0
        
        assert state.step == 10
        assert state.episode == 5
        assert state.total_reward == 100.0


class TestAgentResult:
    """AgentResult 测试"""
    
    def test_default_result(self):
        """测试默认结果"""
        result = AgentResult()
        
        assert result.action is None
        assert result.signal == "NEUTRAL"
        assert result.strength == 0.0
        assert result.confidence == 0.0
    
    def test_custom_result(self):
        """测试自定义结果"""
        result = AgentResult(
            action=0.5,
            signal="LONG",
            strength=0.7,
            confidence=0.8,
            metadata={"symbol": "RB"}
        )
        
        assert result.action == 0.5
        assert result.signal == "LONG"
        assert result.metadata["symbol"] == "RB"


class TestAgentBase:
    """AgentBase 测试"""
    
    def test_cannot_instantiate_abstract(self):
        """测试不能实例化抽象类"""
        with pytest.raises(TypeError):
            AgentBase()
    
    def test_concrete_agent(self):
        """测试具体 Agent 实现"""
        # 创建一个具体的 Agent
        class SimpleAgent(AgentBase):
            def perceive(self, raw_state):
                return {"processed": raw_state}
            
            def reason(self, state):
                return AgentResult(
                    action=state["processed"],
                    signal="LONG" if state["processed"] > 0.5 else "SHORT"
                )
        
        config = AgentConfig(agent_id="test_agent")
        agent = SimpleAgent(config)
        result = agent.run(0.8)
        
        assert result.action == 0.8
        assert result.signal == "LONG"
        assert agent.state.step == 1
    
    def test_agent_with_reflect(self):
        """测试带 reflect 的 Agent"""
        class ReflectiveAgent(AgentBase):
            def perceive(self, raw_state):
                return raw_state
            
            def reason(self, state):
                return AgentResult(action=state, signal="LONG")
            
            def reflect(self, result, execution_result=None):
                # 更新统计
                self.metrics["total_steps"] += 1
                return {"step": self.metrics["total_steps"]}
        
        agent = ReflectiveAgent()
        
        # 运行多次
        for _ in range(5):
            agent.run(1.0)
        
        assert agent.metrics["total_steps"] == 5
    
    def test_agent_train(self):
        """测试训练功能"""
        class TrainableAgent(AgentBase):
            def perceive(self, raw_state):
                return raw_state
            
            def reason(self, state):
                return AgentResult(action=state)
            
            def train(self, experiences):
                # 模拟训练
                loss = sum(e.get("reward", 0) for e in experiences) / len(experiences)
                return {"loss": loss}
        
        agent = TrainableAgent()
        experiences = [{"reward": 1.0}, {"reward": -0.5}, {"reward": 0.5}]
        
        metrics = agent.train(experiences)
        
        assert "loss" in metrics
        assert metrics["loss"] == pytest.approx(0.333, rel=0.01)
    
    def test_agent_save_load(self):
        """测试保存和加载"""
        class SaveableAgent(AgentBase):
            def perceive(self, raw_state):
                return raw_state
            
            def reason(self, state):
                return AgentResult(action=state)
            
            def save(self, path):
                self._saved_path = path
            
            def load(self, path):
                self._loaded_path = path
        
        agent = SaveableAgent()
        agent.save("test_model.pth")
        agent.load("test_model.pth")
        
        assert agent._saved_path == "test_model.pth"
        assert agent._loaded_path == "test_model.pth"
    
    def test_agent_get_metrics(self):
        """测试获取统计信息"""
        class MetricsAgent(AgentBase):
            def perceive(self, raw_state):
                return raw_state
            
            def reason(self, state):
                return AgentResult(action=state)
        
        agent = MetricsAgent()
        agent.run(1.0)
        agent.run(2.0)
        
        metrics = agent.get_metrics()
        
        assert "total_steps" in metrics
        assert "state" in metrics
        assert metrics["state"]["step"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
