"""
分级输出机制 — Phase 4: Formal/Standard/Brief

根据使用场景自动选择输出级别：
- formal: 完整报告（含所有维度分析、因子验证、风险评估）
- standard: 标准简报（核心指标+操作建议+关键风险）
- brief: 快速摘要（一句话结论+置信度）

使用方式:
    from trend_scanner.tiered_output import TieredOutputFormatter

    formatter = TieredOutputFormatter()
    output = formatter.format(market_context, level="standard")
"""

import logging
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 输出级别定义
# ---------------------------------------------------------------------------

OUTPUT_LEVELS = {
    "formal": {
        "name": "正式报告",
        "description": "完整分析报告，包含所有维度、因子验证、风险评估",
        "max_length": 8000,
        "sections": [
            "summary",
            "market_state",
            "indicator_detail",
            "multi_dimension",
            "factor_validation",
            "basis_seasonality",
            "risk_assessment",
            "arbitrage",
            "operation_plans",
            "disclaimer",
        ],
    },
    "standard": {
        "name": "标准简报",
        "description": "核心指标+操作建议+关键风险，适合日常决策",
        "max_length": 3000,
        "sections": ["summary", "market_state", "operation_plans", "risk_brief"],
    },
    "brief": {
        "name": "快速摘要",
        "description": "一句话结论+置信度+关键数字，适合消息推送",
        "max_length": 500,
        "sections": ["one_liner"],
    },
}


# ---------------------------------------------------------------------------
# 输出节格式化器
# ---------------------------------------------------------------------------


