"""
回测框架模块

提供Walk-Forward回测、蒙特卡洛鲁棒性检验等功能：
- WalkForwardBacktester: Walk-Forward回测框架
- MonteCarloValidator: 蒙特卡洛鲁棒性检验
"""

import numpy as np
import pandas as pd


class WalkForwardBacktester:
    """
    Walk-Forward回测框架（7.1）

    防止过拟合的回测方法：
    - 训练集（60%）→ 验证集（20%）→ 测试集（20%）
    - 时间顺序切分，不打乱
    - 滚动回测：每次用过去N天训练，预测未来M天
    """

    def __init__(self, train_ratio: float = 0.6, val_ratio: float = 0.2, test_ratio: float = 0.2, step_size: int = 20):
        """
        参数:
            train_ratio: 训练集比例
            val_ratio: 验证集比例
            test_ratio: 测试集比例
            step_size: 滚动步长（K线数）
        """
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.step_size = step_size

    def split_data(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        按时间顺序切分数据

        参数:
            df: DataFrame

        返回:
            train, val, test: 三个DataFrame
        """
        n = len(df)
        train_end = int(n * self.train_ratio)
        val_end = int(n * (self.train_ratio + self.val_ratio))

        train = df.iloc[:train_end].copy()
        val = df.iloc[train_end:val_end].copy()
        test = df.iloc[val_end:].copy()

        return train, val, test

    def rolling_backtest(self, df: pd.DataFrame, strategy_func, window_size: int = 120) -> dict:
        """
        滚动回测

        参数:
            df: DataFrame
            strategy_func: 策略函数，接收df返回信号序列
            window_size: 滚动窗口大小

        返回:
            回测结果
        """
        n = len(df)
        if n < window_size + self.step_size:
            return {"error": "数据不足"}

        signals = []
        returns = []
        positions = []

        for i in range(window_size, n, self.step_size):
            # 获取训练窗口
            train_start = max(0, i - window_size)
            train_df = df.iloc[train_start:i].copy()

            # 获取测试窗口
            test_start = i
            test_end = min(i + self.step_size, n)
            test_df = df.iloc[test_start:test_end].copy()

            if len(test_df) == 0:
                break

            # 运行策略
            try:
                signal = strategy_func(train_df, test_df)
                signals.extend(signal)
            except Exception:
                # 策略出错时保持之前的状态
                signals.extend([0] * len(test_df))

        # 计算收益
        close = df["close"].iloc[window_size:].values
        for i in range(1, len(signals)):
            if i < len(close):
                ret = (close[i] - close[i - 1]) / close[i - 1]
                returns.append(ret * signals[i - 1])
                positions.append(signals[i - 1])

        returns = np.array(returns)
        positions = np.array(positions)

        # 计算绩效指标
        total_return = np.sum(returns)
        sharpe = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252)
        max_drawdown = self._calc_max_drawdown(returns)
        win_rate = np.sum(returns > 0) / (len(returns) + 1e-10)

        return {
            "total_return": round(total_return, 4),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown": round(max_drawdown, 4),
            "win_rate": round(win_rate, 3),
            "total_trades": len(signals),
            "returns": returns.tolist(),
            "positions": positions.tolist(),
        }

    def _calc_max_drawdown(self, returns: np.ndarray) -> float:
        """计算最大回撤"""
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        return float(np.max(drawdown)) if len(drawdown) > 0 else 0.0


class MonteCarloValidator:
    """
    蒙特卡洛鲁棒性检验（7.2）

    对收益率序列进行块自助法（Block Bootstrap）：
    - 生成N条合成路径
    - 计算策略收益的置信区间
    - 检查策略在不同市场阶段的表现
    """

    def __init__(self, n_simulations: int = 1000, block_size: int = 20, confidence_level: float = 0.95):
        """
        参数:
            n_simulations: 模拟次数
            block_size: 块大小（K线数）
            confidence_level: 置信水平
        """
        self.n_simulations = n_simulations
        self.block_size = block_size
        self.confidence_level = confidence_level

    def block_bootstrap(self, returns: np.ndarray) -> dict:
        """
        块自助法

        参数:
            returns: 收益率序列

        返回:
            模拟结果
        """
        n = len(returns)
        if n < self.block_size * 2:
            return {"error": "数据不足"}

        simulated_returns = []

        for _ in range(self.n_simulations):
            # 随机抽取块
            sim_returns = []
            while len(sim_returns) < n:
                # 随机选择块的起始位置
                start = np.random.randint(0, n - self.block_size)
                block = returns[start : start + self.block_size]
                sim_returns.extend(block.tolist())

            # 截取到原始长度
            sim_returns = sim_returns[:n]
            simulated_returns.append(np.sum(sim_returns))

        simulated_returns = np.array(simulated_returns)

        # 计算置信区间
        alpha = 1 - self.confidence_level
        ci_lower = np.percentile(simulated_returns, alpha / 2 * 100)
        ci_upper = np.percentile(simulated_returns, (1 - alpha / 2) * 100)

        # 计算统计量
        mean_return = np.mean(simulated_returns)
        std_return = np.std(simulated_returns)
        prob_positive = np.sum(simulated_returns > 0) / len(simulated_returns)

        return {
            "mean_return": round(float(mean_return), 4),
            "std_return": round(float(std_return), 4),
            "ci_lower": round(float(ci_lower), 4),
            "ci_upper": round(float(ci_upper), 4),
            "prob_positive": round(float(prob_positive), 3),
            "confidence_level": self.confidence_level,
            "n_simulations": self.n_simulations,
        }

    def regime_analysis(self, returns: np.ndarray, regimes: np.ndarray) -> dict:
        """
        不同市场阶段的表现分析

        参数:
            returns: 收益率序列
            regimes: 市场阶段标签序列（0=震荡，1=上涨，2=下跌）

        返回:
            各阶段表现
        """
        regime_stats = {}

        for regime_id in np.unique(regimes):
            mask = regimes == regime_id
            regime_returns = returns[mask]

            if len(regime_returns) > 0:
                regime_stats[int(regime_id)] = {
                    "count": len(regime_returns),
                    "mean_return": round(float(np.mean(regime_returns)), 4),
                    "std_return": round(float(np.std(regime_returns)), 4),
                    "sharpe": round(
                        float(np.mean(regime_returns) / (np.std(regime_returns) + 1e-10) * np.sqrt(252)), 3
                    ),
                    "win_rate": round(float(np.sum(regime_returns > 0) / len(regime_returns)), 3),
                }

        return regime_stats


class ParameterOptimizer:
    """
    参数在线贝叶斯优化（7.4）

    每周进行一次参数扫描，选择过去N天内夏普比率最高的参数组合
    """

    def __init__(self, lookback_days: int = 60, param_grid: dict = None):
        """
        参数:
            lookback_days: 回看天数
            param_grid: 参数网格
        """
        self.lookback_days = lookback_days
        self.param_grid = param_grid or {}

    def grid_search(self, df: pd.DataFrame, strategy_func, metric: str = "sharpe") -> dict:
        """
        网格搜索

        参数:
            df: DataFrame
            strategy_func: 策略函数
            metric: 优化指标（sharpe/return/max_drawdown）

        返回:
            最优参数和绩效
        """
        if not self.param_grid:
            return {"error": "参数网格为空"}

        best_metric = -np.inf
        best_params = {}
        results = []

        # 生成参数组合
        param_combinations = self._generate_param_combinations()

        for params in param_combinations:
            try:
                # 运行策略
                result = strategy_func(df, **params)

                # 获取指标值
                if metric == "sharpe":
                    metric_value = result.get("sharpe_ratio", 0)
                elif metric == "return":
                    metric_value = result.get("total_return", 0)
                elif metric == "max_drawdown":
                    metric_value = -result.get("max_drawdown", 0)  # 最小化回撤
                else:
                    metric_value = result.get("sharpe_ratio", 0)

                results.append(
                    {
                        "params": params,
                        "metric": metric_value,
                        "result": result,
                    }
                )

                if metric_value > best_metric:
                    best_metric = metric_value
                    best_params = params

            except Exception:
                continue

        return {
            "best_params": best_params,
            "best_metric": round(best_metric, 4),
            "total_combinations": len(param_combinations),
            "successful_runs": len(results),
            "results": results[:10],  # 只返回前10个结果
        }

    def _generate_param_combinations(self) -> list[dict]:
        """生成参数组合"""
        import itertools

        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())

        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))

        return combinations
