"""
Phase 6.1: 端到端集成测试

测试 Phase 1-5 所有模块的完整流程：
  研报解析 → 因子生成 → 轨迹分析 → 概念反馈 → RL 接口设计

创建日期：2026-06-15
"""

import sys
import os
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.trend_scanner.factor_generator import FactorGenerator, FactorResult
from scripts.trend_scanner.factor_validator import FactorValidator
from scripts.trend_scanner.trajectory_analyzer import TrajectoryAnalyzer, TradeRecord
from scripts.trend_scanner.report_parser import ReportParser, ValidationPipeline, ReportAnalysis
from scripts.trend_scanner.conceptual_feedback import (
    ConceptualFeedbackGenerator, BeliefManager, TradeResult, InvestmentBelief
)
from scripts.trend_scanner.rl_interface_designer import RLInterfaceDesigner


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def tmp_knowledge_file(tmp_path):
    """创建临时因子知识库"""
    knowledge = {
        "factors": [
            {
                "id": "factor_001",
                "name": "test_momentum",
                "code": "def factor(df):\n    return df['close'].pct_change(5)",
                "description": "5-day momentum",
                "logic": "pct_change(5)",
                "regime_effectiveness": {"trending": 0.8, "ranging": 0.3, "volatile": 0.5},
                "source": "preset"
            }
        ],
        "metadata": {"version": "1.0", "last_updated": "2026-06-15"}
    }
    filepath = tmp_path / "factor_knowledge.json"
    filepath.write_text(json.dumps(knowledge, ensure_ascii=False), encoding="utf-8")
    return filepath


@pytest.fixture
def sample_trade_records():
    """示例交易记录（字典格式，供 TrajectoryAnalyzer.load_trade_history 使用）"""
    return [
        {
            "trade_id": "T001", "symbol": "DCE.jm2609", "direction": "LONG",
            "entry_price": 1500.0, "exit_price": 1560.0,
            "entry_time": "2026-06-01T09:00:00", "exit_time": "2026-06-03T15:00:00",
            "pnl": 60.0, "pnl_percent": 4.0, "holding_period": 2,
            "market_state": "trending", "trend_phase": "DEVELOPING", "volatility": "medium",
            "er": 0.7, "tsi": 0.6, "rsi": 55.0, "adx": 32.0,
            "max_drawdown": 0.02, "sharpe_ratio": 1.5,
            "failure_reason": None
        },
        {
            "trade_id": "T002", "symbol": "DCE.y2609", "direction": "SHORT",
            "entry_price": 8200.0, "exit_price": 8350.0,
            "entry_time": "2026-06-04T09:00:00", "exit_time": "2026-06-05T15:00:00",
            "pnl": -150.0, "pnl_percent": -1.83, "holding_period": 1,
            "market_state": "volatile", "trend_phase": "EXHAUSTING", "volatility": "high",
            "er": 0.3, "tsi": -0.2, "rsi": 65.0, "adx": 18.0,
            "max_drawdown": 0.05, "sharpe_ratio": -0.8,
            "failure_reason": "入场时机偏早，趋势尚未确立"
        },
        {
            "trade_id": "T003", "symbol": "CZCE.CF609", "direction": "SHORT",
            "entry_price": 14800.0, "exit_price": 14500.0,
            "entry_time": "2026-06-06T09:00:00", "exit_time": "2026-06-10T15:00:00",
            "pnl": 300.0, "pnl_percent": 2.03, "holding_period": 4,
            "market_state": "trending", "trend_phase": "MATURE", "volatility": "low",
            "er": 0.8, "tsi": -0.5, "rsi": 35.0, "adx": 38.0,
            "max_drawdown": 0.01, "sharpe_ratio": 2.1,
            "failure_reason": None
        },
    ]


@pytest.fixture
def sample_trade_result():
    """示例交易结果（用于概念反馈）"""
    return TradeResult(
        trade_id="T001", symbol="DCE.jm2609", direction="LONG",
        entry_price=1500.0, exit_price=1560.0,
        pnl=60.0, pnl_percent=4.0, holding_period=2,
        market_state="trending", trend_phase="DEVELOPING",
        entry_reason="动量突破信号 + 成交量放大",
        exit_reason="达到目标止盈位",
        success_factors=["趋势确立", "成交量配合", "止损合理"],
        failure_factors=[]
    )


@pytest.fixture
def sample_report_content():
    """示例研报内容（内联格式，匹配 ReportParser 规则提取模式）"""
    return """焦煤市场分析报告

核心观点：安全检查限产导致供应收紧，焦煤价格有支撑，焦化利润维持高位对焦煤需求形成支撑。
主要观点：港口库存处于低位，补库需求存在，焦化利润 300 元/吨处于年内高位。

数据逻辑：
- 焦煤矿开工率降至 65%，同比下降 10 个百分点
- 焦化利润 300 元/吨，处于年内高位
- 港口库存 150 万吨，处于近三年低位

逻辑链：限产 → 供应收紧 → 库存下降 → 价格上涨

因子建议：基于库存/开工率比率构建供应紧张因子
"""


