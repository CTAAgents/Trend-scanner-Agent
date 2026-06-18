"""
研报解析模块

实现研报知识注入流水线，支持：
1. 研报内容解析
2. 关键观点提取
3. 数据逻辑提取
4. 因子建议生成

版本：v1.0
创建日期：2026-06-15
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class KeyViewpoint:
    """关键观点"""

    viewpoint_id: str
    content: str
    category: str  # supply, demand, policy, technical, macro
    confidence: float
    supporting_data: list[str]


@dataclass
class DataLogic:
    """数据逻辑"""

    metric: str
    value: str
    context: str
    implication: str


@dataclass
class LogicChain:
    """逻辑链"""

    cause: str
    effect: str
    mechanism: str
    confidence: float


@dataclass
class FactorSuggestion:
    """因子建议"""

    suggestion_id: str
    name: str
    description: str
    logic: str
    expected_effect: str
    implementation_difficulty: str  # low, medium, high
    data_requirements: list[str]


@dataclass
class ReportAnalysis:
    """研报分析结果"""

    report_id: str
    title: str
    source: str
    publish_date: str
    key_viewpoints: list[KeyViewpoint]
    data_logic: list[DataLogic]
    logic_chains: list[LogicChain]
    factor_suggestions: list[FactorSuggestion]
    raw_content: str


class ReportParser:
    """
    研报解析器

    解析研报内容，提取关键观点、数据逻辑和因子建议
    """

    def __init__(self, llm_client=None):
        """
        初始化研报解析器

        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
        logger.info("ReportParser 初始化完成")

    def parse_report(self, report_content: str, report_metadata: dict[str, Any] = None) -> ReportAnalysis:
        """
        解析研报内容

        Args:
            report_content: 研报内容
            report_metadata: 研报元数据（标题、来源、日期等）

        Returns:
            ReportAnalysis: 研报分析结果
        """
        # 提取元数据
        metadata = report_metadata or {}
        report_id = metadata.get("report_id", "unknown")
        title = metadata.get("title", "未知标题")
        source = metadata.get("source", "未知来源")
        publish_date = metadata.get("publish_date", "未知日期")

        # 提取关键观点
        key_viewpoints = self._extract_key_viewpoints(report_content)

        # 提取数据逻辑
        data_logic = self._extract_data_logic(report_content)

        # 提取逻辑链
        logic_chains = self._extract_logic_chains(report_content)

        # 生成因子建议
        factor_suggestions = self._generate_factor_suggestions(key_viewpoints, data_logic, logic_chains)

        # 构建分析结果
        analysis = ReportAnalysis(
            report_id=report_id,
            title=title,
            source=source,
            publish_date=publish_date,
            key_viewpoints=key_viewpoints,
            data_logic=data_logic,
            logic_chains=logic_chains,
            factor_suggestions=factor_suggestions,
            raw_content=report_content,
        )

        logger.info(f"研报解析完成: {title}")
        return analysis

    def _extract_key_viewpoints(self, content: str) -> list[KeyViewpoint]:
        """
        提取关键观点

        Args:
            content: 研报内容

        Returns:
            list: 关键观点列表
        """
        viewpoints = []

        if self.llm_client:
            # 使用 LLM 提取关键观点
            viewpoints = self._extract_viewpoints_with_llm(content)
        else:
            # 使用规则提取关键观点
            viewpoints = self._extract_viewpoints_with_rules(content)

        return viewpoints

    def _extract_viewpoints_with_llm(self, content: str) -> list[KeyViewpoint]:
        """
        使用 LLM 提取关键观点

        Args:
            content: 研报内容

        Returns:
            list: 关键观点列表
        """
        prompt = f"""
请从以下研报中提取关键观点，每个观点用一句话概括。

## 研报内容
{content}

## 输出格式
请以 JSON 格式输出：

```json
{{
  "viewpoints": [
    {{
      "content": "观点内容",
      "category": "类别（supply/demand/policy/technical/macro）",
      "confidence": 0.8,
      "supporting_data": ["支撑数据1", "支撑数据2"]
    }}
  ]
}}
```
"""

        try:
            response = self.llm_client.generate(prompt)
            result = self._parse_json_response(response)

            viewpoints = []
            for i, vp_data in enumerate(result.get("viewpoints", [])):
                viewpoint = KeyViewpoint(
                    viewpoint_id=f"vp_{i + 1:03d}",
                    content=vp_data.get("content", ""),
                    category=vp_data.get("category", "unknown"),
                    confidence=vp_data.get("confidence", 0.5),
                    supporting_data=vp_data.get("supporting_data", []),
                )
                viewpoints.append(viewpoint)

            return viewpoints

        except Exception as e:
            logger.error(f"LLM 提取关键观点失败: {e}")
            return self._extract_viewpoints_with_rules(content)

    def _extract_viewpoints_with_rules(self, content: str) -> list[KeyViewpoint]:
        """
        使用规则提取关键观点

        Args:
            content: 研报内容

        Returns:
            list: 关键观点列表
        """
        viewpoints = []

        # 分割内容为段落
        paragraphs = content.split("\n")

        # 寻找关键观点的模式
        viewpoint_patterns = [
            r"认为[：:](.+)",
            r"指出[：:](.+)",
            r"预计[：:](.+)",
            r"判断[：:](.+)",
            r"结论[：:](.+)",
            r"核心观点[：:](.+)",
            r"主要观点[：:](.+)",
        ]

        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            for pattern in viewpoint_patterns:
                match = re.search(pattern, paragraph)
                if match:
                    viewpoint_content = match.group(1).strip()
                    if len(viewpoint_content) > 10:  # 过滤太短的内容
                        viewpoint = KeyViewpoint(
                            viewpoint_id=f"vp_{len(viewpoints) + 1:03d}",
                            content=viewpoint_content,
                            category=self._classify_viewpoint(viewpoint_content),
                            confidence=0.6,
                            supporting_data=[],
                        )
                        viewpoints.append(viewpoint)

        # 如果没有找到明确的观点，尝试提取第一段作为观点
        if not viewpoints and paragraphs:
            first_paragraph = paragraphs[0].strip()
            if len(first_paragraph) > 20:
                viewpoint = KeyViewpoint(
                    viewpoint_id="vp_001",
                    content=first_paragraph[:200],  # 限制长度
                    category="unknown",
                    confidence=0.4,
                    supporting_data=[],
                )
                viewpoints.append(viewpoint)

        return viewpoints

    def _classify_viewpoint(self, viewpoint: str) -> str:
        """
        分类观点

        Args:
            viewpoint: 观点内容

        Returns:
            str: 类别
        """
        viewpoint_lower = viewpoint.lower()

        # 供应相关
        supply_keywords = ["供应", "产量", "产能", "库存", "进口", "出口", "生产"]
        if any(keyword in viewpoint_lower for keyword in supply_keywords):
            return "supply"

        # 需求相关
        demand_keywords = ["需求", "消费", "采购", "销售", "下游", "终端"]
        if any(keyword in viewpoint_lower for keyword in demand_keywords):
            return "demand"

        # 政策相关
        policy_keywords = ["政策", "监管", "限产", "环保", "安全检查", "补贴"]
        if any(keyword in viewpoint_lower for keyword in policy_keywords):
            return "policy"

        # 技术相关
        technical_keywords = ["技术", "指标", "突破", "支撑", "阻力", "趋势"]
        if any(keyword in viewpoint_lower for keyword in technical_keywords):
            return "technical"

        # 宏观相关
        macro_keywords = ["宏观", "经济", "gdp", "cpi", "利率", "汇率"]
        if any(keyword in viewpoint_lower for keyword in macro_keywords):
            return "macro"

        return "unknown"

    def _extract_data_logic(self, content: str) -> list[DataLogic]:
        """
        提取数据逻辑

        Args:
            content: 研报内容

        Returns:
            list: 数据逻辑列表
        """
        data_logic = []

        # 寻找数据模式
        data_patterns = [
            r"(\w+)[为达]到?(\d+\.?\d*)[万亿%吨]",
            r"(\w+)下降了?(\d+\.?\d*)[万亿%吨]",
            r"(\w+)增长了?(\d+\.?\d*)[万亿%吨]",
            r"(\w+)为(\d+\.?\d*)",
        ]

        paragraphs = content.split("\n")
        for paragraph in paragraphs:
            for pattern in data_patterns:
                matches = re.finditer(pattern, paragraph)
                for match in matches:
                    metric = match.group(1)
                    value = match.group(2)

                    # 提取上下文
                    context = paragraph[:100] if len(paragraph) > 100 else paragraph

                    # 推断含义
                    implication = self._infer_implication(metric, value, context)

                    data_point = DataLogic(metric=metric, value=value, context=context, implication=implication)
                    data_logic.append(data_point)

        return data_logic

    def _infer_implication(self, metric: str, value: str, context: str) -> str:
        """
        推断数据含义

        Args:
            metric: 指标名称
            value: 指标值
            context: 上下文

        Returns:
            str: 含义
        """
        # 简单的规则推断
        if "库存" in metric:
            return f"{metric}为{value}，影响供需平衡"
        elif "产量" in metric or "产能" in metric:
            return f"{metric}为{value}，影响供应端"
        elif "需求" in metric or "消费" in metric:
            return f"{metric}为{value}，影响需求端"
        elif "价格" in metric:
            return f"{metric}为{value}，反映市场供需"
        else:
            return f"{metric}为{value}，需要进一步分析"

    def _extract_logic_chains(self, content: str) -> list[LogicChain]:
        """
        提取逻辑链

        Args:
            content: 研报内容

        Returns:
            list: 逻辑链列表
        """
        logic_chains = []

        # 寻找因果关系模式
        causal_patterns = [
            r"因为(.+)[，,](?:所以|导致|引起)(.+)",
            r"由于(.+)[，,](?:因此|所以)(.+)",
            r"(.+)[，,](?:从而|进而)(.+)",
            r"(.+)[，,](?:推动|拉动|带动)(.+)",
        ]

        paragraphs = content.split("\n")
        for paragraph in paragraphs:
            for pattern in causal_patterns:
                matches = re.finditer(pattern, paragraph)
                for match in matches:
                    cause = match.group(1).strip()
                    effect = match.group(2).strip()

                    if len(cause) > 5 and len(effect) > 5:
                        logic_chain = LogicChain(
                            cause=cause, effect=effect, mechanism=f"{cause} → {effect}", confidence=0.6
                        )
                        logic_chains.append(logic_chain)

        return logic_chains

    def _generate_factor_suggestions(
        self, viewpoints: list[KeyViewpoint], data_logic: list[DataLogic], logic_chains: list[LogicChain]
    ) -> list[FactorSuggestion]:
        """
        生成因子建议

        Args:
            viewpoints: 关键观点
            data_logic: 数据逻辑
            logic_chains: 逻辑链

        Returns:
            list: 因子建议列表
        """
        suggestions = []

        # 基于观点生成因子建议
        for viewpoint in viewpoints:
            if viewpoint.category in ["supply", "demand", "policy"]:
                suggestion = self._create_factor_suggestion_from_viewpoint(viewpoint)
                if suggestion:
                    suggestions.append(suggestion)

        # 基于逻辑链生成因子建议
        for logic_chain in logic_chains:
            suggestion = self._create_factor_suggestion_from_logic_chain(logic_chain)
            if suggestion:
                suggestions.append(suggestion)

        # 去重
        suggestions = self._deduplicate_suggestions(suggestions)

        return suggestions

    def _create_factor_suggestion_from_viewpoint(self, viewpoint: KeyViewpoint) -> FactorSuggestion | None:
        """
        从观点创建因子建议

        Args:
            viewpoint: 关键观点

        Returns:
            FactorSuggestion: 因子建议
        """
        # 根据观点类别生成因子建议
        if viewpoint.category == "supply":
            return FactorSuggestion(
                suggestion_id=f"suggest_{viewpoint.viewpoint_id}",
                name="供应端因子",
                description=f"基于供应端观点: {viewpoint.content[:50]}",
                logic="监控供应端变化，如产量、库存、进口等",
                expected_effect="捕捉供应端变化带来的价格机会",
                implementation_difficulty="medium",
                data_requirements=["产量数据", "库存数据", "进出口数据"],
            )
        elif viewpoint.category == "demand":
            return FactorSuggestion(
                suggestion_id=f"suggest_{viewpoint.viewpoint_id}",
                name="需求端因子",
                description=f"基于需求端观点: {viewpoint.content[:50]}",
                logic="监控需求端变化，如消费、采购、销售等",
                expected_effect="捕捉需求端变化带来的价格机会",
                implementation_difficulty="medium",
                data_requirements=["消费数据", "采购数据", "销售数据"],
            )
        elif viewpoint.category == "policy":
            return FactorSuggestion(
                suggestion_id=f"suggest_{viewpoint.viewpoint_id}",
                name="政策因子",
                description=f"基于政策观点: {viewpoint.content[:50]}",
                logic="监控政策变化，如限产、环保、安全检查等",
                expected_effect="捕捉政策变化带来的价格机会",
                implementation_difficulty="high",
                data_requirements=["政策公告", "执行情况"],
            )

        return None

    def _create_factor_suggestion_from_logic_chain(self, logic_chain: LogicChain) -> FactorSuggestion | None:
        """
        从逻辑链创建因子建议

        Args:
            logic_chain: 逻辑链

        Returns:
            FactorSuggestion: 因子建议
        """
        return FactorSuggestion(
            suggestion_id=f"suggest_lc_{id(logic_chain)}",
            name="逻辑链因子",
            description=f"基于逻辑链: {logic_chain.cause[:30]} → {logic_chain.effect[:30]}",
            logic=f"监控{logic_chain.cause[:20]}的变化，预测{logic_chain.effect[:20]}",
            expected_effect="捕捉逻辑链驱动的价格机会",
            implementation_difficulty="high",
            data_requirements=["相关指标数据"],
        )

    def _deduplicate_suggestions(self, suggestions: list[FactorSuggestion]) -> list[FactorSuggestion]:
        """
        去重因子建议

        Args:
            suggestions: 因子建议列表

        Returns:
            list: 去重后的因子建议列表
        """
        seen_names = set()
        unique_suggestions = []

        for suggestion in suggestions:
            if suggestion.name not in seen_names:
                seen_names.add(suggestion.name)
                unique_suggestions.append(suggestion)

        return unique_suggestions

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """
        解析 JSON 响应

        Args:
            response: LLM 响应

        Returns:
            dict: 解析后的 JSON
        """
        # 尝试从 markdown 代码块中提取
        json_block_pattern = r"```json\s*\n(.*?)```"
        match = re.search(json_block_pattern, response, re.DOTALL)

        if match:
            json_str = match.group(1).strip()
        else:
            # 尝试提取整个响应
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


