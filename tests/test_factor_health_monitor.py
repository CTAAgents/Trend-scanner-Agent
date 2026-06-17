"""
因子健康度监控单元测试

测试健康度检查、退化检测和维护提案生成功能。
"""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.factor_health_monitor import (
    FactorHealthMonitor,
    HealthReport,
    HealthStatus,
    MaintenanceAction,
    MaintenanceProposal,
)
from trend_scanner.factor_lifecycle import FactorAsset, FactorLifecycleManager, LifecycleState


class TestHealthStatus:
    """测试健康状态"""

    def test_all_statuses(self):
        """测试所有状态"""
        statuses = list(HealthStatus)
        assert len(statuses) == 4

    def test_status_values(self):
        """测试状态值"""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.WARNING.value == "warning"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.CRITICAL.value == "critical"


class TestMaintenanceAction:
    """测试维护动作"""

    def test_all_actions(self):
        """测试所有动作"""
        actions = list(MaintenanceAction)
        assert len(actions) == 4

    def test_action_values(self):
        """测试动作值"""
        assert MaintenanceAction.REPAIR.value == "repair"
        assert MaintenanceAction.REPLACE.value == "replace"
        assert MaintenanceAction.DECOMPOSE.value == "decompose"
        assert MaintenanceAction.ARCHIVE.value == "archive"


class TestFactorHealthMonitor:
    """测试健康度监控器"""

    def setup_method(self):
        self.manager = FactorLifecycleManager()
        self.monitor = FactorHealthMonitor(self.manager)

    def test_check_healthy_factor(self):
        """测试检查健康因子"""
        factor = FactorAsset(
            id="healthy_001",
            name="健康因子",
            code="",
            lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 1.5, "max_drawdown": 0.1, "ic": 0.05, "win_rate": 0.55},
        )
        self.manager.register_factor(factor)

        report = self.monitor.check_factor_health(factor)
        assert report.status == HealthStatus.HEALTHY
        assert len(report.issues) == 0

    def test_check_warning_factor(self):
        """测试检查警告因子"""
        factor = FactorAsset(
            id="warning_001",
            name="警告因子",
            code="",
            lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 0.3, "max_drawdown": 0.1, "ic": 0.05, "win_rate": 0.45},
        )
        self.manager.register_factor(factor)

        report = self.monitor.check_factor_health(factor)
        assert report.status == HealthStatus.WARNING
        assert len(report.issues) >= 1

    def test_check_degraded_factor(self):
        """测试检查退化因子"""
        factor = FactorAsset(
            id="degraded_001",
            name="退化因子",
            code="",
            lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 0.3, "max_drawdown": 0.2, "ic": 0.01, "win_rate": 0.35},
        )
        self.manager.register_factor(factor)

        report = self.monitor.check_factor_health(factor)
        assert report.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL)
        assert len(report.issues) >= 2

    def test_check_all_factors(self):
        """测试检查所有因子"""
        f1 = FactorAsset(
            id="all_001", name="f1", code="", lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 1.5, "max_drawdown": 0.1, "ic": 0.05},
        )
        f2 = FactorAsset(
            id="all_002", name="f2", code="", lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 0.3, "max_drawdown": 0.2, "ic": 0.01},
        )
        self.manager.register_factor(f1)
        self.manager.register_factor(f2)

        reports = self.monitor.check_all_factors()
        assert len(reports) == 2

    def test_generate_proposal_repair(self):
        """测试生成修复提案"""
        factor = FactorAsset(
            id="repair_001", name="需修复因子", code="", lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 0.3, "max_drawdown": 0.1, "ic": 0.05},
        )
        report = HealthReport(
            factor_id="repair_001",
            factor_name="需修复因子",
            status=HealthStatus.WARNING,
            issues=["夏普比率过低"],
        )

        proposal = self.monitor.generate_proposal(factor, report)
        assert proposal.action == MaintenanceAction.REPAIR
        assert proposal.factor_id == "repair_001"

    def test_generate_proposal_archive(self):
        """测试生成归档提案"""
        factor = FactorAsset(
            id="archive_001", name="失效因子", code="", lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 0.1, "max_drawdown": 0.3, "ic": 0.005},
        )
        report = HealthReport(
            factor_id="archive_001",
            factor_name="失效因子",
            status=HealthStatus.CRITICAL,
            issues=["夏普比率过低", "最大回撤过高", "IC值过低"],
        )

        proposal = self.monitor.generate_proposal(factor, report)
        assert proposal.action == MaintenanceAction.ARCHIVE
        assert proposal.priority == "critical"

    def test_auto_degrade_factor(self):
        """测试自动降级因子"""
        factor = FactorAsset(
            id="degrade_001", name="将退化因子", code="", lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 0.3, "max_drawdown": 0.2, "ic": 0.01},
        )
        self.manager.register_factor(factor)

        report = self.monitor.check_factor_health(factor)
        self.monitor.auto_degrade_factor(factor, report)

        # 如果健康度为DEGRADED或CRITICAL，应自动降级
        if report.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL):
            assert factor.lifecycle_state == LifecycleState.DEGRADED

    def test_get_proposals(self):
        """测试获取提案"""
        factor = FactorAsset(
            id="prop_001", name="测试因子", code="", lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 0.3, "max_drawdown": 0.1, "ic": 0.05},
        )
        report = HealthReport(
            factor_id="prop_001", factor_name="测试因子",
            status=HealthStatus.WARNING, issues=["夏普比率过低"],
        )
        self.monitor.generate_proposal(factor, report)

        proposals = self.monitor.get_proposals()
        assert len(proposals) == 1

    def test_get_proposals_by_factor(self):
        """测试按因子获取提案"""
        f1 = FactorAsset(id="p1", name="f1", code="", lifecycle_state=LifecycleState.RELEASED,
                         evaluation={"sharpe": 0.3, "max_drawdown": 0.1, "ic": 0.05})
        f2 = FactorAsset(id="p2", name="f2", code="", lifecycle_state=LifecycleState.RELEASED,
                         evaluation={"sharpe": 0.3, "max_drawdown": 0.1, "ic": 0.05})

        r1 = HealthReport(factor_id="p1", factor_name="f1", status=HealthStatus.WARNING, issues=[])
        r2 = HealthReport(factor_id="p2", factor_name="f2", status=HealthStatus.WARNING, issues=[])

        self.monitor.generate_proposal(f1, r1)
        self.monitor.generate_proposal(f2, r2)

        proposals_p1 = self.monitor.get_proposals("p1")
        assert len(proposals_p1) == 1
        assert proposals_p1[0].factor_id == "p1"

    def test_get_health_history(self):
        """测试获取健康度历史"""
        factor = FactorAsset(
            id="hist_001", name="历史因子", code="", lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 1.5, "max_drawdown": 0.1, "ic": 0.05},
        )
        self.monitor.check_factor_health(factor)
        self.monitor.check_factor_health(factor)

        history = self.monitor.get_health_history("hist_001")
        assert len(history) == 2

    def test_get_statistics(self):
        """测试获取统计"""
        factor = FactorAsset(
            id="stat_001", name="统计因子", code="", lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 1.5, "max_drawdown": 0.1, "ic": 0.05},
        )
        self.monitor.check_factor_health(factor)

        stats = self.monitor.get_statistics()
        assert stats["total_checks"] == 1
        assert stats["factors_monitored"] == 1


