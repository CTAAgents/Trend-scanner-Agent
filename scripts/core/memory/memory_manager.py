"""
内存管理器

实现智能内存管理：
- 内存使用监控
- 缓存管理
- 内存优化
- LRU 缓存
"""

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    timestamp: float
    access_count: int = 0


class LRUCache:
    """LRU 缓存"""

    def __init__(self, maxsize: int = 1000):
        self.maxsize = maxsize
        self.cache: OrderedDict = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key in self.cache:
            # 移到末尾（最近使用）
            self.cache.move_to_end(key)
            self.cache[key].access_count += 1
            return self.cache[key].value
        return None

    def put(self, key: str, value: Any):
        """设置缓存值"""
        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key].value = value
            self.cache[key].timestamp = time.time()
        else:
            if len(self.cache) >= self.maxsize:
                # 删除最久未使用的
                self.cache.popitem(last=False)
            self.cache[key] = CacheEntry(
                value=value,
                timestamp=time.time(),
            )

    def remove(self, key: str):
        """删除缓存"""
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)


class MemoryManager:
    """内存管理器"""

    def __init__(self, max_memory_mb: int = 200):
        self.max_memory_mb = max_memory_mb
        self.cache = LRUCache(maxsize=1000)
        self._data_store: Dict[str, Any] = {}

    def get_memory_usage(self) -> Dict[str, float]:
        """获取内存使用情况"""
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
        }

    def is_memory_available(self) -> bool:
        """检查是否有足够内存"""
        usage = self.get_memory_usage()
        return usage["rss_mb"] < self.max_memory_mb

    def optimize_memory(self):
        """优化内存使用"""
        # 1. 清理过期缓存
        self._cleanup_expired_cache()

        # 2. 清理空闲数据
        self._cleanup_idle_data()

        logger.info(f"内存优化完成，当前使用: {self.get_memory_usage()['rss_mb']:.1f}MB")

    def _cleanup_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []

        for key, entry in self.cache.cache.items():
            if current_time - entry.timestamp > 3600:  # 1小时过期
                expired_keys.append(key)

        for key in expired_keys:
            self.cache.remove(key)

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存")

    def _cleanup_idle_data(self):
        """清理空闲数据"""
        # 清理空字典和空列表
        keys_to_remove = [
            k for k, v in self._data_store.items()
            if v is None or (isinstance(v, (dict, list)) and len(v) == 0)
        ]

        for key in keys_to_remove:
            del self._data_store[key]

        if keys_to_remove:
            logger.info(f"清理了 {len(keys_to_remove)} 个空闲数据")

    def set(self, key: str, value: Any, use_cache: bool = True):
        """设置数据"""
        if use_cache:
            self.cache.put(key, value)
        else:
            self._data_store[key] = value

    def get(self, key: str) -> Optional[Any]:
        """获取数据"""
        # 先从缓存获取
        value = self.cache.get(key)
        if value is not None:
            return value

        # 再从数据存储获取
        return self._data_store.get(key)

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "memory_usage": self.get_memory_usage(),
            "cache_size": self.cache.size(),
            "data_store_size": len(self._data_store),
            "max_memory_mb": self.max_memory_mb,
        }
