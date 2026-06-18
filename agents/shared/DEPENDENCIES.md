# QuantNova 依赖模块文档

> 版本：v1.0 | 创建日期：2026-06-15
> 所有 Agent 共享的依赖模块说明

## 一、核心模块

### 1.1 数据模型（models.py）

**路径**：`scripts/trend_scanner/models.py`

**职责**：定义所有数据结构

**主要类**：
- `IndicatorSnapshot` - 指标快照
- `MarketStructure` - 市场结构
- `MomentumState` - 动量状态
- `VolatilityState` - 波动率状态
- `TrendPhase` - 趋势阶段
- `MarketContext` - 市场上下文
- `TradingBrief` - 交易决策简报
- `UserFeedback` - 用户反馈
- `Experience` - 经验记录
- `ExperienceMatch` - 经验匹配

**使用者**：所有 Agent

### 1.2 数据源（data_source.py）

**路径**：`scripts/trend_scanner/data_source.py`

**职责**：提供统一的数据获取接口

**主要类**：
- `DataSource` - 数据源基类
- `TqSdkSource` - TqSdk 数据源
- `CsvSource` - 本地 CSV 数据源
- `DataSourceFactory` - 数据源工厂

**使用者**：Scanner 脚本、Monitor 脚本、Reasoner Agent

**使用示例**：
```python
from trend_scanner.data_source import DataSourceFactory

# 自动选择数据源
ds = DataSourceFactory.create()
df = ds.get_kline("RB", days=120)

# 指定数据源
ds = DataSourceFactory.create(source="csv")
df = ds.get_kline("RB", days=120)
```

### 1.3 技术指标（indicators.py）

**路径**：`scripts/trend_scanner/indicators.py`

**职责**：计算技术指标

**主要类**：
- `IndicatorEngine` - 指标计算引擎

**支持指标**：
- 趋势指标：EMA、SMA、ADX、ER、R²、Hurst
- 震荡指标：RSI、STOCH、CCI、Williams %R
- 动量指标：MACD、TSI、ROC
- 波动率指标：ATR、Bollinger Bands
- 通道指标：Donchian Channel

**使用者**：Scanner 脚本、Monitor 脚本、Reasoner Agent

**使用示例**：
```python
from trend_scanner.indicators import IndicatorEngine

engine = IndicatorEngine(df)
engine.compute_all()
composite = engine.get_trend_strength_composite()
```

## 二、推理模块

### 2.1 推理引擎（reasoning.py）

**路径**：`scripts/trend_scanner/reasoning.py`

**职责**：LLM 推理

**主要类**：
- `LLMProvider` - LLM 提供者基类
- `WorkBuddyAgentProvider` - WorkBuddy Agent 提供者
- `CustomLLMProvider` - 自定义 LLM 提供者
- `ReasoningEngine` - 推理引擎

**使用者**：Reasoner Agent、Debater Agent

**使用示例**：
```python
from trend_scanner.reasoning import ReasoningEngine, WorkBuddyAgentProvider

llm = WorkBuddyAgentProvider()
engine = ReasoningEngine(llm_provider=llm)
result = engine.reason(context, experiences, aggregation)
```

### 2.2 简报生成器（brief.py）

**路径**：`scripts/trend_scanner/brief.py`

**职责**：生成交易决策简报

**主要类**：
- `BriefGenerator` - 简报生成器

**使用者**：Reasoner Agent

**使用示例**：
```python
from trend_scanner.brief import BriefGenerator

generator = BriefGenerator()
brief = generator.generate(context, reasoning_result, experiences)
```

### 2.3 辩论引擎（debate_engine.py）

**路径**：`scripts/trend_scanner/debate_engine.py`

**职责**：鹰派/鸽派辩论

**主要类**：
- `DebateReasoningEngine` - 辩论推理引擎

**使用者**：Debater Agent

**使用示例**：
```python
from trend_scanner.debate_engine import DebateReasoningEngine

engine = DebateReasoningEngine(hawk_llm=hawk, dove_llm=dove)
result = engine.reason(context, experiences, aggregation)
```

## 三、经验模块

### 3.1 经验记忆池（experience.py）

**路径**：`scripts/trend_scanner/experience.py`

**职责**：存储和检索交易经验

**主要类**：
- `ExperienceMemory` - 经验记忆池

**使用者**：Reasoner Agent、Evolver Agent

**使用示例**：
```python
from trend_scanner.experience import ExperienceMemory

memory = ExperienceMemory(db_path="evolution.db")
memory.add_experience(experience)
similar = memory.search_similar(context, top_k=5)
```

### 3.2 进化管理器（evolution_manager.py）

**路径**：`scripts/trend_scanner/evolution_manager.py`

**职责**：管理进化流程

**主要类**：
- `EvolutionManager` - 进化管理器

**使用者**：Evolver Agent

**使用示例**：
```python
from trend_scanner.evolution_manager import EvolutionManager

manager = EvolutionManager(db_path="evolution.db")
manager.record_analysis(context, brief)
manager.record_feedback(feedback, context, brief)
```

## 四、上下文模块

### 4.1 上下文组装器（context.py）

**路径**：`scripts/trend_scanner/context.py`

**职责**：组装市场上下文

**主要类**：
- `ContextAssembler` - 上下文组装器

**使用者**：Reasoner Agent

**使用示例**：
```python
from trend_scanner.context import ContextAssembler

assembler = ContextAssembler(symbol="DCE.jm2609")
context = assembler.assemble(df)
```

## 五、辅助模块

### 5.1 市场分析（market_analysis.py）

**路径**：`scripts/trend_scanner/market_analysis.py`

**职责**：市场结构分析

**使用者**：Scanner 脚本、Monitor 脚本

### 5.2 策略池（strategy.py）

**路径**：`scripts/trend_scanner/strategy.py`

**职责**：管理交易策略

**使用者**：Scanner 脚本、Reasoner Agent

### 5.3 数据持久化（data_store.py）

**路径**：`scripts/trend_scanner/data_store.py`

**职责**：数据持久化

**使用者**：所有 Agent

## 六、依赖关系图

```
                    ┌─────────────┐
                    │   models.py │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ indicators  │   │  reasoning  │   │  experience │
│    .py      │   │    .py      │   │    .py      │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       ▼                 ▼                 ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│data_source  │   │   brief.py  │   │ evolution   │
│    .py      │   │             │   │  _manager   │
└──────┬──────┘   └──────┬──────┘   │    .py      │
       │                 │         └──────┬──────┘
       ▼                 ▼                │
┌─────────────┐   ┌─────────────┐        │
│  context    │   │debate_engine│        │
│    .py      │   │    .py      │        │
└──────┬──────┘   └──────┬──────┘        │
       │                 │               │
       └─────────────────┼───────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Agent 脚本层       │
              │  (tools/*.py)       │
              └─────────────────────┘
```

## 七、版本兼容性

| 模块 | 最低 Python 版本 | 依赖库 |
|------|-----------------|--------|
| models.py | 3.8 | 无 |
| indicators.py | 3.8 | pandas, numpy |
| data_source.py | 3.8 | tqsdk (可选), pandas |
| reasoning.py | 3.8 | 无 |
| brief.py | 3.8 | 无 |
| debate_engine.py | 3.8 | 无 |
| experience.py | 3.8 | sqlite3 |
| evolution_manager.py | 3.8 | sqlite3 |
| context.py | 3.8 | pandas |
