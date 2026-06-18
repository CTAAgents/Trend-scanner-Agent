"""
QuantNova v5.0 性能基准测试

验证各模块的执行时间在可接受范围内：

原有模块:
- 因子生成（规则模式）< 5s
- 轨迹分析（100笔交易）< 10s
- 研报解析（规则模式）< 3s
- RL 接口设计（规则模式）< 5s

核心引擎:
- IndicatorEngine.compute_all()（120行OHLCV）< 2s
- TrendPhaseDetector.detect() < 0.5s
- 因子代码 exec 执行 < 1s
- TrajectoryAnalyzer（50笔交易）< 5s
- IndicatorEngine 内存增量 < 50 MB

创建日期：2026-06-15
"""

import json
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.trend_scanner.conceptual_feedback import ConceptualFeedbackGenerator, TradeResult
from scripts.trend_scanner.factor_generator import FactorGenerator
from scripts.trend_scanner.indicators import IndicatorEngine
from scripts.trend_scanner.market_analysis import MultiIndicatorConsensus, TrendPhaseDetector
from scripts.trend_scanner.report_parser import ReportParser
from scripts.trend_scanner.rl_interface_designer import RLInterfaceDesigner
from scripts.trend_scanner.trajectory_analyzer import TrajectoryAnalyzer


# ============================================================
# Markers
# ============================================================
pytestmark = pytest.mark.benchmark


# ============================================================
# 辅助函数
# ============================================================


def generate_trade_records(n: int):
    """生成 n 笔交易记录（原有逻辑，保留向后兼容）"""
    records = []
    for i in range(n):
        pnl = 100.0 if i % 3 != 0 else -80.0
        records.append(
            {
                "trade_id": f"T{i:04d}",
                "symbol": "DCE.jm2609",
                "direction": "LONG" if i % 2 == 0 else "SHORT",
                "entry_price": 1500.0 + i * 10,
                "exit_price": 1500.0 + i * 10 + (60.0 if pnl > 0 else -80.0),
                "entry_time": f"2026-06-{(i % 28) + 1:02d}T09:00:00",
                "exit_time": f"2026-06-{(i % 28) + 1:02d}T15:00:00",
                "pnl": pnl,
                "pnl_percent": pnl / 1500.0 * 100,
                "holding_period": (i % 5) + 1,
                "market_state": ["trending", "ranging", "volatile"][i % 3],
                "trend_phase": ["DEVELOPING", "MATURE", "EXHAUSTING"][i % 3],
                "volatility": ["low", "medium", "high"][i % 3],
                "er": 0.3 + (i % 5) * 0.1,
                "tsi": -0.3 + (i % 7) * 0.1,
                "rsi": 30.0 + (i % 40),
                "adx": 15.0 + (i % 30),
                "max_drawdown": 0.01 + (i % 5) * 0.01,
                "sharpe_ratio": -0.5 + (i % 4) * 0.5,
                "failure_reason": "止损过紧" if pnl < 0 else None,
            }
        )
    return records


# ╔═══════════════════════════════════════════════════════════╗
# ║  NEW: 核心引擎性能基准测试                                ║
# ╚═══════════════════════════════════════════════════════════╝


