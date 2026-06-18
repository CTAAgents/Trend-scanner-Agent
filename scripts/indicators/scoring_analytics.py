"""
打分分析模块

提供打分有效性分析功能：
- ScoringAnalytics: 打分有效性分析
- 打分-结果相关性计算
- 维度有效性分析
- 打分有效性报告生成
"""

from datetime import datetime

import numpy as np


class ScoringAnalytics:
    """
    打分有效性分析

    分析打分结果与实际交易结果的关联，评估打分体系的有效性。
    """

    def __init__(self, data_store):
        """
        初始化打分分析器

        参数:
            data_store: DataStore 实例
        """
        self.data_store = data_store

    def calculate_correlation(self, symbol: str = None, start_date: str = None, end_date: str = None) -> dict:
        """
        计算打分-结果相关性

        参数:
            symbol: 品种代码（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        返回:
            相关性统计字典
        """
        # 获取已完成的反馈
        feedbacks = self.data_store.get_scoring_feedback(
            symbol=symbol,
            status="completed",
            start_date=start_date,
            end_date=end_date,
        )

        if len(feedbacks) < 10:
            return {
                "correlation": None,
                "accuracy": None,
                "sample_size": len(feedbacks),
                "insufficient_data": True,
            }

        # 计算方向准确率
        correct = sum(1 for f in feedbacks if f.get("direction_correct"))
        accuracy = correct / len(feedbacks)

        # 计算打分与收益的相关性
        scores = [f.get("filtered_composite", 0) for f in feedbacks]
        returns = [f.get("actual_return", 0) for f in feedbacks]

        # 过滤无效数据
        valid_pairs = [(s, r) for s, r in zip(scores, returns) if s != 0 and r != 0]
        if len(valid_pairs) < 5:
            correlation = 0
        else:
            valid_scores, valid_returns = zip(*valid_pairs)
            correlation = np.corrcoef(valid_scores, valid_returns)[0, 1]

        # 计算胜率
        wins = sum(1 for f in feedbacks if f.get("outcome") == "WIN")
        win_rate = wins / len(feedbacks)

        # 计算平均收益
        avg_return = np.mean([f.get("actual_return", 0) for f in feedbacks])

        return {
            "correlation": correlation,
            "accuracy": accuracy,
            "win_rate": win_rate,
            "average_return": avg_return,
            "sample_size": len(feedbacks),
            "insufficient_data": False,
        }

    def calculate_correlation_by_state(self, market_state: str, symbol: str = None) -> dict:
        """
        按市场状态计算相关性

        参数:
            market_state: 市场状态
            symbol: 品种代码（可选）

        返回:
            相关性统计字典
        """
        feedbacks = self.data_store.get_scoring_feedback(
            symbol=symbol,
            status="completed",
        )

        # 过滤特定市场状态
        state_feedbacks = [f for f in feedbacks if f.get("market_state") == market_state]

        if len(state_feedbacks) < 5:
            return {
                "correlation": None,
                "accuracy": None,
                "sample_size": len(state_feedbacks),
                "insufficient_data": True,
            }

        # 计算方向准确率
        correct = sum(1 for f in state_feedbacks if f.get("direction_correct"))
        accuracy = correct / len(state_feedbacks)

        # 计算胜率
        wins = sum(1 for f in state_feedbacks if f.get("outcome") == "WIN")
        win_rate = wins / len(state_feedbacks)

        return {
            "accuracy": accuracy,
            "win_rate": win_rate,
            "sample_size": len(state_feedbacks),
            "insufficient_data": False,
        }

    def calculate_dimension_effectiveness(self, symbol: str = None) -> dict:
        """
        计算各维度的有效性

        参数:
            symbol: 品种代码（可选）

        返回:
            维度有效性字典
        """
        feedbacks = self.data_store.get_scoring_feedback(
            symbol=symbol,
            status="completed",
        )

        if len(feedbacks) < 10:
            return {}

        # 提取维度得分和结果
        dimension_stats = {}

        for feedback in feedbacks:
            dim_scores = feedback.get("dimension_scores", {})
            actual_return = feedback.get("actual_return", 0)
            direction_correct = feedback.get("direction_correct", False)

            for dim_name, dim_score in dim_scores.items():
                if dim_name not in dimension_stats:
                    dimension_stats[dim_name] = {
                        "scores": [],
                        "returns": [],
                        "correct": 0,
                        "total": 0,
                    }

                dimension_stats[dim_name]["scores"].append(dim_score)
                dimension_stats[dim_name]["returns"].append(actual_return)
                dimension_stats[dim_name]["total"] += 1
                if direction_correct:
                    dimension_stats[dim_name]["correct"] += 1

        # 计算各维度的有效性指标
        effectiveness = {}
        for dim_name, stats in dimension_stats.items():
            if len(stats["scores"]) < 5:
                continue

            # 计算维度得分与收益的相关性
            correlation = np.corrcoef(stats["scores"], stats["returns"])[0, 1]

            # 计算维度方向准确率
            accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0

            effectiveness[dim_name] = {
                "correlation": correlation,
                "accuracy": accuracy,
                "sample_size": stats["total"],
                "avg_score": np.mean(stats["scores"]),
                "avg_return": np.mean(stats["returns"]),
            }

        return effectiveness

    def generate_report(self, symbol: str = None) -> str:
        """
        生成打分有效性报告

        参数:
            symbol: 品种代码（可选）

        返回:
            报告文本
        """
        # 整体统计
        overall = self.calculate_correlation(symbol)

        # 按市场状态统计
        state_stats = {}
        for state in ["STRONG_UPTREND", "WEAK_UPTREND", "RANGE_BOUND", "WEAK_DOWNTREND", "STRONG_DOWNTREND"]:
            state_stats[state] = self.calculate_correlation_by_state(state, symbol)

        # 维度有效性
        dimension_effectiveness = self.calculate_dimension_effectiveness(symbol)

        # 生成报告
        report = []
        report.append("# 打分有效性报告")
        report.append(f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if symbol:
            report.append(f"**品种**: {symbol}")

        # 整体统计
        report.append("\n## 1. 整体统计")
        if overall.get("insufficient_data"):
            report.append(f"- 样本量不足（{overall['sample_size']}），无法计算相关性")
        else:
            report.append(f"- 样本量：{overall['sample_size']}")
            report.append(f"- 方向准确率：{overall['accuracy']:.2%}")
            report.append(f"- 打分-收益相关性：{overall['correlation']:.4f}")
            report.append(f"- 胜率：{overall['win_rate']:.2%}")
            report.append(f"- 平均收益：{overall['average_return']:.4f}")

        # 按市场状态统计
        report.append("\n## 2. 按市场状态统计")
        report.append("| 市场状态 | 样本量 | 方向准确率 | 胜率 |")
        report.append("|----------|--------|------------|------|")
        for state, stats in state_stats.items():
            if stats.get("insufficient_data"):
                report.append(f"| {state} | {stats['sample_size']} | - | - |")
            else:
                report.append(
                    f"| {state} | {stats['sample_size']} | {stats['accuracy']:.2%} | {stats['win_rate']:.2%} |"
                )

        # 维度有效性
        report.append("\n## 3. 维度有效性分析")
        if dimension_effectiveness:
            report.append("| 维度 | 相关性 | 方向准确率 | 样本量 | 平均得分 | 平均收益 |")
            report.append("|------|--------|------------|--------|----------|----------|")
            for dim_name, stats in sorted(
                dimension_effectiveness.items(), key=lambda x: abs(x[1].get("correlation", 0)), reverse=True
            ):
                report.append(
                    f"| {dim_name} | {stats['correlation']:.4f} | "
                    f"{stats['accuracy']:.2%} | {stats['sample_size']} | "
                    f"{stats['avg_score']:.4f} | {stats['avg_return']:.4f} |"
                )
        else:
            report.append("- 数据不足，无法计算维度有效性")

        # 建议
        report.append("\n## 4. 建议")
        if overall.get("insufficient_data"):
            report.append("- 继续积累数据，至少需要 100 条已完成的反馈记录")
        else:
            if overall["accuracy"] < 0.55:
                report.append("- 方向准确率偏低，建议检查打分逻辑")
            if overall["correlation"] < 0.1:
                report.append("- 打分-收益相关性较低，建议优化打分权重")
            if overall["win_rate"] < 0.5:
                report.append("- 胜率偏低，建议优化入场条件")

        return "\n".join(report)

    def get_optimization_suggestions(self, symbol: str = None) -> list[dict]:
        """
        获取优化建议

        参数:
            symbol: 品种代码（可选）

        返回:
            优化建议列表
        """
        suggestions = []

        # 整体统计
        overall = self.calculate_correlation(symbol)
        if overall.get("insufficient_data"):
            return [{"type": "data", "message": "数据不足，继续积累反馈记录"}]

        # 维度有效性
        dimension_effectiveness = self.calculate_dimension_effectiveness(symbol)

        # 检查方向准确率
        if overall["accuracy"] < 0.55:
            suggestions.append(
                {
                    "type": "accuracy",
                    "message": f"方向准确率偏低（{overall['accuracy']:.2%}），建议检查打分逻辑",
                    "priority": "high",
                }
            )

        # 检查相关性
        if overall["correlation"] < 0.1:
            suggestions.append(
                {
                    "type": "correlation",
                    "message": f"打分-收益相关性较低（{overall['correlation']:.4f}），建议优化打分权重",
                    "priority": "medium",
                }
            )

        # 检查维度有效性
        for dim_name, stats in dimension_effectiveness.items():
            if stats.get("correlation", 0) < 0:
                suggestions.append(
                    {
                        "type": "dimension",
                        "message": f"维度 {dim_name} 相关性为负（{stats['correlation']:.4f}），建议降低权重",
                        "priority": "medium",
                        "dimension": dim_name,
                    }
                )

        return suggestions
