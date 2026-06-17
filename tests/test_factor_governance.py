"""
因子治理工作波单元测试

测试治理提案、审核、合并和版本控制功能。
"""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.factor_governance import (
    FactorGovernanceWorkflow,
    GovernanceAction,
    GovernanceProposal,
    GovernanceStatus,
)
from trend_scanner.factor_lifecycle import FactorAsset, FactorLifecycleManager, LifecycleState


class TestGovernanceAction:
    """测试治理活动类型"""

    def test_all_actions(self):
        """测试所有类型"""
        actions = list(GovernanceAction)
        assert len(actions) == 6

    def test_action_values(self):
        """测试类型值"""
        assert GovernanceAction.CREATE.value == "create"
        assert GovernanceAction.MODIFY.value == "modify"
        assert GovernanceAction.COMPOSE.value == "compose"
        assert GovernanceAction.DECOMPOSE.value == "decompose"
        assert GovernanceAction.VERSION_UPDATE.value == "version_update"
        assert GovernanceAction.ROLLBACK.value == "rollback"


class TestGovernanceStatus:
    """测试治理状态"""

    def test_all_statuses(self):
        """测试所有状态"""
        statuses = list(GovernanceStatus)
        assert len(statuses) == 5

    def test_status_values(self):
        """测试状态值"""
        assert GovernanceStatus.PENDING.value == "pending"
        assert GovernanceStatus.REVIEWING.value == "reviewing"
        assert GovernanceStatus.APPROVED.value == "approved"
        assert GovernanceStatus.REJECTED.value == "rejected"
        assert GovernanceStatus.MERGED.value == "merged"


class TestFactorGovernanceWorkflow:
    """测试治理工作流"""

    def setup_method(self):
        self.manager = FactorLifecycleManager()
        self.workflow = FactorGovernanceWorkflow(self.manager)

    def test_submit_proposal(self):
        """测试提交提案"""
        factor = FactorAsset(
            id="gov_001", name="测试因子", code="return 0",
            lifecycle_state=LifecycleState.RELEASED,
        )
        self.manager.register_factor(factor)

        proposal = self.workflow.submit_proposal(
            GovernanceAction.MODIFY,
            "gov_001",
            "调整窗口参数",
            changes={"params": {"window": 20}},
        )

        assert proposal.proposal_id.startswith("gov_")
        assert proposal.action == GovernanceAction.MODIFY
        assert proposal.status == GovernanceStatus.PENDING

    def test_submit_proposal_nonexistent_factor(self):
        """测试提交不存在因子的提案"""
        with pytest.raises(ValueError):
            self.workflow.submit_proposal(
                GovernanceAction.MODIFY,
                "nonexistent",
                "测试",
            )

    def test_generate_diff(self):
        """测试生成差异"""
        factor = FactorAsset(
            id="gov_002", name="差异测试", code="old_code",
            lifecycle_state=LifecycleState.RELEASED,
        )
        self.manager.register_factor(factor)

        proposal = self.workflow.submit_proposal(
            GovernanceAction.MODIFY,
            "gov_002",
            "代码修改",
            changes={"code": "new_code"},
        )

        diff = self.workflow.generate_diff(proposal)
        assert diff["code_changed"] is True
        assert diff["details"]["code"]["old"] == "old_code"
        assert diff["details"]["code"]["new"] == "new_code"

    def test_review_proposal_approved(self):
        """测试审核提案（批准）"""
        factor = FactorAsset(
            id="gov_003", name="审核测试", code="",
            lifecycle_state=LifecycleState.RELEASED,
        )
        self.manager.register_factor(factor)

        proposal = self.workflow.submit_proposal(
            GovernanceAction.MODIFY, "gov_003", "参数调整",
        )

        reviewed = self.workflow.review_proposal(
            proposal.proposal_id,
            approved=True,
            reviewer="reasoner_agent",
            comment="参数调整合理",
            metrics={"expected_sharpe_improvement": 0.1},
        )

        assert reviewed.status == GovernanceStatus.APPROVED
        assert reviewed.reviewer == "reasoner_agent"

    def test_review_proposal_rejected(self):
        """测试审核提案（拒绝）"""
        factor = FactorAsset(
            id="gov_004", name="拒绝测试", code="",
            lifecycle_state=LifecycleState.RELEASED,
        )
        self.manager.register_factor(factor)

        proposal = self.workflow.submit_proposal(
            GovernanceAction.MODIFY, "gov_004", "风险修改",
        )

        reviewed = self.workflow.review_proposal(
            proposal.proposal_id,
            approved=False,
            reviewer="risk_officer",
            comment="修改风险过高",
        )

        assert reviewed.status == GovernanceStatus.REJECTED

    def test_merge_proposal(self):
        """测试合并提案"""
        factor = FactorAsset(
            id="gov_005", name="合并测试", code="old_code",
            lifecycle_state=LifecycleState.RELEASED,
        )
        self.manager.register_factor(factor)

        proposal = self.workflow.submit_proposal(
            GovernanceAction.MODIFY,
            "gov_005",
            "代码更新",
            changes={"code": "new_code"},
        )

        # 审核通过
        self.workflow.review_proposal(proposal.proposal_id, approved=True, reviewer="agent")

        # 合并
        merged = self.workflow.merge_proposal(proposal.proposal_id)
        assert merged.status == GovernanceStatus.MERGED
        assert merged.merged_at != ""

        # 验证因子代码已更新
        assert factor.code == "new_code"

    def test_merge_unapproved_proposal(self):
        """测试合并未批准的提案"""
        factor = FactorAsset(
            id="gov_006", name="未批准测试", code="",
            lifecycle_state=LifecycleState.RELEASED,
        )
        self.manager.register_factor(factor)

        proposal = self.workflow.submit_proposal(
            GovernanceAction.MODIFY, "gov_006", "修改",
        )

        with pytest.raises(ValueError, match="提案未批准"):
            self.workflow.merge_proposal(proposal.proposal_id)

    def test_version_update(self):
        """测试版本更新"""
        factor = FactorAsset(
            id="gov_007", name="版本测试", code="v1_code",
            lifecycle_state=LifecycleState.RELEASED,
        )
        self.manager.register_factor(factor)

        proposal = self.workflow.submit_proposal(
            GovernanceAction.VERSION_UPDATE,
            "gov_007",
            "发布v2版本",
            changes={"code": "v2_code"},
        )

        self.workflow.review_proposal(proposal.proposal_id, approved=True, reviewer="agent")
        self.workflow.merge_proposal(proposal.proposal_id)

        assert factor.version == 2
        assert factor.code == "v2_code"
        assert len(factor.versions) >= 1

    def test_rollback(self):
        """测试回滚"""
        factor = FactorAsset(
            id="gov_008", name="回滚测试", code="v2_code",
            lifecycle_state=LifecycleState.RELEASED,
        )
        # 保存一个历史版本
        factor.versions.append({
            "version": 1,
            "code": "v1_code",
            "evaluation": {"sharpe": 1.0},
        })
        self.manager.register_factor(factor)

        proposal = self.workflow.submit_proposal(
            GovernanceAction.ROLLBACK,
            "gov_008",
            "回滚到v1",
        )

        self.workflow.review_proposal(proposal.proposal_id, approved=True, reviewer="agent")
        self.workflow.merge_proposal(proposal.proposal_id)

        assert factor.code == "v1_code"

    def test_get_proposals(self):
        """测试获取提案"""
        factor = FactorAsset(
            id="gov_009", name="列表测试", code="",
            lifecycle_state=LifecycleState.RELEASED,
        )
        self.manager.register_factor(factor)

        self.workflow.submit_proposal(GovernanceAction.MODIFY, "gov_009", "修改1")
        self.workflow.submit_proposal(GovernanceAction.MODIFY, "gov_009", "修改2")

        proposals = self.workflow.get_proposals()
        assert len(proposals) == 2

    def test_get_proposals_filtered(self):
        """测试过滤提案"""
        f1 = FactorAsset(id="gf1", name="f1", code="", lifecycle_state=LifecycleState.RELEASED)
        f2 = FactorAsset(id="gf2", name="f2", code="", lifecycle_state=LifecycleState.RELEASED)
        self.manager.register_factor(f1)
        self.manager.register_factor(f2)

        self.workflow.submit_proposal(GovernanceAction.MODIFY, "gf1", "修改f1")
        self.workflow.submit_proposal(GovernanceAction.MODIFY, "gf2", "修改f2")

        proposals_f1 = self.workflow.get_proposals(factor_id="gf1")
        assert len(proposals_f1) == 1
        assert proposals_f1[0].factor_id == "gf1"

    def test_get_version_history(self):
        """测试获取版本历史"""
        factor = FactorAsset(
            id="gov_010", name="历史测试", code="v1",
            lifecycle_state=LifecycleState.RELEASED,
        )
        factor.save_version_snapshot("v1.0")
        factor.save_version_snapshot("v1.1")
        self.manager.register_factor(factor)

        history = self.workflow.get_version_history("gov_010")
        assert len(history) == 2

    def test_get_statistics(self):
        """测试获取统计"""
        factor = FactorAsset(
            id="gov_011", name="统计测试", code="",
            lifecycle_state=LifecycleState.RELEASED,
        )
        self.manager.register_factor(factor)

        self.workflow.submit_proposal(GovernanceAction.MODIFY, "gov_011", "修改")

        stats = self.workflow.get_statistics()
        assert stats["total_proposals"] == 1
        assert stats["by_action"]["modify"] == 1


