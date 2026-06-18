"""
机制门模块

实现机制门思想，根据当前市场机制动态调整经验权重。

核心思想：
- 同机制经验权重更高
- 异机制经验权重更低
- 推理时考虑机制匹配度

设计原则：
- 向后兼容：可选启用
- 渐进增强：逐步引入机制感知
- 性能优先：缓存机制匹配结果
"""

from dataclasses import dataclass

import numpy as np

from .models import Experience, ExperienceMatch


# 机制阶段定义
REGIME_PHASES = [
    "CONSOLIDATING",  # 横盘整理
    "EMERGING",  # 趋势萌芽
    "DEVELOPING",  # 趋势发展
    "MATURE",  # 趋势成熟
    "FATIGUING",  # 趋势衰竭
    "REVERSING",  # 趋势反转
]

# 机制相似度矩阵（定义哪些机制更相似）
REGIME_SIMILARITY_MATRIX = {
    "CONSOLIDATING": {
        "CONSOLIDATING": 1.0,
        "EMERGING": 0.5,
        "DEVELOPING": 0.2,
        "MATURE": 0.1,
        "FATIGUING": 0.2,
        "REVERSING": 0.3,
    },
    "EMERGING": {
        "CONSOLIDATING": 0.5,
        "EMERGING": 1.0,
        "DEVELOPING": 0.8,
        "MATURE": 0.3,
        "FATIGUING": 0.2,
        "REVERSING": 0.2,
    },
    "DEVELOPING": {
        "CONSOLIDATING": 0.2,
        "EMERGING": 0.8,
        "DEVELOPING": 1.0,
        "MATURE": 0.7,
        "FATIGUING": 0.3,
        "REVERSING": 0.1,
    },
    "MATURE": {
        "CONSOLIDATING": 0.1,
        "EMERGING": 0.3,
        "DEVELOPING": 0.7,
        "MATURE": 1.0,
        "FATIGUING": 0.8,
        "REVERSING": 0.3,
    },
    "FATIGUING": {
        "CONSOLIDATING": 0.2,
        "EMERGING": 0.2,
        "DEVELOPING": 0.3,
        "MATURE": 0.8,
        "FATIGUING": 1.0,
        "REVERSING": 0.7,
    },
    "REVERSING": {
        "CONSOLIDATING": 0.3,
        "EMERGING": 0.2,
        "DEVELOPING": 0.1,
        "MATURE": 0.3,
        "FATIGUING": 0.7,
        "REVERSING": 1.0,
    },
}

# 机制类别（用于粗粒度匹配）
REGIME_CATEGORIES = {
    "CONSOLIDATING": "range",  # 震荡
    "EMERGING": "trend",  # 趋势
    "DEVELOPING": "trend",  # 趋势
    "MATURE": "trend",  # 趋势
    "FATIGUING": "transition",  # 过渡
    "REVERSING": "transition",  # 过渡
}


@dataclass
class RegimeMatchResult:
    """机制匹配结果"""

    experience: Experience
    regime_similarity: float  # 机制相似度 (0-1)
    regime_weight: float  # 机制权重 (0-1)
    is_same_regime: bool  # 是否同机制
    is_same_category: bool  # 是否同类别
    combined_weight: float  # 综合权重（机制权重 * 原始权重）


