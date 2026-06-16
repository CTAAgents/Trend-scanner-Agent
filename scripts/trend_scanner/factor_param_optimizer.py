"""
因子参数贝叶斯优化器

基于 FactorEngine 论文的"逻辑-参数分离"思想：
- LLM 负责因子逻辑创意（宏进化）
- 贝叶斯优化负责参数调优（微进化）

使用 Optuna 实现 TPE（Tree-structured Parzen Estimator）搜索。

版本：v1.0
创建日期：2026-06-16
"""

import logging
import json
import os
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ParamSpec:
    """参数规格"""
    name: str
    type: str  # 'int', 'float', 'categorical'
    low: float = 0
    high: float = 1
    choices: list = None
    step: float = None
    log: bool = False

    def to_dict(self) -> Dict:
        d = {'name': self.name, 'type': self.type}
        if self.type in ('int', 'float'):
            d['low'] = self.low
            d['high'] = self.high
        if self.step is not None:
            d['step'] = self.step
        if self.log:
            d['log'] = True
        if self.choices:
            d['choices'] = self.choices
        return d


@dataclass
class OptimizationResult:
    """优化结果"""
    factor_name: str
    best_params: Dict
    best_score: float
    n_trials: int
    n_completed: int
    optimization_history: List[Dict]
    improvement_pct: float  # 相对于默认参数的提升百分比

    def to_dict(self) -> Dict:
        return {
            'factor_name': self.factor_name,
            'best_params': self.best_params,
            'best_score': self.best_score,
            'n_trials': self.n_trials,
            'n_completed': self.n_completed,
            'improvement_pct': self.improvement_pct,
            'top_trials': self.optimization_history[:10],
        }


# ============================================================
# 预定义参数空间
# ============================================================

PREDEFINED_SPACES = {
    'momentum': [
        ParamSpec('window', 'int', low=5, high=60, step=5),
    ],
    'volatility': [
        ParamSpec('window', 'int', low=5, high=40, step=5),
    ],
    'rsi': [
        ParamSpec('period', 'int', low=5, high=30, step=1),
    ],
    'ema_cross': [
        ParamSpec('fast_period', 'int', low=5, high=30, step=1),
        ParamSpec('slow_period', 'int', low=20, high=120, step=5),
    ],
    'atr_ratio': [
        ParamSpec('atr_period', 'int', low=5, high=30, step=1),
    ],
    'bollinger': [
        ParamSpec('period', 'int', low=10, high=40, step=5),
        ParamSpec('std_dev', 'float', low=1.0, high=3.0, step=0.5),
    ],
}


