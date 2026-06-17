"""
场景分析器测试

测试概率加权场景分析功能
"""

import pytest
from trend_scanner.scenario_analyzer import (
    ScenarioAnalyzer,
    Scenario,
    ScenarioAnalysis,
    analyze_signal,
)


class TestScenarioAnalyzer:
    """场景分析器测试"""

    def test_basic_analysis(self):
        """基础分析测试"""
        analyzer = ScenarioAnalyzer()
        result = analyzer.analyze(
            symbol="RB",
            current_price=3600,
            indicators={"er": 0.65, "tsi": 25, "rsi": 58, "trend_strength_composite": 0.7},
            trend_phase="TREND_UP",
            volatility=0.02,
        )

        assert result.symbol == "RB"
        assert result.current_price == 3600
        assert len(result.scenarios) == 3
        assert result.overall_confidence in ["HIGH", "MEDIUM", "LOW"]
        assert result.recommendation in ["LONG", "SHORT", "HOLD"]

    def test_scenario_probabilities_sum_to_one(self):
        """场景概率之和为1"""
        analyzer = ScenarioAnalyzer()
        result = analyzer.analyze(
            symbol="I",
            current_price=800,
            indicators={"er": 0.5, "tsi": 0, "rsi": 50, "trend_strength_composite": 0},
            trend_phase="RANGE",
        )

        total_prob = sum(s.probability for s in result.scenarios)
        assert abs(total_prob - 1.0) < 0.01

    def test_bull_scenario_in_uptrend(self):
        """上升趋势中牛市概率更高"""
        analyzer = ScenarioAnalyzer()

        # 上升趋势
        result_up = analyzer.analyze(
            symbol="RB",
            current_price=3600,
            indicators={"er": 0.7, "tsi": 30, "rsi": 60, "trend_strength_composite": 0.8},
            trend_phase="TREND_UP",
        )

        # 下降趋势
        result_down = analyzer.analyze(
            symbol="RB",
            current_price=3600,
            indicators={"er": 0.7, "tsi": -30, "rsi": 40, "trend_strength_composite": -0.8},
            trend_phase="TREND_DOWN",
        )

        bull_prob_up = next(s.probability for s in result_up.scenarios if s.name == "bull")
        bull_prob_down = next(s.probability for s in result_down.scenarios if s.name == "bull")

        assert bull_prob_up > bull_prob_down

    def test_weighted_ev_calculation(self):
        """加权预期价值计算"""
        analyzer = ScenarioAnalyzer()
        result = analyzer.analyze(
            symbol="RB",
            current_price=3600,
            indicators={"er": 0.6, "tsi": 20, "rsi": 55, "trend_strength_composite": 0.5},
            trend_phase="TREND_UP",
        )

        # 手动计算 EV
        expected_ev = sum(s.probability * s.expected_return for s in result.scenarios)
        assert abs(result.weighted_ev - expected_ev) < 0.01

    def test_risk_reward_ratio(self):
        """风险收益比计算"""
        analyzer = ScenarioAnalyzer()
        result = analyzer.analyze(
            symbol="RB",
            current_price=3600,
            indicators={"er": 0.6, "tsi": 20, "rsi": 55, "trend_strength_composite": 0.5},
            trend_phase="TREND_UP",
        )

        assert result.risk_reward_ratio > 0

    def test_high_confidence_with_strong_signals(self):
        """强信号时置信度高"""
        analyzer = ScenarioAnalyzer()
        result = analyzer.analyze(
            symbol="RB",
            current_price=3600,
            indicators={
                "er": 0.8,
                "tsi": 40,
                "rsi": 65,
                "trend_strength_composite": 0.9,
                "r_squared": 0.7,
            },
            trend_phase="TREND_UP",
        )

        assert result.overall_confidence == "HIGH"

    def test_low_confidence_with_weak_signals(self):
        """弱信号时置信度低"""
        analyzer = ScenarioAnalyzer()
        result = analyzer.analyze(
            symbol="RB",
            current_price=3600,
            indicators={
                "er": 0.3,
                "tsi": 5,
                "rsi": 50,
                "trend_strength_composite": 0.1,
                "r_squared": 0.2,
            },
            trend_phase="RANGE",
        )

        assert result.overall_confidence == "LOW"

    def test_format_analysis(self):
        """格式化输出"""
        analyzer = ScenarioAnalyzer()
        result = analyzer.analyze(
            symbol="RB",
            current_price=3600,
            indicators={"er": 0.6, "tsi": 20, "rsi": 55, "trend_strength_composite": 0.5},
            trend_phase="TREND_UP",
        )

        formatted = analyzer.format_analysis(result)
        assert "RB" in formatted
        assert "当前价格" in formatted
        assert "加权 EV" in formatted
        assert "推荐" in formatted

    def test_to_dict(self):
        """转换为字典"""
        analyzer = ScenarioAnalyzer()
        result = analyzer.analyze(
            symbol="RB",
            current_price=3600,
            indicators={"er": 0.6, "tsi": 20, "rsi": 55, "trend_strength_composite": 0.5},
            trend_phase="TREND_UP",
        )

        d = result.to_dict()
        assert d["symbol"] == "RB"
        assert d["current_price"] == 3600
        assert len(d["scenarios"]) == 3

    def test_convenience_function(self):
        """便捷函数测试"""
        result = analyze_signal(
            symbol="I",
            current_price=800,
            indicators={"er": 0.6, "tsi": 20, "rsi": 55, "trend_strength_composite": 0.5},
            trend_phase="TREND_UP",
        )

        assert isinstance(result, ScenarioAnalysis)
        assert result.symbol == "I"

    def test_different_trend_phases(self):
        """不同趋势阶段的场景差异"""
        analyzer = ScenarioAnalyzer()

        phases = ["TREND_UP", "TREND_DOWN", "RANGE"]
        results = {}

        for phase in phases:
            results[phase] = analyzer.analyze(
                symbol="RB",
                current_price=3600,
                indicators={"er": 0.6, "tsi": 20, "rsi": 55, "trend_strength_composite": 0.5},
                trend_phase=phase,
            )

        # 上升趋势的推荐应该更偏多
        assert results["TREND_UP"].weighted_ev > results["TREND_DOWN"].weighted_ev
