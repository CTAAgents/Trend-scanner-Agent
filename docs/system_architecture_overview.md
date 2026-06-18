# QuantNova 系统架构总览

> 版本：v2.0.0 | 创建日期：2026-06-18
> 状态：双子系统架构（期货+证券）

---

## 一、系统概述

QuantNova 是一个推理重于规则的量化交易决策辅助系统，支持期货和证券（股票/ETF/可转债/REITs）双市场。

**核心理念**：以人为本，推理为魂，规则为果。

**系统运行原则（必须遵守）**：

| 原则 | 说明 |
|------|------|
| **数据第一原则** | 绝对禁止使用模拟数据，分析必须使用真实数据，必须确保数据的可靠性和时效性 |
| **时效性原则** | 每次分析前必须验证数据时间，数据滞后超过1天需向用户确认 |
| **数据不可用原则** | 数据源不可用时，明确告知用户，不提供基于假设的建议 |
| **期货数据源优先级** | TqSdk（首选）> 通达信MCP > AKShare > 本地缓存 |
| **证券数据源优先级** | 通达信MCP（首选）> NeoData金融搜索 > WeStock Data > 本地缓存 |

**通达信MCP数据能力（证券首选数据源）**：
- 实时行情：tdx_quotes、tdx_kline、tdx_screener
- 财务数据：利润表、资产负债表、现金流量表、财务指标
- 股东数据：股东人数、十大股东、机构持股、控股股东
- 分红数据：分红历史、股息率、配股/增发
- 交易数据：龙虎榜、大宗交易、融资融券、资金流向、北向资金
- 行业数据：产业链、重要事件、行业排名
- 宏观数据：GDP、CPI、PPI、利率、汇率
- 研报数据：券商研报、评级调整、目标价

**架构特点**：
- 双子系统分离：期货子系统 + 证券子系统
- 共享核心模块：推理引擎、因子进化框架、记忆系统
- 市场抽象层：统一接口，多态实现
- 文档先行、测试驱动：遵循 CONTRIBUTING.md 规范

---

