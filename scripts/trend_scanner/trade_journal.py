"""
交易日志模块

基于 self-improvement skill 的学习日志概念，为趋势跟踪系统提供：
- TradeJournalEntry: 交易日志条目
- TradeJournal: 交易日志管理器
- PatternDetector: 重复模式检测器
- RulePromoter: 规则晋升器

核心理念：
1. 结构化记录：每笔交易的教训、洞察、知识缺口
2. 模式检测：识别重复出现的亏损模式
3. 规则晋升：将成功模式固化为策略规则
4. 周期复盘：生成周度/月度复盘报告
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json
import numpy as np


# ===========================================================================
# 数据结构定义
# ===========================================================================

class EntryCategory(Enum):
    """日志条目分类"""
    CORRECTION = "correction"          # 纠正：系统判断错误
    INSIGHT = "insight"                # 洞察：发现新的市场规律
    KNOWLEDGE_GAP = "knowledge_gap"    # 知识缺口：缺少必要信息
    BEST_PRACTICE = "best_practice"    # 最佳实践：成功的做法
    ERROR = "error"                    # 错误：执行错误
    PATTERN = "pattern"                # 模式：重复出现的规律


class PatternSeverity(Enum):
    """模式严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TradeJournalEntry:
    """交易日志条目"""
    entry_id: str
    trade_id: str
    symbol: str
    category: EntryCategory
    timestamp: datetime = field(default_factory=datetime.now)
    summary: str = ""                   # 一句话总结
    details: str = ""                   # 详细描述
    suggested_action: str = ""          # 建议的改进措施
    priority: str = "medium"            # low / medium / high / critical
    status: str = "pending"             # pending / resolved / promoted
    related_trades: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecurringPattern:
    """重复模式"""
    pattern_id: str
    pattern_key: str                    # 模式标识（用于去重）
    description: str
    severity: PatternSeverity = PatternSeverity.MEDIUM
    occurrence_count: int = 0
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    affected_trades: List[str] = field(default_factory=list)
    root_cause: str = ""
    suggested_fix: str = ""
    promoted: bool = False              # 是否已晋升为规则


@dataclass
class StrategyRule:
    """策略规则（从模式晋升而来）"""
    rule_id: str
    name: str
    description: str
    condition: str                      # 触发条件
    action: str                         # 执行动作
    source_pattern: str = ""            # 来源模式ID
    created_at: datetime = field(default_factory=datetime.now)
    enabled: bool = True
    hit_count: int = 0                  # 触发次数
    effectiveness: float = 0.0          # 有效性评分


# ===========================================================================
# 交易日志管理器
# ===========================================================================

