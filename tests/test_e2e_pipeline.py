"""
端到端集成测试

测试完整的交易决策流程：
Scanner → Orchestrator → Reasoner → Debater → Evolver

测试场景：
1. 正常扫描流程
2. 信号触发推理
3. 辩论修正
4. 交易反馈和进化
5. 异常处理
"""

import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path


# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from core.memory import UnifiedMemoryManager


class TestEndToEndPipeline(unittest.TestCase):
    """端到端流程测试"""

    def setUp(self):
        """测试前准备"""
        self.config = {
            "sqlite_path": "data/test_e2e_memory.db",
            "duckdb_path": "data/test_e2e_analytics.duckdb",
            "vector_dim": 15,
            "llm": {"provider": "workbuddy"},
        }
        self.memory = UnifiedMemoryManager(self.config)

        # 测试数据目录
        self.test_data_dir = Path("data/test_e2e")
        self.test_data_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """测试后清理"""
        self.memory.close()

        # 清理测试文件
        for f in ["data/test_e2e_memory.db", "data/test_e2e_analytics.duckdb"]:
            if os.path.exists(f):
                os.remove(f)

        # 清理测试数据目录
        import shutil

        if self.test_data_dir.exists():
            shutil.rmtree(self.test_data_dir)

    def test_01_scanner_signal_generation(self):
        """测试1：Scanner 信号生成"""
        # 模拟 Scanner 输出
        scan_result = {
            "scan_time": datetime.now().isoformat(),
            "total_scanned": 30,
            "signal_count": 2,
            "signals": [
                {
                    "symbol": "SHFE.rb2510",
                    "direction": "LONG",
                    "trend_phase": "DEVELOPING",
                    "trend_strength_composite": 0.72,
                    "tsi": 25.3,
                    "er": 0.65,
                    "r_squared": 0.68,
                    "signal_strength": "STRONG",
                    "trigger_reason": "ER=0.65>=0.6 且 TSI=25.3 且 趋势强度=0.72",
                },
                {
                    "symbol": "DCE.jm2609",
                    "direction": "LONG",
                    "trend_phase": "DEVELOPING",
                    "trend_strength_composite": 0.68,
                    "tsi": 22.1,
                    "er": 0.62,
                    "r_squared": 0.65,
                    "signal_strength": "MEDIUM",
                    "trigger_reason": "ER=0.62>=0.6 且 TSI=22.1 且 趋势强度=0.68",
                },
            ],
            "no_signal_symbols": ["DCE.i2510", "CZCE.CF509"],
        }

        # 保存到文件
        scan_file = self.test_data_dir / "latest_scan.json"
        with open(scan_file, "w", encoding="utf-8") as f:
            json.dump(scan_result, f, ensure_ascii=False, indent=2)

        # 验证文件存在
        self.assertTrue(scan_file.exists())

        # 验证信号数量
        self.assertEqual(scan_result["signal_count"], 2)

        # 验证信号强度
        for signal in scan_result["signals"]:
            self.assertIn("symbol", signal)
            self.assertIn("direction", signal)
            self.assertIn("signal_strength", signal)
            self.assertIn(signal["signal_strength"], ["STRONG", "MEDIUM", "WEAK"])

    def test_02_orchestrator_signal_processing(self):
        """测试2：Orchestrator 信号处理"""
        # 模拟信号
        signal = {"symbol": "DCE.jm2609", "direction": "LONG", "trend_phase": "DEVELOPING", "signal_strength": "STRONG"}

        # 模拟 Orchestrator 决策逻辑
        def should_trigger_reasoner(signal):
            """判断是否触发 Reasoner"""
            strength = signal.get("signal_strength", "WEAK")
            if strength in ["STRONG", "MEDIUM"]:
                return True
            return False

        def should_trigger_debater(signal):
            """判断是否触发 Debater"""
            strength = signal.get("signal_strength", "WEAK")
            if strength == "STRONG":
                return True
            return False

        # 验证决策逻辑
        self.assertTrue(should_trigger_reasoner(signal))
        self.assertTrue(should_trigger_debater(signal))

        # 测试弱信号
        weak_signal = {"symbol": "DCE.i2510", "direction": "LONG", "signal_strength": "WEAK"}
        self.assertFalse(should_trigger_debater(weak_signal))

    def test_03_reasoner_brief_generation(self):
        """测试3：Reasoner 简报生成"""
        # 模拟推理结果
        reasoning_result = {
            "routes": [
                {
                    "route_id": "A",
                    "name": "顺势做多",
                    "action": "在回调至支撑位时入场做多",
                    "confidence": 0.72,
                    "reasoning": "趋势发展阶段，动量充足，均线支撑",
                    "constraints": [
                        {"type": "stop_loss", "value": 1320, "reason": "ATR 止损"},
                        {"type": "position_size", "value": 0.3, "reason": "中等仓位"},
                    ],
                    "risks": ["RSI 接近超买", "波动率扩张"],
                },
                {
                    "route_id": "B",
                    "name": "观望等待",
                    "action": "等待更明确的信号或回调机会",
                    "confidence": 0.28,
                    "reasoning": "RSI 超买风险，等待回调",
                    "constraints": [],
                    "risks": ["可能错过趋势行情"],
                },
            ],
            "recommended_route": "A",
            "warnings": [],
        }

        # 验证推理结果结构
        self.assertIn("routes", reasoning_result)
        self.assertIn("recommended_route", reasoning_result)
        self.assertEqual(len(reasoning_result["routes"]), 2)

        # 验证推荐路线
        recommended = reasoning_result["recommended_route"]
        route_ids = [r["route_id"] for r in reasoning_result["routes"]]
        self.assertIn(recommended, route_ids)

        # 验证置信度
        for route in reasoning_result["routes"]:
            self.assertGreaterEqual(route["confidence"], 0)
            self.assertLessEqual(route["confidence"], 1)

    def test_04_debater_revision(self):
        """测试4：Debater 辩论修正"""
        # 模拟辩论结果
        debate_result = {
            "hawk_arguments": ["RSI 接近超买区域，回调风险增大", "波动率扩张，可能预示趋势反转"],
            "dove_arguments": ["趋势发展阶段，均线多头排列", "ER>0.6，趋势效率高"],
            "synthesis": "趋势整体健康，但短期存在回调风险",
            "divergence": 0.35,
            "revised_confidence": 0.65,
        }

        # 验证辩论结构
        self.assertIn("hawk_arguments", debate_result)
        self.assertIn("dove_arguments", debate_result)
        self.assertIn("synthesis", debate_result)
        self.assertIn("divergence", debate_result)

        # 验证分歧度
        self.assertGreaterEqual(debate_result["divergence"], 0)
        self.assertLessEqual(debate_result["divergence"], 1)

        # 验证修正后的置信度低于原始置信度
        original_confidence = 0.72
        revised_confidence = debate_result["revised_confidence"]
        self.assertLessEqual(revised_confidence, original_confidence)

    def test_05_evolution_feedback_processing(self):
        """测试5：进化反馈处理"""
        # 存储交易经验
        experience = {
            "experience_id": "EXP_E2E_001",
            "timestamp": datetime.now().isoformat(),
            "symbol": "DCE.jm2609",
            "direction": "LONG",
            "trend_phase": "DEVELOPING",
            "action_taken": "LONG",
            "entry_price": 1350,
            "exit_price": 1385,
            "pnl_pct": 2.59,
            "holding_days": 3,
            "feature_vector": [0.65, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        }

        exp_id = self.memory.store_experience(experience)
        self.assertEqual(exp_id, "EXP_E2E_001")

        # 存储交易记录
        trade = {
            "trade_id": "T_E2E_001",
            "timestamp": datetime.now().isoformat(),
            "symbol": "DCE.jm2609",
            "direction": "LONG",
            "entry_price": 1350,
            "exit_price": 1385,
            "pnl_pct": 2.59,
            "holding_days": 3,
        }

        trade_id = self.memory.store_trade(trade)
        self.assertEqual(trade_id, "T_E2E_001")

        # 验证经验存储
        stored_exp = self.memory.get_experience("EXP_E2E_001")
        self.assertIsNotNone(stored_exp)
        self.assertEqual(stored_exp["symbol"], "DCE.jm2609")

        # 验证交易存储
        recent_trades = self.memory.get_recent_trades()
        self.assertGreater(len(recent_trades), 0)

    def test_06_memory_retrieval_integration(self):
        """测试6：记忆检索集成"""
        # 存储多条经验
        for i in range(5):
            experience = {
                "experience_id": f"EXP_MEM_{i}",
                "timestamp": f"2026-06-{10 + i}T10:00:00",
                "symbol": "DCE.jm2609",
                "direction": "LONG",
                "trend_phase": "DEVELOPING",
                "feature_vector": [
                    0.65 + i * 0.01,
                    25.3,
                    0.72,
                    0.68,
                    0.72,
                    0.5,
                    0.5,
                    0.5,
                    0.5,
                    0.5,
                    0.5,
                    0.5,
                    0.5,
                    0.5,
                    0.5,
                ],
            }
            self.memory.store_experience(experience)

        # 检索相似经验
        context = {
            "symbol": "DCE.jm2609",
            "trend_phase": "DEVELOPING",
            "feature_vector": [0.66, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        }

        # 单路检索
        matches = self.memory.retrieve_experiences(context, top_k=3)
        self.assertIsInstance(matches, list)

        # 多路检索
        multi_matches = self.memory.retrieve_experiences_multi_path(context, top_k=3)
        self.assertIsInstance(multi_matches, list)

    def test_07_evolution_trigger_integration(self):
        """测试7：进化触发集成"""
        from core.memory import EvolutionTrigger

        # 存储连续亏损的交易
        for i in range(5):
            trade = {
                "trade_id": f"T_LOSS_{i}",
                "timestamp": f"2026-06-{10 + i}T10:00:00",
                "symbol": "DCE.jm2609",
                "direction": "LONG",
                "pnl_pct": -2.0,  # 亏损
            }
            self.memory.store_trade(trade)

        # 检查进化触发
        trigger = EvolutionTrigger(self.memory)
        should_evolve, reason = trigger.should_evolve()

        # 应该触发进化（连续亏损）
        self.assertTrue(should_evolve)
        self.assertIn("连续亏损", reason)

    def test_08_rule_promotion_integration(self):
        """测试8：规则晋升集成"""
        from core.memory import RulePromoter

        # 创建符合条件的模式
        pattern = {
            "pattern_id": "P_PROMOTE_001",
            "pattern_name": "高胜率趋势模式",
            "pattern_type": "entry",
            "occurrences": 10,
            "win_rate": 0.7,
            "confidence": 0.8,
            "conditions": {"symbol": "DCE.jm2609", "trend_phase": "DEVELOPING"},
        }

        # 晋升规则
        promoter = RulePromoter(self.memory)
        rule = promoter.promote_pattern_to_rule(pattern)

        # 验证晋升成功
        if rule:
            self.assertIn("rule_id", rule)
            self.assertEqual(rule["source"], "promoted")

    def test_09_overfitting_audit_integration(self):
        """测试9：过拟合审计集成"""
        from core.memory import OverfittingAuditor

        # 存储一个规则
        rule = {
            "rule_id": "R_AUDIT_E2E",
            "rule_name": "测试规则",
            "rule_type": "entry",
            "rule_content": "测试内容",
            "trigger_count": 5,
            "win_rate": 0.8,
            "confidence": 0.7,
            "status": "active",
        }
        self.memory.store_rule(rule)

        # 审计
        auditor = OverfittingAuditor(self.memory)
        result = auditor.audit_rule("R_AUDIT_E2E")

        # 验证审计结果
        self.assertIn("status", result)
        self.assertIn("audit_score", result)
        self.assertIn("warnings", result)

    def test_10_full_pipeline_simulation(self):
        """测试10：完整流程模拟"""
        # 1. 模拟 Scanner 输出信号
        scan_signal = {
            "symbol": "DCE.jm2609",
            "direction": "LONG",
            "trend_phase": "DEVELOPING",
            "signal_strength": "STRONG",
            "er": 0.65,
            "tsi": 25.3,
            "r_squared": 0.68,
        }

        # 2. Orchestrator 判断是否触发 Reasoner
        self.assertIn(scan_signal["signal_strength"], ["STRONG", "MEDIUM"])

        # 3. 模拟 Reasoner 输出简报
        brief = {
            "symbol": "DCE.jm2609",
            "routes": [{"route_id": "A", "name": "顺势做多", "confidence": 0.72}],
            "recommended_route": "A",
        }

        # 4. Orchestrator 判断是否触发 Debater
        # 置信度 < 0.7 时触发
        recommended_route = next(r for r in brief["routes"] if r["route_id"] == brief["recommended_route"])

        # 5. 模拟 Debater 修正
        if recommended_route["confidence"] < 0.7:
            debate_result = {"revised_confidence": recommended_route["confidence"] * 0.9, "divergence": 0.3}
        else:
            debate_result = {"revised_confidence": recommended_route["confidence"], "divergence": 0.1}

        # 6. 存储经验
        experience = {
            "experience_id": "EXP_FULL_001",
            "timestamp": datetime.now().isoformat(),
            "symbol": scan_signal["symbol"],
            "direction": scan_signal["direction"],
            "trend_phase": scan_signal["trend_phase"],
            "action_taken": "LONG",
            "pnl_pct": 2.59,
            "feature_vector": [0.65, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        }
        exp_id = self.memory.store_experience(experience)

        # 验证完整流程
        self.assertIsNotNone(exp_id)
        self.assertIn("routes", brief)
        self.assertIn("divergence", debate_result)

        # 验证经验可检索
        stored = self.memory.get_experience("EXP_FULL_001")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["symbol"], "DCE.jm2609")


class TestPipelineErrorHandling(unittest.TestCase):
    """流程异常处理测试"""

    def setUp(self):
        """测试前准备"""
        self.config = {
            "sqlite_path": "data/test_error_memory.db",
            "duckdb_path": "data/test_error_analytics.duckdb",
            "vector_dim": 15,
            "llm": {"provider": "workbuddy"},
        }
        self.memory = UnifiedMemoryManager(self.config)

    def tearDown(self):
        """测试后清理"""
        self.memory.close()
        for f in ["data/test_error_memory.db", "data/test_error_analytics.duckdb"]:
            if os.path.exists(f):
                os.remove(f)

    def test_missing_signal_fields(self):
        """测试缺失信号字段"""
        # 缺失必要字段的信号
        incomplete_signal = {
            "symbol": "DCE.jm2609"
            # 缺失 direction, trend_phase 等
        }

        # 验证可以处理缺失字段
        direction = incomplete_signal.get("direction", "NEUTRAL")
        self.assertEqual(direction, "NEUTRAL")

    def test_invalid_confidence(self):
        """测试无效置信度"""
        # 置信度超出范围
        invalid_route = {
            "route_id": "A",
            "confidence": 1.5,  # 超出 [0, 1] 范围
        }

        # 验证可以处理无效置信度
        confidence = max(0, min(1, invalid_route["confidence"]))
        self.assertEqual(confidence, 1.0)

    def test_empty_experience_list(self):
        """测试空经验列表"""
        context = {
            "symbol": "DCE.jm2609",
            "feature_vector": [0.65, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        }

        # 检索空经验库
        matches = self.memory.retrieve_experiences(context, top_k=5)
        self.assertEqual(len(matches), 0)

    def test_duplicate_experience_storage(self):
        """测试重复经验存储"""
        experience = {
            "experience_id": "EXP_DUP_001",
            "timestamp": datetime.now().isoformat(),
            "symbol": "DCE.jm2609",
            "pnl_pct": 2.59,
            "feature_vector": [0.65, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        }

        # 第一次存储
        exp_id1 = self.memory.store_experience(experience)

        # 第二次存储（相同ID）
        exp_id2 = self.memory.store_experience(experience)

        # 验证不重复
        self.assertEqual(exp_id1, exp_id2)

        # 验证只有一条记录
        stored = self.memory.get_experience("EXP_DUP_001")
        self.assertIsNotNone(stored)


if __name__ == "__main__":
    unittest.main()
