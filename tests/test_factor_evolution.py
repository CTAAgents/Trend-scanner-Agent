"""
闭环因子进化引擎测试

测试进化引擎的核心功能：
1. 因子执行器
2. 门控决策器
3. 进化主循环
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))


# ============================================================
# 测试数据生成
# ============================================================

def generate_mock_data(n_symbols: int = 20, days: int = 120) -> dict:
    """生成模拟 K 线数据"""
    symbols = [f'TEST{i:02d}' for i in range(n_symbols)]
    dates = pd.date_range(end=pd.Timestamp('2026-06-15'), periods=days, freq='B')
    data = {}
    for i, sym in enumerate(symbols):
        np.random.seed(42 + i)
        prices = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, days)))
        data[sym] = pd.DataFrame({
            'date': dates,
            'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(10000, 100000, days).astype(float),
            'open_interest': np.random.randint(50000, 500000, days).astype(float),
        })
    return data


# ============================================================
# 测试 FactorExecutor
# ============================================================

class TestFactorExecutor:
    """FactorExecutor 测试"""

    def setup_method(self):
        from trend_scanner.factor_executor import FactorExecutor
        self.executor = FactorExecutor(safety_check=True)
        self.mock_data = generate_mock_data()

    def test_execute_valid_factor(self):
        """测试执行有效因子"""
        code = '''
def factor(df):
    """动量因子 5 日"""
    return df['close'].pct_change(5).fillna(0)
'''
        result = self.executor.execute(code, self.mock_data)
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert result.shape[1] == 20  # 20 个品种

    def test_execute_invalid_syntax(self):
        """测试执行语法错误的因子"""
        code = '''
def factor(df):
    return df['close'].pct_change(5
'''
        result = self.executor.execute(code, self.mock_data)
        assert result is None

    def test_execute_no_factor_function(self):
        """测试没有 factor 函数的代码"""
        code = '''
def not_factor(df):
    return df['close']
'''
        result = self.executor.execute(code, self.mock_data)
        assert result is None

    def test_safety_check_blocks_dangerous_code(self):
        """测试安全检查阻止危险代码"""
        from trend_scanner.factor_executor import FactorExecutor
        code = '''
def factor(df):
    import os
    os.system("rm -rf /")
    return df['close']
'''
        executor = FactorExecutor(safety_check=True)
        result = executor.execute(code, self.mock_data)
        assert result is None

    def test_safety_check_blocks_future_data(self):
        """测试安全检查阻止未来数据"""
        code = '''
def factor(df):
    return df['close'].shift(-1)
'''
        result = self.executor.execute(code, self.mock_data)
        assert result is None

    def test_execute_function(self):
        """测试直接执行函数"""
        def momentum(df):
            return df['close'].pct_change(5).fillna(0)

        result = self.executor.execute_function(momentum, self.mock_data)
        assert result is not None
        assert result.shape[1] == 20

    def test_validate_and_execute(self):
        """测试验证并执行"""
        code = '''
def factor(df):
    return df['close'].pct_change(5).fillna(0)
'''
        result = self.executor.validate_and_execute(code, self.mock_data)
        assert result['success'] is True
        assert result['symbol_count'] == 20


# ============================================================
# 测试 FactorGate
# ============================================================

class TestFactorGate:
    """FactorGate 测试"""

    def setup_method(self):
        from trend_scanner.factor_gate import FactorGate
        self.gate = FactorGate()

    def test_promote_decision(self):
        """测试晋升决策"""
        evaluation = {
            'icir': 1.5,
            'ic_positive_pct': 0.60,
            't_stat': 3.0,
            'long_short_sharpe': 1.5,
            'ic_days': 60,
        }
        decision = self.gate.decide('test_factor', evaluation)
        assert decision.decision == 'promote'
        assert decision.score > 0.7

    def test_eliminate_decision(self):
        """测试淘汰决策"""
        evaluation = {
            'icir': 0.2,
            'ic_positive_pct': 0.40,
            't_stat': 0.5,
            'long_short_sharpe': 0.2,
            'ic_days': 60,
        }
        decision = self.gate.decide('test_factor', evaluation)
        assert decision.decision == 'eliminate'
        assert decision.score < 0.3

    def test_observe_decision(self):
        """测试观察决策"""
        evaluation = {
            'icir': 0.7,
            'ic_positive_pct': 0.50,
            't_stat': 1.5,
            'long_short_sharpe': 0.8,
            'ic_days': 60,
        }
        decision = self.gate.decide('test_factor', evaluation)
        assert decision.decision == 'observe'

    def test_insufficient_data(self):
        """测试数据不足"""
        evaluation = {
            'icir': 1.5,
            'ic_positive_pct': 0.60,
            't_stat': 3.0,
            'long_short_sharpe': 1.5,
            'ic_days': 10,  # 不足 30 天
        }
        decision = self.gate.decide('test_factor', evaluation)
        assert decision.decision == 'observe'

    def test_batch_decide(self):
        """测试批量决策"""
        evaluations = {
            'good_factor': {
                'icir': 1.5, 'ic_positive_pct': 0.60,
                't_stat': 3.0, 'long_short_sharpe': 1.5, 'ic_days': 60,
            },
            'bad_factor': {
                'icir': 0.2, 'ic_positive_pct': 0.40,
                't_stat': 0.5, 'long_short_sharpe': 0.2, 'ic_days': 60,
            },
        }
        decisions = self.gate.decide_batch(evaluations)
        assert len(decisions) == 2

    def test_summarize(self):
        """测试汇总"""
        from trend_scanner.factor_gate import GateDecision
        decisions = [
            GateDecision('f1', 'promote', 0.9),
            GateDecision('f2', 'eliminate', 0.1),
            GateDecision('f3', 'observe', 0.5),
        ]
        summary = self.gate.summarize(decisions)
        assert summary['promote_count'] == 1
        assert summary['eliminate_count'] == 1
        assert summary['observe_count'] == 1


# ============================================================
# 测试 FactorEvolutionEngine
# ============================================================

class TestFactorEvolutionEngine:
    """FactorEvolutionEngine 测试"""

    def setup_method(self):
        from trend_scanner.factor_evolution_engine import FactorEvolutionEngine
        self.engine = FactorEvolutionEngine()
        self.mock_data = generate_mock_data()

    def test_evolve_basic(self):
        """测试基本进化流程"""
        result = self.engine.evolve(
            kline_data=self.mock_data,
            max_rounds=2,
            candidates_per_round=3,
            target_promoted=2,
        )
        assert result.total_rounds > 0
        assert result.total_candidates > 0
        assert result.status in ['completed', 'early_stop', 'max_rounds']

    def test_evolve_generates_report(self):
        """测试报告生成"""
        result = self.engine.evolve(
            kline_data=self.mock_data,
            max_rounds=1,
            candidates_per_round=2,
            target_promoted=1,
        )
        report = self.engine.generate_report(result)
        assert '因子进化报告' in report
        assert '轮次' in report

    def test_rule_variants(self):
        """测试规则变体生成"""
        variants = self.engine._generate_rule_variants(5, 1)
        assert len(variants) == 5
        for v in variants:
            assert 'name' in v
            assert 'code' in v

    def test_evolve_with_duckdb(self):
        """测试从 DuckDB 加载数据进化（跳过如果数据不足）"""
        from trend_scanner.factor_evaluator import FactorEvaluator
        evaluator = FactorEvaluator()
        count = evaluator.load_data(days=120)

        if count < 10:
            pytest.skip("DuckDB 数据不足")

        result = self.engine.evolve(
            max_rounds=1,
            candidates_per_round=2,
            target_promoted=1,
        )
        assert result.total_rounds > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
