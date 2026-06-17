"""
上下文管理器

管理对话上下文：
- 对话历史
- 用户偏好
- 上下文状态
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ConversationTurn:
    """对话轮次"""
    user_input: str
    system_response: str
    timestamp: datetime
    intent: Optional[str] = None


class ContextManager:
    """上下文管理器"""

    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.history: List[ConversationTurn] = []
        self.user_preferences: Dict[str, Any] = {}
        self.current_context: Dict[str, Any] = {}

    def add_turn(self, user_input: str, system_response: str, intent: Optional[str] = None):
        """添加对话轮次"""
        turn = ConversationTurn(
            user_input=user_input,
            system_response=system_response,
            timestamp=datetime.now(),
            intent=intent,
        )
        self.history.append(turn)

        # 限制历史长度
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_recent_context(self, n: int = 3) -> List[ConversationTurn]:
        """获取最近的对话上下文"""
        return self.history[-n:]

    def set_preference(self, key: str, value: Any):
        """设置用户偏好"""
        self.user_preferences[key] = value

    def get_preference(self, key: str, default: Any = None) -> Any:
        """获取用户偏好"""
        return self.user_preferences.get(key, default)

    def update_context(self, key: str, value: Any):
        """更新当前上下文"""
        self.current_context[key] = value

    def get_context(self, key: str = None) -> Any:
        """获取当前上下文"""
        if key is None:
            return self.current_context
        return self.current_context.get(key)

    def clear_context(self):
        """清空当前上下文"""
        self.current_context.clear()

    def get_summary(self) -> str:
        """获取对话摘要"""
        if not self.history:
            return "暂无对话历史"

        recent = self.get_recent_context(3)
        lines = ["最近对话："]
        for turn in recent:
            lines.append(f"  用户: {turn.user_input[:50]}...")
            lines.append(f"  系统: {turn.system_response[:50]}...")
        return "\n".join(lines)
