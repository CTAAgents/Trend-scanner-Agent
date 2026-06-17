"""
因子治理工作流

参考 SkillWiki 的 Git-style Governance，管理因子变更的审核、版本控制和回滚。

治理活动：
- 创建 — 新增因子
- 修改 — 调整因子参数或代码
- 组合 — 将多个因子组合为新因子
- 分解 — 将复合因子拆分为原子因子
- 版本更新 — 发布新版本
- 回滚 — 回退到上一个版本

工作流：
1. 提交变更提案
2. 自动生成 diff 视图
3. 自动化验证（回测）
4. Reasoner Agent 审核
5. 批准后合并，记录版本历史
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from trend_scanner.factor_lifecycle import FactorAsset, FactorLifecycleManager, LifecycleState


class GovernanceAction(str, Enum):
    """治理活动类型"""

    CREATE = "create"
    MODIFY = "modify"
    COMPOSE = "compose"
    DECOMPOSE = "decompose"
    VERSION_UPDATE = "version_update"
    ROLLBACK = "rollback"


class GovernanceStatus(str, Enum):
    """治理状态"""

    PENDING = "pending"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    MERGED = "merged"


@dataclass
class GovernanceProposal:
    """治理提案"""

    proposal_id: str
    action: GovernanceAction
    factor_id: str
    factor_name: str
    description: str
    status: GovernanceStatus = GovernanceStatus.PENDING

    # 变更内容
    old_value: dict[str, Any] = field(default_factory=dict)
    new_value: dict[str, Any] = field(default_factory=dict)

    # 审核信息
    reviewer: str = ""
    review_comment: str = ""
    review_metrics: dict[str, Any] = field(default_factory=dict)

    # 时间戳
    created_at: str = ""
    reviewed_at: str = ""
    merged_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class FactorGovernanceWorkflow:
    """
    因子治理工作流

    管理因子变更的审核、版本控制和回滚。
    """

    def __init__(self, lifecycle_manager: FactorLifecycleManager = None):
        self.lifecycle_manager = lifecycle_manager or FactorLifecycleManager()
        self._proposals: list[GovernanceProposal] = []
        self._proposal_counter = 0

    def _next_proposal_id(self) -> str:
        """生成下一个提案ID"""
        self._proposal_counter += 1
        return f"gov_{self._proposal_counter:04d}"

    def submit_proposal(
        self,
        action: GovernanceAction,
        factor_id: str,
        description: str,
        changes: dict[str, Any] = None,
    ) -> GovernanceProposal:
        """
        提交治理提案

        Args:
            action: 治理活动类型
            factor_id: 因子ID
            description: 变更描述
            changes: 变更内容

        Returns:
            治理提案
        """
        factor = self.lifecycle_manager.get_factor(factor_id)
        if factor is None:
            raise ValueError(f"因子不存在: {factor_id}")

        proposal = GovernanceProposal(
            proposal_id=self._next_proposal_id(),
            action=action,
            factor_id=factor_id,
            factor_name=factor.name,
            description=description,
            old_value={
                "code": factor.code,
                "evaluation": factor.evaluation,
                "lifecycle_state": factor.lifecycle_state.value,
            },
            new_value=changes or {},
        )

        self._proposals.append(proposal)
        return proposal

    def generate_diff(self, proposal: GovernanceProposal) -> dict[str, Any]:
        """
        生成变更差异

        Args:
            proposal: 治理提案

        Returns:
            差异信息
        """
        old = proposal.old_value
        new = proposal.new_value

        diff = {
            "code_changed": old.get("code", "") != new.get("code", ""),
            "params_changed": old.get("params", {}) != new.get("params", {}),
            "evaluation_changed": old.get("evaluation", {}) != new.get("evaluation", {}),
            "details": {},
        }

        # 代码差异
        if diff["code_changed"]:
            diff["details"]["code"] = {
                "old": old.get("code", ""),
                "new": new.get("code", ""),
            }

        # 参数差异
        if diff["params_changed"]:
            old_params = old.get("params", {})
            new_params = new.get("params", {})
            param_diff = {}
            all_keys = set(list(old_params.keys()) + list(new_params.keys()))
            for key in all_keys:
                if old_params.get(key) != new_params.get(key):
                    param_diff[key] = {
                        "old": old_params.get(key),
                        "new": new_params.get(key),
                    }
            diff["details"]["params"] = param_diff

        return diff

    def review_proposal(
        self,
        proposal_id: str,
        approved: bool,
        reviewer: str,
        comment: str = "",
        metrics: dict[str, Any] = None,
    ) -> GovernanceProposal:
        """
        审核治理提案

        Args:
            proposal_id: 提案ID
            approved: 是否批准
            reviewer: 审核者
            comment: 审核意见
            metrics: 审核指标

        Returns:
            更新后的提案
        """
        proposal = self._get_proposal(proposal_id)
        if proposal is None:
            raise ValueError(f"提案不存在: {proposal_id}")

        proposal.status = GovernanceStatus.APPROVED if approved else GovernanceStatus.REJECTED
        proposal.reviewer = reviewer
        proposal.review_comment = comment
        proposal.review_metrics = metrics or {}
        proposal.reviewed_at = datetime.now().isoformat()

        return proposal

    def merge_proposal(self, proposal_id: str) -> GovernanceProposal:
        """
        合并治理提案

        将批准的变更应用到因子。

        Args:
            proposal_id: 提案ID

        Returns:
            更新后的提案
        """
        proposal = self._get_proposal(proposal_id)
        if proposal is None:
            raise ValueError(f"提案不存在: {proposal_id}")

        if proposal.status != GovernanceStatus.APPROVED:
            raise ValueError(f"提案未批准，当前状态: {proposal.status.value}")

        factor = self.lifecycle_manager.get_factor(proposal.factor_id)
        if factor is None:
            raise ValueError(f"因子不存在: {proposal.factor_id}")

        # 应用变更
        if proposal.action == GovernanceAction.MODIFY:
            self._apply_modify(factor, proposal)
        elif proposal.action == GovernanceAction.VERSION_UPDATE:
            self._apply_version_update(factor, proposal)
        elif proposal.action == GovernanceAction.ROLLBACK:
            self._apply_rollback(factor, proposal)

        proposal.status = GovernanceStatus.MERGED
        proposal.merged_at = datetime.now().isoformat()

        return proposal

    def _apply_modify(self, factor: FactorAsset, proposal: GovernanceProposal) -> None:
        """应用修改"""
        new_value = proposal.new_value

        if "code" in new_value:
            factor.save_version_snapshot(f"修改前版本 (proposal: {proposal.proposal_id})")
            factor.code = new_value["code"]

        if "evaluation" in new_value:
            factor.evaluation = new_value["evaluation"]

        if "params" in new_value:
            factor.evaluation.update(new_value["params"])

        factor.updated_at = datetime.now().isoformat()

    def _apply_version_update(self, factor: FactorAsset, proposal: GovernanceProposal) -> None:
        """应用版本更新"""
        factor.save_version_snapshot(f"版本更新 (proposal: {proposal.proposal_id})")

        new_value = proposal.new_value
        if "code" in new_value:
            factor.code = new_value["code"]
        if "evaluation" in new_value:
            factor.evaluation = new_value["evaluation"]

        factor.updated_at = datetime.now().isoformat()

    def _apply_rollback(self, factor: FactorAsset, proposal: GovernanceProposal) -> None:
        """应用回滚"""
        if factor.versions:
            last_version = factor.versions[-1]
            factor.code = last_version.get("code", factor.code)
            factor.evaluation = last_version.get("evaluation", factor.evaluation)
            factor.save_version_snapshot(f"回滚到版本 {last_version.get('version', '?')}")
            factor.updated_at = datetime.now().isoformat()

    def _get_proposal(self, proposal_id: str) -> Optional[GovernanceProposal]:
        """获取提案"""
        for p in self._proposals:
            if p.proposal_id == proposal_id:
                return p
        return None

    def get_proposals(self, factor_id: str = None, status: GovernanceStatus = None) -> list[GovernanceProposal]:
        """
        获取提案列表

        Args:
            factor_id: 过滤因子ID
            status: 过滤状态

        Returns:
            提案列表
        """
        results = self._proposals

        if factor_id:
            results = [p for p in results if p.factor_id == factor_id]

        if status:
            results = [p for p in results if p.status == status]

        return results

    def get_version_history(self, factor_id: str) -> list[dict[str, Any]]:
        """
        获取因子版本历史

        Args:
            factor_id: 因子ID

        Returns:
            版本历史列表
        """
        factor = self.lifecycle_manager.get_factor(factor_id)
        if factor is None:
            return []

        return factor.versions

    def get_statistics(self) -> dict[str, Any]:
        """获取治理统计"""
        status_counts = {}
        action_counts = {}

        for p in self._proposals:
            s = p.status.value
            a = p.action.value
            status_counts[s] = status_counts.get(s, 0) + 1
            action_counts[a] = action_counts.get(a, 0) + 1

        return {
            "total_proposals": len(self._proposals),
            "by_status": status_counts,
            "by_action": action_counts,
        }
