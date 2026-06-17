"""
Agent 基类模块

定义统一的 Agent 接口，所有 Agent 实现相同生命周期：
- perceive: 感知环境状态
- reason: 基于状态做出决策
- act: 执行动作
- reflect: 评估结果，更新策略

借鉴 ElegantRL 的设计模式，提供标准化的 Agent 开发框架。

版本：v1.0
创建日期：2026-06-17
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent 配置"""
    
    agent_id: str = "default"
    agent_type: str = "generic"
    version: str = "1.0.0"
    
    # 训练配置
    learning_rate: float = 1e-4
    batch_size: int = 64
    max_steps: int = 10000
    
    # 评估配置
    eval_interval: int = 1000
    eval_episodes: int = 10
    
    # 保存配置
    save_dir: str = "models/agent"
    save_interval: int = 5000
    
    # 自定义参数
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """Agent 状态"""
    
    # 当前观察
    observation: Any = None
    
    # 内部状态
    step: int = 0
    episode: int = 0
    
    # 统计信息
    total_reward: float = 0.0
    episode_reward: float = 0.0
    episode_length: int = 0
    
    # 训练状态
    is_training: bool = False
    is_exploring: bool = True
    
    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AgentResult:
    """Agent 结果"""
    
    # 动作
    action: Any = None
    action_type: str = "continuous"  # continuous, discrete
    
    # 信号
    signal: str = "NEUTRAL"  # LONG, SHORT, NEUTRAL
    strength: float = 0.0  # 0-1
    confidence: float = 0.0  # 0-1
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 时间戳
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AgentBase(ABC):
    """
    Agent 基类
    
    定义统一的 Agent 生命周期，所有 Agent 必须实现以下方法：
    
    1. perceive: 感知环境状态
       - 输入：环境原始状态
       - 输出：处理后的内部状态
    
    2. reason: 基于状态做出决策
       - 输入：内部状态
       - 输出：决策结果（动作/信号）
    
    3. act: 执行动作（可选）
       - 输入：决策结果
       - 输出：执行结果
    
    4. reflect: 评估结果，更新策略
       - 输入：执行结果
       - 输出：更新统计信息
    
    使用方式：
        class MyAgent(AgentBase):
            def perceive(self, raw_state):
                # 处理环境状态
                return processed_state
            
            def reason(self, state):
                # 选择动作
                return AgentResult(action=action, signal="LONG")
            
            def act(self, result):
                # 执行动作（可选）
                return execution_result
            
            def reflect(self, result, execution_result):
                # 更新策略
                return metrics
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """
        初始化 Agent
        
        Args:
            config: Agent 配置
        """
        self.config = config or AgentConfig()
        self.state = AgentState()
        
        # 统计信息
        self.metrics = {
            "total_steps": 0,
            "total_episodes": 0,
            "avg_reward": 0.0,
            "best_reward": -float("inf"),
        }
        
        logger.info(f"Agent 初始化: {self.config.agent_id} ({self.config.agent_type})")
    
    @abstractmethod
    def perceive(self, raw_state: Any) -> Any:
        """
        感知：从环境中获取信息并处理
        
        Args:
            raw_state: 环境原始状态
        
        Returns:
            处理后的内部状态
        """
        pass
    
    @abstractmethod
    def reason(self, state: Any) -> AgentResult:
        """
        推理：基于状态做出决策
        
        Args:
            state: 内部状态
        
        Returns:
            决策结果
        """
        pass
    
    def act(self, result: AgentResult) -> Any:
        """
        行动：执行动作（可选，子类可重写）
        
        Args:
            result: 决策结果
        
        Returns:
            执行结果
        """
        # 默认实现：直接返回结果
        return result
    
    def reflect(self, result: AgentResult, execution_result: Any = None) -> Dict[str, Any]:
        """
        反思：评估结果，更新策略（可选，子类可重写）
        
        Args:
            result: 决策结果
            execution_result: 执行结果
        
        Returns:
            更新统计信息
        """
        # 默认实现：更新步骤计数
        self.state.step += 1
        self.state.updated_at = datetime.now().isoformat()
        
        return {
            "step": self.state.step,
            "action": result.action,
            "signal": result.signal,
        }
    
    def run(self, raw_state: Any) -> AgentResult:
        """
        完整流程：感知→推理→行动→反思
        
        Args:
            raw_state: 环境原始状态
        
        Returns:
            决策结果
        """
        # 1. 感知
        state = self.perceive(raw_state)
        self.state.observation = state
        
        # 2. 推理
        result = self.reason(state)
        
        # 3. 行动
        execution_result = self.act(result)
        
        # 4. 反思
        self.reflect(result, execution_result)
        
        return result
    
    def train(self, experiences: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        训练：基于经验更新策略（可选，子类可重写）
        
        Args:
            experiences: 经验列表
        
        Returns:
            训练指标
        """
        # 默认实现：返回空指标
        return {"loss": 0.0}
    
    def evaluate(self, episodes: int = 10) -> Dict[str, float]:
        """
        评估：运行多个 episode 计算平均性能（可选，子类可重写）
        
        Args:
            episodes: 评估 episode 数
        
        Returns:
            评估指标
        """
        # 默认实现：返回空指标
        return {"avg_reward": 0.0, "avg_length": 0.0}
    
    def save(self, path: str):
        """
        保存模型（可选，子类可重写）
        
        Args:
            path: 保存路径
        """
        logger.info(f"Agent 保存到: {path}")
    
    def load(self, path: str):
        """
        加载模型（可选，子类可重写）
        
        Args:
            path: 加载路径
        """
        logger.info(f"Agent 从 {path} 加载")
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.metrics,
            "state": {
                "step": self.state.step,
                "episode": self.state.episode,
                "total_reward": self.state.total_reward,
                "is_training": self.state.is_training,
            },
        }
    
    def reset(self):
        """重置 Agent 状态"""
        self.state = AgentState()
        logger.debug(f"Agent 状态已重置: {self.config.agent_id}")


# 便捷类型定义
Agent = AgentBase
