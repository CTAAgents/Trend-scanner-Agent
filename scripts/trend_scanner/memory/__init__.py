"""
自优化记忆系统模块

提供统一的记忆管理接口，整合 SQLite + DuckDB + 可配置 LLM。

核心组件：
- UnifiedMemoryManager: 统一记忆管理器（唯一入口）
- SQLiteStore: SQLite 事务型存储
- DuckDBStore: DuckDB 分析型存储
- VectorStore: 向量存储
- LLMProviderFactory: LLM 提供者工厂

使用方式：
    from trend_scanner.memory import UnifiedMemoryManager
    
    config = {
        "sqlite_path": "data/memory.db",
        "duckdb_path": "data/analytics.duckdb",
        "llm": {"provider": "workbuddy"}
    }
    memory = UnifiedMemoryManager(config)
"""

from .manager import UnifiedMemoryManager
from .sqlite_store import SQLiteStore
from .duckdb_store import DuckDBStore
from .vector_store import VectorStore
from .llm_factory import LLMProviderFactory, LLMProvider

__all__ = [
    'UnifiedMemoryManager',
    'SQLiteStore',
    'DuckDBStore',
    'VectorStore',
    'LLMProviderFactory',
    'LLMProvider'
]