## 二、系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          QuantNova 双子系统架构                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    共享核心模块 (Shared Core)                  │   │
│  │                                                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │   │
│  │  │ 推理引擎     │  │ 因子进化框架 │  │ 记忆系统    │        │   │
│  │  │ Reasoning   │  │ FactorEvo   │  │ Memory      │        │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │   │
│  │                                                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │   │
│  │  │ 审计轨迹     │  │ V3.0方案    │  │ Prompt路由器 │        │   │
│  │  │ AuditTrail  │  │ V3.0        │  │ PromptRouter│        │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                    │                                │
│  ┌─────────────────────────────────┴─────────────────────────────┐ │
│  │                    市场抽象层 (Market Abstraction)              │ │
│  │                                                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │ │
│  │  │ MarketProvider  │  │ BaseRiskManager │  │ MarketType  │ │ │
│  │  │ (抽象基类)      │  │ (抽象基类)      │  │ (枚举)      │ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────┘ │ │
│  └─────────────────────────────────┬─────────────────────────────┘ │
│                                    │                                │
│          ┌─────────────────────────┴─────────────────────────┐     │
│          │                                                     │     │
│  ┌───────┴───────────────────┐   ┌───────────────────────────┴──┐ │
│  │                           │   │                              │ │
│  │    期货子系统 (Futures)     │   │     证券子系统 (Securities)    │ │
│  │                           │   │                              │ │
│  │  ┌─────────────────────┐  │   │  ┌─────────────────────┐    │ │
│  │  │ FuturesProvider     │  │   │  │ SecuritiesProvider  │    │ │
│  │  │ (TqSdk首选)        │  │   │  │ (通达信MCP首选)     │    │ │
│  │  └─────────────────────┘  │   │  └─────────────────────┘    │ │
│  │                           │   │                              │ │
│  │  ┌─────────────────────┐  │   │  ┌─────────────────────┐    │ │
│  │  │ FuturesMarketCtx    │  │   │  │SecuritiesMarketCtx  │    │ │
│  │  │ • 持仓量            │  │   │  │ • PE/PB/ROE         │    │ │
│  │  │ • 基差              │  │   │  │ • 财务数据          │    │ │
│  │  │ • 期限结构          │  │   │  │ • 股东变动          │    │ │
│  │  │ • 库存              │  │   │  │ • 折溢价率          │    │ │
│  │  └─────────────────────┘  │   │  └─────────────────────┘    │ │
│  │                           │   │                              │ │
│  │  ┌─────────────────────┐  │   │  ┌─────────────────────┐    │ │
│  │  │ FuturesFactorLib    │  │   │  │SecuritiesFactorLib  │    │ │
│  │  │ • 基差因子          │  │   │  │ • 估值因子          │    │ │
│  │  │ • 库存因子          │  │   │  │ • 质量因子          │    │ │
│  │  │ • 持仓量因子        │  │   │  │ • 情绪因子          │    │ │
│  │  └─────────────────────┘  │   │  └─────────────────────┘    │ │
│  │                           │   │                              │ │
│  │  ┌─────────────────────┐  │   │  ┌─────────────────────┐    │ │
│  │  │ FuturesRiskMgr      │  │   │  │SecuritiesRiskMgr    │    │ │
│  │  │ • 保证金/杠杆       │  │   │  │ • T+1交割           │    │ │
│  │  │ • T+0日内           │  │   │  │ • 涨跌停板          │    │ │
│  │  │ • 交割月管理        │  │   │  │ • 流动性风险        │    │ │
│  │  └─────────────────────┘  │   │  └─────────────────────┘    │ │
│  │                           │   │                              │ │
│  │  ┌─────────────────────┐  │   │  ┌─────────────────────┐    │ │
│  │  │ 期货策略            │  │   │  │ 证券策略            │    │ │
│  │  │ • 趋势跟踪          │  │   │  │ • StockStrategy     │    │ │
│  │  │ • Carry策略          │  │   │  │ • ETFStrategy       │    │ │
│  │  │ • 套利策略          │  │   │  │ • ConvertBondStrat  │    │ │
│  │  └─────────────────────┘  │   │  │ • REITsStrategy     │    │ │
│  │                           │   │  └─────────────────────┘    │ │
│  │  ┌─────────────────────┐  │   │  ┌─────────────────────┐    │ │
│  │  │ 期货Prompt          │  │   │  │ 证券Prompt          │    │ │
│  │  │ • T+0逻辑           │  │   │  │ • T+1逻辑           │    │ │
│  │  │ • 杠杆思维          │  │   │  │ • 估值思维          │    │ │
│  │  │ • 基差/库存分析     │  │   │  │ • 财务/股东分析     │    │ │
│  │  └─────────────────────┘  │   │  └─────────────────────┘    │ │
│  │                           │   │                              │ │
│  └───────────────────────────┘   └──────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心工作流

### 3.1 期货市场分析工作流

```
用户请求（期货品种）
    ↓
PromptRouter.get_prompt("futures") → 获取期货Prompt
    ↓
FuturesProvider.get_kline() → 获取K线数据
    ↓
FuturesFactorLibrary.calculate_*() → 计算因子
    ↓
FuturesMarketContext → 组装市场上下文
    ↓
ReasoningEngine.reason() → LLM推理（期货Prompt）
    ↓
FuturesRiskManager.calculate_*() → 风险管理
    ↓
输出决策简报
```

### 3.2 证券市场分析工作流

```
用户请求（证券品种）
    ↓
PromptRouter.get_prompt("securities") → 获取证券Prompt
    ↓
SecuritiesProvider.get_kline() → 获取K线数据
    ↓
SecuritiesFactorLibrary.calculate_*() → 计算因子
    ↓
SecuritiesMarketContext → 组装市场上下文
    ↓
ReasoningEngine.reason() → LLM推理（证券Prompt）
    ↓
SecuritiesRiskManager.calculate_*() → 风险管理
    ↓
输出决策简报
```

