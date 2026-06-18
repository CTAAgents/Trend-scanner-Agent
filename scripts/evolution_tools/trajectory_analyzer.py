"""
轨迹感知优化器模块

基于 FactorEngine 论文的轨迹感知优化思想，实现：
1. 交易轨迹分析
2. 失败模式识别
3. 成功模式提取
4. 优化规则生成

版本：v1.0
创建日期：2026-06-15
"""

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """交易记录"""

    trade_id: str
    symbol: str
    direction: str  # LONG, SHORT
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    pnl: float
    pnl_percent: float
    holding_period: int  # 持仓天数

    # 市场状态
    market_state: str  # trending, ranging, volatile
    trend_phase: str  # DEVELOPING, MATURE, EXHAUSTING
    volatility: str  # low, medium, high

    # 技术指标
    er: float
    tsi: float
    rsi: float
    adx: float

    # 风险指标
    max_drawdown: float
    sharpe_ratio: float

    # 失败原因（如果亏损）
    failure_reason: str | None = None

    # 额外信息
    metadata: dict[str, Any] | None = None


@dataclass
class Pattern:
    """模式"""

    pattern_id: str
    pattern_type: str  # success, failure
    description: str
    conditions: dict[str, Any]
    frequency: int
    avg_pnl: float
    confidence: float


@dataclass
class OptimizationRule:
    """优化规则"""

    rule_id: str
    rule_type: str  # avoidance, enhancement, entry, exit
    condition: str
    action: str
    reason: str
    priority: str  # high, medium, low
    source_pattern_id: str


