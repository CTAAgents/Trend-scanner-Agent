"""
研报解析器单元测试

测试研报解析器、验证流水线的功能。

版本：v1.0
创建日期：2026-06-15
"""

import pytest
import json
import os
import sys

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from trend_scanner.report_parser import (
    ReportParser, ValidationPipeline,
    KeyViewpoint, DataLogic, LogicChain, FactorSuggestion, ReportAnalysis
)


class TestReportParser:
    """研报解析器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.parser = ReportParser()
    
    def test_parse_report_with_metadata(self):
        """测试解析研报（带元数据）"""
        report_content = """
        焦煤市场分析报告
        
        当前焦煤市场处于上升趋势，主要受以下因素驱动：
        1. 安全检查限产导致供应收紧
        2. 焦化利润支撑需求
        3. 钢厂补库需求增加
        
        数据显示，焦煤库存处于历史低位，港口库存下降 20%。
        预计短期内价格将继续上涨，目标位 1600 元/吨。
        """
        
        metadata = {
            'report_id': 'report_001',
            'title': '焦煤市场分析报告',
            'source': '测试来源',
            'publish_date': '2026-06-15'
        }
        
        analysis = self.parser.parse_report(report_content, metadata)
        
        assert isinstance(analysis, ReportAnalysis)
        assert analysis.report_id == 'report_001'
        assert analysis.title == '焦煤市场分析报告'
        assert analysis.source == '测试来源'
        assert analysis.publish_date == '2026-06-15'
        assert analysis.raw_content == report_content
    
    def test_parse_report_without_metadata(self):
        """测试解析研报（不带元数据）"""
        report_content = """
        焦煤市场分析报告
        
        当前焦煤市场处于上升趋势，主要受以下因素驱动：
        1. 安全检查限产导致供应收紧
        2. 焦化利润支撑需求
        3. 钢厂补库需求增加
        """
        
        analysis = self.parser.parse_report(report_content)
        
        assert isinstance(analysis, ReportAnalysis)
        assert analysis.report_id == 'unknown'
        assert analysis.title == '未知标题'
        assert analysis.source == '未知来源'
        assert analysis.publish_date == '未知日期'
    
    def test_extract_key_viewpoints(self):
        """测试提取关键观点"""
        content = """
        焦煤市场分析报告
        
        当前焦煤市场处于上升趋势，主要受以下因素驱动：
        1. 安全检查限产导致供应收紧
        2. 焦化利润支撑需求
        3. 钢厂补库需求增加
        
        核心观点：焦煤价格将继续上涨
        """
        
        viewpoints = self.parser._extract_key_viewpoints(content)
        
        # 应该能提取到一些观点
        assert isinstance(viewpoints, list)
    
    def test_extract_data_logic(self):
        """测试提取数据逻辑"""
        content = """
        数据显示，焦煤库存处于历史低位，港口库存下降 20%。
        产量为 1000 万吨，需求为 1200 万吨。
        """
        
        data_logic = self.parser._extract_data_logic(content)
        
        assert isinstance(data_logic, list)
        # 应该能提取到一些数据
        if data_logic:
            assert data_logic[0].metric != ''
            assert data_logic[0].value != ''
    
    def test_extract_logic_chains(self):
        """测试提取逻辑链"""
        content = """
        因为安全检查限产，所以供应收紧。
        由于焦化利润支撑，因此需求增加。
        """
        
        logic_chains = self.parser._extract_logic_chains(content)
        
        assert isinstance(logic_chains, list)
        # 应该能提取到逻辑链
        if logic_chains:
            assert logic_chains[0].cause != ''
            assert logic_chains[0].effect != ''
    
    def test_classify_viewpoint(self):
        """测试分类观点"""
        # 供应相关
        assert self.parser._classify_viewpoint("供应收紧") == 'supply'
        assert self.parser._classify_viewpoint("产量下降") == 'supply'
        
        # 需求相关
        assert self.parser._classify_viewpoint("需求增加") == 'demand'
        assert self.parser._classify_viewpoint("消费上升") == 'demand'
        
        # 政策相关
        assert self.parser._classify_viewpoint("政策支持") == 'policy'
        assert self.parser._classify_viewpoint("限产政策") == 'policy'
        
        # 技术相关
        assert self.parser._classify_viewpoint("技术突破") == 'technical'
        assert self.parser._classify_viewpoint("趋势确认") == 'technical'
        
        # 宏观相关
        assert self.parser._classify_viewpoint("宏观经济") == 'macro'
        assert self.parser._classify_viewpoint("GDP增长") == 'macro'
    
    def test_infer_implication(self):
        """测试推断数据含义"""
        # 库存相关
        implication = self.parser._infer_implication("焦煤库存", "100万吨", "库存处于低位")
        assert "库存" in implication
        
        # 产量相关
        implication = self.parser._infer_implication("焦煤产量", "1000万吨", "产量稳定")
        assert "产量" in implication or "供应" in implication
        
        # 需求相关
        implication = self.parser._infer_implication("焦煤需求", "1200万吨", "需求旺盛")
        assert "需求" in implication
    
    def test_generate_factor_suggestions(self):
        """测试生成因子建议"""
        viewpoints = [
            KeyViewpoint(
                viewpoint_id='vp_001',
                content='安全检查限产导致供应收紧',
                category='supply',
                confidence=0.8,
                supporting_data=[]
            )
        ]
        
        data_logic = []
        logic_chains = []
        
        suggestions = self.parser._generate_factor_suggestions(
            viewpoints, data_logic, logic_chains
        )
        
        assert isinstance(suggestions, list)
        if suggestions:
            assert suggestions[0].name != ''
            assert suggestions[0].description != ''
    
    def test_parse_json_response(self):
        """测试解析 JSON 响应"""
        # 测试 markdown 代码块中的 JSON
        response_with_code_block = '''
```json
{
  "viewpoints": [
    {
      "content": "观点1",
      "category": "supply",
      "confidence": 0.8,
      "supporting_data": ["数据1"]
    }
  ]
}
```
'''
        result = self.parser._parse_json_response(response_with_code_block)
        assert 'viewpoints' in result
        
        # 测试纯 JSON
        response_pure_json = '{"viewpoints": [{"content": "观点1"}]}'
        result = self.parser._parse_json_response(response_pure_json)
        assert 'viewpoints' in result


class TestValidationPipeline:
    """验证流水线测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.pipeline = ValidationPipeline()
    
    def test_validate_analysis_with_data(self):
        """测试验证有数据的分析结果"""
        analysis = ReportAnalysis(
            report_id='report_001',
            title='测试报告',
            source='测试来源',
            publish_date='2026-06-15',
            key_viewpoints=[
                KeyViewpoint(
                    viewpoint_id='vp_001',
                    content='这是一个测试观点',
                    category='supply',
                    confidence=0.8,
                    supporting_data=[]
                )
            ],
            data_logic=[
                DataLogic(
                    metric='库存',
                    value='100万吨',
                    context='库存处于低位',
                    implication='影响供需平衡'
                )
            ],
            logic_chains=[
                LogicChain(
                    cause='供应收紧',
                    effect='价格上涨',
                    mechanism='供应收紧 → 价格上涨',
                    confidence=0.7
                )
            ],
            factor_suggestions=[
                FactorSuggestion(
                    suggestion_id='suggest_001',
                    name='供应端因子',
                    description='基于供应端观点',
                    logic='监控供应端变化',
                    expected_effect='捕捉供应端机会',
                    implementation_difficulty='medium',
                    data_requirements=['产量数据']
                )
            ],
            raw_content='测试内容'
        )
        
        result = self.pipeline.validate_analysis(analysis)
        
        assert result['is_valid'] == True
        assert result['quality_score'] > 50
        assert len(result['errors']) == 0
    
    def test_validate_analysis_without_data(self):
        """测试验证无数据的分析结果"""
        analysis = ReportAnalysis(
            report_id='report_002',
            title='空报告',
            source='测试来源',
            publish_date='2026-06-15',
            key_viewpoints=[],
            data_logic=[],
            logic_chains=[],
            factor_suggestions=[],
            raw_content='空内容'
        )
        
        result = self.pipeline.validate_analysis(analysis)
        
        assert result['is_valid'] == True  # 没有错误，只有警告
        assert len(result['warnings']) > 0
        assert result['quality_score'] == 50  # 基础分
    
    def test_calculate_quality_score(self):
        """测试计算质量分数"""
        analysis = ReportAnalysis(
            report_id='report_001',
            title='测试报告',
            source='测试来源',
            publish_date='2026-06-15',
            key_viewpoints=[
                KeyViewpoint(viewpoint_id='vp_001', content='观点1', category='supply', confidence=0.8, supporting_data=[]),
                KeyViewpoint(viewpoint_id='vp_002', content='观点2', category='demand', confidence=0.7, supporting_data=[])
            ],
            data_logic=[
                DataLogic(metric='库存', value='100万吨', context='库存低', implication='影响供需')
            ],
            logic_chains=[
                LogicChain(cause='供应', effect='价格', mechanism='供应→价格', confidence=0.7)
            ],
            factor_suggestions=[
                FactorSuggestion(suggestion_id='s1', name='因子1', description='描述', logic='逻辑', expected_effect='效果', implementation_difficulty='medium', data_requirements=[])
            ],
            raw_content='内容'
        )
        
        score = self.pipeline._calculate_quality_score(analysis)
        
        assert score > 50
        assert score <= 100


