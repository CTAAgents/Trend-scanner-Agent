"""
自优化记忆系统集成测试

测试内容：
1. UnifiedMemoryManager 初始化
2. 经验存储和检索
3. 规则存储和检索
4. 多路召回检索
5. 进化触发
6. 规则晋升
7. 过拟合审计
8. LLM 调用
"""

import os
import sys
import json
import unittest
from pathlib import Path

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from trend_scanner.memory import (
    UnifiedMemoryManager,
    SQLiteStore,
    DuckDBStore,
    VectorStore,
    LLMProviderFactory,
    MultiPathRetriever,
    SimilarityCalculator,
    EvolutionTrigger,
    RulePromoter,
    OverfittingAuditor,
    StrategyReflector
)


class TestMemorySystem(unittest.TestCase):
    """记忆系统测试"""
    
    def setUp(self):
        """测试前准备"""
        self.config = {
            'sqlite_path': 'data/test_memory.db',
            'duckdb_path': 'data/test_analytics.duckdb',
            'vector_dim': 15,
            'max_experiences': 100,
            'llm': {'provider': 'workbuddy'}
        }
        self.memory = UnifiedMemoryManager(self.config)
    
    def tearDown(self):
        """测试后清理"""
        self.memory.close()
        
        # 清理测试文件
        for f in ['data/test_memory.db', 'data/test_analytics.duckdb']:
            if os.path.exists(f):
                os.remove(f)
    
    def test_01_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.memory.sqlite_store)
        self.assertIsNotNone(self.memory.duckdb_store)
        self.assertIsNotNone(self.memory.vector_store)
        self.assertIsNotNone(self.memory.llm_provider)
        self.assertIsNotNone(self.memory.retriever)
    
    def test_02_store_experience(self):
        """测试存储经验"""
        experience = {
            'experience_id': 'EXP_TEST_001',
            'timestamp': '2026-06-15T10:00:00',
            'symbol': 'DCE.jm2609',
            'direction': 'LONG',
            'trend_phase': 'DEVELOPING',
            'action_taken': 'LONG',
            'entry_price': 1350,
            'exit_price': 1385,
            'pnl_pct': 2.59,
            'holding_days': 3,
            'feature_vector': [0.65, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        }
        
        exp_id = self.memory.store_experience(experience)
        self.assertEqual(exp_id, 'EXP_TEST_001')
        
        # 验证存储
        stored = self.memory.get_experience('EXP_TEST_001')
        self.assertIsNotNone(stored)
        self.assertEqual(stored['symbol'], 'DCE.jm2609')
    
    def test_03_retrieve_experiences(self):
        """测试检索经验"""
        # 先存储一条经验
        experience = {
            'experience_id': 'EXP_TEST_002',
            'timestamp': '2026-06-15T10:00:00',
            'symbol': 'DCE.jm2609',
            'direction': 'LONG',
            'trend_phase': 'DEVELOPING',
            'feature_vector': [0.65, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        }
        self.memory.store_experience(experience)
        
        # 检索
        context = {
            'symbol': 'DCE.jm2609',
            'feature_vector': [0.62, 22.1, 0.68, 0.65, 0.70, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        }
        
        matches = self.memory.retrieve_experiences(context, top_k=5)
        self.assertIsInstance(matches, list)
        self.assertGreater(len(matches), 0)
    
    def test_04_store_rule(self):
        """测试存储规则"""
        rule = {
            'rule_id': 'R_TEST_001',
            'rule_name': '趋势跟踪入场规则',
            'rule_type': 'entry',
            'rule_content': 'ER > 0.6 且 TSI > 20 时入场',
            'status': 'active'
        }
        
        rule_id = self.memory.store_rule(rule)
        self.assertEqual(rule_id, 'R_TEST_001')
        
        # 验证存储
        rules = self.memory.get_active_rules()
        self.assertGreater(len(rules), 0)
    
    def test_05_store_trade(self):
        """测试存储交易"""
        trade = {
            'trade_id': 'T_TEST_001',
            'timestamp': '2026-06-15T10:00:00',
            'symbol': 'DCE.jm2609',
            'direction': 'LONG',
            'entry_price': 1350,
            'exit_price': 1385,
            'pnl_pct': 2.59,
            'holding_days': 3
        }
        
        trade_id = self.memory.store_trade(trade)
        self.assertEqual(trade_id, 'T_TEST_001')
        
        # 验证存储
        trades = self.memory.get_recent_trades()
        self.assertGreater(len(trades), 0)
    
    def test_06_multi_path_retrieval(self):
        """测试多路召回检索"""
        # 先存储经验
        for i in range(5):
            experience = {
                'experience_id': f'EXP_MULTI_{i}',
                'timestamp': f'2026-06-{10+i}T10:00:00',
                'symbol': 'DCE.jm2609',
                'direction': 'LONG',
                'trend_phase': 'DEVELOPING',
                'feature_vector': [0.65 + i*0.01, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
            }
            self.memory.store_experience(experience)
        
        # 多路召回检索
        context = {
            'symbol': 'DCE.jm2609',
            'trend_phase': 'DEVELOPING',
            'feature_vector': [0.66, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        }
        
        matches = self.memory.retrieve_experiences_multi_path(context, top_k=3)
        self.assertIsInstance(matches, list)
    
    def test_07_evolution_trigger(self):
        """测试进化触发"""
        # 存储足够的交易数据
        for i in range(10):
            trade = {
                'trade_id': f'T_EVO_{i}',
                'timestamp': f'2026-06-{5+i}T10:00:00',
                'symbol': 'DCE.jm2609',
                'direction': 'LONG',
                'pnl_pct': -2.0 if i < 5 else 1.0  # 前5笔亏损，后5笔盈利
            }
            self.memory.store_trade(trade)
        
        # 测试进化触发
        trigger = EvolutionTrigger(self.memory)
        should_evolve, reason = trigger.should_evolve()
        
        self.assertIsInstance(should_evolve, bool)
        self.assertIsInstance(reason, str)
    
    def test_08_rule_promoter(self):
        """测试规则晋升"""
        promoter = RulePromoter(self.memory)
        
        # 创建一个符合条件的模式
        pattern = {
            'pattern_id': 'P_TEST_001',
            'pattern_name': '测试模式',
            'pattern_type': 'entry',
            'occurrences': 10,
            'win_rate': 0.7,
            'confidence': 0.8,
            'conditions': {
                'symbol': 'DCE.jm2609',
                'trend_phase': 'DEVELOPING'
            }
        }
        
        rule = promoter.promote_pattern_to_rule(pattern)
        
        # 如果晋升成功，验证规则
        if rule:
            self.assertIn('rule_id', rule)
            self.assertEqual(rule['source'], 'promoted')
    
    def test_09_overfitting_audit(self):
        """测试过拟合审计"""
        # 先存储一个规则
        rule = {
            'rule_id': 'R_AUDIT_001',
            'rule_name': '测试规则',
            'rule_type': 'entry',
            'rule_content': '测试内容',
            'trigger_count': 5,
            'win_rate': 0.8,
            'confidence': 0.7,
            'status': 'active'
        }
        self.memory.store_rule(rule)
        
        # 审计
        auditor = OverfittingAuditor(self.memory)
        result = auditor.audit_rule('R_AUDIT_001')
        
        self.assertIn('status', result)
        self.assertIn('audit_score', result)
        self.assertIn('warnings', result)
    
    def test_10_strategy_reflector(self):
        """测试策略反思"""
        # 先存储交易和经验
        trade = {
            'trade_id': 'T_REFLECT_001',
            'timestamp': '2026-06-15T10:00:00',
            'symbol': 'DCE.jm2609',
            'direction': 'LONG',
            'pnl_pct': 2.59,
            'feature_vector': [0.65, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        }
        self.memory.store_trade(trade)
        
        # 反思
        reflector = StrategyReflector(self.memory)
        analysis = reflector.reflect_on_trade(trade)
        
        self.assertIn('symbol', analysis)
        self.assertIn('lessons', analysis)
    
    def test_11_llm_call(self):
        """测试 LLM 调用"""
        import os
        if not os.getenv("WORKBUDDY_API_KEY"):
            pytest.skip("WORKBUDDY_API_KEY 未设置，跳过 LLM 调用测试")
        
        response = self.memory.llm_generate('测试提示')
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
    
    def test_12_short_term_memory(self):
        """测试短期记忆"""
        self.memory.set_short_term('test_key', 'test_value')
        value = self.memory.get_short_term('test_key')
        self.assertEqual(value, 'test_value')
        
        self.memory.clear_short_term()
        value = self.memory.get_short_term('test_key')
        self.assertIsNone(value)


class TestSimilarityCalculator(unittest.TestCase):
    """相似度计算器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.calc = SimilarityCalculator()
    
    def test_cosine_similarity(self):
        """测试余弦相似度"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = self.calc._cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(similarity, 1.0, places=2)
    
    def test_euclidean_distance(self):
        """测试欧氏距离"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        distance = self.calc._euclidean_distance(vec1, vec2)
        self.assertAlmostEqual(distance, 1.414, places=2)
    
    def test_combined_similarity(self):
        """测试综合相似度"""
        query = {
            'symbol': 'DCE.jm2609',
            'trend_phase': 'DEVELOPING',
            'direction': 'LONG',
            'feature_vector': [0.65, 25.3, 0.72, 0.68, 0.72, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        }
        
        candidate = {
            'symbol': 'DCE.jm2609',
            'trend_phase': 'DEVELOPING',
            'direction': 'LONG',
            'feature_vector': [0.62, 22.1, 0.68, 0.65, 0.70, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        }
        
        similarity = self.calc.calculate(query, candidate)
        self.assertGreater(similarity, 0)
        self.assertLessEqual(similarity, 1)


if __name__ == '__main__':
    unittest.main()
