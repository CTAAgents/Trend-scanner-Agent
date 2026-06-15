"""
交易决策简报生成器 —— 交互层

将推理引擎的输出转换为用户可读的交易决策简报。
"""

from typing import List, Optional

from .models import (
    MarketContext, TradingBrief, MarketAssessment, Route,
    Constraint, Uncertainty, ExperienceMatch, TrendPhase,
)


class BriefGenerator:
    """
    交易决策简报生成器

    将推理结果转换为结构化的交易决策简报。
    """

    def generate(
        self,
        context: MarketContext,
        reasoning_result: dict,
        similar_experiences: List[ExperienceMatch],
    ) -> TradingBrief:
        """
        生成交易决策简报

        参数:
            context: 市场上下文
            reasoning_result: 推理引擎的输出
            similar_experiences: 相似经验列表

        返回:
            TradingBrief 交易决策简报
        """
        # 1. 趋势阶段
        trend_phase = context.trend_phase

        # 2. 市场评估
        assessment = MarketAssessment(
            trend_phase=trend_phase.phase,
            phase_label=trend_phase.to_chinese(),
            confidence=trend_phase.confidence,
            summary=self._build_summary(context),
            signal_hint=trend_phase.to_signal_hint(),
        )

        # 3. 构建操作方案
        routes = self._build_routes(reasoning_result, context, similar_experiences)

        # 4. 构建不确定性
        uncertainty = self._build_uncertainty(
            trend_phase.confidence, similar_experiences, reasoning_result
        )

        # 5. 构建简报
        brief = TradingBrief(
            symbol=context.symbol,
            timestamp=context.timestamp,
            trend_phase=trend_phase,
            assessment=assessment,
            warnings=reasoning_result.get('warnings', []),
            routes=routes,
            recommended_route=reasoning_result.get('recommended_route', ''),
            uncertainty=uncertainty,
            reasoning_model=reasoning_result.get('reasoning_model', ''),
            experience_count=len(similar_experiences),
            generation_time_ms=reasoning_result.get('generation_time_ms', 0),
        )

        return brief

    def _build_summary(self, context: MarketContext) -> str:
        """构建一句话市场总结（使用四维复合指标）"""
        phase = context.trend_phase
        ma = context.structure.ma_arrangement
        snapshot = context.snapshot

        # 计算四维复合评分
        composite = snapshot.trend_strength_composite

        parts = []
        if phase.phase in ('DEVELOPING', 'MATURE'):
            if 'BULL' in ma:
                parts.append("多头趋势")
            elif 'BEAR' in ma:
                parts.append("空头趋势")
        elif phase.phase == 'CONSOLIDATING':
            parts.append("震荡整理")
        elif phase.phase == 'EMERGING':
            parts.append("趋势萌芽")
        elif phase.phase == 'FATIGUING':
            parts.append("趋势衰竭")
        elif phase.phase == 'REVERSING':
            parts.append("趋势反转")

        # 使用四维复合指标判断趋势强度
        if composite >= 0.7:
            parts.append("趋势强劲")
        elif composite >= 0.5:
            parts.append("趋势明确")
        elif composite < 0.3:
            parts.append("缺乏方向")

        # 添加四维分解信息
        er = snapshot.trend_strength_er
        r2 = snapshot.trend_strength_r2
        hurst = snapshot.trend_strength_hurst
        adx_roc = snapshot.trend_strength_adx_roc

        # 四维状态描述
        dim_status = []
        if er >= 0.6:
            dim_status.append(f"ER={er:.2f}(高效)")
        elif er < 0.3:
            dim_status.append(f"ER={er:.2f}(低效)")

        if r2 >= 0.6:
            dim_status.append(f"R²={r2:.2f}(清晰)")
        elif r2 < 0.3:
            dim_status.append(f"R²={r2:.2f}(模糊)")

        if hurst >= 0.6:
            dim_status.append(f"H={hurst:.2f}(趋势)")
        elif hurst < 0.4:
            dim_status.append(f"H={hurst:.2f}(均值回归)")

        if adx_roc > 0.5:
            dim_status.append(f"ADX ROC={adx_roc:.2f}(加速)")
        elif adx_roc < -0.5:
            dim_status.append(f"ADX ROC={adx_roc:.2f}(减速)")

        if dim_status:
            parts.append("四维：" + "，".join(dim_status))

        return "，".join(parts) if parts else "市场状态中性"

    def _build_routes(
        self,
        reasoning_result: dict,
        context: MarketContext,
        similar_experiences: List[ExperienceMatch],
    ) -> List[Route]:
        """构建操作方案"""
        routes = []

        for route_data in reasoning_result.get('routes', []):
            # 构建约束
            constraints = []
            for c_data in route_data.get('constraints', []):
                constraint = Constraint(
                    constraint_type=c_data.get('constraint_type', 'UNKNOWN'),
                    value=c_data.get('value', ''),
                    numeric_value=c_data.get('numeric_value', 0.0),
                    confidence=c_data.get('confidence', 0.5),
                    reasoning=c_data.get('reasoning', ''),
                    historical_basis=c_data.get('historical_basis', ''),
                    uncertainty_range=c_data.get('uncertainty_range', ''),
                )
                constraints.append(constraint)

            # 找到支撑这条方案的经验
            supporting = []
            action = route_data.get('action', '')
            for exp_match in similar_experiences:
                if exp_match.experience.action_taken in action or action in exp_match.experience.action_taken:
                    supporting.append(exp_match)

            route = Route(
                route_id=route_data.get('route_id', 'A'),
                name=route_data.get('name', '未命名'),
                action=route_data.get('action', '无操作'),
                confidence=route_data.get('confidence', 0.5),
                reasoning=route_data.get('reasoning', ''),
                constraints=constraints,
                risks=route_data.get('risks', []),
                trigger_conditions=route_data.get('trigger_conditions', []),
                opportunity_cost=route_data.get('opportunity_cost', ''),
                historical_analog=route_data.get('historical_analog', ''),
                historical_outcome=route_data.get('historical_outcome', ''),
                supporting_experiences=supporting[:3],
            )
            routes.append(route)

        return routes

    def _build_uncertainty(
        self,
        phase_confidence: float,
        similar_experiences: List[ExperienceMatch],
        reasoning_result: dict,
    ) -> Uncertainty:
        """构建不确定性量化"""
        # 阶段判断置信度
        cluster_confidence = phase_confidence

        # 经验检索置信度
        if similar_experiences:
            avg_similarity = sum(m.similarity for m in similar_experiences) / len(similar_experiences)
            retrieval_confidence = avg_similarity
        else:
            retrieval_confidence = 0.3

        # 约束置信度
        constraint_confidences = []
        for route in reasoning_result.get('routes', []):
            for c in route.get('constraints', []):
                if 'confidence' in c:
                    constraint_confidences.append(c['confidence'])

        if constraint_confidences:
            constraint_confidence = sum(constraint_confidences) / len(constraint_confidences)
        else:
            constraint_confidence = 0.4

        # 综合置信度
        overall_confidence = (
            cluster_confidence * 0.3 +
            retrieval_confidence * 0.4 +
            constraint_confidence * 0.3
        )

        return Uncertainty(
            cluster_confidence=round(cluster_confidence, 2),
            retrieval_confidence=round(retrieval_confidence, 2),
            constraint_confidence=round(constraint_confidence, 2),
            overall_confidence=round(overall_confidence, 2),
        )


