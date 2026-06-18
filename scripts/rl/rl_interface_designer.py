"""
RL 接口设计模块

基于 GIFT 论文思想，实现 LLM 引导的 RL 接口设计：
1. 状态空间设计
2. 奖励函数设计
3. 诊断引导修正

版本：v1.0
创建日期：2026-06-15
"""

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class StateFeature:
    """状态特征"""

    feature_id: str
    name: str
    description: str
    feature_type: str  # price, volume, technical, fundamental
    computation: str  # 计算公式或描述
    normalization: str  # min-max, z-score, none
    importance: float  # 重要性分数


@dataclass
class RewardComponent:
    """奖励组件"""

    component_id: str
    name: str
    description: str
    weight: float
    computation: str
    risk_adjusted: bool


@dataclass
class StateSpaceDesign:
    """状态空间设计"""

    design_id: str
    name: str
    description: str
    features: list[StateFeature]
    dimension: int
    market_context: str
    created_at: str


@dataclass
class RewardFunctionDesign:
    """奖励函数设计"""

    design_id: str
    name: str
    description: str
    components: list[RewardComponent]
    total_weight: float
    risk_rules: dict[str, Any]
    created_at: str


@dataclass
class DiagnosticResult:
    """诊断结果"""

    diagnostic_id: str
    metric_name: str
    current_value: float
    expected_range: list[float]
    status: str  # good, warning, critical
    suggestion: str


@dataclass
class RefinementAction:
    """修正动作"""

    action_id: str
    target: str  # state_space, reward_function
    action_type: str  # add, remove, modify
    description: str
    parameters: dict[str, Any]
    priority: str  # high, medium, low


class StateSpaceDesigner:
    """
    状态空间设计器

    基于 LLM 引导设计状态空间
    """

    def __init__(self, llm_client=None):
        """
        初始化状态空间设计器

        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
        logger.info("StateSpaceDesigner 初始化完成")

    def design_state_space(
        self, market_context: str, trading_objective: str, available_data: list[str]
    ) -> StateSpaceDesign:
        """
        设计状态空间

        Args:
            market_context: 市场上下文
            trading_objective: 交易目标
            available_data: 可用数据列表

        Returns:
            StateSpaceDesign: 状态空间设计
        """
        if self.llm_client:
            return self._design_with_llm(market_context, trading_objective, available_data)
        else:
            return self._design_with_rules(market_context, trading_objective, available_data)

    def _design_with_llm(
        self, market_context: str, trading_objective: str, available_data: list[str]
    ) -> StateSpaceDesign:
        """
        使用 LLM 设计状态空间

        Args:
            market_context: 市场上下文
            trading_objective: 交易目标
            available_data: 可用数据列表

        Returns:
            StateSpaceDesign: 状态空间设计
        """
        prompt = f"""
请根据以下信息设计一个适合强化学习的状态空间。

## 市场上下文
{market_context}

## 交易目标
{trading_objective}

## 可用数据
{available_data}

## 要求
1. 状态特征应该能够描述市场状态
2. 特征应该与交易目标相关
3. 特征应该易于计算和标准化
4. 特征数量适中（5-15个）

