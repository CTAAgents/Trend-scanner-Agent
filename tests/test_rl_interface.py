"""
RL 接口设计单元测试

测试状态空间设计、奖励函数设计、诊断引导修正的功能。

版本：v1.0
创建日期：2026-06-15
"""

import pytest
import json
import os
import sys

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from trend_scanner.rl_interface_designer import (
    RLInterfaceDesigner, StateSpaceDesigner, RewardFunctionDesigner, DiagnosticRefiner,
    StateFeature, RewardComponent, StateSpaceDesign, RewardFunctionDesign,
    DiagnosticResult, RefinementAction
)


class TestStateSpaceDesigner:
    """状态空间设计器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.designer = StateSpaceDesigner()
    
    def test_design_state_space_with_rules(self):
        """测试使用规则设计状态空间"""
        market_context = "焦煤市场处于上升趋势"
        trading_objective = "捕捉趋势机会"
        available_data = ['close', 'volume', 'high', 'low', 'open']
        
        design = self.designer.design_state_space(
            market_context, trading_objective, available_data
        )
        
        assert isinstance(design, StateSpaceDesign)
        assert design.dimension > 0
        assert len(design.features) > 0
        assert design.market_context == market_context
    
    def test_design_state_space_features(self):
        """测试状态空间特征"""
        market_context = "焦煤市场处于上升趋势"
        trading_objective = "捕捉趋势机会"
        available_data = ['close', 'volume']
        
        design = self.designer.design_state_space(
            market_context, trading_objective, available_data
        )
        
        # 检查特征
        for feature in design.features:
            assert isinstance(feature, StateFeature)
            assert feature.feature_id != ''
            assert feature.name != ''
            assert feature.description != ''
            assert feature.feature_type in ['price', 'volume', 'technical', 'fundamental']
            assert feature.normalization in ['min-max', 'z-score', 'none']
            assert 0 <= feature.importance <= 1
    
    def test_design_state_space_without_volume(self):
        """测试没有成交量数据的状态空间设计"""
        market_context = "焦煤市场处于上升趋势"
        trading_objective = "捕捉趋势机会"
        available_data = ['close', 'high', 'low', 'open']
        
        design = self.designer.design_state_space(
            market_context, trading_objective, available_data
        )
        
        assert isinstance(design, StateSpaceDesign)
        # 不应该有成交量特征
        volume_features = [f for f in design.features if f.feature_type == 'volume']
        assert len(volume_features) == 0


class TestRewardFunctionDesigner:
    """奖励函数设计器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.designer = RewardFunctionDesigner()
    
    def test_design_reward_function_with_rules(self):
        """测试使用规则设计奖励函数"""
        trading_objective = "捕捉趋势机会，控制回撤在 10% 以内"
        risk_rules = {
            'max_drawdown': 0.1,
            'position_limit': 0.2,
            'stop_loss': 0.05
        }
        market_context = "焦煤市场处于上升趋势"
        
        design = self.designer.design_reward_function(
            trading_objective, risk_rules, market_context
        )
        
        assert isinstance(design, RewardFunctionDesign)
        assert len(design.components) > 0
        assert design.total_weight > 0
        assert design.risk_rules == risk_rules
    
    def test_design_reward_function_components(self):
        """测试奖励函数组件"""
        trading_objective = "捕捉趋势机会"
        risk_rules = {'max_drawdown': 0.1}
        market_context = "焦煤市场处于上升趋势"
        
        design = self.designer.design_reward_function(
            trading_objective, risk_rules, market_context
        )
        
        # 检查组件
        for component in design.components:
            assert isinstance(component, RewardComponent)
            assert component.component_id != ''
            assert component.name != ''
            assert component.description != ''
            assert 0 <= component.weight <= 1
            assert component.computation != ''
    
    def test_design_reward_function_weights(self):
        """测试奖励函数权重"""
        trading_objective = "捕捉趋势机会"
        risk_rules = {'max_drawdown': 0.1}
        market_context = "焦煤市场处于上升趋势"
        
        design = self.designer.design_reward_function(
            trading_objective, risk_rules, market_context
        )
        
        # 权重总和应该接近 1
        total_weight = sum(c.weight for c in design.components)
        assert abs(total_weight - 1.0) < 0.1  # 允许小误差


