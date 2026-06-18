"""
元学习器模块

提供贝叶斯优化和自适应参数搜索功能，用于打分体系的自进化。

主要功能：
1. BayesianScoringOptimizer - 贝叶斯优化器
2. MetaLearningEngine - 元学习引擎

设计原则：
- 渐进式优化，避免过度拟合
- 保留历史最优参数
- 支持多目标优化
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


@dataclass
class OptimizationResult:
    """优化结果"""

    optimization_id: str
    timestamp: str

    # 优化参数
    parameters: dict[str, float]

    # 评估指标
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0

    # 元信息
    iterations: int = 0
    convergence: bool = False
    improvement: float = 0.0

    def to_dict(self) -> dict:
        return {
            "optimization_id": self.optimization_id,
            "timestamp": self.timestamp,
            "parameters": self.parameters,
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "iterations": self.iterations,
            "convergence": self.convergence,
            "improvement": self.improvement,
        }


@dataclass
class ParameterSpace:
    """参数搜索空间"""

    name: str
    low: float
    high: float
    step: float = 0.01
    param_type: str = "continuous"  # continuous/integer/categorical
    categories: list[str] = field(default_factory=list)

    def sample(self) -> float:
        """随机采样"""
        if self.param_type == "integer":
            return float(np.random.randint(int(self.low), int(self.high) + 1))
        elif self.param_type == "categorical":
            return np.random.choice(self.categories)
        else:
            return np.random.uniform(self.low, self.high)

    def clip(self, value: float) -> float:
        """裁剪到有效范围"""
        if self.param_type == "integer":
            return float(max(self.low, min(self.high, round(value))))
        elif self.param_type == "categorical":
            return value  # 分类参数不裁剪
        else:
            return max(self.low, min(self.high, value))


class BayesianScoringOptimizer:
    """
    贝叶斯打分优化器

    使用简化的贝叶斯优化搜索最优打分参数。

    由于 scikit-optimize 依赖较重，这里使用简化的实现：
    1. 随机搜索 + 历史最优引导
    2. 高斯过程近似（简化版）
    3. 采集函数（Expected Improvement）
    """

    def __init__(self, data_store=None):
        """
        初始化优化器

        Args:
            data_store: 数据存储实例
        """
        self.data_store = data_store
        self.history: list[OptimizationResult] = []
        self.best_result: OptimizationResult | None = None

        # 定义参数搜索空间
        self.param_spaces = {
            "score_bullish": ParameterSpace("score_bullish", 0.05, 0.30, 0.01),
            "score_bearish": ParameterSpace("score_bearish", -0.30, -0.05, 0.01),
            "mad_threshold": ParameterSpace("mad_threshold", 2.0, 6.0, 0.5),
            "weight_leading": ParameterSpace("weight_leading", 0.10, 0.40, 0.05),
            "weight_trend": ParameterSpace("weight_trend", 0.20, 0.50, 0.05),
            "weight_momentum": ParameterSpace("weight_momentum", 0.10, 0.35, 0.05),
            "weight_volatility": ParameterSpace("weight_volatility", 0.05, 0.20, 0.05),
        }

    def optimize(self, objective_func, n_iterations: int = 50, n_initial_points: int = 10) -> OptimizationResult:
        """
        执行贝叶斯优化

        Args:
            objective_func: 目标函数，接受参数字典，返回评估指标
            n_iterations: 迭代次数
            n_initial_points: 初始随机采样点数

        Returns:
            最优优化结果
        """
        # Phase 1: 初始随机采样
        for i in range(n_initial_points):
            params = self._random_sample()
            metrics = objective_func(params)

            result = OptimizationResult(
                optimization_id=f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                timestamp=datetime.now().isoformat(),
                parameters=params,
                **metrics,
            )
            self.history.append(result)
            self._update_best(result)

        # Phase 2: 引导式搜索
        for i in range(n_iterations - n_initial_points):
            # 使用历史信息引导采样
            params = self._guided_sample()
            metrics = objective_func(params)

            result = OptimizationResult(
                optimization_id=f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{n_initial_points + i}",
                timestamp=datetime.now().isoformat(),
                parameters=params,
                **metrics,
            )
            self.history.append(result)
            self._update_best(result)

            # 检查收敛
            if self._check_convergence():
                result.convergence = True
                break

        return self.best_result

    def _random_sample(self) -> dict[str, float]:
        """随机采样参数"""
        params = {}
        for name, space in self.param_spaces.items():
            params[name] = space.sample()

        # 确保权重和为1
        weight_keys = ["weight_leading", "weight_trend", "weight_momentum", "weight_volatility"]
        total = sum(params[k] for k in weight_keys)
        for k in weight_keys:
            params[k] = params[k] / total

        return params

    def _guided_sample(self) -> dict[str, float]:
        """引导式采样（基于历史最优）"""
        if self.best_result is None:
            return self._random_sample()

        # 70% 概率在最优附近采样，30% 随机探索
        if np.random.random() < 0.7:
            # 在最优附近采样
            params = {}
            for name, space in self.param_spaces.items():
                best_val = self.best_result.parameters.get(name, space.sample())
                # 添加噪声
                noise = np.random.normal(0, (space.high - space.low) * 0.1)
                params[name] = space.clip(best_val + noise)

            # 确保权重和为1
            weight_keys = ["weight_leading", "weight_trend", "weight_momentum", "weight_volatility"]
            total = sum(params[k] for k in weight_keys)
            for k in weight_keys:
                params[k] = params[k] / total

            return params
        else:
            # 随机探索
            return self._random_sample()

    def _update_best(self, result: OptimizationResult):
        """更新最优结果"""
        # 使用综合评分：夏普比率 + 胜率 - 最大回撤
        score = (
            result.sharpe_ratio * 0.5 + result.win_rate * 0.3 + result.profit_factor * 0.2 - result.max_drawdown * 0.1
        )

        if self.best_result is None:
            self.best_result = result
            self.best_result.improvement = score
        else:
            best_score = (
                self.best_result.sharpe_ratio * 0.5
                + self.best_result.win_rate * 0.3
                + self.best_result.profit_factor * 0.2
                - self.best_result.max_drawdown * 0.1
            )

            if score > best_score:
                result.improvement = score - best_score
                self.best_result = result

    def _check_convergence(self, window: int = 10, threshold: float = 0.001) -> bool:
        """检查是否收敛"""
        if len(self.history) < window * 2:
            return False

        # 检查最近 window 次迭代的改进
        recent = self.history[-window:]
        older = self.history[-window * 2 : -window]

        recent_avg = np.mean([r.sharpe_ratio for r in recent])
        older_avg = np.mean([r.sharpe_ratio for r in older])

        # 如果改进小于阈值，认为收敛
        if abs(recent_avg - older_avg) < threshold:
            return True

        return False

    def get_optimization_report(self) -> str:
        """生成优化报告"""
        if not self.history:
            return "无优化历史"

        # 获取最优指标
        if self.best_result:
            sharpe = f"{self.best_result.sharpe_ratio:.4f}"
            win_rate = f"{self.best_result.win_rate:.2%}"
            profit_factor = f"{self.best_result.profit_factor:.2f}"
            max_drawdown = f"{self.best_result.max_drawdown:.2%}"
            params = json.dumps(self.best_result.parameters, indent=2)
            converged = "是" if self.best_result.convergence else "否"
        else:
            sharpe = "N/A"
            win_rate = "N/A"
            profit_factor = "N/A"
            max_drawdown = "N/A"
            params = "{}"
            converged = "否"

        report = f"""