class TrajectoryAnalyzer:
    """
    轨迹分析器

    分析交易轨迹，提取成功和失败模式
    """

    def __init__(self):
        """初始化轨迹分析器"""
        self.trade_history: list[TradeRecord] = []
        self.success_cases: list[TradeRecord] = []
        self.failure_cases: list[TradeRecord] = []
        self.patterns: list[Pattern] = []
        self.optimization_rules: list[OptimizationRule] = []

        logger.info("TrajectoryAnalyzer 初始化完成")

    def load_trade_history(self, trade_history: list[dict[str, Any]]) -> None:
        """
        加载交易历史

        Args:
            trade_history: 交易历史列表
        """
        self.trade_history = []
        for trade_data in trade_history:
            try:
                trade = TradeRecord(**trade_data)
                self.trade_history.append(trade)
            except Exception as e:
                logger.warning(f"解析交易记录失败: {e}")

        logger.info(f"加载了 {len(self.trade_history)} 条交易记录")

    def analyze(self) -> dict[str, Any]:
        """
        分析交易轨迹

        Returns:
            dict: 分析结果
        """
        if not self.trade_history:
            logger.warning("交易历史为空，无法分析")
            return {"error": "交易历史为空"}

        # 1. 分类成功和失败案例
        self._classify_cases()

        # 2. 提取模式
        self._extract_patterns()

        # 3. 生成优化规则
        self._generate_optimization_rules()

        # 4. 生成分析报告
        report = self._generate_report()

        return report

    def _classify_cases(self) -> None:
        """分类成功和失败案例"""
        self.success_cases = []
        self.failure_cases = []

        for trade in self.trade_history:
            if trade.pnl > 0:
                self.success_cases.append(trade)
            else:
                self.failure_cases.append(trade)

        logger.info(f"成功案例: {len(self.success_cases)}, 失败案例: {len(self.failure_cases)}")

    def _extract_patterns(self) -> None:
        """提取模式"""
        self.patterns = []

        # 提取成功模式
        success_patterns = self._extract_success_patterns()
        self.patterns.extend(success_patterns)

        # 提取失败模式
        failure_patterns = self._extract_failure_patterns()
        self.patterns.extend(failure_patterns)

        logger.info(f"提取了 {len(self.patterns)} 个模式")

    def _extract_success_patterns(self) -> list[Pattern]:
        """
        提取成功模式

        Returns:
            list: 成功模式列表
        """
        patterns = []

        if not self.success_cases:
            return patterns

        # 按市场状态分组
        market_state_groups = {}
        for trade in self.success_cases:
            state = trade.market_state
            if state not in market_state_groups:
                market_state_groups[state] = []
            market_state_groups[state].append(trade)

        # 为每个市场状态创建模式
        for state, trades in market_state_groups.items():
            if len(trades) >= 2:  # 至少2个案例才认为是模式
                avg_pnl = sum(t.pnl_percent for t in trades) / len(trades)

                pattern = Pattern(
                    pattern_id=f"success_{state}_{len(patterns) + 1:03d}",
                    pattern_type="success",
                    description=f"在{state}市场状态下的成功交易模式",
                    conditions={
                        "market_state": state,
                        "avg_er": sum(t.er for t in trades) / len(trades),
                        "avg_tsi": sum(t.tsi for t in trades) / len(trades),
                        "avg_rsi": sum(t.rsi for t in trades) / len(trades),
                        "avg_adx": sum(t.adx for t in trades) / len(trades),
                        "avg_holding_period": sum(t.holding_period for t in trades) / len(trades),
                    },
                    frequency=len(trades),
                    avg_pnl=avg_pnl,
                    confidence=min(0.9, len(trades) / 10),  # 案例越多置信度越高
                )
                patterns.append(pattern)

        # 按趋势阶段分组
        trend_phase_groups = {}
        for trade in self.success_cases:
            phase = trade.trend_phase
            if phase not in trend_phase_groups:
                trend_phase_groups[phase] = []
            trend_phase_groups[phase].append(trade)

        for phase, trades in trend_phase_groups.items():
            if len(trades) >= 2:
                avg_pnl = sum(t.pnl_percent for t in trades) / len(trades)

                pattern = Pattern(
                    pattern_id=f"success_{phase}_{len(patterns) + 1:03d}",
                    pattern_type="success",
                    description=f"在{phase}趋势阶段的成功交易模式",
                    conditions={
                        "trend_phase": phase,
                        "avg_er": sum(t.er for t in trades) / len(trades),
                        "avg_tsi": sum(t.tsi for t in trades) / len(trades),
                        "avg_rsi": sum(t.rsi for t in trades) / len(trades),
                        "avg_adx": sum(t.adx for t in trades) / len(trades),
                    },
                    frequency=len(trades),
                    avg_pnl=avg_pnl,
                    confidence=min(0.9, len(trades) / 10),
                )
                patterns.append(pattern)

        return patterns

    def _extract_failure_patterns(self) -> list[Pattern]:
        """
        提取失败模式

        Returns:
            list: 失败模式列表
        """
        patterns = []

        if not self.failure_cases:
            return patterns

        # 按失败原因分组
        failure_reason_groups = {}
        for trade in self.failure_cases:
            reason = trade.failure_reason or "未知原因"
            if reason not in failure_reason_groups:
                failure_reason_groups[reason] = []
            failure_reason_groups[reason].append(trade)

        for reason, trades in failure_reason_groups.items():
            if len(trades) >= 2:
                avg_pnl = sum(t.pnl_percent for t in trades) / len(trades)

                pattern = Pattern(
                    pattern_id=f"failure_{len(patterns) + 1:03d}",
                    pattern_type="failure",
                    description=f"失败原因: {reason}",
                    conditions={
                        "failure_reason": reason,
                        "market_state": self._get_most_common([t.market_state for t in trades]),
                        "trend_phase": self._get_most_common([t.trend_phase for t in trades]),
                        "avg_er": sum(t.er for t in trades) / len(trades),
                        "avg_rsi": sum(t.rsi for t in trades) / len(trades),
                    },
                    frequency=len(trades),
                    avg_pnl=avg_pnl,
                    confidence=min(0.9, len(trades) / 10),
                )
                patterns.append(pattern)

        # 按市场状态分组（失败案例）
        market_state_groups = {}
        for trade in self.failure_cases:
            state = trade.market_state
            if state not in market_state_groups:
                market_state_groups[state] = []
            market_state_groups[state].append(trade)

        for state, trades in market_state_groups.items():
            if len(trades) >= 3:  # 失败模式需要更多案例
                avg_pnl = sum(t.pnl_percent for t in trades) / len(trades)

                pattern = Pattern(
                    pattern_id=f"failure_{state}_{len(patterns) + 1:03d}",
                    pattern_type="failure",
                    description=f"在{state}市场状态下的失败交易模式",
                    conditions={
                        "market_state": state,
                        "avg_er": sum(t.er for t in trades) / len(trades),
                        "avg_tsi": sum(t.tsi for t in trades) / len(trades),
                        "avg_rsi": sum(t.rsi for t in trades) / len(trades),
                        "avg_adx": sum(t.adx for t in trades) / len(trades),
                    },
                    frequency=len(trades),
                    avg_pnl=avg_pnl,
                    confidence=min(0.9, len(trades) / 10),
                )
                patterns.append(pattern)

        return patterns

    def _get_most_common(self, items: list[str]) -> str:
        """获取最常见的元素"""
        if not items:
            return "unknown"
        return max(set(items), key=items.count)

    def _generate_optimization_rules(self) -> None:
        """生成优化规则"""
        self.optimization_rules = []

        for pattern in self.patterns:
            if pattern.pattern_type == "failure":
                # 为失败模式生成避免规则
                rule = self._create_avoidance_rule(pattern)
                if rule:
                    self.optimization_rules.append(rule)
            elif pattern.pattern_type == "success":
                # 为成功模式生成增强规则
                rule = self._create_enhancement_rule(pattern)
                if rule:
                    self.optimization_rules.append(rule)

        logger.info(f"生成了 {len(self.optimization_rules)} 条优化规则")

    def _create_avoidance_rule(self, pattern: Pattern) -> OptimizationRule | None:
        """
        创建避免规则

        Args:
            pattern: 失败模式

        Returns:
            OptimizationRule: 优化规则
        """
        conditions = pattern.conditions

        # 构建条件描述
        condition_parts = []
        if "market_state" in conditions:
            condition_parts.append(f"市场状态为 {conditions['market_state']}")
        if "trend_phase" in conditions:
            condition_parts.append(f"趋势阶段为 {conditions['trend_phase']}")
        if "failure_reason" in conditions:
            condition_parts.append(f"失败原因为 {conditions['failure_reason']}")

        condition_str = " 且 ".join(condition_parts) if condition_parts else "特定条件"

        # 构建动作描述
        action = "避免入场或减小仓位"
        if pattern.avg_pnl < -5:
            action = "避免入场"
        elif pattern.avg_pnl < -2:
            action = "减小仓位至 50%"

        rule = OptimizationRule(
            rule_id=f"avoidance_{pattern.pattern_id}",
            rule_type="avoidance",
            condition=condition_str,
            action=action,
            reason=f"历史失败模式: {pattern.description}",
            priority="high" if pattern.frequency >= 5 else "medium",
            source_pattern_id=pattern.pattern_id,
        )

        return rule

    def _create_enhancement_rule(self, pattern: Pattern) -> OptimizationRule | None:
        """
        创建增强规则

        Args:
            pattern: 成功模式

        Returns:
            OptimizationRule: 优化规则
        """
        conditions = pattern.conditions

        # 构建条件描述
        condition_parts = []
        if "market_state" in conditions:
            condition_parts.append(f"市场状态为 {conditions['market_state']}")
        if "trend_phase" in conditions:
            condition_parts.append(f"趋势阶段为 {conditions['trend_phase']}")

        condition_str = " 且 ".join(condition_parts) if condition_parts else "特定条件"

        # 构建动作描述
        action = "维持标准仓位"
        if pattern.avg_pnl > 5:
            action = "可适当增加仓位至 120%"
        elif pattern.avg_pnl > 2:
            action = "维持标准仓位"

        rule = OptimizationRule(
            rule_id=f"enhancement_{pattern.pattern_id}",
            rule_type="enhancement",
            condition=condition_str,
            action=action,
            reason=f"历史成功模式: {pattern.description}",
            priority="medium" if pattern.frequency >= 3 else "low",
            source_pattern_id=pattern.pattern_id,
        )

        return rule

    def _generate_report(self) -> dict[str, Any]:
        """
        生成分析报告

        Returns:
            dict: 分析报告
        """
        report = {
            "summary": {
                "total_trades": len(self.trade_history),
                "success_count": len(self.success_cases),
                "failure_count": len(self.failure_cases),
                "win_rate": len(self.success_cases) / len(self.trade_history) if self.trade_history else 0,
                "avg_pnl": sum(t.pnl_percent for t in self.trade_history) / len(self.trade_history)
                if self.trade_history
                else 0,
                "avg_success_pnl": sum(t.pnl_percent for t in self.success_cases) / len(self.success_cases)
                if self.success_cases
                else 0,
                "avg_failure_pnl": sum(t.pnl_percent for t in self.failure_cases) / len(self.failure_cases)
                if self.failure_cases
                else 0,
            },
            "patterns": [asdict(p) for p in self.patterns],
            "optimization_rules": [asdict(r) for r in self.optimization_rules],
            "failure_analysis": self._analyze_failures(),
            "success_analysis": self._analyze_successes(),
        }

        return report

    def _analyze_failures(self) -> dict[str, Any]:
        """
        分析失败案例

        Returns:
            dict: 失败分析
        """
        if not self.failure_cases:
            return {"count": 0, "analysis": "无失败案例"}

        # 统计失败原因
        failure_reasons = {}
        for trade in self.failure_cases:
            reason = trade.failure_reason or "未知原因"
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

        # 按市场状态统计
        market_state_stats = {}
        for trade in self.failure_cases:
            state = trade.market_state
            if state not in market_state_stats:
                market_state_stats[state] = {"count": 0, "total_pnl": 0}
            market_state_stats[state]["count"] += 1
            market_state_stats[state]["total_pnl"] += trade.pnl_percent

        for state in market_state_stats:
            stats = market_state_stats[state]
            stats["avg_pnl"] = stats["total_pnl"] / stats["count"]

        return {
            "count": len(self.failure_cases),
            "failure_reasons": failure_reasons,
            "market_state_stats": market_state_stats,
            "avg_loss": sum(t.pnl_percent for t in self.failure_cases) / len(self.failure_cases),
        }

    def _analyze_successes(self) -> dict[str, Any]:
        """
        分析成功案例

        Returns:
            dict: 成功分析
        """
        if not self.success_cases:
            return {"count": 0, "analysis": "无成功案例"}

        # 按市场状态统计
        market_state_stats = {}
        for trade in self.success_cases:
            state = trade.market_state
            if state not in market_state_stats:
                market_state_stats[state] = {"count": 0, "total_pnl": 0}
            market_state_stats[state]["count"] += 1
            market_state_stats[state]["total_pnl"] += trade.pnl_percent

        for state in market_state_stats:
            stats = market_state_stats[state]
            stats["avg_pnl"] = stats["total_pnl"] / stats["count"]

        return {
            "count": len(self.success_cases),
            "market_state_stats": market_state_stats,
            "avg_profit": sum(t.pnl_percent for t in self.success_cases) / len(self.success_cases),
        }


