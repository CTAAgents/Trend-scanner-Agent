# QuantNova 系统架构总览

> 版本：v1.0.0 | 创建日期：2026-06-17 | 更新：2026-06-18
> 状态：已完成基本面分析模块集成

## 一、系统概述

QuantNova 是一个推理重于规则的期货趋势跟踪决策辅助系统。系统不自动下单，只输出决策简报供人参考。

**核心理念**：以人为本，推理为魂，规则为果。

**核心能力**：统一数据路由、知识锚点体系、分级输出、套利分析、Reasoner Agent深度分析、闭环因子进化引擎、**基本面分析模块**。

**独立策略模块**：Carry 策略（期限结构套利），与趋势跟踪策略并行运行。

**最新更新**：集成基本面分析模块，支持新闻抓取、供需数据、地缘政治追踪，能够解释市场现象的根本原因。

---

## 二、分层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 10 - 主协调层 (Orchestrator)                                   │
│   navigator.py (TradingAssistant) - 系统主入口                       │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 9 - 分析工具层 (Analytics)                                     │
│   analytics.py, scoring_analytics.py, weight_optimizer.py,          │
│   threshold_optimizer.py, backtest.py, overfitting_detector.py,     │
│   strategy_health.py, position_health.py, position_sizer.py,        │
│   stop_loss.py, control_variable.py                                 │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 8 - 高级分析层 (Advanced Analysis)                             │
│   visibility_graph.py, visibility_graph_operator.py,                │
│   volatility_anchor.py, walk_forward_validator.py,                  │
│   regime_segmenter.py, rl_interface_designer.py, report_parser.py   │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 7 - 因子进化层 (Factor Evolution)                              │
│   factor_generator.py, factor_evaluator.py, factor_executor.py,     │
│   factor_gate.py, factor_evolution_engine.py,                       │
│   factor_param_optimizer.py, seed_factor_pool.py,                   │
│   multi_factor_model.py, factor_experience_db.py                    │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 6 - 进化层 (Evolution)                                         │
│   evolution_manager.py, evolution.py, trajectory_analysis.py,       │
│   trade_journal.py, skill_reflection.py, meta_skill_engine.py,      │
│   overfitting_audit.py, silent_bypass_detector.py, meta_learner.py  │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 5 - 策略层 (Strategy)                                          │
│   scanner.py, strategy.py, risk_management.py, execution.py,        │
│   portfolio.py, narrative_generator.py                              │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 4 - 推理层 (Reasoning)                                         │
│   reasoning.py, debate_engine.py, brief.py,                         │
│   belief_propagation.py, conceptual_feedback.py                     │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 3 - 记忆层 (Memory)                                            │
│   memory/ (UnifiedMemoryManager), experience.py, memory_bridge.py,  │
│   memory_vectorizer.py, vector_enhancement.py, selective_update.py, │
│   regime_gate.py, factor_experience_db.py                           │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 2 - 存储层 (Storage)                                           │
│   data_store.py, storage/sqlite_store.py, storage/duckdb_store.py,  │
│   storage/data_sync.py, tqsdk_bridge.py, tqsdk_worker.py           │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 1 - 感知层 (Perception)                                        │
│   indicators.py, context.py, data_source.py, market_analysis.py,    │
│   macro_state.py, unified_data_router.py                            │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 0 - 数据模型层 (Foundation)                                    │
│   models.py, __version__.py                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心工作流

### 3.1 主流程

```
用户请求 → TradingAssistant (navigator.py)
    ↓
ContextAssembler (context.py) → 组装 MarketContext
    ↓
├── 技术面分析 → IndicatorEngine (indicators.py)
└── 基本面分析 → NewsCrawler + SupplyDemandProvider + GeopoliticalTracker
    ↓
ExperienceMemory (experience.py) → 检索相似经验
    ↓
ReasoningEngine (reasoning.py) → LLM 推理（包含基本面信息）
    ↓
DebateReasoningEngine (debate_engine.py) → 鹰鸽辩论纠偏
    ↓
BriefGenerator (brief.py) → 生成 TradingBrief
    ↓
用户查看决策简报
```

### 3.2 基本面分析流程（新增）

```
品种代码 → ContextAssembler._assemble_fundamental()
    ↓
├── NewsCrawler.crawl() → 抓取新闻（5个数据源）
│   ├── 财新网
│   ├── 新浪财经
│   ├── 央广网
│   ├── 东方财富
│   └── 雪球
    ↓
├── SupplyDemandProvider.get_supply_demand() → 获取供需数据
│   ├── 库存数据
│   ├── 产量数据
│   └── 消费数据
    ↓
├── GeopoliticalTracker.track() → 追踪地缘政治风险
│   ├── 战争/冲突
│   ├── 制裁
│   ├── 关税
│   └── 和平协议
    ↓
└── 组装 FundamentalContext
    ├── news_events: 新闻事件列表
    ├── supply_demand: 供需数据
    ├── geopolitical_risks: 地缘政治风险
    ├── fundamental_score: 基本面综合评分
    └── key_drivers: 关键驱动因素
```