@pytest.fixture
def sample_report_metadata():
    """示例研报元数据"""
    return {
        "source": "test_research",
        "category": "supply_analysis",
        "published_at": "2026-06-15"
    }


# ============================================================
# 集成测试
# ============================================================

class TestModuleInitialization:
    """测试各模块能正常初始化（无 LLM 依赖）"""

    def test_factor_generator_init(self, tmp_knowledge_file):
        """Phase 1: 因子生成器初始化"""
        gen = FactorGenerator()
        assert gen is not None

    def test_trajectory_analyzer_init(self, sample_trade_records):
        """Phase 2: 轨迹分析器初始化"""
        analyzer = TrajectoryAnalyzer(trades=sample_trade_records)
        assert analyzer is not None
        assert len(analyzer.trades) == 3

    def test_report_parser_init(self):
        """Phase 3: 研报解析器初始化"""
        parser = ReportParser()
        assert parser is not None

    def test_validation_pipeline_init(self):
        """Phase 3: 验证流水线初始化"""
        pipeline = ValidationPipeline()
        assert pipeline is not None

    def test_conceptual_feedback_init(self):
        """Phase 4: 概念反馈生成器初始化"""
        gen = ConceptualFeedbackGenerator()
        assert gen is not None

    def test_belief_manager_init(self):
        """Phase 4: 信念管理器初始化"""
        manager = BeliefManager()
        assert manager is not None

    def test_rl_interface_designer_init(self):
        """Phase 5: RL 接口设计器初始化"""
        designer = RLInterfaceDesigner()
        assert designer is not None


class TestPhase3ReportParsing:
    """测试 Phase 3 研报解析"""

    def test_parse_report_returns_analysis(self, sample_report_content, sample_report_metadata):
        """研报解析返回 ReportAnalysis 结构"""
        parser = ReportParser()
        analysis = parser.parse_report(sample_report_content, sample_report_metadata)

        assert isinstance(analysis, ReportAnalysis)
        assert analysis.report_source == "test_research"
        assert len(analysis.key_viewpoints) > 0
        assert len(analysis.data_logic) > 0

    def test_validation_pipeline_accepts_analysis(self, sample_report_content, sample_report_metadata):
        """验证流水线接受有效分析结果"""
        parser = ReportParser()
        analysis = parser.parse_report(sample_report_content, sample_report_metadata)

        pipeline = ValidationPipeline()
        result = pipeline.validate_analysis(analysis)

        assert result["is_valid"] is True
        assert isinstance(result["warnings"], list)

    def test_report_generates_factor_suggestions(self, sample_report_content, sample_report_metadata):
        """研报能生成因子建议"""
        parser = ReportParser()
        analysis = parser.parse_report(sample_report_content, sample_report_metadata)

        assert len(analysis.factor_suggestions) > 0
        suggestion = analysis.factor_suggestions[0]
        assert suggestion.name != ""
        assert suggestion.logic != ""


class TestPhase2TrajectoryAnalysis:
    """测试 Phase 2 轨迹分析"""

    def test_analyze_returns_complete_report(self, sample_trade_records):
        """轨迹分析返回完整报告"""
        analyzer = TrajectoryAnalyzer(trades=sample_trade_records)
        report = analyzer.analyze()

        assert "summary" in report
        assert "patterns" in report
        assert "optimization_rules" in report
        assert "failure_analysis" in report
        assert "success_analysis" in report

    def test_analyze_summary_accuracy(self, sample_trade_records):
        """轨迹分析摘要统计正确"""
        analyzer = TrajectoryAnalyzer(trades=sample_trade_records)
        report = analyzer.analyze()

        summary = report["summary"]
        assert summary["total_trades"] == 3
        # 3 笔交易中 2 笔盈利
        assert summary["win_rate"] == pytest.approx(2 / 3, abs=0.01)

    def test_analyze_identifies_failure_patterns(self, sample_trade_records):
        """轨迹分析能识别失败模式"""
        analyzer = TrajectoryAnalyzer(trades=sample_trade_records)
        report = analyzer.analyze()

        failure = report["failure_analysis"]
        assert failure["total_failures"] == 1
        assert failure["trades"][0]["trade_id"] == "T002"