class FailureLearner:
    """
    失败学习器

    从失败案例中学习，生成避免规则
    """

    def __init__(self):
        """初始化失败学习器"""
        logger.info("FailureLearner 初始化完成")

    def learn_from_failures(self, failure_cases: list[TradeRecord]) -> list[OptimizationRule]:
        """
        从失败案例中学习

        Args:
            failure_cases: 失败案例列表

        Returns:
            list: 优化规则列表
        """
        rules = []

        if not failure_cases:
            return rules

        # 按失败原因分组
        failure_reason_groups = {}
        for trade in failure_cases:
            reason = trade.failure_reason or "未知原因"
            if reason not in failure_reason_groups:
                failure_reason_groups[reason] = []
            failure_reason_groups[reason].append(trade)

        # 为每个失败原因生成规则
        for reason, trades in failure_reason_groups.items():
            if len(trades) >= 2:
                rule = self._create_rule_from_failure_reason(reason, trades)
                if rule:
                    rules.append(rule)

        return rules

    def _create_rule_from_failure_reason(self, reason: str, trades: list[TradeRecord]) -> OptimizationRule | None:
        """
        从失败原因创建规则

        Args:
            reason: 失败原因
            trades: 相关交易列表

        Returns:
            OptimizationRule: 优化规则
        """
        # 分析共同特征
        common_features = self._extract_common_features(trades)

        # 构建条件
        condition_parts = []
        if "market_state" in common_features:
            condition_parts.append(f"市场状态为 {common_features['market_state']}")
        if "trend_phase" in common_features:
            condition_parts.append(f"趋势阶段为 {common_features['trend_phase']}")

        condition_str = " 且 ".join(condition_parts) if condition_parts else "特定条件"

        # 构建动作
        avg_pnl = sum(t.pnl_percent for t in trades) / len(trades)
        if avg_pnl < -5:
            action = "避免入场"
        elif avg_pnl < -2:
            action = "减小仓位至 50%"
        else:
            action = "谨慎入场，设置 tight 止损"

        rule = OptimizationRule(
            rule_id=f"failure_learn_{reason[:20]}",
            rule_type="avoidance",
            condition=condition_str,
            action=action,
            reason=f"失败原因: {reason}",
            priority="high" if len(trades) >= 5 else "medium",
            source_pattern_id=f"failure_{reason[:20]}",
        )

        return rule

    def _extract_common_features(self, trades: list[TradeRecord]) -> dict[str, Any]:
        """
        提取共同特征

        Args:
            trades: 交易列表

        Returns:
            dict: 共同特征
        """
        features = {}

        # 市场状态
        market_states = [t.market_state for t in trades]
        features["market_state"] = max(set(market_states), key=market_states.count)

        # 趋势阶段
        trend_phases = [t.trend_phase for t in trades]
        features["trend_phase"] = max(set(trend_phases), key=trend_phases.count)

        # 平均指标
        features["avg_er"] = sum(t.er for t in trades) / len(trades)
        features["avg_tsi"] = sum(t.tsi for t in trades) / len(trades)
        features["avg_rsi"] = sum(t.rsi for t in trades) / len(trades)
        features["avg_adx"] = sum(t.adx for t in trades) / len(trades)

        return features


