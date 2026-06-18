"""
证券市场上下文

定义证券市场的数据模型
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
class SecuritiesMarketContext:
    """
    证券市场上下文

    包含证券特有的数据字段
    """
    symbol: str
    timestamp: str
    current_price: float

    # 证券专属字段
    pe_ratio: float = 0.0  # PE
    pb_ratio: float = 0.0  # PB
    roe: float = 0.0  # ROE
    dividend_yield: float = 0.0  # 股息率

    # ETF专属
    premium_discount: float = 0.0  # 折溢价率
    tracking_error: float = 0.0  # 跟踪误差
    nav: float = 0.0  # 净值

    # 可转债专属
    conversion_premium: float = 0.0  # 转股溢价率
    pure_bond_value: float = 0.0  # 纯债价值
    conversion_price: float = 0.0  # 转股价

    # REITs专属
    distribution_yield: float = 0.0  # 分红收益率
    nav_premium: float = 0.0  # NAV折溢价

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
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "roe": self.roe,
            "dividend_yield": self.dividend_yield,
            "premium_discount": self.premium_discount,
            "tracking_error": self.tracking_error,
            "nav": self.nav,
            "conversion_premium": self.conversion_premium,
            "pure_bond_value": self.pure_bond_value,
            "conversion_price": self.conversion_price,
            "distribution_yield": self.distribution_yield,
            "nav_premium": self.nav_premium,
        }

    def to_prompt_text(self) -> str:
        """转换为推理层可读的文本"""
        lines = [
            f"【{self.symbol} 证券数据】时间：{self.timestamp}",
            f"当前价格：{self.current_price:.2f}",
            "",
            "## 估值数据",
            f"- PE：{self.pe_ratio:.2f}",
            f"- PB：{self.pb_ratio:.2f}",
            f"- ROE：{self.roe:.2f}%",
            f"- 股息率：{self.dividend_yield:.2%}",
        ]

        if self.premium_discount != 0:
            lines.append("")
            lines.append("## ETF数据")
            lines.append(f"- 折溢价率：{self.premium_discount:.2%}")
            lines.append(f"- 净值：{self.nav:.2f}")

        if self.conversion_premium != 0:
            lines.append("")
            lines.append("## 可转债数据")
            lines.append(f"- 转股溢价率：{self.conversion_premium:.2%}")
            lines.append(f"- 纯债价值：{self.pure_bond_value:.2f}")
            lines.append(f"- 转股价：{self.conversion_price:.2f}")

        if self.distribution_yield != 0:
            lines.append("")
            lines.append("## REITs数据")
            lines.append(f"- 分红收益率：{self.distribution_yield:.2%}")
            lines.append(f"- NAV折溢价：{self.nav_premium:.2%}")

        return "\n".join(lines)
