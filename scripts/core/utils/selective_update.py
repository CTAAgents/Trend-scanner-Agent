"""
选择性更新模块

实现经验池的选择性更新，防止灾难性遗忘。

核心思想：
- 机制感知衰减：同机制经验衰减更慢
- 知识蒸馏：合并相似经验，保留关键经验
- 经验池清理：定期清理过时经验

设计原则：
- 向后兼容
- 渐进增强
- 性能优先
"""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from .models import Experience


@dataclass
class DecayConfig:
    """衰减配置"""

    # 时间衰减
    time_half_life: int = 30  # 时间半衰期（天）

    # 机制衰减
    same_regime_factor: float = 1.0  # 同机制衰减因子（不衰减）
    related_regime_factor: float = 0.7  # 相关机制衰减因子
    cross_regime_factor: float = 0.3  # 异机制衰减因子（重度衰减）

    # 绩效衰减
    profit_factor: float = 1.0  # 盈利经验因子（不衰减）
    loss_factor: float = 0.8  # 亏损经验因子（轻度衰减）

    # 相关机制定义
    related_regimes: dict[str, list[str]] = field(
        default_factory=lambda: {
            "CONSOLIDATING": ["EMERGING", "FATIGUING"],
            "EMERGING": ["CONSOLIDATING", "DEVELOPING"],
            "DEVELOPING": ["EMERGING", "MATURE"],
            "MATURE": ["DEVELOPING", "FATIGUING"],
            "FATIGUING": ["MATURE", "REVERSING"],
            "REVERSING": ["FATIGUING", "CONSOLIDATING"],
        }
    )


class SelectiveUpdater:
    """
    选择性更新器

    实现机制感知衰减和知识蒸馏。
    """

    def __init__(self, config: DecayConfig | None = None):
        """
        初始化选择性更新器

        Args:
            config: 衰减配置
        """
        self.config = config or DecayConfig()

    def calculate_decay_factor(self, experience: Experience, current_phase: str) -> float:
        """
        计算经验的衰减因子

        Args:
            experience: 经验对象
            current_phase: 当前市场阶段

        Returns:
            衰减因子（0-1，越大表示保留越多）
        """
        # 1. 时间衰减
        try:
            exp_time = datetime.fromisoformat(experience.timestamp.replace("Z", "+00:00").split("+")[0])
            age_days = (datetime.now() - exp_time).days
        except (ValueError, AttributeError):
            age_days = 30  # 默认30天

        time_decay = np.exp(-age_days / self.config.time_half_life)

        # 2. 机制衰减
        regime_decay = self._calculate_regime_decay(experience.trend_phase, current_phase)

        # 3. 绩效衰减
        performance_decay = self._calculate_performance_decay(experience)

        # 综合衰减因子
        decay_factor = time_decay * regime_decay * performance_decay

        return float(np.clip(decay_factor, 0.01, 1.0))

    def _calculate_regime_decay(self, experience_phase: str, current_phase: str) -> float:
        """计算机制衰减"""
        if experience_phase == current_phase:
            return self.config.same_regime_factor

        # 检查是否为相关机制
        related = self.config.related_regimes.get(current_phase, [])
        if experience_phase in related:
            return self.config.related_regime_factor

        return self.config.cross_regime_factor

    def _calculate_performance_decay(self, experience: Experience) -> float:
        """计算绩效衰减"""
        if experience.pnl_pct > 0:
            return self.config.profit_factor
        else:
            return self.config.loss_factor

    def apply_decay_to_weights(
        self, experiences: list[Experience], current_phase: str
    ) -> list[tuple[Experience, float]]:
        """
        对经验权重应用衰减

        Args:
            experiences: 经验列表
            current_phase: 当前市场阶段

        Returns:
            [(经验, 衰减因子), ...]
        """
        results = []

        for exp in experiences:
            decay = self.calculate_decay_factor(exp, current_phase)
            results.append((exp, decay))

        return results

    def filter_by_decay(
        self, experiences: list[Experience], current_phase: str, min_decay: float = 0.1
    ) -> list[Experience]:
        """
        根据衰减因子过滤经验

        Args:
            experiences: 经验列表
            current_phase: 当前市场阶段
            min_decay: 最小衰减因子阈值

        Returns:
            过滤后的经验列表
        """
        filtered = []

        for exp in experiences:
            decay = self.calculate_decay_factor(exp, current_phase)
            if decay >= min_decay:
                filtered.append(exp)

        return filtered


