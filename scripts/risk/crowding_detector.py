"""
拥挤度检测模块

基于 Algometrics 论文 (arXiv:2605.23978) 的思想：
- 检测信号拥挤度
- 评估多策略同时运行时的相互干扰
- 识别历史排名反转风险

核心概念：
- 拥挤度 = 多个参与者使用相似信号的程度
- 高拥挤度 → 信号失效风险增加
- 拥挤强度 = 采用强度 × 负反馈系数
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class CrowdingLevel(Enum):
    """拥挤度等级"""
    LOW = "low"           # 低拥挤度，信号有效
    MEDIUM = "medium"     # 中等拥挤度，需关注
    HIGH = "high"         # 高拥挤度，信号可能失效
    CRITICAL = "critical" # 临界拥挤度，建议停止使用


@dataclass
class CrowdingMetrics:
    """拥挤度指标"""
    signal_correlation: float      # 信号与市场订单流相关性
    volume_concentration: float    # 成交量集中度
    price_impact: float           # 价格冲击
    crowding_score: float         # 综合拥挤度分数 (0-1)
    level: CrowdingLevel          # 拥挤度等级
    deployment_risk_premium: float  # 部署风险溢价 (历史风险 vs 部署风险之差)


@dataclass
class FeedbackCoefficients:
    """反馈系数"""
    beta: float  # 线性反馈系数 (行动对价格的影响)
    adoption_rate: float  # 采用率 (市场份额)
    crowding_intensity: float  # 拥挤强度 = adoption_rate × |beta|


class CrowdingDetector:
    """
    拥挤度检测器
    
    基于论文思想：
    1. 检测信号与市场订单流的相关性
    2. 评估成交量集中度
    3. 估算价格冲击
    4. 计算部署风险溢价
    """
    
    def __init__(self, 
                 high_threshold: float = 0.7,
                 critical_threshold: float = 0.9):
        """
        初始化拥挤度检测器
        
        Args:
            high_threshold: 高拥挤度阈值
            critical_threshold: 临界拥挤度阈值
        """
        self.high_threshold = high_threshold
        self.critical_threshold = critical_threshold
        
        # 历史信号记录
        self.signal_history: List[Dict] = []
        
    def detect(self, 
               signal: float,
               market_volume: float,
               price_change: float,
               order_flow: float) -> CrowdingMetrics:
        """
        检测当前拥挤度
        
        Args:
            signal: 交易信号强度 (-1 到 1)
            market_volume: 市场成交量
            price_change: 价格变化
            order_flow: 净订单流 (正=买方压力, 负=卖方压力)
            
        Returns:
            CrowdingMetrics: 拥挤度指标
        """
        # 1. 计算信号与订单流的相关性
        signal_correlation = self._calculate_signal_correlation(
            signal, order_flow
        )
        
        # 2. 计算成交量集中度
        volume_concentration = self._calculate_volume_concentration(
            market_volume
        )
        
        # 3. 计算价格冲击
        price_impact = self._calculate_price_impact(
            price_change, market_volume
        )
        
        # 4. 综合拥挤度分数
        crowding_score = self._calculate_crowding_score(
            signal_correlation,
            volume_concentration,
            price_impact
        )
        
        # 5. 确定拥挤度等级
        level = self._determine_level(crowding_score)
        
        # 6. 估算部署风险溢价
        deployment_risk_premium = self._estimate_deployment_risk_premium(
            crowding_score, signal_correlation
        )
        
        # 记录历史
        self._record_signal(signal, market_volume, price_change)
        
        return CrowdingMetrics(
            signal_correlation=signal_correlation,
            volume_concentration=volume_concentration,
            price_impact=price_impact,
            crowding_score=crowding_score,
            level=level,
            deployment_risk_premium=deployment_risk_premium
        )
    
    def _calculate_signal_correlation(self, 
                                       signal: float, 
                                       order_flow: float) -> float:
        """
        计算信号与订单流的相关性
        
        高相关性 = 高拥挤度（多个参与者使用相似信号）
        """
        # 归一化信号和订单流
        normalized_signal = np.clip(signal, -1, 1)
        normalized_flow = np.clip(order_flow / 1000, -1, 1)  # 假设1000为基准
        
        # 计算相关性 (简化版本)
        correlation = abs(normalized_signal * normalized_flow)
        
        return min(correlation, 1.0)
    
    def _calculate_volume_concentration(self, volume: float) -> float:
        """
        计算成交量集中度
        
        高集中度 = 少数参与者主导市场
        """
        # 使用历史成交量的相对值
        if len(self.signal_history) == 0:
            return 0.5  # 默认中等集中度
        
        historical_volumes = [h['volume'] for h in self.signal_history[-100:]]
        avg_volume = np.mean(historical_volumes)
        
        if avg_volume == 0:
            return 0.5
        
        # 当前成交量与历史平均的比值
        concentration = min(volume / avg_volume, 2.0) / 2.0
        
        return concentration
    
    def _calculate_price_impact(self, 
                                price_change: float, 
                                volume: float) -> float:
        """
        计算价格冲击
        
        高价格冲击 = 市场流动性不足
        """
        if volume == 0:
            return 1.0  # 无成交量，冲击最大
        
        # 价格变化与成交量的比值
        impact = abs(price_change) / (volume / 1000)
        
        return min(impact, 1.0)
    
    def _calculate_crowding_score(self,
                                   signal_corr: float,
                                   volume_conc: float,
                                   price_impact: float) -> float:
        """
        计算综合拥挤度分数
        
        权重：
        - 信号相关性: 40%
        - 成交量集中度: 30%
        - 价格冲击: 30%
        """
        weights = {
            'signal_corr': 0.4,
            'volume_conc': 0.3,
            'price_impact': 0.3
        }
        
        score = (
            weights['signal_corr'] * signal_corr +
            weights['volume_conc'] * volume_conc +
            weights['price_impact'] * price_impact
        )
        
        return min(score, 1.0)
    
    def _determine_level(self, score: float) -> CrowdingLevel:
        """确定拥挤度等级"""
        if score >= self.critical_threshold:
            return CrowdingLevel.CRITICAL
        elif score >= self.high_threshold:
            return CrowdingLevel.HIGH
        elif score >= 0.5:
            return CrowdingLevel.MEDIUM
        else:
            return CrowdingLevel.LOW
    
    def _estimate_deployment_risk_premium(self,
                                           crowding_score: float,
                                           signal_correlation: float) -> float:
        """
        估算部署风险溢价
        
        部署风险溢价 = 部署风险 - 历史风险
        
        基于论文定理2：拥挤强度超过阈值时，排名会反转
        """
        # 简化估算：拥挤度越高，部署风险溢价越大
        base_premium = crowding_score * 0.3  # 基础溢价
        
        # 信号相关性修正
        correlation_factor = 1.0 + signal_correlation * 0.5
        
        premium = base_premium * correlation_factor
        
        return min(premium, 1.0)
    
    def _record_signal(self, signal: float, volume: float, price_change: float):
        """记录信号历史"""
        self.signal_history.append({
            'signal': signal,
            'volume': volume,
            'price_change': price_change
        })
        
        # 保留最近1000条记录
        if len(self.signal_history) > 1000:
            self.signal_history = self.signal_history[-1000:]
    
    def get_crowding_curve(self, 
                           signal_strengths: List[float],
                           adoption_rates: List[float]) -> List[Dict]:
        """
        生成拥挤曲线
        
        论文建议：绘制性能随采用率的变化曲线
        
        Args:
            signal_strengths: 不同信号强度
            adoption_rates: 对应的采用率
            
        Returns:
            拥挤曲线数据点
        """
        curve = []
        
        for signal, adoption in zip(signal_strengths, adoption_rates):
            # 估算该采用率下的部署风险
            deployment_risk = self._estimate_deployment_risk(
                signal, adoption
            )
            
            curve.append({
                'adoption_rate': adoption,
                'signal_strength': signal,
                'deployment_risk': deployment_risk
            })
        
        return curve
    
    def _estimate_deployment_risk(self, 
                                   signal: float, 
                                   adoption_rate: float) -> float:
        """
        估算特定采用率下的部署风险
        
        基于论文公式：R_m(f) = R_0(f) + Γ_m(f)
        """
        # 基础历史风险 (简化)
        historical_risk = 0.3
        
        # 反馈间隙 (拥挤效应)
        feedback_gap = adoption_rate * abs(signal) * 0.5
        
        deployment_risk = historical_risk + feedback_gap
        
        return min(deployment_risk, 1.0)
    
    def check_ranking_reversal(self,
                               model_a_score: float,
                               model_b_score: float,
                               adoption_rate: float,
                               feedback_coefficient: float) -> Dict:
        """
        检查是否会发生排名反转
        
        基于论文定理2：
        当拥挤强度 > 阈值时，历史排名会反转
        
        Args:
            model_a_score: 模型A的历史分数
            model_b_score: 模型B的历史分数
            adoption_rate: 采用率
            feedback_coefficient: 反馈系数
            
        Returns:
            排名反转分析结果
        """
        # 计算拥挤强度
        crowding_intensity = adoption_rate * abs(feedback_coefficient)
        
        # 计算部署风险
        risk_a = self._calculate_deployment_risk(
            model_a_score, crowding_intensity
        )
        risk_b = self._calculate_deployment_risk(
            model_b_score, crowding_intensity
        )
        
        # 检查排名是否反转
        historical_rank = model_a_score > model_b_score
        deployment_rank = risk_a < risk_b  # 风险越低越好
        reversed = historical_rank != deployment_rank
        
        return {
            'crowding_intensity': crowding_intensity,
            'historical_rank_a_better': historical_rank,
            'deployment_rank_a_better': deployment_rank,
            'ranking_reversed': reversed,
            'model_a_deployment_risk': risk_a,
            'model_b_deployment_risk': risk_b,
            'recommendation': '避免使用模型A' if reversed else '排名稳定'
        }
    
    def _calculate_deployment_risk(self, 
                                   historical_score: float,
                                   crowding_intensity: float) -> float:
        """计算部署风险"""
        # 历史风险
        historical_risk = 1.0 - historical_score  # 分数越高，风险越低
        
        # 拥挤效应增加的风险
        crowding_risk = crowding_intensity * 0.5
        
        deployment_risk = historical_risk + crowding_risk
        
        return min(deployment_risk, 1.0)


def create_crowding_report(metrics: CrowdingMetrics) -> str:
    """
    创建拥挤度报告
    
    用于交易决策简报
    """
    level_emoji = {
        CrowdingLevel.LOW: "🟢",
        CrowdingLevel.MEDIUM: "🟡",
        CrowdingLevel.HIGH: "🟠",
        CrowdingLevel.CRITICAL: "🔴"
    }
    
    report = f"""
=== 拥挤度分析报告 ===

信号相关性: {metrics.signal_correlation:.3f}
成交量集中度: {metrics.volume_concentration:.3f}
价格冲击: {metrics.price_impact:.3f}

综合拥挤度: {metrics.crowding_score:.3f} {level_emoji[metrics.level]}
拥挤等级: {metrics.level.value}

部署风险溢价: {metrics.deployment_risk_premium:.3f}

建议: """
    
    if metrics.level == CrowdingLevel.LOW:
        report += "信号有效，可正常交易"
    elif metrics.level == CrowdingLevel.MEDIUM:
        report += "需关注拥挤度变化，适当控制仓位"
    elif metrics.level == CrowdingLevel.HIGH:
        report += "信号可能失效，建议减少交易或等待"
    else:
        report += "高风险！建议停止使用该信号"
    
    return report
