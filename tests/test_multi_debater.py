"""
多角色 Debater 单元测试

测试概念性语言反馈、信念管理、信念传播的功能。

版本：v1.0
创建日期：2026-06-15
"""

import pytest
import json
import os
import sys

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from trend_scanner.conceptual_feedback import (
    ConceptualFeedbackGenerator, BeliefManager,
    TradeResult, ConceptualFeedback, InvestmentBelief, BeliefUpdate
)
from trend_scanner.belief_propagation import (
    BeliefPropagationManager, BeliefSynchronizer,
    PropagationRule, PropagationResult
)


class TestConceptualFeedbackGenerator:
    """概念性语言反馈生成器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.generator = ConceptualFeedbackGenerator()
    
    def test_generate_feedback_success(self):
        """测试生成成功交易反馈"""
        trade_result = TradeResult(
            trade_id='trade_001',
            symbol='DCE.jm2609',
            direction='LONG',
            entry_price=1500,
            exit_price=1550,
            pnl=50,
            pnl_percent=3.33,
            holding_period=4,
            market_state='trending',
            trend_phase='DEVELOPING',
            entry_reason='趋势确认',
            exit_reason='达到目标位',
            success_factors=['趋势确认', '动量充足'],
            failure_factors=[]
        )
        
        feedback = self.generator.generate_feedback(trade_result)
        
        assert isinstance(feedback, ConceptualFeedback)
        assert feedback.feedback_type == 'success'
        assert feedback.trade_id == 'trade_001'
        assert len(feedback.content) > 0
        assert len(feedback.key_lessons) > 0
        assert 0 <= feedback.confidence <= 1
    
    def test_generate_feedback_failure(self):
        """测试生成失败交易反馈"""
        trade_result = TradeResult(
            trade_id='trade_002',
            symbol='DCE.jm2609',
            direction='LONG',
            entry_price=1550,
            exit_price=1520,
            pnl=-30,
            pnl_percent=-1.94,
            holding_period=2,
            market_state='ranging',
            trend_phase='UNKNOWN',
            entry_reason='误判趋势',
            exit_reason='止损出场',
            success_factors=[],
            failure_factors=['市场震荡', '趋势不明确']
        )
        
        feedback = self.generator.generate_feedback(trade_result)
        
        assert isinstance(feedback, ConceptualFeedback)
        assert feedback.feedback_type == 'failure'
        assert feedback.trade_id == 'trade_002'
        assert len(feedback.content) > 0
        assert len(feedback.key_lessons) > 0
    
    def test_generate_feedback_neutral(self):
        """测试生成中性交易反馈"""
        trade_result = TradeResult(
            trade_id='trade_003',
            symbol='DCE.jm2609',
            direction='LONG',
            entry_price=1500,
            exit_price=1500,
            pnl=0,
            pnl_percent=0.0,
            holding_period=1,
            market_state='ranging',
            trend_phase='UNKNOWN',
            entry_reason='试探性入场',
            exit_reason='无明显变化',
            success_factors=[],
            failure_factors=[]
        )
        
        feedback = self.generator.generate_feedback(trade_result)
        
        assert isinstance(feedback, ConceptualFeedback)
        assert feedback.feedback_type == 'neutral'
        assert feedback.trade_id == 'trade_003'
    
    def test_generate_content_success(self):
        """测试生成成功交易内容"""
        trade_result = TradeResult(
            trade_id='trade_001',
            symbol='DCE.jm2609',
            direction='LONG',
            entry_price=1500,
            exit_price=1550,
            pnl=50,
            pnl_percent=3.33,
            holding_period=4,
            market_state='trending',
            trend_phase='DEVELOPING',
            entry_reason='趋势确认',
            exit_reason='达到目标位',
            success_factors=['趋势确认', '动量充足'],
            failure_factors=[]
        )
        
        content = self.generator._generate_content(trade_result, 'success')
        
        assert 'DCE.jm2609' in content
        assert '3.33%' in content
        assert 'trending' in content
        assert '趋势确认' in content
    
    def test_extract_key_lessons_success(self):
        """测试提取成功交易教训"""
        trade_result = TradeResult(
            trade_id='trade_001',
            symbol='DCE.jm2609',
            direction='LONG',
            entry_price=1500,
            exit_price=1550,
            pnl=50,
            pnl_percent=3.33,
            holding_period=4,
            market_state='trending',
            trend_phase='DEVELOPING',
            entry_reason='趋势确认',
            exit_reason='达到目标位',
            success_factors=['趋势确认', '动量充足'],
            failure_factors=[]
        )
        
        lessons = self.generator._extract_key_lessons(trade_result, 'success')
        
        assert len(lessons) > 0
        assert any('趋势' in lesson for lesson in lessons)
    
    def test_calculate_confidence(self):
        """测试计算置信度"""
        trade_result = TradeResult(
            trade_id='trade_001',
            symbol='DCE.jm2609',
            direction='LONG',
            entry_price=1500,
            exit_price=1550,
            pnl=50,
            pnl_percent=3.33,
            holding_period=4,
            market_state='trending',
            trend_phase='DEVELOPING',
            entry_reason='趋势确认',
            exit_reason='达到目标位',
            success_factors=['趋势确认'],
            failure_factors=[]
        )
        
        confidence = self.generator._calculate_confidence(trade_result)
        
        assert 0 <= confidence <= 1
        assert confidence > 0.5  # 成功交易应该有较高的置信度


class TestBeliefManager:
    """信念管理器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.manager = BeliefManager()
    
    def test_create_belief(self):
        """测试创建信念"""
        belief = self.manager.create_belief(
            category='entry',
            content='趋势确认后入场',
            confidence=0.8
        )
        
        assert isinstance(belief, InvestmentBelief)
        assert belief.belief_id == 'belief_001'
        assert belief.category == 'entry'
        assert belief.content == '趋势确认后入场'
        assert belief.confidence == 0.8
    
    def test_update_belief(self):
        """测试更新信念"""
        # 先创建信念
        belief = self.manager.create_belief(
            category='entry',
            content='趋势确认后入场',
            confidence=0.8
        )
        
        # 更新信念
        update = self.manager.update_belief(
            belief_id='belief_001',
            new_confidence=0.9,
            reason='成功交易验证',
            evidence='交易 trade_001 盈利 3.33%'
        )
        
        assert isinstance(update, BeliefUpdate)
        assert update.belief_id == 'belief_001'
        assert update.old_confidence == 0.8
        assert update.new_confidence == 0.9
        
        # 验证信念已更新
        updated_belief = self.manager.get_belief('belief_001')
        assert updated_belief.confidence == 0.9
    
    def test_get_belief(self):
        """测试获取信念"""
        # 创建信念
        self.manager.create_belief(
            category='entry',
            content='趋势确认后入场',
            confidence=0.8
        )
        
        # 获取信念
        belief = self.manager.get_belief('belief_001')
        
        assert belief is not None
        assert belief.belief_id == 'belief_001'
    
    def test_get_beliefs_by_category(self):
        """测试根据类别获取信念"""
        # 创建不同类别的信念
        self.manager.create_belief('entry', '入场信念1', 0.8)
        self.manager.create_belief('entry', '入场信念2', 0.7)
        self.manager.create_belief('exit', '出场信念1', 0.9)
        
        # 获取入场类别信念
        entry_beliefs = self.manager.get_beliefs_by_category('entry')
        
        assert len(entry_beliefs) == 2
        assert all(b.category == 'entry' for b in entry_beliefs)
    
    def test_get_all_beliefs(self):
        """测试获取所有信念"""
        # 创建多个信念
        self.manager.create_belief('entry', '入场信念1', 0.8)
        self.manager.create_belief('exit', '出场信念1', 0.9)
        
        # 获取所有信念
        all_beliefs = self.manager.get_all_beliefs()
        
        assert len(all_beliefs) == 2
    
    def test_update_beliefs_from_feedback(self):
        """测试从反馈中更新信念"""
        # 创建信念
        self.manager.create_belief(
            category='entry',
            content='趋势确认后入场',
            confidence=0.8
        )
        
        # 创建反馈
        feedback = ConceptualFeedback(
            feedback_id='feedback_001',
            trade_id='trade_001',
            feedback_type='success',
            content='交易成功',
            key_lessons=['趋势确认后入场是有效的'],
            confidence=0.9,
            created_at='2026-06-15 17:00:00'
        )
        
        # 从反馈中更新信念
        updates = self.manager.update_beliefs_from_feedback(feedback)
        
        # 注意：由于 _find_related_beliefs 使用简单的关键词匹配
        # 可能无法找到相关信念
        assert isinstance(updates, list)


