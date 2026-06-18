"""
部署风险评估模块

基于 Algometrics 论文 (arXiv:2605.23978) 的思想：
- 区分历史风险与部署风险
- 估算反馈间隙
- 评估模型部署后的真实表现

核心公式：
- 部署风险 R_m(f) = 历史风险 R_0(f) + 反馈间隙 Γ_m(f)
- 反馈间隙 Γ_m(f) = 部署风险 - 历史风险
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class RiskType(Enum):
    """风险类型"""
    HISTORICAL = "historical"    # 历史风险 (被动预测)
    DEPLOYMENT = "deployment"    # 部署风险 (主动交易)
    FEEDBACK = "feedback"        # 反馈间隙


@dataclass
class RiskAssessment:
    """风险评估结果"""
    risk_type: RiskType
    historical_risk: float      # 历史风险 R_0(f)
    deployment_risk: float      # 部署风险 R_m(f)
    feedback_gap: float         # 反馈间隙 Γ_m(f)
    confidence: float           # 评估置信度
    recommendations: List[str]  # 建议


@dataclass
class ModelPerformance:
    """模型表现"""
    model_name: str
    historical_accuracy: float  # 历史准确率
    signal_strength: float      # 信号强度
    trading_frequency: float    # 交易频率
    position_size: float        # 头寸大小


class DeploymentRiskEstimator:
    """
    部署风险评估器
    
    基于论文思想：
    1. 区分历史风险与部署风险
    2. 估算反馈间隙
    3. 提供部署建议
    """
    
    def __init__(self, 
                 feedback_coefficient: float = 0.3,
                 adoption_rate: float = 0.1):
        """
        初始化部署风险评估器
        
        Args:
            feedback_coefficient: 反馈系数 β (行动对价格的影响)
            adoption_rate: 采用率 m (市场份额)
        """
        self.feedback_coefficient = feedback_coefficient
        self.adoption_rate = adoption_rate
        
    def assess(self, 
               model: ModelPerformance,
               market_liquidity: float = 1.0) -> RiskAssessment:
        """
        评估模型的部署风险
        
        Args:
            model: 模型表现
            market_liquidity: 市场流动性
            
        Returns:
            RiskAssessment: 风险评估结果
        """
        # 1. 计算历史风险
        historical_risk = self._calculate_historical_risk(model)
        
        # 2. 计算反馈间隙
        feedback_gap = self._calculate_feedback_gap(
            model, market_liquidity
        )
        
        # 3. 计算部署风险
        deployment_risk = historical_risk + feedback_gap
        
        # 4. 计算置信度
        confidence = self._calculate_confidence(model)
        
        # 5. 生成建议
        recommendations = self._generate_recommendations(
            historical_risk, deployment_risk, feedback_gap
        )
        
        return RiskAssessment(
            risk_type=RiskType.DEPLOYMENT,
            historical_risk=historical_risk,
            deployment_risk=deployment_risk,
            feedback_gap=feedback_gap,
            confidence=confidence,
            recommendations=recommendations
        )
    
    def _calculate_historical_risk(self, model: ModelPerformance) -> float:
        """
        计算历史风险
        
        基于模型的历史表现
        """
        # 历史风险 = 1 - 历史准确率
        base_risk = 1.0 - model.historical_accuracy
        
        # 信号强度修正 (强信号可能更可靠)
        signal_factor = 1.0 - abs(model.signal_strength) * 0.2
        
        historical_risk = base_risk * signal_factor
        
        return np.clip(historical_risk, 0, 1)
    
    def _calculate_feedback_gap(self, 
                                 model: ModelPerformance,
                                 market_liquidity: float) -> float:
        """
        计算反馈间隙
        
        基于论文公式：
        Γ_m(f) = R_m(f) - R_0(f)
        
        反馈间隙取决于：
        1. 反馈系数 β
        2. 采用率 m
        3. 信号强度
        4. 市场流动性
        """
        # 基础反馈间隙
        base_gap = self.feedback_coefficient * self.adoption_rate
        
        # 信号强度修正 (强信号扰动更大)
        signal_factor = abs(model.signal_strength) * 2.0
        
        # 交易频率修正 (高频交易扰动更大)
        frequency_factor = model.trading_frequency
        
        # 头寸大小修正 (大头寸扰动更大)
        position_factor = model.position_size
        
        # 流动性修正 (低流动性市场更容易受影响)
        liquidity_factor = 1.0 / max(market_liquidity, 0.1)
        
        feedback_gap = (
            base_gap * 
            signal_factor * 
            frequency_factor * 
            position_factor * 
            liquidity_factor
        )
        
        return np.clip(feedback_gap, 0, 1)
    
    def _calculate_confidence(self, model: ModelPerformance) -> float:
        """计算评估置信度"""
        # 置信度基于历史数据量和模型稳定性
        base_confidence = 0.7
        
        # 历史准确率越高，置信度越高
        accuracy_factor = model.historical_accuracy * 0.2
        
        confidence = base_confidence + accuracy_factor
        
        return np.clip(confidence, 0, 1)
    
    def _generate_recommendations(self,
                                   historical_risk: float,
                                   deployment_risk: float,
                                   feedback_gap: float) -> List[str]:
        """生成部署建议"""
        recommendations = []
        
        # 基于反馈间隙的建议
        if feedback_gap > 0.3:
            recommendations.append(
                "反馈间隙较大，部署后表现可能显著低于历史回测"
            )
        
        # 基于部署风险的建议
        if deployment_risk > 0.7:
            recommendations.append(
                "部署风险过高，建议暂不部署或大幅降低头寸"
            )
        elif deployment_risk > 0.5:
            recommendations.append(
                "部署风险中等，建议小规模测试部署"
            )
        
        # 基于风险差异的建议
        risk_ratio = deployment_risk / max(historical_risk, 0.01)
        if risk_ratio > 2.0:
            recommendations.append(
                f"部署风险是历史风险的 {risk_ratio:.1f} 倍，需谨慎"
            )
        
        if not recommendations:
            recommendations.append("风险在可接受范围内，可正常部署")
        
        return recommendations
    
    def compare_models(self,
                       models: List[ModelPerformance],
                       market_liquidity: float = 1.0) -> Dict:
        """
        比较多个模型的部署风险
        
        基于论文定理2：历史排名可能在部署后反转
        """
        assessments = []
        
        for model in models:
            assessment = self.assess(model, market_liquidity)
            assessments.append({
                'model': model,
                'assessment': assessment
            })
        
        # 按历史风险排序
        historical_ranking = sorted(
            assessments, 
            key=lambda x: x['assessment'].historical_risk
        )
        
        # 按部署风险排序
        deployment_ranking = sorted(
            assessments, 
            key=lambda x: x['assessment'].deployment_risk
        )
        
        # 检查排名是否反转
        historical_order = [a['model'].model_name for a in historical_ranking]
        deployment_order = [a['model'].model_name for a in deployment_ranking]
        
        ranking_reversed = historical_order != deployment_order
        
        return {
            'assessments': assessments,
            'historical_ranking': historical_order,
            'deployment_ranking': deployment_order,
            'ranking_reversed': ranking_reversed,
            'recommendation': (
                "排名发生反转！选择部署风险最低的模型" if ranking_reversed 
                else "排名稳定，可按历史表现选择"
            )
        }
    
    def estimate_feedback_sensitivity(self,
                                      model: ModelPerformance,
                                      adoption_rates: List[float]) -> List[Dict]:
        """
        估算反馈敏感性
        
        论文建议：报告反馈敏感性，绘制拥挤曲线
        """
        sensitivity_curve = []
        
        for rate in adoption_rates:
            # 临时设置采用率
            original_rate = self.adoption_rate
            self.adoption_rate = rate
            
            # 估算部署风险
            assessment = self.assess(model)
            
            sensitivity_curve.append({
                'adoption_rate': rate,
                'deployment_risk': assessment.deployment_risk,
                'feedback_gap': assessment.feedback_gap
            })
            
            # 恢复原采用率
            self.adoption_rate = original_rate
        
        return sensitivity_curve


def create_risk_assessment_report(assessment: RiskAssessment,
                                   model_name: str) -> str:
    """
    创建风险评估报告
    
    用于交易决策简报
    """
    report = f"""
=== 部署风险评估报告 ===

模型: {model_name}

历史风险: {assessment.historical_risk:.3f}
部署风险: {assessment.deployment_risk:.3f}
反馈间隙: {assessment.feedback_gap:.3f}

置信度: {assessment.confidence:.3f}

建议:
"""
    
    for i, rec in enumerate(assessment.recommendations, 1):
        report += f"  {i}. {rec}\n"
    
    return report
