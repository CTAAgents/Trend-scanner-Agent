"""
截面因子评估器测试

测试因子评估器的核心功能：
1. 因子计算
2. 截面 IC 计算
3. 门控决策
4. 批量评估
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from trend_scanner.factor_evaluator import (
    FactorEvaluator,
    FactorEvaluationResult,
    BUILTIN_FACTORS,
    GATE_THRESHOLDS,
)


# ============================================================
# 测试数据生成
# ============================================================

def generate_mock_kline(symbol: str, days: int = 120, seed: int = 42) -> pd.DataFrame:
    """生成模拟 K 线数据"""
    np.random.seed(seed + hash(symbol) % 1000)

    dates = pd.date_range(end=datetime.now(), periods=days, freq='B')
    base_price = 100 + np.random.randint(0, 900)
    returns = np.random.normal(0.0005, 0.02, days)
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.015, days))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.015, days))),
        'close': prices,
        'volume': np.random.randint(10000, 1000000, days).astype(float),
        'open_interest': np.random.randint(50000, 500000, days).astype(float),
    })
    return df


def generate_mock_data(n_symbols: int = 20, days: int = 120) -> dict:
    """生成多品种模拟数据"""
    symbols = [f'TEST{i:02d}' for i in range(n_symbols)]
    data = {}
    for sym in symbols:
        data[sym] = generate_mock_kline(sym, days)
    return data


# ============================================================
# 测试用例
# ============================================================

class TestFactorEvaluator:
    """FactorEvaluator 测试类"""

    def setup_method(self):
        """每个测试前初始化"""
        self.evaluator = FactorEvaluator()
        self.mock_data = generate_mock_data(n_symbols=20, days=120)
        self.evaluator.set_data(self.mock_data)

    def test_data_loading(self):
        """测试数据加载"""
        assert len(self.evaluator._kline_data) == 20
        assert self.evaluator._returns is not None
        assert len(self.evaluator._returns) > 0

    def test_compute_factor(self):
        """测试因子计算"""
        def simple_factor(df):
            return df['close'].pct_change(5)

        result = self.evaluator.compute_factor('test_factor', simple_factor)
        assert not result.empty
        assert result.shape[1] == 20  # 20 个品种
        assert result.shape[0] > 0    # 有数据行

    def test_cross_sectional_ic(self):
        """测试截面 IC 计算"""
        def momentum(df):
            return df['close'].pct_change(20)

        factor_values = self.evaluator.compute_factor('momentum', momentum)
        ic = self.evaluator.compute_cross_sectional_ic(factor_values)

        assert len(ic) > 0
        assert isinstance(ic, pd.Series)
        # IC 应在 [-1, 1] 范围内
        assert ic.abs().max() <= 1.0

    def test_evaluate_factor(self):
        """测试完整因子评估"""
        def momentum(df):
            return df['close'].pct_change(20)

        result = self.evaluator.evaluate('momentum_20d', momentum)

        assert isinstance(result, FactorEvaluationResult)
        assert result.factor_name == 'momentum_20d'
        assert result.ic_days > 0
        assert result.decision in ['promote', 'observe', 'eliminate']
        assert len(result.decision_reasons) > 0

    def test_evaluate_batch(self):
        """测试批量评估"""
        factors = {
            'momentum_20d': lambda df: df['close'].pct_change(20),
            'volatility': lambda df: -df['close'].pct_change().rolling(20).std(),
        }

        results = self.evaluator.evaluate_batch(factors)
        assert len(results) == 2
        for r in results:
            assert isinstance(r, FactorEvaluationResult)

    def test_gate_decision_promote(self):
        """测试晋升决策"""
        result = FactorEvaluationResult(
            factor_name='test',
            icir=1.5,
            ic_positive_pct=0.60,
            t_stat=3.0,
            long_short_sharpe=1.5,
            ic_days=60,
        )
        decision, reasons = self.evaluator._gate_decision(result)
        assert decision == 'promote'

    def test_gate_decision_eliminate(self):
        """测试淘汰决策"""
        result = FactorEvaluationResult(
            factor_name='test',
            icir=0.2,
            ic_positive_pct=0.40,
            t_stat=0.5,
            long_short_sharpe=0.2,
            ic_days=60,
        )
        decision, reasons = self.evaluator._gate_decision(result)
        assert decision == 'eliminate'

    def test_gate_decision_observe(self):
        """测试观察决策"""
        result = FactorEvaluationResult(
            factor_name='test',
            icir=0.7,       # 介于 0.5 和 1.0 之间
            ic_positive_pct=0.50,
            t_stat=1.5,
            long_short_sharpe=0.8,
            ic_days=60,
        )
        decision, reasons = self.evaluator._gate_decision(result)
        assert decision == 'observe'

    def test_builtin_factors(self):
        """测试内置因子函数"""
        assert len(BUILTIN_FACTORS) == 7
        for name, fn in BUILTIN_FACTORS.items():
            # 每个因子应该能对测试数据计算
            df = self.mock_data['TEST00']
            result = fn(df)
            assert result is not None
            assert len(result) > 0

    def test_report_generation(self):
        """测试报告生成"""
        results = [
            FactorEvaluationResult(
                factor_name='good_factor', icir=1.2, decision='promote',
                ic_mean=0.05, ic_positive_pct=0.60, t_stat=2.5,
                long_short_sharpe=1.3, ic_days=60, cross_section_size_avg=20,
            ),
            FactorEvaluationResult(
                factor_name='bad_factor', icir=0.3, decision='eliminate',
                ic_mean=0.01, ic_positive_pct=0.42, t_stat=0.8,
                long_short_sharpe=0.3, ic_days=60, cross_section_size_avg=20,
            ),
        ]

        report = self.evaluator.generate_report(results)
        assert '晋升' in report
        assert '淘汰' in report
        assert 'good_factor' in report
        assert 'bad_factor' in report

    def test_result_serialization(self):
        """测试结果序列化"""
        result = FactorEvaluationResult(
            factor_name='test', icir=1.0, decision='promote',
            ic_series=pd.Series([0.1, 0.2, 0.3]),  # 不应被序列化
        )
        d = result.to_dict()
        assert 'ic_series' not in d
        assert d['factor_name'] == 'test'
        assert d['icir'] == 1.0

    def test_insufficient_data(self):
        """测试数据不足的情况"""
        # 只有 2 个品种，不足 10 个
        small_data = {k: v for k, v in list(self.mock_data.items())[:2]}
        evaluator = FactorEvaluator()
        evaluator.set_data(small_data)

        def momentum(df):
            return df['close'].pct_change(20)

        result = evaluator.evaluate('test', momentum)
        # 应该因为截面大小不足而无法计算 IC
        assert result.decision in ['observe', 'eliminate']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
