"""
响应生成器

生成自然语言响应：
- 响应模板
- 格式化输出
- 错误处理
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Response:
    """响应"""
    text: str
    data: Optional[Dict[str, Any]] = None
    success: bool = True
    error: Optional[str] = None


class ResponseGenerator:
    """响应生成器"""

    def __init__(self):
        self.templates = self._init_templates()

    def _init_templates(self) -> Dict[str, str]:
        """初始化响应模板"""
        return {
            "scan_success": "扫描完成！发现 {count} 个信号。",
            "scan_empty": "扫描完成，当前没有发现明显信号。",
            "evolve_success": "因子进化完成！发现 {count} 个新因子。",
            "sync_success": "数据同步完成！更新了 {count} 个品种。",
            "health_check": "持仓健康度检查完成：\n{details}",
            "arbitrage": "套利分析完成：\n{details}",
            "status": "系统状态：\n{details}",
            "error": "操作失败：{error}",
            "help": "可用命令：\n{commands}",
            "unknown": "抱歉，我不太理解您的意思。请尝试更明确的表达。",
        }

    def generate(self, template_key: str, **kwargs) -> Response:
        """生成响应"""
        template = self.templates.get(template_key, self.templates["unknown"])

        try:
            text = template.format(**kwargs)
            return Response(text=text, success=True)
        except Exception as e:
            return Response(
                text=f"生成响应时出错: {e}",
                success=False,
                error=str(e),
            )

    def format_signal(self, signal: Dict) -> str:
        """格式化信号"""
        symbol = signal.get("symbol", "未知")
        direction = signal.get("direction", "未知")
        strength = signal.get("strength", "未知")
        indicators = signal.get("indicators", "")

        return f"{symbol} {direction} ({strength}) - {indicators}"

    def format_position(self, position: Dict) -> str:
        """格式化持仓"""
        symbol = position.get("symbol", "未知")
        direction = position.get("direction", "未知")
        pnl = position.get("pnl", 0)
        pnl_pct = position.get("pnl_pct", 0)

        return f"{symbol} {direction}: {pnl:+.2f} ({pnl_pct:+.2f}%)"

    def format_error(self, error: str) -> str:
        """格式化错误"""
        return f"错误：{error}"
