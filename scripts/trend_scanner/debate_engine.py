"""
辩论纠偏器（路径④）

核心机制：
- 鹰派：强调风险、止损、谨慎（通胀紧缩倾向）
- 鸽派：强调机会、趋势、进攻（增长宽松倾向）
- 辩论整合：计算分歧度，分歧度高时降低仓位
- 参考论文：MacroEconomists (Δ Sharpe = +0.044)

设计原则：
- LLM不上硬决策，只做软层
- 控制变量：固定数据管道，只让LLM做辩论
- 可审计性：辩论→分歧度
"""

import json
import time
from typing import Optional, List, Dict

from .reasoning import ReasoningEngine, LLMProvider, WorkBuddyAgentProvider
from .models import MarketContext, ExperienceMatch


# ──────────────────────────────────────────────
# 鹰派/鸽派提示词
# ──────────────────────────────────────────────

HAWK_SYSTEM_PROMPT = """你是一位**鹰派**期货交易分析师。

## 核心倾向
- **通胀紧缩倾向**：关注风险、下行压力、通胀风险
- **谨慎保守**：强调止损、风险控制、仓位管理
- **逆向思维**：在市场乐观时保持警惕，在市场悲观时更加谨慎

## 分析重点
1. **风险识别**：优先识别潜在风险和下行压力
2. **止损设置**：倾向于设置更紧的止损
3. **仓位控制**：倾向于降低仓位，保留现金
4. **逆向信号**：在趋势过度时寻找反转信号

## 输出要求
请以谨慎保守的态度分析市场，强调风险控制。"""

DOVE_SYSTEM_PROMPT = """你是一位**鸽派**期货交易分析师。

## 核心倾向
- **增长宽松倾向**：关注机会、增长动力、宽松政策
- **积极进攻**：强调趋势跟踪、动量交易、仓位配置
- **顺势思维**：在趋势确认时积极跟随，在动量充足时加仓

## 分析重点
1. **机会识别**：优先识别趋势机会和动量信号
2. **趋势跟踪**：倾向于跟随已确认的趋势
3. **仓位配置**：倾向于增加仓位，把握机会
4. **顺势信号**：在趋势确认时积极入场

## 输出要求
请以积极进攻的态度分析市场，强调机会把握。"""


# ──────────────────────────────────────────────
# 辩论推理引擎
# ──────────────────────────────────────────────