class OptimizationRuleGenerator:
    """
    优化规则生成器

    基于模式生成优化规则
    """

    def __init__(self):
        """初始化优化规则生成器"""
        logger.info("OptimizationRuleGenerator 初始化完成")

    def generate_rules(self, patterns: list[Pattern]) -> list[OptimizationRule]:
        """
        生成优化规则

        Args:
            patterns: 模式列表

        Returns:
            list: 优化规则列表
        """
        rules = []

        for pattern in patterns:
            if pattern.pattern_type == "failure":
                rule = self._create_avoidance_rule(pattern)
                if rule:
                    rules.append(rule)
            elif pattern.pattern_type == "success":
                rule = self._create_enhancement_rule(pattern)
                if rule:
                    rules.append(rule)

        return rules

    def _create_avoidance_rule(self, pattern: Pattern) -> OptimizationRule | None:
        """创建避免规则"""
        conditions = pattern.conditions

        condition_parts = []
        if "market_state" in conditions:
            condition_parts.append(f"市场状态为 {conditions['market_state']}")
        if "failure_reason" in conditions:
            condition_parts.append(f"失败原因为 {conditions['failure_reason']}")

        condition_str = " 且 ".join(condition_parts) if condition_parts else "特定条件"

        action = "避免入场或减小仓位"
        if pattern.avg_pnl < -5:
            action = "避免入场"

        rule = OptimizationRule(
            rule_id=f"avoidance_{pattern.pattern_id}",
            rule_type="avoidance",
            condition=condition_str,
            action=action,
            reason=f"历史失败模式: {pattern.description}",
            priority="high" if pattern.frequency >= 5 else "medium",
            source_pattern_id=pattern.pattern_id,
        )

        return rule

    def _create_enhancement_rule(self, pattern: Pattern) -> OptimizationRule | None:
        """创建增强规则"""
        conditions = pattern.conditions

        condition_parts = []
        if "market_state" in conditions:
            condition_parts.append(f"市场状态为 {conditions['market_state']}")

        condition_str = " 且 ".join(condition_parts) if condition_parts else "特定条件"

        action = "维持标准仓位"
        if pattern.avg_pnl > 5:
            action = "可适当增加仓位"

        rule = OptimizationRule(
            rule_id=f"enhancement_{pattern.pattern_id}",
            rule_type="enhancement",
            condition=condition_str,
            action=action,
            reason=f"历史成功模式: {pattern.description}",
            priority="medium" if pattern.frequency >= 3 else "low",
            source_pattern_id=pattern.pattern_id,
        )

        return rule