class TestFullHealthFlow:
    """测试完整健康监控流程"""

    def test_monitoring_cycle(self):
        """测试监控周期"""
        manager = FactorLifecycleManager()
        monitor = FactorHealthMonitor(manager)

        # 创建因子
        factor = FactorAsset(
            id="cycle_001",
            name="监控测试因子",
            code="",
            lifecycle_state=LifecycleState.RELEASED,
            evaluation={"sharpe": 1.5, "max_drawdown": 0.1, "ic": 0.05},
        )
        manager.register_factor(factor)

        # 第一次检查：健康
        report1 = monitor.check_factor_health(factor)
        assert report1.status == HealthStatus.HEALTHY

        # 模拟性能下降
        factor.evaluation = {"sharpe": 0.3, "max_drawdown": 0.2, "ic": 0.01}

        # 第二次检查：退化
        report2 = monitor.check_factor_health(factor)
        assert report2.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL)

        # 自动降级
        monitor.auto_degrade_factor(factor, report2)
        if report2.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL):
            assert factor.lifecycle_state == LifecycleState.DEGRADED

        # 生成维护提案
        proposal = monitor.generate_proposal(factor, report2)
        assert proposal.action in (MaintenanceAction.REPAIR, MaintenanceAction.REPLACE, MaintenanceAction.ARCHIVE)

        # 获取统计
        stats = monitor.get_statistics()
        assert stats["total_checks"] == 2
        assert stats["total_proposals"] == 1