class FactorParamOptimizer:
    """
    因子参数贝叶斯优化器

    使用 Optuna TPE 搜索最优参数。

    使用方式：
        optimizer = FactorParamOptimizer()

        # 定义参数化因子
        def momentum_factor(df, params):
            window = params['window']
            return df['close'].pct_change(window).fillna(0)

        # 定义参数空间
        param_space = [ParamSpec('window', 'int', low=5, high=60)]

        # 优化
        result = optimizer.optimize(
            factor_name='momentum',
            factor_fn=momentum_factor,
            param_space=param_space,
            kline_data=data,
            n_trials=50,
        )
    """

    def __init__(self, metric: str = 'icir', n_startup_trials: int = 10):
        """
        初始化优化器

        Args:
            metric: 优化目标指标 ('icir', 't_stat', 'ls_sharpe')
            n_startup_trials: 随机探索试验数（TPE 启动前）
        """
        self.metric = metric
        self.n_startup_trials = n_startup_trials

    def optimize(self, factor_name: str,
                 factor_fn: Callable[[pd.DataFrame, Dict], pd.Series],
                 param_space: List[ParamSpec],
                 kline_data: Dict[str, pd.DataFrame],
                 returns: pd.DataFrame = None,
                 n_trials: int = 50,
                 default_params: Dict = None) -> OptimizationResult:
        """
        优化因子参数

        Args:
            factor_name: 因子名称
            factor_fn: 参数化因子函数 (df, params) -> Series
            param_space: 参数空间定义
            kline_data: {symbol: DataFrame}
            returns: 次日收益率矩阵（可选，不提供则自动计算）
            n_trials: 优化试验次数
            default_params: 默认参数（用于计算提升百分比）

        Returns:
            OptimizationResult
        """
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        # 计算收益率（如果未提供）
        if returns is None:
            returns = self._compute_returns(kline_data)

        # 计算默认参数的基准分数
        baseline_score = 0.0
        if default_params:
            baseline_score = self._evaluate_params(
                factor_fn, default_params, kline_data, returns
            )
            logger.info(f"基准分数 (默认参数): {baseline_score:.4f}")

        # 定义目标函数
        def objective(trial):
            params = {}
            for spec in param_space:
                if spec.type == 'int':
                    params[spec.name] = trial.suggest_int(
                        spec.name, int(spec.low), int(spec.high),
                        step=int(spec.step) if spec.step else 1
                    )
                elif spec.type == 'float':
                    params[spec.name] = trial.suggest_float(
                        spec.name, spec.low, spec.high,
                        step=spec.step, log=spec.log
                    )
                elif spec.type == 'categorical':
                    params[spec.name] = trial.suggest_categorical(
                        spec.name, spec.choices
                    )

            score = self._evaluate_params(factor_fn, params, kline_data, returns)
            return score

        # 创建并运行优化
        sampler = optuna.samplers.TPESampler(
            n_startup_trials=self.n_startup_trials,
            seed=42,
        )
        study = optuna.create_study(
            direction='maximize',
            sampler=sampler,
            study_name=factor_name,
        )

        # 使用 lambda 避免 NaN 传播
        def safe_objective(trial):
            try:
                score = objective(trial)
                if np.isnan(score) or np.isinf(score):
                    return 0.0
                return score
            except Exception as e:
                logger.debug(f"试验 {trial.number} 失败: {e}")
                return 0.0

        study.optimize(safe_objective, n_trials=n_trials, show_progress_bar=False)

        # 提取结果
        best_params = study.best_params
        best_score = study.best_value

        # 计算提升百分比
        improvement_pct = 0.0
        if baseline_score > 0:
            improvement_pct = (best_score - baseline_score) / abs(baseline_score) * 100

        # 构建优化历史
        history = []
        for trial in sorted(study.trials, key=lambda t: t.value if t.value else 0, reverse=True):
            if trial.value is not None:
                history.append({
                    'trial': trial.number,
                    'params': trial.params,
                    'score': trial.value,
                })

        result = OptimizationResult(
            factor_name=factor_name,
            best_params=best_params,
            best_score=best_score,
            n_trials=n_trials,
            n_completed=len([t for t in study.trials if t.value is not None]),
            optimization_history= history,
            improvement_pct=improvement_pct,
        )

        logger.info(
            f"优化完成: {factor_name}, "
            f"最优分数={best_score:.4f}, "
            f"提升={improvement_pct:+.1f}%, "
            f"最优参数={best_params}"
        )

        return result

    def optimize_with_predefined_space(self, factor_name: str,
                                        factor_fn: Callable,
                                        space_name: str,
                                        kline_data: Dict[str, pd.DataFrame],
                                        returns: pd.DataFrame = None,
                                        n_trials: int = 50) -> OptimizationResult:
        """
        使用预定义参数空间优化

        Args:
            factor_name: 因子名称
            factor_fn: 参数化因子函数
            space_name: 预定义空间名称
            kline_data: K 线数据
            returns: 收益率矩阵
            n_trials: 试验次数
        """
        if space_name not in PREDEFINED_SPACES:
            raise ValueError(f"未找到预定义参数空间: {space_name}，可选: {list(PREDEFINED_SPACES.keys())}")

        param_space = PREDEFINED_SPACES[space_name]
        return self.optimize(factor_name, factor_fn, param_space, kline_data, returns, n_trials)

    def _evaluate_params(self, factor_fn: Callable, params: Dict,
                          kline_data: Dict[str, pd.DataFrame],
                          returns: pd.DataFrame) -> float:
        """
        评估特定参数组合的因子表现

        Args:
            factor_fn: 因子函数
            params: 参数
            kline_data: K 线数据
            returns: 收益率矩阵

        Returns:
            评估分数
        """
        # 计算因子值
        factor_dict = {}
        for symbol, df in kline_data.items():
            try:
                values = factor_fn(df, params)
                if values is not None and len(values) > 0:
                    if isinstance(values, pd.Series):
                        factor_dict[symbol] = values
                    else:
                        factor_dict[symbol] = pd.Series(values, index=df.index)
            except Exception:
                continue

        if len(factor_dict) < 10:
            return 0.0

        factor_df = pd.DataFrame(factor_dict)
        factor_df = factor_df.replace([np.inf, -np.inf], np.nan)

        # 计算截面 IC
        common_dates = factor_df.index.intersection(returns.index)
        if len(common_dates) < 20:
            return 0.0

        ic_values = []
        for date in common_dates:
            fv = factor_df.loc[date].dropna()
            ret = returns.loc[date].dropna()
            common = fv.index.intersection(ret.index)

            if len(common) < 10:
                continue

            fv_cs = fv[common]
            ret_cs = ret[common]

            if fv_cs.std() == 0 or ret_cs.std() == 0:
                continue

            from scipy import stats
            corr, _ = stats.spearmanr(fv_cs.values, ret_cs.values)
            if not np.isnan(corr):
                ic_values.append(corr)

        if len(ic_values) < 10:
            return 0.0

        ic = pd.Series(ic_values)

        if self.metric == 'icir':
            score = abs(ic.mean() / ic.std()) if ic.std() > 0 else 0.0
        elif self.metric == 't_stat':
            n = len(ic)
            score = abs(ic.mean() / (ic.std() / np.sqrt(n))) if ic.std() > 0 else 0.0
        elif self.metric == 'ls_sharpe':
            score = abs(ic.mean() / ic.std()) * np.sqrt(252) if ic.std() > 0 else 0.0
        else:
            score = abs(ic.mean() / ic.std()) if ic.std() > 0 else 0.0

        return score

    def _compute_returns(self, kline_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """计算次日收益率矩阵"""
        returns_dict = {}
        for symbol, df in kline_data.items():
            if 'close' in df.columns and len(df) > 1:
                returns_dict[symbol] = df['close'].pct_change().shift(-1)
        return pd.DataFrame(returns_dict)

    def generate_optimized_factor_code(self, factor_template: str,
                                         best_params: Dict) -> str:
        """
        将优化后的参数写回因子代码

        Args:
            factor_template: 因子代码模板（含 {param} 占位符）
            best_params: 最优参数

        Returns:
            固定参数后的因子代码
        """
        code = factor_template
        for name, value in best_params.items():
            code = code.replace(f'{{{name}}}', str(value))
            code = code.replace(f"params['{name}']", str(value))
            code = code.replace(f'params["{name}"]', str(value))
        return code

    def save_result(self, result: OptimizationResult, path: str = None):
        """保存优化结果到 JSON"""
        if path is None:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'data', f'param_opt_{result.factor_name}.json'
            )

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"优化结果已保存到 {path}")


