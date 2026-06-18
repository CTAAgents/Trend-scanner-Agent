"""
推理层

提供 LLM 推理和决策生成功能：
- ReasoningEngine: LLM 推理引擎
- DebateEngine: 多角色辩论
- TriadDebateEngine: 三方辩论（基于多智能体融合框架）
- EvidenceEvaluator: 论据可靠性评估
- ScenarioAnalyzer: 场景分析
- BriefGenerator: 决策简报生成
- HallucinationDetector: 幻觉检测
- AdaptivePromptRouter: 自适应Prompt路由
"""

from .hallucination_detector import HallucinationDetector, HallucinationType
from .adaptive_prompt_router import AdaptivePromptRouter, PromptTemplateType
from .triad_debate_engine import TriadDebateEngine, TriadDebateResult, RiskPerspective
from .evidence_evaluator import EvidenceEvaluator, EvidenceAssessment, SourceType

__all__ = [
    "HallucinationDetector",
    "HallucinationType",
    "AdaptivePromptRouter",
    "PromptTemplateType",
    "TriadDebateEngine",
    "TriadDebateResult",
    "RiskPerspective",
    "EvidenceEvaluator",
    "EvidenceAssessment",
    "SourceType",
]
