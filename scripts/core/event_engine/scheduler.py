"""
智能调度器

实现任务的智能调度：
- 任务优先级管理
- 资源监控
- 执行时机判断
- 任务队列管理
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 10  # 关键任务
    HIGH = 8       # 高优先级
    MEDIUM = 5     # 中优先级
    LOW = 3        # 低优先级
    BACKGROUND = 1 # 后台任务


@dataclass
class Task:
    """任务定义"""
    task_id: str
    name: str
    priority: TaskPriority
    execute_func: Callable
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    last_run: Optional[datetime] = None
    min_interval: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    timeout: int = 300  # 超时时间（秒）


class IntelligentScheduler:
    """智能调度器"""

    def __init__(self):
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.tasks: Dict[str, Task] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.resource_monitor = None  # 由外部注入

    def set_resource_monitor(self, monitor):
        """设置资源监控器"""
        self.resource_monitor = monitor

    def register_task(self, task: Task):
        """注册任务"""
        self.tasks[task.task_id] = task
        logger.info(f"注册任务: {task.name} (优先级: {task.priority.name})")

    async def submit_task(self, task_id: str):
        """提交任务到队列"""
        if task_id not in self.tasks:
            logger.error(f"任务不存在: {task_id}")
            return

        task = self.tasks[task_id]

        # 检查是否应该执行
        if not await self.should_execute(task):
            logger.debug(f"任务 {task.name} 不满足执行条件")
            return

        # 添加到队列（使用负优先级，因为 PriorityQueue 是最小堆）
        await self.task_queue.put((-task.priority.value, task))

    async def should_execute(self, task: Task) -> bool:
        """判断任务是否应该执行"""
        # 检查资源状态
        if self.resource_monitor and not self.resource_monitor.has_enough_resources():
            return False

        # 检查执行间隔
        if task.last_run:
            elapsed = datetime.now() - task.last_run
            if elapsed < task.min_interval:
                return False

        # 检查是否已在运行
        if task.task_id in self.running_tasks:
            if not self.running_tasks[task.task_id].done():
                return False

        return True

    async def start(self):
        """启动调度器"""
        asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        """处理任务队列"""
        while True:
            try:
                # 获取任务
                priority, task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )

                # 执行任务
                await self._execute_task(task)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"处理任务队列异常: {e}")

    async def _execute_task(self, task: Task):
        """执行任务"""
        logger.info(f"执行任务: {task.name}")

        try:
            # 创建异步任务
            async_task = asyncio.create_task(
                self._run_task_with_timeout(task)
            )
            self.running_tasks[task.task_id] = async_task

            # 等待完成
            await async_task

            # 更新最后运行时间
            task.last_run = datetime.now()

        except Exception as e:
            logger.error(f"执行任务失败: {task.name}, 错误: {e}")
        finally:
            # 清理
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]

    async def _run_task_with_timeout(self, task: Task):
        """带超时的任务执行"""
        try:
            await asyncio.wait_for(
                task.execute_func(*task.args, **task.kwargs),
                timeout=task.timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"任务超时: {task.name}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            "registered_tasks": len(self.tasks),
            "queue_size": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "tasks": {
                task_id: {
                    "name": task.name,
                    "priority": task.priority.name,
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                }
                for task_id, task in self.tasks.items()
            },
        }