# ============================================================
# 参数化因子模板（内置）
# ============================================================

def parametric_momentum(df: pd.DataFrame, params: Dict) -> pd.Series:
    """参数化动量因子"""
    window = params.get('window', 20)
    return df['close'].pct_change(window).fillna(0)


def parametric_volatility(df: pd.DataFrame, params: Dict) -> pd.Series:
    """参数化波动率因子"""
    window = params.get('window', 20)
    return -df['close'].pct_change().rolling(window).std().fillna(0)


def parametric_rsi(df: pd.DataFrame, params: Dict) -> pd.Series:
    """参数化 RSI 因子"""
    period = params.get('period', 14)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return ((rsi - 50) / 50).fillna(0)


def parametric_ema_cross(df: pd.DataFrame, params: Dict) -> pd.Series:
    """参数化 EMA 交叉因子"""
    fast = params.get('fast_period', 20)
    slow = params.get('slow_period', 60)
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    return ((ema_fast - ema_slow) / df['close']).fillna(0)


def parametric_atr_ratio(df: pd.DataFrame, params: Dict) -> pd.Series:
    """参数化 ATR 比率因子"""
    period = params.get('atr_period', 14)
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return -(atr / close).fillna(0)


# 内置参数化因子
PARAMETRIC_FACTORS = {
    'momentum': parametric_momentum,
    'volatility': parametric_volatility,
    'rsi': parametric_rsi,
    'ema_cross': parametric_ema_cross,
    'atr_ratio': parametric_atr_ratio,
}


# ============================================================
# 命令行入口
# ============================================================

def main():
    """命令行入口"""
    import argparse
    import sys

    scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    parser = argparse.ArgumentParser(description='因子参数贝叶斯优化器')
    parser.add_argument('--db', type=str, default=None, help='DuckDB 路径')
    parser.add_argument('--days', type=int, default=120, help='数据天数')
    parser.add_argument('--trials', type=int, default=50, help='优化试验次数')
    parser.add_argument('--factors', type=str, default=None,
                        help='因子名称（逗号分隔），不指定则优化所有内置参数化因子')
    parser.add_argument('--save', action='store_true', help='保存结果')

    args = parser.parse_args()

    # 加载数据
    from trend_scanner.factor_evaluator import FactorEvaluator
    evaluator = FactorEvaluator(db_path=args.db)
    count = evaluator.load_data(days=args.days)
    print(f"加载 {count} 个品种的数据")

    if count < 10:
        print("品种数量不足（< 10），无法优化")
        return

    kline_data = evaluator._kline_data
    returns = evaluator._returns

    # 选择因子
    if args.factors:
        factor_names = [f.strip() for f in args.factors.split(',')]
    else:
        factor_names = list(PARAMETRIC_FACTORS.keys())

    # 运行优化
    optimizer = FactorParamOptimizer(metric='icir')

    for name in factor_names:
        if name not in PARAMETRIC_FACTORS:
            print(f"未找到因子: {name}")
            continue

        if name not in PREDEFINED_SPACES:
            print(f"未找到参数空间: {name}")
            continue

        print(f"\n{'=' * 50}")
        print(f"优化因子: {name}")
        print(f"{'=' * 50}")

        result = optimizer.optimize_with_predefined_space(
            factor_name=name,
            factor_fn=PARAMETRIC_FACTORS[name],
            space_name=name,
            kline_data=kline_data,
            returns=returns,
            n_trials=args.trials,
        )

        print(f"  最优参数: {result.best_params}")
        print(f"  最优分数: {result.best_score:.4f}")
        print(f"  提升: {result.improvement_pct:+.1f}%")
        print(f"  完成试验: {result.n_completed}/{result.n_trials}")

        if args.save:
            optimizer.save_result(result)


if __name__ == '__main__':
    main()
