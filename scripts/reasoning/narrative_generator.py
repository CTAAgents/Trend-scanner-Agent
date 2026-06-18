"""
叙事生成器（路径①）

核心机制：
- 叙事层：将市场数据转化为结构化叙事（不包含交易建议）
- 规则层：基于叙事生成交易规则（止损、仓位、入场条件）
- 控制变量：固定技术指标层，只让LLM做叙事

设计原则：
- LLM不上硬决策，只做软层
- 控制变量是核心设计语言
- 可审计性 = 可上线
"""

from .models import MarketContext


# ──────────────────────────────────────────────
# 趋势阶段描述
# ──────────────────────────────────────────────

PHASE_DESCRIPTIONS = {
    "CONSOLIDATING": {
        "chinese": "横盘整理",
        "emoji": "📊",
        "description": "无明确趋势，市场震荡",
        "key_features": "ADX低位，均线缠绕，波动率收窄",
    },
    "EMERGING": {
        "chinese": "趋势萌芽",
        "emoji": "🆕",
        "description": "趋势信号初现，方向待确认",
        "key_features": "ADX上升，均线开始发散，成交量放大",
    },
    "DEVELOPING": {
        "chinese": "趋势发展",
        "emoji": "🌱",
        "description": "趋势确认，动能增强",
        "key_features": "ADX中高位，均线同向，MACD动能扩张",
    },
    "MATURE": {
        "chinese": "趋势成熟",
        "emoji": "🏆",
        "description": "趋势充分发展，动能充沛",
        "key_features": "ADX高位，均线多头/空头排列，成交量配合",
    },
    "FATIGUING": {
        "chinese": "趋势衰竭",
        "emoji": "⚠️",
        "description": "动能减弱，趋势可能接近尾声",
        "key_features": "ADX下降，均线斜率减缓，MACD背离",
    },
    "REVERSING": {
        "chinese": "趋势反转",
        "emoji": "🔄",
        "description": "方向改变，新趋势可能开始",
        "key_features": "ADX快速下降，均线交叉，价格突破关键位",
    },
}


# ──────────────────────────────────────────────
# 叙事生成器
# ──────────────────────────────────────────────