class TradeJournal:
    """
    交易日志管理器

    基于 self-improvement skill 的学习日志概念：
    - 结构化记录每笔交易的教训
    - 支持按分类、优先级、状态筛选
    - 生成周期性复盘报告
    """

    def __init__(self):
        self.entries: List[TradeJournalEntry] = []
        self.patterns: List[RecurringPattern] = []
        self.rules: List[StrategyRule] = []

    def log_trade_lesson(self, trade, fault_attribution: Dict[str, Any] = None,
                        trajectory_analysis: Dict[str, Any] = None) -> TradeJournalEntry:
        """
        记录交易教训

        参数:
            trade: TradeRecord 对象
            fault_attribution: 故障归因结果
            trajectory_analysis: 轨迹分析结果

        返回:
            TradeJournalEntry 对象
        """
        # 确定分类
        category = self._determine_category(trade, fault_attribution)

        # 生成总结
        summary = self._generate_summary(trade, category)

        # 生成详细描述
        details = self._generate_details(trade, fault_attribution, trajectory_analysis)

        # 生成建议
        suggested_action = self._generate_suggested_action(trade, fault_attribution)

        # 确定优先级
        priority = self._determine_priority(trade, fault_attribution)

        # 生成标签
        tags = self._generate_tags(trade, fault_attribution)

        entry = TradeJournalEntry(
            entry_id=f"JRN-{datetime.now().strftime('%Y%m%d')}-{len(self.entries):03d}",
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            category=category,
            summary=summary,
            details=details,
            suggested_action=suggested_action,
            priority=priority,
            tags=tags,
            metadata={
                'pnl': trade.pnl,
                'pnl_pct': trade.pnl_pct,
                'direction': trade.direction,
                'exit_reason': trade.exit_reason,
                'market_state': trade.market_state_at_entry,
                'trend_phase': trade.trend_phase_at_entry,
            }
        )

        self.entries.append(entry)
        return entry

    def log_analysis(self, record: Dict[str, Any]):
        """
        记录分析结果（由 EvolutionManager 调用）

        参数:
            record: 分析记录字典
        """
        entry = TradeJournalEntry(
            entry_id=f"ANL-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            trade_id=record.get('trade_id', ''),
            symbol=record.get('symbol', 'UNKNOWN'),
            category='analysis',
            summary=f"{record.get('symbol', '')} 分析记录",
            details=json.dumps(record, ensure_ascii=False, default=str),
            suggested_action='',
            priority='low',
            tags=['analysis'],
            metadata=record
        )
        self.entries.append(entry)
        return entry

    def _determine_category(self, trade, fault_attribution: Dict[str, Any] = None) -> EntryCategory:
        """确定日志分类"""
        if trade.pnl > 0:
            return EntryCategory.BEST_PRACTICE

        if fault_attribution and fault_attribution.get('has_fault'):
            faults = fault_attribution.get('faults', [])
            fault_types = [f.fault_type.value for f in faults]

            if 'phase_mismatch' in fault_types:
                return EntryCategory.CORRECTION
            elif 'indicator_misuse' in fault_types:
                return EntryCategory.KNOWLEDGE_GAP
            elif 'timing_error' in fault_types:
                return EntryCategory.INSIGHT
            elif 'risk_mismanagement' in fault_types:
                return EntryCategory.ERROR

        return EntryCategory.CORRECTION

    def _generate_summary(self, trade, category: EntryCategory) -> str:
        """生成一句话总结"""
        direction = "多头" if trade.direction == "LONG" else "空头"
        pnl_str = f"+{trade.pnl:.0f}" if trade.pnl > 0 else f"{trade.pnl:.0f}"

        if category == EntryCategory.BEST_PRACTICE:
            return f"{direction}交易盈利{pnl_str}，{trade.exit_reason}出场"
        elif category == EntryCategory.CORRECTION:
            return f"{direction}交易亏损{pnl_str}，市场状态/阶段判断错误"
        elif category == EntryCategory.ERROR:
            return f"{direction}交易亏损{pnl_str}，风控执行错误"
        else:
            return f"{direction}交易亏损{pnl_str}，需要进一步分析"

    def _generate_details(self, trade, fault_attribution: Dict[str, Any] = None,
                         trajectory_analysis: Dict[str, Any] = None) -> str:
        """生成详细描述"""
        details = []

        # 基本信息
        details.append(f"入场: {trade.entry_price}, 出场: {trade.exit_price}")
        details.append(f"市场状态: {trade.market_state_at_entry}")
        details.append(f"趋势阶段: {trade.trend_phase_at_entry}")
        details.append(f"可靠性评分: {trade.reliability_score_at_entry}")

        # 策略投票
        if trade.strategy_votes_at_entry:
            votes_str = ", ".join(f"{k}:{v}" for k, v in trade.strategy_votes_at_entry.items())
            details.append(f"策略投票: {votes_str}")

        # 故障归因
        if fault_attribution and fault_attribution.get('has_fault'):
            details.append("--- 故障归因 ---")
            for fault in fault_attribution.get('faults', []):
                details.append(f"  [{fault.fault_type.value}] {fault.description}")
                for resp in fault.responsible_strategies:
                    details.append(f"    责任策略: {resp.strategy_name} (分数: {resp.score:.2f})")

        # 轨迹分析
        if trajectory_analysis:
            metrics = trajectory_analysis.get('metrics', {})
            details.append("--- 轨迹分析 ---")
            details.append(f"  轨迹质量: {metrics.get('quality_score', 0):.0f}/100")
            details.append(f"  策略一致性: {metrics.get('strategy_consistency', 0):.2f}")

        return "\n".join(details)

    def _generate_suggested_action(self, trade, fault_attribution: Dict[str, Any] = None) -> str:
        """生成建议的改进措施"""
        if trade.pnl > 0:
            return "保持当前策略，继续执行"

        if not fault_attribution or not fault_attribution.get('has_fault'):
            return "需要更多数据进行分析"

        suggestions = []
        for fault in fault_attribution.get('faults', []):
            if fault.fault_type.value == "phase_mismatch":
                suggestions.append("提高入场门槛，确保趋势阶段支持交易方向")
            elif fault.fault_type.value == "indicator_misuse":
                suggestions.append("调整指标参数，提高信号过滤标准")
            elif fault.fault_type.value == "timing_error":
                suggestions.append("优化入场/出场时机判断逻辑")
            elif fault.fault_type.value == "risk_mismanagement":
                suggestions.append("调整止损/仓位管理参数")
            elif fault.fault_type.value == "strategy_conflict":
                suggestions.append("减少策略冲突时的交易频率")

        return "; ".join(suggestions) if suggestions else "需要进一步分析"

    def _determine_priority(self, trade, fault_attribution: Dict[str, Any] = None) -> str:
        """确定优先级"""
        if trade.pnl < 0 and abs(trade.pnl_pct) > 0.02:
            return "high"
        elif trade.pnl < 0 and abs(trade.pnl_pct) > 0.01:
            return "medium"
        elif trade.pnl > 0:
            return "low"
        return "medium"

    def _generate_tags(self, trade, fault_attribution: Dict[str, Any] = None) -> List[str]:
        """生成标签"""
        tags = []

        # 方向标签
        tags.append("long" if trade.direction == "LONG" else "short")

        # 市场状态标签
        if trade.market_state_at_entry:
            tags.append(trade.market_state_at_entry.lower())

        # 趋势阶段标签
        if trade.trend_phase_at_entry:
            tags.append(trade.trend_phase_at_entry.lower())

        # 出场原因标签
        if trade.exit_reason:
            tags.append(trade.exit_reason.lower())

        # 故障类型标签
        if fault_attribution and fault_attribution.get('has_fault'):
            for fault in fault_attribution.get('faults', []):
                tags.append(f"fault:{fault.fault_type.value}")

        return tags

    def get_entries(self, symbol: str = None, category: EntryCategory = None,
                   status: str = None, limit: int = 50) -> List[TradeJournalEntry]:
        """获取日志条目"""
        filtered = self.entries

        if symbol:
            filtered = [e for e in filtered if e.symbol == symbol]
        if category:
            filtered = [e for e in filtered if e.category == category]
        if status:
            filtered = [e for e in filtered if e.status == status]

        return filtered[-limit:]

    def generate_weekly_review(self, symbol: str = None) -> Dict[str, Any]:
        """生成周度复盘报告"""
        # 获取最近7天的日志
        week_ago = datetime.now() - timedelta(days=7)
        recent_entries = [e for e in self.entries if e.timestamp >= week_ago]

        if symbol:
            recent_entries = [e for e in recent_entries if e.symbol == symbol]

        if not recent_entries:
            return {"message": "本周无交易日志"}

        # 统计分类
        category_counts = Counter(e.category.value for e in recent_entries)
        priority_counts = Counter(e.priority for e in recent_entries)

        # 统计标签
        all_tags = []
        for e in recent_entries:
            all_tags.extend(e.tags)
        tag_counts = Counter(all_tags)

        # 生成摘要
        summary = {
            "period": f"{week_ago.strftime('%Y-%m-%d')} ~ {datetime.now().strftime('%Y-%m-%d')}",
            "total_entries": len(recent_entries),
            "category_distribution": dict(category_counts),
            "priority_distribution": dict(priority_counts),
            "top_tags": dict(tag_counts.most_common(10)),
            "key_insights": self._extract_key_insights(recent_entries),
            "improvement_suggestions": self._extract_improvement_suggestions(recent_entries),
        }

        return summary

    def _extract_key_insights(self, entries: List[TradeJournalEntry]) -> List[str]:
        """提取关键洞察"""
        insights = []

        # 统计最常见的问题
        correction_entries = [e for e in entries if e.category == EntryCategory.CORRECTION]
        if correction_entries:
            insights.append(f"本周有{len(correction_entries)}笔交易存在判断错误")

        error_entries = [e for e in entries if e.category == EntryCategory.ERROR]
        if error_entries:
            insights.append(f"本周有{len(error_entries)}笔交易存在执行错误")

        best_practice_entries = [e for e in entries if e.category == EntryCategory.BEST_PRACTICE]
        if best_practice_entries:
            insights.append(f"本周有{len(best_practice_entries)}笔交易成功，可总结经验")

        return insights

    def _extract_improvement_suggestions(self, entries: List[TradeJournalEntry]) -> List[str]:
        """提取改进建议"""
        suggestions = []

        for entry in entries:
            if entry.suggested_action and entry.suggested_action not in suggestions:
                suggestions.append(entry.suggested_action)

        return suggestions[:5]  # 最多返回5条建议


