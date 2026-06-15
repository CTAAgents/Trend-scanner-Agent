---
name: trend-scanner-agent
description: >
  推理重于规则的期货趋势跟踪 Agent v4.0。
  脚本+Agent 混合架构，动态因子生成，多角色协作，RL 接口自设计。
  数据源：TqSdk（首选）+ 通达信 MCP（备选）+ 本地数据库缓存。
---

# Trend Scanner Agent

推理重于规则的期货趋势跟踪决策辅助系统 v4.0。

## 核心理念

**以人为本，推理为魂，规则为果。**

所有看似"规则"的内容（止损、仓位、入场条件）均由推理层根据当前市场状态动态生成，而非事先写死。系统不自动下单，只输出决策简报供人参考。

## 一、系统架构

### 1.1 整体架构（六层管线）

```
定时触发 (08:40 / 15:20 / 20:40)
    │
    ▼
┌─────────────────────────────────────────────────┐
│  ① 数据采集层（纯 Python）                       │
│  - TqSdk 拉取所有非僵尸品种 120 日 K 线          │
│  - 写入本地 DuckDB 数据库（data/market.duckdb）   │
│  - 增量更新：只拉取新数据，避免重复下载            │
│  - 降级策略：TqSdk → 通达信 MCP → 本地数据库      │
└────────────────────┬────────────────────────────┘
                     │ 数据就绪
                     ▼
┌─────────────────────────────────────────────────┐
│  ② Scanner 脚本（纯 Python，无 LLM）             │
│  - 从本地数据库读取 K 线数据                      │
│  - 计算 ER / TSI / R² / Hurst / RSI / ADX       │
│  - 复合趋势强度打分                               │
│  - 筛选条件过滤（OR/AND 可配置）                  │
│  - 可选：加载动态因子（--use-dynamic-factors）     │
│  输出 → data/latest_scan.json                    │
└────────────────────┬────────────────────────────┘
                     │ 有信号
                     ▼
┌─────────────────────────────────────────────────┐
│  ③ Reasoner Agent（LLM 推理）                    │
│  - 接收信号 + 市场上下文 + 历史经验               │
│  - 生成交易决策简报：                             │
│    市场评估 → 操作方案 → 约束建议 → 置信度        │
│  - 置信度 < 0.7 时触发 Debater                   │
│  输出 → data/latest_reasoning.json               │
└────────────────────┬────────────────────────────┘
                     │ 置信度不足
                     ▼
┌─────────────────────────────────────────────────┐
│  ④ Debater Agent（多角色协作，FinCon 思想）       │
│  四个角色独立分析后汇总辩论：                      │
│  - 分析师：技术面（趋势/动量/形态）               │
│  - 风控官：风险收益比/止损/仓位                   │
│  - 基本面研究员：供需/政策/产业链                  │
│  - 协调者：汇总分歧，修正方案                     │
│  角色间通过「概念性语言反馈」互相教学              │
│  输出 → data/latest_debate.json                  │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  ⑤ Monitor 脚本（纯 Python，每 30 分钟）          │
│  - 读取持仓数据 config/positions.json             │
│  - 从本地数据库获取最新指标                       │
│  - 监控趋势强度下降 / ER 骤降 / RSI 超买         │
│  - 分级预警：HIGH / MEDIUM / LOW                 │
│  输出 → data/latest_monitor.json                 │
└────────────────────┬────────────────────────────┘
                     │ 交易结束后
                     ▼
┌─────────────────────────────────────────────────┐
│  ⑥ Evolver Agent（LLM 引导的 RL，GIFT 思想）     │
│  - 轨迹分析：从交易历史提取成功/失败模式          │
│  - 失败学习：生成「避免规则」                     │
│  - RL 接口设计：LLM 设计状态空间和奖励函数        │
│  - 诊断修正：基于回滚诊断优化策略参数              │
│  - 信念更新：将学习成果写入投资信念库              │
└─────────────────────────────────────────────────┘
```

### 1.2 架构总览