class NarrativeGenerator:
    """
    叙事生成器

    将市场数据转化为结构化叙事，不包含交易建议。

    职责：
    1. 接收市场上下文
    2. 生成结构化叙事（描述市场状态，不做判断）
    3. 输出可审计的叙事报告

    设计原则：
    - 只描述，不建议
    - 只观察，不判断
    - 只叙事，不决策
    """

    def __init__(self, include_technical_details: bool = True):
        """
        初始化叙事生成器

        Args:
            include_technical_details: 是否包含技术细节
        """
        self.include_technical_details = include_technical_details

    def generate(self, context: MarketContext) -> str:
        """
        生成叙事文本

        Args:
            context: 市场上下文

        Returns:
            叙事文本（纯文本，不包含交易建议）
        """
        parts = []

        # 1. 市场标识
        parts.append(f"【{context.symbol} 日线数据】")

        # 2. 价格信息
        if hasattr(context, "current_price") and context.current_price:
            parts.append(f"当前价格：{context.current_price:.2f}")

        # 3. 趋势阶段
        phase = context.trend_phase.phase if hasattr(context, "trend_phase") else "UNKNOWN"
        confidence = context.trend_phase.confidence if hasattr(context, "trend_phase") else 0.5

        phase_info = PHASE_DESCRIPTIONS.get(
            phase,
            {
                "chinese": "未知",
                "emoji": "❓",
                "description": "未知阶段",
                "key_features": "无",
            },
        )

        parts.append(f"趋势阶段：{phase_info['emoji']} {phase_info['chinese']}（{phase}）")
        parts.append(f"阶段置信度：{confidence:.0%}")
        parts.append(f"阶段特征：{phase_info['key_features']}")

        # 4. 市场结构（如果有）
        if hasattr(context, "snapshot") and context.snapshot:
            snapshot = context.snapshot
            parts.append(f"日内波动：{snapshot.low:.2f} - {snapshot.high:.2f}")
            parts.append(f"成交量：{snapshot.volume}")

            # 计算波动率
            if context.current_price > 0:
                volatility = (snapshot.high - snapshot.low) / context.current_price * 100
                parts.append(f"日内波动率：{volatility:.2f}%")

        # 5. 叙事总结
        parts.append("")
        parts.append("## 市场叙事")
        parts.append(self._generate_narrative_summary(context, phase_info))

        return "\n".join(parts)

    def generate_structured(self, context: MarketContext) -> dict:
        """
        生成结构化叙事

        Args:
            context: 市场上下文

        Returns:
            结构化叙事字典
        """
        phase = context.trend_phase.phase if hasattr(context, "trend_phase") else "UNKNOWN"
        confidence = context.trend_phase.confidence if hasattr(context, "trend_phase") else 0.5

        phase_info = PHASE_DESCRIPTIONS.get(
            phase,
            {
                "chinese": "未知",
                "emoji": "❓",
                "description": "未知阶段",
                "key_features": "无",
            },
        )

        structured = {
            "symbol": context.symbol,
            "timestamp": context.timestamp if hasattr(context, "timestamp") else "",
            "current_price": context.current_price if hasattr(context, "current_price") else 0,
            "phase": phase,
            "phase_chinese": phase_info["chinese"],
            "phase_emoji": phase_info["emoji"],
            "phase_description": phase_info["description"],
            "phase_confidence": confidence,
            "key_features": phase_info["key_features"],
            "narrative": self._generate_narrative_summary(context, phase_info),
        }

        # 添加市场结构信息
        if hasattr(context, "snapshot") and context.snapshot:
            snapshot = context.snapshot
            structured["market_structure"] = {
                "high": snapshot.high,
                "low": snapshot.low,
                "open": snapshot.open,
                "close": snapshot.close,
                "volume": snapshot.volume,
                "volatility": (snapshot.high - snapshot.low) / context.current_price * 100
                if context.current_price > 0
                else 0,
            }

        return structured

    def _generate_narrative_summary(self, context: MarketContext, phase_info: dict) -> str:
        """
        生成叙事总结

        Args:
            context: 市场上下文
            phase_info: 阶段信息

        Returns:
            叙事总结文本
        """
        phase = context.trend_phase.phase if hasattr(context, "trend_phase") else "UNKNOWN"
        confidence = context.trend_phase.confidence if hasattr(context, "trend_phase") else 0.5

        # 基于阶段生成叙事
        if phase == "CONSOLIDATING":
            return (
                "市场处于横盘整理阶段，无明确趋势方向。"
                "均线缠绕，波动率收窄，成交量萎缩。"
                "市场正在积蓄能量，等待突破方向确认。"
            )
        elif phase == "EMERGING":
            return (
                "趋势信号初现，市场正在尝试突破整理区间。"
                "ADX开始上升，均线开始发散，成交量有所放大。"
                "但趋势方向尚未完全确认，需要进一步观察。"
            )
        elif phase == "DEVELOPING":
            return (
                "趋势已经确认，市场处于发展阶段。"
                "ADX中高位运行，均线同向排列，MACD动能扩张。"
                "趋势正在加速，市场参与度提升。"
            )
        elif phase == "MATURE":
            return (
                "趋势充分发展，市场处于成熟阶段。"
                "ADX高位运行，均线多头/空头排列完整，成交量配合。"
                "趋势动能充沛，但需要警惕过度延伸的风险。"
            )
        elif phase == "FATIGUING":
            return (
                "趋势动能减弱，市场可能接近尾声。"
                "ADX开始下降，均线斜率减缓，MACD出现背离。"
                "市场参与者开始犹豫，趋势可能即将结束。"
            )
        elif phase == "REVERSING":
            return (
                "趋势方向改变，市场可能出现反转。"
                "ADX快速下降，均线交叉，价格突破关键位置。"
                "市场情绪正在转变，新的趋势可能正在形成。"
            )
        else:
            return "市场状态不明确，需要进一步观察。建议等待更明确的信号出现。"