class TestPhase4ConceptualFeedback:
    """测试 Phase 4 概念反馈"""

    def test_generate_feedback_success(self, sample_trade_result):
        """成功交易的概念反馈"""
        gen = ConceptualFeedbackGenerator()
        feedback = gen.generate_feedback(sample_trade_result)

        assert feedback.feedback_type == "success"
        assert feedback.trade_id == "T001"
        assert len(feedback.key_lessons) > 0
        assert 0.0 <= feedback.confidence <= 1.0

    def test_belief_manager_create_and_query(self):
        """信念管理器创建和查询信念"""
        manager = BeliefManager()

        belief = manager.create_belief(
            category="entry",
            content="高 ER 值时入场胜率更高",
            confidence=0.7
        )

        assert belief.belief_id != ""
        assert belief.category == "entry"
        assert belief.confidence == 0.7

        beliefs = manager.get_beliefs_by_category("entry")
        assert len(beliefs) >= 1

    def test_feedback_failure_trade(self):
        """失败交易的概念反馈"""
        gen = ConceptualFeedbackGenerator()

        failure_result = TradeResult(
            trade_id="T002", symbol="DCE.y2609", direction="SHORT",
            entry_price=8200.0, exit_price=8350.0,
            pnl=-150.0, pnl_percent=-1.83, holding_period=1,
            market_state="volatile", trend_phase="EXHAUSTING",
            entry_reason="RSI 超买反转信号",
            exit_reason="止损触发",
            success_factors=[],
            failure_factors=["入场时机偏早", "止损过紧", "市场波动率过高"]
        )

        feedback = gen.generate_feedback(failure_result)

        assert feedback.feedback_type == "failure"
        assert len(feedback.key_lessons) > 0


class TestPhase5RLInterfaceDesign:
    """测试 Phase 5 RL 接口设计"""

    def test_design_interface_rule_mode(self):
        """规则模式下设计 RL 接口"""
        designer = RLInterfaceDesigner()
        design = designer.design_interface(
            market_context="焦煤市场处于上升趋势",
            trading_objective="捕捉趋势机会，控制回撤在 10% 以内",
            available_data=["close", "volume", "high", "low", "open"],
            risk_rules={"max_drawdown": 0.10, "position_limit": 0.3}
        )

        assert "state_space" in design
        assert "reward_function" in design
        assert design["state_space"]["dimension"] > 0
        assert len(design["reward_function"]["components"]) > 0

    def test_refine_interface_with_metrics(self):
        """诊断引导修正接口设计"""
        designer = RLInterfaceDesigner()

        design = designer.design_interface(
            market_context="测试市场",
            trading_objective="测试目标",
            available_data=["close", "volume"],
            risk_rules={"max_drawdown": 0.10}
        )

        refinement = designer.refine_interface(
            current_design=design,
            training_metrics={"sharpe": 0.5, "max_drawdown": 0.15, "win_rate": 0.45},
            expected_metrics={"sharpe": 1.0, "max_drawdown": 0.10, "win_rate": 0.55}
        )

        assert "diagnostics" in refinement
        assert "refinement_actions" in refinement
        assert refinement["summary"]["total_diagnostics"] > 0


