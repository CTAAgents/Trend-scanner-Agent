"""
审计轨迹系统

基于 TradeArena 和 Representation Signatures 论文的思想：
- 记录完整决策周期：观察→规划→风险→行动→反思
- 支持轨迹重放和验证
- 提供可审计性

核心设计原则：
- 审计优先：每个决策步骤都有完整记录
- 可验证性：轨迹哈希验证
- 可重放性：支持事后重放决策过程
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Observation:
    """观察记录"""
    timestamp: str
    market_data: Dict[str, Any]
    indicators: Dict[str, Any]
    context: str = ""


@dataclass
class Planning:
    """规划记录"""
    timestamp: str
    reasoning: str
    signal: str  # BUY/SELL/HOLD
    confidence: float
    target_weights: Dict[str, float] = field(default_factory=dict)


@dataclass
class RiskReview:
    """风险审查记录"""
    timestamp: str
    risk_checks: List[Dict[str, Any]]
    risk_decision: str  # APPROVED/REJECTED/MODIFIED
    risk_notes: str = ""


@dataclass
class Action:
    """行动记录"""
    timestamp: str
    orders: List[Dict[str, Any]]
    execution_mode: str  # REALISTIC/SIMULATED
    slippage: float = 0.0
    commission: float = 0.0


@dataclass
class Reflection:
    """反思记录"""
    timestamp: str
    outcome: str  # PROFIT/LOSS/NEUTRAL
    pnl: float = 0.0
    lessons: str = ""


@dataclass
class AuditRecord:
    """审计记录"""
    record_id: str
    symbol: str
    start_time: str
    end_time: str
    
    observation: Observation
    planning: Planning
    risk_review: RiskReview
    action: Action
    reflection: Reflection
    
    # 元数据
    model_version: str = ""
    prompt_version: str = ""
    data_timestamp: str = ""
    
    # 验证
    content_hash: str = ""
    
    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "symbol": self.symbol,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "observation": asdict(self.observation),
            "planning": asdict(self.planning),
            "risk_review": asdict(self.risk_review),
            "action": asdict(self.action),
            "reflection": asdict(self.reflection),
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "data_timestamp": self.data_timestamp,
            "content_hash": self.content_hash,
        }
    
    def compute_hash(self) -> str:
        """计算内容哈希"""
        content = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()


class AuditTrail:
    """
    审计轨迹系统
    
    记录完整决策周期，支持重放和验证
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        初始化审计轨迹系统
        
        Args:
            storage_path: 存储路径（可选）
        """
        self.storage_path = storage_path
        self.records: List[AuditRecord] = []
    
    def record(self, record: AuditRecord) -> str:
        """
        记录审计轨迹
        
        Args:
            record: 审计记录
            
        Returns:
            record_id: 记录ID
        """
        # 计算内容哈希
        record.content_hash = record.compute_hash()
        
        # 存储记录
        self.records.append(record)
        
        # 持久化（如果配置了存储路径）
        if self.storage_path:
            self._persist(record)
        
        logger.info(f"审计记录已存储: {record.record_id}")
        return record.record_id
    
    def replay(self, record_id: str) -> Optional[AuditRecord]:
        """
        重放审计轨迹
        
        Args:
            record_id: 记录ID
            
        Returns:
            AuditRecord: 审计记录（如果找到）
        """
        for record in self.records:
            if record.record_id == record_id:
                return record
        
        logger.warning(f"未找到审计记录: {record_id}")
        return None
    
    def verify(self, record: AuditRecord) -> bool:
        """
        验证审计记录完整性
        
        Args:
            record: 审计记录
            
        Returns:
            bool: 验证是否通过
        """
        # 保存原始哈希
        stored_hash = record.content_hash
        
        # 临时清空哈希以重新计算
        record.content_hash = ""
        computed_hash = record.compute_hash()
        
        # 恢复原始哈希
        record.content_hash = stored_hash
        
        return stored_hash == computed_hash
    
    def get_timeline(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        获取决策时间线
        
        Args:
            record_id: 记录ID
            
        Returns:
            Dict: 决策时间线
        """
        record = self.replay(record_id)
        if record is None:
            return None
        
        return {
            "record_id": record.record_id,
            "symbol": record.symbol,
            "timeline": [
                {"phase": "observation", "time": record.observation.timestamp, "data": record.observation.context},
                {"phase": "planning", "time": record.planning.timestamp, "signal": record.planning.signal, "confidence": record.planning.confidence},
                {"phase": "risk_review", "time": record.risk_review.timestamp, "decision": record.risk_review.risk_decision},
                {"phase": "action", "time": record.action.timestamp, "orders": len(record.action.orders)},
                {"phase": "reflection", "time": record.reflection.timestamp, "outcome": record.reflection.outcome},
            ],
            "content_hash": record.content_hash,
        }
    
    def _persist(self, record: AuditRecord):
        """持久化记录"""
        # 简化实现：JSON文件存储
        if self.storage_path:
            import os
            os.makedirs(self.storage_path, exist_ok=True)
            filepath = os.path.join(self.storage_path, f"{record.record_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)


class AuditTrailBuilder:
    """审计记录构建器"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.observation = None
        self.planning = None
        self.risk_review = None
        self.action = None
        self.reflection = None
    
    def set_observation(self, market_data: Dict, indicators: Dict, context: str = "") -> "AuditTrailBuilder":
        self.observation = Observation(
            timestamp=datetime.now().isoformat(),
            market_data=market_data,
            indicators=indicators,
            context=context,
        )
        return self
    
    def set_planning(self, reasoning: str, signal: str, confidence: float, target_weights: Dict = None) -> "AuditTrailBuilder":
        self.planning = Planning(
            timestamp=datetime.now().isoformat(),
            reasoning=reasoning,
            signal=signal,
            confidence=confidence,
            target_weights=target_weights or {},
        )
        return self
    
    def set_risk_review(self, risk_checks: List[Dict], decision: str, notes: str = "") -> "AuditTrailBuilder":
        self.risk_review = RiskReview(
            timestamp=datetime.now().isoformat(),
            risk_checks=risk_checks,
            risk_decision=decision,
            risk_notes=notes,
        )
        return self
    
    def set_action(self, orders: List[Dict], mode: str = "SIMULATED", slippage: float = 0, commission: float = 0) -> "AuditTrailBuilder":
        self.action = Action(
            timestamp=datetime.now().isoformat(),
            orders=orders,
            execution_mode=mode,
            slippage=slippage,
            commission=commission,
        )
        return self
    
    def set_reflection(self, outcome: str, pnl: float = 0, lessons: str = "") -> "AuditTrailBuilder":
        self.reflection = Reflection(
            timestamp=datetime.now().isoformat(),
            outcome=outcome,
            pnl=pnl,
            lessons=lessons,
        )
        return self
    
    def build(self) -> AuditRecord:
        """构建审计记录"""
        import uuid
        
        if not all([self.observation, self.planning, self.risk_review, self.action, self.reflection]):
            raise ValueError("所有阶段必须设置完整")
        
        record_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        return AuditRecord(
            record_id=record_id,
            symbol=self.symbol,
            start_time=self.observation.timestamp,
            end_time=self.reflection.timestamp,
            observation=self.observation,
            planning=self.planning,
            risk_review=self.risk_review,
            action=self.action,
            reflection=self.reflection,
        )
