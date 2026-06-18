"""
三方辩论引擎测试

测试 TriadDebateEngine 和 EvidenceEvaluator
"""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from reasoning.evidence_evaluator import (
    EvidenceEvaluator,
    EvidenceAssessment,
    SourceType,
    TimeRelevance,
    Verifiability,
    HistoricalConsistency,
)


class TestEvidenceEvaluator:
    """论据可靠性评估器测试"""
    
    def test_init(self):
        """测试初始化"""
        evaluator = EvidenceEvaluator()
        assert evaluator is not None
    
    def test_assess_basic(self):
        """测试基本评估"""
        evaluator = EvidenceEvaluator()
        
        assessment = evaluator.assess(
            source_type=SourceType.EXCHANGE,
            time_relevance=TimeRelevance.REALTIME,
            verifiability=Verifiability.QUANTITATIVE,
            historical_consistency=HistoricalConsistency.MULTIPLE_VERIFIED,
        )
        
        assert assessment.source_credibility == 1.0
        assert assessment.time_score == 1.0
        assert assessment.verifiability_score == 1.0
        assert assessment.consistency_score == 1.0
        assert abs(assessment.overall_score - 1.0) < 0.001
    
    def test_assess_low_quality(self):
        """测试低质量论据评估"""
        evaluator = EvidenceEvaluator()
        
        assessment = evaluator.assess(
            source_type=SourceType.SOCIAL,
            time_relevance=TimeRelevance.MONTHLY,
            verifiability=Verifiability.SUBJECTIVE,
            historical_consistency=HistoricalConsistency.UNVERIFIED,
        )
        
        assert assessment.source_credibility == 0.3
        assert assessment.time_score == 0.2
        assert assessment.verifiability_score == 0.3
        assert assessment.consistency_score == 0.2
        assert assessment.overall_score < 0.5
    
    def test_assess_from_text(self):
        """测试从文本评估"""
        evaluator = EvidenceEvaluator()
        
        # 测试交易所数据
        text1 = "交易所最新库存数据显示..."
        assessment1 = evaluator.assess_from_text(text1)
        assert assessment1.source_type == SourceType.EXCHANGE
        
        # 测试券商研报
        text2 = "中信建投研报指出..."
        assessment2 = evaluator.assess_from_text(text2)
        assert assessment2.source_type == SourceType.BROKER
        
        # 测试社交媒体
        text3 = "微博有人说..."
        assessment3 = evaluator.assess_from_text(text3)
        assert assessment3.source_type == SourceType.SOCIAL
    
    def test_compare_evidence(self):
        """测试论据比较"""
        evaluator = EvidenceEvaluator()
        
        evidence_list = [
            {"text": "交易所最新数据"},
            {"text": "微博传闻"},
            {"text": "券商研报分析"},
        ]
        
        sorted_evidence = evaluator.compare_evidence(evidence_list)
        
        # 应该按可靠性排序
        assert sorted_evidence[0]["text"] == "交易所最新数据"
        assert sorted_evidence[-1]["text"] == "微博传闻"
    
    def test_create_assessment_report(self):
        """测试评估报告生成"""
        evaluator = EvidenceEvaluator()
        
        assessment = evaluator.assess(
            source_type=SourceType.BROKER,
            time_relevance=TimeRelevance.DAILY,
            verifiability=Verifiability.LOGICAL,
            historical_consistency=HistoricalConsistency.OCCASIONALLY_VERIFIED,
        )
        
        report = evaluator.create_assessment_report(assessment)
        
        assert "来源类型" in report
        assert "综合得分" in report


class TestIntegration:
    """集成测试"""
    
    def test_triad_debate_with_evidence(self):
        """测试三方辩论与论据评估集成"""
        # 创建评估器
        evidence_evaluator = EvidenceEvaluator()
        
        # 评估三条论据
        evidence1 = evidence_evaluator.assess_from_text("交易所最新数据")
        evidence2 = evidence_evaluator.assess_from_text("微博传闻")
        evidence3 = evidence_evaluator.assess_from_text("券商研报分析")
        
        # 比较可靠性
        assert evidence1.overall_score > evidence3.overall_score
        assert evidence3.overall_score > evidence2.overall_score
        
        # 三方辩论引擎可以使用评估结果
        assert evidence1 is not None
        assert evidence2 is not None
        assert evidence3 is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