# 示例用法
if __name__ == "__main__":
    # 测试轨迹分析器
    analyzer = TrajectoryAnalyzer()

    # 模拟交易历史
    trade_history = [
        {
            "trade_id": "trade_001",
            "symbol": "DCE.jm2609",
            "direction": "LONG",
            "entry_price": 1500,
            "exit_price": 1550,
            "entry_time": "2026-06-01 10:00:00",
            "exit_time": "2026-06-05 15:00:00",
            "pnl": 50,
            "pnl_percent": 3.33,
            "holding_period": 4,
            "market_state": "trending",
            "trend_phase": "DEVELOPING",
            "volatility": "medium",
            "er": 0.7,
            "tsi": 25.3,
            "rsi": 55,
            "adx": 30,
            "max_drawdown": 1.5,
            "sharpe_ratio": 1.2,
        },
        {
            "trade_id": "trade_002",
            "symbol": "DCE.jm2609",
            "direction": "LONG",
            "entry_price": 1550,
            "exit_price": 1520,
            "entry_time": "2026-06-06 10:00:00",
            "exit_time": "2026-06-08 15:00:00",
            "pnl": -30,
            "pnl_percent": -1.94,
            "holding_period": 2,
            "market_state": "ranging",
            "trend_phase": "UNKNOWN",
            "volatility": "low",
            "er": 0.4,
            "tsi": 5.2,
            "rsi": 48,
            "adx": 15,
            "max_drawdown": 2.5,
            "sharpe_ratio": -0.8,
            "failure_reason": "市场震荡，趋势不明确",
        },
    ]

    analyzer.load_trade_history(trade_history)
    report = analyzer.analyze()

    print("分析报告:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
