"""
自优化闭环模块

职责：
- 进化触发：检测是否需要进化
- 规则晋升：将模式晋升为规则
- 过拟合审计：防止过度优化
- 策略反思：从交易结果中学习

进化流程：
交易执行 → 结果记录 → 轨迹分析 → 故障归因 → 模式检测
    ↑                                              │
    └──────────── 规则优化 ← LLM 反思 ←────────────┘
"""

from datetime import datetime
from typing import Any


class EvolutionTrigger:
    """进化触发器"""

    def __init__(self, memory_manager):
        """
        初始化进化触发器

        Args:
            memory_manager: UnifiedMemoryManager 实例
        """
        self.memory = memory_manager

    def should_evolve(self) -> tuple[bool, str]:
        """
        检查是否应该触发进化

        Returns:
            (是否触发, 触发原因)
        """
        # 获取最近的交易
        recent_trades = self.memory.get_recent_trades(n=20)

        if len(recent_trades) < 3:
            return False, "交易数据不足"

        # 条件1：连续亏损 >= 3 次
        consecutive_losses = self._count_consecutive_losses(recent_trades)
        if consecutive_losses >= 3:
            return True, f"连续亏损{consecutive_losses}次"

        # 条件2：累计亏损 >= 10%
        cumulative_pnl = sum(t.get("pnl_pct", 0) for t in recent_trades[:10])
        if cumulative_pnl <= -10:
            return True, f"累计亏损{cumulative_pnl:.1f}%"

        # 条件3：距上次进化 >= 20 笔交易
        last_evolution = self.memory.get_last_evolution()
        if last_evolution:
            last_evolution_time = last_evolution.get("timestamp", "")
            trades_since = self._count_trades_since(recent_trades, last_evolution_time)
            if trades_since >= 20:
                return True, f"距上次进化{trades_since}笔交易"
        else:
            # 从未进化过
            if len(recent_trades) >= 10:
                return True, "首次进化"

        # 条件4：检测到新模式
        new_patterns = self._detect_new_patterns(recent_trades)
        if len(new_patterns) > 0:
            return True, f"检测到{len(new_patterns)}个新模式"

        return False, "未达到触发条件"

    def _count_consecutive_losses(self, trades: list[dict[str, Any]]) -> int:
        """统计连续亏损次数"""
        count = 0
        for trade in trades:
            if trade.get("pnl_pct", 0) < 0:
                count += 1
            else:
                break
        return count

    def _count_trades_since(self, trades: list[dict[str, Any]], since_time: str) -> int:
        """统计指定时间之后的交易数量"""
        if not since_time:
            return len(trades)

        count = 0
        for trade in trades:
            trade_time = trade.get("timestamp", "")
            if trade_time and trade_time > since_time:
                count += 1
        return count

    def _detect_new_patterns(self, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """检测新模式"""
        patterns = []

        # 按品种分组
        by_symbol = {}
        for trade in trades:
            symbol = trade.get("symbol", "")
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(trade)

        # 检测每个品种的模式
        for symbol, symbol_trades in by_symbol.items():
            if len(symbol_trades) >= 3:
                # 计算胜率
                wins = sum(1 for t in symbol_trades if t.get("pnl_pct", 0) > 0)
                win_rate = wins / len(symbol_trades)

                # 如果胜率异常高或异常低，可能是新模式
                if win_rate > 0.8 or win_rate < 0.2:
                    patterns.append({"symbol": symbol, "win_rate": win_rate, "trade_count": len(symbol_trades)})

        return patterns


class RulePromoter:
    """规则晋升器"""

    def __init__(self, memory_manager):
        """
        初始化规则晋升器

        Args:
            memory_manager: UnifiedMemoryManager 实例
        """
        self.memory = memory_manager

    def promote_pattern_to_rule(self, pattern: dict[str, Any]) -> dict[str, Any] | None:
        """
        将模式晋升为规则

        Args:
            pattern: 模式数据

        Returns:
            晋升的规则，如果不符合条件返回 None
        """
        # 检查晋升条件
        if pattern.get("occurrences", 0) < 5:
            return None  # 样本不足

        if pattern.get("win_rate", 0) < 0.6:
            return None  # 胜率不足

        if pattern.get("confidence", 0) < 0.7:
            return None  # 置信度不足

        # 创建规则
        rule = {
            "rule_id": f"R_{pattern.get('pattern_id', '')}",
            "rule_name": f"从模式 {pattern.get('pattern_name', '')} 晋升",
            "rule_type": self._infer_rule_type(pattern),
            "rule_content": self._generate_rule_content(pattern),
            "applicable_phases": pattern.get("applicable_phases", []),
            "applicable_symbols": pattern.get("applicable_symbols", []),
            "confidence": pattern.get("confidence", 0.5),
            "source": "promoted",
        }

        # 存储规则
        rule_id = self.memory.store_rule(rule)

        # 记录进化历史
        self.memory.record_evolution(
            {
                "timestamp": datetime.now().isoformat(),
                "trigger_reason": "模式晋升",
                "change_type": "pattern_promote",
                "target_id": pattern.get("pattern_id", ""),
                "new_value": rule_id,
                "expected_improvement": pattern.get("avg_pnl", 0),
            }
        )

        return rule

    def _infer_rule_type(self, pattern: dict[str, Any]) -> str:
        """推断规则类型"""
        pattern_type = pattern.get("pattern_type", "")

        if "entry" in pattern_type.lower() or "入场" in pattern_type:
            return "entry"
        elif "exit" in pattern_type.lower() or "出场" in pattern_type:
            return "exit"
        elif "position" in pattern_type.lower() or "仓位" in pattern_type:
            return "position"
        elif "risk" in pattern_type.lower() or "风险" in pattern_type:
            return "risk"
        else:
            return "entry"  # 默认

    def _generate_rule_content(self, pattern: dict[str, Any]) -> str:
        """生成规则内容"""
        conditions = pattern.get("conditions", {})

        # 构建规则描述
        parts = []

        if "symbol" in conditions:
            parts.append(f"品种: {conditions['symbol']}")

        if "trend_phase" in conditions:
            parts.append(f"趋势阶段: {conditions['trend_phase']}")

        if "direction" in conditions:
            parts.append(f"方向: {conditions['direction']}")

        if "er_min" in conditions:
            parts.append(f"ER >= {conditions['er_min']}")

        if "tsi_min" in conditions:
            parts.append(f"TSI >= {conditions['tsi_min']}")

        return " 且 ".join(parts) if parts else "自动生成的规则"


class OverfittingAuditor:
    """过拟合审计器"""

    def __init__(self, memory_manager):
        """
        初始化过拟合审计器

        Args:
            memory_manager: UnifiedMemoryManager 实例
        """
        self.memory = memory_manager

    def audit_rule(self, rule_id: str) -> dict[str, Any]:
        """
        审计规则是否过拟合

        Args:
            rule_id: 规则ID

        Returns:
            审计结果
        """
        # 获取规则
        rules = self.memory.get_active_rules()
        rule = next((r for r in rules if r.get("rule_id") == rule_id), None)

        if not rule:
            return {"rule_id": rule_id, "status": "not_found", "audit_score": 0, "warnings": ["规则不存在"]}

        warnings = []
        audit_score = 1.0  # 初始分数

        # 检查1：触发次数
        trigger_count = rule.get("trigger_count", 0)
        if trigger_count < 10:
            warnings.append(f"触发次数不足（{trigger_count}次），样本量太小")
            audit_score *= 0.8

        # 检查2：胜率异常
        win_rate = rule.get("win_rate", 0)
        if win_rate > 0.9:
            warnings.append(f"胜率异常高（{win_rate:.1%}），可能存在过拟合")
            audit_score *= 0.7
        elif win_rate < 0.3:
            warnings.append(f"胜率过低（{win_rate:.1%}），规则可能无效")
            audit_score *= 0.6

        # 检查3：置信度
        confidence = rule.get("confidence", 0)
        if confidence < 0.5:
            warnings.append(f"置信度过低（{confidence:.2f}），规则不可靠")
            audit_score *= 0.7

        # 检查4：来源
        source = rule.get("source", "")
        if source == "promoted":
            # 晋升的规则需要更多验证
            if trigger_count < 20:
                warnings.append("晋升规则触发次数不足，需要更多验证")
                audit_score *= 0.9

        # 确定状态
        if audit_score >= 0.8:
            status = "healthy"
        elif audit_score >= 0.6:
            status = "warning"
        else:
            status = "critical"

        return {
            "rule_id": rule_id,
            "status": status,
            "audit_score": audit_score,
            "warnings": warnings,
            "trigger_count": trigger_count,
            "win_rate": win_rate,
            "confidence": confidence,
        }

    def audit_all_rules(self) -> list[dict[str, Any]]:
        """审计所有规则"""
        rules = self.memory.get_active_rules()
        results = []

        for rule in rules:
            rule_id = rule.get("rule_id", "")
            if rule_id:
                audit_result = self.audit_rule(rule_id)
                results.append(audit_result)

        return results


class StrategyReflector:
    """策略反思器"""

    def __init__(self, memory_manager):
        """
        初始化策略反思器

        Args:
            memory_manager: UnifiedMemoryManager 实例
        """
        self.memory = memory_manager

    def reflect_on_trade(self, trade: dict[str, Any]) -> dict[str, Any]:
        """
        对单笔交易进行反思

        Args:
            trade: 交易数据

        Returns:
            反思结果
        """
        symbol = trade.get("symbol", "")
        pnl_pct = trade.get("pnl_pct", 0)
        direction = trade.get("direction", "")

        # 获取相似经验
        context = {"symbol": symbol, "direction": direction, "feature_vector": trade.get("feature_vector", [])}
        similar_experiences = self.memory.retrieve_experiences(context, top_k=5)

        # 分析
        analysis = {
            "symbol": symbol,
            "pnl_pct": pnl_pct,
            "direction": direction,
            "similar_experiences_count": len(similar_experiences),
            "lessons": [],
            "patterns": [],
        }

        # 提取教训
        if pnl_pct < 0:
            # 亏损交易
            analysis["lessons"].append(f"{symbol} {direction} 亏损 {pnl_pct:.2f}%")

            # 检查是否有类似的成功经验
            successful_similar = [e for e in similar_experiences if e.get("pnl_pct", 0) > 0]
            if successful_similar:
                analysis["lessons"].append(f"存在{len(successful_similar)}条类似的成功经验，可能是执行问题")
        else:
            # 盈利交易
            analysis["lessons"].append(f"{symbol} {direction} 盈利 {pnl_pct:.2f}%")

            # 检查是否有类似的失败经验
            failed_similar = [e for e in similar_experiences if e.get("pnl_pct", 0) < 0]
            if failed_similar:
                analysis["lessons"].append(f"存在{len(failed_similar)}条类似的失败经验，需要总结成功原因")

        # 检测模式
        if len(similar_experiences) >= 3:
            avg_pnl = sum(e.get("pnl_pct", 0) for e in similar_experiences) / len(similar_experiences)
            if abs(avg_pnl) > 2:
                analysis["patterns"].append(
                    {
                        "type": "recurring",
                        "description": f"{symbol} {direction} 平均盈亏 {avg_pnl:.2f}%",
                        "occurrences": len(similar_experiences),
                    }
                )

        return analysis

    def generate_reflection_report(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        """
        生成反思报告

        Args:
            trades: 交易列表

        Returns:
            反思报告
        """
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
        losing_trades = total_trades - winning_trades

        total_pnl = sum(t.get("pnl_pct", 0) for t in trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

        # 按品种分组
        by_symbol = {}
        for trade in trades:
            symbol = trade.get("symbol", "")
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(trade)

        # 生成报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": winning_trades / total_trades if total_trades > 0 else 0,
                "total_pnl": total_pnl,
                "avg_pnl": avg_pnl,
            },
            "by_symbol": {},
            "lessons": [],
            "recommendations": [],
        }

        # 按品种分析
        for symbol, symbol_trades in by_symbol.items():
            symbol_wins = sum(1 for t in symbol_trades if t.get("pnl_pct", 0) > 0)
            symbol_pnl = sum(t.get("pnl_pct", 0) for t in symbol_trades)

            report["by_symbol"][symbol] = {
                "trade_count": len(symbol_trades),
                "win_rate": symbol_wins / len(symbol_trades) if symbol_trades else 0,
                "total_pnl": symbol_pnl,
            }

        # 提取教训
        if losing_trades > winning_trades:
            report["lessons"].append("亏损交易多于盈利交易，需要优化入场条件")

        if avg_pnl < 0:
            report["lessons"].append("平均盈亏为负，需要提高盈利能力")

        # 生成建议
        if report["summary"]["win_rate"] < 0.4:
            report["recommendations"].append("胜率过低，建议收紧入场条件")

        if report["summary"]["avg_pnl"] < 0:
            report["recommendations"].append("平均盈亏为负，建议优化止损止盈")

        return report
