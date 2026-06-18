"""
风险评估模块

基于多篇论文的思想：
- Algometrics (arXiv:2605.23978): 拥挤度检测、部署风险评估
- KTD-Fin (arXiv:2605.28359): Barra风格收益归因
- Representation Signatures (arXiv:2605.28850): 表示诊断、风险反馈对齐
- TradeArena: 审计轨迹系统、多阶段风险检查
"""

from .crowding_detector import CrowdingDetector, CrowdingMetrics, CrowdingLevel
from .deployment_risk import DeploymentRiskEstimator, RiskAssessment
from .return_attributor import ReturnAttributor, AttributionResult
from .audit_trail import AuditTrail, AuditRecord, AuditTrailBuilder

__all__ = [
    "CrowdingDetector",
    "CrowdingMetrics", 
    "CrowdingLevel",
    "DeploymentRiskEstimator",
    "RiskAssessment",
    "ReturnAttributor",
    "AttributionResult",
    "AuditTrail",
    "AuditRecord",
    "AuditTrailBuilder",
]