# ===========================================================================
# 重复模式检测器
# ===========================================================================

class PatternDetector:
    """
    重复模式检测器

    基于 self-improvement skill 的模式检测概念：
    - 识别重复出现的亏损模式
    - 聚类相似的交易失败
    - 生成模式报告
    """

    def __init__(self, min_occurrences: int = 3):
        self.min_occurrences = min_occurrences
        self.patterns: List[RecurringPattern] = []

    def detect_patterns(self, journal: TradeJournal) -> List[RecurringPattern]:
        """
        检测重复模式

        参数:
            journal: 交易日志

        返回:
            检测到的重复模式列表
        """
        # 获取所有亏损交易的日志
        loss_entries = [e for e in journal.entries
                       if e.category in (EntryCategory.CORRECTION, EntryCategory.ERROR)]

        if len(loss_entries) < self.min_occurrences:
            return []

        # 按标签聚类
        tag_clusters = self._cluster_by_tags(loss_entries)

        # 检测模式
        patterns = []
        for tag, entries in tag_clusters.items():
            if len(entries) >= self.min_occurrences:
                pattern = self._create_pattern(tag, entries)
                patterns.append(pattern)

        # 按严重程度排序
        patterns.sort(key=lambda p: p.severity.value, reverse=True)

        self.patterns = patterns
        return patterns

    def _cluster_by_tags(self, entries: List[TradeJournalEntry]) -> Dict[str, List[TradeJournalEntry]]:
        """按标签聚类"""
        clusters = defaultdict(list)

        for entry in entries:
            for tag in entry.tags:
                # 排除通用标签
                if tag not in ('long', 'short') and not tag.startswith('fault:'):
                    clusters[tag].append(entry)

        return dict(clusters)

    def _create_pattern(self, tag: str, entries: List[TradeJournalEntry]) -> RecurringPattern:
        """创建重复模式"""
        # 计算严重程度
        avg_pnl = np.mean([e.metadata.get('pnl', 0) for e in entries])
        occurrence_count = len(entries)

        if occurrence_count >= 5 and avg_pnl < -1000:
            severity = PatternSeverity.CRITICAL
        elif occurrence_count >= 4 or avg_pnl < -500:
            severity = PatternSeverity.HIGH
        elif occurrence_count >= 3:
            severity = PatternSeverity.MEDIUM
        else:
            severity = PatternSeverity.LOW

        # 提取根因
        root_cause = self._infer_root_cause(tag, entries)

        # 生成修复建议
        suggested_fix = self._generate_fix_suggestion(tag, entries)

        return RecurringPattern(
            pattern_id=f"PAT-{datetime.now().strftime('%Y%m%d')}-{tag}",
            pattern_key=tag,
            description=f"重复出现的{tag}相关亏损模式（{occurrence_count}次）",
            severity=severity,
            occurrence_count=occurrence_count,
            first_seen=min(e.timestamp for e in entries),
            last_seen=max(e.timestamp for e in entries),
            affected_trades=[e.trade_id for e in entries],
            root_cause=root_cause,
            suggested_fix=suggested_fix,
        )

    def _infer_root_cause(self, tag: str, entries: List[TradeJournalEntry]) -> str:
        """推断根因"""
        # 分析最常见的元数据
        market_states = [e.metadata.get('market_state', 'UNKNOWN') for e in entries]
        trend_phases = [e.metadata.get('trend_phase', 'UNKNOWN') for e in entries]
        exit_reasons = [e.metadata.get('exit_reason', 'UNKNOWN') for e in entries]

        state_counter = Counter(market_states)
        phase_counter = Counter(trend_phases)
        exit_counter = Counter(exit_reasons)

        causes = []

        most_common_state = state_counter.most_common(1)[0] if state_counter else None
        if most_common_state and most_common_state[0] != 'UNKNOWN':
            causes.append(f"主要发生在{most_common_state[0]}状态（{most_common_state[1]}次）")

        most_common_phase = phase_counter.most_common(1)[0] if phase_counter else None
        if most_common_phase and most_common_phase[0] != 'UNKNOWN':
            causes.append(f"主要在{most_common_phase[0]}阶段（{most_common_phase[1]}次）")

        most_common_exit = exit_counter.most_common(1)[0] if exit_counter else None
        if most_common_exit and most_common_exit[0] != 'UNKNOWN':
            causes.append(f"主要因{most_common_exit[0]}出场（{most_common_exit[1]}次）")

        return "; ".join(causes) if causes else "需要进一步分析"

    def _generate_fix_suggestion(self, tag: str, entries: List[TradeJournalEntry]) -> str:
        """生成修复建议"""
        suggestions = []

        for entry in entries:
            if entry.suggested_action and entry.suggested_action not in suggestions:
                suggestions.append(entry.suggested_action)

        return suggestions[0] if suggestions else "需要根据具体模式制定修复方案"


