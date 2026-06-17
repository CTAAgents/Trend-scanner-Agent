"""
事件驱动引擎

实现事件驱动的系统自动运行架构：
- 事件类型定义
- 事件队列管理
- 事件处理器注册
- 异步事件处理
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型"""
    DATA_UPDATE = "data_update"
    SIGNAL = "signal"
    FACTOR_EVOLUTION = "factor_evolution"
    STRATEGY_GENERATION = "strategy_generation"
    SYSTEM_HEALTH = "system_health"
    CUSTOM = "custom"


@dataclass
class Event:
    """事件基类"""
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # 0-10，数字越大优先级越高


@dataclass
class DataUpdateEvent(Event):
    """数据更新事件"""
    symbol: str = ""
    data_type: str = "kline"

    def __post_init__(self):
        self.event_type = EventType.DATA_UPDATE


@dataclass
class SignalEvent(Event):
    """信号触发事件"""
    signal_type: str = ""
    signal_strength: float = 0.0

    def __post_init__(self):
        self.event_type = EventType.SIGNAL


@dataclass
class FactorEvolutionEvent(Event):
    """因子进化事件"""
    evolution_rounds: int = 1

    def __post_init__(self):
        self.event_type = EventType.FACTOR_EVOLUTION


@dataclass
class StrategyGenerationEvent(Event):
    """策略生成事件"""
    strategy_type: str = ""

    def __post_init__(self):
        self.event_type = EventType.STRATEGY_GENERATION


class EventHandler(ABC):
    """事件处理器基类"""

    @abstractmethod
    async def handle(self, event: Event) -> Any:
        """处理事件"""
        pass

    @abstractmethod
    def can_handle(self, event: Event) -> bool:
        """判断是否能处理该事件"""
        pass


class EventDrivenEngine:
    """事件驱动引擎"""

    def __init__(self):
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.handlers: Dict[EventType, List[EventHandler]] = {}
        self.running = False
        self._tasks: List[asyncio.Task] = []
        self._event_history: List[Event] = []

    def register_handler(self, event_type: EventType, handler: EventHandler):
        """注册事件处理器"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        logger.info(f"注册事件处理器: {event_type.value} -> {handler.__class__.__name__}")

    async def start(self):
        """启动引擎"""
        if self.running:
            logger.warning("引擎已在运行")
            return

        self.running = True
        logger.info("事件驱动引擎启动")

        # 启动事件处理任务
        self._tasks.append(asyncio.create_task(self._process_events()))

        # 启动市场监控任务
        self._tasks.append(asyncio.create_task(self._monitor_market_state()))

    async def stop(self):
        """停止引擎"""
        self.running = False
        logger.info("事件驱动引擎停止")

        # 取消所有任务
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    async def emit(self, event: Event):
        """发射事件"""
        await self.event_queue.put(event)
        self._event_history.append(event)
        logger.debug(f"发射事件: {event.event_type.value}")

    async def _process_events(self):
        """处理事件"""
        while self.running:
            try:
                event = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=1.0
                )
                await self._handle_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"处理事件异常: {e}")

    async def _handle_event(self, event: Event):
        """处理单个事件"""
        handlers = self.handlers.get(event.event_type, [])

        for handler in handlers:
            if handler.can_handle(event):
                try:
                    await handler.handle(event)
                except Exception as e:
                    logger.error(f"处理器异常: {e}")

    async def _monitor_market_state(self):
        """监控市场状态"""
        while self.running:
            try:
                # 检查是否在交易时间
                if self._is_trading_time():
                    # 检查数据是否更新
                    if self._data_needs_update():
                        await self.emit(DataUpdateEvent())

                    # 检查是否有信号触发
                    if self._signal_triggered():
                        await self.emit(SignalEvent())

                # 智能休眠
                await self._smart_sleep()

            except Exception as e:
                logger.error(f"市场监控异常: {e}")

    def _is_trading_time(self) -> bool:
        """判断是否为交易时间"""
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()

        # 周末不交易
        if weekday >= 5:
            return False

        # 期货交易时间：9:00-11:30, 13:30-15:00, 21:00-23:00
        return (9 <= hour < 11 or 13 <= hour < 15 or 21 <= hour < 23)

    def _data_needs_update(self) -> bool:
        """检查数据是否需要更新"""
        # TODO: 实现数据更新检测逻辑
        return False

    def _signal_triggered(self) -> bool:
        """检查是否触发信号"""
        # TODO: 实现信号触发检测逻辑
        return False

    async def _smart_sleep(self):
        """智能休眠"""
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()

        if weekday >= 5:
            # 周末：1小时
            await asyncio.sleep(3600)
        elif self._is_trading_time():
            # 交易时间：100ms
            await asyncio.sleep(0.1)
        else:
            # 非交易时间：5分钟
            await asyncio.sleep(300)

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        return {
            "running": self.running,
            "queue_size": self.event_queue.qsize(),
            "handlers_count": sum(len(h) for h in self.handlers.values()),
            "event_history_size": len(self._event_history),
            "tasks_count": len(self._tasks),
        }
