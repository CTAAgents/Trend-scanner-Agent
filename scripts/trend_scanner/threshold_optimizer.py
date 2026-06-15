"""
阈值优化器模块

实现打分方向阈值的动态调整：
- ThresholdOptimizer: 阈值优化器
- 波动率感知的阈值调整
- 基于反馈的阈值优化
"""

from typing import Dict, List, Optional, Tuple
import numpy as np


class ThresholdOptimizer:
    """
    阈值优化器

    根据波动率和历史反馈，动态调整打分方向阈值。
    """

    # 默认阈值
    DEFAULT_BULLISH_THRESHOLD = 0.15
    DEFAULT_BEARISH_THRESHOLD = -0.15

    # 波动率分位数阈值
    VOL_HIGH_PERCENTILE = 0.80
    VOL_LOW_PERCENTILE = 0.20

    # 阈值调整系数
    VOL_HIGH_FACTOR = 1.3  # 高波动时阈值放宽
    VOL_LOW_FACTOR = 0.8   # 低波动时阈值收紧

    # 阈值搜索空间
    THRESHOLD_SPACE = np.arange(0.05, 0.35, 0.01)

    def __init__(self, data_store):
        """
        初始化阈值优化器

        参数:
            data_store: DataStore 实例
        """
        self.data_store = data_store

    def get_dynamic_threshold(self, df, base_threshold: float = None) -> Tuple[float, float]:
        """
        根据波动率动态调整打分方向阈值

        参数:
            df: DataFrame，包含 OHLCV 数据
            base_threshold: 基础阈值（可选）

        返回:
            (bullish_threshold, bearish_threshold)
        """
        if base_threshold is None:
            base_threshold = self.DEFAULT_BULLISH_THRESHOLD

        # 计算波动率分位数
        if 'atr' not in df.columns or 'close' not in df.columns:
            return base_threshold, -base_threshold

        atr_pct = df['atr'] / df['close'] * 100
        vol_percentile = atr_pct.rolling(250).rank(pct=True).iloc[-1]

        if np.isnan(vol_percentile):
            return base_threshold, -base_threshold

        # 波动率调整
        # 高波动时，阈值放宽（减少误报）
        # 低波动时，阈值收紧（提高灵敏度）
        if vol_percentile > self.VOL_HIGH_PERCENTILE:
            factor = self.VOL_HIGH_FACTOR
        elif vol_percentile < self.VOL_LOW_PERCENTILE:
            factor = self.VOL_LOW_FACTOR
        else:
            # 线性插值
            factor = 1.0 + (vol_percentile - 0.5) * (self.VOL_HIGH_FACTOR - 1.0) / 0.3

        threshold = base_threshold * factor

        return threshold, -threshold

    def optimize_threshold(self, symbol: str = None,
                          volatility_regime: str = None) -> Dict:
        """
        基于历史反馈优化阈值

        参数:
            symbol: 品种代码（可选）
            volatility_regime: 波动率状态（high/normal/low）

        返回:
            优化结果
        """
        # 获取历史反馈
        feedbacks = self.data_store.get_scoring_feedback(
            symbol=symbol,
            status='completed',
        )

        if volatility_regime:
            feedbacks = [f for f in feedbacks if f.get('volatility_regime') == volatility_regime]

        if len(feedbacks) < 20:
            return {
                'optimal_threshold': None,
                'optimal_accuracy': None,
                'optimal_coverage': None,
                'sample_size': len(feedbacks),
                'insufficient_data': True,
            }

        # 评估不同阈值
        results = []
        for threshold in self.THRESHOLD_SPACE:
            accuracy, coverage = self._evaluate_threshold(feedbacks, threshold)
            f1_score = 2 * accuracy * coverage / (accuracy + coverage + 1e-8)
            results.append({
                'threshold': threshold,
                'accuracy': accuracy,
                'coverage': coverage,
                'f1_score': f1_score,
            })

        # 选择 F1 分数最高的阈值
        best = max(results, key=lambda x: x['f1_score'])

        # 计算基准（使用默认阈值）
        baseline_accuracy, baseline_coverage = self._evaluate_threshold(
            feedbacks, self.DEFAULT_BULLISH_THRESHOLD
        )
        baseline_f1 = 2 * baseline_accuracy * baseline_coverage / (baseline_accuracy + baseline_coverage + 1e-8)

        return {
            'optimal_threshold': best['threshold'],
            'optimal_accuracy': best['accuracy'],
            'optimal_coverage': best['coverage'],
            'optimal_f1': best['f1_score'],
            'baseline_threshold': self.DEFAULT_BULLISH_THRESHOLD,
            'baseline_accuracy': baseline_accuracy,
            'baseline_coverage': baseline_coverage,
            'baseline_f1': baseline_f1,
            'improvement': (best['f1_score'] - baseline_f1) / baseline_f1 if baseline_f1 > 0 else 0,
            'sample_size': len(feedbacks),
            'insufficient_data': False,
        }

    def _evaluate_threshold(self, feedbacks: List[Dict],
                           threshold: float) -> Tuple[float, float]:
        """
        评估阈值效果

        参数:
            feedbacks: 历史反馈列表
            threshold: 阈值

        返回:
            (accuracy, coverage)
        """
        if not feedbacks:
            return 0.0, 0.0

        correct = 0
        total_signals = 0
        total_samples = len(feedbacks)

        for feedback in feedbacks:
            score = feedback.get('filtered_composite', 0)
            actual_direction = feedback.get('actual_direction', 0)

            # 判断是否有信号
            if abs(score) > threshold:
                total_signals += 1
                score_direction = 1 if score > threshold else -1

                # 判断是否正确
                if score_direction == actual_direction:
                    correct += 1

        accuracy = correct / total_signals if total_signals > 0 else 0
        coverage = total_signals / total_samples if total_samples > 0 else 0

        return accuracy, coverage

    def optimize_for_regime(self, symbol: str = None) -> Dict[str, Dict]:
        """
        为每种波动率状态优化阈值

        参数:
            symbol: 品种代码（可选）

        返回:
            各波动率状态的最优阈值
        """
        results = {}

        for regime in ['high', 'normal', 'low']:
            results[regime] = self.optimize_threshold(
                symbol=symbol,
                volatility_regime=regime
            )

        return results

    def get_threshold_report(self, symbol: str = None) -> str:
        """
        生成阈值优化报告

        参数:
            symbol: 品种代码（可选）

        返回:
            报告文本
        """
        # 整体优化
        overall = self.optimize_threshold(symbol=symbol)

        # 按波动率状态优化
        by_regime = self.optimize_for_regime(symbol)

        # 生成报告
        report = []
        report.append("# 阈值优化报告")
        report.append(f"\n**品种**: {symbol or '全部'}")

        # 整体优化结果
        report.append("\n## 1. 整体优化")
        if overall.get('insufficient_data'):
            report.append(f"- 样本量不足（{overall['sample_size']}），无法优化")
        else:
            report.append(f"- 样本量：{overall['sample_size']}")
            report.append(f"- 基准阈值：{overall['baseline_threshold']:.4f}")
            report.append(f"- 基准准确率：{overall['baseline_accuracy']:.2%}")
            report.append(f"- 基准覆盖率：{overall['baseline_coverage']:.2%}")
            report.append(f"- 基准 F1：{overall['baseline_f1']:.4f}")
            report.append(f"\n**最优结果**:")
            report.append(f"- 最优阈值：{overall['optimal_threshold']:.4f}")
            report.append(f"- 最优准确率：{overall['optimal_accuracy']:.2%}")
            report.append(f"- 最优覆盖率：{overall['optimal_coverage']:.2%}")
            report.append(f"- 最优 F1：{overall['optimal_f1']:.4f}")
            report.append(f"- 改进幅度：{overall['improvement']:.2%}")

        # 按波动率状态优化结果
        report.append("\n## 2. 按波动率状态优化")
        report.append("| 波动率状态 | 样本量 | 最优阈值 | 准确率 | 覆盖率 | F1 |")
        report.append("|------------|--------|----------|--------|--------|-----|")
        for regime, result in by_regime.items():
            if result.get('insufficient_data'):
                report.append(f"| {regime} | {result['sample_size']} | - | - | - | - |")
            else:
                report.append(f"| {regime} | {result['sample_size']} | "
                            f"{result['optimal_threshold']:.4f} | "
                            f"{result['optimal_accuracy']:.2%} | "
                            f"{result['optimal_coverage']:.2%} | "
                            f"{result['optimal_f1']:.4f} |")

        # 建议
        report.append("\n## 3. 建议")
        if overall.get('insufficient_data'):
            report.append("- 继续积累数据，至少需要 100 条已完成的反馈记录")
        else:
            if overall['improvement'] > 0.1:
                report.append(f"- 建议将阈值从 {overall['baseline_threshold']:.4f} "
                            f"调整为 {overall['optimal_threshold']:.4f}")
            else:
                report.append("- 当前阈值效果良好，无需调整")

        return "\n".join(report)
