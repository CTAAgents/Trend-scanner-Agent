# QuantNova 双子系统架构设计

> 版本：v1.0 | 创建日期：2026-06-18
> 架构决策：期货/股票双子系统分离

---

## 一、架构设计原则

### 1.1 核心原则

- **共享核心**：推理引擎、因子进化、记忆系统等核心模块完全共享
- **独立适配**：数据源、交易机制、策略逻辑等市场专属模块独立实现
- **统一接口**：通过抽象接口实现多态，上层代码无需关心底层市场差异
- **配置驱动**：通过配置文件切换市场类型，无需修改代码

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          QuantNova 核心系统                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    共享核心模块 (Shared Core)                  │   │
│  │  ReasoningEngine │ FactorEvolution │ MemorySystem │ NLP      │   │
│  │  DebateEngine    │ RiskFramework   │ AuditTrail   │ V3.0     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                    ▲                                │
│                                    │                                │
│  ┌─────────────────────────────────┴─────────────────────────────┐ │
│  │                    市场抽象层 (Market Abstraction)              │ │
│  │         MarketProvider │ StrategyFactory │ RiskAdapter         │ │
│  └─────────────────────────────────┬─────────────────────────────┘ │
│                                    │                                │
│          ┌─────────────────────────┴─────────────────────────┐     │
│          │                                                     │     │
│  ┌───────┴───────────────────┐   ┌───────────────────────────┴──┐ │
│  │    期货子系统 (Futures)     │   │     股票子系统 (Stocks)        │ │
│  │                           │   │                              │ │
│  │  FuturesProvider          │   │  StocksProvider              │ │
│  │  ├─ TqSdk数据源           │   │  ├─ Tushare/AkShare数据源    │ │
│  │  ├─ 主力合约映射          │   │  ├─ 个股行情                 │ │
│  │  ├─ 持仓量/基差           │   │  ├─ 财务数据                 │ │
│  │  └─ 期限结构              │   │  └─ 估值指标                 │ │
│  │                           │   │                              │ │
│  │  FuturesStrategy          │   │  StocksStrategy              │ │
│  │  ├─ 趋势跟踪              │   │  ├─ 价值投资                 │ │
│  │  ├─ Carry策略              │   │  ├─ 成长股                   │ │
│  │  ├─ 套利策略              │   │  ├─ 动量/反转                 │ │
│  │  └─ 跨品种对冲            │   │  └─ 行业轮动                 │ │
│  │                           │   │                              │ │
│  │  FuturesRiskManager       │   │  StocksRiskManager           │ │
│  │  ├─ 保证金/杠杆           │   │  ├─ T+1交割                  │ │
│  │  ├─ T+0日内               │   │  ├─ 涨跌停板                 │ │
│  │  ├─ 强平风险              │   │  ├─ 停牌/ST风险               │ │
│  │  └─ 交割月管理            │   │  └─ 流动性风险               │ │
│  │                           │   │                              │ │
│  │  FuturesTradingEnv        │   │  StocksTradingEnv            │ │
│  │  └─ Gym环境               │   │  └─ Gym环境                  │ │
│  └───────────────────────────┘   └──────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构

```
QuantNova/
├── scripts/
│   ├── core/                    # 共享核心模块
│   │   ├── models.py           # 数据模型（扩展支持股票）
│   │   ├── context.py          # 上下文组装器
│   │   ├── module_registry.py  # 模块注册中心
│   │   └── ...
│   │
│   ├── reasoning/               # 共享推理模块
│   │   ├── reasoning_engine.py
│   │   ├── debate_engine.py
│   │   └── ...
│   │
│   ├── evolution/               # 共享因子进化
│   │   └── ...
│   │
│   ├── risk/                    # 共享风险框架
│   │   └── ...
│   │
│   ├── futures/                 # 期货子系统
│   │   ├── __init__.py
│   │   ├── provider.py         # FuturesProvider
│   │   ├── data_source.py      # TqSdk数据源
│   │   ├── strategy.py         # 期货策略
│   │   ├── risk_manager.py     # 期货风控
│   │   ├── trading_env.py      # 期货Gym环境
│   │   └── fundamental.py      # 期货基本面（库存/仓单）
│   │
│   └── stocks/                  # 股票子系统
│       ├── __init__.py
│       ├── provider.py         # StocksProvider
│       ├── data_source.py      # Tushare/AkShare数据源
│       ├── strategy.py         # 股票策略
│       ├── risk_manager.py     # 股票风控
│       ├── trading_env.py      # 股票Gym环境
│       └── fundamental.py      # 股票基本面（财务/估值）
│
├── config/
│   ├── config.json             # 主配置
│   ├── futures_config.json     # 期货配置
│   └── stocks_config.json      # 股票配置
│
└── tests/
    ├── test_futures/           # 期货子系统测试
    └── test_stocks/            # 股票子系统测试
```

