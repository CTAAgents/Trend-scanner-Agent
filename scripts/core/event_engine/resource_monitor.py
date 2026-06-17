"""
资源监控器

监控系统资源使用情况：
- CPU 使用率
- 内存使用率
- 磁盘使用率
- 网络状态
"""

import asyncio
import logging
import psutil
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class ResourceStatus:
    """资源状态"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    network_active: bool


class ResourceMonitor:
    """资源监控器"""

    def __init__(
        self,
        max_cpu_percent: float = 80.0,
        max_memory_percent: float = 80.0,
        max_disk_percent: float = 90.0,
    ):
        self.max_cpu_percent = max_cpu_percent
        self.max_memory_percent = max_memory_percent
        self.max_disk_percent = max_disk_percent
        self._status: ResourceStatus = None

    def get_status(self) -> ResourceStatus:
        """获取当前资源状态"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net_io = psutil.net_io_counters()

        self._status = ResourceStatus(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / 1024 / 1024,
            memory_total_mb=memory.total / 1024 / 1024,
            disk_percent=disk.percent,
            network_active=net_io.bytes_sent > 0 or net_io.bytes_recv > 0,
        )

        return self._status

    def has_enough_resources(self) -> bool:
        """检查是否有足够资源"""
        status = self.get_status()

        if status.cpu_percent > self.max_cpu_percent:
            logger.warning(f"CPU 使用率过高: {status.cpu_percent:.1f}%")
            return False

        if status.memory_percent > self.max_memory_percent:
            logger.warning(f"内存使用率过高: {status.memory_percent:.1f}%")
            return False

        if status.disk_percent > self.max_disk_percent:
            logger.warning(f"磁盘使用率过高: {status.disk_percent:.1f}%")
            return False

        return True

    def get_status_dict(self) -> Dict[str, Any]:
        """获取资源状态字典"""
        status = self.get_status()
        return {
            "cpu_percent": status.cpu_percent,
            "memory_percent": status.memory_percent,
            "memory_used_mb": status.memory_used_mb,
            "memory_total_mb": status.memory_total_mb,
            "disk_percent": status.disk_percent,
            "network_active": status.network_active,
        }