### 3.2 因子进化流程

```
FactorEvolutionEngine.evolve()
    ↓
[1] 生成候选因子 (FactorGenerator + SeedFactorPool)
    ↓
[2] 执行因子 (FactorExecutor)
    ↓
[3] 评估因子 (FactorEvaluator - IC/ICIR/t-stat)
    ↓
[3.5] Walk-Forward 验证 (WalkForwardValidator) - 可选
    ↓
[4] 门控决策 (FactorGate - 晋升/观察/淘汰)
    ↓
[5] 记忆更新 (FactorExperienceDB)
    ↓
[6] 检查终止条件 → 循环或结束
```

### 3.3 自优化闭环

```
交易执行 → 结果记录 (trade_journal.py)
    ↓
轨迹分析 (trajectory_analysis.py)
    ↓
故障归因 (TradeFaultAttributor)
    ↓
模式检测 (PatternDetector)
    ↓
LLM 反思 (LLMProvider)
    ↓
规则优化 (strategy_rules)
    ↓
过拟合审计 (OverfittingAuditor)
    ↓
规则晋升 (pattern → rules)
    ↓
经验存储 (experiences)
    ↓
回到交易执行 (闭环)
```

---

## 四、模块清单（按层级）

### 4.0 数据模型层 (1 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `models.py` | MarketContext, Experience, TradingBrief, NewsEvent, SupplyDemandData, GeopoliticalRisk, FundamentalContext | 所有数据结构定义（包含基本面数据模型） |

### 4.1 感知层 (5 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `indicators.py` | IndicatorEngine | 35+ 技术指标计算 |
| `context.py` | ContextAssembler | 组装结构化 MarketContext |
| `data_source.py` | DataSourceFactory | 数据源适配器 (TqSdk/通达信/CSV) |
| `market_analysis.py` | MultiIndicatorConsensus | 市场分析与趋势检测 |
| `macro_state.py` | MacroStateDetector | 宏观状态检测 |

### 4.2 存储层 (6 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `data_store.py` | DataStore | SQLite+DuckDB 双引擎存储 |
| `storage/sqlite_store.py` | SQLiteStore | 品种元数据/配置/交易日志 |
| `storage/duckdb_store.py` | DuckDBStore | K线/行情/技术指标 |
| `storage/data_sync.py` | DataSyncManager | 数据同步管理 |
| `tqsdk_bridge.py` | TqSdkBridge | TqSdk 数据桥接 |
| `tqsdk_worker.py` | TqSdkWorker | TqSdk 工作进程 |

### 4.3 记忆层 (8 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `memory/manager.py` | UnifiedMemoryManager | 记忆系统唯一入口 |
| `experience.py` | ExperienceMemory | 经验记忆池 |
| `memory_bridge.py` | MemoryBridge | Scanner/Reasoner/Evolver 集成 |
| `memory_vectorizer.py` | MemoryVectorizer | 文本语义向量化 |
| `vector_enhancement.py` | VectorEnhancer | 向量增强与多粒度检索 |
| `selective_update.py` | SelectiveUpdater | 选择性更新与知识蒸馏 |
| `regime_gate.py` | RegimeGate | 机制门权重调整 |
| `factor_experience_db.py` | FactorExperienceDB | 因子演化轨迹经验 |

### 4.4 推理层 (5 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `reasoning.py` | ReasoningEngine | LLM 推理引擎 |
| `debate_engine.py` | DebateReasoningEngine | 鹰鸽辩论纠偏 |
| `brief.py` | BriefGenerator | 交易决策简报生成 |
| `belief_propagation.py` | BeliefPropagationManager | 信念传播 (FinCon) |
| `conceptual_feedback.py` | ConceptualFeedbackGenerator | 概念性反馈 |

### 4.5 策略层 (6 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `scanner.py` | TrendScanner | 趋势扫描器 |
| `strategy.py` | StrategyPool | 策略池管理 |
| `risk_management.py` | RiskManager | 风险管理 |
| `execution.py` | ExecutionEngine | 执行引擎 |
| `portfolio.py` | PortfolioManager | 组合管理 |
| `narrative_generator.py` | NarrativeGenerator | 叙事生成器 |

### 4.6 基本面分析层 (4 个模块) - 新增

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `fundamental/news_crawler.py` | NewsCrawler | 新闻抓取（5个数据源） |
| `fundamental/supply_demand.py` | SupplyDemandProvider | 供需数据接口 |
| `fundamental/geopolitical.py` | GeopoliticalTracker | 地缘政治事件追踪 |
| `fundamental/__init__.py` | - | 基本面分析模块初始化 |

