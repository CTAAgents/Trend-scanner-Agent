"""
概率加权场景分析器

借鉴 ai-investment-skills 的 EV Calculator 思想，为期货交易提供：
- 牛市/基准/熊市场景建模
- 概率加权预期价值计算
- 信号置信度评估
- 操作建议生成

核心思想：
- 不依赖单一预测，而是构建多个可能的未来情景
- 为每个情景分配概率权重
- 计算预期价值（Expected Value）
- 基于 EV 和置信度生成操作建议
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    """单个场景"""

    name: str  # bull/base/bear
    probability: float  # 概率 (0-1)
    target_price: float  # 目标价格
    expected_return: float  # 预期收益率 (%)
    catalyst: str  # 触发条件
    timeframe: str = "1-5天"  # 时间框架
    confidence: str = "MEDIUM"  # HIGH/MEDIUM/LOW


@dataclass
class ScenarioAnalysis:
    """场景分析结果"""

    symbol: str
    current_price: float
    scenarios: list[Scenario]
    weighted_ev: float  # 加权预期价值 (%)
    risk_reward_ratio: float  # 风险收益比
    overall_confidence: str  # HIGH/MEDIUM/LOW
    recommendation: str  # LONG/SHORT/HOLD
    reasoning: str  # 推理依据

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "scenarios": [
                {
                    "name": s.name,
                    "probability": s.probability,
                    "target_price": s.target_price,
                    "expected_return": s.expected_return,
                    "catalyst": s.catalyst,
                    "timeframe": s.timeframe,
                    "confidence": s.confidence,
                }
                for s in self.scenarios
            ],
            "weighted_ev": self.weighted_ev,
            "risk_reward_ratio": self.risk_reward_ratio,
            "overall_confidence": self.overall_confidence,
            "recommendation": self.recommendation,
            "reasoning": self.reasoning,
        }


class ScenarioAnalyzer:
    """
    场景分析器

    基于当前市场状态和历史数据，构建多个未来情景并计算预期价值。
    """

    def __init__(self, risk_free_rate: float = 0.02):
        """
        初始化场景分析器

        参数:
            risk_free_rate: 无风险利率（年化），默认 2%
        """
        self.risk_free_rate = risk_free_rate

    def analyze(
        self,
        symbol: str,
        current_price: float,
        indicators: dict[str, Any],
        trend_phase: str = "UNKNOWN",
        volatility: float = 0.02,
    ) -> ScenarioAnalysis:
        """
        执行场景分析

        参数:
            symbol: 品种代码
            current_price: 当前价格
            indicators: 技术指标字典
            trend_phase: 趋势阶段 (TREND_UP/TREND_DOWN/RANGE)
            volatility: 历史波动率（日）

        返回:
            ScenarioAnalysis 结果
        """
        # 1. 构建场景
        scenarios = self._build_scenarios(
            current_price, indicators, trend_phase, volatility
        )

        # 2. 计算加权预期价值
        weighted_ev = self._calculate_weighted_ev(scenarios)

        # 3. 计算风险收益比
        risk_reward = self._calculate_risk_reward(scenarios)

        # 4. 评估整体置信度
        confidence = self._assess_confidence(indicators, trend_phase)

        # 5. 生成推荐
        recommendation, reasoning = self._generate_recommendation(
            weighted_ev, risk_reward, confidence, trend_phase
        )

        return ScenarioAnalysis(
            symbol=symbol,
            current_price=current_price,
            scenarios=scenarios,
            weighted_ev=weighted_ev,
            risk_reward_ratio=risk_reward,
            overall_confidence=confidence,
            recommendation=recommendation,
            reasoning=reasoning,
        )

    def _build_scenarios(
        self,
        current_price: float,
        indicators: dict,
        trend_phase: str,
        volatility: float,
    ) -> list[Scenario]:
        """构建三个场景"""
        scenarios = []

        # 提取关键指标
        er = indicators.get("er", 0.5)
        tsi = indicators.get("tsi", 0)
        rsi = indicators.get("rsi", 50)
        trend_strength = indicators.get("trend_strength_composite", 0)

        # 计算波动率倍数（用于目标价格）
        vol_multiple = volatility * current_price

        # === 牛市场景 ===
        bull_prob, bull_return, bull_catalyst = self._bull_scenario(
            er, tsi, rsi, trend_strength, trend_phase
        )
        scenarios.append(
            Scenario(
                name="bull",
                probability=bull_prob,
                target_price=current_price * (1 + bull_return),
                expected_return=bull_return * 100,
                catalyst=bull_catalyst,
                confidence="HIGH" if er > 0.6 and tsi > 20 else "MEDIUM",
            )
        )

        # === 基准场景 ===
        base_prob, base_return, base_catalyst = self._base_scenario(
            er, tsi, rsi, trend_phase
        )
        scenarios.append(
            Scenario(
                name="base",
                probability=base_prob,
                target_price=current_price * (1 + base_return),
                expected_return=base_return * 100,
                catalyst=base_catalyst,
                confidence="HIGH",
            )
        )

        # === 熊市场景 ===
        bear_prob, bear_return, bear_catalyst = self._bear_scenario(
            er, tsi, rsi, trend_strength, trend_phase
        )
        scenarios.append(
            Scenario(
                name="bear",
                probability=bear_prob,
                target_price=current_price * (1 + bear_return),
                expected_return=bear_return * 100,
                catalyst=bear_catalyst,
                confidence="HIGH" if er > 0.6 and tsi < -20 else "MEDIUM",
            )
        )

        # 归一化概率
        total_prob = sum(s.probability for s in scenarios)
        if total_prob > 0:
            for s in scenarios:
                s.probability /= total_prob

        return scenarios

    def _bull_scenario(
        self, er: float, tsi: float, rsi: float, trend_strength: float, trend_phase: str
    ) -> tuple[float, float, str]:
        """牛市场景：概率、收益率、触发条件"""
        # 基础概率
        base_prob = 0.3

        # 根据指标调整
        if trend_phase == "TREND_UP":
            base_prob += 0.1
        if er > 0.6:
            base_prob += 0.05
        if tsi > 20:
            base_prob += 0.05
        if rsi > 50 and rsi < 70:
            base_prob += 0.05

        # 收益率：基于趋势强度
        base_return = 0.05 + trend_strength * 0.1  # 5% + 趋势强度 * 10%

        # 触发条件
        catalyst = "趋势确认突破"
        if er > 0.6:
            catalyst = "高效率比率确认趋势"
        if tsi > 20:
            catalyst += " + TSI动量向上"

        return min(base_prob, 0.5), base_return, catalyst

    def _base_scenario(
        self, er: float, tsi: float, rsi: float, trend_phase: str
    ) -> tuple[float, float, str]:
        """基准场景：概率、收益率、触发条件"""
        base_prob = 0.4

        # 震荡市概率更高
        if trend_phase == "RANGE":
            base_prob += 0.1

        # 收益率：小幅波动
        base_return = 0.02  # 2%

        catalyst = "正常波动，无明显趋势"

        return base_prob, base_return, catalyst

    def _bear_scenario(
        self, er: float, tsi: float, rsi: float, trend_strength: float, trend_phase: str
    ) -> tuple[float, float, str]:
        """熊市场景：概率、收益率、触发条件"""
        base_prob = 0.3

        # 根据指标调整
        if trend_phase == "TREND_DOWN":
            base_prob += 0.1
        if er > 0.6:
            base_prob += 0.05
        if tsi < -20:
            base_prob += 0.05
        if rsi < 50 and rsi > 30:
            base_prob += 0.05

        # 收益率：基于趋势强度（负收益）
        base_return = -0.05 - trend_strength * 0.1  # -5% - 趋势强度 * 10%

        # 触发条件
        catalyst = "趋势反转"
        if er > 0.6:
            catalyst = "高效率比率确认下跌趋势"
        if tsi < -20:
            catalyst += " + TSI动量向下"

        return min(base_prob, 0.5), base_return, catalyst

    def _calculate_weighted_ev(self, scenarios: list[Scenario]) -> float:
        """计算加权预期价值"""
        ev = sum(s.probability * s.expected_return for s in scenarios)
        return ev

    def _calculate_risk_reward(self, scenarios: list[Scenario]) -> float:
        """计算风险收益比"""
        bull = next((s for s in scenarios if s.name == "bull"), None)
        bear = next((s for s in scenarios if s.name == "bear"), None)

        if bull and bear and bear.expected_return != 0:
            return abs(bull.expected_return / bear.expected_return)
        return 1.0

    def _assess_confidence(self, indicators: dict, trend_phase: str) -> str:
        """评估整体置信度"""
        er = indicators.get("er", 0.5)
        r_squared = indicators.get("r_squared", 0.5)
        trend_strength = indicators.get("trend_strength_composite", 0)

        # 计算置信度分数
        score = 0
        if er > 0.6:
            score += 2
        elif er > 0.4:
            score += 1

        if r_squared > 0.5:
            score += 2
        elif r_squared > 0.3:
            score += 1

        if abs(trend_strength) > 0.5:
            score += 2
        elif abs(trend_strength) > 0.3:
            score += 1

        if trend_phase in ["TREND_UP", "TREND_DOWN"]:
            score += 1

        # 判断置信度
        if score >= 5:
            return "HIGH"
        elif score >= 3:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_recommendation(
        self,
        weighted_ev: float,
        risk_reward: float,
        confidence: str,
        trend_phase: str,
    ) -> tuple[str, str]:
        """生成推荐和推理依据"""
        # 基于 EV 和风险收益比
        if weighted_ev > 3 and risk_reward > 1.5 and confidence == "HIGH":
            return "LONG", f"EV={weighted_ev:+.1f}%, 风险收益比={risk_reward:.1f}, 置信度高"
        elif weighted_ev < -3 and risk_reward > 1.5 and confidence == "HIGH":
            return "SHORT", f"EV={weighted_ev:+.1f}%, 风险收益比={risk_reward:.1f}, 置信度高"
        elif weighted_ev > 1 and confidence != "LOW":
            return "LONG", f"EV={weighted_ev:+.1f}%, 正预期价值"
        elif weighted_ev < -1 and confidence != "LOW":
            return "SHORT", f"EV={weighted_ev:+.1f}%, 负预期价值"
        else:
            return "HOLD", f"EV={weighted_ev:+.1f}%, 信号不明确或置信度低"

    def format_analysis(self, analysis: ScenarioAnalysis) -> str:
        """格式化分析结果"""
        lines = [
            f"=== 场景分析 — {analysis.symbol} ===",
            f"当前价格: {analysis.current_price:.2f}",
            "",
            "场景分解:",
        ]

        for s in analysis.scenarios:
            emoji = "📈" if s.name == "bull" else ("➡️" if s.name == "base" else "📉")
            lines.append(
                f"  {emoji} {s.name.upper():6} "
                f"({s.probability:.0%}): "
                f"{s.target_price:.2f} ({s.expected_return:+.1f}%) "
                f"[{s.confidence}]"
            )
            lines.append(f"        触发: {s.catalyst}")

        lines.extend(
            [
                "",
                "─────────────────────────────────────",
                f"加权 EV: {analysis.weighted_ev:+.1f}%",
                f"风险收益比: {analysis.risk_reward_ratio:.1f}",
                f"整体置信度: {analysis.overall_confidence}",
                f"推荐: {analysis.recommendation}",
                f"理由: {analysis.reasoning}",
            ]
        )

        return "\n".join(lines)


def analyze_signal(
    symbol: str,
    current_price: float,
    indicators: dict,
    trend_phase: str = "UNKNOWN",
    volatility: float = 0.02,
) -> ScenarioAnalysis:
    """
    便捷函数：分析交易信号的预期价值

    参数:
        symbol: 品种代码
        current_price: 当前价格
        indicators: 技术指标字典
        trend_phase: 趋势阶段
        volatility: 历史波动率

    返回:
        ScenarioAnalysis 结果
    """
    analyzer = ScenarioAnalyzer()
    return analyzer.analyze(
        symbol=symbol,
        current_price=current_price,
        indicators=indicators,
        trend_phase=trend_phase,
        volatility=volatility,
    )