class TestIndicatorEnginePerformance:
    """IndicatorEngine 技术指标计算性能"""

    def test_compute_all_120_rows(self, ohlcv_120: pd.DataFrame):
        """
        IndicatorEngine.compute_all() 处理 120 行 OHLCV < 2s

        compute_all() 会依次计算 EMA/SMA/ATR/ADX/ADX_Pct/Donchian/
        MACD/Bollinger/CCI/RSI/STOCH/STOCHRSI/Williams_R/Ultimate_Osc/
        ROC/Bull_Bear_Power/Swing_Structure/ER/R²/Hurst/ADX_ROC/
        EMA_Slope_Strength/TSI/ATR_Ratio 等 35+ 指标。
        """
        engine = IndicatorEngine(ohlcv_120)

        start = time.perf_counter()
        result = engine.compute_all()
        elapsed = time.perf_counter() - start

        # 阈值: 2 秒（120 行是标准测试规模）
        assert elapsed < 2.0, f"IndicatorEngine.compute_all() 120行耗时 {elapsed:.3f}s，超过 2s 阈值"
        # 验证结果完整性
        assert len(result) == 120
        assert "adx" in result.columns
        assert "rsi" in result.columns
        assert "macd" in result.columns
        assert "ema20" in result.columns
        print(f"\n  IndicatorEngine.compute_all(120行): {elapsed:.3f}s")

    def test_compute_all_200_rows(self, ohlcv_200: pd.DataFrame):
        """IndicatorEngine.compute_all() 处理 200 行 < 3s"""
        engine = IndicatorEngine(ohlcv_200)

        start = time.perf_counter()
        result = engine.compute_all()
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0, f"IndicatorEngine.compute_all() 200行耗时 {elapsed:.3f}s，超过 3s 阈值"
        assert len(result) == 200
        print(f"\n  IndicatorEngine.compute_all(200行): {elapsed:.3f}s")

    def test_compute_all_500_rows(self, ohlcv_500: pd.DataFrame):
        """IndicatorEngine.compute_all() 处理 500 行（压力测试）< 8s"""
        engine = IndicatorEngine(ohlcv_500)

        start = time.perf_counter()
        result = engine.compute_all()
        elapsed = time.perf_counter() - start

        assert elapsed < 8.0, f"IndicatorEngine.compute_all() 500行耗时 {elapsed:.3f}s，超过 8s 阈值"
        assert len(result) == 500
        print(f"\n  IndicatorEngine.compute_all(500行): {elapsed:.3f}s")

    def test_single_indicator_adx(self, ohlcv_120: pd.DataFrame):
        """单个 ADX 指标计算 < 0.3s"""
        engine = IndicatorEngine(ohlcv_120)

        start = time.perf_counter()
        engine.add_adx(14)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"ADX 计算耗时 {elapsed:.3f}s，超过 0.5s 阈值"
        assert "adx" in engine.df.columns
        assert "plus_di" in engine.df.columns
        print(f"\n  ADX 单指标: {elapsed:.4f}s")

    def test_single_indicator_rsi(self, ohlcv_120: pd.DataFrame):
        """单个 RSI（Wilder's）指标计算 < 0.3s"""
        engine = IndicatorEngine(ohlcv_120)

        start = time.perf_counter()
        engine.add_rsi(14)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"RSI 计算耗时 {elapsed:.3f}s，超过 0.5s 阈值"
        assert "rsi" in engine.df.columns
        print(f"\n  RSI 单指标: {elapsed:.4f}s")