### 4.6 进化层 (9 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `evolution_manager.py` | EvolutionManager | 进化管理器 |
| `evolution.py` | EnhancedEvolutionEngine | 自进化引擎 |
| `trajectory_analysis.py` | TradeTrajectoryAnalyzer | 交易轨迹分析 |
| `trade_journal.py` | TradeJournal | 交易日志 |
| `skill_reflection.py` | SkillAwareReflector | 技能反思 |
| `meta_skill_engine.py` | MetaSkillEngine | 元技能引擎 |
| `overfitting_audit.py` | OverfittingAuditor | 过拟合审计 |
| `silent_bypass_detector.py` | SilentBypassDetector | 静默旁路检测 |
| `meta_learner.py` | MetaLearningEngine | 元学习引擎 |

### 4.7 因子进化层 (10 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `factor_generator.py` | FactorGenerator | LLM 因子生成 |
| `factor_evaluator.py` | FactorEvaluator | 因子评估 |
| `factor_executor.py` | FactorExecutor | 因子执行 |
| `factor_gate.py` | FactorGate | 因子准入门控 |
| `factor_evolution_engine.py` | FactorEvolutionEngine | 因子进化引擎 |
| `factor_param_optimizer.py` | FactorParamOptimizer | 因子参数优化 |
| `seed_factor_pool.py` | SeedFactorPool | 种子因子池 |
| `multi_factor_model.py` | MultiFactorModel | 多因子模型 |
| `factor_experience_db.py` | FactorExperienceDB | 因子经验数据库 |
| `factor_validator.py` | FactorValidator | 因子代码验证 |

### 4.8 高级分析层 (7 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `visibility_graph.py` | VGRSI, MultiTimeframeVGRSI | 可见图算法 |
| `visibility_graph_operator.py` | VisibilityGraphOperator | 可见图算子 |
| `volatility_anchor.py` | VolatilityAnchor | 波动率锚定 |
| `walk_forward_validator.py` | WalkForwardValidator | 滚动前推验证 |
| `regime_segmenter.py` | RegimeSegmenter | 分层机制检测 |
| `rl_interface_designer.py` | RLInterfaceDesigner | RL 接口设计 |
| `report_parser.py` | ReportParser | 研报解析 |

### 4.9 分析工具层 (11 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `analytics.py` | KPICalculator | KPI 计算 |
| `scoring_analytics.py` | ScoringAnalytics | 打分分析 |
| `weight_optimizer.py` | WeightOptimizer | 权重优化 |
| `threshold_optimizer.py` | ThresholdOptimizer | 阈值优化 |
| `backtest.py` | WalkForwardBacktester | 回测框架 |
| `overfitting_detector.py` | OverfittingDetector | 过拟合检测 |
| `strategy_health.py` | StrategyHealthChecker | 策略健康度 |
| `position_health.py` | PositionHealthChecker | 持仓健康度 |
| `position_sizer.py` | PositionSizer | 仓位管理 |
| `stop_loss.py` | StopLossCalculator | 止损管理 |
| `control_variable.py` | ControlVariableAnalyzer | 控制变量分析 |

### 4.10 主协调层 (1 个模块)

| 模块 | 主要类 | 职责 |
|------|--------|------|
| `navigator.py` | TradingAssistant | 系统主入口 |

---

## 五、设计原则

1. **推理优先**: 所有约束由推理层实时推导，而非事先写死
2. **计算用脚本，推理用 Agent**: Scanner/Monitor 用纯 Python，只对有信号的品种触发 LLM
3. **双存储引擎**: SQLite 管事务，DuckDB 管分析
4. **三层记忆**: 短期(内存) / 工作(SQLite) / 长期(SQLite+DuckDB+向量)
5. **自优化闭环**: 经验 → 模式 → 规则 → 参数，自动进化
6. **可配置 LLM**: 支持 OpenAI/Anthropic/Ollama/WorkBuddy 一键切换
7. **技术面+基本面融合**: 技术指标提供入场时机，基本面提供方向判断
8. **事件驱动分析**: 重大事件（地缘政治、政策变化）优先于技术信号

---

## 六、模块统计

| 层级 | 模块数 | 主要职责 |
|------|--------|----------|
| 数据模型层 | 1 | 数据结构定义（包含基本面数据模型） |
| 感知层 | 5 | 技术指标、市场分析 |
| 存储层 | 6 | 数据存储与同步 |
| 记忆层 | 8 | 经验管理、向量检索 |
| 推理层 | 5 | LLM 推理、辩论 |
| 策略层 | 6 | 扫描、执行、风控 |
| 基本面分析层 | 4 | 新闻抓取、供需数据、地缘政治追踪 |
| 进化层 | 9 | 自优化、轨迹分析 |
| 因子进化层 | 10 | 因子生成、评估、进化 |
| 高级分析层 | 7 | 可见图、Walk-Forward |
| 分析工具层 | 11 | KPI、回测、健康度 |
| 主协调层 | 1 | 系统主入口 |
| **总计** | **73** | |

---

*本文档是 QuantNova 系统的架构总览。*