# ──────────────────────────────────────────────
# 规则生成器
# ──────────────────────────────────────────────


class RuleGenerator:
    """
    规则生成器

    基于叙事生成交易规则（止损、仓位、入场条件）。

    职责：
    1. 接收叙事（市场状态描述）
    2. 生成交易规则（可执行的约束）
    3. 输出可审计的规则报告

    设计原则：
    - 规则是叙事的产物
    - 规则是可执行的约束
    - 规则是可审计的
    """

    def generate_rules(self, narrative: dict) -> dict:
        """
        基于叙事生成规则

        Args:
            narrative: 结构化叙事

        Returns:
            交易规则字典
        """
        phase = narrative.get("phase", "UNKNOWN")
        confidence = narrative.get("phase_confidence", 0.5)

        # 基于阶段生成基础规则
        base_rules = self._generate_base_rules(phase, confidence)

        # 添加叙事信息
        base_rules["narrative"] = narrative.get("narrative", "")
        base_rules["phase"] = phase
        base_rules["phase_confidence"] = confidence

        return base_rules

    def _generate_base_rules(self, phase: str, confidence: float) -> dict:
        """
        生成基础规则

        Args:
            phase: 趋势阶段
            confidence: 置信度

        Returns:
            基础规则字典
        """
        # 基于阶段的基础规则
        phase_rules = {
            "CONSOLIDATING": {
                "direction": 0,
                "signal": "HOLD",
                "strength": "NEUTRAL",
                "position_pct": 0.0,
                "stop_loss_pct": 0.0,
                "take_profit_pct": 0.0,
            },
            "EMERGING": {
                "direction": 0,
                "signal": "WATCH",
                "strength": "WEAK",
                "position_pct": 0.0,
                "stop_loss_pct": 0.0,
                "take_profit_pct": 0.0,
            },
            "DEVELOPING": {
                "direction": 1,
                "signal": "BUY",
                "strength": "MEDIUM",
                "position_pct": 0.02,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.04,
            },
            "MATURE": {
                "direction": 1,
                "signal": "HOLD_LONG",
                "strength": "STRONG",
                "position_pct": 0.03,
                "stop_loss_pct": 0.015,
                "take_profit_pct": 0.05,
            },
            "FATIGUING": {
                "direction": 0,
                "signal": "REDUCE",
                "strength": "WEAK",
                "position_pct": 0.01,
                "stop_loss_pct": 0.01,
                "take_profit_pct": 0.02,
            },
            "REVERSING": {
                "direction": -1,
                "signal": "SELL",
                "strength": "MEDIUM",
                "position_pct": 0.02,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.04,
            },
        }

        rules = phase_rules.get(
            phase,
            {
                "direction": 0,
                "signal": "UNKNOWN",
                "strength": "NEUTRAL",
                "position_pct": 0.0,
                "stop_loss_pct": 0.0,
                "take_profit_pct": 0.0,
            },
        )

        # 置信度调整
        rules["position_pct"] *= confidence
        rules["confidence"] = confidence

        return rules


# ──────────────────────────────────────────────
# 便捷函数
# ──────────────────────────────────────────────


def generate_narrative(context: MarketContext, structured: bool = False):
    """
    生成叙事

    Args:
        context: 市场上下文
        structured: 是否返回结构化结果

    Returns:
        叙事文本或结构化字典
    """
    generator = NarrativeGenerator()

    if structured:
        return generator.generate_structured(context)
    else:
        return generator.generate(context)


def generate_rules_from_narrative(narrative: dict) -> dict:
    """
    基于叙事生成规则

    Args:
        narrative: 结构化叙事

    Returns:
        交易规则字典
    """
    generator = RuleGenerator()
    return generator.generate_rules(narrative)
