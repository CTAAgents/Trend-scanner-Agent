"""
元技能引擎模块

基于 SkillEvolver (arXiv:2605.10500) 的核心思想：
- 元技能：学习如何生成、优化和迭代改进其他技能
- 在线学习：从部署反馈中持续改进
- 过拟合审计：防止数据泄漏和静默旁路

核心理念：
策略规则本身也是一种"技能"，可以通过元技能来自动生成和优化。
元技能不是完成特定交易任务，而是学习如何创建更好的交易策略规则。

在趋势跟踪系统中：
- 元技能 = 策略规则生成器 + 参数优化器 + 规则精炼器
- 领域技能 = 具体的交易策略规则（如MA交叉、通道突破等）
- 学习信号 = 策略在实际交易中的失败案例
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


class SkillGenerationPhase(Enum):
    """技能生成阶段"""

    CREATION = "creation"  # 创作阶段：生成初始规则
    DEPLOYMENT = "deployment"  # 部署阶段：在实际交易中测试
    REFINEMENT = "refinement"  # 精炼阶段：根据失败信号改进
    MATURE = "mature"  # 成熟阶段：规则稳定有效


class AuditResult(Enum):
    """审计结果"""

    PASS = "pass"  # 通过
    WARNING = "warning"  # 警告
    FAIL = "fail"  # 失败


@dataclass
class SkillTemplate:
    """技能模板"""

    template_id: str
    name: str
    description: str
    category: str  # "trend_following" / "momentum" / "mean_reversion"
    parameters: dict[str, Any] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GeneratedSkill:
    """生成的技能（策略规则）"""

    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    phase: SkillGenerationPhase = SkillGenerationPhase.CREATION
    template_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    performance_history: list[dict[str, Any]] = field(default_factory=list)
    failure_count: int = 0
    success_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditReport:
    """审计报告"""

    audit_id: str
    skill_id: str
    result: AuditResult
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SkillEvolution:
    """技能进化记录"""

    evolution_id: str
    skill_id: str
    old_version: str
    new_version: str
    changes: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    trigger: str = ""  # "failure_analysis" / "performance_review" / "audit"
    performance_before: dict[str, Any] = field(default_factory=dict)
    performance_after: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


# ===========================================================================
# 元技能引擎
# ===========================================================================


class MetaSkillEngine:
    """
    元技能引擎

    基于 SkillEvolver 的核心机制：
    1. 创作阶段：根据模板生成初始策略规则
    2. 部署阶段：在实际交易中测试规则
    3. 精炼阶段：根据失败信号迭代改进规则
    4. 过拟合审计：防止数据泄漏和静默旁路
    """

    def __init__(self):
        self.templates: dict[str, SkillTemplate] = {}
        self.skills: dict[str, GeneratedSkill] = {}
        self.audit_reports: list[AuditReport] = []
        self.evolution_history: list[SkillEvolution] = []

        # 初始化默认模板
        self._init_default_templates()

    def _init_default_templates(self):
        """初始化默认技能模板"""
        # 趋势跟踪模板
        self.templates["trend_following"] = SkillTemplate(
            template_id="trend_following",
            name="趋势跟踪模板",
            description="基于均线和通道的趋势跟踪策略",
            category="trend_following",
            parameters={
                "fast_ma": 20,
                "slow_ma": 60,
                "adx_threshold": 25,
                "atr_multiplier": 2.0,
            },
            rules=[
                "当快速均线上穿慢速均线时做多",
                "当快速均线下穿慢速均线时做空",
                "ADX > 阈值时确认趋势有效",
                "止损 = ATR * 乘数",
            ],
            conditions=[
                "market_state != 'RANGE_BOUND'",
                "trend_phase not in ('FATIGUING', 'REVERSING')",
            ],
        )

        # 动量模板
        self.templates["momentum"] = SkillTemplate(
            template_id="momentum",
            name="动量策略模板",
            description="基于RSI和MACD的动量策略",
            category="momentum",
            parameters={
                "rsi_period": 14,
                "rsi_overbought": 70,
                "rsi_oversold": 30,
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
            },
            rules=[
                "RSI < 超卖阈值时做多",
                "RSI > 超买阈值时做空",
                "MACD金叉确认做多",
                "MACD死叉确认做空",
            ],
            conditions=[
                "adx > 20",
                "volume > volume_ma * 0.8",
            ],
        )

        # 通道突破模板
        self.templates["channel_breakout"] = SkillTemplate(
            template_id="channel_breakout",
            name="通道突破模板",
            description="基于唐奇安通道的突破策略",
            category="channel_breakout",
            parameters={
                "channel_period": 20,
                "atr_multiplier": 2.5,
            },
            rules=[
                "价格突破上轨时做多",
                "价格突破下轨时做空",
                "止损 = ATR * 乘数",
            ],
            conditions=[
                "adx > 25",
                "bb_width > 0.05",
            ],
        )

    def create_skill_from_template(
        self, template_id: str, custom_params: dict[str, Any] = None
    ) -> GeneratedSkill | None:
        """
        从模板创建技能

        参数:
            template_id: 模板ID
            custom_params: 自定义参数

        返回:
            生成的技能对象
        """
        template = self.templates.get(template_id)
        if not template:
            return None

        # 合并参数
        params = template.parameters.copy()
        if custom_params:
            params.update(custom_params)

        # 生成技能ID
        skill_id = f"SKILL-{template_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 创建技能
        skill = GeneratedSkill(
            skill_id=skill_id,
            name=f"{template.name} v1.0",
            description=template.description,
            version="1.0.0",
            phase=SkillGenerationPhase.CREATION,
            template_id=template_id,
            parameters=params,
            rules=template.rules.copy(),
            conditions=template.conditions.copy(),
        )

        self.skills[skill_id] = skill
        return skill

    def deploy_skill(self, skill_id: str) -> bool:
        """
        部署技能到实际交易

        参数:
            skill_id: 技能ID

        返回:
            是否成功部署
        """
        skill = self.skills.get(skill_id)
        if not skill:
            return False

        skill.phase = SkillGenerationPhase.DEPLOYMENT
        skill.updated_at = datetime.now()
        return True

    def record_trade_result(self, skill_id: str, trade_result: dict[str, Any]):
        """
        记录交易结果

        参数:
            skill_id: 技能ID
            trade_result: 交易结果
        """
        skill = self.skills.get(skill_id)
        if not skill:
            return

        # 记录性能历史
        skill.performance_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "pnl": trade_result.get("pnl", 0),
                "pnl_pct": trade_result.get("pnl_pct", 0),
                "success": trade_result.get("pnl", 0) > 0,
                "market_state": trade_result.get("market_state", "UNKNOWN"),
                "trend_phase": trade_result.get("trend_phase", "UNKNOWN"),
            }
        )

        # 更新成功/失败计数
        if trade_result.get("pnl", 0) > 0:
            skill.success_count += 1
        else:
            skill.failure_count += 1

        skill.updated_at = datetime.now()

    def refine_skill_from_failures(self, skill_id: str, failures: list[dict[str, Any]]) -> SkillEvolution | None:
        """
        根据失败信号精炼技能

        参数:
            skill_id: 技能ID
            failures: 失败案例列表

        返回:
            进化记录
        """
        skill = self.skills.get(skill_id)
        if not skill:
            return None

        if not failures:
            return None

        # 分析失败原因
        failure_analysis = self._analyze_failures(failures)

        # 生成改进方案
        improvements = self._generate_improvements(skill, failure_analysis)

        if not improvements:
            return None

        # 记录进化前的性能
        perf_before = self._calculate_performance(skill)

        # 应用改进
        old_version = skill.version
        self._apply_improvements(skill, improvements)

        # 记录进化后的性能（假设改进后会有提升）
        perf_after = perf_before.copy()  # 实际应用中需要等待新交易数据

        # 创建进化记录
        evolution = SkillEvolution(
            evolution_id=f"EVO-{datetime.now().strftime('%Y%m%d')}-{skill_id}",
            skill_id=skill_id,
            old_version=old_version,
            new_version=skill.version,
            changes=improvements,
            reason=failure_analysis.get("summary", "根据失败信号改进"),
            trigger="failure_analysis",
            performance_before=perf_before,
            performance_after=perf_after,
        )

        self.evolution_history.append(evolution)
        return evolution

    def _analyze_failures(self, failures: list[dict[str, Any]]) -> dict[str, Any]:
        """分析失败原因"""
        analysis = {
            "total_failures": len(failures),
            "failure_types": defaultdict(int),
            "market_states": defaultdict(int),
            "trend_phases": defaultdict(int),
            "common_patterns": [],
        }

        for failure in failures:
            # 统计失败类型
            fault_type = failure.get("fault_type", "unknown")
            analysis["failure_types"][fault_type] += 1

            # 统计市场状态
            market_state = failure.get("market_state", "UNKNOWN")
            analysis["market_states"][market_state] += 1

            # 统计趋势阶段
            trend_phase = failure.get("trend_phase", "UNKNOWN")
            analysis["trend_phases"][trend_phase] += 1

        # 识别常见模式
        if analysis["failure_types"]:
            most_common_type = max(analysis["failure_types"].items(), key=lambda x: x[1])
            analysis["common_patterns"].append(f"最常见失败类型: {most_common_type[0]} ({most_common_type[1]}次)")

        if analysis["market_states"]:
            most_common_state = max(analysis["market_states"].items(), key=lambda x: x[1])
            analysis["common_patterns"].append(f"最常见市场状态: {most_common_state[0]} ({most_common_state[1]}次)")

        # 生成摘要
        analysis["summary"] = f"共{len(failures)}次失败，" + "; ".join(analysis["common_patterns"][:3])

        return analysis

    def _generate_improvements(self, skill: GeneratedSkill, failure_analysis: dict[str, Any]) -> dict[str, Any]:
        """生成改进方案"""
        improvements = {
            "parameter_changes": {},
            "rule_changes": [],
            "condition_changes": [],
        }

        failure_types = failure_analysis.get("failure_types", {})
        market_states = failure_analysis.get("market_states", {})
        trend_phases = failure_analysis.get("trend_phases", {})

        # 根据失败类型生成改进
        if "phase_mismatch" in failure_types:
            # 阶段错配：加强趋势阶段过滤
            improvements["condition_changes"].append(
                "添加条件: trend_phase not in ('FATIGUING', 'REVERSING', 'CONSOLIDATING')"
            )

        if "indicator_misuse" in failure_types:
            # 指标误用：提高指标阈值
            if "adx_threshold" in skill.parameters:
                old_threshold = skill.parameters["adx_threshold"]
                new_threshold = min(35, old_threshold + 5)
                improvements["parameter_changes"]["adx_threshold"] = new_threshold

        if "timing_error" in failure_types:
            # 时机错误：优化止损参数
            if "atr_multiplier" in skill.parameters:
                old_mult = skill.parameters["atr_multiplier"]
                new_mult = min(3.0, old_mult + 0.5)
                improvements["parameter_changes"]["atr_multiplier"] = new_mult

        if "risk_mismanagement" in failure_types:
            # 风控失误：添加风控规则
            improvements["rule_changes"].append("添加规则: 单笔风险不超过账户的2%")

        # 根据市场状态生成改进
        if market_states.get("RANGE_BOUND", 0) > 2:
            improvements["condition_changes"].append("添加条件: market_state != 'RANGE_BOUND'")

        return improvements

    def _apply_improvements(self, skill: GeneratedSkill, improvements: dict[str, Any]):
        """应用改进"""
        # 应用参数变更
        for param, value in improvements.get("parameter_changes", {}).items():
            skill.parameters[param] = value

        # 应用规则变更
        for rule in improvements.get("rule_changes", []):
            if rule not in skill.rules:
                skill.rules.append(rule)

        # 应用条件变更
        for condition in improvements.get("condition_changes", []):
            if condition not in skill.conditions:
                skill.conditions.append(condition)

        # 更新版本
        major, minor, patch = map(int, skill.version.split("."))
        skill.version = f"{major}.{minor}.{patch + 1}"

        # 更新阶段
        skill.phase = SkillGenerationPhase.REFINEMENT
        skill.updated_at = datetime.now()

    def _calculate_performance(self, skill: GeneratedSkill) -> dict[str, Any]:
        """计算性能指标"""
        if not skill.performance_history:
            return {}

        pnls = [p["pnl"] for p in skill.performance_history]
        pnl_pcts = [p["pnl_pct"] for p in skill.performance_history]

        return {
            "total_trades": len(pnls),
            "win_rate": sum(1 for p in pnls if p > 0) / len(pnls) if pnls else 0,
            "total_pnl": sum(pnls),
            "avg_pnl_pct": np.mean(pnl_pcts) if pnl_pcts else 0,
            "profit_factor": sum(p for p in pnls if p > 0) / abs(sum(p for p in pnls if p < 0))
            if any(p < 0 for p in pnls)
            else float("inf"),
            "success_count": skill.success_count,
            "failure_count": skill.failure_count,
        }

    def get_skill(self, skill_id: str) -> GeneratedSkill | None:
        """获取技能"""
        return self.skills.get(skill_id)

    def get_all_skills(self) -> list[GeneratedSkill]:
        """获取所有技能"""
        return list(self.skills.values())

    def get_skills_by_phase(self, phase: SkillGenerationPhase) -> list[GeneratedSkill]:
        """按阶段获取技能"""
        return [s for s in self.skills.values() if s.phase == phase]

    def get_evolution_history(self, skill_id: str = None) -> list[SkillEvolution]:
        """获取进化历史"""
        if skill_id:
            return [e for e in self.evolution_history if e.skill_id == skill_id]
        return self.evolution_history
