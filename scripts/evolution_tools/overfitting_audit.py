"""
过拟合审计模块

基于 SkillEvolver (arXiv:2605.10500) 的审计机制：
- 数据泄漏检测：防止训练/测试数据混用
- 静默旁路检测：识别策略存在但从未触发的情况
- 过拟合风险评估：评估策略对历史数据的过度拟合

核心理念：
1. 数据泄漏：策略参数可能无意中"看到"了测试数据
2. 静默旁路：策略定义存在，但在实际交易中从未被触发
3. 过拟合风险：策略在历史数据上表现优异，但在新数据上失效
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np


# ===========================================================================
# 数据结构定义
# ===========================================================================


class AuditCheckType(Enum):
    """审计检查类型"""

    DATA_LEAKAGE = "data_leakage"  # 数据泄漏
    SILENT_BYPASS = "silent_bypass"  # 静默旁路
    OVERFITTING_RISK = "overfitting_risk"  # 过拟合风险
    PERFORMANCE_DRIFT = "performance_drift"  # 性能漂移


class AuditSeverity(Enum):
    """审计严重程度"""

    INFO = "info"  # 信息
    WARNING = "warning"  # 警告
    CRITICAL = "critical"  # 严重


@dataclass
class AuditCheck:
    """审计检查项"""

    check_id: str
    check_type: AuditCheckType
    severity: AuditSeverity
    description: str
    passed: bool = True
    details: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class AuditReport:
    """审计报告"""

    report_id: str
    skill_id: str
    skill_name: str
    checks: list[AuditCheck] = field(default_factory=list)
    overall_result: str = "PASS"  # PASS / WARNING / FAIL
    risk_score: float = 0.0  # 0-100，风险评分
    created_at: datetime = field(default_factory=datetime.now)
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)


@dataclass
class SilentBypassPattern:
    """静默旁路模式"""

    pattern_id: str
    skill_id: str
    skill_name: str
    trigger_condition: str
    expected_triggers: int = 0  # 预期触发次数
    actual_triggers: int = 0  # 实际触发次数
    bypass_rate: float = 0.0  # 旁路率 = 1 - 实际/预期
    last_triggered: datetime | None = None
    suggestions: list[str] = field(default_factory=list)


# ===========================================================================
# 过拟合审计器
# ===========================================================================


class OverfittingAuditor:
    """
    过拟合审计器

    基于 SkillEvolver 的审计机制：
    1. 数据泄漏检测：检查策略参数是否无意中"看到"了测试数据
    2. 静默旁路检测：识别策略存在但从未触发的情况
    3. 过拟合风险评估：评估策略对历史数据的过度拟合
    4. 性能漂移检测：检测策略性能随时间的变化
    """

    def __init__(self):
        self.audit_reports: list[AuditReport] = []
        self.silent_bypass_patterns: list[SilentBypassPattern] = []

    def audit_skill(
        self,
        skill_id: str,
        skill_name: str,
        trades: list[Any],
        train_period: tuple[datetime, datetime] = None,
        test_period: tuple[datetime, datetime] = None,
    ) -> AuditReport:
        """
        对技能进行全面审计

        参数:
            skill_id: 技能ID
            skill_name: 技能名称
            trades: 交易记录列表
            train_period: 训练期间（可选）
            test_period: 测试期间（可选）

        返回:
            审计报告
        """
        checks = []

        # 1. 数据泄漏检测
        if train_period and test_period:
            leakage_check = self._check_data_leakage(skill_id, trades, train_period, test_period)
            checks.append(leakage_check)

        # 2. 静默旁路检测
        bypass_check = self._check_silent_bypass(skill_id, skill_name, trades)
        checks.append(bypass_check)

        # 3. 过拟合风险评估
        overfitting_check = self._check_overfitting_risk(skill_id, trades)
        checks.append(overfitting_check)

        # 4. 性能漂移检测
        drift_check = self._check_performance_drift(skill_id, trades)
        checks.append(drift_check)

        # 计算总体结果
        overall_result, risk_score = self._calculate_overall_result(checks)

        # 生成建议
        recommendations = self._generate_recommendations(checks)

        # 生成摘要
        summary = self._generate_summary(checks, overall_result, risk_score)

        report = AuditReport(
            report_id=f"AUDIT-{datetime.now().strftime('%Y%m%d')}-{skill_id}",
            skill_id=skill_id,
            skill_name=skill_name,
            checks=checks,
            overall_result=overall_result,
            risk_score=risk_score,
            summary=summary,
            recommendations=recommendations,
        )

        self.audit_reports.append(report)
        return report

    def _check_data_leakage(
        self,
        skill_id: str,
        trades: list[Any],
        train_period: tuple[datetime, datetime],
        test_period: tuple[datetime, datetime],
    ) -> AuditCheck:
        """检查数据泄漏"""
        train_start, train_end = train_period
        test_start, test_end = test_period

        # 检查训练期间的交易是否泄漏到测试期间
        leakage_count = 0
        leakage_trades = []

        for trade in trades:
            trade_time = trade.entry_time if hasattr(trade, "entry_time") else None
            if not trade_time:
                continue

            # 检查交易是否在训练期间
            if train_start <= trade_time <= train_end:
                # 检查该交易的信号是否在测试期间被使用
                # 这里简化处理：检查是否有相似的交易在测试期间出现
                for test_trade in trades:
                    test_time = test_trade.entry_time if hasattr(test_trade, "entry_time") else None
                    if not test_time:
                        continue

                    if test_start <= test_time <= test_end:
                        # 检查是否是相似交易（相同方向、相似价格）
                        if (
                            trade.direction == test_direction
                            and abs(trade.entry_price - test_trade.entry_price) / trade.entry_price < 0.01
                        ):
                            leakage_count += 1
                            leakage_trades.append(
                                {
                                    "train_trade": trade.trade_id,
                                    "test_trade": test_trade.trade_id,
                                    "similarity": 0.95,
                                }
                            )
                            break

        passed = leakage_count == 0
        severity = (
            AuditSeverity.CRITICAL
            if leakage_count > 3
            else AuditSeverity.WARNING
            if leakage_count > 0
            else AuditSeverity.INFO
        )

        return AuditCheck(
            check_id=f"CHECK-LEAKAGE-{skill_id}",
            check_type=AuditCheckType.DATA_LEAKAGE,
            severity=severity,
            description=f"数据泄漏检测: 发现{leakage_count}个潜在泄漏",
            passed=passed,
            details={
                "leakage_count": leakage_count,
                "leakage_trades": leakage_trades[:5],  # 只显示前5个
            },
            recommendations=[] if passed else ["重新划分训练/测试集", "使用时间序列分割"],
        )

    def _check_silent_bypass(self, skill_id: str, skill_name: str, trades: list[Any]) -> AuditCheck:
        """检查静默旁路"""
        # 统计策略触发次数
        trigger_counts = defaultdict(int)
        total_trades = len(trades)

        for trade in trades:
            if hasattr(trade, "strategy_votes_at_entry") and trade.strategy_votes_at_entry:
                for strategy, vote in trade.strategy_votes_at_entry.items():
                    if vote != "观望":
                        trigger_counts[strategy] += 1

        # 识别从未触发或触发率极低的策略
        bypass_patterns = []
        for strategy, count in trigger_counts.items():
            trigger_rate = count / total_trades if total_trades > 0 else 0
            if trigger_rate < 0.05:  # 触发率低于5%
                bypass_patterns.append(
                    SilentBypassPattern(
                        pattern_id=f"BYPASS-{datetime.now().strftime('%Y%m%d')}-{strategy}",
                        skill_id=skill_id,
                        skill_name=skill_name,
                        trigger_condition=f"strategy == '{strategy}'",
                        expected_triggers=int(total_trades * 0.1),  # 预期10%的触发率
                        actual_triggers=count,
                        bypass_rate=1 - trigger_rate,
                        suggestions=[
                            f"检查{strategy}策略的触发条件是否过于严格",
                            f"考虑调整{strategy}策略的参数",
                            f"如果{strategy}策略不适用，考虑移除",
                        ],
                    )
                )

        # 检查完全未触发的策略
        all_strategies = set()
        for trade in trades:
            if hasattr(trade, "strategy_votes_at_entry") and trade.strategy_votes_at_entry:
                all_strategies.update(trade.strategy_votes_at_entry.keys())

        untriggered_strategies = all_strategies - set(trigger_counts.keys())
        for strategy in untriggered_strategies:
            bypass_patterns.append(
                SilentBypassPattern(
                    pattern_id=f"BYPASS-{datetime.now().strftime('%Y%m%d')}-{strategy}",
                    skill_id=skill_id,
                    skill_name=skill_name,
                    trigger_condition=f"strategy == '{strategy}'",
                    expected_triggers=int(total_trades * 0.05),
                    actual_triggers=0,
                    bypass_rate=1.0,
                    suggestions=[
                        f"{strategy}策略从未触发，检查触发条件",
                        f"考虑移除{strategy}策略或调整参数",
                    ],
                )
            )

        self.silent_bypass_patterns.extend(bypass_patterns)

        passed = len(bypass_patterns) == 0
        severity = AuditSeverity.WARNING if len(bypass_patterns) > 0 else AuditSeverity.INFO

        return AuditCheck(
            check_id=f"CHECK-BYPASS-{skill_id}",
            check_type=AuditCheckType.SILENT_BYPASS,
            severity=severity,
            description=f"静默旁路检测: 发现{len(bypass_patterns)}个未触发策略",
            passed=passed,
            details={
                "bypass_patterns": [
                    {
                        "strategy": p.skill_name,
                        "trigger_rate": 1 - p.bypass_rate,
                        "suggestions": p.suggestions,
                    }
                    for p in bypass_patterns
                ],
            },
            recommendations=[p.suggestions[0] for p in bypass_patterns] if bypass_patterns else [],
        )

    def _check_overfitting_risk(self, skill_id: str, trades: list[Any]) -> AuditCheck:
        """检查过拟合风险"""
        if len(trades) < 20:
            return AuditCheck(
                check_id=f"CHECK-OVERFIT-{skill_id}",
                check_type=AuditCheckType.OVERFITTING_RISK,
                severity=AuditSeverity.INFO,
                description="过拟合风险评估: 数据不足，无法评估",
                passed=True,
                details={"reason": "交易数量不足"},
            )

        # 计算滚动窗口的性能指标
        window_size = 20
        rolling_winrates = []
        rolling_pnl = []

        for i in range(window_size, len(trades)):
            window_trades = trades[i - window_size : i]
            winrate = sum(1 for t in window_trades if t.pnl > 0) / window_size
            avg_pnl = np.mean([t.pnl_pct for t in window_trades])
            rolling_winrates.append(winrate)
            rolling_pnl.append(avg_pnl)

        # 检查性能指标的稳定性
        winrate_std = np.std(rolling_winrates) if rolling_winrates else 0
        pnl_std = np.std(rolling_pnl) if rolling_pnl else 0

        # 计算过拟合风险评分
        risk_score = 0
        risk_factors = []

        if winrate_std > 0.15:
            risk_score += 30
            risk_factors.append(f"胜率波动过大: {winrate_std:.2f}")

        if pnl_std > 0.02:
            risk_score += 30
            risk_factors.append(f"收益波动过大: {pnl_std:.4f}")

        # 检查是否有连续亏损
        max_consecutive_loss = 0
        current_consecutive_loss = 0
        for trade in trades:
            if trade.pnl < 0:
                current_consecutive_loss += 1
                max_consecutive_loss = max(max_consecutive_loss, current_consecutive_loss)
            else:
                current_consecutive_loss = 0

        if max_consecutive_loss > 5:
            risk_score += 20
            risk_factors.append(f"最大连续亏损: {max_consecutive_loss}次")

        # 检查收益分布
        pnl_pcts = [t.pnl_pct for t in trades]
        if pnl_pcts:
            pnl_skew = self._calculate_skewness(pnl_pcts)
            if abs(pnl_skew) > 2:
                risk_score += 20
                risk_factors.append(f"收益分布偏斜: {pnl_skew:.2f}")

        passed = risk_score < 50
        severity = (
            AuditSeverity.CRITICAL
            if risk_score >= 70
            else AuditSeverity.WARNING
            if risk_score >= 50
            else AuditSeverity.INFO
        )

        return AuditCheck(
            check_id=f"CHECK-OVERFIT-{skill_id}",
            check_type=AuditCheckType.OVERFITTING_RISK,
            severity=severity,
            description=f"过拟合风险评估: 风险评分 {risk_score}/100",
            passed=passed,
            details={
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "winrate_std": winrate_std,
                "pnl_std": pnl_std,
                "max_consecutive_loss": max_consecutive_loss,
            },
            recommendations=[
                "增加样本外测试",
                "使用Walk-Forward验证",
                "减少参数数量",
            ]
            if not passed
            else [],
        )

    def _check_performance_drift(self, skill_id: str, trades: list[Any]) -> AuditCheck:
        """检查性能漂移"""
        if len(trades) < 40:
            return AuditCheck(
                check_id=f"CHECK-DRIFT-{skill_id}",
                check_type=AuditCheckType.PERFORMANCE_DRIFT,
                severity=AuditSeverity.INFO,
                description="性能漂移检测: 数据不足，无法检测",
                passed=True,
                details={"reason": "交易数量不足"},
            )

        # 将交易分为前半段和后半段
        mid = len(trades) // 2
        first_half = trades[:mid]
        second_half = trades[mid:]

        # 计算性能指标
        first_winrate = sum(1 for t in first_half if t.pnl > 0) / len(first_half)
        second_winrate = sum(1 for t in second_half if t.pnl > 0) / len(second_half)

        first_pnl = np.mean([t.pnl_pct for t in first_half])
        second_pnl = np.mean([t.pnl_pct for t in second_half])

        # 计算漂移程度
        winrate_drift = abs(second_winrate - first_winrate)
        pnl_drift = abs(second_pnl - first_pnl)

        # 判断是否存在显著漂移
        drift_detected = winrate_drift > 0.1 or pnl_drift > 0.01

        severity = (
            AuditSeverity.CRITICAL
            if winrate_drift > 0.2 or pnl_drift > 0.02
            else AuditSeverity.WARNING
            if drift_detected
            else AuditSeverity.INFO
        )

        return AuditCheck(
            check_id=f"CHECK-DRIFT-{skill_id}",
            check_type=AuditCheckType.PERFORMANCE_DRIFT,
            severity=severity,
            description=f"性能漂移检测: {'检测到显著漂移' if drift_detected else '无显著漂移'}",
            passed=not drift_detected,
            details={
                "first_half_winrate": first_winrate,
                "second_half_winrate": second_winrate,
                "first_half_pnl": first_pnl,
                "second_half_pnl": second_pnl,
                "winrate_drift": winrate_drift,
                "pnl_drift": pnl_drift,
            },
            recommendations=[
                "重新评估策略参数",
                "检查市场环境变化",
                "考虑使用自适应参数",
            ]
            if drift_detected
            else [],
        )

    def _calculate_skewness(self, data: list[float]) -> float:
        """计算偏度"""
        if len(data) < 3:
            return 0.0

        n = len(data)
        mean = np.mean(data)
        std = np.std(data)

        if std == 0:
            return 0.0

        skew = (n / ((n - 1) * (n - 2))) * sum(((x - mean) / std) ** 3 for x in data)
        return skew

    def _calculate_overall_result(self, checks: list[AuditCheck]) -> tuple[str, float]:
        """计算总体结果"""
        if not checks:
            return "PASS", 0.0

        # 计算风险评分
        risk_score = 0
        critical_count = 0
        warning_count = 0

        for check in checks:
            if check.severity == AuditSeverity.CRITICAL:
                critical_count += 1
                risk_score += 30
            elif check.severity == AuditSeverity.WARNING:
                warning_count += 1
                risk_score += 10

            if not check.passed:
                risk_score += 20

        risk_score = min(100, risk_score)

        # 确定总体结果
        if critical_count > 0:
            overall_result = "FAIL"
        elif warning_count > 0:
            overall_result = "WARNING"
        else:
            overall_result = "PASS"

        return overall_result, risk_score

    def _generate_recommendations(self, checks: list[AuditCheck]) -> list[str]:
        """生成建议"""
        recommendations = []

        for check in checks:
            if not check.passed and check.recommendations:
                recommendations.extend(check.recommendations)

        # 去重
        return list(set(recommendations))[:5]  # 最多返回5条建议

    def _generate_summary(self, checks: list[AuditCheck], overall_result: str, risk_score: float) -> str:
        """生成摘要"""
        total_checks = len(checks)
        passed_checks = sum(1 for c in checks if c.passed)
        failed_checks = total_checks - passed_checks

        summary = f"审计完成: {total_checks}项检查，{passed_checks}项通过，{failed_checks}项未通过。"
        summary += f"总体结果: {overall_result}，风险评分: {risk_score:.0f}/100。"

        # 列出主要问题
        critical_checks = [c for c in checks if c.severity == AuditSeverity.CRITICAL and not c.passed]
        if critical_checks:
            summary += f" 严重问题: {len(critical_checks)}个。"
            for check in critical_checks[:2]:
                summary += f" - {check.description}"

        return summary

    def get_latest_report(self, skill_id: str) -> AuditReport | None:
        """获取最新的审计报告"""
        reports = [r for r in self.audit_reports if r.skill_id == skill_id]
        return reports[-1] if reports else None

    def get_silent_bypass_patterns(self) -> list[SilentBypassPattern]:
        """获取所有静默旁路模式"""
        return self.silent_bypass_patterns

    def generate_audit_summary_report(self) -> dict[str, Any]:
        """生成审计汇总报告"""
        if not self.audit_reports:
            return {"message": "无审计记录"}

        total_reports = len(self.audit_reports)
        passed_reports = sum(1 for r in self.audit_reports if r.overall_result == "PASS")
        warning_reports = sum(1 for r in self.audit_reports if r.overall_result == "WARNING")
        failed_reports = sum(1 for r in self.audit_reports if r.overall_result == "FAIL")

        avg_risk_score = np.mean([r.risk_score for r in self.audit_reports])

        return {
            "total_reports": total_reports,
            "results_distribution": {
                "PASS": passed_reports,
                "WARNING": warning_reports,
                "FAIL": failed_reports,
            },
            "average_risk_score": avg_risk_score,
            "silent_bypass_patterns": len(self.silent_bypass_patterns),
            "key_findings": self._extract_key_findings(),
        }

    def _extract_key_findings(self) -> list[str]:
        """提取关键发现"""
        findings = []

        # 统计最常见的问题
        check_type_counts = defaultdict(int)
        for report in self.audit_reports:
            for check in report.checks:
                if not check.passed:
                    check_type_counts[check.check_type.value] += 1

        if check_type_counts:
            most_common = max(check_type_counts.items(), key=lambda x: x[1])
            findings.append(f"最常见问题: {most_common[0]} ({most_common[1]}次)")

        # 检查静默旁路
        if self.silent_bypass_patterns:
            findings.append(f"发现{len(self.silent_bypass_patterns)}个静默旁路模式")

        return findings[:5]