class DebateReasoningEngine:
    """
    辩论推理引擎

    通过鹰派/鸽派双视角辩论，修正偏差，提升决策质量。

    参考论文：MacroEconomists (arXiv: 2606.08283)
    - 辩论=偏差修正
    - Δ Sharpe = +0.044
    - 分歧度=置信度
    """

    def __init__(
        self,
        hawk_llm: Optional[LLMProvider] = None,
        dove_llm: Optional[LLMProvider] = None,
    ):
        """
        初始化辩论引擎

        Args:
            hawk_llm: 鹰派LLM提供商
            dove_llm: 鸽派LLM提供商
        """
        self.hawk_llm = hawk_llm or WorkBuddyAgentProvider()
        self.dove_llm = dove_llm or WorkBuddyAgentProvider()

        # 创建鹰派和鸽派的推理引擎
        self.hawk_engine = ReasoningEngine(self.hawk_llm)
        self.dove_engine = ReasoningEngine(self.dove_llm)

    def reason(
        self,
        context: MarketContext,
        similar_experiences: List[ExperienceMatch],
        experience_aggregation: dict,
    ) -> dict:
        """
        执行辩论推理

        Args:
            context: 市场上下文
            similar_experiences: 相似经验
            experience_aggregation: 经验聚合

        Returns:
            辩论结果（包含鹰派、鸽派、分歧度、整合结果）
        """
        start_time = time.time()

        # 1. 鹰派推理
        hawk_result = self._reason_with_role(
            context, similar_experiences, experience_aggregation, 'hawk'
        )

        # 2. 鸽派推理
        dove_result = self._reason_with_role(
            context, similar_experiences, experience_aggregation, 'dove'
        )

        # 3. 计算分歧度
        divergence = self._calculate_divergence(hawk_result, dove_result)

        # 4. 整合辩论结果
        integrated = self._integrate_debate(hawk_result, dove_result, divergence)

        # 5. 添加辩论元信息
        integrated['hawk_result'] = hawk_result
        integrated['dove_result'] = dove_result
        integrated['debate_analysis'] = {
            'divergence': divergence,
            'hawk_confidence': hawk_result.get('confidence', 0.5),
            'dove_confidence': dove_result.get('confidence', 0.5),
            'hawk_action': self._extract_action(hawk_result),
            'dove_action': self._extract_action(dove_result),
            'integration_method': 'divergence_weighted',
        }

        # 6. 分歧度高时降低仓位
        if divergence > 0.3:
            integrated['position_scale'] = 1.0 - divergence
            integrated['warnings'] = integrated.get('warnings', [])
            integrated['warnings'].append(
                f'鹰派鸽派分歧较大（{divergence:.0%}），建议降低仓位'
            )

        # 7. 添加元信息
        integrated['generation_time_ms'] = int((time.time() - start_time) * 1000)
        integrated['reasoning_model'] = f'debate({self.hawk_llm.name},{self.dove_llm.name})'
        integrated['experience_count'] = len(similar_experiences)

        return integrated

    def _reason_with_role(
        self,
        context: MarketContext,
        similar_experiences: List[ExperienceMatch],
        experience_aggregation: dict,
        role: str,
    ) -> dict:
        """
        使用特定角色进行推理

        Args:
            context: 市场上下文
            similar_experiences: 相似经验
            experience_aggregation: 经验聚合
            role: 角色（'hawk' 或 'dove'）

        Returns:
            推理结果
        """
        # 选择对应的引擎
        engine = self.hawk_engine if role == 'hawk' else self.dove_engine

        # 构建角色特定的提示词
        system_prompt = HAWK_SYSTEM_PROMPT if role == 'hawk' else DOVE_SYSTEM_PROMPT

        # 构建用户提示词
        user_prompt = engine._build_user_prompt(
            context, similar_experiences, experience_aggregation
        )

        # 调用LLM
        try:
            llm_response = engine.llm_provider.generate(system_prompt, user_prompt)
        except Exception as e:
            llm_response = engine._emergency_fallback(context)

        # 解析响应
        try:
            parsed = engine._parse_response(llm_response)
        except Exception as e:
            parsed = engine._emergency_fallback(context)

        # 添加角色标记
        parsed['role'] = role

        return parsed

    def _calculate_divergence(self, hawk_result: dict, dove_result: dict) -> float:
        """
        计算鹰派和鸽派的分歧度

        分歧度计算方法：
        1. 比较推荐路线的动作方向
        2. 比较置信度差异
        3. 比较警告数量

        Returns:
            分歧度（0-1，0=完全一致，1=完全对立）
        """
        divergence_factors = []

        # 1. 动作方向分歧
        hawk_action = self._extract_action(hawk_result)
        dove_action = self._extract_action(dove_result)

        hawk_direction = self._action_to_direction(hawk_action)
        dove_direction = self._action_to_direction(dove_action)

        # 方向分歧（0=同向，1=反向）
        direction_divergence = abs(hawk_direction - dove_direction) / 2.0
        divergence_factors.append(direction_divergence)

        # 2. 置信度差异
        hawk_confidence = hawk_result.get('confidence', 0.5)
        dove_confidence = dove_result.get('confidence', 0.5)
        confidence_divergence = abs(hawk_confidence - dove_confidence)
        divergence_factors.append(confidence_divergence)

        # 3. 路线数量差异
        hawk_routes = len(hawk_result.get('routes', []))
        dove_routes = len(dove_result.get('routes', []))
        routes_divergence = abs(hawk_routes - dove_routes) / max(hawk_routes, dove_routes, 1)
        divergence_factors.append(routes_divergence)

        # 加权平均
        weights = [0.5, 0.3, 0.2]  # 方向最重要，置信度次之，路线数量再次
        divergence = sum(d * w for d, w in zip(divergence_factors, weights))

        return min(max(divergence, 0.0), 1.0)

    def _action_to_direction(self, action: str) -> int:
        """
        将动作转换为方向

        Returns:
            1=多头，-1=空头，0=中性
        """
        action_lower = action.lower()

        # 多头关键词
        if any(k in action_lower for k in ['多', 'long', '买入', '加仓', '做多']):
            return 1

        # 空头关键词
        if any(k in action_lower for k in ['空', 'short', '卖出', '减仓', '做空']):
            return -1

        return 0

    def _extract_action(self, result: dict) -> str:
        """提取推荐动作"""
        routes = result.get('routes', [])
        recommended = result.get('recommended_route', '')

        for route in routes:
            if route.get('route_id') == recommended:
                return route.get('action', '')

        # 如果没有推荐，返回第一个路线的动作
        if routes:
            return routes[0].get('action', '')

        return ''

    def _integrate_debate(
        self,
        hawk_result: dict,
        dove_result: dict,
        divergence: float,
    ) -> dict:
        """
        整合鹰派和鸽派的辩论结果

        整合策略：
        - 低分歧（<0.3）：偏向鸽派（积极进攻）
        - 中分歧（0.3-0.6）：综合两者
        - 高分歧（>0.6）：偏向鹰派（谨慎保守）

        Args:
            hawk_result: 鹰派结果
            dove_result: 鸽派结果
            divergence: 分歧度

        Returns:
            整合结果
        """
        # 选择主导方
        if divergence < 0.3:
            # 低分歧：偏向鸽派
            primary = dove_result
            secondary = hawk_result
            integration_note = '低分歧，偏向鸽派（积极进攻）'
        elif divergence > 0.6:
            # 高分歧：偏向鹰派
            primary = hawk_result
            secondary = dove_result
            integration_note = '高分歧，偏向鹰派（谨慎保守）'
        else:
            # 中分歧：综合两者
            # 选择置信度更高的一方
            if hawk_result.get('confidence', 0.5) > dove_result.get('confidence', 0.5):
                primary = hawk_result
                secondary = dove_result
            else:
                primary = dove_result
                secondary = hawk_result
            integration_note = '中分歧，综合两者'

        # 构建整合结果
        integrated = {
            'routes': primary.get('routes', []),
            'recommended_route': primary.get('recommended_route', ''),
            'warnings': primary.get('warnings', []) + secondary.get('warnings', []),
            'confidence': (primary.get('confidence', 0.5) + secondary.get('confidence', 0.5)) / 2,
            'integration_note': integration_note,
        }

        return integrated


# ──────────────────────────────────────────────
# 便捷函数
# ──────────────────────────────────────────────

def create_debate_engine(
    hawk_api_url: str = None,
    hawk_api_key: str = None,
    dove_api_url: str = None,
    dove_api_key: str = None,
) -> DebateReasoningEngine:
    """
    创建辩论引擎

    Args:
        hawk_api_url: 鹰派LLM API URL
        hawk_api_key: 鹰派LLM API Key
        dove_api_url: 鸽派LLM API URL
        dove_api_key: 鸽派LLM API Key

    Returns:
        辩论引擎实例
    """
    from .reasoning import CustomLLMProvider

    hawk_llm = None
    dove_llm = None

    if hawk_api_url and hawk_api_key:
        hawk_llm = CustomLLMProvider(hawk_api_url, hawk_api_key, 'hawk-model')

    if dove_api_url and dove_api_key:
        dove_llm = CustomLLMProvider(dove_api_url, dove_api_key, 'dove-model')

    return DebateReasoningEngine(hawk_llm, dove_llm)