```
Orchestrator Agent（主协调）
  │
  ├── 数据采集层
  │     ├── TqSdk 数据源（首选）
  │     ├── 通达信 MCP（备选）
  │     └── 本地 DuckDB（缓存 + 兜底）
  │
  ├── Scanner 脚本（纯 Python）
  │     ├── 传统技术指标计算
  │     └── 动态因子生成器（LLM 引导）  ← FactorEngine
  │
  ├── Reasoner Agent（LLM 推理）
  │     ├── 市场状态分析
  │     └── 知识注入（研报、经验）  ← FactorEngine
  │
  ├── Debater Agent（多角色协作）  ← FinCon
  │     ├── 分析师角色（agents/analyst_role.md）
  │     ├── 基本面研究员角色
  │     ├── 风控官角色（agents/risk_officer_role.md）
  │     └── 概念性语言反馈
  │
  ├── Monitor 脚本（纯 Python）
  │     └── 持仓风险监控
  │
  ├── 记忆系统
  │     ├── MemoryBridge（集成桥接器）
  │     ├── SQLite（经验/规则/日志）
  │     └── DuckDB（K线/指标/因子库）
  │
  └── Evolver Agent（LLM 引导的 RL）  ← GIFT
        ├── 轨迹感知优化器
        ├── 状态空间设计
        ├── 奖励函数设计
        └── 诊断引导修正
```

### 1.3 设计原则

| 原则 | 含义 | 体现 |
|------|------|------|
| 推理重于规则 | 所有"规则"由推理层动态生成 | 不存在独立的规则层 |
| 计算用脚本，推理用 Agent | 确定性计算不调 LLM | Scanner/Monitor 是纯 Python |
| 数据本地化 | TqSdk 数据写入本地 DuckDB | 避免重复 API 调用 |
| 因子即代码 | 因子是 LLM 生成的可执行代码 | FactorEngine 思想 |
| 概念性语言反馈 | Agent 间用自然语言互相教学 | FinCon 思想 |
| RL 接口自设计 | LLM 设计状态空间和奖励函数 | GIFT 思想 |

---

## 二、数据采集层

### 2.1 工作机制

```
TqSdk API
    │
    ▼
┌─────────────────────────────────┐
│  DataSourceFactory.create()     │
│  - 自动选择最优数据源            │
│  - 优先级：TqSdk > 通达信 > CSV  │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  TqSdkSource.get_kline()        │
│  - 拉取所有非僵尸品种 120 日 K 线│
│  - 返回 DataFrame               │
│    (date,open,high,low,close,   │
│     volume,open_interest)       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  DuckDBStore.insert_klines()    │
│  - 增量写入 data/market.duckdb  │
│  - 按 (symbol, timestamp) 去重  │
│  - 创建索引加速查询              │
└─────────────────────────────────┘
```

### 2.2 数据源适配器

**文件**：`scripts/trend_scanner/data_source.py`

统一接口 `DataSource`，三个实现：

| 数据源 | 类 | 优先级 | 特点 |
|--------|-----|--------|------|
| TqSdk | `TqSdkSource` | 首选 | 期货实时行情，主力合约自动识别 |
| 通达信 MCP | `TdxSource` | 备选 | A股/港股/美股/期货，通过 MCP 工具调用 |
| 本地 CSV | `CsvSource` | 兜底 | 用户导入的历史数据 |

**降级逻辑**：`DataSourceFactory.create()` 按优先级尝试，不可用时自动降级。

### 2.3 本地数据库（DuckDB）

**文件**：`scripts/trend_scanner/memory/duckdb_store.py`

```
data/market.duckdb
  │
  ├── klines 表（K线时序数据）
  │     symbol | timestamp | timeframe | OHLCV | source
  │
  ├── indicators 表（技术指标历史）
  │     symbol | timestamp | indicator_name | value
  │
  └── factor_library 表（因子库）
        factor_id | name | type | expression | IC | IR
```

**特点**：列式存储，适合时序数据聚合查询。

---

## 三、Scanner 模块