## 输出格式
```json
{{
  "name": "状态空间名称",
  "description": "状态空间描述",
  "features": [
    {{
      "feature_id": "feature_001",
      "name": "特征名称",
      "description": "特征描述",
      "feature_type": "price/volume/technical/fundamental",
      "computation": "计算公式",
      "normalization": "min-max/z-score/none",
      "importance": 0.8
    }}
  ]
}}
```
"""

        try:
            response = self.llm_client.generate(prompt)
            result = self._parse_json_response(response)

            features = []
            for i, feat_data in enumerate(result.get("features", [])):
                feature = StateFeature(
                    feature_id=feat_data.get("feature_id", f"feature_{i + 1:03d}"),
                    name=feat_data.get("name", ""),
                    description=feat_data.get("description", ""),
                    feature_type=feat_data.get("feature_type", "technical"),
                    computation=feat_data.get("computation", ""),
                    normalization=feat_data.get("normalization", "z-score"),
                    importance=feat_data.get("importance", 0.5),
                )
                features.append(feature)

            design = StateSpaceDesign(
                design_id=f"state_design_{id(self)}",
                name=result.get("name", "LLM 设计的状态空间"),
                description=result.get("description", ""),
                features=features,
                dimension=len(features),
                market_context=market_context,
                created_at=self._get_timestamp(),
            )

            return design

        except Exception as e:
            logger.error(f"LLM 设计状态空间失败: {e}")
            return self._design_with_rules(market_context, trading_objective, available_data)

    def _design_with_rules(
        self, market_context: str, trading_objective: str, available_data: list[str]
    ) -> StateSpaceDesign:
        """
        使用规则设计状态空间

        Args:
            market_context: 市场上下文
            trading_objective: 交易目标
            available_data: 可用数据列表

        Returns:
            StateSpaceDesign: 状态空间设计
        """
        features = []

        # 价格特征
        if "close" in available_data:
            features.append(
                StateFeature(
                    feature_id="feature_001",
                    name="价格动量",
                    description="价格变化率",
                    feature_type="price",
                    computation="close.pct_change(5)",
                    normalization="z-score",
                    importance=0.8,
                )
            )

            features.append(
                StateFeature(
                    feature_id="feature_002",
                    name="价格波动率",
                    description="价格标准差",
                    feature_type="price",
                    computation="close.rolling(20).std()",
                    normalization="min-max",
                    importance=0.7,
                )
            )

        # 成交量特征
        if "volume" in available_data:
            features.append(
                StateFeature(
                    feature_id="feature_003",
                    name="成交量比率",
                    description="当前成交量与均值的比率",
                    feature_type="volume",
                    computation="volume / volume.rolling(20).mean()",
                    normalization="z-score",
                    importance=0.6,
                )
            )

        # 技术指标特征
        features.append(
            StateFeature(
                feature_id="feature_004",
                name="RSI",
                description="相对强弱指数",
                feature_type="technical",
                computation="RSI(14)",
                normalization="min-max",
                importance=0.7,
            )
        )

        features.append(
            StateFeature(
                feature_id="feature_005",
                name="趋势强度",
                description="趋势强度综合指标",
                feature_type="technical",
                computation="trend_strength_composite",
                normalization="min-max",
                importance=0.9,
            )
        )

        design = StateSpaceDesign(
            design_id="state_design_rules",
            name="规则设计的状态空间",
            description="基于交易规则设计的状态空间",
            features=features,
            dimension=len(features),
            market_context=market_context,
            created_at=self._get_timestamp(),
        )

        return design

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """解析 JSON 响应"""
        import re

        json_block_pattern = r"```json\s*\n(.*?)```"
        match = re.search(json_block_pattern, response, re.DOTALL)

        if match:
            json_str = match.group(1).strip()
        else:
            json_pattern = r"(\{.*\})"
            match = re.search(json_pattern, response, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
            else:
                json_str = response.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return {}


class RewardFunctionDesigner:
    """
    奖励函数设计器

    基于 LLM 引导设计奖励函数
    """

    def __init__(self, llm_client=None):
        """
        初始化奖励函数设计器

        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
        logger.info("RewardFunctionDesigner 初始化完成")

    def design_reward_function(
        self, trading_objective: str, risk_rules: dict[str, Any], market_context: str
    ) -> RewardFunctionDesign:
        """
        设计奖励函数

        Args:
            trading_objective: 交易目标
            risk_rules: 风险规则
            market_context: 市场上下文

        Returns:
            RewardFunctionDesign: 奖励函数设计
        """
        if self.llm_client:
            return self._design_with_llm(trading_objective, risk_rules, market_context)
        else:
            return self._design_with_rules(trading_objective, risk_rules, market_context)

    def _design_with_llm(
        self, trading_objective: str, risk_rules: dict[str, Any], market_context: str
    ) -> RewardFunctionDesign:
        """
        使用 LLM 设计奖励函数

        Args:
            trading_objective: 交易目标
            risk_rules: 风险规则
            market_context: 市场上下文

        Returns:
            RewardFunctionDesign: 奖励函数设计
        """
        prompt = f"""
请根据以下信息设计一个适合强化学习的奖励函数。

## 交易目标
{trading_objective}

## 风险规则
{json.dumps(risk_rules, ensure_ascii=False)}

## 市场上下文
{market_context}

## 要求
1. 奖励函数应该与交易目标一致
2. 应该考虑风险调整
3. 应该包含多个组件（收益、风险、成本等）
4. 组件权重应该合理分配

## 输出格式
```json
{{
  "name": "奖励函数名称",
  "description": "奖励函数描述",
  "components": [
    {{
      "component_id": "component_001",
      "name": "组件名称",
      "description": "组件描述",
      "weight": 0.5,
      "computation": "计算公式",
      "risk_adjusted": true
    }}
  ],
  "risk_rules": {{
    "max_drawdown": 0.1,
    "position_limit": 0.2
  }}
}}
```
"""

        try:
            response = self.llm_client.generate(prompt)
            result = self._parse_json_response(response)

            components = []
            for i, comp_data in enumerate(result.get("components", [])):
                component = RewardComponent(
                    component_id=comp_data.get("component_id", f"component_{i + 1:03d}"),
                    name=comp_data.get("name", ""),
                    description=comp_data.get("description", ""),
                    weight=comp_data.get("weight", 0.5),
                    computation=comp_data.get("computation", ""),
                    risk_adjusted=comp_data.get("risk_adjusted", False),
                )
                components.append(component)

            design = RewardFunctionDesign(
                design_id=f"reward_design_{id(self)}",
                name=result.get("name", "LLM 设计的奖励函数"),
                description=result.get("description", ""),
                components=components,
                total_weight=sum(c.weight for c in components),
                risk_rules=result.get("risk_rules", risk_rules),
                created_at=self._get_timestamp(),
            )

            return design

        except Exception as e:
            logger.error(f"LLM 设计奖励函数失败: {e}")
            return self._design_with_rules(trading_objective, risk_rules, market_context)

    def _design_with_rules(
        self, trading_objective: str, risk_rules: dict[str, Any], market_context: str
    ) -> RewardFunctionDesign:
        """
        使用规则设计奖励函数

        Args:
            trading_objective: 交易目标
            risk_rules: 风险规则
            market_context: 市场上下文

        Returns:
            RewardFunctionDesign: 奖励函数设计
        """
        components = [
            RewardComponent(
                component_id="component_001",
                name="收益组件",
                description="基于交易收益的奖励",
                weight=0.5,
                computation="pnl_percent",
                risk_adjusted=True,
            ),
            RewardComponent(
                component_id="component_002",
                name="风险组件",
                description="基于最大回撤的惩罚",
                weight=0.3,
                computation="-max_drawdown",
                risk_adjusted=True,
            ),
            RewardComponent(
                component_id="component_003",
                name="成本组件",
                description="基于交易成本的惩罚",
                weight=0.2,
                computation="-transaction_cost",
                risk_adjusted=False,
            ),
        ]

        design = RewardFunctionDesign(
            design_id="reward_design_rules",
            name="规则设计的奖励函数",
            description="基于交易规则设计的奖励函数",
            components=components,
            total_weight=sum(c.weight for c in components),
            risk_rules=risk_rules,
            created_at=self._get_timestamp(),
        )

        return design

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """解析 JSON 响应"""
        import re

        json_block_pattern = r"```json\s*\n(.*?)```"
        match = re.search(json_block_pattern, response, re.DOTALL)

        if match:
            json_str = match.group(1).strip()
        else:
            json_pattern = r"(\{.*\})"
            match = re.search(json_pattern, response, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
            else:
                json_str = response.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return {}


class DiagnosticRefiner:
    """
    诊断引导修正器

    基于诊断结果修正状态空间和奖励函数
    """

    def __init__(self):
        """初始化诊断引导修正器"""
        logger.info("DiagnosticRefiner 初始化完成")

    def collect_diagnostics(
        self, training_metrics: dict[str, Any], expected_metrics: dict[str, Any]
    ) -> list[DiagnosticResult]:
        """
        收集诊断结果

        Args:
            training_metrics: 训练指标
            expected_metrics: 预期指标

        Returns:
            list: 诊断结果列表
        """
        diagnostics = []

        for metric_name, current_value in training_metrics.items():
            if metric_name in expected_metrics:
                expected_range = expected_metrics[metric_name]

                # 判断状态
                if isinstance(expected_range, list) and len(expected_range) == 2:
                    min_val, max_val = expected_range
                    if min_val <= current_value <= max_val:
                        status = "good"
                        suggestion = "指标正常"
                    elif current_value < min_val:
                        status = "warning"
                        suggestion = "指标偏低，建议调整"
                    else:
                        status = "warning"
                        suggestion = "指标偏高，建议调整"
                else:
                    status = "unknown"
                    suggestion = "无法判断"

                diagnostic = DiagnosticResult(
                    diagnostic_id=f"diag_{metric_name}",
                    metric_name=metric_name,
                    current_value=current_value,
                    expected_range=expected_range if isinstance(expected_range, list) else [expected_range],
                    status=status,
                    suggestion=suggestion,
                )
                diagnostics.append(diagnostic)

        return diagnostics

    def suggest_refinements(
        self, diagnostics: list[DiagnosticResult], current_design: dict[str, Any]
    ) -> list[RefinementAction]:
        """
        建议修正方案

        Args:
            diagnostics: 诊断结果列表
            current_design: 当前设计

        Returns:
            list: 修正动作列表
        """
        actions = []

        for diagnostic in diagnostics:
            if diagnostic.status == "warning" or diagnostic.status == "critical":
                # 根据诊断结果生成修正动作
                action = self._create_refinement_action(diagnostic, current_design)
                if action:
                    actions.append(action)

        return actions

    def _create_refinement_action(
        self, diagnostic: DiagnosticResult, current_design: dict[str, Any]
    ) -> RefinementAction | None:
        """
        创建修正动作

        Args:
            diagnostic: 诊断结果
            current_design: 当前设计

        Returns:
            RefinementAction: 修正动作
        """
        # 根据指标名称生成修正动作
        if "reward" in diagnostic.metric_name.lower():
            return RefinementAction(
                action_id=f"action_{diagnostic.diagnostic_id}",
                target="reward_function",
                action_type="modify",
                description=f"调整奖励函数的 {diagnostic.metric_name}",
                parameters={"metric": diagnostic.metric_name, "adjustment": diagnostic.suggestion},
                priority="high" if diagnostic.status == "critical" else "medium",
            )
        elif "state" in diagnostic.metric_name.lower() or "feature" in diagnostic.metric_name.lower():
            return RefinementAction(
                action_id=f"action_{diagnostic.diagnostic_id}",
                target="state_space",
                action_type="modify",
                description=f"调整状态空间的 {diagnostic.metric_name}",
                parameters={"metric": diagnostic.metric_name, "adjustment": diagnostic.suggestion},
                priority="high" if diagnostic.status == "critical" else "medium",
            )

        return None


class RLInterfaceDesigner:
    """
    RL 接口设计器

    整合状态空间设计、奖励函数设计和诊断引导修正
    """

    def __init__(self, llm_client=None):
        """
        初始化 RL 接口设计器

        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
        self.state_designer = StateSpaceDesigner(llm_client)
        self.reward_designer = RewardFunctionDesigner(llm_client)
        self.diagnostic_refiner = DiagnosticRefiner()

        logger.info("RLInterfaceDesigner 初始化完成")

    def design_interface(
        self, market_context: str, trading_objective: str, available_data: list[str], risk_rules: dict[str, Any]
    ) -> dict[str, Any]:
        """
        设计 RL 接口

        Args:
            market_context: 市场上下文
            trading_objective: 交易目标
            available_data: 可用数据
            risk_rules: 风险规则

        Returns:
            dict: RL 接口设计
        """
        # 设计状态空间
        state_design = self.state_designer.design_state_space(market_context, trading_objective, available_data)

        # 设计奖励函数
        reward_design = self.reward_designer.design_reward_function(trading_objective, risk_rules, market_context)

        return {
            "state_space": asdict(state_design),
            "reward_function": asdict(reward_design),
            "metadata": {
                "market_context": market_context,
                "trading_objective": trading_objective,
                "available_data": available_data,
                "risk_rules": risk_rules,
            },
        }

    def refine_interface(
        self, current_design: dict[str, Any], training_metrics: dict[str, Any], expected_metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """
        修正 RL 接口

        Args:
            current_design: 当前设计
            training_metrics: 训练指标
            expected_metrics: 预期指标

        Returns:
            dict: 修正建议
        """
        # 收集诊断结果
        diagnostics = self.diagnostic_refiner.collect_diagnostics(training_metrics, expected_metrics)

        # 建议修正方案
        actions = self.diagnostic_refiner.suggest_refinements(diagnostics, current_design)

        return {
            "diagnostics": [asdict(d) for d in diagnostics],
            "refinement_actions": [asdict(a) for a in actions],
            "summary": {
                "total_diagnostics": len(diagnostics),
                "warnings": len([d for d in diagnostics if d.status == "warning"]),
                "critical": len([d for d in diagnostics if d.status == "critical"]),
                "actions_suggested": len(actions),
            },
        }


# 示例用法
if __name__ == "__main__":
    # 测试 RL 接口设计器
    designer = RLInterfaceDesigner()

    market_context = "焦煤市场处于上升趋势，安全检查限产导致供应收紧"
    trading_objective = "捕捉趋势机会，控制回撤在 10% 以内"
    available_data = ["close", "volume", "high", "low", "open"]
    risk_rules = {"max_drawdown": 0.1, "position_limit": 0.2, "stop_loss": 0.05}

    # 设计接口
    interface = designer.design_interface(market_context, trading_objective, available_data, risk_rules)

    print("RL 接口设计:")
    print(f"状态空间特征数: {len(interface['state_space']['features'])}")
    print(f"奖励函数组件数: {len(interface['reward_function']['components'])}")
