"""
技能感知反思模块

基于 EmbodiSkill (arXiv:2605.10332) 的核心思想：
- 区分"技能内容错误"与"执行失误"
- 针对性修订：技能错误→更新规则，执行错误→保留并强化指导
- 从成功和失败的交易中持续学习

核心理念：
交易失败可能源于两种原因：
1. 策略规则本身有问题（skill content error）→ 需要更新规则
2. 交易者未遵循正确的策略规则（execution error）→ 需要强化执行纪律

这个模块能够智能区分这两种情况，并采取不同的进化策略。
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ===========================================================================
# 数据结构定义
# ===========================================================================


class EvidenceType(Enum):
    """证据类型"""

    SKILL_CONTENT_ERROR = "skill_content_error"  # 技能内容错误
    EXECUTION_ERROR = "execution_error"  # 执行失误
    MIXED = "mixed"  # 混合型
    NO_EVIDENCE = "no_evidence"  # 无明确证据


class RevisionAction(Enum):
    """修订动作"""

    UPDATE_RULE = "update_rule"  # 更新策略规则
    REINFORCE_GUIDANCE = "reinforce_guidance"  # 强化执行指导
    MAINTAIN = "maintain"  # 保持现状
    INVESTIGATE = "investigate"  # 需要进一步调查


@dataclass
class ReflectionEvidence:
    """反思证据"""

    evidence_id: str
    evidence_type: EvidenceType
    confidence: float  # 0-1，证据置信度
    description: str
    supporting_data: dict[str, Any] = field(default_factory=dict)
    trade_ids: list[str] = field(default_factory=list)


@dataclass
class SkillReflection:
    """技能反思结果"""

    reflection_id: str
    strategy_name: str
    evidence_type: EvidenceType
    confidence: float  # 0-1，整体置信度
    description: str
    evidences: list[ReflectionEvidence] = field(default_factory=list)
    recommended_action: RevisionAction = RevisionAction.MAINTAIN
    reasoning: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GuidanceReinforcement:
    """指导强化记录"""

    guidance_id: str
    strategy_name: str
    original_guidance: str
    reinforced_guidance: str
    reason: str
    execution_errors_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)


# ===========================================================================
# 技能感知反思器
# ===========================================================================


class SkillAwareReflector:
    """
    技能感知反思器

    基于 EmbodiSkill 的核心机制：
    1. 分析交易轨迹，区分技能内容错误和执行失误
    2. 对技能内容错误：生成修订建议
    3. 对执行失误：保留并强化有效指导
    """

    def __init__(self):
        self.reflections: list[SkillReflection] = []
        self.guidance_reinforcements: list[GuidanceReinforcement] = []

    def reflect_on_trade(
        self, trade, trajectory_analysis: dict[str, Any] = None, fault_attribution: dict[str, Any] = None
    ) -> SkillReflection:
        """
        对单笔交易进行技能感知反思

        参数:
            trade: TradeRecord 对象
            trajectory_analysis: 轨迹分析结果
            fault_attribution: 故障归因结果

        返回:
            SkillReflection 对象
        """
        # 收集证据
        evidences = []

        # 1. 分析入场决策
        entry_evidence = self._analyze_entry_decision(trade, fault_attribution)
        if entry_evidence:
            evidences.append(entry_evidence)

        # 2. 分析持仓期间行为
        holding_evidence = self._analyze_holding_behavior(trade, trajectory_analysis)
        if holding_evidence:
            evidences.extend(holding_evidence)

        # 3. 分析出场决策
        exit_evidence = self._analyze_exit_decision(trade, fault_attribution)
        if exit_evidence:
            evidences.append(exit_evidence)

        # 4. 综合判断证据类型
        evidence_type, confidence = self._aggregate_evidence(evidences)

        # 5. 生成推荐动作
        recommended_action, reasoning = self._determine_action(evidence_type, confidence, trade, evidences)

        # 6. 生成描述
        description = self._generate_description(trade, evidence_type, recommended_action, evidences)

        reflection = SkillReflection(
            reflection_id=f"REF-{datetime.now().strftime('%Y%m%d')}-{trade.trade_id}",
            strategy_name=self._identify_primary_strategy(trade),
            evidence_type=evidence_type,
            confidence=confidence,
            description=description,
            evidences=evidences,
            recommended_action=recommended_action,
            reasoning=reasoning,
        )

        self.reflections.append(reflection)

        # 7. 如果是执行失误，生成指导强化记录
        if evidence_type == EvidenceType.EXECUTION_ERROR:
            self._create_guidance_reinforcement(trade, reflection)

        return reflection

    def _analyze_entry_decision(self, trade, fault_attribution: dict[str, Any] = None) -> ReflectionEvidence | None:
        """分析入场决策"""
        if not fault_attribution or not fault_attribution.get("has_fault"):
            return None

        faults = fault_attribution.get("faults", [])
        entry_faults = [f for f in faults if f.step_id == 0]

        if not entry_faults:
            return None

        # 检查入场时是否有明确的策略规则违反
        skill_content_errors = []
        execution_errors = []

        for fault in entry_faults:
            # 检查是否是策略规则本身的问题
            if self._is_skill_content_error(fault, trade):
                skill_content_errors.append(fault)
            # 检查是否是执行问题（策略规则正确但未遵循）
            elif self._is_execution_error(fault, trade):
                execution_errors.append(fault)

        if skill_content_errors:
            return ReflectionEvidence(
                evidence_id=f"EVE-{datetime.now().strftime('%Y%m%d')}-ENTRY-SKILL",
                evidence_type=EvidenceType.SKILL_CONTENT_ERROR,
                confidence=0.8,
                description=f"入场时存在{len(skill_content_errors)}个技能内容错误",
                supporting_data={"faults": [f.description for f in skill_content_errors]},
                trade_ids=[trade.trade_id],
            )
        elif execution_errors:
            return ReflectionEvidence(
                evidence_id=f"EVE-{datetime.now().strftime('%Y%m%d')}-ENTRY-EXEC",
                evidence_type=EvidenceType.EXECUTION_ERROR,
                confidence=0.7,
                description=f"入场时存在{len(execution_errors)}个执行失误",
                supporting_data={"faults": [f.description for f in execution_errors]},
                trade_ids=[trade.trade_id],
            )

        return None

    def _analyze_holding_behavior(self, trade, trajectory_analysis: dict[str, Any] = None) -> list[ReflectionEvidence]:
        """分析持仓期间行为"""
        evidences = []

        if not trajectory_analysis:
            return evidences

        metrics = trajectory_analysis.get("metrics", {})
        trajectory = trajectory_analysis.get("trajectory")

        if not trajectory:
            return evidences

        # 检查持仓期间的指标变化
        holding_steps = [s for s in trajectory.steps if s.phase == "holding"]

        if len(holding_steps) < 2:
            return evidences

        # 检查1: 持仓期间是否有明确的出场信号被忽略
        direction = trade.direction
        for step in holding_steps:
            rsi = step.indicators.get("rsi", 50)

            # 多头持仓时RSI超买但未出场
            if direction == "LONG" and rsi > 80:
                evidences.append(
                    ReflectionEvidence(
                        evidence_id=f"EVE-{datetime.now().strftime('%Y%m%d')}-HOLD-RSI",
                        evidence_type=EvidenceType.EXECUTION_ERROR,
                        confidence=0.6,
                        description=f"持仓期间RSI={rsi:.1f}超买但未及时出场",
                        supporting_data={"rsi": rsi, "step_id": step.step_id},
                        trade_ids=[trade.trade_id],
                    )
                )
                break

            # 空头持仓时RSI超卖但未出场
            if direction == "SHORT" and rsi < 20:
                evidences.append(
                    ReflectionEvidence(
                        evidence_id=f"EVE-{datetime.now().strftime('%Y%m%d')}-HOLD-RSI",
                        evidence_type=EvidenceType.EXECUTION_ERROR,
                        confidence=0.6,
                        description=f"持仓期间RSI={rsi:.1f}超卖但未及时出场",
                        supporting_data={"rsi": rsi, "step_id": step.step_id},
                        trade_ids=[trade.trade_id],
                    )
                )
                break

        # 检查2: 持仓期间ADX持续下降（趋势衰减）
        adx_values = [s.indicators.get("adx", 0) for s in holding_steps if s.indicators.get("adx", 0) > 0]
        if len(adx_values) >= 3:
            adx_decline = adx_values[0] - adx_values[-1]
            if adx_decline > 15 and adx_values[0] > 25:
                # 这可能是技能内容错误（策略规则应该包含ADX衰减出场条件）
                evidences.append(
                    ReflectionEvidence(
                        evidence_id=f"EVE-{datetime.now().strftime('%Y%m%d')}-HOLD-ADX",
                        evidence_type=EvidenceType.SKILL_CONTENT_ERROR,
                        confidence=0.7,
                        description=f"持仓期间ADX从{adx_values[0]:.1f}下降到{adx_values[-1]:.1f}，策略缺少趋势衰减出场规则",
                        supporting_data={"adx_start": adx_values[0], "adx_end": adx_values[-1]},
                        trade_ids=[trade.trade_id],
                    )
                )

        return evidences

    def _analyze_exit_decision(self, trade, fault_attribution: dict[str, Any] = None) -> ReflectionEvidence | None:
        """分析出场决策"""
        if not fault_attribution or not fault_attribution.get("has_fault"):
            return None

        faults = fault_attribution.get("faults", [])
        exit_faults = [f for f in faults if f.step_id > 0]

        if not exit_faults:
            return None

        # 检查出场故障类型
        for fault in exit_faults:
            if "止损过紧" in fault.description or "过早离场" in fault.description:
                # 止损过紧可能是技能内容错误（止损参数设置不合理）
                return ReflectionEvidence(
                    evidence_id=f"EVE-{datetime.now().strftime('%Y%m%d')}-EXIT-SKILL",
                    evidence_type=EvidenceType.SKILL_CONTENT_ERROR,
                    confidence=0.7,
                    description=f"出场时止损设置不合理: {fault.description}",
                    supporting_data={"fault": fault.description},
                    trade_ids=[trade.trade_id],
                )

        return None

    def _is_skill_content_error(self, fault, trade) -> bool:
        """判断是否是技能内容错误"""
        # 阶段错配：策略规则应该过滤掉不合适的市场阶段
        if fault.fault_type.value == "phase_mismatch":
            return True

        # 策略冲突：策略规则应该处理信号冲突
        if fault.fault_type.value == "strategy_conflict":
            return True

        # ADX不足但入场：策略规则应该包含ADX过滤
        if fault.fault_type.value == "indicator_misuse" and "ADX" in fault.description:
            return True

        return False

    def _is_execution_error(self, fault, trade) -> bool:
        """判断是否是执行失误"""
        # 时机错误：交易者应该在正确时机入场/出场
        if fault.fault_type.value == "timing_error":
            return True

        # 风控失误：交易者应该遵循风控规则
        if fault.fault_type.value == "risk_mismanagement":
            return True

        return False

    def _aggregate_evidence(self, evidences: list[ReflectionEvidence]) -> tuple[EvidenceType, float]:
        """综合判断证据类型"""
        if not evidences:
            return EvidenceType.NO_EVIDENCE, 0.0

        # 统计各类证据的数量和置信度
        skill_content_count = 0
        execution_count = 0
        skill_content_confidence = 0.0
        execution_confidence = 0.0

        for evidence in evidences:
            if evidence.evidence_type == EvidenceType.SKILL_CONTENT_ERROR:
                skill_content_count += 1
                skill_content_confidence += evidence.confidence
            elif evidence.evidence_type == EvidenceType.EXECUTION_ERROR:
                execution_count += 1
                execution_confidence += evidence.confidence

        # 计算平均置信度
        if skill_content_count > 0:
            skill_content_confidence /= skill_content_count
        if execution_count > 0:
            execution_confidence /= execution_count

        # 判断主要证据类型
        if skill_content_count > 0 and execution_count > 0:
            # 混合型
            confidence = (skill_content_confidence + execution_confidence) / 2
            return EvidenceType.MIXED, confidence
        elif skill_content_count > 0:
            return EvidenceType.SKILL_CONTENT_ERROR, skill_content_confidence
        elif execution_count > 0:
            return EvidenceType.EXECUTION_ERROR, execution_confidence
        else:
            return EvidenceType.NO_EVIDENCE, 0.0

    def _determine_action(
        self, evidence_type: EvidenceType, confidence: float, trade, evidences: list[ReflectionEvidence]
    ) -> tuple[RevisionAction, str]:
        """确定推荐动作"""
        if evidence_type == EvidenceType.NO_EVIDENCE:
            return RevisionAction.MAINTAIN, "无明确证据，保持现状"

        if confidence < 0.5:
            return RevisionAction.INVESTIGATE, f"证据置信度不足({confidence:.2f})，需要进一步调查"

        if evidence_type == EvidenceType.SKILL_CONTENT_ERROR:
            # 技能内容错误：需要更新规则
            return RevisionAction.UPDATE_RULE, "检测到策略规则本身存在问题，需要更新规则"

        elif evidence_type == EvidenceType.EXECUTION_ERROR:
            # 执行失误：保留并强化指导
            return RevisionAction.REINFORCE_GUIDANCE, "检测到执行失误，需要强化执行纪律"

        elif evidence_type == EvidenceType.MIXED:
            # 混合型：优先更新规则，同时强化指导
            return RevisionAction.UPDATE_RULE, "检测到混合型问题，优先更新规则并强化指导"

        return RevisionAction.MAINTAIN, "保持现状"

    def _generate_description(
        self, trade, evidence_type: EvidenceType, action: RevisionAction, evidences: list[ReflectionEvidence]
    ) -> str:
        """生成描述"""
        direction = "多头" if trade.direction == "LONG" else "空头"
        pnl_str = f"+{trade.pnl:.0f}" if trade.pnl > 0 else f"{trade.pnl:.0f}"

        if evidence_type == EvidenceType.SKILL_CONTENT_ERROR:
            return f"{direction}交易{pnl_str}亏损，策略规则本身存在问题，需要更新规则"
        elif evidence_type == EvidenceType.EXECUTION_ERROR:
            return f"{direction}交易{pnl_str}亏损，执行失误，需要强化执行纪律"
        elif evidence_type == EvidenceType.MIXED:
            return f"{direction}交易{pnl_str}亏损，存在技能内容错误和执行失误，需要综合改进"
        else:
            return f"{direction}交易{pnl_str}，无明确证据"

    def _identify_primary_strategy(self, trade) -> str:
        """识别主要责任策略"""
        if trade.strategy_votes_at_entry:
            # 找到与交易方向一致的策略
            direction = trade.direction
            for strategy, vote in trade.strategy_votes_at_entry.items():
                if (direction == "LONG" and "多" in vote) or (direction == "SHORT" and "空" in vote):
                    return strategy
        return "UNKNOWN"

    def _create_guidance_reinforcement(self, trade, reflection: SkillReflection):
        """创建指导强化记录"""
        # 生成强化后的指导
        original_guidance = self._get_original_guidance(trade)
        reinforced_guidance = self._generate_reinforced_guidance(trade, reflection)

        reinforcement = GuidanceReinforcement(
            guidance_id=f"GRF-{datetime.now().strftime('%Y%m%d')}-{trade.trade_id}",
            strategy_name=reflection.strategy_name,
            original_guidance=original_guidance,
            reinforced_guidance=reinforced_guidance,
            reason=reflection.description,
            execution_errors_count=1,
        )

        self.guidance_reinforcements.append(reinforcement)

    def _get_original_guidance(self, trade) -> str:
        """获取原始指导"""
        # 这里可以从策略规则库中获取
        return f"执行{trade.direction}交易，止损{trade.stop_loss}"

    def _generate_reinforced_guidance(self, trade, reflection: SkillReflection) -> str:
        """生成强化后的指导"""
        direction = "多头" if trade.direction == "LONG" else "空头"

        # 根据证据类型生成强化指导
        for evidence in reflection.evidences:
            if evidence.evidence_type == EvidenceType.EXECUTION_ERROR:
                if "RSI" in evidence.description:
                    return f"强化：{direction}持仓期间，RSI>80必须出场，RSI<20必须出场"
                elif "止损" in evidence.description:
                    return f"强化：{direction}交易止损距离必须≥1.5倍ATR"

        return f"强化：严格执行{direction}交易的入场和出场规则"

    def get_skill_content_errors(self) -> list[SkillReflection]:
        """获取所有技能内容错误的反思"""
        return [r for r in self.reflections if r.evidence_type == EvidenceType.SKILL_CONTENT_ERROR]

    def get_execution_errors(self) -> list[SkillReflection]:
        """获取所有执行失误的反思"""
        return [r for r in self.reflections if r.evidence_type == EvidenceType.EXECUTION_ERROR]

    def get_reinforcement_guidance(self) -> list[GuidanceReinforcement]:
        """获取所有指导强化记录"""
        return self.guidance_reinforcements

    def generate_summary_report(self) -> dict[str, Any]:
        """生成反思汇总报告"""
        total = len(self.reflections)
        if total == 0:
            return {"message": "无反思记录"}

        skill_content_errors = len(self.get_skill_content_errors())
        execution_errors = len(self.get_execution_errors())
        mixed = len([r for r in self.reflections if r.evidence_type == EvidenceType.MIXED])
        no_evidence = len([r for r in self.reflections if r.evidence_type == EvidenceType.NO_EVIDENCE])

        # 统计推荐动作
        action_counts = defaultdict(int)
        for r in self.reflections:
            action_counts[r.recommended_action.value] += 1

        return {
            "total_reflections": total,
            "evidence_distribution": {
                "skill_content_error": skill_content_errors,
                "execution_error": execution_errors,
                "mixed": mixed,
                "no_evidence": no_evidence,
            },
            "action_distribution": dict(action_counts),
            "guidance_reinforcements": len(self.guidance_reinforcements),
            "key_insights": self._extract_key_insights(),
        }

    def _extract_key_insights(self) -> list[str]:
        """提取关键洞察"""
        insights = []

        skill_errors = self.get_skill_content_errors()
        exec_errors = self.get_execution_errors()

        if skill_errors:
            # 找出最常见的技能内容错误类型
            error_descriptions = [e.description for e in skill_errors]
            if any("阶段错配" in d for d in error_descriptions):
                insights.append("策略规则缺少足够的市场阶段过滤条件")
            if any("止损" in d for d in error_descriptions):
                insights.append("止损参数设置需要优化")
            if any("ADX" in d for d in error_descriptions):
                insights.append("需要加强ADX趋势强度过滤")

        if exec_errors:
            # 找出最常见的执行失误类型
            error_descriptions = [e.description for e in exec_errors]
            if any("RSI" in d for d in error_descriptions):
                insights.append("需要强化RSI超买/超卖出场纪律")
            if any("止损" in d for d in error_descriptions):
                insights.append("需要严格执行止损规则")

        return insights[:5]  # 最多返回5条洞察
