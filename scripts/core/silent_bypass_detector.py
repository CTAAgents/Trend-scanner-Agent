"""
静默旁路检测模块

基于 SkillEvolver (arXiv:2605.10500) 的静默旁路概念：
- 检测策略池中存在但从未被触发的"僵尸策略"
- 识别策略定义与实际市场条件的脱节
- 提供激活或移除建议

核心理念：
策略规则可能存在，但在实际交易中从未被触发，原因可能是：
1. 触发条件过于严格
2. 策略与当前市场环境不匹配
3. 策略参数设置不合理
4. 策略被其他策略"遮蔽"

这种"静默旁路"模式会导致：
- 策略池臃肿但实际有效策略很少
- 资源浪费在维护无效策略上
- 错过潜在的交易机会
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


# ===========================================================================
# 数据结构定义
# ===========================================================================


class BypassReason(Enum):
    """旁路原因"""

    OVERLY_STRICT = "overly_strict"  # 触发条件过于严格
    MARKET_MISMATCH = "market_mismatch"  # 与市场环境不匹配
    PARAMETER_ISSUE = "parameter_issue"  # 参数设置不合理
    SHADOWED_BY_OTHERS = "shadowed_by_others"  # 被其他策略遮蔽
    RARE_EVENT = "rare_event"  # 策略针对罕见事件
    UNKNOWN = "unknown"


class ActionRecommendation(Enum):
    """动作建议"""

    ADJUST_PARAMETERS = "adjust_parameters"  # 调整参数
    RELAX_CONDITIONS = "relax_conditions"  # 放宽条件
    REMOVE = "remove"  # 移除策略
    KEEP_AS_HEDGE = "keep_as_hedge"  # 保留作为对冲
    INVESTIGATE = "investigate"  # 需要进一步调查


@dataclass
class StrategyUsageStats:
    """策略使用统计"""

    strategy_name: str
    total_trades: int = 0  # 总交易次数
    triggered_count: int = 0  # 触发次数
    trigger_rate: float = 0.0  # 触发率
    vote_distribution: dict[str, int] = field(default_factory=dict)  # 投票分布
    last_triggered: datetime | None = None  # 最后触发时间
    avg_confidence_when_triggered: float = 0.0  # 触发时的平均置信度


@dataclass
class BypassPattern:
    """旁路模式"""

    pattern_id: str
    strategy_name: str
    reason: BypassReason
    severity: str = "medium"  # low / medium / high
    description: str = ""
    trigger_condition: str = ""
    expected_trigger_rate: float = 0.0  # 预期触发率
    actual_trigger_rate: float = 0.0  # 实际触发率
    bypass_rate: float = 0.0  # 旁路率
    affected_trades: int = 0  # 受影响的交易次数
    recommendations: list[ActionRecommendation] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class BypassReport:
    """旁路检测报告"""

    report_id: str
    total_strategies: int = 0
    active_strategies: int = 0  # 活跃策略数
    bypassed_strategies: int = 0  # 被旁路的策略数
    bypass_patterns: list[BypassPattern] = field(default_factory=list)
    strategy_stats: list[StrategyUsageStats] = field(default_factory=list)
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


# ===========================================================================
# 静默旁路检测器
# ===========================================================================


class SilentBypassDetector:
    """
    静默旁路检测器

    基于 SkillEvolver 的静默旁路检测机制：
    1. 统计策略触发频率
    2. 识别从未触发或触发率极低的策略
    3. 分析旁路原因
    4. 生成激活或移除建议
    """

    def __init__(self, trigger_rate_threshold: float = 0.05, analysis_window_days: int = 30):
        """
        参数:
            trigger_rate_threshold: 触发率阈值（低于此值视为旁路）
            analysis_window_days: 分析窗口天数
        """
        self.trigger_rate_threshold = trigger_rate_threshold
        self.analysis_window_days = analysis_window_days
        self.reports: list[BypassReport] = []

    def detect(self, trades: list[Any], strategy_pool: dict[str, Any] = None) -> BypassReport:
        """
        检测静默旁路

        参数:
            trades: 交易记录列表
            strategy_pool: 策略池配置（可选）

        返回:
            旁路检测报告
        """
        # 1. 统计策略使用情况
        strategy_stats = self._calculate_strategy_stats(trades)

        # 2. 识别旁路模式
        bypass_patterns = self._identify_bypass_patterns(strategy_stats, strategy_pool)

        # 3. 分析旁路原因
        for pattern in bypass_patterns:
            pattern.reason = self._analyze_bypass_reason(pattern, strategy_stats, trades)
            pattern.recommendations = self._generate_recommendations(pattern)

        # 4. 生成报告
        active_strategies = sum(1 for s in strategy_stats if s.trigger_rate >= self.trigger_rate_threshold)
        bypassed_strategies = len(strategy_stats) - active_strategies

        summary = self._generate_summary(strategy_stats, bypass_patterns)
        recommendations = self._generate_overall_recommendations(bypass_patterns)

        report = BypassReport(
            report_id=f"BYPASS-{datetime.now().strftime('%Y%m%d')}",
            total_strategies=len(strategy_stats),
            active_strategies=active_strategies,
            bypassed_strategies=bypassed_strategies,
            bypass_patterns=bypass_patterns,
            strategy_stats=strategy_stats,
            summary=summary,
            recommendations=recommendations,
        )

        self.reports.append(report)
        return report

    def _calculate_strategy_stats(self, trades: list[Any]) -> list[StrategyUsageStats]:
        """计算策略使用统计"""
        # 确定分析窗口
        if trades:
            latest_trade = max(trades, key=lambda t: t.entry_time if hasattr(t, "entry_time") else datetime.min)
            window_start = latest_trade.entry_time - timedelta(days=self.analysis_window_days)
            window_trades = [t for t in trades if hasattr(t, "entry_time") and t.entry_time >= window_start]
        else:
            window_trades = trades

        # 统计每个策略的使用情况
        strategy_counts = defaultdict(int)
        strategy_votes = defaultdict(lambda: defaultdict(int))
        strategy_last_triggered = {}
        strategy_confidence_sum = defaultdict(float)
        strategy_confidence_count = defaultdict(int)

        for trade in window_trades:
            if not hasattr(trade, "strategy_votes_at_entry") or not trade.strategy_votes_at_entry:
                continue

            for strategy, vote in trade.strategy_votes_at_entry.items():
                # 统计触发次数（非"观望"的投票视为触发）
                if vote != "观望":
                    strategy_counts[strategy] += 1

                    # 记录最后触发时间
                    if hasattr(trade, "entry_time"):
                        if (
                            strategy not in strategy_last_triggered
                            or trade.entry_time > strategy_last_triggered[strategy]
                        ):
                            strategy_last_triggered[strategy] = trade.entry_time

                # 统计投票分布
                strategy_votes[strategy][vote] += 1

        # 计算统计指标
        total_trades = len(window_trades)
        stats = []

        for strategy in set(list(strategy_counts.keys()) + list(strategy_votes.keys())):
            triggered_count = strategy_counts.get(strategy, 0)
            trigger_rate = triggered_count / total_trades if total_trades > 0 else 0

            stat = StrategyUsageStats(
                strategy_name=strategy,
                total_trades=total_trades,
                triggered_count=triggered_count,
                trigger_rate=trigger_rate,
                vote_distribution=dict(strategy_votes.get(strategy, {})),
                last_triggered=strategy_last_triggered.get(strategy),
                avg_confidence_when_triggered=0.0,  # 简化处理
            )
            stats.append(stat)

        # 按触发率排序
        stats.sort(key=lambda s: s.trigger_rate, reverse=True)

        return stats

    def _identify_bypass_patterns(
        self, strategy_stats: list[StrategyUsageStats], strategy_pool: dict[str, Any] = None
    ) -> list[BypassPattern]:
        """识别旁路模式"""
        patterns = []

        for stat in strategy_stats:
            # 检查触发率是否低于阈值
            if stat.trigger_rate < self.trigger_rate_threshold:
                # 计算旁路率
                bypass_rate = (
                    1 - (stat.trigger_rate / self.trigger_rate_threshold) if self.trigger_rate_threshold > 0 else 1.0
                )

                # 确定严重程度
                severity = self._determine_severity(stat.trigger_rate, bypass_rate)

                # 生成描述
                description = self._generate_pattern_description(stat, bypass_rate)

                pattern = BypassPattern(
                    pattern_id=f"BP-{datetime.now().strftime('%Y%m%d')}-{stat.strategy_name}",
                    strategy_name=stat.strategy_name,
                    reason=BypassReason.UNKNOWN,  # 将在后续分析中确定
                    severity=severity,
                    description=description,
                    expected_trigger_rate=self.trigger_rate_threshold,
                    actual_trigger_rate=stat.trigger_rate,
                    bypass_rate=bypass_rate,
                    affected_trades=stat.total_trades - stat.triggered_count,
                )
                patterns.append(pattern)

        return patterns

    def _determine_severity(self, trigger_rate: float, bypass_rate: float) -> str:
        """确定严重程度"""
        if trigger_rate == 0:
            return "high"  # 从未触发
        elif bypass_rate > 0.8:
            return "high"  # 旁路率超过80%
        elif bypass_rate > 0.5:
            return "medium"  # 旁路率超过50%
        else:
            return "low"

    def _generate_pattern_description(self, stat: StrategyUsageStats, bypass_rate: float) -> str:
        """生成模式描述"""
        if stat.trigger_rate == 0:
            return f"策略 {stat.strategy_name} 在分析窗口内从未触发"
        else:
            return f"策略 {stat.strategy_name} 触发率仅为 {stat.trigger_rate:.1%}，旁路率 {bypass_rate:.1%}"

    def _analyze_bypass_reason(
        self, pattern: BypassPattern, strategy_stats: list[StrategyUsageStats], trades: list[Any]
    ) -> BypassReason:
        """分析旁路原因"""
        strategy_name = pattern.strategy_name

        # 检查1: 是否从未触发
        if pattern.actual_trigger_rate == 0:
            # 检查是否有其他策略经常触发
            active_strategies = [s for s in strategy_stats if s.trigger_rate > 0.1]
            if len(active_strategies) > 3:
                return BypassReason.SHADOWED_BY_OTHERS
            else:
                return BypassReason.OVERLY_STRICT

        # 检查2: 触发率极低
        if pattern.actual_trigger_rate < 0.02:
            return BypassReason.OVERLY_STRICT

        # 检查3: 是否与市场环境不匹配
        # 分析触发时的市场状态
        triggered_market_states = defaultdict(int)
        for trade in trades:
            if (
                hasattr(trade, "strategy_votes_at_entry")
                and trade.strategy_votes_at_entry
                and strategy_name in trade.strategy_votes_at_entry
                and trade.strategy_votes_at_entry[strategy_name] != "观望"
            ):
                if hasattr(trade, "market_state_at_entry"):
                    triggered_market_states[trade.market_state_at_entry] += 1

        # 如果只在少数市场状态下触发，可能是市场环境不匹配
        if len(triggered_market_states) <= 2 and len(triggered_market_states) > 0:
            return BypassReason.MARKET_MISMATCH

        # 检查4: 参数问题
        # 这需要更深入的分析，这里简化处理
        if pattern.bypass_rate > 0.5:
            return BypassReason.PARAMETER_ISSUE

        return BypassReason.UNKNOWN

    def _generate_recommendations(self, pattern: BypassPattern) -> list[ActionRecommendation]:
        """生成建议"""
        recommendations = []

        if pattern.reason == BypassReason.OVERLY_STRICT:
            recommendations.append(ActionRecommendation.RELAX_CONDITIONS)
            recommendations.append(ActionRecommendation.ADJUST_PARAMETERS)

        elif pattern.reason == BypassReason.MARKET_MISMATCH:
            recommendations.append(ActionRecommendation.ADJUST_PARAMETERS)
            if pattern.severity == "high":
                recommendations.append(ActionRecommendation.REMOVE)

        elif pattern.reason == BypassReason.PARAMETER_ISSUE:
            recommendations.append(ActionRecommendation.ADJUST_PARAMETERS)

        elif pattern.reason == BypassReason.SHADOWED_BY_OTHERS:
            recommendations.append(ActionRecommendation.KEEP_AS_HEDGE)
            if pattern.severity == "high":
                recommendations.append(ActionRecommendation.REMOVE)

        elif pattern.reason == BypassReason.RARE_EVENT:
            recommendations.append(ActionRecommendation.KEEP_AS_HEDGE)

        else:
            recommendations.append(ActionRecommendation.INVESTIGATE)

        return recommendations

    def _generate_summary(self, strategy_stats: list[StrategyUsageStats], bypass_patterns: list[BypassPattern]) -> str:
        """生成摘要"""
        total = len(strategy_stats)
        active = sum(1 for s in strategy_stats if s.trigger_rate >= self.trigger_rate_threshold)
        bypassed = total - active

        summary = f"策略池共{total}个策略，其中{active}个活跃，{bypassed}个被旁路。"

        if bypass_patterns:
            high_severity = sum(1 for p in bypass_patterns if p.severity == "high")
            if high_severity > 0:
                summary += f" {high_severity}个策略存在严重旁路问题。"

            # 列出最常见的旁路原因
            reason_counts = defaultdict(int)
            for p in bypass_patterns:
                reason_counts[p.reason.value] += 1
            if reason_counts:
                most_common = max(reason_counts.items(), key=lambda x: x[1])
                summary += f" 最常见旁路原因: {most_common[0]} ({most_common[1]}次)。"

        return summary

    def _generate_overall_recommendations(self, bypass_patterns: list[BypassPattern]) -> list[str]:
        """生成整体建议"""
        recommendations = []

        if not bypass_patterns:
            return ["策略池运行正常，无需调整"]

        # 统计建议类型
        recommendation_counts = defaultdict(int)
        for pattern in bypass_patterns:
            for rec in pattern.recommendations:
                recommendation_counts[rec.value] += 1

        # 生成建议
        if recommendation_counts.get("remove", 0) > 2:
            recommendations.append("建议移除多个长期未触发的策略以简化策略池")

        if recommendation_counts.get("adjust_parameters", 0) > 2:
            recommendations.append("建议对多个策略进行参数优化")

        if recommendation_counts.get("relax_conditions", 0) > 2:
            recommendations.append("建议放宽多个策略的触发条件")

        # 通用建议
        recommendations.append("定期审查策略池，移除无效策略")
        recommendations.append("使用Walk-Forward验证策略有效性")

        return recommendations[:5]

    def get_latest_report(self) -> BypassReport | None:
        """获取最新的报告"""
        return self.reports[-1] if self.reports else None

    def get_bypassed_strategies(self) -> list[str]:
        """获取被旁路的策略列表"""
        if not self.reports:
            return []

        latest_report = self.reports[-1]
        return [p.strategy_name for p in latest_report.bypass_patterns]

    def get_active_strategies(self) -> list[str]:
        """获取活跃策略列表"""
        if not self.reports:
            return []

        latest_report = self.reports[-1]
        return [s.strategy_name for s in latest_report.strategy_stats if s.trigger_rate >= self.trigger_rate_threshold]