class TestFullGovernanceFlow:
    """测试完整治理流程"""

    def test_modify_workflow(self):
        """测试修改工作流"""
        manager = FactorLifecycleManager()
        workflow = FactorGovernanceWorkflow(manager)

        # 创建因子
        factor = FactorAsset(
            id="full_gov_001",
            name="完整治理测试",
            code="def factor(df): return df['close'].pct_change(5)",
            lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 1.0},
        )
        manager.register_factor(factor)

        # 提交修改提案
        proposal = workflow.submit_proposal(
            GovernanceAction.MODIFY,
            "full_gov_001",
            "优化动量窗口从5天改为10天",
            changes={
                "code": "def factor(df): return df['close'].pct_change(10)",
                "params": {"window": 10},
            },
        )
        assert proposal.status == GovernanceStatus.PENDING

        # 生成差异
        diff = workflow.generate_diff(proposal)
        assert diff["code_changed"] is True

        # Reasoner Agent 审核
        workflow.review_proposal(
            proposal.proposal_id,
            approved=True,
            reviewer="reasoner_agent",
            comment="窗口调整合理，预期夏普提升0.2",
            metrics={"expected_sharpe": 1.2},
        )
        assert proposal.status == GovernanceStatus.APPROVED

        # 合并
        workflow.merge_proposal(proposal.proposal_id)
        assert proposal.status == GovernanceStatus.MERGED
        assert factor.code == "def factor(df): return df['close'].pct_change(10)"
        assert factor.version == 2

        # 获取统计
        stats = workflow.get_statistics()
        assert stats["total_proposals"] == 1
        assert stats["by_status"]["merged"] == 1
