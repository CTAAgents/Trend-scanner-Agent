"""
控制变量隔离模块

实现五路径框架的第二条公理：控制变量是核心设计语言

核心思想：
- 显式标记哪些层是"固定的"（无LLM影响）
- 显式标记哪些层是"LLM影响的"
- 提供接口来获取"纯规则"结果（不含LLM修正）
- 量化LLM的边际贡献

设计原则：
- LLM不上硬决策，只做软层
- 控制变量是核心设计语言
- 可审计性 = 可上线
"""

from dataclasses import dataclass

from .models import MarketContext
from .narrative_generator import NarrativeGenerator, RuleGenerator


# ──────────────────────────────────────────────
# 层定义
# ──────────────────────────────────────────────


@dataclass
class LayerConfig:
    """层配置"""

    name: str
    is_fixed: bool  # 是否固定（无LLM影响）
    description: str
    components: list[str]


# 系统层配置
SYSTEM_LAYERS = {
    "indicators": LayerConfig(
        name="indicators",
        is_fixed=True,
        description="技术指标计算层（固定，无LLM影响）",
        components=["IndicatorEngine", "add_ema", "add_macd", "add_rsi", "add_atr"],
    ),
    "context": LayerConfig(
        name="context",
        is_fixed=True,
        description="上下文组装层（固定，无LLM影响）",
        components=["ContextAssembler"],
    ),
    "strategy": LayerConfig(
        name="strategy",
        is_fixed=True,
        description="策略池层（固定，无LLM影响）",
        components=["StrategyPool"],
    ),
    "risk_management": LayerConfig(
        name="risk_management",
        is_fixed=True,
        description="风险管理层（固定，无LLM影响）",
        components=["RiskManager", "ExitSignalGenerator"],
    ),
    "narrative": LayerConfig(
        name="narrative",
        is_fixed=False,
        description="叙事生成层（LLM影响）",
        components=["NarrativeGenerator"],
    ),
    "reasoning": LayerConfig(
        name="reasoning",
        is_fixed=False,
        description="推理引擎层（LLM影响）",
        components=["ReasoningEngine"],
    ),
    "debate": LayerConfig(
        name="debate",
        is_fixed=False,
        description="辩论纠偏层（LLM影响）",
        components=["DebateReasoningEngine"],
    ),
    "brief": LayerConfig(
        name="brief",
        is_fixed=False,
        description="简报生成层（LLM影响）",
        components=["BriefGenerator"],
    ),
}


# ──────────────────────────────────────────────
# 控制变量分析器
# ──────────────────────────────────────────────


