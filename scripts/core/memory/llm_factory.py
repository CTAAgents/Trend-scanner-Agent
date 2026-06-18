"""
LLM 提供者工厂

职责：
- 提供统一的 LLM 调用接口
- 支持多种 LLM 提供者（OpenAI/Anthropic/本地模型/WorkBuddy）
- 处理降级和错误恢复

支持的提供者：
- openai: OpenAI GPT-4
- anthropic: Anthropic Claude
- local: 本地模型（Ollama）
- workbuddy: WorkBuddy Agent（默认）
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """LLM 提供者抽象基类"""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 输入提示
            **kwargs: 额外参数（temperature, max_tokens 等）

        Returns:
            生成的文本
        """
        pass

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        """
        对话模式

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            **kwargs: 额外参数

        Returns:
            回复文本
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """提供者名称"""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """模型名称"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI 提供者"""

    def __init__(self, api_key: str, model: str = "gpt-4", timeout: int = 120):
        try:
            import openai

            self.client = openai.OpenAI(api_key=api_key, timeout=timeout)
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

        self._model = model
        self._timeout = timeout

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
        return response.choices[0].message.content

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
        return response.choices[0].message.content

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model


class AnthropicProvider(LLMProvider):
    """Anthropic 提供者"""

    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        try:
            import anthropic

            self.client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("请安装 anthropic: pip install anthropic")

        self._model = model

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.messages.create(
            model=self._model, messages=[{"role": "user", "content": prompt}], max_tokens=kwargs.get("max_tokens", 2000)
        )
        return response.content[0].text

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        response = self.client.messages.create(
            model=self._model, messages=messages, max_tokens=kwargs.get("max_tokens", 2000)
        )
        return response.content[0].text

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model


class LocalLLMProvider(LLMProvider):
    """本地 LLM 提供者（Ollama）"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        try:
            import requests

            self.requests = requests
        except ImportError:
            raise ImportError("请安装 requests: pip install requests")

        self.base_url = base_url
        self._model = model

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
            timeout=kwargs.get("timeout", 60),
        )
        response.raise_for_status()
        return response.json()["response"]

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        response = self.requests.post(
            f"{self.base_url}/api/chat",
            json={"model": self._model, "messages": messages, "stream": False},
            timeout=kwargs.get("timeout", 60),
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    @property
    def name(self) -> str:
        return "local"

    @property
    def model(self) -> str:
        return self._model


class WorkBuddyProvider(LLMProvider):
    """
    LLM 提供者（默认）

    通过 OpenAI 兼容接口调用大模型，支持任意兼容服务商。

    环境变量：
        LLM_API_KEY: API 密钥（必需）
        LLM_BASE_URL: API 端点（可选）
    """

    DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
    DEFAULT_MODEL = "mimo-v2.5-pro"

    def __init__(self, api_key: str = None, model: str = None, base_url: str = None, timeout: int = 120):
        self._api_key = api_key or os.getenv("LLM_API_KEY")
        self._model = model or os.getenv("LLM_MODEL", self.DEFAULT_MODEL)
        self._base_url = base_url or os.getenv("LLM_BASE_URL", self.DEFAULT_BASE_URL)
        self._timeout = timeout
        self._client = None

        if self._api_key:
            try:
                import openai

                self._client = openai.OpenAI(api_key=self._api_key, base_url=self._base_url, timeout=self._timeout)
            except ImportError:
                pass

    def generate(self, prompt: str, **kwargs) -> str:
        if not self._client:
            # LLM 未配置时返回降级响应（由宿主平台的 Agent 驱动推理）
            return json.dumps(
                {
                    "status": "llm_not_configured",
                    "message": "LLM 未配置，推理由宿主平台 Agent 驱动",
                    "suggestion": "如需直接调用 LLM，请设置环境变量 LLM_API_KEY",
                },
                ensure_ascii=False,
            )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", 0.3),
                max_tokens=kwargs.get("max_tokens", 2000),
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(
                f"LLM API 调用失败: {e}\n"
                f"请检查：1) API Key 是否有效；2) 网络连接是否正常；3) 端点 {self._base_url} 是否可达。"
            )

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        if not self._client:
            # LLM 未配置时返回降级响应
            return json.dumps(
                {"status": "llm_not_configured", "message": "LLM 未配置，推理由宿主平台 Agent 驱动"}, ensure_ascii=False
            )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.3),
                max_tokens=kwargs.get("max_tokens", 2000),
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(
                f"LLM API 调用失败: {e}\n"
                f"请检查：1) API Key 是否有效；2) 网络连接是否正常；3) 端点 {self._base_url} 是否可达。"
            )

    def _fallback(self, prompt: str, reason: str = "LLM 不可用") -> str:
        """降级响应"""
        return json.dumps(
            {
                "routes": [
                    {
                        "route_id": "A",
                        "name": "观望等待",
                        "action": "暂不操作，等待更明确的信号",
                        "confidence": 0.5,
                        "reasoning": f"LLM 不可用（{reason}），使用规则退化建议",
                    }
                ],
                "warnings": [f"当前使用规则退化模式: {reason}"],
            },
            ensure_ascii=False,
        )

    @property
    def name(self) -> str:
        return "workbuddy"

    @property
    def model(self) -> str:
        return self._model


class LLMProviderFactory:
    """LLM 提供者工厂"""

    @staticmethod
    def create(config: dict[str, Any]) -> LLMProvider:
        """
        创建 LLM 提供者

        Args:
            config: 配置字典，包含：
                - provider: 提供者名称（openai/anthropic/local/workbuddy）
                - api_key: API 密钥（OpenAI/Anthropic 需要）
                - model: 模型名称
                - base_url: 本地模型 URL

        Returns:
            LLMProvider 实例
        """
        provider = config.get("provider", "workbuddy")

        # 支持环境变量替换
        api_key = config.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")

        # 支持api_key_env字段（环境变量名）
        if not api_key:
            api_key_env = config.get("api_key_env", "")
            if api_key_env:
                api_key = os.environ.get(api_key_env, "")

        # 支持auto模式：优先使用workbuddy，其次尝试openai
        if provider == "auto":
            # 优先使用workbuddy（内置LLM）
            provider = "workbuddy"

        if provider == "openai":
            return OpenAIProvider(
                api_key=api_key, model=config.get("model", "gpt-4"), timeout=config.get("timeout", 120)
            )
        elif provider == "anthropic":
            return AnthropicProvider(api_key=api_key, model=config.get("model", "claude-3-sonnet-20240229"))
        elif provider == "local":
            return LocalLLMProvider(
                base_url=config.get("base_url", "http://localhost:11434"), model=config.get("model", "llama2")
            )
        elif provider == "workbuddy":
            return WorkBuddyProvider(model=config.get("model", "default"))
        else:
            raise ValueError(f"不支持的 LLM 提供者: {provider}")