### 3.1 工作机制

```
本地 DuckDB (klines)
    │
    ▼
┌─────────────────────────────────┐
│  IndicatorEngine.compute_all()  │
│  - 计算 7 维趋势强度指标         │
│  - TSI / ER / R² / Hurst       │
│  - RSI / ADX / EMA斜率 / ATR   │
│  - 复合趋势强度打分              │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  信号筛选（filter_mode: or/and）│
│  - ER ≥ 0.6                    │
│  - TSI ≥ 20 (多头) / ≤ -20 (空)│
│  - 趋势强度 ≥ 0.5              │
│  - R² ≥ 0.4                    │
│  - OR: 任一满足即触发           │
│  - AND: 全部满足才触发          │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  动态因子（可选）               │
│  - 从 data/factor_knowledge.json│
│    加载因子代码                 │
│  - exec() 执行，获取因子值      │
│  - 附加到信号输出               │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  MemoryBridge.store_scan_result │
│  - 存储扫描结果到记忆系统       │
│  - 存储技术指标到 DuckDB        │
└─────────────────────────────────┘
```

### 3.2 技术指标（7 维）

| 指标 | 权重 | 含义 | 计算方式 |
|------|------|------|----------|
| TSI | 25% | 趋势强度指数 | 双重平滑动量 |
| ER | 25% | 效率比 | 方向移动 / 总移动 |
| EMA 斜率 | 15% | 均线斜率强度 | EMA20 变化率 |
| ATR 比率 | 10% | 波动率比率 | ATR / 价格 |
| R² | 10% | 拟合度 | 线性回归 R² |
| Hurst | 8% | 赫斯特指数 | 趋势持续性 |
| ADX ROC | 7% | ADX 变化率 | 趋势加速 |

### 3.3 信号筛选

**配置**：`config/config.json` → `scanner.signal_filter`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `filter_mode` | `"or"` | or=任一触发，and=全部触发 |
| `er_min` | 0.6 | 效率比阈值 |
| `tsi_min` | 20 | 多头 TSI 阈值 |
| `tsi_max` | -20 | 空头 TSI 阈值 |
| `trend_strength_min` | 0.5 | 复合趋势强度阈值 |
| `r2_min` | 0.4 | R² 阈值 |

**信号强度**：按满足条件数自动判定 — 4/4=STRONG，2-3=MEDIUM，1=WEAK。

---

## 四、Reasoner Agent

### 4.1 工作机制

```
Scanner 信号 (latest_scan.json)
    │
    ▼
┌─────────────────────────────────┐
│  MemoryBridge.retrieve_experiences│
│  - 向量检索（粗筛 top_k*3）     │
│  - 结构化过滤（品种/方向）      │
│  - 时间衰减（半衰期 90 天）     │
│  - 综合排序 → 返回 top_k       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  TradingAssistant.analyze()     │
│  - 接收 K 线数据 + 相似经验     │
│  - LLM 推理生成决策简报         │
│  - 输出：                       │
│    市场评估（趋势方向/阶段）    │
│    操作方案（入场/止损/目标）   │
│    约束建议（仓位/风控）        │
│    置信度（0-1）                │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  MemoryBridge.store_reasoning   │
│  - 存储推理结果到记忆系统       │
└──────────────┬──────────────────┘
               │
               ▼
        置信度 < 0.7 ?
           │         │
           是        否
           │         │
           ▼         ▼
      Debater    输出简报
```

### 4.2 决策简报输出格式

```json
{
  "symbol": "DCE.jm2609",
  "direction": "LONG",
  "confidence": 0.75,
  "market_assessment": {
    "trend_phase": "DEVELOPING",
    "trend_strength": "中强",
    "key_observations": ["焦煤安全检查限产预期", "焦化利润支撑"]
  },
  "routes": [
    {
      "name": "方案A：顺势做多",
      "entry": "当前价附近入场",
      "stop_loss": "前低下方 2ATR",
      "reasoning": "趋势发展阶段，动量充足"
    }
  ],
  "constraints": [
    {"type": "position_size", "value": "标准仓位的 60%"}
  ],
  "uncertainty": {
    "level": "MEDIUM",
    "factors": ["政策风险", "需求端不确定性"]
  }
}
```

