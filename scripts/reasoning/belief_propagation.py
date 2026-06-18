"""
信念传播模块

基于 FinCon 论文思想，实现信念在 Agent 间的传播：
1. 信念筛选
2. 信念传播
3. 信念同步

版本：v1.0
创建日期：2026-06-15
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class PropagationRule:
    """传播规则"""

    rule_id: str
    source_agent: str
    target_agent: str
    belief_categories: list[str]
    min_confidence: float
    max_beliefs: int
    priority: str  # high, medium, low


@dataclass
class PropagationResult:
    """传播结果"""

    result_id: str
    source_agent: str
    target_agent: str
    beliefs_propagated: int
    beliefs_filtered: int
    propagation_time: str
    success: bool


class BeliefPropagationManager:
    """
    信念传播管理器

    管理信念在 Agent 间的传播
    """

    def __init__(self):
        """初始化信念传播管理器"""
        self.propagation_rules: dict[str, PropagationRule] = {}
        self.propagation_history: list[PropagationResult] = []
        logger.info("BeliefPropagationManager 初始化完成")

    def add_rule(self, rule: PropagationRule) -> None:
        """
        添加传播规则

        Args:
            rule: 传播规则
        """
        self.propagation_rules[rule.rule_id] = rule
        logger.info(f"添加传播规则: {rule.rule_id}")

    def remove_rule(self, rule_id: str) -> bool:
        """
        移除传播规则

        Args:
            rule_id: 规则 ID

        Returns:
            bool: 是否移除成功
        """
        if rule_id in self.propagation_rules:
            del self.propagation_rules[rule_id]
            logger.info(f"移除传播规则: {rule_id}")
            return True
        return False

    def propagate_beliefs(self, source_agent: str, target_agent: str, beliefs: list[Any]) -> PropagationResult:
        """
        传播信念

        Args:
            source_agent: 源 Agent
            target_agent: 目标 Agent
            beliefs: 信念列表

        Returns:
            PropagationResult: 传播结果
        """
        # 查找匹配的传播规则
        rule = self._find_matching_rule(source_agent, target_agent)

        if not rule:
            logger.warning(f"未找到匹配的传播规则: {source_agent} -> {target_agent}")
            return PropagationResult(
                result_id=f"result_{len(self.propagation_history) + 1:03d}",
                source_agent=source_agent,
                target_agent=target_agent,
                beliefs_propagated=0,
                beliefs_filtered=len(beliefs),
                propagation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                success=False,
            )

        # 筛选信念
        filtered_beliefs = self._filter_beliefs(beliefs, rule)

        # 记录传播结果
        result = PropagationResult(
            result_id=f"result_{len(self.propagation_history) + 1:03d}",
            source_agent=source_agent,
            target_agent=target_agent,
            beliefs_propagated=len(filtered_beliefs),
            beliefs_filtered=len(beliefs) - len(filtered_beliefs),
            propagation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            success=True,
        )

        self.propagation_history.append(result)

        logger.info(f"传播信念: {source_agent} -> {target_agent}, 传播 {len(filtered_beliefs)} 个信念")

        return result

    def _find_matching_rule(self, source_agent: str, target_agent: str) -> PropagationRule | None:
        """
        查找匹配的传播规则

        Args:
            source_agent: 源 Agent
            target_agent: 目标 Agent

        Returns:
            PropagationRule: 匹配的传播规则
        """
        for rule in self.propagation_rules.values():
            if rule.source_agent == source_agent and rule.target_agent == target_agent:
                return rule
        return None

    def _filter_beliefs(self, beliefs: list[Any], rule: PropagationRule) -> list[Any]:
        """
        筛选信念

        Args:
            beliefs: 信念列表
            rule: 传播规则

        Returns:
            list: 筛选后的信念列表
        """
        filtered_beliefs = []

        for belief in beliefs:
            # 检查置信度
            if hasattr(belief, "confidence"):
                if belief.confidence < rule.min_confidence:
                    continue

            # 检查类别
            if hasattr(belief, "category"):
                if rule.belief_categories and belief.category not in rule.belief_categories:
                    continue

            filtered_beliefs.append(belief)

            # 检查数量限制
            if len(filtered_beliefs) >= rule.max_beliefs:
                break

        return filtered_beliefs

    def get_propagation_history(self) -> list[PropagationResult]:
        """
        获取传播历史

        Returns:
            list: 传播历史列表
        """
        return self.propagation_history

    def get_rules_for_agent(self, agent: str) -> list[PropagationRule]:
        """
        获取 Agent 相关的传播规则

        Args:
            agent: Agent 名称

        Returns:
            list: 传播规则列表
        """
        rules = []
        for rule in self.propagation_rules.values():
            if rule.source_agent == agent or rule.target_agent == agent:
                rules.append(rule)
        return rules


class BeliefSynchronizer:
    """
    信念同步器

    同步不同 Agent 间的信念
    """

    def __init__(self):
        """初始化信念同步器"""
        logger.info("BeliefSynchronizer 初始化完成")

    def synchronize_beliefs(self, agent_beliefs: dict[str, list[Any]]) -> dict[str, list[Any]]:
        """
        同步信念

        Args:
            agent_beliefs: Agent 信念字典

        Returns:
            dict: 同步后的 Agent 信念字典
        """
        # 收集所有信念
        all_beliefs = []
        for beliefs in agent_beliefs.values():
            all_beliefs.extend(beliefs)

        # 去重
        unique_beliefs = self._deduplicate_beliefs(all_beliefs)

        # 分配信念到 Agent
        synchronized_beliefs = self._distribute_beliefs(unique_beliefs, agent_beliefs.keys())

        return synchronized_beliefs

    def _deduplicate_beliefs(self, beliefs: list[Any]) -> list[Any]:
        """
        去重信念

        Args:
            beliefs: 信念列表

        Returns:
            list: 去重后的信念列表
        """
        seen_contents = set()
        unique_beliefs = []

        for belief in beliefs:
            if hasattr(belief, "content"):
                if belief.content not in seen_contents:
                    seen_contents.add(belief.content)
                    unique_beliefs.append(belief)
            else:
                unique_beliefs.append(belief)

        return unique_beliefs

    def _distribute_beliefs(self, beliefs: list[Any], agents: list[str]) -> dict[str, list[Any]]:
        """
        分配信念到 Agent

        Args:
            beliefs: 信念列表
            agents: Agent 列表

        Returns:
            dict: Agent 信念字典
        """
        # 简单策略：所有 Agent 共享所有信念
        synchronized_beliefs = {}
        for agent in agents:
            synchronized_beliefs[agent] = beliefs.copy()

        return synchronized_beliefs


# 示例用法
if __name__ == "__main__":
    # 测试信念传播管理器
    manager = BeliefPropagationManager()

    # 添加传播规则
    rule = PropagationRule(
        rule_id="rule_001",
        source_agent="reasoner",
        target_agent="debater",
        belief_categories=["entry", "exit"],
        min_confidence=0.6,
        max_beliefs=5,
        priority="high",
    )

    manager.add_rule(rule)

    # 模拟信念传播
    from trend_scanner.conceptual_feedback import InvestmentBelief

    beliefs = [
        InvestmentBelief(
            belief_id="belief_001",
            category="entry",
            content="趋势确认后入场",
            confidence=0.8,
            supporting_evidence=["历史成功案例"],
            contradicting_evidence=[],
            created_at="2026-06-15 17:00:00",
            last_updated="2026-06-15 17:00:00",
        )
    ]

    result = manager.propagate_beliefs("reasoner", "debater", beliefs)

    print("传播结果:")
    print(f"源 Agent: {result.source_agent}")
    print(f"目标 Agent: {result.target_agent}")
    print(f"传播信念数: {result.beliefs_propagated}")
    print(f"过滤信念数: {result.beliefs_filtered}")
    print(f"成功: {result.success}")