class TestTrendPhaseDetectorPerformance:
    """TrendPhaseDetector 趋势阶段识别性能"""

    def test_detect_speed(self, indicator_df_200: pd.DataFrame):
        """
        TrendPhaseDetector.detect() 单次调用 < 0.5s

        detect() 执行多指标确认：反转期、衰竭期、成熟期、
        发展期、萌芽期、假突破回退检测，最后计算可靠性评分。
        """
        start = time.perf_counter()
        phase, confidence, reliability, breakdown, alerts, evidence = TrendPhaseDetector.detect(
            indicator_df_200, "trending"
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"TrendPhaseDetector.detect() 耗时 {elapsed:.3f}s，超过 0.5s 阈值"
        assert phase in TrendPhaseDetector.PHASES
        assert 0 <= confidence <= 1.0
        assert 0 <= reliability <= 100
        print(f"\n  TrendPhaseDetector.detect(): {elapsed:.4f}s, phase={phase}")

    def test_detect_100_iterations(self, indicator_df_200: pd.DataFrame):
        """TrendPhaseDetector.detect() 连续 100 次 < 3s（模拟实盘场景）"""
        start = time.perf_counter()
        for _ in range(100):
            TrendPhaseDetector.detect(indicator_df_200, "trending")
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0, f"100 次 TrendPhaseDetector.detect() 耗时 {elapsed:.2f}s，超过 3s 阈值"
        per_call = elapsed / 100
        print(f"\n  TrendPhaseDetector.detect() × 100: {elapsed:.3f}s, 每次 {per_call * 1000:.2f}ms")

    def test_consensus_speed(self, indicator_df_200: pd.DataFrame):
        """MultiIndicatorConsensus.consensus() 单次调用 < 1s"""
        start = time.perf_counter()
        result = MultiIndicatorConsensus.consensus(indicator_df_200)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"MultiIndicatorConsensus.consensus() 耗时 {elapsed:.3f}s，超过 1s 阈值"
        assert "state" in result
        assert "confidence" in result
        print(f"\n  MultiIndicatorConsensus.consensus(): {elapsed:.4f}s, state={result['state']}")


class TestFactorCodeExecutionPerformance:
    """因子代码 exec 执行性能"""

    def test_factor_exec_speed(self, ohlcv_120: pd.DataFrame, factor_code: str):
        """
        通过 exec() 执行因子代码 < 1s

        模拟 FactorGenerator 产出的因子代码被执行的场景：
        加载代码 → exec → 调用 factor() → 获取结果。
        """
        namespace: dict = {"pd": pd, "np": np}
        start = time.perf_counter()
        exec(factor_code, namespace)
        factor_func = namespace["factor"]
        result = factor_func(ohlcv_120.copy())
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"因子代码 exec 执行耗时 {elapsed:.3f}s，超过 1s 阈值"
        assert isinstance(result, pd.Series)
        assert len(result) == len(ohlcv_120)
        print(f"\n  因子代码 exec: {elapsed:.4f}s, 输出长度={len(result)}")

    def test_factor_exec_from_knowledge_base(self, ohlcv_120: pd.DataFrame):
        """
        从 factor_knowledge.json 加载并执行第一个因子 < 1.5s

        完整的因子生命周期：读取 JSON → 提取代码 → exec → 运行。
        """
        knowledge_path = PROJECT_ROOT / "data" / "factor_knowledge.json"
        if not knowledge_path.exists():
            pytest.skip("factor_knowledge.json 不存在")

        with open(knowledge_path, encoding="utf-8") as f:
            knowledge = json.load(f)

        factors = knowledge.get("factors", [])
        if not factors:
            pytest.skip("因子知识库为空")

        # 取第一个有代码的因子
        factor_code = None
        for fac in factors:
            if fac.get("code") and "def factor" in fac.get("code", ""):
                factor_code = fac["code"]
                break

        if factor_code is None:
            pytest.skip("未找到可执行的因子代码")

        namespace: dict = {"pd": pd, "np": np}
        start = time.perf_counter()
        exec(factor_code, namespace)
        factor_func = namespace["factor"]
        result = factor_func(ohlcv_120.copy())
        elapsed = time.perf_counter() - start

        assert elapsed < 1.5, f"因子(知识库) exec 耗时 {elapsed:.3f}s，超过 1.5s 阈值"
        assert isinstance(result, pd.Series)
        print(f"\n  因子知识库 exec: {elapsed:.4f}s")

    def test_factor_exec_200_rows(self, ohlcv_200: pd.DataFrame, factor_code: str):
        """因子 exec 200 行数据 < 1s"""
        namespace: dict = {"pd": pd, "np": np}
        start = time.perf_counter()
        exec(factor_code, namespace)
        result = namespace["factor"](ohlcv_200.copy())
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"因子 exec 200行耗时 {elapsed:.3f}s，超过 1s 阈值"
        print(f"\n  因子 exec (200行): {elapsed:.4f}s")


class TestTrajectoryAnalyzer50Performance:
    """TrajectoryAnalyzer 50 笔交易基准（使用 conftest 的随机化 fixture）"""

    def test_analyze_50_trades(self, trade_history_50: list):
        """
        TrajectoryAnalyzer.analyze() 50 笔交易 < 5s

        包含：案例分类 → 模式提取 → 优化规则生成 → 报告生成。
        """
        analyzer = TrajectoryAnalyzer()
        analyzer.load_trade_history(trade_history_50)

        start = time.perf_counter()
        report = analyzer.analyze()
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"轨迹分析(50笔)耗时 {elapsed:.2f}s，超过 5s 阈值"
        assert report["summary"]["total_trades"] == 50
        assert "patterns" in report
        assert "optimization_rules" in report
        print(f"\n  TrajectoryAnalyzer(50笔): {elapsed:.3f}s")

    def test_load_and_analyze_combined(self, trade_history_50: list):
        """load_trade_history + analyze 完整流程 < 6s"""
        analyzer = TrajectoryAnalyzer()

        start = time.perf_counter()
        analyzer.load_trade_history(trade_history_50)
        report = analyzer.analyze()
        elapsed = time.perf_counter() - start

        assert elapsed < 6.0, f"完整轨迹分析流程耗时 {elapsed:.2f}s，超过 6s 阈值"
        print(f"\n  TrajectoryAnalyzer 完整流程(50笔): {elapsed:.3f}s")


class TestMemoryUsage:
    """内存使用基准测试"""

    def test_indicator_engine_memory_120_rows(self, ohlcv_120: pd.DataFrame):
        """
        IndicatorEngine.compute_all() 内存增量 < 50 MB

        使用 tracemalloc 追踪 compute_all() 执行期间的峰值内存。
        """
        tracemalloc.start()
        # 记录基线
        engine = IndicatorEngine(ohlcv_120)
        baseline = tracemalloc.get_traced_memory()[0]

        # 执行计算
        result = engine.compute_all()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        delta_mb = (peak - baseline) / (1024 * 1024)
        assert delta_mb < 50.0, f"IndicatorEngine 内存增量 {delta_mb:.1f} MB，超过 50 MB 阈值"
        print(f"\n  IndicatorEngine 内存增量(120行): {delta_mb:.2f} MB")

    def test_indicator_engine_memory_500_rows(self, ohlcv_500: pd.DataFrame):
        """IndicatorEngine.compute_all() 500 行内存增量 < 100 MB"""
        tracemalloc.start()
        engine = IndicatorEngine(ohlcv_500)
        baseline = tracemalloc.get_traced_memory()[0]

        result = engine.compute_all()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        delta_mb = (peak - baseline) / (1024 * 1024)
        assert delta_mb < 100.0, f"IndicatorEngine 内存增量(500行) {delta_mb:.1f} MB，超过 100 MB 阈值"
        print(f"\n  IndicatorEngine 内存增量(500行): {delta_mb:.2f} MB")


class TestEndToEndIndicatorPipeline:
    """端到端指标计算 → 分析管线性能"""

    def test_indicators_then_consensus(self, ohlcv_200: pd.DataFrame):
        """
        指标计算 + 多指标共识 < 3s

        模拟实盘场景：先 compute_all()，再 consensus()。
        """
        start = time.perf_counter()
        engine = IndicatorEngine(ohlcv_200)
        df = engine.compute_all()
        result = MultiIndicatorConsensus.consensus(df)
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0, f"指标+共识管线耗时 {elapsed:.2f}s，超过 3s 阈值"
        assert "state" in result
        print(f"\n  指标+共识管线(200行): {elapsed:.3f}s, state={result['state']}")

    def test_indicators_then_phase_detect(self, ohlcv_200: pd.DataFrame):
        """指标计算 + 趋势阶段检测 < 3s"""
        start = time.perf_counter()
        engine = IndicatorEngine(ohlcv_200)
        df = engine.compute_all()
        phase, conf, rel, bd, alerts, ev = TrendPhaseDetector.detect(df, "trending")
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0, f"指标+阶段检测管线耗时 {elapsed:.2f}s，超过 3s 阈值"
        assert phase in TrendPhaseDetector.PHASES
        print(f"\n  指标+阶段检测管线(200行): {elapsed:.3f}s, phase={phase}")

    def test_full_indicator_pipeline_500_rows(self, ohlcv_500: pd.DataFrame):
        """500 行：指标 → 共识 → 阶段检测 < 10s"""
        start = time.perf_counter()
        engine = IndicatorEngine(ohlcv_500)
        df = engine.compute_all()
        consensus = MultiIndicatorConsensus.consensus(df)
        phase, conf, rel, bd, alerts, ev = TrendPhaseDetector.detect(df, "trending")
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0, f"完整管线(500行)耗时 {elapsed:.2f}s，超过 10s 阈值"
        print(f"\n  完整管线(500行): {elapsed:.3f}s")


# ╔═══════════════════════════════════════════════════════════╗
# ║  原有模块性能测试（保留向后兼容）                           ║
# ╚═══════════════════════════════════════════════════════════╝


class TestFactorGeneratorPerformance:
    """Phase 1: 因子生成器性能"""

    def test_generate_factor_rule_mode(self):
        """因子生成（规则模式）< 5s

        注意：FactorGenerator 要求 LLM 客户端，无 LLM 时测试初始化耗时
        """
        start = time.time()
        try:
            # 尝试从环境变量创建 LLM 客户端
            import os

            from scripts.trend_scanner.llm_factor_client import create_llm_client

            llm_client = None
            if os.getenv("LLM_API_KEY"):
                try:
                    llm_client = create_llm_client("workbuddy")
                except Exception:
                    pass

            gen = FactorGenerator(llm_client=llm_client)
            result = gen.generate_factor("焦煤市场处于上升趋势，安全检查限产")
            elapsed = time.time() - start
            assert elapsed < 5.0, f"因子生成耗时 {elapsed:.2f}s，超过 5s 阈值"
        except ValueError as e:
            # 无 LLM 客户端时，验证初始化本身 < 2s
            elapsed = time.time() - start
            assert elapsed < 2.0, f"因子生成器初始化耗时 {elapsed:.2f}s，超过 2s 阈值"
            pytest.skip(f"无 LLM 客户端，跳过因子生成性能测试: {e}")
        print(f"\n因子生成耗时: {elapsed:.3f}s")


class TestTrajectoryAnalyzerPerformance:
    """Phase 2: 轨迹分析器性能"""

    def test_analyze_100_trades(self):
        """100 笔交易轨迹分析 < 10s"""
        records = generate_trade_records(100)
        analyzer = TrajectoryAnalyzer()
        analyzer.load_trade_history(records)

        start = time.time()
        report = analyzer.analyze()
        elapsed = time.time() - start

        assert elapsed < 10.0, f"轨迹分析耗时 {elapsed:.2f}s，超过 10s 阈值"
        assert report["summary"]["total_trades"] == 100
        print(f"\n100 笔交易轨迹分析耗时: {elapsed:.3f}s")

    def test_analyze_1000_trades(self):
        """1000 笔交易轨迹分析 < 30s"""
        records = generate_trade_records(1000)
        analyzer = TrajectoryAnalyzer()
        analyzer.load_trade_history(records)

        start = time.time()
        report = analyzer.analyze()
        elapsed = time.time() - start

        assert elapsed < 30.0, f"1000 笔交易轨迹分析耗时 {elapsed:.2f}s，超过 30s 阈值"
        assert report["summary"]["total_trades"] == 1000
        print(f"\n1000 笔交易轨迹分析耗时: {elapsed:.3f}s")


class TestReportParserPerformance:
    """Phase 3: 研报解析器性能"""

    def test_parse_report_rule_mode(self):
        """研报解析（规则模式）< 3s"""
        parser = ReportParser()

        content = """焦煤市场分析报告

核心观点：安全检查限产导致供应收紧，焦煤价格有支撑。
主要观点：港口库存处于低位，补库需求存在。

数据逻辑：
- 焦煤矿开工率为65%，同比下降10个百分点
- 焦化利润为300元/吨，处于年内高位
- 港口库存为150万吨，处于近三年低位

逻辑链：限产 → 供应收紧 → 库存下降 → 价格上涨
"""
        metadata = {"source": "benchmark", "title": "性能测试研报"}

        start = time.time()
        analysis = parser.parse_report(content, metadata)
        elapsed = time.time() - start

        assert elapsed < 3.0, f"研报解析耗时 {elapsed:.2f}s，超过 3s 阈值"
        print(f"\n研报解析耗时: {elapsed:.3f}s")


class TestConceptualFeedbackPerformance:
    """Phase 4: 概念反馈生成器性能"""

    def test_generate_feedback(self):
        """概念反馈生成 < 2s"""
        gen = ConceptualFeedbackGenerator()
        trade = TradeResult(
            trade_id="T001",
            symbol="DCE.jm2609",
            direction="LONG",
            entry_price=1500.0,
            exit_price=1560.0,
            pnl=60.0,
            pnl_percent=4.0,
            holding_period=2,
            market_state="trending",
            trend_phase="DEVELOPING",
            entry_reason="动量突破信号",
            exit_reason="达到目标止盈位",
            success_factors=["趋势确立", "成交量配合"],
            failure_factors=[],
        )

        start = time.time()
        feedback = gen.generate_feedback(trade)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"概念反馈生成耗时 {elapsed:.2f}s，超过 2s 阈值"
        print(f"\n概念反馈生成耗时: {elapsed:.3f}s")


class TestRLInterfaceDesignerPerformance:
    """Phase 5: RL 接口设计器性能"""

    def test_design_interface_rule_mode(self):
        """RL 接口设计（规则模式）< 5s"""
        designer = RLInterfaceDesigner()

        start = time.time()
        design = designer.design_interface(
            market_context="焦煤市场处于上升趋势",
            trading_objective="捕捉趋势机会，控制回撤在 10% 以内",
            available_data=["close", "volume", "high", "low", "open"],
            risk_rules={"max_drawdown": 0.10, "position_limit": 0.3},
        )
        elapsed = time.time() - start

        assert elapsed < 5.0, f"RL 接口设计耗时 {elapsed:.2f}s，超过 5s 阈值"
        assert design["state_space"]["dimension"] > 0
        print(f"\nRL 接口设计耗时: {elapsed:.3f}s")

    def test_refine_interface(self):
        """RL 接口诊断修正 < 5s"""
        designer = RLInterfaceDesigner()
        design = designer.design_interface(
            market_context="测试市场",
            trading_objective="测试目标",
            available_data=["close", "volume"],
            risk_rules={"max_drawdown": 0.10},
        )

        start = time.time()
        refinement = designer.refine_interface(
            current_design=design,
            training_metrics={"sharpe": 0.5, "max_drawdown": 0.15, "win_rate": 0.45},
            expected_metrics={"sharpe": 1.0, "max_drawdown": 0.10, "win_rate": 0.55},
        )
        elapsed = time.time() - start

        assert elapsed < 5.0, f"RL 接口诊断修正耗时 {elapsed:.2f}s，超过 5s 阈值"
        print(f"\nRL 接口诊断修正耗时: {elapsed:.3f}s")


class TestFullPipelinePerformance:
    """端到端全流程性能"""

    def test_full_pipeline_100_trades(self):
        """完整流程（100 笔交易）< 30s"""
        start_total = time.time()

        # Phase 3: 研报解析
        parser = ReportParser()
        t0 = time.time()
        analysis = parser.parse_report(
            "核心观点：安全检查限产导致供应收紧，焦煤价格有支撑。数据逻辑：焦煤矿开工率为65%。", {"source": "benchmark"}
        )
        t_report = time.time() - t0

        # Phase 2: 轨迹分析
        analyzer = TrajectoryAnalyzer()
        analyzer.load_trade_history(generate_trade_records(100))
        t0 = time.time()
        trajectory = analyzer.analyze()
        t_trajectory = time.time() - t0

        # Phase 4: 概念反馈
        gen = ConceptualFeedbackGenerator()
        trade = TradeResult(
            trade_id="T001",
            symbol="DCE.jm2609",
            direction="LONG",
            entry_price=1500.0,
            exit_price=1560.0,
            pnl=60.0,
            pnl_percent=4.0,
            holding_period=2,
            market_state="trending",
            trend_phase="DEVELOPING",
            entry_reason="动量突破",
            exit_reason="止盈",
            success_factors=["趋势确立"],
            failure_factors=[],
        )
        t0 = time.time()
        feedback = gen.generate_feedback(trade)
        t_feedback = time.time() - t0

        # Phase 5: RL 接口设计
        designer = RLInterfaceDesigner()
        t0 = time.time()
        rl_design = designer.design_interface(
            market_context="测试市场",
            trading_objective="捕捉趋势",
            available_data=["close", "volume"],
            risk_rules={"max_drawdown": 0.10},
        )
        t_rl = time.time() - t0

        elapsed_total = time.time() - start_total

        assert elapsed_total < 30.0, f"完整流程耗时 {elapsed_total:.2f}s，超过 30s 阈值"
        print("\n=== 完整流程性能 ===")
        print(f"  研报解析: {t_report:.3f}s")
        print(f"  轨迹分析(100笔): {t_trajectory:.3f}s")
        print(f"  概念反馈: {t_feedback:.3f}s")
        print(f"  RL 接口设计: {t_rl:.3f}s")
        print(f"  总耗时: {elapsed_total:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