class _SectionFormatter:
    """节格式化器 — 将各类数据格式化为 Markdown 节"""

    @staticmethod
    def format_summary(ctx: dict) -> str:
        """摘要节"""
        parts = []
        symbol = ctx.get("symbol", "未知品种")
        direction = ctx.get("direction", "观望")
        confidence = ctx.get("confidence", 0)
        trend_phase = ctx.get("trend_phase", "UNKNOWN")

        emoji_dir = "看多" if direction == "LONG" else ("看空" if direction == "SHORT" else "观望")
        parts.append(f"**{symbol}** | 方向: {emoji_dir} | 置信度: {confidence:.0%}")
        parts.append(f"趋势阶段: {trend_phase}")
        return "\n".join(parts)

    @staticmethod
    def format_market_state(ctx: dict) -> str:
        """市场状态节"""
        parts = []
        parts.append("## 市场状态")

        indicators = ctx.get("indicators", {})
        if indicators:
            er = indicators.get("er", 0)
            tsi = indicators.get("tsi", 0)
            r2 = indicators.get("r_squared", 0)
            hurst = indicators.get("hurst", 0.5)
            trend_strength = indicators.get("trend_strength_composite", 0)
            rsi = indicators.get("rsi", 50)
            adx = indicators.get("adx", 0)

            parts.append(f"- ER: {er:.3f} ({'趋势' if er > 0.6 else '震荡' if er < 0.3 else '弱趋势'})")
            parts.append(f"- TSI: {tsi:.1f} ({'多头' if tsi > 20 else '空头' if tsi < -20 else '中性'})")
            parts.append(f"- R²: {r2:.3f}")
            parts.append(
                f"- Hurst: {hurst:.3f} ({'趋势持续' if hurst > 0.55 else '均值回归' if hurst < 0.45 else '随机'})"
            )
            parts.append(f"- 复合趋势强度: {trend_strength:.3f}")
            parts.append(f"- RSI: {rsi:.1f}")
            parts.append(f"- ADX: {adx:.1f}")

        return "\n".join(parts)

    @staticmethod
    def format_indicator_detail(ctx: dict) -> str:
        """指标详情节（仅 formal）"""
        parts = []
        parts.append("## 指标详情")

        indicators = ctx.get("indicators", {})
        categories = {
            "趋势指标": ["er", "r_squared", "tsi", "adx", "ma20", "ma60", "hurst", "trend_strength_composite"],
            "动量指标": ["rsi", "macd_hist", "cci", "roc", "mtm"],
            "波动率指标": ["atr_14", "bb_upper", "bb_lower", "bb_bandwidth"],
            "成交量指标": ["obv", "mfi", "ad_line", "vwap"],
        }

        for cat_name, keys in categories.items():
            cat_data = {k: indicators.get(k) for k in keys if indicators.get(k) is not None}
            if cat_data:
                parts.append(f"\n### {cat_name}")
                for k, v in cat_data.items():
                    if isinstance(v, float):
                        parts.append(f"- {k}: {v:.4f}")

        return "\n".join(parts)

    @staticmethod
    def format_multi_dimension(ctx: dict) -> str:
        """多维度评分节"""
        parts = []
        parts.append("## 多维度评分")

        scores = ctx.get("multi_dimension_scores", {})
        if scores:
            for dim, score in scores.items():
                bar = "+" * int(score * 10) + "-" * (10 - int(score * 10))
                parts.append(f"- {dim}: [{bar}] {score:.2f}")
        else:
            parts.append("暂无多维度评分数据")

        return "\n".join(parts)

    @staticmethod
    def format_basis_seasonality(ctx: dict) -> str:
        """基差与季节性节"""
        parts = []
        parts.append("## 基差与季节性")

        basis = ctx.get("basis")
        if basis and basis.get("ok"):
            bd = basis.get("data", {})
            parts.append("### 基差")
            parts.append(f"- 现货: {bd.get('spot_price', 'N/A')} | 期货: {bd.get('futures_price', 'N/A')}")
            parts.append(f"- 基差: {bd.get('basis', 'N/A')} (基差率 {bd.get('basis_rate', 'N/A')}%)")

        seasonality = ctx.get("seasonality")
        if seasonality and seasonality.get("ok"):
            sd = seasonality.get("data", {})
            parts.append("### 季节性")
            parts.append(f"- 当前月份信号: {sd.get('current_month_signal', 0):+.2f}%")
            parts.append(f"- 上涨概率: {sd.get('current_month_pos_rate', 0):.0f}%")
            if sd.get("strong_months"):
                parts.append(f"- 强势月份: {sd['strong_months']}")

        if not basis and not seasonality:
            parts.append("暂无基差/季节性数据")

        return "\n".join(parts)

    @staticmethod
    def format_operation_plans(ctx: dict) -> str:
        """操作方案节"""
        parts = []
        parts.append("## 操作方案")

        plans = ctx.get("operation_plans", [])
        if plans:
            for i, plan in enumerate(plans, 1):
                action = plan.get("action", "观望")
                reason = plan.get("reason", "")
                position = plan.get("position", "")
                stop_loss = plan.get("stop_loss", "")
                entry = plan.get("entry", "")

                parts.append(f"\n### 方案{i}: {action}")
                if reason:
                    parts.append(f"- 理由: {reason}")
                if position:
                    parts.append(f"- 仓位: {position}")
                if entry:
                    parts.append(f"- 入场: {entry}")
                if stop_loss:
                    parts.append(f"- 止损: {stop_loss}")
        else:
            parts.append("暂无操作方案")

        return "\n".join(parts)

    @staticmethod
    def format_risk_brief(ctx: dict) -> str:
        """风险简报节"""
        parts = []
        parts.append("## 风险提示")

        risks = ctx.get("risks", [])
        if risks:
            for risk in risks[:3]:  # brief 只显示前3个
                parts.append(f"- {risk}")
        else:
            parts.append("暂无特别风险提示")

        return "\n".join(parts)

    @staticmethod
    def format_risk_assessment(ctx: dict) -> str:
        """风险评估节（formal 详细版）"""
        parts = []
        parts.append("## 风险评估")

        risks = ctx.get("risks", [])
        if risks:
            for i, risk in enumerate(risks, 1):
                parts.append(f"{i}. {risk}")

        # 波动率锚点
        anchor = ctx.get("volatility_anchor")
        if anchor:
            parts.append("\n### 波动幅度止损锚点")
            parts.append(f"- 当前价格: {anchor.get('current_price', 'N/A')}")
            parts.append(f"- 多头止损参考: {anchor.get('long_stop_loss', 'N/A')}")
            parts.append(f"- 空头止损参考: {anchor.get('short_stop_loss', 'N/A')}")

        return "\n".join(parts)

    @staticmethod
    def format_arbitrage(ctx: dict) -> str:
        """套利分析节"""
        parts = []
        parts.append("## 套利分析")

        arb = ctx.get("arbitrage")
        if arb and arb.get("ok"):
            arb_data = arb.get("data", {})
            parts.append(f"- 价差: {arb_data.get('spread', 'N/A')}")
            parts.append(f"- Z-Score: {arb_data.get('z_score', 'N/A')}")
            parts.append(f"- 信号: {arb_data.get('signal', 'N/A')}")
        else:
            parts.append("暂无套利机会")

        return "\n".join(parts)

    @staticmethod
    def format_one_liner(ctx: dict) -> str:
        """一句话摘要"""
        symbol = ctx.get("symbol", "品种")
        direction = ctx.get("direction", "观望")
        confidence = ctx.get("confidence", 0)
        trend_phase = ctx.get("trend_phase", "UNKNOWN")
        er = ctx.get("indicators", {}).get("er", 0)

        if direction == "LONG":
            return f"{symbol}: 看多 | 置信度{confidence:.0%} | {trend_phase} | ER={er:.2f}"
        elif direction == "SHORT":
            return f"{symbol}: 看空 | 置信度{confidence:.0%} | {trend_phase} | ER={er:.2f}"
        else:
            return f"{symbol}: 观望 | 置信度{confidence:.0%} | {trend_phase} | ER={er:.2f}"

    @staticmethod
    def format_disclaimer(ctx: dict) -> str:
        """免责声明"""
        return (
            "---\n\n"
            "**免责声明**: 本报告由 AI 系统自动生成，仅供参考，不构成投资建议。"
            "市场有风险，投资需谨慎。所有交易决策应基于您自己的判断和风险承受能力。"
        )


