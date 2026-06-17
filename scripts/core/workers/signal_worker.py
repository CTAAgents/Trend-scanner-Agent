"""
信号扫描 Worker

实现独立的信号扫描进程：
- 市场信号检测
- 信号强度评估
- 信号触发处理
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SignalScanWorker:
    """信号扫描 Worker"""

    def __init__(self):
        self.running = False
        self.last_scan_time: Optional[datetime] = None

    async def start(self):
        """启动 Worker"""
        self.running = True
        logger.info("信号扫描 Worker 启动")
        asyncio.create_task(self._scan_loop())

    async def stop(self):
        """停止 Worker"""
        self.running = False
        logger.info("信号扫描 Worker 停止")

    async def _scan_loop(self):
        """扫描循环"""
        while self.running:
            try:
                if self._needs_scan():
                    await self._scan_signals()
                await self._smart_sleep()
            except Exception as e:
                logger.error(f"信号扫描异常: {e}")
                await asyncio.sleep(60)

    def _needs_scan(self) -> bool:
        if self.last_scan_time is None:
            return True
        now = datetime.now()
        if not self._is_trading_time(now):
            return False
        elapsed = (now - self.last_scan_time).total_seconds()
        return elapsed > 60  # 1分钟

    async def _scan_signals(self):
        logger.info("开始扫描信号")
        try:
            # TODO: 实现实际的信号扫描逻辑
            self.last_scan_time = datetime.now()
            logger.info("信号扫描完成")
        except Exception as e:
            logger.error(f"信号扫描失败: {e}")

    def _is_trading_time(self, now) -> bool:
        hour = now.hour
        weekday = now.weekday()
        if weekday >= 5:
            return False
        return (9 <= hour < 11 or 13 <= hour < 15 or 21 <= hour < 23)

    async def _smart_sleep(self):
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()
        if weekday >= 5:
            await asyncio.sleep(3600)
        elif self._is_trading_time(now):
            await asyncio.sleep(0.1)
        else:
            await asyncio.sleep(300)

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
        }