class KnowledgeDistiller:
    """
    知识蒸馏器

    合并相似经验，保留关键经验。
    """

    def __init__(self, max_experiences: int = 1000, similarity_threshold: float = 0.8):
        """
        初始化知识蒸馏器

        Args:
            max_experiences: 最大经验数量
            similarity_threshold: 相似度阈值
        """
        self.max_experiences = max_experiences
        self.similarity_threshold = similarity_threshold

    def distill(self, experiences: list[Experience]) -> list[Experience]:
        """
        蒸馏经验

        Args:
            experiences: 经验列表

        Returns:
            蒸馏后的经验列表
        """
        if len(experiences) <= self.max_experiences:
            return experiences

        # 1. 按机制分组
        grouped = self._group_by_regime(experiences)

        # 2. 对每组进行蒸馏
        distilled = []
        for regime, exps in grouped.items():
            if len(exps) <= 5:
                # 经验较少，全部保留
                distilled.extend(exps)
            else:
                # 经验较多，保留关键经验
                key_exps = self._select_key_experiences(exps, n=5)
                distilled.extend(key_exps)

        return distilled[: self.max_experiences]

    def _group_by_regime(self, experiences: list[Experience]) -> dict[str, list[Experience]]:
        """按机制分组"""
        grouped = {}

        for exp in experiences:
            phase = exp.trend_phase or "UNKNOWN"
            if phase not in grouped:
                grouped[phase] = []
            grouped[phase].append(exp)

        return grouped

    def _select_key_experiences(self, experiences: list[Experience], n: int = 5) -> list[Experience]:
        """
        选择关键经验

        保留：
        1. 最新的经验
        2. 盈利最大的经验
        3. 风险调整收益最高的经验
        """
        # 按时间排序（最新）
        by_time = sorted(experiences, key=lambda x: x.timestamp, reverse=True)

        # 按收益排序（最高）
        by_return = sorted(experiences, key=lambda x: x.pnl_pct, reverse=True)

        # 按风险调整收益排序
        by_risk_adj = sorted(experiences, key=lambda x: x.risk_adjusted_return, reverse=True)

        # 合并选择
        selected = set()
        result = []

        # 选择最新的 2 个
        for exp in by_time[:2]:
            if exp.experience_id not in selected:
                selected.add(exp.experience_id)
                result.append(exp)

        # 选择收益最高的 2 个
        for exp in by_return[:2]:
            if exp.experience_id not in selected:
                selected.add(exp.experience_id)
                result.append(exp)

        # 选择风险调整收益最高的 1 个
        for exp in by_risk_adj[:1]:
            if exp.experience_id not in selected:
                selected.add(exp.experience_id)
                result.append(exp)

        # 如果还不够，从剩余中选择
        for exp in experiences:
            if len(result) >= n:
                break
            if exp.experience_id not in selected:
                selected.add(exp.experience_id)
                result.append(exp)

        return result[:n]

    def merge_similar_experiences(self, experiences: list[Experience]) -> list[Experience]:
        """
        合并相似经验

        将特征向量非常相似的经验合并为一个。
        """
        if not experiences:
            return []

        # 简化实现：保留最新的，丢弃重复的
        # 实际应该计算向量相似度
        seen = set()
        merged = []

        # 按时间排序
        sorted_exps = sorted(experiences, key=lambda x: x.timestamp, reverse=True)

        for exp in sorted_exps:
            # 使用简化标识（实际应该用向量相似度）
            key = (exp.trend_phase, exp.action_taken)

            if key not in seen:
                seen.add(key)
                merged.append(exp)

        return merged


class ExperiencePoolManager:
    """
    经验池管理器

    整合选择性更新和知识蒸馏。
    """

    def __init__(
        self, max_experiences: int = 1000, decay_config: DecayConfig | None = None, distill_threshold: float = 0.8
    ):
        """
        初始化经验池管理器

        Args:
            max_experiences: 最大经验数量
            decay_config: 衰减配置
            distill_threshold: 蒸馏相似度阈值
        """
        self.max_experiences = max_experiences
        self.selective_updater = SelectiveUpdater(decay_config)
        self.distiller = KnowledgeDistiller(max_experiences, distill_threshold)

    def update_pool(self, experiences: list[Experience], current_phase: str) -> list[Experience]:
        """
        更新经验池

        Args:
            experiences: 当前经验列表
            current_phase: 当前市场阶段

        Returns:
            更新后的经验列表
        """
        # 1. 过滤低衰减因子的经验
        filtered = self.selective_updater.filter_by_decay(experiences, current_phase, min_decay=0.1)

        # 2. 蒸馏
        distilled = self.distiller.distill(filtered)

        return distilled

    def get_decay_report(self, experiences: list[Experience], current_phase: str) -> dict:
        """
        获取衰减报告

        Args:
            experiences: 经验列表
            current_phase: 当前市场阶段

        Returns:
            衰减报告
        """
        decay_results = self.selective_updater.apply_decay_to_weights(experiences, current_phase)

        # 统计
        decay_values = [d for _, d in decay_results]

        # 按机制分组统计
        regime_stats = {}
        for exp, decay in decay_results:
            phase = exp.trend_phase or "UNKNOWN"
            if phase not in regime_stats:
                regime_stats[phase] = {"count": 0, "avg_decay": []}
            regime_stats[phase]["count"] += 1
            regime_stats[phase]["avg_decay"].append(decay)

        # 计算平均衰减
        for phase in regime_stats:
            stats = regime_stats[phase]
            stats["avg_decay"] = round(float(np.mean(stats["avg_decay"])), 3)

        return {
            "total_experiences": len(experiences),
            "avg_decay": round(float(np.mean(decay_values)), 3),
            "min_decay": round(float(np.min(decay_values)), 3),
            "max_decay": round(float(np.max(decay_values)), 3),
            "regime_stats": regime_stats,
        }


# 便捷函数
def create_selective_updater(config: DecayConfig | None = None) -> SelectiveUpdater:
    """创建选择性更新器"""
    return SelectiveUpdater(config)


def create_knowledge_distiller(max_experiences: int = 1000) -> KnowledgeDistiller:
    """创建知识蒸馏器"""
    return KnowledgeDistiller(max_experiences)


def create_pool_manager(max_experiences: int = 1000) -> ExperiencePoolManager:
    """创建经验池管理器"""
    return ExperiencePoolManager(max_experiences)


def calculate_experience_decay(experience: Experience, current_phase: str) -> float:
    """快速计算经验衰减因子"""
    updater = SelectiveUpdater()
    return updater.calculate_decay_factor(experience, current_phase)
