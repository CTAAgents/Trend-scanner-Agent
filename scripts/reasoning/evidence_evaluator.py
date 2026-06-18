"""
论据可靠性评估模块

基于期货CTA多智能体融合框架的设计思想：
- 数据来源权重（权威 > 研报 > 媒体 > 网络）
- 时间相关性（实时 > 日内 > 日度 > 周度）
- 可验证性（量化验证 > 逻辑推理 > 主观判断）
- 历史一致性（多次验证 > 偶尔验证 > 未验证）

核心功能：
1. 论据来源评估
2. 时间相关性评估
3. 可验证性评估
4. 历史一致性评估
5. 综合权重计算
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """数据来源类型"""
    EXCHANGE = "exchange"  # 交易所官方数据
    REGULATORY = "regulatory"  # 监管机构数据
    BROKER = "broker"  # 头部券商研报
    TERMINAL = "terminal"  # 专业终端（Wind/Bloomberg）
    MEDIA = "media"  # 财经媒体
    SOCIAL = "social"  # 社交媒体/自媒体


class TimeRelevance(Enum):
    """时间相关性"""
    REALTIME = "realtime"  # 实时
    INTRADAY = "intraday"  # 日内
    DAILY = "daily"  # 日度
    WEEKLY = "weekly"  # 周度
    MONTHLY = "monthly"  # 月度


class Verifiability(Enum):
    """可验证性"""
    QUANTITATIVE = "quantitative"  # 量化验证
    LOGICAL = "logical"  # 逻辑推理
    SUBJECTIVE = "subjective"  # 主观判断


class HistoricalConsistency(Enum):
    """历史一致性"""
    MULTIPLE_VERIFIED = "multiple_verified"  # 多次验证
    OCCASIONALLY_VERIFIED = "occasionally_verified"  # 偶尔验证
    UNVERIFIED = "unverified"  # 未验证


@dataclass
class EvidenceAssessment:
    """论据评估结果"""
    source_type: SourceType
    source_credibility: float  # 来源可信度 (0-1)
    
    time_relevance: TimeRelevance
    time_score: float  # 时间相关性得分 (0-1)
    
    verifiability: Verifiability
    verifiability_score: float  # 可验证性得分 (0-1)
    
    historical_consistency: HistoricalConsistency
    consistency_score: float  # 历史一致性得分 (0-1)
    
    # 综合得分
    overall_score: float = 0.0
    
    def __post_init__(self):
        """计算综合得分"""
        self.overall_score = (
            self.source_credibility * 0.4 +
            self.time_score * 0.3 +
            self.verifiability_score * 0.2 +
            self.consistency_score * 0.1
        )


class EvidenceEvaluator:
    """
    论据可靠性评估器
    
    基于期货CTA多智能体融合框架的论据评估框架
    """
    
    # 来源可信度权重
    SOURCE_CREDIBILITY = {
        SourceType.EXCHANGE: 1.0,
        SourceType.REGULATORY: 0.95,
        SourceType.BROKER: 0.8,
        SourceType.TERMINAL: 0.7,
        SourceType.MEDIA: 0.5,
        SourceType.SOCIAL: 0.3,
    }
    
    # 时间相关性得分
    TIME_SCORES = {
        TimeRelevance.REALTIME: 1.0,
        TimeRelevance.INTRADAY: 0.8,
        TimeRelevance.DAILY: 0.6,
        TimeRelevance.WEEKLY: 0.4,
        TimeRelevance.MONTHLY: 0.2,
    }
    
    # 可验证性得分
    VERIFIABILITY_SCORES = {
        Verifiability.QUANTITATIVE: 1.0,
        Verifiability.LOGICAL: 0.6,
        Verifiability.SUBJECTIVE: 0.3,
    }
    
    # 历史一致性得分
    CONSISTENCY_SCORES = {
        HistoricalConsistency.MULTIPLE_VERIFIED: 1.0,
        HistoricalConsistency.OCCASIONALLY_VERIFIED: 0.6,
        HistoricalConsistency.UNVERIFIED: 0.2,
    }
    
    def __init__(self):
        """初始化论据评估器"""
        pass
    
    def assess(
        self,
        source_type: SourceType,
        time_relevance: TimeRelevance,
        verifiability: Verifiability,
        historical_consistency: HistoricalConsistency,
    ) -> EvidenceAssessment:
        """
        评估论据可靠性
        
        Args:
            source_type: 数据来源类型
            time_relevance: 时间相关性
            verifiability: 可验证性
            historical_consistency: 历史一致性
            
        Returns:
            EvidenceAssessment: 评估结果
        """
        return EvidenceAssessment(
            source_type=source_type,
            source_credibility=self.SOURCE_CREDIBILITY[source_type],
            time_relevance=time_relevance,
            time_score=self.TIME_SCORES[time_relevance],
            verifiability=verifiability,
            verifiability_score=self.VERIFIABILITY_SCORES[verifiability],
            historical_consistency=historical_consistency,
            consistency_score=self.CONSISTENCY_SCORES[historical_consistency],
        )
    
    def assess_from_text(self, text: str) -> EvidenceAssessment:
        """
        从文本推断论据可靠性
        
        Args:
            text: 论据文本
            
        Returns:
            EvidenceAssessment: 评估结果
        """
        # 推断来源类型
        source_type = self._infer_source_type(text)
        
        # 推断时间相关性
        time_relevance = self._infer_time_relevance(text)
        
        # 推断可验证性
        verifiability = self._infer_verifiability(text)
        
        # 推断历史一致性
        historical_consistency = self._infer_historical_consistency(text)
        
        return self.assess(
            source_type, time_relevance, verifiability, historical_consistency
        )
    
    def _infer_source_type(self, text: str) -> SourceType:
        """从文本推断来源类型"""
        text_lower = text.lower()
        
        # 交易所/监管机构关键词
        if any(k in text_lower for k in ["交易所", "证监会", "统计局", "央行"]):
            return SourceType.EXCHANGE
        
        # 券商研报关键词
        if any(k in text_lower for k in ["研报", "券商", "中信", "中金", "国泰"]):
            return SourceType.BROKER
        
        # 专业终端关键词
        if any(k in text_lower for k in ["wind", "bloomberg", "reuters"]):
            return SourceType.TERMINAL
        
        # 媒体关键词
        if any(k in text_lower for k in ["财经", "新闻", "报道"]):
            return SourceType.MEDIA
        
        # 社交媒体关键词
        if any(k in text_lower for k in ["微博", "股吧", "抖音", "自媒体"]):
            return SourceType.SOCIAL
        
        # 默认：媒体
        return SourceType.MEDIA
    
    def _infer_time_relevance(self, text: str) -> TimeRelevance:
        """从文本推断时间相关性"""
        text_lower = text.lower()
        
        if any(k in text_lower for k in ["实时", "最新", "刚刚"]):
            return TimeRelevance.REALTIME
        elif any(k in text_lower for k in ["今日", "今天", "日内"]):
            return TimeRelevance.INTRADAY
        elif any(k in text_lower for k in ["昨日", "昨天", "日线", "日度"]):
            return TimeRelevance.DAILY
        elif any(k in text_lower for k in ["本周", "周线", "周度"]):
            return TimeRelevance.WEEKLY
        elif any(k in text_lower for k in ["本月", "月线", "月度"]):
            return TimeRelevance.MONTHLY
        
        # 默认：日度
        return TimeRelevance.DAILY
    
    def _infer_verifiability(self, text: str) -> Verifiability:
        """从文本推断可验证性"""
        text_lower = text.lower()
        
        # 量化验证关键词
        if any(k in text_lower for k in ["回测", "数据", "统计", "指标", "量化"]):
            return Verifiability.QUANTITATIVE
        
        # 主观判断关键词
        if any(k in text_lower for k in ["我认为", "感觉", "估计", "可能"]):
            return Verifiability.SUBJECTIVE
        
        # 默认：逻辑推理
        return Verifiability.LOGICAL
    
    def _infer_historical_consistency(self, text: str) -> HistoricalConsistency:
        """从文本推断历史一致性"""
        text_lower = text.lower()
        
        # 多次验证关键词
        if any(k in text_lower for k in ["历史", "过去", "多次", "验证"]):
            return HistoricalConsistency.MULTIPLE_VERIFIED
        
        # 未验证关键词
        if any(k in text_lower for k in ["首次", "新", "创新"]):
            return HistoricalConsistency.UNVERIFIED
        
        # 默认：偶尔验证
        return HistoricalConsistency.OCCASIONALLY_VERIFIED
    
    def compare_evidence(
        self, evidence_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        比较多条论据的可靠性
        
        Args:
            evidence_list: 论据列表，每条包含text字段
            
        Returns:
            按可靠性排序的论据列表
        """
        assessed = []
        
        for evidence in evidence_list:
            text = evidence.get("text", "")
            assessment = self.assess_from_text(text)
            
            assessed.append({
                **evidence,
                "assessment": assessment,
                "overall_score": assessment.overall_score,
            })
        
        # 按综合得分排序
        assessed.sort(key=lambda x: x["overall_score"], reverse=True)
        
        return assessed
    
    def create_assessment_report(self, assessment: EvidenceAssessment) -> str:
        """创建评估报告"""
        lines = [
            "=== 论据可靠性评估报告 ===",
            f"来源类型：{assessment.source_type.value}",
            f"来源可信度：{assessment.source_credibility:.2f}",
            f"时间相关性：{assessment.time_relevance.value}（得分：{assessment.time_score:.2f}）",
            f"可验证性：{assessment.verifiability.value}（得分：{assessment.verifiability_score:.2f}）",
            f"历史一致性：{assessment.historical_consistency.value}（得分：{assessment.consistency_score:.2f}）",
            f"综合得分：{assessment.overall_score:.2f}",
        ]
        
        return "\n".join(lines)