# ---------------------------------------------------------------------------
# TieredOutputFormatter
# ---------------------------------------------------------------------------


class TieredOutputFormatter:
    """分级输出格式化器

    根据输出级别自动选择节并格式化。
    """

    def __init__(self, default_level: str = "standard"):
        self._default_level = default_level
        self._formatter = _SectionFormatter()

    def format(self, market_context: dict[str, Any], level: str = None) -> str:
        """格式化市场上下文为指定级别的输出

        参数:
            market_context: 市场上下文字典（含指标、方向、方案等）
            level: 输出级别 (formal/standard/brief)，None 使用默认级别

        返回:
            格式化的 Markdown 文本
        """
        level = level or self._default_level
        level_config = OUTPUT_LEVELS.get(level, OUTPUT_LEVELS["standard"])

        sections = level_config["sections"]
        parts = []

        # 标题
        symbol = market_context.get("symbol", "品种")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        parts.append(f"# {symbol} 交易决策简报 ({level_config['name']})")
        parts.append(f"*生成时间: {timestamp}*")
        parts.append("")

        # 格式化各节
        section_methods = {
            "summary": self._formatter.format_summary,
            "market_state": self._formatter.format_market_state,
            "indicator_detail": self._formatter.format_indicator_detail,
            "multi_dimension": self._formatter.format_multi_dimension,
            "basis_seasonality": self._formatter.format_basis_seasonality,
            "operation_plans": self._formatter.format_operation_plans,
            "risk_brief": self._formatter.format_risk_brief,
            "risk_assessment": self._formatter.format_risk_assessment,
            "arbitrage": self._formatter.format_arbitrage,
            "one_liner": self._formatter.format_one_liner,
            "disclaimer": self._formatter.format_disclaimer,
        }

        for section_name in sections:
            method = section_methods.get(section_name)
            if method:
                try:
                    section_text = method(market_context)
                    if section_text:
                        parts.append(section_text)
                        parts.append("")
                except Exception as e:
                    logger.debug(f"格式化节 {section_name} 失败: {e}")

        return "\n".join(parts).strip()

    def format_json(self, market_context: dict[str, Any], level: str = None) -> dict[str, Any]:
        """JSON 格式输出（供 API/前端消费）"""
        level = level or self._default_level
        level_config = OUTPUT_LEVELS.get(level, OUTPUT_LEVELS["standard"])

        return {
            "symbol": market_context.get("symbol", ""),
            "level": level,
            "level_name": level_config["name"],
            "timestamp": datetime.now().isoformat(),
            "direction": market_context.get("direction", "HOLD"),
            "confidence": market_context.get("confidence", 0),
            "trend_phase": market_context.get("trend_phase", "UNKNOWN"),
            "text_output": self.format(market_context, level),
            "sections": {s: True for s in level_config["sections"]},
        }

    @staticmethod
    def get_available_levels() -> dict[str, str]:
        """获取可用输出级别"""
        return {k: v["name"] for k, v in OUTPUT_LEVELS.items()}
