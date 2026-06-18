# 期货子系统设计文档

> 版本：v1.0 | 创建日期：2026-06-18
> 关联：dual_subsystem_implementation_plan.md Phase 2

---

## 一、设计目标

将现有期货逻辑迁移到独立的 `scripts/futures/` 子系统，实现：
- FuturesProvider（数据源）
- FuturesMarketContext（数据模型）
- FuturesFactorLibrary（因子库）
- FuturesRiskManager（风控）
- 期货策略模块

---

## 二、目录结构

```
scripts/futures/
├── __init__.py
├── provider.py           # FuturesProvider
├── market_context.py     # FuturesMarketContext
├── factor_library.py     # FuturesFactorLibrary
├── risk_manager.py       # FuturesRiskManager
├── strategy/
│   ├── __init__.py
│   ├── trend.py          # 趋势跟踪策略
│   ├── carry.py          # Carry策略
│   └── arbitrage.py      # 套利策略
└── fundamental.py        # 期货基本面
```

---

## 三、核心接口

### 3.1 FuturesProvider

```python
class FuturesProvider(MarketProvider):
    """期货数据提供者"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.tdx_client = None  # 通达信MCP客户端
    
    def _get_market_type(self) -> MarketType:
        return MarketType.FUTURES
    
    def get_kline(self, symbol, timeframe="daily", count=100) -> pd.DataFrame:
        """获取期货K线数据"""
        pass
    
    def get_realtime_quote(self, symbol) -> dict:
        """获取期货实时行情"""
        pass
    
    def get_symbols(self) -> list:
        """获取期货品种列表"""
        pass
    
    def get_fundamental(self, symbol) -> dict:
        """获取期货基本面数据（库存/仓单/持仓量）"""
        pass
    
    def get_open_interest(self, symbol) -> float:
        """获取持仓量"""
        pass
    
    def get_basis(self, symbol) -> float:
        """获取基差"""
        pass
    
    def get_term_structure(self, symbol) -> dict:
        """获取期限结构"""
        pass
```

### 3.2 FuturesMarketContext

```python
@dataclass
class FuturesMarketContext:
    """期货市场上下文"""
    symbol: str
    timestamp: str
    current_price: float
    
    # 期货专属字段
    open_interest: float      # 持仓量
    basis: float              # 基差
    basis_rate: float         # 基差率
    term_structure: dict      # 期限结构
    inventory: float          # 交易所库存
    warehouse_receipt: float  # 仓单量
    
    # 通用字段
    indicators: IndicatorSnapshot
    trend_phase: TrendPhase
    structure: MarketStructure
    momentum: MomentumState
    volatility: VolatilityState
```

### 3.3 FuturesFactorLibrary

```python
class FuturesFactorLibrary:
    """期货因子库（完全独立）"""
    
    def calculate_basis_factors(self, data: pd.DataFrame) -> dict:
        """计算基差因子"""
        pass
    
    def calculate_inventory_factors(self, data: pd.DataFrame) -> dict:
        """计算库存因子"""
        pass
    
    def calculate_oi_factors(self, data: pd.DataFrame) -> dict:
        """计算持仓量因子"""
        pass
    
    def calculate_term_structure_factors(self, data: pd.DataFrame) -> dict:
        """计算期限结构因子"""
        pass
    
    def calculate_trend_factors(self, data: pd.DataFrame) -> dict:
        """计算趋势因子"""
        pass
    
    def calculate_momentum_factors(self, data: pd.DataFrame) -> dict:
        """计算动量因子"""
        pass
```

### 3.4 FuturesRiskManager

```python
class FuturesRiskManager(BaseRiskManager):
    """期货风控"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.margin_rate = config.get("margin_rate", 0.1)
        self.leverage = config.get("leverage", 10)
    
    def calculate_position_size(self, signal, capital, current_price) -> float:
        """计算仓位（考虑保证金）"""
        pass
    
    def calculate_stop_loss(self, entry_price, signal) -> float:
        """计算止损（ATR止损）"""
        pass
    
    def calculate_take_profit(self, entry_price, signal) -> float:
        """计算止盈"""
        pass
    
    def check_stop_loss(self, position, current_price) -> bool:
        """检查止损"""
        pass
    
    def check_take_profit(self, position, current_price) -> bool:
        """检查止盈"""
        pass
    
    def get_risk_metrics(self, position, current_price) -> RiskMetrics:
        """获取风险指标"""
        pass
    
    def check_margin(self, position, current_price) -> bool:
        """检查保证金是否充足"""
        pass
    
    def check_delivery_month(self, symbol, current_date) -> bool:
        """检查是否接近交割月"""
        pass
```

---

## 四、测试要求

详见 `tests/test_futures_subsystem.py`

---

*本文档由 WorkBuddy 于 2026-06-18 创建*
