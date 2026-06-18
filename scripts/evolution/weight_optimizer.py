"""
权重优化器模块

基于历史反馈数据优化打分权重：
- WeightOptimizer: 权重优化器
- 支持网格搜索和贝叶斯优化
- 基于市场状态的权重调整
"""

from itertools import product

import numpy as np


class WeightOptimizer:
    """
    权重优化器

    基于历史反馈数据，优化打分维度权重。
    """

    # 维度权重搜索空间
    WEIGHT_SPACE = {
        "leading_signals": [0.05, 0.08, 0.10],  # ≤10%约束
        "trend_confirmation": [0.35, 0.40, 0.45, 0.50, 0.55],  # 核心维度
        "momentum_health": [0.20, 0.25, 0.30, 0.35, 0.40],  # 核心维度
        "volatility": [0.05, 0.08, 0.10, 0.12, 0.15],  # ≤15%约束
        "trend_strength": [0.03, 0.05, 0.08, 0.10],  # ≤10%约束
    }

    # 市场状态权重调整系数
    STATE_ADJUSTMENTS = {
        "STRONG_UPTREND": {
            "leading_signals": 0.8,  # 降低
            "trend_confirmation": 1.3,  # 提升
            "momentum_health": 1.0,
            "volatility": 1.0,
            "trend_strength": 1.0,
        },
        "WEAK_UPTREND": {
            "leading_signals": 1.0,
            "trend_confirmation": 1.1,
            "momentum_health": 1.0,
            "volatility": 1.0,
            "trend_strength": 1.0,
        },
        "RANGE_BOUND": {
            "leading_signals": 1.2,  # 提升
            "trend_confirmation": 0.7,  # 降低
            "momentum_health": 1.3,  # 提升
            "volatility": 1.3,  # 提升
            "trend_strength": 0.8,  # 降低
        },
        "WEAK_DOWNTREND": {
            "leading_signals": 1.0,
            "trend_confirmation": 1.1,
            "momentum_health": 1.0,
            "volatility": 1.0,
            "trend_strength": 1.0,
        },
        "STRONG_DOWNTREND": {
            "leading_signals": 0.8,
            "trend_confirmation": 1.3,
            "momentum_health": 1.0,
            "volatility": 1.0,
            "trend_strength": 1.0,
        },
    }

    def __init__(self, data_store):
        """
        初始化权重优化器

        参数:
            data_store: DataStore 实例
        """
        self.data_store = data_store

    def get_dynamic_weights(
        self, base_weights: dict[str, float], market_state: str, volatility_regime: str = "normal"
    ) -> dict[str, float]:
        """
        根据市场状态和波动率动态调整权重

        参数:
            base_weights: 基础权重
            market_state: 市场状态
            volatility_regime: 波动率状态（high/normal/low）

        返回:
            调整后的权重
        """
        # 复制基础权重
        weights = base_weights.copy()

        # 应用市场状态调整
        if market_state in self.STATE_ADJUSTMENTS:
            adjustments = self.STATE_ADJUSTMENTS[market_state]
            for dim_name, factor in adjustments.items():
                if dim_name in weights:
                    weights[dim_name] *= factor

        # 应用波动率调整
        if volatility_regime == "high":
            weights["leading_signals"] *= 1.2
            weights["trend_confirmation"] *= 0.8
        elif volatility_regime == "low":
            weights["leading_signals"] *= 0.8
            weights["trend_confirmation"] *= 1.2

        # 归一化
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def grid_search_weights(self, symbol: str = None, market_state: str = None) -> dict:
        """
        网格搜索最优权重

        参数:
            symbol: 品种代码（可选）
            market_state: 市场状态（可选）

        返回:
            最优权重和评估结果
        """
        # 获取历史反馈
        feedbacks = self.data_store.get_scoring_feedback(
            symbol=symbol,
            status="completed",
        )

        if market_state:
            feedbacks = [f for f in feedbacks if f.get("market_state") == market_state]

        if len(feedbacks) < 20:
            return {
                "optimal_weights": None,
                "improvement": 0,
                "sample_size": len(feedbacks),
                "insufficient_data": True,
            }

        # 生成权重组合
        weight_combinations = self._generate_weight_combinations()

        # 评估每个组合
        best_score = -np.inf
        best_weights = None
        baseline_score = self._evaluate_weights(None, feedbacks)  # 使用当前权重

        for weights in weight_combinations:
            score = self._evaluate_weights(weights, feedbacks)
            if score > best_score:
                best_score = score
                best_weights = weights

        # 计算改进幅度
        improvement = (best_score - baseline_score) / abs(baseline_score) if baseline_score != 0 else 0

        return {
            "optimal_weights": best_weights,
            "optimal_score": best_score,
            "baseline_score": baseline_score,
            "improvement": improvement,
            "sample_size": len(feedbacks),
            "insufficient_data": False,
        }

    def _generate_weight_combinations(self) -> list[dict[str, float]]:
        """生成权重组合"""
        combinations = []

        # 获取所有维度的搜索空间
        dims = list(self.WEIGHT_SPACE.keys())
        values_list = [self.WEIGHT_SPACE[dim] for dim in dims]

        # 生成所有组合
        for combo in product(*values_list):
            weights = dict(zip(dims, combo))

            # 检查权重和是否接近1
            total = sum(weights.values())
            if abs(total - 1.0) < 0.05:
                # 归一化
                weights = {k: v / total for k, v in weights.items()}
                combinations.append(weights)

        # 限制组合数量
        if len(combinations) > 1000:
            # 随机采样
            indices = np.random.choice(len(combinations), 1000, replace=False)
            combinations = [combinations[i] for i in indices]

        return combinations

    def _evaluate_weights(self, weights: dict[str, float] | None, feedbacks: list[dict]) -> float:
        """
        评估权重效果

        参数:
            weights: 权重（None 表示使用当前权重）
            feedbacks: 历史反馈列表

        返回:
            评估分数（夏普比率）
        """
        if not feedbacks:
            return 0.0

        # 计算加权打分
        weighted_returns = []

        for feedback in feedbacks:
            dimension_scores = feedback.get("dimension_scores", {})
            actual_return = feedback.get("actual_return", 0)

            if weights:
                # 使用新权重计算加权打分
                weighted_score = sum(dimension_scores.get(dim, 0) * weights.get(dim, 0) for dim in dimension_scores)
            else:
                # 使用原始打分
                weighted_score = feedback.get("filtered_composite", 0)

            # 如果打分方向正确，记录收益
            score_direction = 1 if weighted_score > 0.15 else (-1 if weighted_score < -0.15 else 0)
            actual_direction = feedback.get("actual_direction", 0)

            if score_direction != 0 and score_direction == actual_direction:
                weighted_returns.append(actual_return)
            elif score_direction != 0 and score_direction != actual_direction:
                weighted_returns.append(-actual_return)

        if not weighted_returns:
            return 0.0

        # 计算夏普比率
        mean_return = np.mean(weighted_returns)
        std_return = np.std(weighted_returns)

        if std_return == 0:
            return mean_return * 100  # 无波动时直接返回收益

        sharpe = mean_return / std_return * np.sqrt(252)  # 年化夏普比率

        return sharpe

    def optimize_for_state(self, symbol: str = None) -> dict[str, dict]:
        """
        为每种市场状态优化权重

        参数:
            symbol: 品种代码（可选）

        返回:
            各市场状态的最优权重
        """
        results = {}

        for state in self.STATE_ADJUSTMENTS.keys():
            result = self.grid_search_weights(symbol=symbol, market_state=state)
            results[state] = result

        return results

    def get_weight_report(self, symbol: str = None) -> str:
        """
        生成权重优化报告

        参数:
            symbol: 品种代码（可选）

        返回:
            报告文本
        """
        # 整体优化
        overall = self.grid_search_weights(symbol=symbol)

        # 按市场状态优化
        by_state = self.optimize_for_state(symbol)

        # 生成报告
        report = []
        report.append("# 权重优化报告")
        report.append(f"\n**品种**: {symbol or '全部'}")

        # 整体优化结果
        report.append("\n## 1. 整体优化")
        if overall.get("insufficient_data"):
            report.append(f"- 样本量不足（{overall['sample_size']}），无法优化")
        else:
            report.append(f"- 样本量：{overall['sample_size']}")
            report.append(f"- 基准分数：{overall['baseline_score']:.4f}")
            report.append(f"- 最优分数：{overall['optimal_score']:.4f}")
            report.append(f"- 改进幅度：{overall['improvement']:.2%}")
            if overall["optimal_weights"]:
                report.append("\n**最优权重**:")
                for dim, weight in overall["optimal_weights"].items():
                    report.append(f"  - {dim}: {weight:.4f}")

        # 按市场状态优化结果
        report.append("\n## 2. 按市场状态优化")
        report.append("| 市场状态 | 样本量 | 基准分数 | 最优分数 | 改进幅度 |")
        report.append("|----------|--------|----------|----------|----------|")
        for state, result in by_state.items():
            if result.get("insufficient_data"):
                report.append(f"| {state} | {result['sample_size']} | - | - | - |")
            else:
                report.append(
                    f"| {state} | {result['sample_size']} | "
                    f"{result['baseline_score']:.4f} | "
                    f"{result['optimal_score']:.4f} | "
                    f"{result['improvement']:.2%} |"
                )

        # 建议
        report.append("\n## 3. 建议")
        if overall.get("insufficient_data"):
            report.append("- 继续积累数据，至少需要 100 条已完成的反馈记录")
        else:
            if overall["improvement"] > 0.1:
                report.append("- 建议采用优化后的权重")
            else:
                report.append("- 当前权重效果良好，无需调整")

        return "\n".join(report)
