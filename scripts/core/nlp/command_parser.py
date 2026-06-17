"""
命令解析器

将自然语言意图转换为系统命令：
- 意图到命令映射
- 参数验证
- 命令生成
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .intent_recognizer import Intent, IntentType


@dataclass
class Command:
    """命令"""
    command: str
    args: List[str]
    kwargs: Dict[str, Any]
    description: str


class CommandParser:
    """命令解析器"""

    def __init__(self):
        self.command_map = self._init_command_map()

    def _init_command_map(self) -> Dict[str, Dict]:
        """初始化命令映射"""
        return {
            "scan": {
                "command": "python tools/scan_opportunities.py",
                "args_template": ["--output", "text", "--save"],
                "description": "执行市场扫描",
            },
            "evolve": {
                "command": "python tools/scan_opportunities.py",
                "args_template": ["--evolve", "--evolve-rounds", "3"],
                "description": "执行因子进化",
            },
            "sync": {
                "command": "python tools/sync_data.py",
                "args_template": ["sync", "--days", "120"],
                "description": "同步数据",
            },
            "health_check": {
                "command": "python tools/scan_opportunities.py",
                "args_template": ["--position-health"],
                "description": "检查持仓健康度",
            },
            "arbitrage": {
                "command": "python tools/scan_opportunities.py",
                "args_template": ["--arbitrage", "--output", "text"],
                "description": "套利分析",
            },
            "status": {
                "command": "python scripts/core/main.py",
                "args_template": ["--status"],
                "description": "查看系统状态",
            },
        }

    def parse(self, intent: Intent) -> Optional[Command]:
        """解析意图为命令"""
        if intent.action == "unknown":
            return None

        if intent.action not in self.command_map:
            return None

        cmd_info = self.command_map[intent.action]

        # 构建命令
        args = cmd_info["args_template"].copy()

        # 添加参数
        if "symbols" in intent.parameters:
            args.extend(["--symbols", ",".join(intent.parameters["symbols"])])

        return Command(
            command=cmd_info["command"],
            args=args,
            kwargs={},
            description=cmd_info["description"],
        )

    def get_help(self) -> str:
        """获取帮助信息"""
        lines = ["可用命令："]
        for action, info in self.command_map.items():
            lines.append(f"  {action}: {info['description']}")
        return "\n".join(lines)