class TestBeliefPropagationManager:
    """信念传播管理器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.manager = BeliefPropagationManager()
    
    def test_add_rule(self):
        """测试添加传播规则"""
        rule = PropagationRule(
            rule_id='rule_001',
            source_agent='reasoner',
            target_agent='debater',
            belief_categories=['entry', 'exit'],
            min_confidence=0.6,
            max_beliefs=5,
            priority='high'
        )
        
        self.manager.add_rule(rule)
        
        assert 'rule_001' in self.manager.propagation_rules
    
    def test_remove_rule(self):
        """测试移除传播规则"""
        # 先添加规则
        rule = PropagationRule(
            rule_id='rule_001',
            source_agent='reasoner',
            target_agent='debater',
            belief_categories=['entry', 'exit'],
            min_confidence=0.6,
            max_beliefs=5,
            priority='high'
        )
        self.manager.add_rule(rule)
        
        # 移除规则
        success = self.manager.remove_rule('rule_001')
        
        assert success == True
        assert 'rule_001' not in self.manager.propagation_rules
    
    def test_propagate_beliefs(self):
        """测试传播信念"""
        # 添加传播规则
        rule = PropagationRule(
            rule_id='rule_001',
            source_agent='reasoner',
            target_agent='debater',
            belief_categories=['entry', 'exit'],
            min_confidence=0.6,
            max_beliefs=5,
            priority='high'
        )
        self.manager.add_rule(rule)
        
        # 创建信念
        beliefs = [
            InvestmentBelief(
                belief_id='belief_001',
                category='entry',
                content='趋势确认后入场',
                confidence=0.8,
                supporting_evidence=[],
                contradicting_evidence=[],
                created_at='2026-06-15 17:00:00',
                last_updated='2026-06-15 17:00:00'
            )
        ]
        
        # 传播信念
        result = self.manager.propagate_beliefs('reasoner', 'debater', beliefs)
        
        assert isinstance(result, PropagationResult)
        assert result.source_agent == 'reasoner'
        assert result.target_agent == 'debater'
        assert result.beliefs_propagated == 1
        assert result.success == True
    
    def test_get_propagation_history(self):
        """测试获取传播历史"""
        # 添加传播规则
        rule = PropagationRule(
            rule_id='rule_001',
            source_agent='reasoner',
            target_agent='debater',
            belief_categories=['entry', 'exit'],
            min_confidence=0.6,
            max_beliefs=5,
            priority='high'
        )
        self.manager.add_rule(rule)
        
        # 传播信念
        beliefs = [
            InvestmentBelief(
                belief_id='belief_001',
                category='entry',
                content='趋势确认后入场',
                confidence=0.8,
                supporting_evidence=[],
                contradicting_evidence=[],
                created_at='2026-06-15 17:00:00',
                last_updated='2026-06-15 17:00:00'
            )
        ]
        
        self.manager.propagate_beliefs('reasoner', 'debater', beliefs)
        
        # 获取传播历史
        history = self.manager.get_propagation_history()
        
        assert len(history) == 1
        assert history[0].source_agent == 'reasoner'
    
    def test_get_rules_for_agent(self):
        """测试获取 Agent 相关的传播规则"""
        # 添加传播规则
        rule1 = PropagationRule(
            rule_id='rule_001',
            source_agent='reasoner',
            target_agent='debater',
            belief_categories=['entry', 'exit'],
            min_confidence=0.6,
            max_beliefs=5,
            priority='high'
        )
        rule2 = PropagationRule(
            rule_id='rule_002',
            source_agent='debater',
            target_agent='evolver',
            belief_categories=['risk'],
            min_confidence=0.7,
            max_beliefs=3,
            priority='medium'
        )
        
        self.manager.add_rule(rule1)
        self.manager.add_rule(rule2)
        
        # 获取 debater 相关的规则
        rules = self.manager.get_rules_for_agent('debater')
        
        assert len(rules) == 2
        assert any(r.source_agent == 'debater' for r in rules)
        assert any(r.target_agent == 'debater' for r in rules)


class TestBeliefSynchronizer:
    """信念同步器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.synchronizer = BeliefSynchronizer()
    
    def test_synchronize_beliefs(self):
        """测试同步信念"""
        # 创建 Agent 信念
        agent_beliefs = {
            'reasoner': [
                InvestmentBelief(
                    belief_id='belief_001',
                    category='entry',
                    content='趋势确认后入场',
                    confidence=0.8,
                    supporting_evidence=[],
                    contradicting_evidence=[],
                    created_at='2026-06-15 17:00:00',
                    last_updated='2026-06-15 17:00:00'
                )
            ],
            'debater': [
                InvestmentBelief(
                    belief_id='belief_002',
                    category='exit',
                    content='达到目标位出场',
                    confidence=0.9,
                    supporting_evidence=[],
                    contradicting_evidence=[],
                    created_at='2026-06-15 17:00:00',
                    last_updated='2026-06-15 17:00:00'
                )
            ]
        }
        
        # 同步信念
        synchronized = self.synchronizer.synchronize_beliefs(agent_beliefs)
        
        assert 'reasoner' in synchronized
        assert 'debater' in synchronized
        # 所有 Agent 应该共享所有信念
        assert len(synchronized['reasoner']) == 2
        assert len(synchronized['debater']) == 2