class TestKeyViewpoint:
    """关键观点测试"""
    
    def test_create_key_viewpoint(self):
        """测试创建关键观点"""
        viewpoint = KeyViewpoint(
            viewpoint_id='vp_001',
            content='安全检查限产导致供应收紧',
            category='supply',
            confidence=0.8,
            supporting_data=['数据1', '数据2']
        )
        
        assert viewpoint.viewpoint_id == 'vp_001'
        assert viewpoint.content == '安全检查限产导致供应收紧'
        assert viewpoint.category == 'supply'
        assert viewpoint.confidence == 0.8
        assert len(viewpoint.supporting_data) == 2


class TestDataLogic:
    """数据逻辑测试"""
    
    def test_create_data_logic(self):
        """测试创建数据逻辑"""
        data_logic = DataLogic(
            metric='焦煤库存',
            value='100万吨',
            context='库存处于历史低位',
            implication='影响供需平衡'
        )
        
        assert data_logic.metric == '焦煤库存'
        assert data_logic.value == '100万吨'
        assert data_logic.context == '库存处于历史低位'
        assert data_logic.implication == '影响供需平衡'


class TestLogicChain:
    """逻辑链测试"""
    
    def test_create_logic_chain(self):
        """测试创建逻辑链"""
        logic_chain = LogicChain(
            cause='安全检查限产',
            effect='供应收紧',
            mechanism='安全检查限产 → 供应收紧',
            confidence=0.7
        )
        
        assert logic_chain.cause == '安全检查限产'
        assert logic_chain.effect == '供应收紧'
        assert logic_chain.mechanism == '安全检查限产 → 供应收紧'
        assert logic_chain.confidence == 0.7


class TestFactorSuggestion:
    """因子建议测试"""
    
    def test_create_factor_suggestion(self):
        """测试创建因子建议"""
        suggestion = FactorSuggestion(
            suggestion_id='suggest_001',
            name='供应端因子',
            description='基于供应端观点的因子',
            logic='监控供应端变化',
            expected_effect='捕捉供应端机会',
            implementation_difficulty='medium',
            data_requirements=['产量数据', '库存数据']
        )
        
        assert suggestion.suggestion_id == 'suggest_001'
        assert suggestion.name == '供应端因子'
        assert suggestion.description == '基于供应端观点的因子'
        assert suggestion.logic == '监控供应端变化'
        assert suggestion.expected_effect == '捕捉供应端机会'
        assert suggestion.implementation_difficulty == 'medium'
        assert len(suggestion.data_requirements) == 2


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
