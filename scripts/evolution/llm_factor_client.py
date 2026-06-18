"""
LLM 因子生成客户端

提供与 LLM 交互的接口，用于生成因子代码。
支持多种 LLM 提供商，包括 OpenAI、Anthropic、本地 LLM 等。

版本：v1.0
创建日期：2026-06-15
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any


logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """
    LLM 客户端基类

    定义与 LLM 交互的通用接口
    """

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数

        Returns:
            str: 生成的文本
        """
        pass

    @abstractmethod
    def generate_with_json_output(self, prompt: str, **kwargs) -> dict[str, Any]:
        """
        生成 JSON 格式的输出

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数

        Returns:
            dict: 解析后的 JSON
        """
        pass


class OpenAIClient(LLMClient):
    """
    OpenAI 客户端

    使用 OpenAI API 生成文本
    """

    def __init__(self, api_key: str = None, model: str = "gpt-4", base_url: str = None):
        """
        初始化 OpenAI 客户端

        Args:
            api_key: OpenAI API key
            model: 模型名称
            base_url: API 基础 URL（可选，用于代理或自定义端点）
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url

        if not self.api_key:
            raise ValueError("OpenAI API key 未提供")

        # 尝试导入 openai 库
        try:
            import openai

            self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            logger.info(f"OpenAI 客户端初始化成功，模型: {self.model}")
        except ImportError:
            logger.error("openai 库未安装，请运行: pip install openai")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数
                - temperature: 温度参数
                - max_tokens: 最大 token 数
                - system_prompt: 系统 prompt

        Returns:
            str: 生成的文本
        """
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2000)
        system_prompt = kwargs.get("system_prompt", "你是一个量化因子挖掘专家。")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            raise

    def generate_with_json_output(self, prompt: str, **kwargs) -> dict[str, Any]:
        """
        生成 JSON 格式的输出

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数

        Returns:
            dict: 解析后的 JSON
        """
        # 在 prompt 中要求输出 JSON 格式
        json_prompt = f"""
{prompt}

请以 JSON 格式输出结果，确保输出是有效的 JSON。
"""

        response = self.generate(json_prompt, **kwargs)

        try:
            # 尝试从响应中提取 JSON
            json_str = self._extract_json_from_response(response)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.error(f"原始响应: {response}")
            raise

    def _extract_json_from_response(self, response: str) -> str:
        """
        从响应中提取 JSON

        Args:
            response: LLM 响应

        Returns:
            str: JSON 字符串
        """
        import re

        # 尝试从 markdown 代码块中提取
        json_block_pattern = r"```json\s*\n(.*?)```"
        match = re.search(json_block_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 尝试提取整个响应
        # 查找 { 开始的 JSON
        json_pattern = r"(\{.*\})"
        match = re.search(json_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 如果都找不到，返回整个响应
        return response.strip()


class AnthropicClient(LLMClient):
    """
    Anthropic 客户端

    使用 Anthropic API 生成文本
    """

    def __init__(self, api_key: str = None, model: str = "claude-3-sonnet-20240229"):
        """
        初始化 Anthropic 客户端

        Args:
            api_key: Anthropic API key
            model: 模型名称
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("Anthropic API key 未提供")

        # 尝试导入 anthropic 库
        try:
            import anthropic

            self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info(f"Anthropic 客户端初始化成功，模型: {self.model}")
        except ImportError:
            logger.error("anthropic 库未安装，请运行: pip install anthropic")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数
                - temperature: 温度参数
                - max_tokens: 最大 token 数
                - system_prompt: 系统 prompt

        Returns:
            str: 生成的文本
        """
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2000)
        system_prompt = kwargs.get("system_prompt", "你是一个量化因子挖掘专家。")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API 调用失败: {e}")
            raise

    def generate_with_json_output(self, prompt: str, **kwargs) -> dict[str, Any]:
        """
        生成 JSON 格式的输出

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数

        Returns:
            dict: 解析后的 JSON
        """
        # 在 prompt 中要求输出 JSON 格式
        json_prompt = f"""
{prompt}

请以 JSON 格式输出结果，确保输出是有效的 JSON。
"""

        response = self.generate(json_prompt, **kwargs)

        try:
            # 尝试从响应中提取 JSON
            json_str = self._extract_json_from_response(response)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.error(f"原始响应: {response}")
            raise

    def _extract_json_from_response(self, response: str) -> str:
        """
        从响应中提取 JSON

        Args:
            response: LLM 响应

        Returns:
            str: JSON 字符串
        """
        import re

        # 尝试从 markdown 代码块中提取
        json_block_pattern = r"```json\s*\n(.*?)```"
        match = re.search(json_block_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 尝试提取整个响应
        # 查找 { 开始的 JSON
        json_pattern = r"(\{.*\})"
        match = re.search(json_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 如果都找不到，返回整个响应
        return response.strip()


class LocalLLMClient(LLMClient):
    """
    本地 LLM 客户端

    使用本地部署的 LLM 生成文本
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        """
        初始化本地 LLM 客户端

        Args:
            base_url: 本地 LLM 服务地址
            model: 模型名称
        """
        self.base_url = base_url
        self.model = model

        logger.info(f"本地 LLM 客户端初始化成功，模型: {self.model}")

    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数

        Returns:
            str: 生成的文本
        """
        import requests

        temperature = kwargs.get("temperature", 0.7)

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": temperature}},
            )

            response.raise_for_status()
            return response.json()["response"]

        except Exception as e:
            logger.error(f"本地 LLM 调用失败: {e}")
            raise

    def generate_with_json_output(self, prompt: str, **kwargs) -> dict[str, Any]:
        """
        生成 JSON 格式的输出

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数

        Returns:
            dict: 解析后的 JSON
        """
        # 在 prompt 中要求输出 JSON 格式
        json_prompt = f"""
{prompt}

请以 JSON 格式输出结果，确保输出是有效的 JSON。
"""

        response = self.generate(json_prompt, **kwargs)

        try:
            # 尝试从响应中提取 JSON
            json_str = self._extract_json_from_response(response)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.error(f"原始响应: {response}")
            raise

    def _extract_json_from_response(self, response: str) -> str:
        """
        从响应中提取 JSON

        Args:
            response: LLM 响应

        Returns:
            str: JSON 字符串
        """
        import re

        # 尝试从 markdown 代码块中提取
        json_block_pattern = r"```json\s*\n(.*?)```"
        match = re.search(json_block_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 尝试提取整个响应
        # 查找 { 开始的 JSON
        json_pattern = r"(\{.*\})"
        match = re.search(json_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 如果都找不到，返回整个响应
        return response.strip()


class MockLLMClient(LLMClient):
    """
    模拟 LLM 客户端

    用于测试和开发
    """

    def __init__(self, responses: dict[str, str] = None):
        """
        初始化模拟 LLM 客户端

        Args:
            responses: 预定义的响应字典
        """
        self.responses = responses or {}
        self.call_count = 0

        logger.info("MockLLMClient 初始化完成")

    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本（模拟）

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数

        Returns:
            str: 生成的文本
        """
        self.call_count += 1

        # 检查是否有预定义响应
        for key, response in self.responses.items():
            if key in prompt:
                return response

        # 返回默认响应
        return self._generate_default_response(prompt)

    def generate_with_json_output(self, prompt: str, **kwargs) -> dict[str, Any]:
        """
        生成 JSON 格式的输出（模拟）

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数

        Returns:
            dict: 解析后的 JSON
        """
        response = self.generate(prompt, **kwargs)

        try:
            import re

            json_str = re.search(r"```json\s*\n(.*?)```", response, re.DOTALL)
            if json_str:
                return json.loads(json_str.group(1))
            return json.loads(response)
        except:
            return {"mock": True, "response": response}

    def _generate_default_response(self, prompt: str) -> str:
        """
        生成默认响应

        Args:
            prompt: 输入 prompt

        Returns:
            str: 默认响应
        """
        if "因子" in prompt or "factor" in prompt.lower():
            return '''```python
def factor(df: pd.DataFrame) -> pd.Series:
    """
    因子名称：动量突破因子
    因子描述：结合价格动量和成交量放大，捕捉突破信号
    逻辑：5日收益率 * 成交量比率
    
    Args:
        df: 包含 OHLCV 数据的 DataFrame
        
    Returns:
        pd.Series: 因子值，index 与输入 df 相同
    """
    import pandas as pd
    
    # 计算5日收益率
    returns = df['close'].pct_change(5)
    
    # 计算成交量比率
    volume_ratio = df['volume'] / df['volume'].rolling(20).mean()
    
    # 计算因子值
    factor_value = returns * volume_ratio
    
    # 归一化到 [-1, 1] 范围
    factor_value = factor_value / factor_value.abs().max()
    
    return factor_value
```'''

        return "这是一个模拟响应。"


class LLMFactorClient:
    """
    LLM 因子生成客户端

    封装 LLM 客户端，提供因子生成专用接口
    """

    def __init__(self, llm_client: LLMClient = None):
        """
        初始化 LLM 因子生成客户端

        Args:
            llm_client: LLM 客户端实例
        """
        self.llm_client = llm_client or MockLLMClient()

        logger.info("LLMFactorClient 初始化完成")

    def generate_factor_code(self, market_context: str, research_report: str = None) -> str:
        """
        生成因子代码

        Args:
            market_context: 市场上下文
            research_report: 研报内容

        Returns:
            str: 因子代码
        """
        prompt = self._build_factor_generation_prompt(market_context, research_report)

        response = self.llm_client.generate(prompt)

        # 提取代码
        code = self._extract_code_from_response(response)

        return code

    def generate_factor_suggestions(self, market_context: str, research_report: str = None) -> list[dict[str, Any]]:
        """
        生成因子建议

        Args:
            market_context: 市场上下文
            research_report: 研报内容

        Returns:
            list: 因子建议列表
        """
        prompt = self._build_factor_suggestion_prompt(market_context, research_report)

        response = self.llm_client.generate_with_json_output(prompt)

        return response.get("suggestions", [])

    def refine_factor_code(self, factor_code: str, errors: list[str]) -> str:
        """
        修正因子代码

        Args:
            factor_code: 原始因子代码
            errors: 错误列表

        Returns:
            str: 修正后的因子代码
        """
        prompt = self._build_refine_prompt(factor_code, errors)

        response = self.llm_client.generate(prompt)

        # 提取代码
        code = self._extract_code_from_response(response)

        return code

    def analyze_factor_logic(self, factor_code: str) -> dict[str, Any]:
        """
        分析因子逻辑

        Args:
            factor_code: 因子代码

        Returns:
            dict: 因子逻辑分析
        """
        prompt = self._build_analysis_prompt(factor_code)

        response = self.llm_client.generate_with_json_output(prompt)

        return response

    def _build_factor_generation_prompt(self, market_context: str, research_report: str = None) -> str:
        """
        构建因子生成 prompt

        Args:
            market_context: 市场上下文
            research_report: 研报内容

        Returns:
            str: prompt
        """
        prompt = f"""你是一个量化因子挖掘专家，擅长从市场数据和研报中提取有效的交易因子。

## 任务
根据以下市场上下文，生成一个可执行的因子代码。

## 市场上下文
{market_context}

## 因子要求
1. 因子必须是 Python 函数，接收 pandas DataFrame 作为输入
2. 因子返回 pandas Series，值建议在 [-1, 1] 之间（或可归一化到此范围）
3. 因子逻辑必须清晰，可解释
4. 优先使用技术指标和价量数据
5. 因子应具有一定的预测能力

## 输出格式
请严格按照以下格式输出：

```python
def factor(df: pd.DataFrame) -> pd.Series:
    \"\"\"
    因子名称：[因子名称]
    因子描述：[简要描述因子逻辑和作用]
    逻辑：[详细说明因子的计算逻辑]
    
    Args:
        df: 包含 OHLCV 数据的 DataFrame
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - volume: 成交量
        
    Returns:
        pd.Series: 因子值，index 与输入 df 相同
    \"\"\"
    # 因子实现代码
    # ...
    
    return result
```

## 注意事项
1. 不要使用未来数据（如用 t+1 的收盘价）
2. 确保代码可执行，无语法错误
3. 处理好 NaN 值
4. 如果需要使用特定库，请在函数内导入
"""

        if research_report:
            prompt += f"""

## 研报参考
以下研报内容可能包含有用的因子逻辑，请参考：

{research_report}
"""

        return prompt

    def _build_factor_suggestion_prompt(self, market_context: str, research_report: str = None) -> str:
        """
        构建因子建议 prompt

        Args:
            market_context: 市场上下文
            research_report: 研报内容

        Returns:
            str: prompt
        """
        prompt = f"""你是一个量化因子挖掘专家。请根据以下市场上下文，生成 2-3 个因子建议。

## 市场上下文
{market_context}

## 输出格式
请以 JSON 格式输出：

```json
{{
  "suggestions": [
    {{
      "name": "因子名称",
      "description": "因子描述",
      "logic": "因子逻辑",
      "expected_effect": "预期效果",
      "implementation_difficulty": "低/中/高"
    }}
  ]
}}
```
"""

        if research_report:
            prompt += f"""

## 研报参考
{research_report}
"""

        return prompt

    def _build_refine_prompt(self, factor_code: str, errors: list[str]) -> str:
        """
        构建修正 prompt

        Args:
            factor_code: 原始因子代码
            errors: 错误列表

        Returns:
            str: prompt
        """
        prompt = f"""因子代码存在以下问题，请修正：

## 问题
{chr(10).join(f"- {error}" for error in errors)}

## 原始代码
```python
{factor_code}
```

## 要求
1. 修正所有问题
2. 保持因子的核心逻辑
3. 确保代码可执行
4. 输出修正后的完整代码

请输出修正后的代码：
"""

        return prompt

    def _build_analysis_prompt(self, factor_code: str) -> str:
        """
        构建分析 prompt

        Args:
            factor_code: 因子代码

        Returns:
            str: prompt
        """
        prompt = f"""请分析以下因子代码的逻辑：

## 因子代码
```python
{factor_code}
```

## 输出格式
请以 JSON 格式输出分析结果：

```json
{{
  "factor_name": "因子名称",
  "factor_type": "因子类型（动量/均值回归/波动率等）",
  "logic_summary": "逻辑摘要",
  "key_features": ["特征1", "特征2"],
  "potential_issues": ["潜在问题1", "潜在问题2"],
  "improvement_suggestions": ["改进建议1", "改进建议2"]
}}
```
"""

        return prompt

    def _extract_code_from_response(self, response: str) -> str:
        """
        从响应中提取代码

        Args:
            response: LLM 响应

        Returns:
            str: 代码
        """
        import re

        # 尝试从 markdown 代码块中提取
        code_block_pattern = r"```python\s*\n(.*?)```"
        match = re.search(code_block_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 如果没有代码块，尝试提取整个响应
        # 查找 def factor 开始的代码
        factor_pattern = r"(def factor\(.*\n(?:.*\n)*?return .*)"
        match = re.search(factor_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 如果都找不到，返回整个响应
        logger.warning("无法从响应中提取因子代码，返回完整响应")
        return response.strip()


# 工厂函数
def create_llm_client(provider: str = "auto", **kwargs) -> LLMClient:
    """
    创建 LLM 客户端

    LLM 降级链：
    1. 用户自定义 LLM（LLM_API_KEY）— 优先
    2. 宿主平台 LLM（WORKBUDDY_API_KEY 等）— 次选
    3. 规则模式（返回 None）— 兜底

    Args:
        provider: LLM 提供商名称
            - "auto": 自动检测（默认，按降级链选择）
            - "openai": OpenAI 兼容接口
            - "anthropic": Anthropic API
            - "local": 本地 LLM（Ollama）
        **kwargs: 其他参数

    Returns:
        LLMClient 或 None（所有 LLM 都不可用时）
    """
    if provider == "auto":
        # 降级链：LLM_API_KEY → 宿主平台 KEY → None
        api_key = (
            kwargs.get("api_key") or os.getenv("LLM_API_KEY") or os.getenv("WORKBUDDY_API_KEY")  # 宿主平台兼容
        )
        if not api_key:
            return None  # 所有 LLM 都不可用，由调方降级为规则模式
        kwargs["api_key"] = api_key
        provider = "openai"

    if provider == "openai":
        return WorkBuddyClient(**kwargs)
    elif provider == "anthropic":
        return AnthropicClient(**kwargs)
    elif provider == "local":
        return LocalLLMClient(**kwargs)
    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")


class WorkBuddyClient(LLMClient):
    """
    LLM 客户端（OpenAI 兼容接口）

    通过 OpenAI 兼容接口调用大模型，支持任意兼容服务商。

    环境变量：
        LLM_API_KEY: API 密钥（必需）
        LLM_BASE_URL: API 端点（可选，默认使用配置文件中的 base_url）
    """

    DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
    DEFAULT_MODEL = "mimo-v2.5-pro"

    def __init__(self, api_key: str = None, model: str = None, base_url: str = None):
        """
        初始化 LLM 客户端

        Args:
            api_key: API 密钥
            model: 模型名称
            base_url: API 端点
        """
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or self.DEFAULT_MODEL
        self.base_url = base_url or os.getenv("LLM_BASE_URL", self.DEFAULT_BASE_URL)

        if not self.api_key:
            raise ValueError("LLM API key 未设置。请设置环境变量 LLM_API_KEY，或在初始化时传入 api_key 参数。")

        # 使用 OpenAI 兼容接口
        try:
            import openai

            self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            logger.info(f"WorkBuddy LLM 客户端初始化成功，模型: {self.model}，端点: {self.base_url}")
        except ImportError:
            logger.error("openai 库未安装，请运行: pip install openai")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数
                - temperature: 温度参数（默认 0.7）
                - max_tokens: 最大 token 数（默认 2000）
                - system_prompt: 系统 prompt

        Returns:
            str: 生成的文本
        """
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2000)
        system_prompt = kwargs.get("system_prompt", "你是一个量化因子挖掘专家。")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"WorkBuddy LLM API 调用失败: {e}")
            raise

    def generate_with_json_output(self, prompt: str, **kwargs) -> dict[str, Any]:
        """
        生成 JSON 格式的输出

        Args:
            prompt: 输入 prompt
            **kwargs: 其他参数

        Returns:
            dict: 解析后的 JSON
        """
        json_prompt = f"""
{prompt}

请以 JSON 格式输出结果，确保输出是有效的 JSON。
"""

        response = self.generate(json_prompt, **kwargs)

        try:
            json_str = self._extract_json_from_response(response)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.error(f"原始响应: {response}")
            raise

    def _extract_json_from_response(self, response: str) -> str:
        """从响应中提取 JSON"""
        import re

        # 尝试从 markdown 代码块中提取
        json_block_pattern = r"```json\s*\n(.*?)```"
        match = re.search(json_block_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 尝试提取 { 开始的 JSON
        json_pattern = r"(\{.*\})"
        match = re.search(json_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        return response.strip()


# 示例用法
if __name__ == "__main__":
    # 测试 MockLLMClient
    client = MockLLMClient()

    prompt = "请生成一个动量因子"
    response = client.generate(prompt)

    print("响应:")
    print(response)