class RegimeGate:
    """
    机制门

    根据当前市场机制动态调整经验权重。

    功能：
    1. 计算机制相似度
    2. 调整经验权重
    3. 生成机制权重报告
    """

    def __init__(
        self, same_regime_boost: float = 1.5, cross_regime_penalty: float = 0.5, category_match_boost: float = 1.2
    ):
        """
        初始化机制门

        Args:
            same_regime_boost: 同机制加权系数
            cross_regime_penalty: 异机制惩罚系数
            category_match_boost: 同类别加权系数
        """
        self.same_regime_boost = same_regime_boost
        self.cross_regime_penalty = cross_regime_penalty
        self.category_match_boost = category_match_boost

        # 缓存机制匹配结果
        self._similarity_cache: dict[tuple[str, str], float] = {}

    def get_regime_similarity(self, phase1: str, phase2: str) -> float:
        """
        获取两个机制阶段的相似度

        Args:
            phase1: 机制阶段1
            phase2: 机制阶段2

        Returns:
            相似度 (0-1)
        """
        # 检查缓存
        cache_key = (phase1, phase2)
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]

        # 从矩阵获取
        if phase1 in REGIME_SIMILARITY_MATRIX and phase2 in REGIME_SIMILARITY_MATRIX[phase1]:
            similarity = REGIME_SIMILARITY_MATRIX[phase1][phase2]
        else:
            # 默认相似度
            similarity = 0.5 if phase1 == phase2 else 0.3

        # 缓存结果
        self._similarity_cache[cache_key] = similarity

        return similarity

    def get_regime_category(self, phase: str) -> str:
        """获取机制类别"""
        return REGIME_CATEGORIES.get(phase, "unknown")

    def calculate_regime_weight(
        self, experience_phase: str, current_phase: str, phase_confidence: float = 1.0
    ) -> float:
        """
        计算机制权重

        Args:
            experience_phase: 经验的机制阶段
            current_phase: 当前机制阶段
            phase_confidence: 阶段置信度

        Returns:
            机制权重 (0-1)
        """
        # 基础相似度
        base_similarity = self.get_regime_similarity(experience_phase, current_phase)

        # 同机制加成
        if experience_phase == current_phase:
            weight = base_similarity * self.same_regime_boost
        else:
            weight = base_similarity * self.cross_regime_penalty

        # 同类别加成
        if self.get_regime_category(experience_phase) == self.get_regime_category(current_phase):
            weight *= self.category_match_boost

        # 置信度调整
        weight *= phase_confidence

        return min(weight, 1.0)  # 限制在 0-1

    def apply_regime_weights(
        self, matches: list[ExperienceMatch], current_phase: str, phase_confidence: float = 1.0
    ) -> list[RegimeMatchResult]:
        """
        对经验匹配结果应用机制权重

        Args:
            matches: 经验匹配列表
            current_phase: 当前机制阶段
            phase_confidence: 阶段置信度

        Returns:
            应用机制权重后的结果列表
        """
        results = []

        for match in matches:
            exp = match.experience

            # 计算机制权重
            regime_weight = self.calculate_regime_weight(exp.trend_phase, current_phase, phase_confidence)

            # 计算综合权重
            combined_weight = match.weight * regime_weight

            # 创建结果
            result = RegimeMatchResult(
                experience=exp,
                regime_similarity=self.get_regime_similarity(exp.trend_phase, current_phase),
                regime_weight=regime_weight,
                is_same_regime=(exp.trend_phase == current_phase),
                is_same_category=(self.get_regime_category(exp.trend_phase) == self.get_regime_category(current_phase)),
                combined_weight=combined_weight,
            )
            results.append(result)

        # 按综合权重排序
        results.sort(key=lambda x: x.combined_weight, reverse=True)

        return results

    def aggregate_by_regime(self, results: list[RegimeMatchResult]) -> dict[str, dict]:
        """
        按机制聚合经验

        Args:
            results: 机制匹配结果列表

        Returns:
            按机制聚合的统计信息
        """
        regime_stats = {}

        for result in results:
            phase = result.experience.trend_phase

            if phase not in regime_stats:
                regime_stats[phase] = {
                    "count": 0,
                    "returns": [],
                    "weights": [],
                    "regime_weights": [],
                    "combined_weights": [],
                }

            stats = regime_stats[phase]
            stats["count"] += 1
            stats["returns"].append(result.experience.pnl_pct)
            stats["weights"].append(result.experience.risk_adjusted_return)
            stats["regime_weights"].append(result.regime_weight)
            stats["combined_weights"].append(result.combined_weight)

        # 计算统计量
        aggregated = {}
        for phase, stats in regime_stats.items():
            returns = np.array(stats["returns"])
            combined_weights = np.array(stats["combined_weights"])

            # 加权平均收益
            if combined_weights.sum() > 0:
                avg_return = np.average(returns, weights=combined_weights)
            else:
                avg_return = returns.mean()

            # 胜率
            win_rate = (returns > 0).sum() / len(returns) if len(returns) > 0 else 0

            aggregated[phase] = {
                "count": stats["count"],
                "avg_return": round(float(avg_return), 2),
                "win_rate": round(float(win_rate), 2),
                "avg_regime_weight": round(float(np.mean(stats["regime_weights"])), 2),
                "avg_combined_weight": round(float(np.mean(stats["combined_weights"])), 2),
            }

        return aggregated

    def generate_regime_report(self, current_phase: str, results: list[RegimeMatchResult]) -> str:
        """
        生成机制权重报告

        Args:
            current_phase: 当前机制阶段
            results: 机制匹配结果列表

        Returns:
            格式化的报告文本
        """
        if not results:
            return "无历史经验"

        # 统计同机制和异机制
        same_regime = [r for r in results if r.is_same_regime]
        cross_regime = [r for r in results if not r.is_same_regime]

        report = f"""
## 机制权重分析

当前机制：**{current_phase}**

### 经验分布
- 同机制经验：{len(same_regime)} 条（平均权重 {np.mean([r.regime_weight for r in same_regime]):.2f}）
- 异机制经验：{len(cross_regime)} 条（平均权重 {np.mean([r.regime_weight for r in cross_regime]):.2f}）

### 权重调整建议
"""

        if len(same_regime) >= 3:
            report += "- 同机制经验充足，建议优先参考\n"
        elif len(same_regime) >= 1:
            report += "- 同机制经验有限，建议结合异机制经验综合判断\n"
        else:
            report += "- 无同机制经验，建议谨慎参考异机制经验\n"

        # 按机制聚合
        regime_agg = self.aggregate_by_regime(results)
        if regime_agg:
            report += "\n### 各机制统计\n"
            for phase, stats in regime_agg.items():
                report += f"- **{phase}**：{stats['count']}次，平均收益{stats['avg_return']:+.2f}%，胜率{int(stats['win_rate'] * 100)}%\n"

        return report

    def generate_strategy_mix(self, results: list[RegimeMatchResult], current_phase: str) -> dict:
        """
        生成策略混合报告

        输出类似："现在80%像策略A，20%像策略B"

        Args:
            results: 机制匹配结果列表
            current_phase: 当前机制阶段

        Returns:
            策略混合报告字典
        """
        if not results:
            return {
                "strategy_weights": {},
                "confidence": 0.0,
                "current_phase": current_phase,
                "total_experiences": 0,
            }

        # 按机制阶段分组
        phase_groups = {}
        for result in results:
            phase = result.experience.trend_phase
            if phase not in phase_groups:
                phase_groups[phase] = []
            phase_groups[phase].append(result)

        # 计算每个阶段的总权重
        phase_weights = {}
        total_weight = 0.0

        for phase, group in phase_groups.items():
            # 使用综合权重的平均值
            avg_weight = np.mean([r.combined_weight for r in group])
            phase_weights[phase] = avg_weight
            total_weight += avg_weight

        # 归一化权重
        if total_weight > 0:
            strategy_weights = {phase: round(weight / total_weight, 3) for phase, weight in phase_weights.items()}
        else:
            strategy_weights = {phase: 1.0 / len(phase_groups) for phase in phase_groups}

        # 计算置信度
        # 置信度 = 同机制经验占比 * 平均机制权重
        same_regime = [r for r in results if r.is_same_regime]
        same_regime_ratio = len(same_regime) / len(results) if results else 0
        avg_regime_weight = np.mean([r.regime_weight for r in results]) if results else 0
        confidence = same_regime_ratio * avg_regime_weight

        # 构建策略描述
        strategy_descriptions = []
        for phase, weight in sorted(strategy_weights.items(), key=lambda x: x[1], reverse=True):
            group = phase_groups[phase]
            avg_return = np.mean([r.experience.pnl_pct for r in group])
            win_rate = sum(1 for r in group if r.experience.pnl_pct > 0) / len(group)

            strategy_descriptions.append(
                {
                    "phase": phase,
                    "weight": weight,
                    "avg_return": round(float(avg_return), 2),
                    "win_rate": round(float(win_rate), 2),
                    "count": len(group),
                }
            )

        return {
            "strategy_weights": strategy_weights,
            "confidence": round(float(confidence), 3),
            "current_phase": current_phase,
            "total_experiences": len(results),
            "same_regime_count": len(same_regime),
            "strategy_descriptions": strategy_descriptions,
        }