---

## 五、Debater Agent

### 5.1 工作机制（多角色协作）

```
Reasoner 决策简报
    │
    ▼
┌─────────────────────────────────────────┐
│  Step 1: 分析师角色独立分析              │
│  - 技术面：趋势阶段/动量/成交量/形态     │
│  - 输出：技术面评估 + 关键信号           │
└──────────────────┬──────────────────────┘
                   │
┌─────────────────────────────────────────┐
│  Step 2: 风控官角色独立分析              │
│  - 风险收益比/止损评估/仓位建议          │
│  - 输出：风险评估 + 风险约束             │
└──────────────────┬──────────────────────┘
                   │
┌─────────────────────────────────────────┐
│  Step 3: 基本面研究员角色独立分析（可选）│
│  - 供需/政策/产业链/季节性               │
│  - 输出：基本面评估 + 驱动因素           │
└──────────────────┬──────────────────────┘
                   │
┌─────────────────────────────────────────┐
│  Step 4: 概念性语言反馈                  │
│  - 分析师 → 风控官：技术面风险点         │
│  - 风控官 → 分析师：风险约束要求         │
│  - 各角色基于反馈调整分析                │
└──────────────────┬──────────────────────┘
                   │
┌─────────────────────────────────────────┐
│  Step 5: 协调者综合决策                  │
│  - 识别共识区域                          │
│  - 识别分歧点和分歧度                    │
│  - 权衡技术面/风险/基本面                │
│  - 修正方案 + 决策理由                   │
└──────────────────┬──────────────────────┘
                   │
                   ▼
          data/latest_debate.json
```

### 5.2 角色定义

| 角色 | 文件 | 职责 | 关注点 |
|------|------|------|--------|
| 分析师 | `agents/analyst_role.md` | 技术面分析 | 趋势/动量/形态/成交量 |
| 风控官 | `agents/risk_officer_role.md` | 风险评估 | 风险收益比/止损/仓位 |
| 基本面研究员 | 内置于 `debater.md` | 供需分析 | 政策/产业链/库存 |
| 协调者 | 内置于 `debater.md` | 综合决策 | 分歧权衡/方案修正 |

### 5.3 概念性语言反馈（FinCon）

**核心思想**：Agent 间用自然语言反馈互相教学，而非数值奖励。

```
分析师："RSI 接近超买区域（68），短期回调风险增大"
    ↓ 概念性反馈
风控官："建议将止损收紧到 EMA20 下方，仓位降至 60%"
    ↓ 概念性反馈
协调者："综合判断：趋势方向不变，但入场时机需要优化"
```

**vs 传统数值反馈**：
- 传统：`reward = 0.7`（黑盒，不可解释）
- FinCon："在趋势发展阶段入场是正确的，但仓位控制过于激进"（可解释，可行动）

---

## 六、Monitor 模块

### 6.1 工作机制

```
config/positions.json (持仓数据)
    │
    ▼
┌─────────────────────────────────┐
│  从本地 DuckDB 获取最新指标     │
│  - 趋势强度 / ER / TSI / RSI   │
│  - 与历史值对比                 │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  风险检测                       │
│  - 趋势强度下降 ≥ 0.35 → HIGH  │
│  - ER 骤降至 < 0.3 → HIGH      │
│  - RSI > 70 / < 30 → MEDIUM    │
│  - 盈利回撤 > 25% → MEDIUM     │
│  - 波动率扩大 → LOW            │
└──────────────┬──────────────────┘
               │
               ▼
          data/latest_monitor.json
```

### 6.2 预警分级

| 级别 | 触发条件 | 动作 |
|------|----------|------|
| HIGH | 趋势反转 / ER 骤降 / 趋势强度不足 | 立即通知 |
| MEDIUM | 盈利回撤 / RSI 超买超卖 / 均线交叉 | 关注观察 |
| LOW | 波动率扩大 / ADX 趋势减弱 | 记录备查 |

