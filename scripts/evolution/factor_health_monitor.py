"""
因子健康度监控与自动维护提案

持续监控因子健康度，自动检测退化并生成维护提案。

监控指标：
- 滚动夏普比率
- 滚动最大回撤
- 因子IC值
- 胜率变化

退化检测规则：
- 夏普比率 < 0.5 且持续10个交易日 → 标记为 Degraded
- 最大回撤 > 15% → 立即标记为 Degraded
- IC 衰减到0附近 → 生成维护提案

维护提案类型：
- Repair   — 调整参数（如窗口期、阈值）
- Replace  — 用新因子替代
- Decompose — 将复合因子拆分为更稳定的原子因子
- Archive  — 归档失效因子
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from trend_scanner.factor_lifecycle import (
    FactorAsset,
    FactorLifecycleManager,
    LifecycleState,
    HEALTH_THRESHOLDS,
)


class MaintenanceAction(str, Enum):
    """维护提案类型"""

    REPAIR = "repair"  # 参数调整
    REPLACE = "replace"  # 替换因子
    DECOMPOSE = "decompose"  # 拆分因子
    ARCHIVE = "archive"  # 归档因子


class HealthStatus(str, Enum):
    """健康状态"""

    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass
class HealthReport:
    """健康度报告"""

    factor_id: str
    factor_name: str
    status: HealthStatus
    metrics: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    checked_at: str = ""

    def __post_init__(self):
        if not self.checked_at:
            self.checked_at = datetime.now().isoformat()


@dataclass
class MaintenanceProposal:
    """维护提案"""

    proposal_id: str
    factor_id: str
    factor_name: str
    action: MaintenanceAction
    reason: str
    current_metrics: dict[str, Any] = field(default_factory=dict)
    proposed_changes: dict[str, Any] = field(default_factory=dict)
    priority: str = "medium"  # low / medium / high / critical
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class FactorHealthMonitor:
    """
    因子健康度监控器

    持续监控因子健康度，自动检测退化并生成维护提案。
    """

    def __init__(self, lifecycle_manager: FactorLifecycleManager = None):
        self.lifecycle_manager = lifecycle_manager or FactorLifecycleManager()
        self._health_history: dict[str, list[HealthReport]] = {}
        self._proposals: list[MaintenanceProposal] = []
        self._proposal_counter = 0

    def _next_proposal_id(self) -> str:
        """生成下一个提案ID"""
        self._proposal_counter += 1
        return f"proposal_{self._proposal_counter:04d}"

    def check_factor_health(self, factor: FactorAsset) -> HealthReport:
        """
        检查单个因子健康度

        Args:
            factor: 因子资产

        Returns:
            健康度报告
        """
        metrics = {}
        issues = []
        status = HealthStatus.HEALTHY

        eval_data = factor.evaluation

        # 检查夏普比率
        sharpe = eval_data.get("sharpe", eval_data.get("long_short_sharpe", 0))
        metrics["sharpe"] = sharpe
        if sharpe < HEALTH_THRESHOLDS["min_sharpe"]:
            issues.append(f"夏普比率过低: {sharpe:.3f} < {HEALTH_THRESHOLDS['min_sharpe']}")
            status = HealthStatus.WARNING

        # 检查最大回撤
        max_dd = eval_data.get("max_drawdown", 0)
        metrics["max_drawdown"] = max_dd
        if max_dd > HEALTH_THRESHOLDS["max_drawdown"]:
            issues.append(f"最大回撤过高: {max_dd:.3f} > {HEALTH_THRESHOLDS['max_drawdown']}")
            status = HealthStatus.DEGRADED

        # 检查IC值
        ic = eval_data.get("ic", eval_data.get("ic_positive_pct", 0))
        metrics["ic"] = ic
        if abs(ic) < HEALTH_THRESHOLDS["min_ic"]:
            issues.append(f"IC值过低: {ic:.4f} < {HEALTH_THRESHOLDS['min_ic']}")
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.WARNING

        # 检查胜率
        win_rate = eval_data.get("win_rate", 0)
        metrics["win_rate"] = win_rate
        if win_rate < 0.4:
            issues.append(f"胜率过低: {win_rate:.3f} < 0.4")
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.WARNING

        # 综合判断
        if len(issues) >= 3:
            status = HealthStatus.CRITICAL
        elif len(issues) >= 2:
            status = HealthStatus.DEGRADED

        report = HealthReport(
            factor_id=factor.id,
            factor_name=factor.name,
            status=status,
            metrics=metrics,
            issues=issues,
        )

        # 记录历史
        if factor.id not in self._health_history:
            self._health_history[factor.id] = []
        self._health_history[factor.id].append(report)

        return report

    def check_all_factors(self) -> list[HealthReport]:
        """
        检查所有已发布因子的健康度

        Returns:
            健康度报告列表
        """
        reports = []
        for factor in self.lifecycle_manager.factors.values():
            if factor.lifecycle_state == LifecycleState.RELEASED:
                report = self.check_factor_health(factor)
                reports.append(report)
        return reports

    def detect_degradation(self, factor: FactorAsset) -> bool:
        """
        检测因子是否退化

        基于历史健康度报告判断是否持续退化。

        Args:
            factor: 因子资产

        Returns:
            是否退化
        """
        history = self._health_history.get(factor.id, [])
        if len(history) < 2:
            return False

        # 检查最近N次检查是否持续退化
        recent = history[-HEALTH_THRESHOLDS["degradation_window"] :]
        degraded_count = sum(
            1 for r in recent if r.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL)
        )

        return degraded_count >= len(recent) * 0.6  # 60%以上退化

    def generate_proposal(self, factor: FactorAsset, report: HealthReport) -> MaintenanceProposal:
        """
        生成维护提案

        Args:
            factor: 因子资产
            report: 健康度报告

        Returns:
            维护提案
        """
        # 确定维护动作
        if report.status == HealthStatus.CRITICAL:
            action = MaintenanceAction.ARCHIVE
            priority = "critical"
        elif report.status == HealthStatus.DEGRADED:
            # 检查是否可以修复
            if self._can_repair(factor, report):
                action = MaintenanceAction.REPAIR
                priority = "high"
            else:
                action = MaintenanceAction.REPLACE
                priority = "high"
        else:
            action = MaintenanceAction.REPAIR
            priority = "medium"

        # 生成提案
        proposal = MaintenanceProposal(
            proposal_id=self._next_proposal_id(),
            factor_id=factor.id,
            factor_name=factor.name,
            action=action,
            reason=f"健康度检查发现问题: {'; '.join(report.issues)}",
            current_metrics=report.metrics,
            proposed_changes=self._generate_changes(factor, action, report),
            priority=priority,
        )

        self._proposals.append(proposal)
        return proposal

    def _can_repair(self, factor: FactorAsset, report: HealthReport) -> bool:
        """判断是否可以修复"""
        # 如果只是参数问题，可以修复
        issues = report.issues
        param_issues = [i for i in issues if "比率" in i or "回撤" in i]
        return len(param_issues) < len(issues)

    def _generate_changes(
        self, factor: FactorAsset, action: MaintenanceAction, report: HealthReport
    ) -> dict[str, Any]:
        """生成修复建议"""
        changes = {}

        if action == MaintenanceAction.REPAIR:
            # 参数调整建议
            if report.metrics.get("sharpe", 0) < HEALTH_THRESHOLDS["min_sharpe"]:
                changes["suggestion"] = "建议调整因子窗口期或阈值参数"
                changes["params_to_adjust"] = ["window", "threshold"]

            if report.metrics.get("max_drawdown", 0) > HEALTH_THRESHOLDS["max_drawdown"]:
                changes["suggestion"] = "建议增加止损逻辑或缩小仓位"
                changes["params_to_adjust"] = ["stop_loss", "position_size"]

        elif action == MaintenanceAction.REPLACE:
            changes["suggestion"] = "建议用新因子替代当前因子"
            changes["replacement_criteria"] = ["higher_sharpe", "lower_drawdown"]

        elif action == MaintenanceAction.DECOMPOSE:
            changes["suggestion"] = "建议将复合因子拆分为更稳定的原子因子"

        elif action == MaintenanceAction.ARCHIVE:
            changes["suggestion"] = "因子已失效，建议归档"

        return changes

    def auto_degrade_factor(self, factor: FactorAsset, report: HealthReport) -> None:
        """
        自动降级因子

        如果因子健康度严重下降，自动将其降级到 Degraded 状态。

        Args:
            factor: 因子资产
            report: 健康度报告
        """
        if factor.lifecycle_state == LifecycleState.RELEASED:
            if report.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL):
                try:
                    factor.transition(
                        LifecycleState.DEGRADED,
                        reason=f"自动降级: {'; '.join(report.issues)}",
                        metrics=report.metrics,
                        approved_by="health_monitor",
                    )
                except Exception:
                    pass  # 已经在 Degraded 状态或其他无效转换

    def get_proposals(self, factor_id: str = None) -> list[MaintenanceProposal]:
        """
        获取维护提案

        Args:
            factor_id: 过滤指定因子的提案

        Returns:
            提案列表
        """
        if factor_id:
            return [p for p in self._proposals if p.factor_id == factor_id]
        return self._proposals.copy()

    def get_health_history(self, factor_id: str) -> list[HealthReport]:
        """获取因子健康度历史"""
        return self._health_history.get(factor_id, [])

    def get_statistics(self) -> dict[str, Any]:
        """获取监控统计"""
        status_counts = {}
        for history in self._health_history.values():
            for report in history:
                s = report.status.value
                status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "total_checks": sum(len(h) for h in self._health_history.values()),
            "factors_monitored": len(self._health_history),
            "total_proposals": len(self._proposals),
            "status_distribution": status_counts,
        }