# ===========================================================================
# 规则晋升器
# ===========================================================================

class RulePromoter:
    """
    规则晋升器

    基于 self-improvement skill 的晋升概念：
    - 将高价值模式晋升为策略规则
    - 规则具有触发条件和执行动作
    - 跟踪规则的有效性
    """

    def __init__(self, min_occurrences: int = 3, min_severity: str = "medium"):
        self.min_occurrences = min_occurrences
        self.min_severity = min_severity
        self.rules: List[StrategyRule] = []

    def promote_patterns(self, patterns: List[RecurringPattern]) -> List[StrategyRule]:
        """
        将符合条件的模式晋升为规则

        参数:
            patterns: 重复模式列表

        返回:
            新创建的规则列表
        """
        new_rules = []

        for pattern in patterns:
            if self._should_promote(pattern):
                rule = self._create_rule(pattern)
                new_rules.append(rule)
                pattern.promoted = True

        self.rules.extend(new_rules)
        return new_rules

    def _should_promote(self, pattern: RecurringPattern) -> bool:
        """判断是否应该晋升"""
        # 检查出现次数
        if pattern.occurrence_count < self.min_occurrences:
            return False

        # 检查严重程度
        severity_order = ["low", "medium", "high", "critical"]
        if severity_order.index(pattern.severity.value) < severity_order.index(self.min_severity):
            return False

        # 检查是否已晋升
        if pattern.promoted:
            return False

        return True

    def _create_rule(self, pattern: RecurringPattern) -> StrategyRule:
        """从模式创建规则"""
        # 根据模式类型生成规则
        if "range_bound" in pattern.pattern_key:
            return self._create_range_bound_rule(pattern)
        elif "fatiguing" in pattern.pattern_key or "reversing" in pattern.pattern_key:
            return self._create_phase_rule(pattern)
        elif "adx" in pattern.pattern_key:
            return self._create_adx_rule(pattern)
        elif "stop_loss" in pattern.pattern_key:
            return self._create_stop_loss_rule(pattern)
        else:
            return self._create_generic_rule(pattern)

    def _create_range_bound_rule(self, pattern: RecurringPattern) -> StrategyRule:
        """创建震荡市规则"""
        return StrategyRule(
            rule_id=f"RULE-{datetime.now().strftime('%Y%m%d')}-RANGE",
            name="震荡市过滤规则",
            description=f"基于{pattern.occurrence_count}次震荡市亏损经验",
            condition="market_state == 'RANGE_BOUND' AND trend_phase == 'CONSOLIDATING'",
            action="HOLD (不交易)",
            source_pattern=pattern.pattern_id,
        )

    def _create_phase_rule(self, pattern: RecurringPattern) -> StrategyRule:
        """创建阶段规则"""
        return StrategyRule(
            rule_id=f"RULE-{datetime.now().strftime('%Y%m%d')}-PHASE",
            name="趋势阶段过滤规则",
            description=f"基于{pattern.occurrence_count}次阶段错配亏损经验",
            condition="trend_phase IN ('FATIGUING', 'REVERSING')",
            action="HOLD (不交易) OR reduce_position(50%)",
            source_pattern=pattern.pattern_id,
        )

    def _create_adx_rule(self, pattern: RecurringPattern) -> StrategyRule:
        """创建ADX规则"""
        return StrategyRule(
            rule_id=f"RULE-{datetime.now().strftime('%Y%m%d')}-ADX",
            name="ADX过滤规则",
            description=f"基于{pattern.occurrence_count}次ADX不足亏损经验",
            condition="adx < 20 OR adx_pct < 0.5",
            action="HOLD (不交易)",
            source_pattern=pattern.pattern_id,
        )

    def _create_stop_loss_rule(self, pattern: RecurringPattern) -> StrategyRule:
        """创建止损规则"""
        return StrategyRule(
            rule_id=f"RULE-{datetime.now().strftime('%Y%m%d')}-STOP",
            name="止损优化规则",
            description=f"基于{pattern.occurrence_count}次止损问题亏损经验",
            condition="atr_multiplier < 2.0",
            action="SET atr_multiplier = 2.0",
            source_pattern=pattern.pattern_id,
        )

    def _create_generic_rule(self, pattern: RecurringPattern) -> StrategyRule:
        """创建通用规则"""
        return StrategyRule(
            rule_id=f"RULE-{datetime.now().strftime('%Y%m%d')}-GEN",
            name=f"经验规则: {pattern.pattern_key}",
            description=pattern.description,
            condition=f"tag == '{pattern.pattern_key}'",
            action=pattern.suggested_fix,
            source_pattern=pattern.pattern_id,
        )

    def evaluate_rules(self, market_context: Dict[str, Any]) -> List[StrategyRule]:
        """
        评估规则是否应该触发

        参数:
            market_context: 市场上下文

        返回:
            应该触发的规则列表
        """
        triggered = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            if self._check_condition(rule.condition, market_context):
                rule.hit_count += 1
                triggered.append(rule)

        return triggered

    def _check_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """检查规则条件（简化版）"""
        # 简化的条件检查
        if "RANGE_BOUND" in condition:
            return context.get('market_state') == 'RANGE_BOUND'
        elif "FATIGUING" in condition or "REVERSING" in condition:
            return context.get('trend_phase') in ('FATIGUING', 'REVERSING')
        elif "adx < 20" in condition:
            return context.get('adx', 100) < 20
        elif "adx_pct < 0.5" in condition:
            return context.get('adx_pct', 1.0) < 0.5

        return False