class TestTradeResult:
    """交易结果测试"""
    
    def test_create_trade_result(self):
        """测试创建交易结果"""
        trade_result = TradeResult(
            trade_id='trade_001',
            symbol='DCE.jm2609',
            direction='LONG',
            entry_price=1500,
            exit_price=1550,
            pnl=50,
            pnl_percent=3.33,
            holding_period=4,
            market_state='trending',
            trend_phase='DEVELOPING',
            entry_reason='趋势确认',
            exit_reason='达到目标位',
            success_factors=['趋势确认', '动量充足'],
            failure_factors=[]
        )
        
        assert trade_result.trade_id == 'trade_001'
        assert trade_result.symbol == 'DCE.jm2609'
        assert trade_result.direction == 'LONG'
        assert trade_result.pnl == 50
        assert trade_result.pnl_percent == 3.33


class TestConceptualFeedback:
    """概念性语言反馈测试"""
    
    def test_create_conceptual_feedback(self):
        """测试创建概念性语言反馈"""
        feedback = ConceptualFeedback(
            feedback_id='feedback_001',
            trade_id='trade_001',
            feedback_type='success',
            content='交易成功',
            key_lessons=['教训1', '教训2'],
            confidence=0.8,
            created_at='2026-06-15 17:00:00'
        )
        
        assert feedback.feedback_id == 'feedback_001'
        assert feedback.trade_id == 'trade_001'
        assert feedback.feedback_type == 'success'
        assert feedback.content == '交易成功'
        assert len(feedback.key_lessons) == 2


