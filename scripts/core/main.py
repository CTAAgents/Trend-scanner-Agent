"""
主进程管理器

实现系统独立运行的核心：
- 主进程启动
- Worker 进程管理
- 资源监控
- 智能休眠
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from core.event_engine import EventDrivenEngine, IntelligentScheduler, ResourceMonitor
from core.memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class MainProcess:
    """主进程管理器"""

    def __init__(self):
        # 核心组件
        self.event_engine = EventDrivenEngine()
        self.scheduler = IntelligentScheduler()
        self.resource_monitor = ResourceMonitor()
        self.memory_manager = MemoryManager(max_memory_mb=200)

        # 状态
        self.running = False
        self.workers: Dict[str, Any] = {}

    async def start(self):
        """启动主进程"""
        logger.info("启动 Trend Scanner Agent 主进程")

        # 设置信号处理
        self._setup_signal_handlers()

        # 启动核心组件
        await self.event_engine.start()
        await self.scheduler.start()

        self.running = True
        logger.info("主进程启动完成")

        # 进入主循环
        await self._main_loop()

    async def stop(self):
        """停止主进程"""
        logger.info("停止主进程")

        self.running = False

        # 停止核心组件
        await self.event_engine.stop()

        # 清理资源
        self.memory_manager.optimize_memory()

        logger.info("主进程已停止")

    def _setup_signal_handlers(self):
        """设置信号处理"""
        def signal_handler(sig, frame):
            logger.info(f"收到信号 {sig}，准备停止...")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _main_loop(self):
        """主循环"""
        while self.running:
            try:
                # 检查资源状态
                if not self.resource_monitor.has_enough_resources():
                    logger.warning("资源不足，进入休眠模式")
                    await self._sleep_mode()
                    continue

                # 优化内存
                if not self.memory_manager.is_memory_available():
                    self.memory_manager.optimize_memory()

                # 检查是否有任务需要执行
                await self._check_pending_tasks()

                # 智能休眠
                await self._smart_sleep()

            except Exception as e:
                logger.error(f"主循环异常: {e}")
                await asyncio.sleep(1)

    async def _sleep_mode(self):
        """休眠模式"""
        logger.info("进入休眠模式，等待资源恢复")
        while not self.resource_monitor.has_enough_resources():
            await asyncio.sleep(60)  # 每分钟检查一次

    async def _check_pending_tasks(self):
        """检查待执行任务"""
        # TODO: 实现任务检查逻辑
        pass

    async def _smart_sleep(self):
        """智能休眠"""
        now = __import__('datetime').datetime.now()
        hour = now.hour
        weekday = now.weekday()

        if weekday >= 5:
            # 周末：1小时
            await asyncio.sleep(3600)
        elif self._is_trading_time(now):
            # 交易时间：100ms
            await asyncio.sleep(0.1)
        else:
            # 非交易时间：5分钟
            await asyncio.sleep(300)

    def _is_trading_time(self, now) -> bool:
        """判断是否为交易时间"""
        hour = now.hour
        # 期货交易时间：9:00-11:30, 13:30-15:00, 21:00-23:00
        return (9 <= hour < 11 or 13 <= hour < 15 or 21 <= hour < 23)

    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "running": self.running,
            "event_engine": self.event_engine.get_status(),
            "scheduler": self.scheduler.get_status(),
            "resource_monitor": self.resource_monitor.get_status_dict(),
            "memory_manager": self.memory_manager.get_status(),
        }


async def main():
    """主入口"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建并启动主进程
    process = MainProcess()

    try:
        await process.start()
    except KeyboardInterrupt:
        await process.stop()


if __name__ == "__main__":
    asyncio.run(main())
