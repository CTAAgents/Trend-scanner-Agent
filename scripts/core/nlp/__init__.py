"""
自然语言处理模块

实现自然语言交互：
- 意图识别
- 命令解析
- 上下文管理
- 响应生成
"""

from .intent_recognizer import IntentRecognizer, Intent
from .command_parser import CommandParser
from .context_manager import ContextManager
from .response_generator import ResponseGenerator
from .nlp_engine import NLPEngine

__all__ = [
    "IntentRecognizer",
    "Intent",
    "CommandParser",
    "ContextManager",
    "ResponseGenerator",
    "NLPEngine",
]
