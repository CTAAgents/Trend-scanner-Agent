"""
推理引擎 —— 系统的大脑

核心理念：推理是一切的上游，规则只是推理的临时产物。
所有约束（止损、仓位、入场条件）均由推理层根据当前市场状态
和历史经验实时推导，而非事先写死。

默认使用 WorkBuddy Agent 调用，后接自定义 LLM。

v3.1 增强：机制门思想
- 引入机制权重，根据当前市场机制动态调整历史经验权重
- 同机制经验权重更高，异机制经验权重更低
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Any

from .models import (
    Constraint,
    ExperienceMatch,
    MarketContext,
)


# ──────────────────────────────────────────────
# LLM Provider 抽象
# ──────────────────────────────────────────────


class LLMProvider(ABC):
    """LLM 提供者抽象基类"""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        调用 LLM 生成响应

        参数:
            system_prompt: 系统提示词
            user_prompt: 用户提示词

        返回:
            LLM 的文本响应
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """提供者名称"""
        pass


class WorkBuddyAgentProvider(LLMProvider):
    """
    WorkBuddy Agent 提供者

    通过 WorkBuddy 的 Agent 系统调用 LLM。
    这是默认的推理提供者。
    """

    def __init__(self, model: str = "default"):
        self.model = model
        self._llm_provider = None

        # 尝试从配置加载LLM提供者
        try:
            self._init_llm_provider()
        except Exception as e:
            print(f"[警告] LLM提供者初始化失败: {e}", flush=True)

    def _init_llm_provider(self):
        """初始化LLM提供者"""
        import json
        from pathlib import Path

        # 尝试加载配置文件
        config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)

            llm_config = config.get("llm", {})
            if llm_config:
                # 尝试创建LLM提供者
                try:
                    from .memory.llm_factory import LLMProviderFactory

                    self._llm_provider = LLMProviderFactory.create(llm_config)
                    print(f"[LLM] 使用 {self._llm_provider.name} 提供者", flush=True)
                except Exception as e:
                    print(f"[LLM] 创建提供者失败: {e}", flush=True)

    @property
    def name(self) -> str:
        if self._llm_provider:
            return f"LLM ({self._llm_provider.name})"
        return f"WorkBuddy Agent ({self.model})"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        通过 WorkBuddy Agent 调用 LLM

        注意：这个方法在实际运行时会被 WorkBuddy 的 Agent 系统接管。
        在独立运行时，它会尝试调用本地 LLM 或返回模拟响应。
        """
        # 如果有LLM提供者，直接调用
        if self._llm_provider:
            try:
                # 构建完整的提示词
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                # 传递max_tokens参数
                return self._llm_provider.generate(full_prompt, max_tokens=2000)
            except Exception as e:
                print(f"[LLM] 调用失败: {e}", flush=True)
                return self._fallback_response(system_prompt, user_prompt)

        # 否则使用fallback
        return self._fallback_response(system_prompt, user_prompt)

    def _call_via_agent(self, system_prompt: str, user_prompt: str) -> str:
        """
        通过 WorkBuddy Agent 调用

        在 WorkBuddy 环境中，这个方法会被 Agent 系统接管。
        """
        # 这里应该调用 WorkBuddy 的 Agent API
        # 暂时使用简单的实现
        raise NotImplementedError("需要在 WorkBuddy 环境中运行")

    def _fallback_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Fallback 响应（当 LLM 不可用时）

        使用规则退化，生成基本的路线建议。
        """
        # 解析用户提示中的关键信息
        lines = user_prompt.split("\n")

        # 提取趋势阶段信息
        trend_phase = "CONSOLIDATING"  # 默认
        for line in lines:
            if "趋势发展" in line or "趋势成熟" in line:
                trend_phase = "DEVELOPING"
            elif "趋势萌芽" in line:
                trend_phase = "EMERGING"
            elif "趋势衰竭" in line:
                trend_phase = "FATIGUING"
            elif "趋势反转" in line:
                trend_phase = "REVERSING"
            elif "横盘整理" in line or "震荡" in line:
                trend_phase = "CONSOLIDATING"

        # 生成基本响应
        return json.dumps(
            {
                "routes": [
                    {
                        "route_id": "A",
                        "name": "观望等待",
                        "action": "暂不操作，等待更明确的信号",
                        "confidence": 0.5,
                        "reasoning": "LLM 不可用，使用规则退化建议",
                        "constraints": [],
                        "risks": ["无法进行深度推理，建议仅供参考"],
                    }
                ],
                "recommended_route": "A",
                "warnings": ["当前使用规则退化模式，建议质量有限"],
            },
            ensure_ascii=False,
        )


class CustomLLMProvider(LLMProvider):
    """
    自定义 LLM 提供者

    支持接入自定义的 LLM API（如 OpenAI、DeepSeek 等）。
    """

    def __init__(self, api_url: str, api_key: str, model: str = "default"):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model

    @property
    def name(self) -> str:
        return f"Custom LLM ({self.model})"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """调用自定义 LLM API"""
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            return json.dumps(
                {
                    "routes": [{"route_id": "A", "name": "错误", "action": f"LLM 调用失败: {e}", "confidence": 0}],
                    "warnings": [f"LLM 调用失败: {e}"],
                },
                ensure_ascii=False,
            )


# ──────────────────────────────────────────────
# 推理引擎
# ──────────────────────────────────────────────


class ReasoningEngine:
    """
    推理引擎 —— 系统的大脑

    职责：
    1. 接收市场上下文和相似经验
    2. 构建推理提示词
    3. 调用 LLM 生成路线建议
    4. 解析和验证 LLM 输出
    5. 生成动态约束
    """

    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm_provider = llm_provider or WorkBuddyAgentProvider()

        # 波动幅度止损锚点（v6.0 新增）
        from .volatility_anchor import VolatilityAnchor

        self.volatility_anchor = VolatilityAnchor(window=20, multiplier=2.0)

    def reason(
        self,
        context: MarketContext,
        similar_experiences: list[ExperienceMatch],
        experience_aggregation: dict,
        multi_dimension_result: dict | None = None,
        trade_history: list[float] | None = None,
        circuit_breaker_status: dict | None = None,
        rl_signal: dict | None = None,
    ) -> dict:
        """
        执行推理

        参数:
            context: 当前市场上下文
            similar_experiences: 相似经验列表
            experience_aggregation: 经验聚合结果
            multi_dimension_result: 多维度筛选评分结果（可选）
            trade_history: 历史交易盈亏列表（可选，用于蒙特卡洛模拟）
            circuit_breaker_status: 熔断器状态（可选）

        返回:
            推理结果（包含操作方案、约束、不确定性等）
        """
        start_time = time.time()

        # 1. 生成基础预测（技术指标层）
        base_prediction = self._generate_base_prediction(context)

        # 2. 构建系统提示词
        system_prompt = self._build_system_prompt()

        # 3. 构建用户提示词
        user_prompt = self._build_user_prompt(
            context,
            similar_experiences,
            experience_aggregation,
            multi_dimension_result=multi_dimension_result,
            trade_history=trade_history,
            circuit_breaker_status=circuit_breaker_status,
            rl_signal=rl_signal,
        )

        # 4. 调用 LLM
        try:
            llm_response = self.llm_provider.generate(system_prompt, user_prompt)
        except Exception:
            llm_response = self._emergency_fallback(context)

        # 5. 解析响应
        try:
            parsed = self._parse_response(llm_response)
        except Exception:
            parsed = self._emergency_fallback(context)

        # 6. 添加元信息
        parsed["generation_time_ms"] = int((time.time() - start_time) * 1000)
        parsed["reasoning_model"] = self.llm_provider.name
        parsed["experience_count"] = len(similar_experiences)

        # 7. 记录修正轨迹（路径②：最后一公里）
        parsed["base_prediction"] = base_prediction
        parsed["llm_revision"] = self._extract_llm_revision(parsed)
        parsed["revision_trace"] = self._build_revision_trace(base_prediction, parsed)

        # 8. 记录分歧度和条件层级（可审计性）
        parsed["divergence"] = self._calculate_divergence(parsed)
        parsed["condition_levels"] = self._extract_condition_levels(parsed)

        return parsed

    def _calculate_divergence(self, parsed: dict) -> dict:
        """
        计算分歧度

        分歧度衡量LLM输出中的不确定性：
        1. 路线分歧：多个路线之间的方向差异
        2. 置信度分歧：推荐路线的置信度
        3. 警告分歧：警告数量

        Returns:
            分歧度字典
        """
        routes = parsed.get("routes", [])
        recommended = parsed.get("recommended_route", "")
        warnings = parsed.get("warnings", [])

        # 1. 路线分歧
        if len(routes) > 1:
            # 提取所有路线的方向
            directions = []
            for route in routes:
                action = route.get("action", "")
                if "多" in action or "LONG" in action.upper():
                    directions.append(1)
                elif "空" in action or "SHORT" in action.upper():
                    directions.append(-1)
                else:
                    directions.append(0)

            # 计算方向分歧（标准差）
            if directions:
                import numpy as np

                direction_std = float(np.std(directions))
            else:
                direction_std = 0.0
        else:
            direction_std = 0.0

        # 2. 置信度分歧
        recommended_confidence = 0.5
        for route in routes:
            if route.get("route_id") == recommended:
                recommended_confidence = route.get("confidence", 0.5)
                break

        # 3. 警告分歧
        warning_count = len(warnings)

        # 综合分歧度
        divergence_score = (
            direction_std * 0.5  # 方向分歧权重50%
            + (1 - recommended_confidence) * 0.3  # 置信度分歧权重30%
            + min(warning_count / 5, 1.0) * 0.2  # 警告分歧权重20%
        )

        return {
            "score": round(divergence_score, 3),
            "direction_std": round(direction_std, 3),
            "recommended_confidence": round(recommended_confidence, 3),
            "warning_count": warning_count,
            "routes_count": len(routes),
            "level": "LOW" if divergence_score < 0.3 else "MEDIUM" if divergence_score < 0.6 else "HIGH",
        }

    def _extract_condition_levels(self, parsed: dict) -> dict:
        """
        提取条件层级

        条件层级衡量反身性框架的条件：
        1. 自我强化程度
        2. 预期反映度
        3. 反身性周期阶段
        4. 反转风险

        Returns:
            条件层级字典
        """
        # 从LLM输出中提取反身性分析
        # 由于LLM输出是JSON，我们需要从文本中提取
        llm_response = parsed.get("llm_response", "")

        # 默认条件层级
        condition_levels = {
            "self_reinforcing": "UNKNOWN",  # 自我强化程度
            "expectation_reflection": "UNKNOWN",  # 预期反映度
            "reflexivity_cycle": "UNKNOWN",  # 反身性周期阶段
            "reversal_risk": "UNKNOWN",  # 反转风险
            "overall": "UNKNOWN",  # 整体条件层级
        }

        # 从路线推理中提取条件信息
        routes = parsed.get("routes", [])
        recommended = parsed.get("recommended_route", "")

        for route in routes:
            if route.get("route_id") == recommended:
                reasoning = route.get("reasoning", "")

                # 分析推理文本中的反身性关键词
                reasoning_lower = reasoning.lower()

                # 自我强化程度
                if any(k in reasoning_lower for k in ["自我强化", "self-reinforc", "加速", "amplif"]):
                    condition_levels["self_reinforcing"] = "HIGH"
                elif any(k in reasoning_lower for k in ["减弱", "衰减", "fade", "weaken"]):
                    condition_levels["self_reinforcing"] = "LOW"
                else:
                    condition_levels["self_reinforcing"] = "MEDIUM"

                # 预期反映度
                if any(k in reasoning_lower for k in ["过度", "overextend", "过热", "overheat"]):
                    condition_levels["expectation_reflection"] = "HIGH"
                elif any(k in reasoning_lower for k in ["不足", "insufficient", "低估", "underestimate"]):
                    condition_levels["expectation_reflection"] = "LOW"
                else:
                    condition_levels["expectation_reflection"] = "MEDIUM"

                # 反身性周期阶段
                if any(k in reasoning_lower for k in ["早期", "early", "初期", "begin"]):
                    condition_levels["reflexivity_cycle"] = "EARLY"
                elif any(k in reasoning_lower for k in ["中期", "middle", "加速", "accelerat"]):
                    condition_levels["reflexivity_cycle"] = "MIDDLE"
                elif any(k in reasoning_lower for k in ["晚期", "late", "末期", "end"]):
                    condition_levels["reflexivity_cycle"] = "LATE"
                else:
                    condition_levels["reflexivity_cycle"] = "UNKNOWN"

                # 反转风险
                if any(k in reasoning_lower for k in ["反转", "reversal", "崩盘", "crash"]):
                    condition_levels["reversal_risk"] = "HIGH"
                elif any(k in reasoning_lower for k in ["稳定", "stable", "持续", "continu"]):
                    condition_levels["reversal_risk"] = "LOW"
                else:
                    condition_levels["reversal_risk"] = "MEDIUM"

                break

        # 整体条件层级
        risk_levels = ["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
        risk_scores = {level: i for i, level in enumerate(risk_levels)}

        # 计算整体风险分数
        total_score = 0
        count = 0
        for key in ["self_reinforcing", "expectation_reflection", "reversal_risk"]:
            level = condition_levels[key]
            if level in risk_scores:
                total_score += risk_scores[level]
                count += 1

        if count > 0:
            avg_score = total_score / count
            if avg_score < 1.0:
                condition_levels["overall"] = "LOW"
            elif avg_score < 2.0:
                condition_levels["overall"] = "MEDIUM"
            else:
                condition_levels["overall"] = "HIGH"

        return condition_levels

    def _generate_base_prediction(self, context: MarketContext) -> dict:
        """
        生成基础预测（技术指标层）

        基于市场上下文的技术指标，生成一个纯粹的"基础预测"。
        这个预测不经过LLM推理，只基于规则和指标。

        这是路径②中的"基础模型预测"，LLM在此之上做"最后一公里修正"。
        """
        # 从趋势阶段推导基础方向
        phase = context.trend_phase.phase if hasattr(context, "trend_phase") else "UNKNOWN"
        confidence = context.trend_phase.confidence if hasattr(context, "trend_phase") else 0.5

        # 基于阶段的基础信号
        phase_signal_map = {
            "CONSOLIDATING": {"direction": 0, "signal": "HOLD", "strength": "NEUTRAL"},
            "EMERGING": {"direction": 0, "signal": "WATCH", "strength": "WEAK"},
            "DEVELOPING": {"direction": 1, "signal": "BUY", "strength": "MEDIUM"},
            "MATURE": {"direction": 1, "signal": "HOLD_LONG", "strength": "STRONG"},
            "FATIGUING": {"direction": 0, "signal": "REDUCE", "strength": "WEAK"},
            "REVERSING": {"direction": -1, "signal": "SELL", "strength": "MEDIUM"},
        }

        base = phase_signal_map.get(phase, {"direction": 0, "signal": "UNKNOWN", "strength": "NEUTRAL"})

        # 添加上下文信息
        base["trend_phase"] = phase
        base["phase_confidence"] = confidence
        base["current_price"] = context.current_price if hasattr(context, "current_price") else 0

        # 添加市场结构信息（如果有）
        if hasattr(context, "snapshot") and context.snapshot:
            base["volatility"] = (
                "HIGH" if context.snapshot.high - context.snapshot.low > context.current_price * 0.02 else "NORMAL"
            )

        return base

    def _extract_llm_revision(self, parsed: dict) -> dict:
        """
        从LLM输出中提取修正信息

        提取LLM对基础预测的修正内容。
        """
        revision = {
            "routes_count": len(parsed.get("routes", [])),
            "recommended_route": parsed.get("recommended_route", ""),
            "warnings": parsed.get("warnings", []),
            "has_recommendation": bool(parsed.get("recommended_route")),
        }

        # 提取推荐路线的详细信息
        routes = parsed.get("routes", [])
        if routes and parsed.get("recommended_route"):
            for route in routes:
                if route.get("route_id") == parsed["recommended_route"]:
                    revision["recommended_action"] = route.get("action", "")
                    revision["recommended_confidence"] = route.get("confidence", 0)
                    revision["recommended_reasoning"] = route.get("reasoning", "")
                    break

        return revision

    def _calculate_volatility_anchor(self, context: MarketContext) -> dict[str, Any] | None:
        """
        计算波动幅度止损锚点

        Args:
            context: 市场上下文

        Returns:
            锚点信息字典，如果计算失败返回 None
        """
        try:
            # 从上下文中获取价格数据
            # 注意：这里使用上下文中的指标数据来估算
            snapshot = context.snapshot

            # 获取当前价格
            current_price = snapshot.close if hasattr(snapshot, "close") else None
            if current_price is None:
                return None

            # 使用 ATR 作为波动幅度的近似值
            # ATR 是 Average True Range，与 K 线高度类似
            atr = snapshot.atr if hasattr(snapshot, "atr") else None
            if atr is None:
                return None

            # 计算锚点距离（ATR * 2.0）
            anchor_distance = atr * 2.0
            anchor_distance_pct = anchor_distance / current_price * 100

            # 计算多头和空头止损
            long_stop_loss = current_price - anchor_distance
            short_stop_loss = current_price + anchor_distance

            return {
                "current_price": current_price,
                "median_height": atr,  # 使用 ATR 近似
                "anchor_distance": anchor_distance,
                "anchor_distance_pct": anchor_distance_pct,
                "long_stop_loss": long_stop_loss,
                "short_stop_loss": short_stop_loss,
            }
        except Exception as e:
            logger.warning(f"计算波动幅度锚点失败: {e}")
            return None

    def _build_revision_trace(self, base_prediction: dict, parsed: dict) -> dict:
        """
        构建修正轨迹

        记录基础预测和LLM修正之间的差异，用于可审计性。
        """
        llm_revision = parsed.get("llm_revision", {})
        recommended_action = llm_revision.get("recommended_action", "")

        # 判断LLM是否修正了基础预测
        base_signal = base_prediction.get("signal", "UNKNOWN")
        base_direction = base_prediction.get("direction", 0)

        # 从LLM推荐动作推断方向
        llm_direction = 0
        if "多" in recommended_action or "LONG" in recommended_action.upper():
            llm_direction = 1
        elif "空" in recommended_action or "SHORT" in recommended_action.upper():
            llm_direction = -1

        # 计算修正幅度
        revision_magnitude = abs(llm_direction - base_direction)

        # 判断修正类型
        if revision_magnitude == 0:
            revision_type = "CONFIRM"  # LLM确认基础预测
        elif llm_direction == 0:
            revision_type = "SOFTEN"  # LLM降低信号强度
        else:
            revision_type = "REVERSE"  # LLM反转信号

        trace = {
            "base_signal": base_signal,
            "base_direction": base_direction,
            "llm_direction": llm_direction,
            "revision_type": revision_type,
            "revision_magnitude": revision_magnitude,
            "base_confidence": base_prediction.get("phase_confidence", 0.5),
            "llm_confidence": llm_revision.get("recommended_confidence", 0),
            "confidence_change": llm_revision.get("recommended_confidence", 0)
            - base_prediction.get("phase_confidence", 0.5),
            "warnings_count": len(llm_revision.get("warnings", [])),
        }

        return trace

    # ──────────────────────────────────────────
    # 提示词构建
    # ──────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一位资深期货交易分析师。你的职责是提供态势研判、风险提示与操作建议，最终决策权在交易者手中。

## 核心原则

1. **推理优先**：所有建议都必须基于对当前市场状态的理解和推理，而非固定规则。
2. **以人为本**：提供选项和代价，不替人做决定。
3. **可解释性**：每个建议都必须附带推理依据。
4. **不确定性诚实**：明确标注置信度和不确定性区间。

## 输出格式

请以 JSON 格式输出，包含以下字段：

```json
{
    "routes": [
        {
            "route_id": "A",
            "name": "路线名称（如：顺势做多）",
            "action": "具体动作描述",
            "confidence": 0.75,
            "reasoning": "详细的推理过程",
            "constraints": [
                {
                    "constraint_type": "POSITION_SIZE",
                    "value": "建议仓位描述",
                    "numeric_value": 0.05,
                    "confidence": 0.7,
                    "reasoning": "约束的推理依据",
                    "historical_basis": "历史依据",
                    "uncertainty_range": "不确定性区间"
                }
            ],
            "risks": ["风险1", "风险2"],
            "trigger_conditions": ["触发条件1"],
            "opportunity_cost": "不选这条路的代价",
            "historical_analog": "历史类比描述",
            "historical_outcome": "历史结果"
        }
    ],
    "recommended_route": "A",
    "warnings": ["警告1"],
    "reasoning_summary": "整体推理总结"
}
```

## 重要提醒

- 不要机械地读指标数字，要理解它们在当前市场环境下的含义
- 考虑市场结构、动量状态、波动率的综合影响
- 历史经验只是参考，不是预测——市场每次都不一样
- 如果不确定性很高，诚实地说出来"""

    def _build_user_prompt(
        self,
        context: MarketContext,
        similar_experiences: list[ExperienceMatch],
        experience_aggregation: dict,
        multi_dimension_result: dict | None = None,
        trade_history: list[float] | None = None,
        circuit_breaker_status: dict | None = None,
        rl_signal: dict | None = None,
    ) -> str:
        """
        构建用户提示词

        v3.1 增强：添加机制权重信息
        """
        parts = []

        # 1. 市场上下文
        parts.append("# 当前市场状态")
        parts.append(context.to_prompt_text())
        parts.append("")

        # 1.5 基本面信息（v1.0 新增）
        if hasattr(context, 'fundamental') and context.fundamental:
            fundamental = context.fundamental
            if fundamental.news_events or fundamental.geopolitical_risks:
                parts.append("# 基本面信息")
                parts.append(fundamental.to_prompt_text())
                parts.append("")
                
                # 特别提醒地缘政治风险
                if fundamental.geopolitical_risk_level == "high":
                    parts.append("**重要提醒**：当前存在高地缘政治风险，请特别关注！")
                    parts.append("")

        # 2. 机制权重分析（v3.1 新增）
        current_phase = context.trend_phase.phase if hasattr(context, "trend_phase") else "UNKNOWN"
        phase_confidence = context.trend_phase.confidence if hasattr(context, "trend_phase") else 0.5

        parts.append("# 机制权重分析")
        parts.append(f"当前市场机制：**{current_phase}**（置信度 {phase_confidence:.0%}）")
        parts.append("")

        # 统计同机制和异机制经验
        if similar_experiences:
            same_regime = [m for m in similar_experiences if m.experience.trend_phase == current_phase]
            cross_regime = [m for m in similar_experiences if m.experience.trend_phase != current_phase]

            parts.append("## 经验分布")
            parts.append(f"- 同机制经验（{current_phase}）：{len(same_regime)} 条")
            parts.append(f"- 异机制经验：{len(cross_regime)} 条")
            parts.append("")

            # 权重建议
            if len(same_regime) >= 3:
                parts.append("**建议**：同机制经验充足，优先参考同机制经验。")
            elif len(same_regime) >= 1:
                parts.append("**建议**：同机制经验有限，结合异机制经验综合判断。")
            else:
                parts.append("**建议**：无同机制经验，谨慎参考异机制经验，注意机制差异。")
            parts.append("")

        # 3. 相似历史经验
        if similar_experiences:
            parts.append("# 相似历史经验")
            parts.append(f"共找到 {len(similar_experiences)} 条相似情境：")
            parts.append("")

            for i, match in enumerate(similar_experiences[:5], 1):
                exp = match.experience
                # 标记是否为同机制
                regime_marker = "【同机制】" if exp.trend_phase == current_phase else "【异机制】"

                parts.append(f"## 经验{i}（相似度{int(match.similarity * 100)}%）{regime_marker}")
                parts.append(f"- 时间：{exp.timestamp}")
                parts.append(f"- 趋势阶段：{exp.trend_phase}")
                parts.append(f"- 动作：{exp.action_taken}")
                parts.append(f"- 结果：收益{exp.pnl_pct:+.2f}%，持仓{exp.holding_days}天")
                parts.append(f"- 最大回撤：{exp.max_drawdown_pct:.2f}%")
                if exp.action_reasoning:
                    parts.append(f"- 当时推理：{exp.action_reasoning}")
                parts.append("")

        # 4. 经验聚合统计
        if experience_aggregation:
            parts.append("# 经验聚合统计")
            for action, stats in experience_aggregation.items():
                parts.append(
                    f"- {action}：{stats['count']}次，"
                    f"平均收益{stats['avg_return']:+.2f}%，"
                    f"胜率{int(stats['win_rate'] * 100)}%，"
                    f"风险调整收益{stats['risk_adjusted_return']:+.2f}"
                )
            parts.append("")

        # 5. 反身性分析框架（v3.2 新增）
        parts.append("# 反身性分析框架")
        parts.append("请考虑以下反身性（Reflexivity）问题，这是市场参与者的认知与市场价格之间的自我强化循环：")
        parts.append("")
        parts.append("## 自我强化循环")
        parts.append("当前趋势是否在自我强化？")
        parts.append("- 上升趋势：价格上涨 → 乐观情绪 → 更多买入 → 价格继续上涨")
        parts.append("- 下降趋势：价格下跌 → 恐慌情绪 → 更多卖出 → 价格继续下跌")
        parts.append("")
        parts.append("## 预期反映度")
        parts.append("市场参与者的预期是否已经过度反映在价格中？")
        parts.append("- 如果预期已充分反映，趋势可能接近反转")
        parts.append("- 如果预期尚未充分反映，趋势可能继续")
        parts.append("")
        parts.append("## 反身性周期阶段")
        parts.append("当前处于反身性周期的哪个阶段？")
        parts.append("- 早期：趋势刚刚开始自我强化，参与者认知尚未一致")
        parts.append("- 中期：趋势正在加速自我强化，参与者认知趋于一致")
        parts.append("- 晚期：趋势可能即将反转，参与者认知高度一致（过度乐观/悲观）")
        parts.append("")
        parts.append("## 反转风险")
        parts.append("如果当前趋势反转，反身性循环会如何加速崩盘？")
        parts.append("- 上升趋势反转：止损触发 → 强制平仓 → 价格加速下跌 → 更多止损")
        parts.append("- 下降趋势反转：空头回补 → 价格反弹 → 更多空头回补 → 价格加速上涨")

        # 6. 波动幅度止损锚点（v6.0 新增）
        try:
            anchor_info = self._calculate_volatility_anchor(context)
            if anchor_info:
                parts.append("")
                parts.append("# 波动幅度止损锚点（参考值）")
                parts.append("基于近期市场波动计算的止损参考锚点，可作为止损位置的参考：")
                parts.append("")
                parts.append(f"- **当前价格**: {anchor_info['current_price']:.2f}")
                parts.append(f"- **波动幅度中位数**: {anchor_info['median_height']:.2f}")
                parts.append(
                    f"- **止损锚点距离**: {anchor_info['anchor_distance']:.2f}（{anchor_info['anchor_distance_pct']:.2f}%）"
                )
                parts.append(f"- **多头止损参考**: {anchor_info['long_stop_loss']:.2f}")
                parts.append(f"- **空头止损参考**: {anchor_info['short_stop_loss']:.2f}")
                parts.append("")
                parts.append("**说明**：止损锚点是基于近期 K 线波动幅度中位数 × 2.0 计算的参考值。")
                parts.append("你可以根据当前市场状态、趋势强度和反身性分析，动态调整止损位置。")
        except Exception as e:
            logger.warning(f"计算波动幅度锚点失败: {e}")

        # 7. 基差与季节性分析（统一路由层新增）
        try:
            symbol_variety = getattr(context, "symbol", "") or ""
            # 提取品种代码
            variety = (
                "".join([c for c in symbol_variety.split(".")[-1] if not c.isdigit()]).upper() if symbol_variety else ""
            )

            if variety:
                from trend_scanner.unified_data_router import get_router

                router = get_router()

                # 基差数据
                basis_resp = router.get_basis(variety)
                if basis_resp.ok and basis_resp.data:
                    bd = basis_resp.data
                    parts.append("")
                    parts.append("# 基差分析")
                    parts.append(f"- **现货价格**: {bd.get('spot_price', 'N/A')}")
                    parts.append(f"- **期货价格**: {bd.get('futures_price', 'N/A')}")
                    parts.append(f"- **基差**: {bd.get('basis', 'N/A')}（基差率 {bd.get('basis_rate', 'N/A')}%）")
                    if bd.get("basis", 0) > 0:
                        parts.append("**解读**：正基差（现货升水），反映现货偏紧或市场看涨预期。")
                    elif bd.get("basis", 0) < 0:
                        parts.append("**解读**：负基差（期货升水），反映库存充足或市场看跌预期。")

                # 季节性数据
                season_resp = router.get_seasonality(variety)
                if season_resp.ok and season_resp.data:
                    sd = season_resp.data
                    parts.append("")
                    parts.append("# 季节性规律")
                    current_month = datetime.now().month
                    current_signal = sd.get("current_month_signal", 0)
                    current_pos_rate = sd.get("current_month_pos_rate", 0)
                    parts.append(
                        f"- **当前月份({current_month}月)**: 历史平均变化 {current_signal:+.2f}%, 上涨概率 {current_pos_rate:.0f}%"
                    )
                    if sd.get("strong_months"):
                        parts.append(f"- **强势月份**: {sd['strong_months']}月（历史上涨概率>60%）")
                    if sd.get("weak_months"):
                        parts.append(f"- **弱势月份**: {sd['weak_months']}月（历史下跌概率>60%）")
                    parts.append(f"- **数据覆盖**: 近{sd.get('years_covered', 5)}年")
                    parts.append("**说明**：季节性规律是统计参考，不构成确定性预测。需结合当前供需格局判断。")
        except Exception as e:
            logger.debug(f"基差/季节性数据注入失败: {e}")

        # 7.5 知识锚点注入（v6.1 新增）
        try:
            import os

            from trend_scanner.knowledge_anchors import KnowledgeAnchorManager

            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "meta.db")
            if os.path.exists(db_path):
                anchor_mgr = KnowledgeAnchorManager(db_path)
                # 自动导入默认锚点（如果表为空）
                stats = anchor_mgr.get_statistics()
                if stats.get("total_anchors", 0) == 0:
                    anchor_mgr.seed_default_anchors()

                # 获取与当前趋势阶段相关的锚点
                phase = current_phase if current_phase != "UNKNOWN" else None
                dimension_map = {
                    "TREND_UP": "trend",
                    "TREND_DOWN": "trend",
                    "RANGE": "volatility",
                }
                target_dim = dimension_map.get(current_phase)

                # 获取相关锚点种子
                seeds = anchor_mgr.get_factor_seeds_for_llm(dimension=target_dim)
                if seeds:
                    parts.append("")
                    parts.append("# 知识锚点参考（因子种子）")
                    parts.append("以下是与当前市场状态相关的分析方法论和因子种子，供推理参考：")
                    parts.append("")
                    for s in seeds[:5]:  # 最多5个
                        parts.append(f"### {s['title']}（{s['dimension']}）")
                        parts.append(f"- **核心逻辑**: {s['core_logic']}")
                        if s.get("factor_seeds"):
                            parts.append(f"- **因子种子**: {', '.join(fs['name'] for fs in s['factor_seeds'][:3])}")
                        parts.append(
                            f"- **验证规则**: IC≥{s['validation_rules'].get('min_ic', 0)}, 胜率≥{s['validation_rules'].get('min_win_rate', 0):.0%}"
                        )
                        parts.append("")
                    parts.append("**说明**: 知识锚点是经过验证的分析方法论，可作为推理的参考框架。")
        except Exception as e:
            logger.debug(f"知识锚点注入失败: {e}")

        # 8. 多维度筛选评分（v5.1 新增）
        if multi_dimension_result:
            try:
                md = multi_dimension_result
                parts.append("")
                parts.append("# 多维度筛选评分（五维度）")
                parts.append("基于 Trend/Momentum/Volume/Volatility/Channel 五个维度的综合评分：")
                parts.append("")

                # 整体概览
                overall = md.get("overall_score", 0)
                confidence = md.get("confidence", 0)
                signal = md.get("signal", "NEUTRAL")
                parts.append(f"- **综合得分**: {overall:+.3f} (范围: -1.0 ~ +1.0)")
                parts.append(f"- **信号方向**: {signal}")
                parts.append(f"- **置信度**: {confidence:.0%}")
                parts.append("")

                # 各维度明细
                dims = md.get("dimensions", [])
                if dims:
                    parts.append("## 维度明细")
                    for d in dims:
                        name = d.get("name", "?")
                        composite = d.get("composite", 0)
                        direction = d.get("direction", "NEUTRAL")
                        weight = d.get("weight", 0)
                        dim_conf = d.get("confidence", 0)

                        # 方向标记
                        if direction == "BULLISH":
                            arrow = "↑"
                        elif direction == "BEARISH":
                            arrow = "↓"
                        else:
                            arrow = "→"

                        parts.append(
                            f"- **{name}** (权重{weight:.0%}): "
                            f"{composite:+.3f} {arrow} {direction} "
                            f"[置信度{dim_conf:.0%}]"
                        )

                        # 各维度关键指标得分
                        ind_scores = d.get("indicator_scores", {})
                        if ind_scores:
                            top3 = sorted(ind_scores.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
                            parts.append("  关键指标: " + ", ".join(f"{k}={v:+.2f}" for k, v in top3))
                    parts.append("")

                # 维度间一致性
                if len(dims) >= 2:
                    directions = [d.get("direction", "NEUTRAL") for d in dims]
                    bullish_count = sum(1 for d in directions if d == "BULLISH")
                    bearish_count = sum(1 for d in directions if d == "BEARISH")
                    total = len(directions)

                    if bullish_count >= total * 0.6:
                        parts.append(f"**维度一致性**: 偏多共识 ({bullish_count}/{total} 维度看多)")
                    elif bearish_count >= total * 0.6:
                        parts.append(f"**维度一致性**: 偏空共识 ({bearish_count}/{total} 维度看空)")
                    else:
                        parts.append(
                            "**维度一致性**: 分歧较大 "
                            f"(多{bullish_count}/空{bearish_count}/中{total - bullish_count - bearish_count})"
                        )
                    parts.append("")

                # 量能特别提示
                vol_dim = None
                for d in dims:
                    if d.get("name") == "volume":
                        vol_dim = d
                        break
                if vol_dim:
                    vol_composite = vol_dim.get("composite", 0)
                    vol_direction = vol_dim.get("direction", "NEUTRAL")
                    if vol_composite > 0.4:
                        parts.append(
                            f"**量能提示**: 成交量结构明显偏多，建议确认是否为趋势突破放量 (score={vol_composite:+.3f})"
                        )
                    elif vol_composite < -0.4:
                        parts.append(
                            f"**量能提示**: 成交量结构明显偏空，注意是否为趋势衰竭缩量 (score={vol_composite:+.3f})"
                        )
                    parts.append("")

            except Exception as e:
                logger.warning(f"注入多维度评分失败: {e}")

        # 8.2 RL 策略信号（新增）
        if rl_signal:
            try:
                parts.append("")
                parts.append("# RL 策略信号")
                parts.append("基于强化学习（PPO）策略的信号，作为传统技术指标的补充参考：")
                parts.append("")
                
                # 信号概览
                rl_direction = rl_signal.get('direction', 'NEUTRAL')
                rl_strength = rl_signal.get('strength', 0)
                rl_confidence = rl_signal.get('confidence', 0)
                rl_source = rl_signal.get('source', 'rl')
                
                # 方向标记
                if rl_direction == 'LONG':
                    direction_mark = '↑ 做多'
                elif rl_direction == 'SHORT':
                    direction_mark = '↓ 做空'
                else:
                    direction_mark = '→ 中性'
                
                parts.append(f"- **信号方向**: {direction_mark}")
                parts.append(f"- **信号强度**: {rl_strength:.2f} (范围: 0~1)")
                parts.append(f"- **置信度**: {rl_confidence:.0%}")
                parts.append(f"- **信号来源**: {rl_source}")
                parts.append("")
                
                # 集成信息（如果有）
                if rl_source == 'rl_ensemble':
                    consistency = rl_signal.get('consistency', 0)
                    n_models = rl_signal.get('n_models', 0)
                    parts.append("## 集成模型信息")
                    parts.append(f"- **模型数量**: {n_models} 个")
                    parts.append(f"- **一致性**: {consistency:.0%}")
                    
                    if consistency > 0.8:
                        parts.append("- **评价**: 模型高度一致，信号可靠")
                    elif consistency > 0.5:
                        parts.append("- **评价**: 模型中等一致，信号有一定参考价值")
                    else:
                        parts.append("- **评价**: 模型分歧较大，信号需谨慎参考")
                    parts.append("")
                
                # 与传统信号对比
                parts.append("## 与传统信号对比")
                parts.append("RL 信号与传统技术指标信号的对比：")
                parts.append("- 传统信号基于规则（ER、TSI、R²等阈值判断）")
                parts.append("- RL 信号基于历史数据学习的模式识别")
                parts.append("- 两者一致时信号更可靠，冲突时建议谨慎")
                parts.append("")
                
                # 使用建议
                parts.append("## 使用建议")
                if rl_confidence > 0.7:
                    parts.append("- RL 信号置信度较高，可作为重要参考")
                elif rl_confidence > 0.4:
                    parts.append("- RL 信号置信度中等，建议结合其他指标综合判断")
                else:
                    parts.append("- RL 信号置信度较低，建议主要参考传统指标")
                
                if rl_strength > 0.5:
                    parts.append("- RL 信号强度较高，建议关注")
                else:
                    parts.append("- RL 信号强度一般，可作为辅助参考")
                    
            except Exception as e:
                logger.warning(f"注入 RL 信号失败: {e}")

        # 8.3 场景分析（v0.2.0 新增 - 借鉴 ai-investment-skills）
        try:
            from trend_scanner.scenario_analyzer import ScenarioAnalyzer

            # 获取关键指标
            er = getattr(context, "er", 0.5)
            tsi = getattr(context, "tsi", 0)
            rsi = getattr(context, "rsi", 50)
            trend_strength = getattr(context, "trend_strength_composite", 0)
            current_price = getattr(context, "current_price", 0)
            symbol = getattr(context, "symbol", "")

            if current_price > 0:
                analyzer = ScenarioAnalyzer()
                scenario_result = analyzer.analyze(
                    symbol=symbol,
                    current_price=current_price,
                    indicators={
                        "er": er,
                        "tsi": tsi,
                        "rsi": rsi,
                        "trend_strength_composite": trend_strength,
                        "r_squared": getattr(context, "r_squared", 0.5),
                    },
                    trend_phase=current_phase,
                    volatility=0.02,  # 默认波动率
                )

                parts.append("")
                parts.append("# 概率加权场景分析")
                parts.append("基于当前市场状态构建的三个可能情景及其预期价值：")
                parts.append("")

                for s in scenario_result.scenarios:
                    emoji = "📈" if s.name == "bull" else ("➡️" if s.name == "base" else "📉")
                    parts.append(
                        f"- {emoji} **{s.name.upper()}** ({s.probability:.0%}): "
                        f"{s.target_price:.2f} ({s.expected_return:+.1f}%) "
                        f"[{s.confidence}]"
                    )
                    parts.append(f"  触发条件: {s.catalyst}")

                parts.append("")
                parts.append(f"- **加权 EV**: {scenario_result.weighted_ev:+.1f}%")
                parts.append(f"- **风险收益比**: {scenario_result.risk_reward_ratio:.1f}")
                parts.append(f"- **整体置信度**: {scenario_result.overall_confidence}")
                parts.append(f"- **推荐**: {scenario_result.recommendation}")
                parts.append("")
                parts.append(
                    "**说明**: EV（预期价值）是概率加权的预期收益率。"
                    "正 EV 表示长期来看该方向有利可图，但不保证单次交易盈利。"
                )
        except Exception as e:
            logger.debug(f"场景分析失败: {e}")

        # 8.4 蒙特卡洛模拟（Davey Step 5）
        if trade_history and len(trade_history) >= 3:
            try:
                from trend_scanner.monte_carlo import MonteCarloSimulator

                sim = MonteCarloSimulator(n_simulations=1000, random_seed=42)
                mc_result = sim.simulate(trade_history, initial_capital=100000)

                parts.append("")
                parts.append("# 蒙特卡洛模拟（风险评估）")
                parts.append("基于历史交易结果的1000次随机重排模拟，评估最坏情况：")
                parts.append("")
                parts.append(f"- **破产概率**: {mc_result.ruin_probability:.2%}")
                parts.append(f"- **预期最大回撤（中位数）**: {mc_result.max_drawdown_median:.2%}")
                parts.append(f"- **95%置信回撤**: {mc_result.max_drawdown_95:.2%}")
                parts.append(f"- **99%置信回撤**: {mc_result.max_drawdown_99:.2%}")
                parts.append(f"- **最差情景**: 资金降至{mc_result.worst_case.get('final_capital', 0):.0f}")

                if mc_result.ruin_probability > 0.1:
                    parts.append("")
                    parts.append("**风险警告**: 破产概率超过10%，建议降低仓位或暂停交易。")
                elif mc_result.max_drawdown_95 > 0.3:
                    parts.append("")
                    parts.append("**风险警告**: 95%置信回撤超过30%，注意资金管理。")
            except Exception as e:
                logger.debug(f"蒙特卡洛模拟失败: {e}")

        # 8.5 熔断器状态（Davey Step 7）
        if circuit_breaker_status:
            try:
                is_paused = circuit_breaker_status.get("is_paused", False)
                if is_paused:
                    parts.append("")
                    parts.append("# 策略熔断状态")
                    parts.append("**该策略已触发熔断，当前处于暂停交易状态。**")
                    parts.append(f"- 暂停原因: {circuit_breaker_status.get('pause_reason', '未知')}")
                    parts.append(f"- 累计亏损: {circuit_breaker_status.get('total_loss', 0):.0f}")
                    parts.append(f"- 最大回撤: {circuit_breaker_status.get('max_drawdown', 0):.2%}")
                    parts.append(f"- 连续亏损: {circuit_breaker_status.get('consecutive_losses', 0)}次")
                    parts.append("")
                    parts.append("**建议**: 等待冷却期结束或手动重置后再考虑交易。")
                else:
                    # 未熔断，但提供风险指标
                    total_loss = circuit_breaker_status.get("total_loss", 0)
                    max_dd = circuit_breaker_status.get("max_drawdown", 0)
                    consec = circuit_breaker_status.get("consecutive_losses", 0)

                    if total_loss < 0 or max_dd > 0.1 or consec >= 3:
                        parts.append("")
                        parts.append("# 风控指标")
                        parts.append("当前策略的风控指标提醒：")
                        if total_loss < 0:
                            parts.append(f"- 累计亏损: {abs(total_loss):.0f}")
                        if max_dd > 0.1:
                            parts.append(f"- 最大回撤: {max_dd:.2%}")
                        if consec >= 3:
                            parts.append(f"- 连续亏损: {consec}次")
                        parts.append("**建议**: 关注风控指标，必要时降低仓位。")
            except Exception as e:
                logger.debug(f"熔断器状态注入失败: {e}")

        # 9. 请求推理
        parts.append("")
        parts.append("# 请求")
        parts.append(
            "基于以上市场状态、历史经验、反身性分析、波动幅度锚点、基差和季节性数据"
            + ("、多维度筛选评分" if multi_dimension_result else "")
            + "，请给出2-3条操作方案。"
        )
        parts.append("每条方案都要有具体的约束建议（仓位、止损、入场条件），并附带推理依据。")
        parts.append("如果有明确推荐，请说明理由。")
        parts.append("")
        parts.append("**特别注意**：")
        parts.append("1. 请考虑机制权重，优先参考同机制的历史经验。")
        parts.append("2. 请结合反身性分析，评估当前趋势的自我强化程度和反转风险。")
        parts.append("3. 波动幅度止损锚点是参考值，你可以根据市场状态动态调整止损位置。")
        parts.append("4. 基差和季节性是补充维度，可辅助判断供需格局和时机选择。")
        if multi_dimension_result:
            parts.append(
                "5. 多维度评分是五维度综合结果，重点关注维度间一致性。当维度一致性高时信号更可靠；分歧大时建议谨慎。"
            )

        # 10. 反叙事约束（v0.2.0 新增 - 借鉴 ai-investment-skills）
        parts.append("")
        parts.append("# 反叙事约束（质量控制）")
        parts.append("以下规则强制执行，防止构建误导性市场叙事：")
        parts.append("")
        parts.append("## 1. 数字优于叙事")
        parts.append("- **必须**用具体数字描述市场状态，禁止模糊表述")
        parts.append("- 正确示例：'ER=0.65, TSI=25.3, RSI=58'")
        parts.append("- 错误示例：'趋势强劲'、'动量充足'、'超买'")
        parts.append("")
        parts.append("## 2. 交叉验证")
        parts.append("- 任何价格/指标主张必须有 2+ 数据源支持")
        parts.append("- 如果数据源不一致，必须说明差异并给出判断依据")
        parts.append("- 禁止单一数据源支撑的确定性结论")
        parts.append("")
        parts.append("## 3. 禁止叙事重复")
        parts.append("- 每次分析必须基于当前数据，禁止复制粘贴之前的分析")
        parts.append("- 如果市场状态相似，必须指出与上次分析的差异点")
        parts.append("- 禁止使用'如前所述'、'之前分析过'等表述")
        parts.append("")
        parts.append("## 4. 卖出检查清单")
        parts.append("- 禁止恐慌性卖出，必须先检查：")
        parts.append("  a) 是否触底？（技术指标是否超卖）")
        parts.append("  b) 是否有新催化剂？（基本面是否恶化）")
        parts.append("  c) 止损逻辑是否仍然有效？")
        parts.append("  d) 仓位大小是否合理？")
        parts.append("")
        parts.append("## 5. 置信度透明")
        parts.append("- 每个操作方案必须附带置信度评估（高/中/低）")
        parts.append("- 低置信度方案必须说明原因（数据不足、指标矛盾等）")
        parts.append("- 禁止对不确定的结论给出高置信度")

        return "\n".join(parts)

    # ──────────────────────────────────────────
    # 响应解析
    # ──────────────────────────────────────────

    def _parse_response(self, response: str) -> dict:
        """解析 LLM 响应"""
        # 尝试提取 JSON
        json_str = self._extract_json(response)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # 如果不是 JSON，尝试从文本中提取关键信息
            data = self._extract_from_text(response)

        # 验证和规范化
        return self._validate_response(data)

    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON"""
        # 尝试找到 JSON 块
        import re

        # 找 ```json ... ``` 块
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            return json_match.group(1)

        # 找 { ... } 块
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            return brace_match.group(0)

        return text

    def _extract_from_text(self, text: str) -> dict:
        """从纯文本中提取结构化信息（fallback）"""
        return {
            "routes": [
                {
                    "route_id": "A",
                    "name": "基于文本分析",
                    "action": "请参考推理文本",
                    "confidence": 0.5,
                    "reasoning": text[:500],
                    "constraints": [],
                    "risks": ["文本解析不完整"],
                }
            ],
            "recommended_route": "A",
            "warnings": ["LLM 响应格式不标准，已降级处理"],
            "reasoning_summary": text[:200],
        }

    def _validate_response(self, data: dict) -> dict:
        """验证和规范化响应"""
        # 确保 routes 存在
        if "routes" not in data:
            data["routes"] = []

        # 确保每个 route 有必要的字段
        for route in data["routes"]:
            if "route_id" not in route:
                route["route_id"] = "A"
            if "name" not in route:
                route["name"] = "未命名路线"
            if "action" not in route:
                route["action"] = "无操作"
            if "confidence" not in route:
                route["confidence"] = 0.5
            if "reasoning" not in route:
                route["reasoning"] = "无推理"
            if "constraints" not in route:
                route["constraints"] = []
            if "risks" not in route:
                route["risks"] = []

        # 确保 recommended_route 存在
        if "recommended_route" not in data and data["routes"]:
            data["recommended_route"] = data["routes"][0]["route_id"]

        # 确保 warnings 存在
        if "warnings" not in data:
            data["warnings"] = []

        return data

    def _emergency_fallback(self, context: MarketContext) -> str:
        """紧急 fallback（当 LLM 完全不可用时）"""
        phase = context.trend_phase.phase

        # 基于趋势阶段生成最基本的建议
        if phase in ("DEVELOPING", "MATURE"):
            routes = [
                {
                    "route_id": "A",
                    "name": "顺势操作",
                    "action": "跟随趋势方向操作",
                    "confidence": 0.6,
                    "reasoning": "市场处于明确趋势中，顺势操作风险收益比较好",
                    "constraints": [
                        {"constraint_type": "POSITION_SIZE", "value": "3-5%", "confidence": 0.5},
                        {"constraint_type": "STOP_LOSS", "value": "2倍ATR", "confidence": 0.5},
                    ],
                    "risks": ["趋势可能接近尾声"],
                },
                {
                    "route_id": "B",
                    "name": "观望等待回调",
                    "action": "等待回调后再入场",
                    "confidence": 0.4,
                    "reasoning": "等待更好的入场点",
                    "constraints": [],
                    "risks": ["可能错过趋势"],
                },
            ]
        elif phase == "CONSOLIDATING":
            routes = [
                {
                    "route_id": "A",
                    "name": "观望等待",
                    "action": "暂不操作，等待突破",
                    "confidence": 0.7,
                    "reasoning": "市场震荡整理，方向不明，观望是最佳选择",
                    "constraints": [],
                    "risks": ["可能错过突破行情"],
                },
            ]
        else:
            routes = [
                {
                    "route_id": "A",
                    "name": "谨慎观望",
                    "action": "降低仓位或观望",
                    "confidence": 0.5,
                    "reasoning": "市场状态不明朗，风险较高",
                    "constraints": [
                        {"constraint_type": "POSITION_SIZE", "value": "1-2%", "confidence": 0.4},
                    ],
                    "risks": ["市场可能出现剧烈波动"],
                },
            ]

        return json.dumps(
            {
                "routes": routes,
                "recommended_route": "A",
                "warnings": ["紧急 fallback 模式，建议质量有限"],
                "reasoning_summary": f"市场处于{phase}阶段，使用规则退化建议",
            },
            ensure_ascii=False,
        )


class ConstraintGenerator:
    """
    动态约束生成器

    基于推理结果和经验数据，生成具体的约束建议。
    约束不是固定规则，而是"基于当前状态和历史经验，建议这样做"。
    """

    def generate_from_route(
        self,
        route_data: dict,
        context: MarketContext,
        experience_aggregation: dict,
    ) -> list[Constraint]:
        """从路线数据生成约束"""
        constraints = []

        # 从 LLM 输出中提取约束
        for c_data in route_data.get("constraints", []):
            constraint = Constraint(
                constraint_type=c_data.get("constraint_type", "UNKNOWN"),
                value=c_data.get("value", ""),
                numeric_value=c_data.get("numeric_value", 0.0),
                confidence=c_data.get("confidence", 0.5),
                reasoning=c_data.get("reasoning", ""),
                historical_basis=c_data.get("historical_basis", ""),
                uncertainty_range=c_data.get("uncertainty_range", ""),
            )
            constraints.append(constraint)

        # 如果 LLM 没有提供足够的约束，用经验数据补充
        if not constraints:
            constraints = self._generate_from_experience(context, experience_aggregation)

        return constraints

    def _generate_from_experience(
        self,
        context: MarketContext,
        experience_aggregation: dict,
    ) -> list[Constraint]:
        """从经验数据生成约束"""
        constraints = []

        # 找到最佳动作
        best_action = None
        best_score = -float("inf")

        for action, stats in experience_aggregation.items():
            score = stats.get("risk_adjusted_return", 0) * stats.get("win_rate", 0)
            if score > best_score:
                best_score = score
                best_action = action

        if best_action and best_action in experience_aggregation:
            stats = experience_aggregation[best_action]

            # 仓位约束
            if stats["win_rate"] > 0.5:
                position_pct = min(5, max(1, int(stats["win_rate"] * 8)))
                constraints.append(
                    Constraint(
                        constraint_type="POSITION_SIZE",
                        value=f"{position_pct}%",
                        numeric_value=position_pct / 100,
                        confidence=stats["win_rate"],
                        reasoning=f"历史胜率{int(stats['win_rate'] * 100)}%，风险调整收益{stats['risk_adjusted_return']:+.2f}",
                        historical_basis=f"基于{stats['count']}次相似情境",
                    )
                )

            # 止损约束
            atr = context.snapshot.atr
            if atr > 0:
                stop_distance = atr * 2  # 默认 2 倍 ATR
                stop_price = (
                    context.current_price - stop_distance
                    if best_action == "LONG"
                    else context.current_price + stop_distance
                )
                constraints.append(
                    Constraint(
                        constraint_type="STOP_LOSS",
                        value=f"{stop_price:.0f}（2倍ATR）",
                        numeric_value=stop_price,
                        confidence=0.6,
                        reasoning=f"基于当前ATR({atr:.2f})的2倍设置止损",
                        historical_basis=f"相似情境平均最大回撤{stats.get('avg_max_drawdown', 0):.2f}%",
                    )
                )

        return constraints