---

## 三、共享核心模块

### 3.1 推理引擎（完全共享）

| 模块 | 功能 | 适配方式 |
|------|------|----------|
| `ReasoningEngine` | LLM推理 | 无需修改，Prompt自动适配 |
| `TriadDebateEngine` | 三方辩论 | 无需修改 |
| `HallucinationDetector` | 幻觉检测 | 无需修改 |
| `AdaptivePromptRouter` | 自适应Prompt | 添加股票场景模板 |

### 3.2 因子进化（完全共享）

| 模块 | 功能 | 适配方式 |
|------|------|----------|
| `FactorEvolutionEngine` | 因子进化 | 无需修改 |
| `FactorGenerator` | 因子生成 | 无需修改 |
| `FactorEvaluator` | 因子评估 | 无需修改 |

### 3.3 风险框架（接口共享）

```python
# 共享的风险评估接口
class BaseRiskManager(ABC):
    @abstractmethod
    def calculate_position_size(self, signal, capital) -> float:
        """计算仓位大小"""
        pass
    
    @abstractmethod
    def check_stop_loss(self, position, current_price) -> bool:
        """检查止损"""
        pass
    
    @abstractmethod
    def get_risk_metrics(self) -> dict:
        """获取风险指标"""
        pass
```

---

## 四、期货子系统

### 4.1 FuturesProvider

```python
class FuturesProvider:
    """期货数据提供者"""
    
    def __init__(self, config: dict):
        self.tqsdk_bridge = TqSdkBridge(config)
    
    def get_kline(self, symbol, timeframe, count) -> pd.DataFrame:
        """获取K线数据"""
        # TqSdk实现
        pass
    
    def get_main_contract(self, symbol) -> str:
        """获取主力合约"""
        pass
    
    def get_term_structure(self, symbol) -> TermStructure:
        """获取期限结构"""
        pass
    
    def get_inventory(self, symbol) -> InventoryData:
        """获取库存数据"""
        pass
```

### 4.2 FuturesRiskManager

```python
class FuturesRiskManager(BaseRiskManager):
    """期货风控"""
    
    def __init__(self, config: dict):
        self.margin_rate = config.get("margin_rate", 0.1)  # 保证金率
        self.leverage = config.get("leverage", 10)  # 杠杆倍数
    
    def calculate_position_size(self, signal, capital) -> float:
        """期货仓位计算（考虑保证金）"""
        # 仓位 = 资金 × 风险比例 / (保证金 × 杠杆)
        pass
    
    def check_margin(self, position, current_price) -> bool:
        """检查保证金是否充足"""
        pass
```

### 4.3 期货专属策略

| 策略 | 说明 |
|------|------|
| 趋势跟踪 | 基于技术指标的趋势跟踪 |
| Carry策略 | 期限结构套利（Contango/Backwardation） |
| 跨期套利 | 不同月份合约价差交易 |
| 跨品种套利 | 相关品种价差交易（如RB-I） |

---

## 五、股票子系统

### 5.1 StocksProvider