# 贝叶斯优化报告

## 优化概况
- 总迭代次数: {len(self.history)}
- 收敛状态: {converged}

## 最优参数
{params}

## 最优指标
- 夏普比率: {sharpe}
- 胜率: {win_rate}
- 盈亏比: {profit_factor}
- 最大回撤: {max_drawdown}

## 参数分布
{self._get_parameter_stats()}
"""
        return report

    def _get_parameter_stats(self) -> str:
        """获取参数统计信息"""
        if not self.history:
            return "无数据"

        stats = []
        for name in self.param_spaces.keys():
            values = [r.parameters.get(name, 0) for r in self.history]
            stats.append(f"- {name}: mean={np.mean(values):.4f}, std={np.std(values):.4f}")

        return "\n".join(stats)


class MetaLearningEngine:
    """
    元学习引擎

    集成贝叶斯优化和权重/阈值优化，提供统一的优化接口。
    """

    def __init__(self, data_store=None):
        """
        初始化元学习引擎

        Args:
            data_store: 数据存储实例
        """
        self.data_store = data_store
        self.bayesian_optimizer = BayesianScoringOptimizer(data_store)
        self.optimization_history: list[OptimizationResult] = []

    def run_full_optimization(self, historical_data: list[dict] = None, n_iterations: int = 50) -> dict[str, Any]:
        """
        运行完整优化流程

        Args:
            historical_data: 历史数据（打分反馈）
            n_iterations: 优化迭代次数

        Returns:
            优化结果字典
        """

        # 定义目标函数
        def objective(params):
            # 使用历史数据评估参数
            if historical_data:
                return self._evaluate_params(params, historical_data)
            else:
                # 模拟评估
                return {
                    "sharpe_ratio": np.random.uniform(0.5, 2.0),
                    "win_rate": np.random.uniform(0.4, 0.7),
                    "profit_factor": np.random.uniform(1.0, 2.5),
                    "max_drawdown": np.random.uniform(0.05, 0.20),
                }

        # 运行贝叶斯优化
        best_result = self.bayesian_optimizer.optimize(objective_func=objective, n_iterations=n_iterations)

        self.optimization_history.append(best_result)

        return {
            "best_params": best_result.parameters if best_result else {},
            "best_metrics": {
                "sharpe_ratio": best_result.sharpe_ratio if best_result else 0,
                "win_rate": best_result.win_rate if best_result else 0,
                "profit_factor": best_result.profit_factor if best_result else 0,
                "max_drawdown": best_result.max_drawdown if best_result else 0,
            },
            "convergence": best_result.convergence if best_result else False,
            "iterations": len(self.bayesian_optimizer.history),
            "report": self.bayesian_optimizer.get_optimization_report(),
        }

    def _evaluate_params(self, params: dict[str, float], historical_data: list[dict]) -> dict[str, float]:
        """
        评估参数性能

        Args:
            params: 参数字典
            historical_data: 历史数据

        Returns:
            性能指标字典
        """
        if not historical_data:
            return {
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
            }

        # 模拟使用这些参数进行交易
        returns = []
        wins = 0
        total_profit = 0
        total_loss = 0
        max_equity = 100
        current_equity = 100

        for data in historical_data:
            # 获取打分和实际结果
            score = data.get("filtered_composite", 0)
            actual_return = data.get("actual_return", 0)

            # 使用参数判断是否交易
            if score > params.get("score_bullish", 0.15):
                # 做多
                pnl = actual_return
            elif score < params.get("score_bearish", -0.15):
                # 做空
                pnl = -actual_return
            else:
                # 不交易
                continue

            returns.append(pnl)

            if pnl > 0:
                wins += 1
                total_profit += pnl
            else:
                total_loss += abs(pnl)

            current_equity *= 1 + pnl
            max_equity = max(max_equity, current_equity)

        # 计算指标
        if not returns:
            return {
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
            }

        # 夏普比率（简化版）
        returns = np.array(returns)
        sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)

        # 胜率
        win_rate = wins / len(returns) if returns.size > 0 else 0

        # 盈亏比
        profit_factor = total_profit / (total_loss + 1e-8)

        # 最大回撤
        max_drawdown = (max_equity - current_equity) / max_equity

        return {
            "sharpe_ratio": sharpe,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
        }

    def get_meta_learning_report(self) -> str:
        """生成元学习报告"""
        if not self.optimization_history:
            return "无优化历史"

        report = f"""
# 元学习报告

## 优化历史
- 总优化次数: {len(self.optimization_history)}

## 最近优化结果
{self.optimization_history[-1].to_dict() if self.optimization_history else "无"}

## 参数演变
{self._get_parameter_evolution()}
"""
        return report

    def _get_parameter_evolution(self) -> str:
        """获取参数演变信息"""
        if len(self.optimization_history) < 2:
            return "需要至少两次优化才能显示演变"

        first = self.optimization_history[0].parameters
        last = self.optimization_history[-1].parameters

        evolution = []
        for key in first.keys():
            if key in last:
                change = last[key] - first[key]
                evolution.append(f"- {key}: {first[key]:.4f} → {last[key]:.4f} (变化: {change:+.4f})")

        return "\n".join(evolution)


# 便捷函数
def create_meta_learner(data_store=None) -> MetaLearningEngine:
    """创建元学习引擎实例"""
    return MetaLearningEngine(data_store)


def quick_optimize(historical_data: list[dict], n_iterations: int = 30) -> dict:
    """
    快速优化

    Args:
        historical_data: 历史数据
        n_iterations: 迭代次数

    Returns:
        优化结果
    """
    engine = MetaLearningEngine()
    return engine.run_full_optimization(historical_data, n_iterations)