---

## 四、数据流

### 4.1 数据获取

```
通达信MCP → FuturesProvider / SecuritiesProvider
    ↓
K线数据 + 基本面数据
    ↓
MarketContext（期货/证券各自的数据模型）
```

### 4.2 因子计算

```
MarketContext → FactorLibrary（完全独立）
    ↓
期货因子：基差、库存、持仓量、期限结构
证券因子：估值、质量、情绪、动量
    ↓
因子得分
```

### 4.3 风险管理

```
MarketContext + FactorScores → RiskManager（各自独立）
    ↓
期货风控：保证金/杠杆/T+0
证券风控：T+1/涨跌停/流动性
    ↓
风险指标 + 止损止盈
```

---

## 五、模块清单

### 5.1 共享核心模块

| 模块 | 路径 | 功能 |
|------|------|------|
| MarketProvider | `scripts/core/market_provider.py` | 市场数据提供者抽象基类 |
| BaseRiskManager | `scripts/core/base_risk_manager.py` | 风险管理器抽象基类 |
| ModuleRegistry | `scripts/core/module_registry.py` | 模块注册中心 |
| ReasoningEngine | `scripts/reasoning/reasoning_engine.py` | 推理引擎 |
| PromptRouter | `scripts/reasoning/prompt_router.py` | Prompt路由器 |

### 5.2 期货子系统

| 模块 | 路径 | 功能 |
|------|------|------|
| FuturesProvider | `scripts/futures/provider.py` | 期货数据提供者 |
| FuturesMarketContext | `scripts/futures/market_context.py` | 期货市场上下文 |
| FuturesFactorLibrary | `scripts/futures/factor_library.py` | 期货因子库 |
| FuturesRiskManager | `scripts/futures/risk_manager.py` | 期货风控 |
| TrendStrategy | `scripts/futures/strategy/trend.py` | 趋势策略 |
| CarryStrategy | `scripts/futures/strategy/carry.py` | Carry策略 |
| ArbitrageStrategy | `scripts/futures/strategy/arbitrage.py` | 套利策略 |
| FuturesPrompt | `scripts/reasoning/futures_prompt.py` | 期货Prompt |

### 5.3 证券子系统

| 模块 | 路径 | 功能 |
|------|------|------|
| SecuritiesProvider | `scripts/securities/provider.py` | 证券数据提供者 |
| SecuritiesMarketContext | `scripts/securities/market_context.py` | 证券市场上下文 |
| SecuritiesFactorLibrary | `scripts/securities/factor_library.py` | 证券因子库 |
| SecuritiesRiskManager | `scripts/securities/risk_manager.py` | 证券风控 |
| StockStrategy | `scripts/securities/strategy/stock.py` | 股票策略 |
| ETFStrategy | `scripts/securities/strategy/etf.py` | ETF策略 |
| REITsStrategy | `scripts/securities/strategy/reits.py` | REITs策略 |
| ConvertibleBondStrategy | `scripts/securities/convertible_bond/strategy.py` | 可转债策略 |
| ConvertibleBondRiskManager | `scripts/securities/convertible_bond/risk_manager.py` | 可转债风控 |
| SecuritiesPrompt | `scripts/reasoning/securities_prompt.py` | 证券Prompt |

---

## 六、技术栈

| 组件 | 技术 |
|------|------|
| 数据源 | 通达信MCP（默认） |
| 推理引擎 | LLM + Prompt模板 |
| 因子计算 | Python + NumPy + Pandas |
| 风险管理 | Python + 自研算法 |
| 测试框架 | pytest |

---

## 七、配置管理

```json
{
  "market_type": "futures",
  "active_subsystem": "futures",
  "data_source": "tdx_mcp",
  "subsystems": {
    "futures": {
      "margin_rate": 0.1,
      "leverage": 10
    },
    "securities": {
      "t_plus_1": true,
      "limit_up_pct": 0.1
    }
  }
}
```

---

*本文档由 WorkBuddy 于 2026-06-18 创建*