class ControlVariableAnalyzer:
    """
    控制变量分析器

    分析LLM对最终结果的边际贡献。
    """

    def __init__(self):
        self.narrative_generator = NarrativeGenerator()
        self.rule_generator = RuleGenerator()

    def get_fixed_result(self, context: MarketContext) -> dict:
        """
        获取纯规则结果（不含LLM修正）

        这是"控制变量"的结果，用于与LLM修正后的结果对比。

        Args:
            context: 市场上下文

        Returns:
            纯规则结果
        """
        # 1. 生成叙事（固定层）
        narrative = self.narrative_generator.generate_structured(context)

        # 2. 生成规则（固定层）
        rules = self.rule_generator.generate_rules(narrative)

        return {
            "narrative": narrative,
            "rules": rules,
            "source": "fixed_layers_only",
            "llm_contribution": False,
        }

    def calculate_llm_contribution(self, fixed_result: dict, llm_result: dict) -> dict:
        """
        计算LLM的边际贡献

        Args:
            fixed_result: 纯规则结果
            llm_result: LLM修正后的结果

        Returns:
            LLM贡献分析
        """
        fixed_rules = fixed_result.get("rules", {})
        llm_rules = llm_result.get("rules", {})

        # 方向差异
        fixed_direction = fixed_rules.get("direction", 0)
        llm_direction = llm_rules.get("direction", 0)
        direction_change = llm_direction - fixed_direction

        # 信号差异
        fixed_signal = fixed_rules.get("signal", "UNKNOWN")
        llm_signal = llm_rules.get("signal", "UNKNOWN")
        signal_changed = fixed_signal != llm_signal

        # 仓位差异
        fixed_position = fixed_rules.get("position_pct", 0)
        llm_position = llm_rules.get("position_pct", 0)
        position_change = llm_position - fixed_position

        # 置信度差异
        fixed_confidence = fixed_rules.get("confidence", 0.5)
        llm_confidence = llm_rules.get("confidence", 0.5)
        confidence_change = llm_confidence - fixed_confidence

        # 判断LLM贡献类型
        if direction_change == 0 and not signal_changed:
            contribution_type = "CONFIRM"  # LLM确认规则
        elif direction_change == 0 and signal_changed:
            contribution_type = "REFINE"  # LLM细化信号
        elif abs(direction_change) == 1:
            contribution_type = "REVERSE"  # LLM反转方向
        elif abs(direction_change) == 2:
            contribution_type = "STRONG_REVERSE"  # LLM强烈反转
        else:
            contribution_type = "UNKNOWN"

        return {
            "contribution_type": contribution_type,
            "direction_change": direction_change,
            "signal_changed": signal_changed,
            "position_change": round(position_change, 4),
            "confidence_change": round(confidence_change, 4),
            "fixed_direction": fixed_direction,
            "llm_direction": llm_direction,
            "fixed_signal": fixed_signal,
            "llm_signal": llm_signal,
            "fixed_position": fixed_position,
            "llm_position": llm_position,
            "fixed_confidence": fixed_confidence,
            "llm_confidence": llm_confidence,
        }

    def generate_audit_report(self, context: MarketContext, llm_result: dict) -> str:
        """
        生成审计报告

        Args:
            context: 市场上下文
            llm_result: LLM修正后的结果

        Returns:
            审计报告文本
        """
        # 获取纯规则结果
        fixed_result = self.get_fixed_result(context)

        # 计算LLM贡献
        contribution = self.calculate_llm_contribution(fixed_result, llm_result)

        report = f"""
# 控制变量审计报告

## 固定层结果（无LLM影响）
- 方向：{contribution["fixed_direction"]} ({contribution["fixed_signal"]})
- 仓位：{contribution["fixed_position"]:.2%}
- 置信度：{contribution["fixed_confidence"]:.2%}

## LLM修正后结果
- 方向：{contribution["llm_direction"]} ({contribution["llm_signal"]})
- 仓位：{contribution["llm_position"]:.2%}
- 置信度：{contribution["llm_confidence"]:.2%}

## LLM边际贡献
- 贡献类型：{contribution["contribution_type"]}
- 方向变化：{contribution["direction_change"]}
- 信号变化：{"是" if contribution["signal_changed"] else "否"}
- 仓位变化：{contribution["position_change"]:+.2%}
- 置信度变化：{contribution["confidence_change"]:+.2%}

## 结论
"""
        if contribution["contribution_type"] == "CONFIRM":
            report += "LLM确认了固定层的规则，未做修正。"
        elif contribution["contribution_type"] == "REFINE":
            report += "LLM对固定层的信号进行了细化调整。"
        elif contribution["contribution_type"] == "REVERSE":
            report += "LLM反转了固定层的方向判断，需要重点关注。"
        elif contribution["contribution_type"] == "STRONG_REVERSE":
            report += "LLM强烈反转了固定层的方向判断，需要特别关注。"
        else:
            report += "LLM贡献类型未知。"

        return report


# ──────────────────────────────────────────────
# 便捷函数
# ──────────────────────────────────────────────


def get_system_layers() -> dict[str, LayerConfig]:
    """获取系统层配置"""
    return SYSTEM_LAYERS


def get_fixed_layers() -> dict[str, LayerConfig]:
    """获取固定层配置"""
    return {k: v for k, v in SYSTEM_LAYERS.items() if v.is_fixed}


def get_llm_layers() -> dict[str, LayerConfig]:
    """获取LLM影响层配置"""
    return {k: v for k, v in SYSTEM_LAYERS.items() if not v.is_fixed}


def analyze_llm_contribution(context: MarketContext, llm_result: dict) -> dict:
    """
    分析LLM贡献

    Args:
        context: 市场上下文
        llm_result: LLM修正后的结果

    Returns:
        LLM贡献分析
    """
    analyzer = ControlVariableAnalyzer()
    fixed_result = analyzer.get_fixed_result(context)
    return analyzer.calculate_llm_contribution(fixed_result, llm_result)