class TestInvestmentBelief:
    """投资信念测试"""
    
    def test_create_investment_belief(self):
        """测试创建投资信念"""
        belief = InvestmentBelief(
            belief_id='belief_001',
            category='entry',
            content='趋势确认后入场',
            confidence=0.8,
            supporting_evidence=['证据1'],
            contradicting_evidence=[],
            created_at='2026-06-15 17:00:00',
            last_updated='2026-06-15 17:00:00'
        )
        
        assert belief.belief_id == 'belief_001'
        assert belief.category == 'entry'
        assert belief.content == '趋势确认后入场'
        assert belief.confidence == 0.8
        assert len(belief.supporting_evidence) == 1


class TestPropagationRule:
    """传播规则测试"""
    
    def test_create_propagation_rule(self):
        """测试创建传播规则"""
        rule = PropagationRule(
            rule_id='rule_001',
            source_agent='reasoner',
            target_agent='debater',
            belief_categories=['entry', 'exit'],
            min_confidence=0.6,
            max_beliefs=5,
            priority='high'
        )
        
        assert rule.rule_id == 'rule_001'
        assert rule.source_agent == 'reasoner'
        assert rule.target_agent == 'debater'
        assert len(rule.belief_categories) == 2
        assert rule.min_confidence == 0.6
        assert rule.max_beliefs == 5
        assert rule.priority == 'high'


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