---

## 七、Evolver Agent

### 7.1 工作机制（GIFT 思想）

```
交易结果
    │
    ▼
┌─────────────────────────────────┐
│  轨迹分析（TrajectoryAnalyzer） │
│  - 分类成功/失败案例            │
│  - 提取共同特征                 │
│  - 识别模式                     │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  失败学习（FailureLearner）     │
│  - 分析失败原因                 │
│  - 生成「避免规则」             │
│  - 例如："当市场震荡时减仓"    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  RL 接口设计（RLInterfaceDesigner）│
│  - LLM 设计状态空间             │
│  - LLM 设计奖励函数             │
│  - 诊断修正：基于回滚优化       │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  信念更新                       │
│  - 将学习成果写入投资信念库     │
│  - 概念性语言形式存储           │
│  - 跨 Agent 传播               │
└──────────────┬──────────────────┘
               │
               ▼
    MemoryBridge.store_evolution_result
```

### 7.2 进化触发条件

| 条件 | 阈值 | 说明 |
|------|------|------|
| 连续亏损 | ≥ 3 次 | 策略可能失效 |
| 累计亏损 | ≥ 10% | 风险失控 |
| 定期进化 | 每 20 笔交易 | 主动优化 |
| 新模式 | 检测到新模式 | 环境变化 |

### 7.3 RL 接口设计（GIFT）

**核心思想**：不直接让 LLM 做交易决策，而是设计状态空间和奖励函数。

```
LLM 设计 → 状态空间（趋势阶段/动量/波动率/...）
LLM 设计 → 奖励函数（收益/风险/交易成本/...）
    │
    ▼
选定后固定 → 测试时不再查询 LLM
    │
    ▼
诊断修正 → 基于 PPO 回滚诊断优化
```

---

## 八、记忆系统

### 8.1 三层记忆架构

```
┌─────────────────────────────────────────────────┐
│                 记忆系统架构                       │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │  ① 短期记忆（Session）                       │ │
│  │  - 存储：内存（Python dict）                  │ │
│  │  - 生命周期：会话级                           │ │
│  │  - 用途：当前会话临时上下文                   │ │
│  └─────────────────────────────────────────────┘ │
│                      │                            │
│                      ▼                            │
│  ┌─────────────────────────────────────────────┐ │
│  │  ② 工作记忆（Working）                       │ │
│  │  - 存储：SQLite（data/memory.db）             │ │
│  │  - 生命周期：日级                             │ │
│  │  - 用途：当日交易经验、临时规则               │ │
│  └─────────────────────────────────────────────┘ │
│                      │                            │
│                      ▼                            │
│  ┌─────────────────────────────────────────────┐ │
│  │  ③ 长期记忆（Persistent）                    │ │
│  │  - 存储：SQLite + DuckDB                      │ │
│  │  - 生命周期：永久                             │ │
│  │  - 用途：历史经验、策略规则、交易日志         │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 8.2 双存储引擎

| 引擎 | 文件 | 用途 | 表结构 |
|------|------|------|--------|
| **SQLite** | `data/memory.db` | 事务型 | experiences, strategy_rules, trade_journal, evolution_history |
| **DuckDB** | `data/market.duckdb` | 分析型 | klines, indicators, factor_library |

### 8.3 多路召回检索

```
查询上下文（品种/方向/特征向量）
    │
    ├── 向量相似度（cosine + euclidean）→ 粗筛 top_k*3
    ├── 结构化条件（品种/方向/阶段）→ 精筛
    ├── 时间相似度（指数衰减，半衰期 90 天）→ 加权
    └── 品种相似度 → 加权
    │
    ▼
