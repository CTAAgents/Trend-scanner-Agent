"""
三方辩论引擎

基于期货CTA多智能体融合框架的设计思想：
- 激进风控（Hawk）：接受较高风险，追求收益最大化
- 中性风控（Neutral）：平衡风险与收益
- 保守风控（Dove）：优先保护本金
- 首席风控官（ChiefRiskOfficer）：综合裁决

核心改进：
1. 从二元辩论扩展为三方辩论
2. 增加论据可靠性评估
3. 增加风险权重调节
"""

import sys
from pathlib import Path
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.core.models import ExperienceMatch, MarketContext
from .reasoning_engine import LLMProvider, ReasoningEngine, WorkBuddyAgentProvider


class RiskPerspective(Enum):
    """风险视角"""
    AGGRESSIVE = "aggressive"  # 激进
    NEUTRAL = "neutral"  # 中性
    CONSERVATIVE = "conservative"  # 保守


@dataclass
class ArgumentEvidence:
    """论据证据"""
    source: str  # 数据来源
    credibility: float  # 可信度 (0-1)
    time_relevance: float  # 时间相关性 (0-1)
    verifiability: float  # 可验证性 (0-1)
    historical_consistency: float  # 历史一致性 (0-1)
    weight: float = 0.0  # 综合权重
    
    def __post_init__(self):
        """计算综合权重"""
        self.weight = (
            self.credibility * 0.4 +
            self.time_relevance * 0.3 +
            self.verifiability * 0.2 +
            self.historical_consistency * 0.1
        )


@dataclass
class TriadDebateResult:
    """三方辩论结果"""
    aggressive_view: Dict[str, Any]  # 激进视角
    neutral_view: Dict[str, Any]  # 中性视角
    conservative_view: Dict[str, Any]  # 保守视角
    
    # 分歧度
    divergence_score: float  # 0-1
    
    # 整合结果
    integrated_direction: str  # LONG/SHORT/HOLD
    integrated_confidence: float  # 0-1
    position_scale: float  # 仓位调整系数 0-1
    
    # 论据评估
    evidence_scores: List[Dict[str, Any]] = field(default_factory=list)
    
    # 风险评估
    risk_level: str = "MEDIUM"  # LOW/MEDIUM/HIGH
    warnings: List[str] = field(default_factory=list)