class TestFullPipeline:
    """端到端全流程集成测试"""

    def test_report_to_factor_suggestion(self, sample_report_content, sample_report_metadata):
        """流程 1: 研报 → 因子建议"""
        parser = ReportParser()
        analysis = parser.parse_report(sample_report_content, sample_report_metadata)

        # 研报应产出因子建议
        assert len(analysis.factor_suggestions) > 0

        # 验证因子建议有效
        pipeline = ValidationPipeline()
        validation = pipeline.validate_analysis(analysis)
        assert validation["is_valid"] is True

    def test_trajectory_to_feedback_to_belief(
        self, sample_trade_records, sample_trade_result
    ):
        """流程 2: 交易记录 → 轨迹分析 → 概念反馈 → 信念更新"""
        # Step 1: 轨迹分析
        analyzer = TrajectoryAnalyzer(trades=sample_trade_records)
        report = analyzer.analyze()
        assert report["summary"]["total_trades"] == 3

        # Step 2: 基于轨迹分析生成概念反馈
        feedback_gen = ConceptualFeedbackGenerator()
        feedback = feedback_gen.generate_feedback(sample_trade_result)
        assert feedback.feedback_type == "success"

        # Step 3: 将反馈写入信念
        belief_mgr = BeliefManager()
        for lesson in feedback.key_lessons:
            belief = belief_mgr.create_belief(
                category="entry",
                content=lesson,
                confidence=feedback.confidence
            )
            assert belief.belief_id != ""

        # 验证信念已创建
        beliefs = belief_mgr.get_beliefs_by_category("entry")
        assert len(beliefs) >= 1

    def test_rl_design_with_trajectory_context(self, sample_trade_records):
        """流程 3: 轨迹分析结果 → RL 接口设计"""
        # Step 1: 轨迹分析
        analyzer = TrajectoryAnalyzer(trades=sample_trade_records)
        report = analyzer.analyze()

        # Step 2: 用轨迹分析结果构建 RL 接口设计输入
        market_context = f"基于 {report['summary']['total_trades']} 笔交易分析，胜率 {report['summary']['win_rate']:.1%}"
        trading_objective = "优化入场时机，提高胜率"

        designer = RLInterfaceDesigner()
        design = designer.design_interface(
            market_context=market_context,
            trading_objective=trading_objective,
            available_data=["close", "volume", "high", "low", "open"],
            risk_rules={"max_drawdown": 0.10, "position_limit": 0.3}
        )

        assert design["state_space"]["dimension"] > 0
        assert len(design["reward_function"]["components"]) > 0

        # Step 3: 用实际回测指标诊断设计
        # 模拟实际指标低于预期
        refinement = designer.refine_interface(
            current_design=design,
            training_metrics={
                "sharpe": report["summary"]["win_rate"] - 0.2,
                "max_drawdown": 0.12,
                "win_rate": report["summary"]["win_rate"]
            },
            expected_metrics={
                "sharpe": 1.0,
                "max_drawdown": 0.08,
                "win_rate": 0.6
            }
        )

        assert refinement["summary"]["total_diagnostics"] > 0

    def test_full_end_to_end_pipeline(
        self,
        sample_report_content,
        sample_report_metadata,
        sample_trade_records,
        sample_trade_result
    ):
        """完整端到端流程：研报→因子→交易→轨迹→反馈→信念→RL设计"""

        # === Phase 3: 研报解析 ===
        parser = ReportParser()
        analysis = parser.parse_report(sample_report_content, sample_report_metadata)

        pipeline = ValidationPipeline()
        validation = pipeline.validate_analysis(analysis)
        assert validation["is_valid"], "研报验证失败"

        # === Phase 1: 因子建议提取 ===
        factor_suggestions = analysis.factor_suggestions
        assert len(factor_suggestions) > 0, "研报未产生因子建议"

        # === Phase 2: 轨迹分析 ===
        analyzer = TrajectoryAnalyzer(trades=sample_trade_records)
        trajectory_report = analyzer.analyze()

        assert trajectory_report["summary"]["total_trades"] == 3
        assert trajectory_report["summary"]["win_rate"] > 0

        # === Phase 4: 概念反馈 + 信念 ===
        feedback_gen = ConceptualFeedbackGenerator()
        feedback = feedback_gen.generate_feedback(sample_trade_result)

        belief_mgr = BeliefManager()
        # 将研报观点写入信念
        for vp in analysis.key_viewpoints[:3]:
            belief = belief_mgr.create_belief(
                category="market",
                content=vp.content if hasattr(vp, 'content') else str(vp),
                confidence=0.6
            )
            assert belief.belief_id != ""

        # 将反馈教训写入信念
        for lesson in feedback.key_lessons:
            belief = belief_mgr.create_belief(
                category="entry",
                content=lesson,
                confidence=feedback.confidence
            )
            assert belief.belief_id != ""

        # === Phase 5: RL 接口设计 ===
        designer = RLInterfaceDesigner()
        rl_design = designer.design_interface(
            market_context=f"基于研报分析：{analysis.key_viewpoints[0] if analysis.key_viewpoints else '无'}",
            trading_objective="捕捉趋势机会",
            available_data=["close", "volume", "high", "low", "open"],
            risk_rules={"max_drawdown": 0.10}
        )

        assert rl_design["state_space"]["dimension"] > 0
        assert len(rl_design["reward_function"]["components"]) > 0

        # 诊断修正
        refinement = designer.refine_interface(
            current_design=rl_design,
            training_metrics={"sharpe": 0.5, "max_drawdown": 0.15},
            expected_metrics={"sharpe": 1.0, "max_drawdown": 0.10}
        )

        assert refinement["summary"]["total_diagnostics"] > 0

        # === 汇总验证 ===
        all_beliefs = belief_mgr.get_beliefs_by_category("market") + \
                      belief_mgr.get_beliefs_by_category("entry")
        assert len(all_beliefs) >= 2, "信念库应包含至少 2 条信念"

        print("\n=== 端到端集成测试通过 ===")
        print(f"  研报观点数: {len(analysis.key_viewpoints)}")
        print(f"  因子建议数: {len(factor_suggestions)}")
        print(f"  交易轨迹数: {trajectory_report['summary']['total_trades']}")
        print(f"  概念反馈类型: {feedback.feedback_type}")
        print(f"  信念总数: {len(all_beliefs)}")
        print(f"  RL 状态维度: {rl_design['state_space']['dimension']}")
        print(f"  RL 诊断数: {refinement['summary']['total_diagnostics']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
