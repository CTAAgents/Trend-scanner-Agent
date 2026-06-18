"""
期货市场上下文

定义期货市场的数据模型
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.core.models import (
    IndicatorSnapshot,
    MarketStructure,
    MomentumState,
    TrendPhase,
    VolatilityState,
)


@dataclass
class FuturesMarketContext:
    """
    期货市场上下文

    包含期货特有的数据字段
    """
    symbol: str
    timestamp: str
    current_price: float

    # 期货专属字段
    open_interest: float = 0.0  # 持仓量
    basis: float = 0.0  # 基差
    basis_rate: float = 0.0  # 基差率
    term_structure: Dict[str, float] = field(default_factory=dict)  # 期限结构
    inventory: float = 0.0  # 交易所库存
    warehouse_receipt: float = 0.0  # 仓单量

    # 通用字段
    indicators: IndicatorSnapshot = field(default_factory=lambda: IndicatorSnapshot(
        timestamp="",
        close=0.0,
        high=0.0,
        low=0.0,
        open=0.0,
        volume=0.0,
    ))
    trend_phase: TrendPhase = field(default_factory=TrendPhase)
    structure: MarketStructure = field(default_factory=MarketStructure)
    momentum: MomentumState = field(default_factory=MomentumState)
    volatility: VolatilityState = field(default_factory=VolatilityState)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "current_price": self.current_price,
            "open_interest": self.open_interest,
            "basis": self.basis,
            "basis_rate": self.basis_rate,
            "term_structure": self.term_structure,
            "inventory": self.inventory,
            "warehouse_receipt": self.warehouse_receipt,
        }

    def to_prompt_text(self) -> str:
        """转换为推理层可读的文本"""
        lines = [
            f"【{self.symbol} 期货数据】时间：{self.timestamp}",
            f"当前价格：{self.current_price:.2f}",
            "",
            "## 期货专属数据",
            f"- 持仓量：{self.open_interest:,.0f}",
            f"- 基差：{self.basis:.2f}",
            f"- 基差率：{self.basis_rate:.2%}",
            f"- 交易所库存：{self.inventory:,.0f}",
            f"- 仓单量：{self.warehouse_receipt:,.0f}",
        ]

        if self.term_structure:
            lines.append("- 期限结构：")
            for key, value in self.term_structure.items():
                lines.append(f"  - {key}: {value:.2f}")

        return "\n".join(lines)
