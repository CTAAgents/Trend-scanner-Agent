"""
数据层模块

提供数据获取、存储和管理功能：
- 数据源适配器（TqSdk, CSV, Pytdx）
- 数据存储（DuckDB, SQLite）
- 统一数据路由
"""

from .sources import DataSource, DataSourceFactory
from .storage import DuckDBStore, SQLiteStore, DataSyncManager
from .router import UnifiedDataRouter, get_router

__all__ = [
    "DataSource",
    "DataSourceFactory",
    "DuckDBStore",
    "SQLiteStore",
    "DataSyncManager",
    "UnifiedDataRouter",
    "get_router",
]
