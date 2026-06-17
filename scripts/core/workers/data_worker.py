"""
数据同步 Worker

实现独立的数据同步进程：
- K线数据同步
- 指标数据计算
- 数据质量检查
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DataSyncWorker:
    """数据同步 Worker"""

    def __init__(self):
        self.running = False
        self.last_sync_time: Optional[datetime] = None

    async def start(self):
        """启动 Worker"""
        self.running = True
        logger.info("数据同步 Worker 启动")

        # 启动同步循环
        asyncio.create_task(self._sync_loop())

    async def stop(self):
        """停止 Worker"""
        self.running = False
        logger.info("数据同步 Worker 停止")

    async def _sync_loop(self):
        """同步循环"""
        while self.running:
            try:
                # 检查是否需要同步
                if self._needs_sync():
                    await self._sync_data()

                # 智能休眠
                await self._smart_sleep()

            except Exception as e:
                logger.error(f"数据同步异常: {e}")
                await asyncio.sleep(60)

    def _needs_sync(self) -> bool:
        """检查是否需要同步"""
        if self.last_sync_time is None:
            return True

        # 检查是否在交易时间
        now = datetime.now()
        if not self._is_trading_time(now):
            return False

        # 检查同步间隔
        elapsed = (now - self.last_sync_time).total_seconds()
        return elapsed > 300  # 5分钟

    async def _sync_data(self):
        """同步数据"""
        logger.info("开始同步数据")

        try:
            # TODO: 实现实际的数据同步逻辑
            # 1. 调用 sync_data.py
            # 2. 调用 sync_indicators.py
            # 3. 验证数据质量

            self.last_sync_time = datetime.now()
            logger.info("数据同步完成")

        except Exception as e:
            logger.error(f"数据同步失败: {e}")

    def _is_trading_time(self, now) -> bool:
        """判断是否为交易时间"""
        hour = now.hour
        weekday = now.weekday()

        if weekday >= 5:
            return False

        return (9 <= hour < 11 or 13 <= hour < 15 or 21 <= hour < 23)

    async def _smart_sleep(self):
        """智能休眠"""
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()

        if weekday >= 5:
            await asyncio.sleep(3600)
        elif self._is_trading_time(now):
            await asyncio.sleep(0.5)
        else:
            await asyncio.sleep(300)

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "running": self.running,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
        }