综合排序 → 返回 top_k
```

### 8.4 MemoryBridge（集成桥接器）

**文件**：`scripts/trend_scanner/memory_bridge.py`

连接 Scanner/Reasoner/Evolver 与记忆系统的统一接口：

| 调用方 | 方法 | 功能 |
|--------|------|------|
| Scanner | `store_scan_result()` | 存储扫描结果 |
| Scanner | `store_indicators()` | 存储技术指标 |
| Reasoner | `retrieve_similar_experiences()` | 检索相似经验 |
| Reasoner | `store_reasoning_result()` | 存储推理结果 |
| Evolver | `get_trade_history()` | 获取交易历史 |
| Evolver | `store_evolution_result()` | 存储进化结果 |

### 8.5 自优化闭环

```
交易执行 → 结果记录 → 轨迹分析 → 故障归因 → 模式检测
    ↑                                              │
    └──────────── 规则优化 ← LLM 反思 ←────────────┘
```

**进化触发**：连续亏损/累计亏损/定期进化/新模式检测

---

## 九、动态因子生成（FactorEngine）

### 9.1 工作机制

```
市场上下文 / 研报内容
    │
    ▼
┌─────────────────────────────────┐
│  FactorGenerator.generate()     │
│  - 构建 prompt（市场上下文）     │
│  - 调用 LLM 生成因子代码        │
│  - 代码格式：                   │
│    def factor(df) -> pd.Series  │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  FactorValidator.validate()     │
│  - 语法检查                     │
│  - 结构检查（必须有 return）     │
│  - 安全检查（禁止危险操作）     │
│  - 性能指标（IC/ICIR/稳定性）   │
└──────────────┬──────────────────┘
               │
               ▼
        验证通过？
           │         │
           是        否
           │         │
           ▼         ▼
    存入知识库    LLM 修正 → 重新验证
