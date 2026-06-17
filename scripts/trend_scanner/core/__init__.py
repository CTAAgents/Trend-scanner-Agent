"""
核心模块

提供系统的核心抽象和基础设施：
- AgentBase: 统一的 Agent 基类
- Config: 统一的配置管理
- 数据类型定义

版本：v1.0
创建日期：2026-06-17
"""

from .agent_base import AgentBase, AgentConfig, AgentState, AgentResult

__all__ = [
    "AgentBase",
    "AgentConfig",
    "AgentState",
    "AgentResult",
]