class RegimeAwareRetriever:
    """
    机制感知检索器

    结合向量相似度和机制相似度进行经验检索。
    """

    def __init__(self, regime_gate: RegimeGate | None = None):
        self.regime_gate = regime_gate or RegimeGate()

    def retrieve_with_regime_awareness(
        self,
        experiences: list[Experience],
        query_vector: list[float],
        current_phase: str,
        phase_confidence: float = 1.0,
        top_k: int = 10,
        min_similarity: float = 0.3,
        regime_weight_factor: float = 0.3,
    ) -> list[RegimeMatchResult]:
        """
        机制感知检索

        Args:
            experiences: 经验列表
            query_vector: 查询向量
            current_phase: 当前机制阶段
            phase_confidence: 阶段置信度
            top_k: 返回数量
            min_similarity: 最小相似度阈值
            regime_weight_factor: 机制权重因子（0-1，越大机制权重影响越大）

        Returns:
            机制匹配结果列表
        """
        if not experiences:
            return []

        # 计算向量相似度
        from .vector_enhancement import VectorEnhancer

        enhancer = VectorEnhancer()

        matches = []
        for exp in experiences:
            if not exp.feature_vector:
                continue

            # 向量相似度
            vector_sim = enhancer.combined_similarity(query_vector, exp.feature_vector)

            if vector_sim < min_similarity:
                continue

            # 创建匹配结果
            match = ExperienceMatch(
                experience=exp,
                similarity=vector_sim,
                distance=1 - vector_sim,
                weight=vector_sim,
            )
            matches.append(match)

        # 应用机制权重
        results = self.regime_gate.apply_regime_weights(matches, current_phase, phase_confidence)

        # 调整综合权重（结合向量相似度和机制权重）
        for result in results:
            vector_weight = result.experience.feature_vector  # 原始向量权重
            regime_weight = result.regime_weight

            # 综合权重 = (1 - factor) * 向量权重 + factor * 机制权重
            result.combined_weight = (
                (1 - regime_weight_factor) * result.combined_weight  # 向量权重部分
                + regime_weight_factor * regime_weight  # 机制权重部分
            )

        # 重新排序
        results.sort(key=lambda x: x.combined_weight, reverse=True)

        return results[:top_k]


def create_regime_gate(same_regime_boost: float = 1.5, cross_regime_penalty: float = 0.5) -> RegimeGate:
    """创建机制门实例"""
    return RegimeGate(
        same_regime_boost=same_regime_boost,
        cross_regime_penalty=cross_regime_penalty,
    )


def get_regime_weight(experience_phase: str, current_phase: str) -> float:
    """快速获取机制权重"""
    gate = RegimeGate()
    return gate.calculate_regime_weight(experience_phase, current_phase)
