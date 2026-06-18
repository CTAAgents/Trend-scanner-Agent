"""
概念性语言反馈模块

基于 FinCon 论文思想，实现概念性语言强化学习：
1. 自然语言反馈生成
2. 投资信念更新
3. 信念传播机制

版本：v1.0
创建日期：2026-06-15
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """交易结果"""

    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_percent: float
    holding_period: int
    market_state: str
    trend_phase: str
    entry_reason: str
    exit_reason: str
    success_factors: list[str]
    failure_factors: list[str]


@dataclass
class ConceptualFeedback:
    """概念性语言反馈"""

    feedback_id: str
    trade_id: str
    feedback_type: str  # success, failure, neutral
    content: str
    key_lessons: list[str]
    confidence: float
    created_at: str


@dataclass
class InvestmentBelief:
    """投资信念"""

    belief_id: str
    category: str  # entry, exit, position, risk, market
    content: str
    confidence: float
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    created_at: str
    last_updated: str


@dataclass
class BeliefUpdate:
    """信念更新"""

    update_id: str
    belief_id: str
    old_confidence: float
    new_confidence: float
    reason: str
    evidence: str
    created_at: str


class ConceptualFeedbackGenerator:
    """
    概念性语言反馈生成器

    基于交易结果生成自然语言反馈
    """

    def __init__(self, llm_client=None):
        """
        初始化概念性语言反馈生成器

        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
        logger.info("ConceptualFeedbackGenerator 初始化完成")

    def generate_feedback(self, trade_result: TradeResult) -> ConceptualFeedback:
        """
        生成概念性语言反馈

        Args:
            trade_result: 交易结果

        Returns:
            ConceptualFeedback: 概念性语言反馈
        """
        if self.llm_client:
            return self._generate_feedback_with_llm(trade_result)
        else:
            return self._generate_feedback_with_rules(trade_result)

    def _generate_feedback_with_llm(self, trade_result: TradeResult) -> ConceptualFeedback:
        """
        使用 LLM 生成反馈

        Args:
            trade_result: 交易结果

        Returns:
            ConceptualFeedback: 概念性语言反馈
        """
        prompt = f"""
请基于以下交易结果生成概念性语言反馈。

## 交易信息
- 品种: {trade_result.symbol}
- 方向: {trade_result.direction}
- 入场价: {trade_result.entry_price}
- 出场价: {trade_result.exit_price}
- 盈亏: {trade_result.pnl_percent:.2f}%
- 持仓周期: {trade_result.holding_period} 天
- 市场状态: {trade_result.market_state}
- 趋势阶段: {trade_result.trend_phase}
- 入场原因: {trade_result.entry_reason}
- 出场原因: {trade_result.exit_reason}
- 成功因素: {trade_result.success_factors}
- 失败因素: {trade_result.failure_factors}

## 要求
1. 用自然语言描述交易结果和原因
2. 提取关键教训
3. 评估交易质量
4. 提出改进建议

## 输出格式
```json
{{
  "feedback_type": "success/failure/neutral",
  "content": "自然语言反馈内容",
  "key_lessons": ["教训1", "教训2"],
  "confidence": 0.8
}}
```
"""

        try:
            response = self.llm_client.generate(prompt)
            result = self._parse_json_response(response)

            feedback = ConceptualFeedback(
                feedback_id=f"feedback_{trade_result.trade_id}",
                trade_id=trade_result.trade_id,
                feedback_type=result.get("feedback_type", "neutral"),
                content=result.get("content", ""),
                key_lessons=result.get("key_lessons", []),
                confidence=result.get("confidence", 0.5),
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

            return feedback

        except Exception as e:
            logger.error(f"LLM 生成反馈失败: {e}")
            return self._generate_feedback_with_rules(trade_result)

    def _generate_feedback_with_rules(self, trade_result: TradeResult) -> ConceptualFeedback:
        """
        使用规则生成反馈

        Args:
            trade_result: 交易结果

        Returns:
            ConceptualFeedback: 概念性语言反馈
        """
        # 确定反馈类型
        if trade_result.pnl > 0:
            feedback_type = "success"
        elif trade_result.pnl < 0:
            feedback_type = "failure"
        else:
            feedback_type = "neutral"

        # 生成反馈内容
        content = self._generate_content(trade_result, feedback_type)

        # 提取关键教训
        key_lessons = self._extract_key_lessons(trade_result, feedback_type)

        # 计算置信度
        confidence = self._calculate_confidence(trade_result)

        feedback = ConceptualFeedback(
            feedback_id=f"feedback_{trade_result.trade_id}",
            trade_id=trade_result.trade_id,
            feedback_type=feedback_type,
            content=content,
            key_lessons=key_lessons,
            confidence=confidence,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        return feedback

    def _generate_content(self, trade_result: TradeResult, feedback_type: str) -> str:
        """
        生成反馈内容

        Args:
            trade_result: 交易结果
            feedback_type: 反馈类型

        Returns:
            str: 反馈内容
        """
        if feedback_type == "success":
            content = f"交易 {trade_result.symbol} 盈利 {trade_result.pnl_percent:.2f}%。"
            content += f"在 {trade_result.market_state} 市场状态下，"
            content += f"{trade_result.trend_phase} 趋势阶段入场，"
            content += f"持仓 {trade_result.holding_period} 天后出场。"

            if trade_result.success_factors:
                content += f"成功因素：{', '.join(trade_result.success_factors)}。"

        elif feedback_type == "failure":
            content = f"交易 {trade_result.symbol} 亏损 {abs(trade_result.pnl_percent):.2f}%。"
            content += f"在 {trade_result.market_state} 市场状态下，"
            content += f"{trade_result.trend_phase} 趋势阶段入场，"
            content += f"持仓 {trade_result.holding_period} 天后出场。"

            if trade_result.failure_factors:
                content += f"失败因素：{', '.join(trade_result.failure_factors)}。"

        else:
            content = f"交易 {trade_result.symbol} 盈亏平衡。"
            content += f"在 {trade_result.market_state} 市场状态下，"
            content += f"{trade_result.trend_phase} 趋势阶段入场，"
            content += f"持仓 {trade_result.holding_period} 天后出场。"

        return content

    def _extract_key_lessons(self, trade_result: TradeResult, feedback_type: str) -> list[str]:
        """
        提取关键教训

        Args:
            trade_result: 交易结果
            feedback_type: 反馈类型

        Returns:
            list: 关键教训列表
        """
        lessons = []

        if feedback_type == "success":
            # 成功交易的教训
            if trade_result.market_state == "trending":
                lessons.append("在趋势市场中顺势交易是有效的")
            if trade_result.trend_phase == "DEVELOPING":
                lessons.append("在趋势发展阶段入场可以获得较好的收益")
            if trade_result.holding_period <= 5:
                lessons.append("短期持仓可以降低风险")

            # 添加成功因素作为教训
            for factor in trade_result.success_factors:
                lessons.append(f"成功因素: {factor}")

        elif feedback_type == "failure":
            # 失败交易的教训
            if trade_result.market_state == "ranging":
                lessons.append("在震荡市场中交易需要更谨慎")
            if trade_result.trend_phase == "UNKNOWN":
                lessons.append("趋势不明确时应避免入场")
            if trade_result.holding_period > 10:
                lessons.append("长期持仓可能增加风险")

            # 添加失败因素作为教训
            for factor in trade_result.failure_factors:
                lessons.append(f"失败因素: {factor}")

        return lessons

    def _calculate_confidence(self, trade_result: TradeResult) -> float:
        """
        计算置信度

        Args:
            trade_result: 交易结果

        Returns:
            float: 置信度 (0-1)
        """
        confidence = 0.5

        # 根据盈亏调整置信度
        if trade_result.pnl > 0:
            confidence += 0.2
        elif trade_result.pnl < 0:
            confidence -= 0.1

        # 根据持仓周期调整置信度
        if trade_result.holding_period <= 5:
            confidence += 0.1
        elif trade_result.holding_period > 10:
            confidence -= 0.1

        # 根据市场状态调整置信度
        if trade_result.market_state == "trending":
            confidence += 0.1
        elif trade_result.market_state == "ranging":
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """
        解析 JSON 响应

        Args:
            response: LLM 响应

        Returns:
            dict: 解析后的 JSON
        """
        # 尝试从 markdown 代码块中提取
        json_block_pattern = r"```json\s*\n(.*?)```"
        match = re.search(json_block_pattern, response, re.DOTALL)

        if match:
            json_str = match.group(1).strip()
        else:
            # 尝试提取整个响应
            json_pattern = r"(\{.*\})"
            match = re.search(json_pattern, response, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
            else:
                json_str = response.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return {}


class BeliefManager:
    """
    信念管理器

    管理投资信念的创建、更新和查询
    """

    def __init__(self):
        """初始化信念管理器"""
        self.beliefs: dict[str, InvestmentBelief] = {}
        self.belief_updates: list[BeliefUpdate] = []
        logger.info("BeliefManager 初始化完成")

    def create_belief(self, category: str, content: str, confidence: float = 0.5) -> InvestmentBelief:
        """
        创建投资信念

        Args:
            category: 信念类别
            content: 信念内容
            confidence: 置信度

        Returns:
            InvestmentBelief: 投资信念
        """
        belief_id = f"belief_{len(self.beliefs) + 1:03d}"

        belief = InvestmentBelief(
            belief_id=belief_id,
            category=category,
            content=content,
            confidence=confidence,
            supporting_evidence=[],
            contradicting_evidence=[],
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        self.beliefs[belief_id] = belief
        logger.info(f"创建信念: {belief_id}")

        return belief

    def update_belief(self, belief_id: str, new_confidence: float, reason: str, evidence: str) -> BeliefUpdate | None:
        """
        更新投资信念

        Args:
            belief_id: 信念 ID
            new_confidence: 新置信度
            reason: 更新原因
            evidence: 证据

        Returns:
            BeliefUpdate: 信念更新
        """
        if belief_id not in self.beliefs:
            logger.warning(f"信念不存在: {belief_id}")
            return None

        belief = self.beliefs[belief_id]
        old_confidence = belief.confidence

        # 更新信念
        belief.confidence = new_confidence
        belief.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 添加证据
        if new_confidence > old_confidence:
            belief.supporting_evidence.append(evidence)
        else:
            belief.contradicting_evidence.append(evidence)

        # 记录更新
        update = BeliefUpdate(
            update_id=f"update_{len(self.belief_updates) + 1:03d}",
            belief_id=belief_id,
            old_confidence=old_confidence,
            new_confidence=new_confidence,
            reason=reason,
            evidence=evidence,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        self.belief_updates.append(update)
        logger.info(f"更新信念: {belief_id}, 置信度: {old_confidence:.2f} -> {new_confidence:.2f}")

        return update

    def get_belief(self, belief_id: str) -> InvestmentBelief | None:
        """
        获取投资信念

        Args:
            belief_id: 信念 ID

        Returns:
            InvestmentBelief: 投资信念
        """
        return self.beliefs.get(belief_id)

    def get_beliefs_by_category(self, category: str) -> list[InvestmentBelief]:
        """
        根据类别获取信念

        Args:
            category: 信念类别

        Returns:
            list: 信念列表
        """
        return [belief for belief in self.beliefs.values() if belief.category == category]

    def get_all_beliefs(self) -> list[InvestmentBelief]:
        """
        获取所有信念

        Returns:
            list: 信念列表
        """
        return list(self.beliefs.values())

    def update_beliefs_from_feedback(self, feedback: ConceptualFeedback) -> list[BeliefUpdate]:
        """
        从反馈中更新信念

        Args:
            feedback: 概念性语言反馈

        Returns:
            list: 信念更新列表
        """
        updates = []

        # 根据反馈类型更新相关信念
        if feedback.feedback_type == "success":
            # 成功交易增强相关信念
            for lesson in feedback.key_lessons:
                # 查找相关信念
                related_beliefs = self._find_related_beliefs(lesson)
                for belief in related_beliefs:
                    # 增强信念置信度
                    new_confidence = min(1.0, belief.confidence + 0.1)
                    update = self.update_belief(
                        belief.belief_id, new_confidence, f"成功交易验证: {lesson}", feedback.content
                    )
                    if update:
                        updates.append(update)

        elif feedback.feedback_type == "failure":
            # 失败交易削弱相关信念
            for lesson in feedback.key_lessons:
                # 查找相关信念
                related_beliefs = self._find_related_beliefs(lesson)
                for belief in related_beliefs:
                    # 削弱信念置信度
                    new_confidence = max(0.0, belief.confidence - 0.1)
                    update = self.update_belief(
                        belief.belief_id, new_confidence, f"失败交易挑战: {lesson}", feedback.content
                    )
                    if update:
                        updates.append(update)

        return updates

    def _find_related_beliefs(self, lesson: str) -> list[InvestmentBelief]:
        """
        查找相关信念

        Args:
            lesson: 教训

        Returns:
            list: 相关信念列表
        """
        related_beliefs = []

        lesson_lower = lesson.lower()

        for belief in self.beliefs.values():
            belief_lower = belief.content.lower()

            # 简单的关键词匹配
            keywords = ["趋势", "震荡", "入场", "出场", "仓位", "止损", "市场"]
            for keyword in keywords:
                if keyword in lesson_lower and keyword in belief_lower:
                    related_beliefs.append(belief)
                    break

        return related_beliefs


class BeliefPropagation:
    """
    信念传播器

    实现信念在 Agent 间的传播
    """

    def __init__(self):
        """初始化信念传播器"""
        logger.info("BeliefPropagation 初始化完成")

    def propagate_beliefs(
        self, source_beliefs: list[InvestmentBelief], target_agents: list[str], propagation_rules: dict[str, Any] = None
    ) -> dict[str, list[InvestmentBelief]]:
        """
        传播信念到目标 Agent

        Args:
            source_beliefs: 源信念列表
            target_agents: 目标 Agent 列表
            propagation_rules: 传播规则

        Returns:
            dict: 目标 Agent 接收到的信念
        """
        propagation_result = {}

        for agent in target_agents:
            # 根据传播规则筛选信念
            filtered_beliefs = self._filter_beliefs_for_agent(source_beliefs, agent, propagation_rules)
            propagation_result[agent] = filtered_beliefs

        return propagation_result

    def _filter_beliefs_for_agent(
        self, beliefs: list[InvestmentBelief], agent: str, rules: dict[str, Any] = None
    ) -> list[InvestmentBelief]:
        """
        为特定 Agent 筛选信念

        Args:
            beliefs: 信念列表
            agent: 目标 Agent
            rules: 传播规则

        Returns:
            list: 筛选后的信念列表
        """
        filtered_beliefs = []

        # 默认规则：只传播高置信度的信念
        min_confidence = 0.6

        if rules and agent in rules:
            min_confidence = rules[agent].get("min_confidence", 0.6)

        for belief in beliefs:
            if belief.confidence >= min_confidence:
                filtered_beliefs.append(belief)

        return filtered_beliefs


# 示例用法
if __name__ == "__main__":
    # 测试概念性语言反馈生成器
    generator = ConceptualFeedbackGenerator()

    trade_result = TradeResult(
        trade_id="trade_001",
        symbol="DCE.jm2609",
        direction="LONG",
        entry_price=1500,
        exit_price=1550,
        pnl=50,
        pnl_percent=3.33,
        holding_period=4,
        market_state="trending",
        trend_phase="DEVELOPING",
        entry_reason="趋势确认",
        exit_reason="达到目标位",
        success_factors=["趋势确认", "动量充足"],
        failure_factors=[],
    )

    feedback = generator.generate_feedback(trade_result)

    print("概念性语言反馈:")
    print(f"反馈类型: {feedback.feedback_type}")
    print(f"反馈内容: {feedback.content}")
    print(f"关键教训: {feedback.key_lessons}")
    print(f"置信度: {feedback.confidence}")