```

### 9.2 因子知识库

**文件**：`data/factor_knowledge.json`

```json
{
  "factors": [
    {
      "id": "factor_001",
      "name": "动量突破因子",
      "code": "def factor(df): ...",
      "description": "结合价格动量和成交量放大",
      "performance": {"ic": 0.05, "icir": 1.2},
      "regime_effectiveness": {"trending": 0.9, "ranging": 0.3}
    }
  ]
}
```

### 9.3 LLM 客户端

**文件**：`scripts/trend_scanner/llm_factor_client.py`

| 提供者 | 类 | 模型 | 用途 |
|--------|-----|------|------|
| WorkBuddy | `WorkBuddyClient` | Mimo-V2.5-Pro | 生产环境（默认） |
| OpenAI | `OpenAIClient` | GPT-4 | 备选 |
| Mock | `MockLLMClient` | 无 | 测试/降级 |

**降级策略**：API 不可用时自动降级到 MockLLMClient。

---

## 十、数据流与调度

### 10.1 数据流总览

| 阶段 | 输入 | 处理 | 输出 |
|------|------|------|------|
| 数据采集 | TqSdk API | 增量拉取 + 写入 DuckDB | `data/market.duckdb` |
| Scanner | 本地 DuckDB | 指标计算 + 因子筛选 | `data/latest_scan.json` |
| Reasoner | 信号 + 经验库 | LLM 推理 | `data/latest_reasoning.json` |
| Debater | 决策简报 | 四角色辩论 | `data/latest_debate.json` |
| Monitor | 持仓 + 本地指标 | 风险监控 | `data/latest_monitor.json` |
| Evolver | 交易结果 | 轨迹分析 + RL 优化 | 进化报告 |

### 10.2 调度

| 时间 | 任务 | 说明 |
|------|------|------|
| 08:40 | 盘前准备 | 数据同步 + 全品种扫描 |
| 15:20 | 日盘收盘 | 数据同步 + 全品种扫描 + 输出总结 |
| 20:40 | 夜盘开盘 | 数据同步 + 全品种扫描 |
| 每 30 分钟 | 持仓监控 | Monitor 脚本 |
| 每 5 分钟 | 心跳检测 | 交易时段内 |

### 10.3 Token 预算

每日预算：850,000 token

| 使用率 | 动作 |
|--------|------|
| < 80% | 正常运行 |
| 80-90% | 停止 Debater Agent |
| 90-100% | 只保留 Scanner 脚本 |
| >= 100% | 停止所有 Agent |

---

## 附录

### A. 目录结构

```
Trend-scanner-Agent/
├── SKILL.md                    # 项目文档（本文件）
├── config/
│   ├── config.json             # 统一配置
│   └── positions.json          # 持仓数据
├── scripts/trend_scanner/      # 核心计算包
│   ├── data_source.py          # 数据源适配器
│   ├── memory_bridge.py        # 记忆系统集成桥接器
│   ├── factor_generator.py     # 动态因子生成
│   ├── llm_factor_client.py    # LLM 客户端
│   ├── factor_validator.py     # 因子验证器
│   ├── trajectory_analyzer.py  # 轨迹感知优化器
│   ├── report_parser.py        # 研报知识注入
│   ├── conceptual_feedback.py  # 概念性语言反馈
│   ├── belief_propagation.py   # 信念传播
│   ├── rl_interface_designer.py # RL 接口设计
│   └── memory/                 # 记忆系统
│       ├── manager.py          # 统一记忆管理器
│       ├── sqlite_store.py     # SQLite 存储
│       ├── duckdb_store.py     # DuckDB 存储
│       ├── llm_factory.py      # LLM 提供者工厂
│       ├── retriever.py        # 多路召回检索器
│       └── evolution.py        # 自优化闭环
├── tools/
│   ├── scan_opportunities.py   # Scanner
│   ├── monitor_positions.py    # Monitor
│   ├── heartbeat.py            # 心跳监控
│   ├── orchestrator.py         # Orchestrator
│   ├── run_reasoner.py         # Reasoner
│   ├── run_debater.py          # Debater
│   ├── run_evolver.py          # Evolver
│   ├── deploy_v4.sh            # 部署脚本
│   └── data_formats.py         # 数据格式定义
├── agents/
│   ├── orchestrator.md         # Orchestrator Agent
│   ├── reasoner.md             # Reasoner Agent
│   ├── debater.md              # Debater Agent v2.0
│   ├── analyst_role.md         # 分析师角色
│   ├── risk_officer_role.md    # 风控官角色
│   └── evolver.md              # Evolver Agent v2.0
├── tests/                      # 154 个测试
├── data/
│   ├── market.duckdb           # K 线数据库
│   ├── memory.db               # 记忆系统数据库
│   └── factor_knowledge.json   # 因子知识库
└── docs/
    ├── paper_analysis_improvements.md
    ├── implementation_plan.md
    └── CODE_STYLE.md
```

### B. 快速开始

```bash
git clone https://github.com/CTAAgents/Trend-scanner-Agent.git
cd Trend-scanner-Agent
pip install -r requirements.txt

# 配置环境变量
export TQ_USER=your_username
export TQ_PASSWORD=your_password
export WORKBUDDY_API_KEY=your_api_key

# 运行扫描
python tools/scan_opportunities.py --output text --save

# 完整流程
python tools/orchestrator.py full
```

### C. 测试覆盖

| 测试文件 | 数量 | 状态 |
|---------|------|------|
| test_factor_generator.py | 22 | ✅ |
| test_trajectory_analyzer.py | 11 | ✅ |
| test_report_parser.py | 16 | ✅ |
| test_multi_debater.py | 22 | ✅ |
| test_rl_interface.py | 15 | ✅ |
| test_e2e_pipeline.py | 14 | ✅ |
| test_full_pipeline.py | 22 | ✅ |
| test_performance.py | 20 | ✅ |
| test_memory_system.py | 12 | ✅ |
| **总计** | **154** | **全部通过** |

### D. 论文来源

| 论文 | 核心思想 | 对应模块 |
|-----|---------|---------|
| FactorEngine (2603.16365) | 因子即代码、知识注入 | Scanner / Reasoner |
| FinCon (2407.06567) | 概念性语言反馈、多角色协作 | Debater |
| GIFT (2606.08450) | LLM 引导的 RL 接口设计 | Evolver |

### E. 许可证

MIT License
