"""
截面因子评估器模块

基于 Agentic AI for Factor Investing (2603.14288) 和 FactorEngine (2603.16365) 的思想，
实现截面 IC/ICIR 因子评估体系。

核心功能：
1. 截面 IC 计算：每日所有品种的因子值 vs 次日收益率的 Spearman 相关
2. ICIR 计算：IC 均值 / IC 标准差，衡量预测稳定性
3. 门控决策：晋升 / 观察 / 淘汰，阈值预设不可调

版本：v1.0
创建日期：2026-06-16
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict

import pandas as pd
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


# ============================================================
# 门控阈值（预设不可调，防 p-hacking）
# ============================================================

GATE_THRESHOLDS = {
    # ICIR 阈值
    'icir_promote': 1.0,      # |ICIR| >= 1.0 → 晋升
    'icir_eliminate': 0.5,    # |ICIR| < 0.5 → 淘汰
    # 介于两者之间 → 观察

    # IC 方向一致性
    'ic_positive_pct_promote': 0.55,   # IC > 0 比例 >= 55% → 晋升
    'ic_positive_pct_eliminate': 0.45, # IC > 0 比例 < 45% → 淘汰

    # t 统计量
    't_stat_promote': 2.0,
    't_stat_eliminate': 1.0,

    # 多空 Sharpe
    'ls_sharpe_promote': 1.0,
    'ls_sharpe_eliminate': 0.5,

    # 最少样本数
    'min_cross_section_size': 10,  # 每日最少 10 个品种
    'min_ic_days': 30,             # 最少 30 个交易日的 IC
}


@dataclass
class FactorEvaluationResult:
    """因子评估结果"""
    factor_name: str
    ic_mean: float = 0.0
    ic_std: float = 0.0
    icir: float = 0.0
    rank_ic_mean: float = 0.0
    rank_ic_std: float = 0.0
    rank_icir: float = 0.0
    ic_positive_pct: float = 0.0
    t_stat: float = 0.0
    long_short_sharpe: float = 0.0
    ic_days: int = 0
    cross_section_size_avg: float = 0.0
    decision: str = 'observe'  # 'promote' / 'observe' / 'eliminate'
    decision_reasons: List[str] = field(default_factory=list)
    ic_series: Optional[pd.Series] = None  # 每日 IC 序列（不序列化）

    def to_dict(self) -> Dict:
        """转换为可序列化字典"""
        d = asdict(self)
        d.pop('ic_series', None)  # 不序列化 IC 序列
        return d


class FactorEvaluator:
    """
    截面因子评估器

    评估因子对多个品种的截面预测能力。

    使用方式：
        evaluator = FactorEvaluator()

        # 方式 1：从 DuckDB 加载数据
        evaluator.load_data(days=120)

        # 方式 2：直接传入数据
        evaluator.set_data(kline_data, returns_data)

        # 定义因子函数
        def my_factor(df):
            return df['close'].pct_change(20)

        # 评估因子
        result = evaluator.evaluate('momentum_20d', my_factor)
    """

    def __init__(self, db_path: str = None, thresholds: Dict = None):
        """
        初始化评估器

        Args:
            db_path: DuckDB 数据库路径
            thresholds: 自定义门控阈值（覆盖默认值）
        """
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'market.db'
        )
        self.thresholds = {**GATE_THRESHOLDS, **(thresholds or {})}

        # 数据存储
        self._kline_data: Dict[str, pd.DataFrame] = {}  # {symbol: DataFrame}
        self._returns: Optional[pd.DataFrame] = None     # 次日收益率矩阵
        self._factor_cache: Dict[str, pd.DataFrame] = {} # {factor_name: factor_values}

    # ============================================================
    # 数据加载
    # ============================================================

    def load_data(self, days: int = 120, timeframe: str = 'daily',
                  symbols: List[str] = None) -> int:
        """
        从 DuckDB 加载多品种 K 线数据

        Args:
            days: 加载天数
            timeframe: 时间周期
            symbols: 品种列表，None 则加载所有有数据的品种

        Returns:
            加载的品种数量
        """
        import duckdb

        conn = duckdb.connect(self.db_path, read_only=True)
        try:
            # 获取有数据的品种列表
            if symbols is None:
                result = conn.execute("""
                    SELECT DISTINCT symbol FROM klines
                    WHERE timeframe = ?
                    GROUP BY symbol
                    HAVING COUNT(*) >= 60
                """, [timeframe]).fetchall()
                symbols = [r[0] for r in result]

            if not symbols:
                logger.warning("DuckDB 中无可用品种数据")
                return 0

            # 批量加载
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            for symbol in symbols:
                df = conn.execute("""
                    SELECT timestamp as date, open, high, low, close, volume, open_interest
                    FROM klines
                    WHERE symbol = ? AND timeframe = ?
                    AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp
                """, [symbol, timeframe, start_date, end_date]).fetchdf()

                if not df.empty and len(df) >= 60:
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.set_index('date')
                    self._kline_data[symbol] = df

            # 计算次日收益率矩阵
            self._compute_returns()

            logger.info(f"加载 {len(self._kline_data)} 个品种的 K 线数据")
            return len(self._kline_data)

        finally:
            conn.close()

    def set_data(self, kline_data: Dict[str, pd.DataFrame]):
        """
        直接设置 K 线数据

        Args:
            kline_data: {symbol: DataFrame(date, open, high, low, close, volume)}
        """
        self._kline_data = {}
        for symbol, df in kline_data.items():
            df = df.copy()
            if 'date' in df.columns:
                df = df.set_index('date')
            # 统一日期精度到天（去掉时分秒）
            df.index = pd.to_datetime(df.index).normalize()
            self._kline_data[symbol] = df
        self._compute_returns()

    def _compute_returns(self):
        """计算次日收益率矩阵"""
        if not self._kline_data:
            return

        returns_dict = {}
        for symbol, df in self._kline_data.items():
            if 'close' in df.columns and len(df) > 1:
                # 次日收益率 = (明日收盘 - 今日收盘) / 今日收盘
                returns_dict[symbol] = df['close'].pct_change().shift(-1)

        self._returns = pd.DataFrame(returns_dict)

    # ============================================================
    # 因子计算
    # ============================================================

    def compute_factor(self, factor_name: str,
                       factor_fn: Callable[[pd.DataFrame], pd.Series]) -> pd.DataFrame:
        """
        对所有品种计算因子值

        Args:
            factor_name: 因子名称
            factor_fn: 因子函数，输入单品种 DataFrame，输出因子值 Series

        Returns:
            DataFrame, index=date, columns=symbol, values=因子值
        """
        factor_dict = {}

        for symbol, df in self._kline_data.items():
            try:
                values = factor_fn(df)
                if values is not None and len(values) > 0:
                    if isinstance(values, pd.Series):
                        factor_dict[symbol] = values
                    else:
                        factor_dict[symbol] = pd.Series(values, index=df.index)
            except Exception as e:
                logger.debug(f"因子 {factor_name} 在 {symbol} 上计算失败: {e}")
                continue

        if not factor_dict:
            logger.warning(f"因子 {factor_name} 在所有品种上计算失败")
            return pd.DataFrame()

        factor_df = pd.DataFrame(factor_dict)
        self._factor_cache[factor_name] = factor_df
        return factor_df

    # ============================================================
    # 截面 IC 计算
    # ============================================================

    def compute_cross_sectional_ic(self, factor_values: pd.DataFrame,
                                    method: str = 'spearman') -> pd.Series:
        """
        计算每日截面 IC

        Args:
            factor_values: DataFrame, index=date, columns=symbol, values=因子值
            method: 相关系数方法 ('spearman' 或 'pearson')

        Returns:
            Series, index=date, values=IC
        """
        if self._returns is None or self._returns.empty:
            logger.error("收益率数据未加载")
            return pd.Series(dtype=float)

        # 对齐日期
        common_dates = factor_values.index.intersection(self._returns.index)
        if len(common_dates) < self.thresholds['min_ic_days']:
            logger.warning(f"对齐后只有 {len(common_dates)} 天数据，不足 {self.thresholds['min_ic_days']}")
            return pd.Series(dtype=float)

        ic_series = pd.Series(index=common_dates, dtype=float)

        for date in common_dates:
            fv = factor_values.loc[date].dropna()
            ret = self._returns.loc[date].dropna()
            common_symbols = fv.index.intersection(ret.index)

            if len(common_symbols) < self.thresholds['min_cross_section_size']:
                continue

            fv_cs = fv[common_symbols]
            ret_cs = ret[common_symbols]

            if method == 'spearman':
                # 处理常量数组（标准差为 0 时相关系数未定义）
                if fv_cs.std() == 0 or ret_cs.std() == 0:
                    continue
                corr, _ = stats.spearmanr(fv_cs.values, ret_cs.values)
            else:
                corr = fv_cs.corr(ret_cs)

            ic_series[date] = corr

        return ic_series.dropna()

    # ============================================================
    # 因子评估
    # ============================================================

    def evaluate(self, factor_name: str,
                 factor_fn: Callable[[pd.DataFrame], pd.Series]) -> FactorEvaluationResult:
        """
        评估因子的截面预测能力

        Args:
            factor_name: 因子名称
            factor_fn: 因子函数

        Returns:
            FactorEvaluationResult
        """
        result = FactorEvaluationResult(factor_name=factor_name)

        # 1. 计算因子值
        factor_values = self.compute_factor(factor_name, factor_fn)
        if factor_values.empty:
            result.decision = 'eliminate'
            result.decision_reasons.append('因子计算失败')
            return result

        # 2. 计算截面 IC
        ic = self.compute_cross_sectional_ic(factor_values, method='spearman')
        if len(ic) < self.thresholds['min_ic_days']:
            result.decision = 'observe'
            result.decision_reasons.append(f'IC 样本不足 ({len(ic)} < {self.thresholds["min_ic_days"]})')
            result.ic_days = len(ic)
            return result

        # 3. 计算评估指标
        result.ic_days = len(ic)
        result.ic_series = ic

        # IC 统计
        result.ic_mean = float(ic.mean())
        result.ic_std = float(ic.std())
        result.icir = float(ic.mean() / ic.std()) if ic.std() > 0 else 0.0

        # Rank IC（Spearman 本身就是 Rank IC）
        result.rank_ic_mean = result.ic_mean
        result.rank_ic_std = result.ic_std
        result.rank_icir = result.icir

        # IC > 0 比例
        result.ic_positive_pct = float((ic > 0).mean())

        # t 统计量
        n = len(ic)
        result.t_stat = float(ic.mean() / (ic.std() / np.sqrt(n))) if ic.std() > 0 else 0.0

        # 截面大小平均值
        result.cross_section_size_avg = float(
            factor_values.notna().sum(axis=1).mean()
        )

        # 多空 Sharpe
        result.long_short_sharpe = self._compute_long_short_sharpe(factor_values)

        # 4. 门控决策
        result.decision, result.decision_reasons = self._gate_decision(result)

        return result

    def evaluate_batch(self, factors: Dict[str, Callable]) -> List[FactorEvaluationResult]:
        """
        批量评估多个因子

        Args:
            factors: {factor_name: factor_fn}

        Returns:
            评估结果列表
        """
        results = []
        for name, fn in factors.items():
            logger.info(f"评估因子: {name}")
            result = self.evaluate(name, fn)
            results.append(result)
            logger.info(f"  {name}: ICIR={result.icir:.3f}, 决策={result.decision}")

        return results

    # ============================================================
    # 多空 Sharpe 计算
    # ============================================================

    def _compute_long_short_sharpe(self, factor_values: pd.DataFrame,
                                    quantile: float = 0.2) -> float:
        """
        计算多空组合 Sharpe

        按因子值分组：Top 20% 做多，Bottom 20% 做空

        Args:
            factor_values: 因子值矩阵
            quantile: 分位数（默认 20%）

        Returns:
            年化 Sharpe
        """
        if self._returns is None:
            return 0.0

        common_dates = factor_values.index.intersection(self._returns.index)
        if len(common_dates) < 30:
            return 0.0

        daily_ls_returns = []

        for date in common_dates:
            fv = factor_values.loc[date].dropna()
            ret = self._returns.loc[date].dropna()
            common = fv.index.intersection(ret.index)

            if len(common) < 10:
                continue

            fv_cs = fv[common]
            ret_cs = ret[common]

            # 按因子值排序
            n = len(common)
            top_n = max(1, int(n * quantile))
            bottom_n = max(1, int(n * quantile))

            sorted_fv = fv_cs.sort_values(ascending=False)
            top_symbols = sorted_fv.head(top_n).index
            bottom_symbols = sorted_fv.tail(bottom_n).index

            # 多空收益 = 多头平均 - 空头平均
            long_ret = ret_cs[top_symbols].mean()
            short_ret = ret_cs[bottom_symbols].mean()
            ls_ret = long_ret - short_ret
            daily_ls_returns.append(ls_ret)

        if len(daily_ls_returns) < 20:
            return 0.0

        ls_returns = pd.Series(daily_ls_returns)
        # 年化 Sharpe = sqrt(252) * mean / std
        sharpe = float(np.sqrt(252) * ls_returns.mean() / ls_returns.std()) if ls_returns.std() > 0 else 0.0
        return sharpe

    # ============================================================
    # 门控决策
    # ============================================================

    def _gate_decision(self, result: FactorEvaluationResult) -> tuple:
        """
        门控决策：晋升 / 观察 / 淘汰

        规则（参考 Paper 1 的透明门控机制）：
        - 晋升：至少 2 项指标达到晋升阈值，且无项达到淘汰阈值
        - 淘汰：任意 2 项指标达到淘汰阈值
        - 观察：其余情况

        Returns:
            (decision, reasons)
        """
        promote_count = 0
        eliminate_count = 0
        reasons = []

        # ICIR
        if abs(result.icir) >= self.thresholds['icir_promote']:
            promote_count += 1
            reasons.append(f'ICIR={result.icir:.2f} >= {self.thresholds["icir_promote"]}')
        elif abs(result.icir) < self.thresholds['icir_eliminate']:
            eliminate_count += 1
            reasons.append(f'ICIR={result.icir:.2f} < {self.thresholds["icir_eliminate"]}')

        # IC > 0 比例
        if result.ic_positive_pct >= self.thresholds['ic_positive_pct_promote']:
            promote_count += 1
            reasons.append(f'IC>0比例={result.ic_positive_pct:.1%} >= {self.thresholds["ic_positive_pct_promote"]:.0%}')
        elif result.ic_positive_pct < self.thresholds['ic_positive_pct_eliminate']:
            eliminate_count += 1
            reasons.append(f'IC>0比例={result.ic_positive_pct:.1%} < {self.thresholds["ic_positive_pct_eliminate"]:.0%}')

        # t 统计量
        if abs(result.t_stat) >= self.thresholds['t_stat_promote']:
            promote_count += 1
            reasons.append(f't={result.t_stat:.2f} >= {self.thresholds["t_stat_promote"]}')
        elif abs(result.t_stat) < self.thresholds['t_stat_eliminate']:
            eliminate_count += 1
            reasons.append(f't={result.t_stat:.2f} < {self.thresholds["t_stat_eliminate"]}')

        # 多空 Sharpe
        if abs(result.long_short_sharpe) >= self.thresholds['ls_sharpe_promote']:
            promote_count += 1
            reasons.append(f'多空Sharpe={result.long_short_sharpe:.2f} >= {self.thresholds["ls_sharpe_promote"]}')
        elif abs(result.long_short_sharpe) < self.thresholds['ls_sharpe_eliminate']:
            eliminate_count += 1
            reasons.append(f'多空Sharpe={result.long_short_sharpe:.2f} < {self.thresholds["ls_sharpe_eliminate"]}')

        # 决策逻辑
        if eliminate_count >= 2:
            return 'eliminate', reasons
        elif promote_count >= 2:
            return 'promote', reasons
        else:
            return 'observe', reasons

    # ============================================================
    # 报告生成
    # ============================================================

    def generate_report(self, results: List[FactorEvaluationResult]) -> str:
        """
        生成评估报告

        Args:
            results: 评估结果列表

        Returns:
            格式化的报告文本
        """
        lines = []
        lines.append("=" * 70)
        lines.append("截面因子评估报告")
        lines.append(f"评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"品种数量: {len(self._kline_data)}")
        lines.append("=" * 70)

        # 分组
        promoted = [r for r in results if r.decision == 'promote']
        observed = [r for r in results if r.decision == 'observe']
        eliminated = [r for r in results if r.decision == 'eliminate']

        for group_name, group in [('晋升', promoted), ('观察', observed), ('淘汰', eliminated)]:
            if not group:
                continue
            lines.append(f"\n--- {group_name} ({len(group)} 个) ---")
            for r in group:
                lines.append(f"  {r.factor_name}")
                lines.append(f"    IC均值={r.ic_mean:.4f}  ICIR={r.icir:.2f}  t={r.t_stat:.2f}")
                lines.append(f"    IC>0={r.ic_positive_pct:.1%}  多空Sharpe={r.long_short_sharpe:.2f}")
                lines.append(f"    样本={r.ic_days}天  截面={r.cross_section_size_avg:.0f}品种")
                if r.decision_reasons:
                    lines.append(f"    原因: {', '.join(r.decision_reasons[:3])}")

        lines.append("\n" + "=" * 70)
        lines.append(f"总计: {len(results)} 个因子, "
                     f"晋升 {len(promoted)}, 观察 {len(observed)}, 淘汰 {len(eliminated)}")
        lines.append("=" * 70)

        return '\n'.join(lines)

    def save_results(self, results: List[FactorEvaluationResult],
                     path: str = None):
        """
        保存评估结果到 JSON

        Args:
            results: 评估结果列表
            path: 保存路径
        """
        if path is None:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'data', 'factor_evaluation.json'
            )

        data = {
            'evaluation_time': datetime.now().isoformat(),
            'symbol_count': len(self._kline_data),
            'thresholds': self.thresholds,
            'results': [r.to_dict() for r in results],
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"评估结果已保存到 {path}")


# ============================================================
# 内置因子函数（用于测试和基准评估）
# ============================================================

def factor_momentum_20d(df: pd.DataFrame) -> pd.Series:
    """20 日动量因子"""
    return df['close'].pct_change(20)


def factor_momentum_60d(df: pd.DataFrame) -> pd.Series:
    """60 日动量因子"""
    return df['close'].pct_change(60)


def factor_volatility_20d(df: pd.DataFrame) -> pd.Series:
    """20 日波动率因子（负号：低波动做多）"""
    return -df['close'].pct_change().rolling(20).std()


def factor_volume_price_corr(df: pd.DataFrame) -> pd.Series:
    """量价相关性因子"""
    return df['close'].pct_change().rolling(20).corr(df['volume'].pct_change())


def factor_rsi_14d(df: pd.DataFrame) -> pd.Series:
    """RSI 因子（标准化到 [-1, 1]）"""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return (rsi - 50) / 50  # 标准化到 [-1, 1]


def factor_atr_ratio(df: pd.DataFrame) -> pd.Series:
    """ATR/价格比率因子（负号：低波动做多）"""
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    return -(atr / close)


def factor_trend_strength(df: pd.DataFrame) -> pd.Series:
    """趋势强度因子（EMA20 vs EMA60 距离）"""
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    ema60 = df['close'].ewm(span=60, adjust=False).mean()
    return (ema20 - ema60) / df['close']


# 内置因子集合
BUILTIN_FACTORS = {
    'momentum_20d': factor_momentum_20d,
    'momentum_60d': factor_momentum_60d,
    'volatility_20d': factor_volatility_20d,
    'volume_price_corr': factor_volume_price_corr,
    'rsi_14d': factor_rsi_14d,
    'atr_ratio': factor_atr_ratio,
    'trend_strength': factor_trend_strength,
}


# ============================================================
# 命令行入口
# ============================================================

def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='截面因子评估器')
    parser.add_argument('--db', type=str, default=None, help='DuckDB 数据库路径')
    parser.add_argument('--days', type=int, default=120, help='数据天数')
    parser.add_argument('--factors', type=str, default=None,
                        help='因子名称（逗号分隔），不指定则评估所有内置因子')
    parser.add_argument('--save', action='store_true', help='保存结果到 JSON')

    args = parser.parse_args()

    # 初始化评估器
    evaluator = FactorEvaluator(db_path=args.db)

    # 加载数据
    count = evaluator.load_data(days=args.days)
    print(f"加载 {count} 个品种的数据")

    if count < 10:
        print("品种数量不足（< 10），无法进行截面评估")
        return

    # 选择因子
    if args.factors:
        factor_names = [f.strip() for f in args.factors.split(',')]
        factors = {n: BUILTIN_FACTORS[n] for n in factor_names if n in BUILTIN_FACTORS}
    else:
        factors = BUILTIN_FACTORS

    if not factors:
        print("未找到匹配的因子")
        return

    # 评估
    print(f"\n评估 {len(factors)} 个因子...")
    results = evaluator.evaluate_batch(factors)

    # 输出报告
    report = evaluator.generate_report(results)
    print(report)

    # 保存结果
    if args.save:
        evaluator.save_results(results)
        print("\n结果已保存到 data/factor_evaluation.json")


if __name__ == '__main__':
    main()