class TestDiagnosticRefiner:
    """诊断引导修正器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.refiner = DiagnosticRefiner()
    
    def test_collect_diagnostics(self):
        """测试收集诊断结果"""
        training_metrics = {
            'reward_mean': 0.5,
            'episode_length': 100,
            'loss': 0.1
        }
        expected_metrics = {
            'reward_mean': [0.3, 0.7],
            'episode_length': [50, 150],
            'loss': [0.01, 0.2]
        }
        
        diagnostics = self.refiner.collect_diagnostics(
            training_metrics, expected_metrics
        )
        
        assert len(diagnostics) == 3
        for diagnostic in diagnostics:
            assert isinstance(diagnostic, DiagnosticResult)
            assert diagnostic.status in ['good', 'warning', 'critical', 'unknown']
    
    def test_collect_diagnostics_with_warning(self):
        """测试收集诊断结果（警告）"""
        training_metrics = {
            'reward_mean': 0.2,  # 低于预期范围
            'episode_length': 100
        }
        expected_metrics = {
            'reward_mean': [0.3, 0.7],
            'episode_length': [50, 150]
        }
        
        diagnostics = self.refiner.collect_diagnostics(
            training_metrics, expected_metrics
        )
        
        # reward_mean 应该有警告
        reward_diag = next(d for d in diagnostics if d.metric_name == 'reward_mean')
        assert reward_diag.status == 'warning'
    
    def test_suggest_refinements(self):
        """测试建议修正方案"""
        diagnostics = [
            DiagnosticResult(
                diagnostic_id='diag_1',
                metric_name='reward_mean',
                current_value=0.2,
                expected_range=[0.3, 0.7],
                status='warning',
                suggestion='指标偏低，建议调整'
            )
        ]
        current_design = {}
        
        actions = self.refiner.suggest_refinements(diagnostics, current_design)
        
        assert len(actions) > 0
        for action in actions:
            assert isinstance(action, RefinementAction)
            assert action.target in ['state_space', 'reward_function']
            assert action.action_type in ['add', 'remove', 'modify']
            assert action.priority in ['high', 'medium', 'low']


class TestRLInterfaceDesigner:
    """RL 接口设计器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.designer = RLInterfaceDesigner()
    
    def test_design_interface(self):
        """测试设计 RL 接口"""
        market_context = "焦煤市场处于上升趋势"
        trading_objective = "捕捉趋势机会，控制回撤在 10% 以内"
        available_data = ['close', 'volume', 'high', 'low', 'open']
        risk_rules = {
            'max_drawdown': 0.1,
            'position_limit': 0.2,
            'stop_loss': 0.05
        }
        
        interface = self.designer.design_interface(
            market_context, trading_objective, available_data, risk_rules
        )
        
        assert 'state_space' in interface
        assert 'reward_function' in interface
        assert 'metadata' in interface
        
        # 检查状态空间
        state_space = interface['state_space']
        assert 'features' in state_space
        assert len(state_space['features']) > 0
        
        # 检查奖励函数
        reward_function = interface['reward_function']
        assert 'components' in reward_function
        assert len(reward_function['components']) > 0
        
        # 检查元数据
        metadata = interface['metadata']
        assert metadata['market_context'] == market_context
        assert metadata['trading_objective'] == trading_objective
        assert metadata['available_data'] == available_data
        assert metadata['risk_rules'] == risk_rules
    
    def test_refine_interface(self):
        """测试修正 RL 接口"""
        # 当前设计
        current_design = {
            'state_space': {'features': []},
            'reward_function': {'components': []}
        }
        
        # 训练指标
        training_metrics = {
            'reward_mean': 0.2,
            'episode_length': 100
        }
        
        # 预期指标
        expected_metrics = {
            'reward_mean': [0.3, 0.7],
            'episode_length': [50, 150]
        }
        
        refinement = self.designer.refine_interface(
            current_design, training_metrics, expected_metrics
        )
        
        assert 'diagnostics' in refinement
        assert 'refinement_actions' in refinement
        assert 'summary' in refinement
        
        # 检查诊断结果
        assert len(refinement['diagnostics']) > 0
        
        # 检查摘要
        summary = refinement['summary']
        assert 'total_diagnostics' in summary
        assert 'warnings' in summary
        assert 'critical' in summary
        assert 'actions_suggested' in summary


class TestStateFeature:
    """状态特征测试"""
    
    def test_create_state_feature(self):
        """测试创建状态特征"""
        feature = StateFeature(
            feature_id='feature_001',
            name='价格动量',
            description='价格变化率',
            feature_type='price',
            computation='close.pct_change(5)',
            normalization='z-score',
            importance=0.8
        )
        
        assert feature.feature_id == 'feature_001'
        assert feature.name == '价格动量'
        assert feature.description == '价格变化率'
        assert feature.feature_type == 'price'
        assert feature.computation == 'close.pct_change(5)'
        assert feature.normalization == 'z-score'
        assert feature.importance == 0.8


class TestRewardComponent:
    """奖励组件测试"""
    
    def test_create_reward_component(self):
        """测试创建奖励组件"""
        component = RewardComponent(
            component_id='component_001',
            name='收益组件',
            description='基于交易收益的奖励',
            weight=0.5,
            computation='pnl_percent',
            risk_adjusted=True
        )
        
        assert component.component_id == 'component_001'
        assert component.name == '收益组件'
        assert component.description == '基于交易收益的奖励'
        assert component.weight == 0.5
        assert component.computation == 'pnl_percent'
        assert component.risk_adjusted == True


class TestDiagnosticResult:
    """诊断结果测试"""
    
    def test_create_diagnostic_result(self):
        """测试创建诊断结果"""
        diagnostic = DiagnosticResult(
            diagnostic_id='diag_001',
            metric_name='reward_mean',
            current_value=0.5,
            expected_range=[0.3, 0.7],
            status='good',
            suggestion='指标正常'
        )
        
        assert diagnostic.diagnostic_id == 'diag_001'
        assert diagnostic.metric_name == 'reward_mean'
        assert diagnostic.current_value == 0.5
        assert diagnostic.expected_range == [0.3, 0.7]
        assert diagnostic.status == 'good'
        assert diagnostic.suggestion == '指标正常'


class TestRefinementAction:
    """修正动作测试"""
    
    def test_create_refinement_action(self):
        """测试创建修正动作"""
        action = RefinementAction(
            action_id='action_001',
            target='reward_function',
            action_type='modify',
            description='调整奖励函数的权重',
            parameters={'component': '收益组件', 'adjustment': '增加权重'},
            priority='high'
        )
        
        assert action.action_id == 'action_001'
        assert action.target == 'reward_function'
        assert action.action_type == 'modify'
        assert action.description == '调整奖励函数的权重'
        assert action.parameters == {'component': '收益组件', 'adjustment': '增加权重'}
        assert action.priority == 'high'


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
