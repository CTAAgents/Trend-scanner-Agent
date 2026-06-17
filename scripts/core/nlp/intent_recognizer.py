"""
意图识别器

识别用户自然语言输入的意图：
- 查询意图
- 操作意图
- 设置意图
- 分析意图
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class IntentType(Enum):
    """意图类型"""
    QUERY = "query"           # 查询
    ACTION = "action"         # 操作
    SETTING = "setting"       # 设置
    ANALYSIS = "analysis"     # 分析
    HELP = "help"             # 帮助
    STATUS = "status"         # 状态
    UNKNOWN = "unknown"       # 未知


@dataclass
class Intent:
    """意图"""
    intent_type: IntentType
    action: str
    parameters: Dict[str, Any]
    confidence: float
    raw_text: str


class IntentRecognizer:
    """意图识别器"""

    def __init__(self):
        self.patterns = self._init_patterns()

    def _init_patterns(self) -> Dict[IntentType, List[Dict]]:
        """初始化意图模式"""
        return {
            IntentType.QUERY: [
                {"pattern": r"(查看|显示|查询|获取).*(信号|行情|持仓|状态)", "action": "query"},
                {"pattern": r"(什么|哪些).*(品种|合约|信号)", "action": "query"},
                {"pattern": r"(现在|当前).*(价格|行情)", "action": "query"},
            ],
            IntentType.ACTION: [
                {"pattern": r"(扫描|扫描一下|运行扫描)", "action": "scan"},
                {"pattern": r"(进化|因子进化|运行进化)", "action": "evolve"},
                {"pattern": r"(同步|数据同步|更新数据)", "action": "sync"},
                {"pattern": r"(评估|健康度|检查)", "action": "health_check"},
                {"pattern": r"(套利|价差|套利分析)", "action": "arbitrage"},
            ],
            IntentType.SETTING: [
                {"pattern": r"(设置|配置|调整).*(参数|配置)", "action": "setting"},
                {"pattern": r"(开启|启用|关闭).*(功能|模式)", "action": "toggle"},
            ],
            IntentType.ANALYSIS: [
                {"pattern": r"(分析|深度分析|详细分析)", "action": "analyze"},
                {"pattern": r"(为什么|原因|解释)", "action": "explain"},
                {"pattern": r"(预测|预估|预期)", "action": "predict"},
            ],
            IntentType.HELP: [
                {"pattern": r"(帮助|怎么用|如何使用|使用说明)", "action": "help"},
                {"pattern": r"(命令|指令|操作)", "action": "help"},
            ],
            IntentType.STATUS: [
                {"pattern": r"(状态|系统状态|运行状态)", "action": "status"},
                {"pattern": r"(是否|有没有).*(运行|启动)", "action": "status"},
            ],
        }

    def recognize(self, text: str) -> Intent:
        """识别意图"""
        text = text.strip().lower()

        # 尝试匹配每种意图类型
        for intent_type, patterns in self.patterns.items():
            for pattern_info in patterns:
                match = re.search(pattern_info["pattern"], text)
                if match:
                    return Intent(
                        intent_type=intent_type,
                        action=pattern_info["action"],
                        parameters=self._extract_parameters(text),
                        confidence=0.8,
                        raw_text=text,
                    )

        # 未匹配到任何意图
        return Intent(
            intent_type=IntentType.UNKNOWN,
            action="unknown",
            parameters={},
            confidence=0.0,
            raw_text=text,
        )

    def _extract_parameters(self, text: str) -> Dict[str, Any]:
        """提取参数"""
        params = {}

        # 提取品种代码
        symbol_pattern = r"([A-Z]{2}\d{4})"
        symbols = re.findall(symbol_pattern, text.upper())
        if symbols:
            params["symbols"] = symbols

        # 提取数字
        number_pattern = r"(\d+)"
        numbers = re.findall(number_pattern, text)
        if numbers:
            params["numbers"] = [int(n) for n in numbers]

        return params