class BriefFormatter:
    """
    简报格式化器

    将 TradingBrief 转换为各种格式的文本。
    """

    @staticmethod
    def to_markdown(brief: TradingBrief) -> str:
        """转换为 Markdown 格式"""
        return brief.to_text()

    @staticmethod
    def to_plain_text(brief: TradingBrief) -> str:
        """转换为纯文本格式"""
        lines = []

        # 开场
        lines.append(f"{brief.symbol} 交易决策简报")
        lines.append(f"时间：{brief.timestamp}")
        lines.append("")

        # 市场评估
        phase = brief.trend_phase
        lines.append(f"趋势阶段：{phase.to_chinese()}")
        lines.append(f"判断依据：{phase.reasoning}")
        lines.append(f"信号倾向：{brief.assessment.signal_hint}")
        lines.append("")

        # 风险提示
        if brief.warnings:
            lines.append("风险提示：")
            for w in brief.warnings:
                lines.append(f"  - {w}")
            lines.append("")

        # 操作方案
        lines.append("操作方案：")
        for route in brief.routes:
            conf_pct = int(route.confidence * 100)
            lines.append(f"  方案{route.route_id}：{route.name}（置信度{conf_pct}%）")
            lines.append(f"    动作：{route.action}")
            lines.append(f"    推理：{route.reasoning}")
            if route.constraints:
                lines.append("    约束：")
                for c in route.constraints:
                    lines.append(f"      - {c._type_label()}：{c.value}")
            lines.append("")

        # 推荐
        if brief.recommended_route:
            lines.append(f"推荐方案：{brief.recommended_route}")
            lines.append("")

        # 不确定性
        lines.append(f"不确定性：{brief.uncertainty.to_text()}")
        lines.append("")

        # 收尾
        lines.append("以上为系统分析建议，最终决策权在你手中。")

        return "\n".join(lines)

    @staticmethod
    def to_notification(brief: TradingBrief) -> str:
        """转换为通知格式（简短）"""
        phase_label = brief.trend_phase.to_chinese()
        conf = int(brief.trend_phase.confidence * 100)

        lines = [
            f"【{brief.symbol}】{phase_label}（置信度{conf}%）",
        ]

        if brief.recommended_route:
            for route in brief.routes:
                if route.route_id == brief.recommended_route:
                    lines.append(f"推荐：{route.name} - {route.action}")
                    break

        if brief.warnings:
            lines.append(f"风险：{brief.warnings[0]}")

        lines.append(f"综合置信度：{int(brief.uncertainty.overall_confidence * 100)}%")

        return " | ".join(lines)
