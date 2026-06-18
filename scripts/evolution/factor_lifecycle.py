"""
因子生命周期管理

参考 SkillWiki 论文的八阶段生命周期模型，适配为因子场景。

生命周期状态（S0-S7）：
- S0 Raw        — LLM生成的原始因子想法
- S1 Candidate  — 通过语法检查和初步筛选的因子
- S2 Draft      — 有完整代码实现，可运行
- S3 Verified   — 通过 Walk-Forward 验证
- S4 Released   — 进入实盘观察期
- S5 Degraded   — 滚动夏普比低于阈值或最大回撤超标
- S6 Deprecated — 被新因子替代或永久失效
- S7 Archived   — 保留历史记录供参考

状态转换规则：
- 正向推进：S0→S1→S2→S3→S4
- 退化回退：S4→S5（自动检测）
- 维护修复：S5→S2（参数调整后重新验证）
- 归档：S5→S6→S7 或 S4→S6→S7
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class LifecycleState(str, Enum):
    """因子生命周期状态"""

    RAW = "S0_raw"
    CANDIDATE = "S1_candidate"
    DRAFT = "S2_draft"
    VERIFIED = "S3_verified"
    RELEASED = "S4_released"
    DEGRADED = "S5_degraded"
    DEPRECATED = "S6_deprecated"
    ARCHIVED = "S7_archived"


# 状态转换规则：定义每个状态可以转换到哪些状态
VALID_TRANSITIONS: dict[LifecycleState, list[LifecycleState]] = {
    LifecycleState.RAW: [LifecycleState.CANDIDATE],
    LifecycleState.CANDIDATE: [LifecycleState.DRAFT, LifecycleState.ARCHIVED],
    LifecycleState.DRAFT: [LifecycleState.VERIFIED, LifecycleState.CANDIDATE, LifecycleState.ARCHIVED],
    LifecycleState.VERIFIED: [LifecycleState.RELEASED, LifecycleState.DRAFT, LifecycleState.ARCHIVED],
    LifecycleState.RELEASED: [LifecycleState.DEGRADED, LifecycleState.DEPRECATED, LifecycleState.ARCHIVED],
    LifecycleState.DEGRADED: [
        LifecycleState.DRAFT,  # 维护修复后重新验证
        LifecycleState.DEPRECATED,
        LifecycleState.ARCHIVED,
    ],
    LifecycleState.DEPRECATED: [LifecycleState.ARCHIVED],
    LifecycleState.ARCHIVED: [],  # 终态，不可再转换
}

# 状态中文名称
STATE_NAMES: dict[LifecycleState, str] = {
    LifecycleState.RAW: "原始",
    LifecycleState.CANDIDATE: "候选",
    LifecycleState.DRAFT: "草案",
    LifecycleState.VERIFIED: "已验证",
    LifecycleState.RELEASED: "已发布",
    LifecycleState.DEGRADED: "退化",
    LifecycleState.DEPRECATED: "已弃用",
    LifecycleState.ARCHIVED: "已归档",
}

# 健康度阈值
HEALTH_THRESHOLDS = {
    "min_sharpe": 0.5,  # 最低滚动夏普比率
    "max_drawdown": 0.15,  # 最大回撤阈值
    "min_ic": 0.02,  # 最低IC值
    "degradation_window": 10,  # 退化检测窗口（交易日）
}


class InvalidTransitionError(Exception):
    """无效的状态转换"""

    pass


@dataclass
class StateTransition:
    """状态转换记录"""

    from_state: LifecycleState
    to_state: LifecycleState
    timestamp: str
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)
    approved_by: str = "system"  # system / reasoner / manual


@dataclass
class FactorAsset:
    """
    因子资产

    包含因子的完整生命周期信息，参考 SkillWiki 的统一技能表示。
    """

    # 基本信息
    id: str
    name: str
    code: str
    description: str = ""
    logic: str = ""
    category: str = ""  # momentum / volume / volatility / trend / composite

    # 生命周期
    lifecycle_state: LifecycleState = LifecycleState.RAW
    lifecycle_history: list[StateTransition] = field(default_factory=list)

    # 来源追溯
    source_type: str = ""  # paper / trajectory / document / manual
    source_ref: str = ""  # 论文URL、轨迹ID等
    inspired_by: list[str] = field(default_factory=list)  # 启发来源的因子ID列表
    evolved_from: list[str] = field(default_factory=list)  # 进化来源的因子ID列表

    # 评估指标
    evaluation: dict[str, Any] = field(default_factory=dict)
    health_metrics: dict[str, Any] = field(default_factory=dict)

    # 版本控制
    version: int = 1
    versions: list[dict[str, Any]] = field(default_factory=list)

    # 时间戳
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

    def can_transition_to(self, target_state: LifecycleState) -> bool:
        """检查是否可以转换到目标状态"""
        return target_state in VALID_TRANSITIONS.get(self.lifecycle_state, [])

    def transition(
        self,
        target_state: LifecycleState,
        reason: str,
        metrics: dict[str, Any] = None,
        approved_by: str = "system",
    ) -> StateTransition:
        """
        执行状态转换

        Args:
            target_state: 目标状态
            reason: 转换原因
            metrics: 转换时的评估指标
            approved_by: 审批者

        Returns:
            StateTransition 记录

        Raises:
            InvalidTransitionError: 如果转换无效
        """
        if not self.can_transition_to(target_state):
            current = STATE_NAMES[self.lifecycle_state]
            target = STATE_NAMES[target_state]
            valid_targets = [STATE_NAMES[s] for s in VALID_TRANSITIONS.get(self.lifecycle_state, [])]
            raise InvalidTransitionError(
                f"无效转换: {current} → {target}。"
                f"当前状态 {self.lifecycle_state.value} 可转换到: {valid_targets}"
            )

        transition = StateTransition(
            from_state=self.lifecycle_state,
            to_state=target_state,
            timestamp=datetime.now().isoformat(),
            reason=reason,
            metrics=metrics or {},
            approved_by=approved_by,
        )

        self.lifecycle_history.append(transition)
        self.lifecycle_state = target_state
        self.updated_at = datetime.now().isoformat()

        return transition

    def save_version_snapshot(self, description: str = ""):
        """保存当前版本快照"""
        snapshot = {
            "version": self.version,
            "lifecycle_state": self.lifecycle_state.value,
            "code": self.code,
            "evaluation": self.evaluation.copy(),
            "health_metrics": self.health_metrics.copy(),
            "description": description,
            "timestamp": datetime.now().isoformat(),
        }
        self.versions.append(snapshot)
        self.version += 1

    def check_health(self) -> dict[str, Any]:
        """
        检查因子健康度

        Returns:
            健康度报告
        """
        report = {
            "is_healthy": True,
            "issues": [],
            "metrics": {},
        }

        eval_data = self.evaluation

        # 检查夏普比率
        sharpe = eval_data.get("sharpe", eval_data.get("long_short_sharpe", 0))
        if sharpe < HEALTH_THRESHOLDS["min_sharpe"]:
            report["is_healthy"] = False
            report["issues"].append(f"夏普比率过低: {sharpe:.3f} < {HEALTH_THRESHOLDS['min_sharpe']}")
        report["metrics"]["sharpe"] = sharpe

        # 检查最大回撤
        max_dd = eval_data.get("max_drawdown", 0)
        if max_dd > HEALTH_THRESHOLDS["max_drawdown"]:
            report["is_healthy"] = False
            report["issues"].append(f"最大回撤过高: {max_dd:.3f} > {HEALTH_THRESHOLDS['max_drawdown']}")
        report["metrics"]["max_drawdown"] = max_dd

        # 检查IC值
        ic = eval_data.get("ic", eval_data.get("ic_positive_pct", 0))
        if abs(ic) < HEALTH_THRESHOLDS["min_ic"]:
            report["is_healthy"] = False
            report["issues"].append(f"IC值过低: {ic:.4f} < {HEALTH_THRESHOLDS['min_ic']}")
        report["metrics"]["ic"] = ic

        # 更新健康指标
        self.health_metrics = {
            "last_check": datetime.now().isoformat(),
            "is_healthy": report["is_healthy"],
            "issues": report["issues"],
        }

        return report

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "logic": self.logic,
            "category": self.category,
            "lifecycle_state": self.lifecycle_state.value,
            "lifecycle_state_name": STATE_NAMES[self.lifecycle_state],
            "lifecycle_history": [
                {
                    "from_state": t.from_state.value,
                    "to_state": t.to_state.value,
                    "timestamp": t.timestamp,
                    "reason": t.reason,
                    "metrics": t.metrics,
                    "approved_by": t.approved_by,
                }
                for t in self.lifecycle_history
            ],
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "inspired_by": self.inspired_by,
            "evolved_from": self.evolved_from,
            "evaluation": self.evaluation,
            "health_metrics": self.health_metrics,
            "version": self.version,
            "versions": self.versions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FactorAsset":
        """从字典创建 FactorAsset"""
        # 转换 lifecycle_state
        state_str = data.get("lifecycle_state", "S0_raw")
        try:
            lifecycle_state = LifecycleState(state_str)
        except ValueError:
            lifecycle_state = LifecycleState.RAW

        # 转换 lifecycle_history
        history = []
        for h in data.get("lifecycle_history", []):
            try:
                from_state = LifecycleState(h["from_state"])
                to_state = LifecycleState(h["to_state"])
                history.append(
                    StateTransition(
                        from_state=from_state,
                        to_state=to_state,
                        timestamp=h.get("timestamp", ""),
                        reason=h.get("reason", ""),
                        metrics=h.get("metrics", {}),
                        approved_by=h.get("approved_by", "system"),
                    )
                )
            except (KeyError, ValueError):
                continue

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            code=data.get("code", ""),
            description=data.get("description", ""),
            logic=data.get("logic", ""),
            category=data.get("category", ""),
            lifecycle_state=lifecycle_state,
            lifecycle_history=history,
            source_type=data.get("source_type", ""),
            source_ref=data.get("source_ref", ""),
            inspired_by=data.get("inspired_by", []),
            evolved_from=data.get("evolved_from", []),
            evaluation=data.get("evaluation", {}),
            health_metrics=data.get("health_metrics", {}),
            version=data.get("version", 1),
            versions=data.get("versions", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class FactorLifecycleManager:
    """
    因子生命周期管理器

    管理因子集合的生命周期状态转换、健康度监控和维护提案。
    """

    def __init__(self):
        self.factors: dict[str, FactorAsset] = {}

    def register_factor(self, factor: FactorAsset) -> None:
        """注册因子到管理器"""
        self.factors[factor.id] = factor

    def get_factor(self, factor_id: str) -> Optional[FactorAsset]:
        """获取因子"""
        return self.factors.get(factor_id)

    def list_factors_by_state(self, state: LifecycleState) -> list[FactorAsset]:
        """按状态列出因子"""
        return [f for f in self.factors.values() if f.lifecycle_state == state]

    def advance_factor(
        self,
        factor_id: str,
        target_state: LifecycleState,
        reason: str,
        metrics: dict[str, Any] = None,
        approved_by: str = "system",
    ) -> StateTransition:
        """
        推进因子到下一状态

        Args:
            factor_id: 因子ID
            target_state: 目标状态
            reason: 转换原因
            metrics: 评估指标
            approved_by: 审批者

        Returns:
            StateTransition 记录
        """
        factor = self.get_factor(factor_id)
        if factor is None:
            raise ValueError(f"因子不存在: {factor_id}")

        return factor.transition(target_state, reason, metrics, approved_by)

    def check_all_health(self) -> dict[str, dict[str, Any]]:
        """
        检查所有已发布因子的健康度

        Returns:
            因子ID -> 健康度报告
        """
        results = {}
        for factor_id, factor in self.factors.items():
            if factor.lifecycle_state == LifecycleState.RELEASED:
                results[factor_id] = factor.check_health()
        return results

    def generate_maintenance_proposals(self) -> list[dict[str, Any]]:
        """
        生成维护提案

        检查退化的因子，自动生成修复/替换/归档提案。

        Returns:
            维护提案列表
        """
        proposals = []

        for factor_id, factor in self.factors.items():
            if factor.lifecycle_state == LifecycleState.RELEASED:
                health = factor.check_health()
                if not health["is_healthy"]:
                    proposal = {
                        "factor_id": factor_id,
                        "factor_name": factor.name,
                        "current_state": factor.lifecycle_state.value,
                        "issues": health["issues"],
                        "proposed_action": "degrade",  # 降级到 S5
                        "reason": f"健康度检查失败: {'; '.join(health['issues'])}",
                        "timestamp": datetime.now().isoformat(),
                    }
                    proposals.append(proposal)

            elif factor.lifecycle_state == LifecycleState.DEGRADED:
                # 退化因子的维护提案
                health = factor.check_health()
                if health["is_healthy"]:
                    # 恢复健康，可以重新发布
                    proposal = {
                        "factor_id": factor_id,
                        "factor_name": factor.name,
                        "current_state": factor.lifecycle_state.value,
                        "issues": [],
                        "proposed_action": "re_release",  # 重新发布到 S4
                        "reason": "因子已恢复健康，建议重新发布",
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    # 仍然退化，建议归档
                    proposal = {
                        "factor_id": factor_id,
                        "factor_name": factor.name,
                        "current_state": factor.lifecycle_state.value,
                        "issues": health["issues"],
                        "proposed_action": "deprecate",  # 弃用到 S6
                        "reason": f"因子持续退化，建议弃用: {'; '.join(health['issues'])}",
                        "timestamp": datetime.now().isoformat(),
                    }
                proposals.append(proposal)

        return proposals

    def get_statistics(self) -> dict[str, Any]:
        """获取生命周期统计"""
        stats = {state.value: 0 for state in LifecycleState}
        for factor in self.factors.values():
            stats[factor.lifecycle_state.value] += 1

        return {
            "total_factors": len(self.factors),
            "by_state": stats,
            "active_factors": stats.get(LifecycleState.RELEASED.value, 0)
            + stats.get(LifecycleState.VERIFIED.value, 0),
            "degraded_factors": stats.get(LifecycleState.DEGRADED.value, 0),
        }