class ValidationPipeline:
    """
    验证流水线

    验证研报分析结果的质量
    """

    def __init__(self):
        """初始化验证流水线"""
        logger.info("ValidationPipeline 初始化完成")

    def validate_analysis(self, analysis: ReportAnalysis) -> dict[str, Any]:
        """
        验证研报分析结果

        Args:
            analysis: 研报分析结果

        Returns:
            dict: 验证结果
        """
        errors = []
        warnings = []

        # 验证关键观点
        if not analysis.key_viewpoints:
            warnings.append("未提取到关键观点")

        # 验证数据逻辑
        if not analysis.data_logic:
            warnings.append("未提取到数据逻辑")

        # 验证逻辑链
        if not analysis.logic_chains:
            warnings.append("未提取到逻辑链")

        # 验证因子建议
        if not analysis.factor_suggestions:
            warnings.append("未生成因子建议")

        # 验证观点质量
        for viewpoint in analysis.key_viewpoints:
            if len(viewpoint.content) < 10:
                warnings.append(f"观点内容过短: {viewpoint.content}")
            if viewpoint.confidence < 0.3:
                warnings.append(f"观点置信度过低: {viewpoint.content}")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "quality_score": self._calculate_quality_score(analysis),
        }

    def _calculate_quality_score(self, analysis: ReportAnalysis) -> float:
        """
        计算质量分数

        Args:
            analysis: 研报分析结果

        Returns:
            float: 质量分数 (0-100)
        """
        score = 50.0  # 基础分

        # 关键观点
        if analysis.key_viewpoints:
            score += min(20, len(analysis.key_viewpoints) * 5)

        # 数据逻辑
        if analysis.data_logic:
            score += min(15, len(analysis.data_logic) * 3)

        # 逻辑链
        if analysis.logic_chains:
            score += min(10, len(analysis.logic_chains) * 5)

        # 因子建议
        if analysis.factor_suggestions:
            score += min(10, len(analysis.factor_suggestions) * 5)

        return min(100, score)


# 示例用法
if __name__ == "__main__":
    # 测试研报解析器
    parser = ReportParser()

    report_content = """
    焦煤市场分析报告
    
    当前焦煤市场处于上升趋势，主要受以下因素驱动：
    1. 安全检查限产导致供应收紧
    2. 焦化利润支撑需求
    3. 钢厂补库需求增加
    
    数据显示，焦煤库存处于历史低位，港口库存下降 20%。
    预计短期内价格将继续上涨，目标位 1600 元/吨。
    """

    metadata = {
        "report_id": "report_001",
        "title": "焦煤市场分析报告",
        "source": "测试来源",
        "publish_date": "2026-06-15",
    }

    analysis = parser.parse_report(report_content, metadata)

    print("研报分析结果:")
    print(f"标题: {analysis.title}")
    print(f"关键观点数量: {len(analysis.key_viewpoints)}")
    print(f"数据逻辑数量: {len(analysis.data_logic)}")
    print(f"逻辑链数量: {len(analysis.logic_chains)}")
    print(f"因子建议数量: {len(analysis.factor_suggestions)}")
