# 证券子系统设计文档

> 版本：v1.0 | 创建日期：2026-06-18
> 关联：dual_subsystem_implementation_plan.md Phase 3

---

## 一、设计目标

开发证券子系统，支持：
- 股票（个股）
- ETF（场内基金）
- 可转债
- REITs

---

## 二、目录结构

```
scripts/securities/
├── __init__.py
├── provider.py           # SecuritiesProvider
├── market_context.py     # SecuritiesMarketContext
├── factor_library.py     # SecuritiesFactorLibrary
├── risk_manager.py       # SecuritiesRiskManager
├── convertible_bond/
│   ├── __init__.py
│   ├── strategy.py       # ConvertibleBondStrategy
│   └── risk_manager.py   # ConvertibleBondRiskManager
├── strategy/
│   ├── __init__.py
│   ├── stock.py          # StockStrategy
│   ├── etf.py            # ETFStrategy
│   └── reits.py          # REITsStrategy
└── fundamental.py        # 证券基本面
```

---

## 三、核心接口

### 3.1 SecuritiesProvider

```python
class SecuritiesProvider(MarketProvider):
    """证券数据提供者"""
    
    def _get_market_type(self) -> MarketType:
        return MarketType.SECURITIES
    
    def get_kline(self, symbol, timeframe="daily", count=100) -> pd.DataFrame:
        """获取证券K线数据"""
        pass
    
    def get_realtime_quote(self, symbol) -> dict:
        """获取证券实时行情"""
        pass
    
    def get_symbols(self) -> list:
        """获取证券品种列表"""
        pass
    
    def get_fundamental(self, symbol) -> dict:
        """获取证券基本面数据（财务/估值/股东）"""
        pass
    
    def get_financial_data(self, symbol) -> dict:
        """获取财务数据"""
        pass
    
    def get_valuation(self, symbol) -> dict:
        """获取估值数据"""
        pass
    
    def get_shareholder_data(self, symbol) -> dict:
        """获取股东数据"""
        pass
```

### 3.2 SecuritiesMarketContext

```python
@dataclass
class SecuritiesMarketContext:
    """证券市场上下文"""
    symbol: str
    timestamp: str
    current_price: float
    
    # 证券专属字段
    pe_ratio: float           # PE
    pb_ratio: float           # PB
    roe: float                # ROE
    dividend_yield: float     # 股息率
    
    # ETF专属
    premium_discount: float   # 折溢价率
    tracking_error: float     # 跟踪误差
    nav: float                # 净值
    
    # 可转债专属
    conversion_premium: float # 转股溢价率
    pure_bond_value: float    # 纯债价值
    conversion_price: float   # 转股价
    
    # REITs专属
    distribution_yield: float # 分红收益率
    nav_premium: float        # NAV折溢价
    
    # 通用字段
    indicators: IndicatorSnapshot
    trend_phase: TrendPhase
    structure: MarketStructure
    momentum: MomentumState
    volatility: VolatilityState
```

### 3.3 SecuritiesFactorLibrary

```python
class SecuritiesFactorLibrary:
    """证券因子库（完全独立）"""
    
    def calculate_valuation_factors(self, data: pd.DataFrame) -> dict:
        """计算估值因子"""
        pass
    
    def calculate_quality_factors(self, data: pd.DataFrame) -> dict:
        """计算质量因子"""
        pass
    
    def calculate_sentiment_factors(self, data: pd.DataFrame) -> dict:
        """计算情绪因子"""
        pass
    
    def calculate_momentum_factors(self, data: pd.DataFrame) -> dict:
        """计算动量因子"""
        pass
```

### 3.4 SecuritiesRiskManager

```python
class SecuritiesRiskManager(BaseRiskManager):
    """证券风控"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.t_plus_1 = config.get("t_plus_1", True)
        self.limit_up_pct = config.get("limit_up_pct", 0.1)
    
    def calculate_position_size(self, signal, capital, current_price) -> float:
        """计算仓位（全额资金）"""
        pass
    
    def check_t_plus_1(self, trade_date) -> bool:
        """检查T+1限制"""
        pass
    
    def check_limit(self, price, prev_close) -> bool:
        """检查涨跌停"""
        pass
```

---

## 四、测试要求

详见 `tests/test_securities_subsystem.py`

---

*本文档由 WorkBuddy 于 2026-06-18 创建*