```python
class StocksProvider:
    """股票数据提供者"""
    
    def __init__(self, config: dict):
        self.tushare_client = TushareClient(config)
    
    def get_kline(self, symbol, timeframe, count) -> pd.DataFrame:
        """获取K线数据"""
        pass
    
    def get_fundamental(self, symbol) -> FundamentalData:
        """获取财务数据"""
        # PE/PB/ROE/营收增速等
        pass
    
    def get_shareholder(self, symbol) -> ShareholderData:
        """获取股东数据"""
        pass
    
    def get_block_trade(self, symbol) -> pd.DataFrame:
        """获取大宗交易"""
        pass
```

### 5.2 StocksRiskManager

```python
class StocksRiskManager(BaseRiskManager):
    """股票风控"""
    
    def __init__(self, config: dict):
        self.t_plus_1 = True  # T+1交割
        self.limit_up_pct = config.get("limit_up", 0.1)  # 涨停板10%
    
    def calculate_position_size(self, signal, capital) -> float:
        """股票仓位计算（全额资金）"""
        # 仓位 = 资金 × 风险比例 / 股价
        pass
    
    def check_t_plus_1(self, trade_date) -> bool:
        """检查T+1限制"""
        pass
    
    def check_limit(self, price, prev_close) -> bool:
        """检查涨跌停"""
        pass
```

### 5.3 股票专属策略

| 策略 | 说明 |
|------|------|
| 价值投资 | 低PE、高股息、低PB |
| 成长股 | 营收增速、净利润增速、研发投入 |
| 动量策略 | 价格动量、成交量配合 |
| 反转策略 | 超跌反弹、均值回归 |
| 行业轮动 | 行业景气度、资金流向 |

---

## 六、配置管理

### 6.1 主配置（config.json）

```json
{
  "market_type": "futures",
  "active_subsystem": "futures",
  "subsystems": {
    "futures": "config/futures_config.json",
    "stocks": "config/stocks_config.json"
  }
}
```

### 6.2 期货配置（futures_config.json）

```json
{
  "data_source": "tqsdk",
  "symbols": ["RB", "I", "J", "JM", "SC"],
  "margin_rate": 0.1,
  "leverage": 10,
  "trading_hours": {
    "day": ["09:00-11:30", "13:30-15:00"],
    "night": ["21:00-23:00"]
  }
}
```

### 6.3 股票配置（stocks_config.json）

```json
{
  "data_source": "tushare",
  "symbols": ["000001.SZ", "600519.SH"],
  "market": "A股",
  "t_plus_1": true,
  "limit_up_pct": 0.1,
  "min_trade_unit": 100
}
```

---

## 七、使用示例

### 7.1 切换市场类型

```python
# 期货模式
from scripts.futures.provider import FuturesProvider
from scripts.futures.risk_manager import FuturesRiskManager

provider = FuturesProvider(config)
risk_manager = FuturesRiskManager(config)

# 股票模式
from scripts.stocks.provider import StocksProvider
from scripts.stocks.risk_manager import StocksRiskManager

provider = StocksProvider(config)
risk_manager = StocksRiskManager(config)
```

### 7.2 统一接口调用

```python
# 无论期货还是股票，使用相同的接口
context = assembler.assemble(df)
result = reasoning_engine.reason(context, experiences)
risk_check = risk_manager.check_stop_loss(position, current_price)
```

---

## 八、实施计划

### Phase 1：市场抽象层（1周）
- 创建 `MarketProvider` 抽象基类
- 创建 `BaseRiskManager` 抽象基类
- 创建 `StrategyFactory`

### Phase 2：期货子系统迁移（1周）
- 将现有期货逻辑迁移到 `scripts/futures/`
- 实现 `FuturesProvider`
- 实现 `FuturesRiskManager`

### Phase 3：股票子系统开发（2周）
- 实现 `StocksProvider`（Tushare/AkShare）
- 实现 `StocksRiskManager`
- 实现股票策略模块

### Phase 4：测试与集成（1周）
- 编写期货子系统测试
- 编写股票子系统测试
- 集成测试

**总计：5周**

---

*本文档由 WorkBuddy 于 2026-06-18 创建*