class TriadDebateEngine:
    """
    三方辩论引擎
    
    基于期货CTA多智能体融合框架的设计思想
    """
    
    # 角色提示词
    ROLE_PROMPTS = {
        RiskPerspective.AGGRESSIVE: """你是一位**激进型**期货交易分析师。

## 核心倾向
- **高风险偏好**：愿意承担较高风险以获取更高收益
- **积极进攻**：强调趋势跟踪、动量交易、机会把握
- **快速决策**：在趋势确认时果断入场

## 分析重点
1. **机会最大化**：优先识别高胜率、高赔率的交易机会
2. **趋势强度**：关注趋势的持续性和加速信号
3. **动量信号**：重视价格动量和成交量配合
4. **收益潜力**：评估潜在收益空间

## 输出要求
请以积极进取的态度分析市场，强调机会把握和收益潜力。""",
        
        RiskPerspective.NEUTRAL: """你是一位**中性型**期货交易分析师。

## 核心倾向
- **风险平衡**：在风险与收益之间寻找最佳平衡点
- **稳健分析**：综合技术面、基本面、资金面多维度分析
- **灵活应对**：根据市场状态动态调整策略

## 分析重点
1. **多维验证**：要求技术面、基本面、资金面多维度确认
2. **风险收益比**：评估每笔交易的风险收益比
3. **市场状态**：判断当前市场处于趋势、震荡还是反转阶段
4. **仓位平衡**：建议适中的仓位配置

## 输出要求
请以客观中立的态度分析市场，强调风险收益平衡和多维验证。""",
        
        RiskPerspective.CONSERVATIVE: """你是一位**保守型**期货交易分析师。

## 核心倾向
- **本金保护**：优先保护本金，避免重大亏损
- **风险厌恶**：强调止损、风险控制、仓位管理
- **谨慎保守**：在不确定性高时选择观望

## 分析重点
1. **风险识别**：优先识别潜在风险和下行压力
2. **止损设置**：倾向于设置更紧的止损
3. **仓位控制**：倾向于降低仓位，保留现金
4. **安全边际**：要求足够的安全边际才入场

## 输出要求
请以谨慎保守的态度分析市场，强调风险控制和本金保护。""",
    }
    
    def __init__(
        self,
        aggressive_llm: Optional[LLMProvider] = None,
        neutral_llm: Optional[LLMProvider] = None,
        conservative_llm: Optional[LLMProvider] = None,
    ):
        """
        初始化三方辩论引擎
        
        Args:
            aggressive_llm: 激进视角LLM
            neutral_llm: 中性视角LLM
            conservative_llm: 保守视角LLM
        """
        self.aggressive_llm = aggressive_llm or WorkBuddyAgentProvider()
        self.neutral_llm = neutral_llm or WorkBuddyAgentProvider()
        self.conservative_llm = conservative_llm or WorkBuddyAgentProvider()
        
        # 创建推理引擎
        self.aggressive_engine = ReasoningEngine(self.aggressive_llm)
        self.neutral_engine = ReasoningEngine(self.neutral_llm)
        self.conservative_engine = ReasoningEngine(self.conservative_llm)
    
    def debate(
        self,
        context: MarketContext,
        similar_experiences: List[ExperienceMatch],
        experience_aggregation: Dict[str, Any],
    ) -> TriadDebateResult:
        """
        执行三方辩论
        
        Args:
            context: 市场上下文
            similar_experiences: 相似经验
            experience_aggregation: 经验聚合
            
        Returns:
            TriadDebateResult: 辩论结果
        """
        start_time = time.time()
        
        # 1. 三方推理
        aggressive_view = self._reason_with_role(
            context, similar_experiences, experience_aggregation,
            RiskPerspective.AGGRESSIVE
        )
        neutral_view = self._reason_with_role(
            context, similar_experiences, experience_aggregation,
            RiskPerspective.NEUTRAL
        )
        conservative_view = self._reason_with_role(
            context, similar_experiences, experience_aggregation,
            RiskPerspective.CONSERVATIVE
        )
        
        # 2. 计算分歧度
        divergence_score = self._calculate_divergence(
            aggressive_view, neutral_view, conservative_view
        )
        
        # 3. 整合辩论结果
        integrated = self._integrate_triad_debate(
            aggressive_view, neutral_view, conservative_view,
            divergence_score
        )
        
        # 4. 评估论据可靠性
        evidence_scores = self._evaluate_evidence(
            aggressive_view, neutral_view, conservative_view
        )
        
        # 5. 评估风险水平
        risk_level = self._assess_risk_level(
            divergence_score, context
        )
        
        # 6. 生成警告
        warnings = self._generate_warnings(
            divergence_score, risk_level, context
        )
        
        return TriadDebateResult(
            aggressive_view=aggressive_view,
            neutral_view=neutral_view,
            conservative_view=conservative_view,
            divergence_score=divergence_score,
            integrated_direction=integrated["direction"],
            integrated_confidence=integrated["confidence"],
            position_scale=integrated["position_scale"],
            evidence_scores=evidence_scores,
            risk_level=risk_level,
            warnings=warnings,
        )
    
    def _reason_with_role(
        self,
        context: MarketContext,
        similar_experiences: List[ExperienceMatch],
        experience_aggregation: Dict[str, Any],
        perspective: RiskPerspective,
    ) -> Dict[str, Any]:
        """
        使用特定角色进行推理
        
        Args:
            context: 市场上下文
            similar_experiences: 相似经验
            experience_aggregation: 经验聚合
            perspective: 风险视角
            
        Returns:
            推理结果
        """
        # 选择对应的引擎
        engines = {
            RiskPerspective.AGGRESSIVE: self.aggressive_engine,
            RiskPerspective.NEUTRAL: self.neutral_engine,
            RiskPerspective.CONSERVATIVE: self.conservative_engine,
        }
        engine = engines[perspective]
        
        # 构建角色特定的提示词
        system_prompt = self.ROLE_PROMPTS[perspective]
        
        # 构建用户提示词
        user_prompt = engine._build_user_prompt(
            context, similar_experiences, experience_aggregation
        )
        
        # 调用LLM
        try:
            llm_response = engine.llm_provider.generate(system_prompt, user_prompt)
        except Exception:
            llm_response = engine._emergency_fallback(context)
        
        # 解析响应
        try:
            parsed = engine._parse_response(llm_response)
        except Exception:
            parsed = engine._emergency_fallback(context)
        
        # 添加角色标记
        parsed["perspective"] = perspective.value
        
        return parsed
    
    def _calculate_divergence(
        self,
        aggressive_view: Dict[str, Any],
        neutral_view: Dict[str, Any],
        conservative_view: Dict[str, Any],
    ) -> float:
        """
        计算三方分歧度
        
        Returns:
            分歧度 (0-1)
        """
        views = [aggressive_view, neutral_view, conservative_view]
        
        # 提取方向
        directions = []
        for view in views:
            direction = self._extract_direction(view)
            directions.append(direction)
        
        # 计算方向分歧
        direction_divergence = 0.0
        for i in range(len(directions)):
            for j in range(i + 1, len(directions)):
                direction_divergence += abs(directions[i] - directions[j])
        direction_divergence /= 6.0  # 除以3个组合的总数
        
        # 计算置信度分歧
        confidences = [view.get("confidence", 0.5) for view in views]
        confidence_divergence = max(confidences) - min(confidences)
        
        # 加权平均
        divergence = direction_divergence * 0.6 + confidence_divergence * 0.4
        
        return min(max(divergence, 0.0), 1.0)
    
    def _extract_direction(self, view: Dict[str, Any]) -> int:
        """提取方向 (1=多头, -1=空头, 0=中性)"""
        routes = view.get("routes", [])
        recommended = view.get("recommended_route", "")
        
        for route in routes:
            if route.get("route_id") == recommended:
                action = route.get("action", "").lower()
                if any(k in action for k in ["多", "long", "买入", "加仓", "做多"]):
                    return 1
                if any(k in action for k in ["空", "short", "卖出", "减仓", "做空"]):
                    return -1
        
        return 0
    
    def _integrate_triad_debate(
        self,
        aggressive_view: Dict[str, Any],
        neutral_view: Dict[str, Any],
        conservative_view: Dict[str, Any],
        divergence_score: float,
    ) -> Dict[str, Any]:
        """
        整合三方辩论结果
        
        整合策略：
        - 低分歧 (<0.3)：偏向激进
        - 中分歧 (0.3-0.6)：以中性为主
        - 高分歧 (>0.6)：偏向保守
        """
        views = {
            "aggressive": aggressive_view,
            "neutral": neutral_view,
            "conservative": conservative_view,
        }
        
        # 根据分歧度选择主导视角
        if divergence_score < 0.3:
            primary = "aggressive"
            integration_note = "低分歧，偏向激进（追求收益）"
        elif divergence_score > 0.6:
            primary = "conservative"
            integration_note = "高分歧，偏向保守（保护本金）"
        else:
            primary = "neutral"
            integration_note = "中分歧，以中性为主（平衡风险收益）"
        
        primary_view = views[primary]
        
        # 提取整合结果
        direction = self._extract_direction(primary_view)
        direction_str = {1: "LONG", -1: "SHORT", 0: "HOLD"}[direction]
        
        confidence = primary_view.get("confidence", 0.5)
        
        # 仓位调整系数
        position_scale = 1.0 - divergence_score * 0.5
        
        return {
            "direction": direction_str,
            "confidence": confidence,
            "position_scale": position_scale,
            "integration_note": integration_note,
            "primary_perspective": primary,
        }
    
    def _evaluate_evidence(
        self,
        aggressive_view: Dict[str, Any],
        neutral_view: Dict[str, Any],
        conservative_view: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """评估论据可靠性"""
        # 简化实现：返回各视角的论据质量评分
        return [
            {
                "perspective": "aggressive",
                "evidence_quality": aggressive_view.get("confidence", 0.5),
            },
            {
                "perspective": "neutral",
                "evidence_quality": neutral_view.get("confidence", 0.5),
            },
            {
                "perspective": "conservative",
                "evidence_quality": conservative_view.get("confidence", 0.5),
            },
        ]
    
    def _assess_risk_level(
        self,
        divergence_score: float,
        context: MarketContext,
    ) -> str:
        """评估风险水平"""
        # 基于分歧度和市场状态评估风险
        if divergence_score > 0.6:
            return "HIGH"
        elif divergence_score > 0.3:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _generate_warnings(
        self,
        divergence_score: float,
        risk_level: str,
        context: MarketContext,
    ) -> List[str]:
        """生成警告"""
        warnings = []
        
        if divergence_score > 0.5:
            warnings.append(f"三方分歧度较高（{divergence_score:.0%}），建议降低仓位或观望")
        
        if risk_level == "HIGH":
            warnings.append("市场风险水平较高，建议加强风控")
        
        if context.crowding_level in ["HIGH", "CRITICAL"]:
            warnings.append("信号拥挤度较高，部署后表现可能低于预期")
        
        return warnings
