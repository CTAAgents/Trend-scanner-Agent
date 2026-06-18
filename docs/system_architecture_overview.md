# QuantNova 系统架构总览

> 版本：v2.0.0 | 创建日期：2026-06-17 | 更新：2026-06-18
> 状态：全面梳理，与实际代码结构完全对齐

## 一、系统概述

QuantNova 是一个推理重于规则的期货趋势跟踪决策辅助系统。系统不自动下单，只输出决策简报供人参考。

**核心理念**：以人为本，推理为魂，规则为果。

**核心能力**：统一数据路由、知识锚点体系、分级输出、套利分析、Reasoner Agent深度分析、闭环因子进化引擎、基本面分析模块。

**独立策略模块**：Carry 策略（期限结构套利）、套利策略（跨期/跨品种），与趋势跟踪策略并行运行。

**跨层支撑模块**：RL强化学习（信号增强）、NLP自然语言交互、事件驱动引擎（调度中枢）、Workers异步任务池。

---

## 二、分层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 10 - 主协调层 (Orchestrator)                                   │
│   navigator.py (TradingAssistant) - 系统主入口                       │
│   main.py (MainProcess) - 独立运行模式                                │
│   event_engine/ - 事件驱动调度 + 资源监控 + 定时器                    │
│   workers/ - 异步任务池（数据/信号/进化/策略四类Worker）              │
│   nlp/ - 自然语言交互（命令解析+意图识别+LLM对话）                    │
│   agent_base.py - Agent 基类定义                                     │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 9 - 分析工具层 (Analytics)                                     │
│   core/analytics/ → scoring_analytics.py, weight_optimizer.py,       │
│   threshold_optimizer.py, control_variable.py                        │
│   indicators/ → scoring_analytics.py                                 │
│   evolution/ → weight_optimizer.py                                   │
│   evolution_tools/ → overfitting_detector.py, strategy_health.py     │
│   core/risk/ → position_health.py, position_sizer.py, stop_loss.py  │
│   strategies/ → strategy_portfolio.py                                │
│   tools/ → backtest, overfitting_audit                               │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 8 - 高级分析层 (Advanced Analysis)                             │
│   evolution/ → visibility_graph.py, visibility_graph_operator.py,    │
│   factor_graph.py, factor_health_monitor.py, factor_lifecycle.py,    │
│   factor_governance.py, factor_validator.py, llm_factor_client.py    │
│   indicators/ → volatility_anchor.py                                 │
│   evolution_tools/ → regime_segmenter.py, regime_gate.py             │
│   rl/ → rl_interface_designer.py                                     │
│   core/data/ → data_validator.py                                     │
│   core/utils/ → knowledge_anchors.py, knowledge_ingestion.py         │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 7 - 因子进化层 (Factor Evolution)                              │
│   evolution/ → factor_generator.py, factor_evaluator.py,             │
│   factor_executor.py, factor_gate.py, factor_evolution_engine.py,    │
│   factor_param_optimizer.py, seed_factor_pool.py,                    │
│   multi_factor_model.py, factor_experience_db.py, evolver.py         │
│   evolution_tools/ → evolution_manager.py, trade_journal.py,         │
│   trajectory_analysis.py, trajectory_analyzer.py, circuit_breaker.py │
│   core/meta/ → meta_learner.py, meta_skill_engine.py                │
│   core/utils/ → selective_update.py, silent_bypass_detector.py      │
│   core/memory/ → skill_reflection.py, vector_store.py, retriever.py │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 6 - 进化层 (Evolution)                                         │
│   (与 Layer 7 因子进化层共享模块，但侧重自优化闭环而非因子发现)        │
│   evolution_tools/ → evolution_manager.py, overfitting_audit.py,     │
│   circuit_breaker.py, trajectory_analysis.py, trade_journal.py       │
│   core/meta/ → meta_learner.py, meta_skill_engine.py                │
│   core/memory/ → skill_reflection.py, evolution.py                  │
│   core/utils/ → selective_update.py, silent_bypass_detector.py      │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 5 - 策略层 (Strategy)                                          │
│   strategies/trend_following/ → scanner.py, strategy.py              │
│   strategies/carry/ → carry_analyzer.py                              │
│   strategies/arbitrage/ → arbitrage_analyzer.py                      │
│   strategies/ → strategy_portfolio.py                                │
│   core/risk/ → risk_management.py, position_sizer.py, stop_loss.py  │
│   core/trading/ → execution.py, portfolio.py, positions_manager.py  │
│   rl/ → scanner_integration.py                                       │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 4 - 推理层 (Reasoning)                                         │
│   reasoning/ → reasoning_engine.py, debater.py, brief.py,           │
│   belief_propagation.py, conceptual_feedback.py,                    │
│   llm_reasoning.py, scenario_analyzer.py, reasoner.py,              │
│   market_analysis.py, narrative_generator.py                         │
│   core/memory/ → llm_factory.py                                      │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 3 - 记忆层 (Memory)                                            │
│   core/memory/ → manager.py, memory_manager.py, memory_bridge.py,   │
│   experience.py, memory_vectorizer.py, vector_store.py,             │
│   retriever.py, duckdb_store.py, sqlite_store.py                    │
│   evolution/ → factor_experience_db.py, vector_enhancement.py       │
│   core/utils/ → selective_update.py                                  │
│   evolution_tools/ → regime_gate.py                                  │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 2 - 存储层 (Storage)                                           │
│   core/data/ → data_store.py, data_sync.py, data_source.py,         │
│   data_validator.py, tqsdk_bridge.py, tqsdk_worker.py,             │
│   tqsdk_batch_kline.py, unified_data_router.py                      │
│   core/memory/ → duckdb_store.py, sqlite_store.py                   │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 1 - 感知层 (Perception)                                        │
│   indicators/ → indicator_engine.py, indicator_hub.py,              │
│   multi_dimension_screener.py, macro_state.py,                      │
│   scoring_analytics.py, volatility_anchor.py                        │
│   core/data/ → unified_data_router.py, data_source.py              │
│   fundamental/ → news_crawler.py, supply_demand.py, geopolitical.py │
│   risk/ → crowding_detector.py, deployment_risk.py,                 │
│          return_attributor.py, audit_trail.py                        │
│   data/ → conflict_resolver.py, anomaly_weighter.py (V3.0)          │
│   reasoning/ → hallucination_detector.py, adaptive_prompt_router.py │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 0 - 数据模型层 (Foundation)                                    │
│   core/models.py → 所有数据结构定义                                   │
│   core/config/ → trend_scanner_config.py, control_variable.py       │
│   core/module_registry.py → 模块注册中心（统一管理所有模块）          │
└─────────────────────────────────────────────────────────────────────┘
```

**跨层模块**：

| 模块 | 文件位置 | 横跨层级 | 说明 |
|------|----------|----------|------|
| RL | `scripts/rl/` (8个文件) | Layer 5/7/8/10 | PPO信号→策略层；RL接口→高级分析层；Walk-Forward→进化层 |
| NLP | `scripts/core/nlp/` (7个文件) | Layer 1/10 | 命令解析→感知层；LLM对话→主协调层 |
| 事件引擎 | `scripts/core/event_engine/` (3个文件) | Layer 10 | 调度中枢，驱动所有定时任务 |
| Workers | `scripts/core/workers/` (4个文件) | Layer 10 | 异步任务池，解耦阻塞操作 |

---

## 三、核心工作流

### 3.1 主流程

```
用户请求 → TradingAssistant (navigator.py)
    ↓
ContextAssembler (core/context.py) → 组装 MarketContext
    ↓
├── 技术面分析 → IndicatorEngine (indicators/indicator_engine.py)
│   └── 自研35+指标 + TqSdk内置70+指标 + 7维趋势强度
├── 基本面分析 → NewsCrawler + SupplyDemandProvider + GeopoliticalTracker
│   └── 10+新闻源(国际权威+国内产业) + 供需数据 + 地缘政治风险追踪
├── 风险评估（Algometrics）
│   ├── CrowdingDetector → 拥挤度检测
│   └── DeploymentRiskEstimator → 部署风险评估
├── 收益归因（KTD-Fin）
│   └── ReturnAttributor → Barra风格收益归因
├── 审计轨迹记录（TradeArena）
│   └── AuditTrail → 决策全周期记录
├── 数据质量评估（V3.0）
│   ├── AnomalyWeighter → 异常值分层加权
│   └── DataConflictResolver → 多源数据冲突裁决
└── 幻觉检测（V3.0）
    └── HallucinationDetector → 幻觉检测
    ↓
ExperienceMemory (core/memory/experience.py) → 检索相似经验
    ↓
AdaptivePromptRouter (V3.0) → 自适应Prompt模板选择
    ↓
ReasoningEngine (reasoning/reasoning_engine.py) → LLM 推理
    ├── 包含基本面信息 + 风险评估信息注入
    ├── LLM 不可用时规则降级（fallback）
    ↓
DebateReasoningEngine (reasoning/debate_engine.py) → 鹰鸽辩论纠偏
    ├── Hawk（鹰派）：激进假设，风险放大
    ├── Dove（鸽派）：保守假设，风险缩小
    ├── 分歧评分 → 仓位调整
    ↓
BriefGenerator (reasoning/brief.py) → 生成 TradingBrief
    ├── MarketAssessment（市场评估）
    ├── Routes（操作方案）
    ├── Uncertainty（不确定性标注）
    ├── RiskAssessment（风险评估）
    ├── ReturnAttribution（收益归因）
    └── DataQuality（数据质量）
    ↓
用户查看决策简报
```

### 3.2 基本面分析流程

```
品种代码 → ContextAssembler._assemble_fundamental()
    ↓
├── NewsCrawler.crawl() → 抓取新闻（10+数据源）
│   ├── 国际: 华尔街日报/路透/彭博/CNN财经
│   ├── 国内: 财新网/新浪财经/央广网/东方财富
│   └── 雪球
    ↓
├── SupplyDemandProvider.get_supply_demand() → 获取供需数据
│   ├── 库存数据
│   ├── 产量数据
│   └── 消费数据
    ↓
├── GeopoliticalTracker.track() → 追踪地缘政治风险
│   ├── 战争/冲突 → 优先识别和平协议（风险降低信号）
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

### 3.3 因子进化流程

```
FactorEvolutionEngine.evolve()
    ↓
[1] 生成候选因子 (FactorGenerator + SeedFactorPool + KnowledgeAnchors)
    ↓
[2] 代码验证 (FactorValidator) - 安全检查+语法验证+沙箱执行
    ↓
[3] 执行因子 (FactorExecutor) - 计算因子值
    ↓
[4] 评估因子 (FactorEvaluator - IC/ICIR/t-stat)
    ↓
[4.5] Walk-Forward 验证 (WalkForwardValidator) - 可选
    ↓
[5] 门控决策 (FactorGate - 晋升/观察/淘汰)
    ↓
[6] 记忆更新 (FactorExperienceDB)
    ↓
[7] 反馈 → SeedFactorPool/KnowledgeAnchors
    ↓
[8] 检查终止条件 → 循环或结束
```

### 3.4 自优化闭环

```
交易执行 → 结果记录 (trade_journal.py)
    ↓
轨迹分析 (trajectory_analysis.py + trajectory_analyzer.py)
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

### 3.5 独立运行模式

```
MainProcess (main.py)
    ↓
EventDrivenEngine → 事件驱动调度（替代 cron）
    ├── DATA_UPDATE → 触发数据同步
    ├── SIGNAL → 触发信号扫描
    ├── FACTOR_EVOLUTION → 触发因子进化
    ├── STRATEGY_GENERATION → 触发策略生成
    ├── SYSTEM_HEALTH → 触发健康检查
    ↓
Scheduler → 定时任务注册
    ├── 智能休眠（交易时段/非交易时段自适应）
    ↓
Workers → 异步任务池
    ├── data_worker → 数据同步
    ├── signal_worker → 信号扫描
    ├── evolution_worker → 因子进化
    ├── strategy_worker → 策略生成
    ↓
ResourceMonitor → 资源监控
    ├── 内存/CPU/Token预算追踪
```

### 3.6 NLP交互流程

```
用户自然语言输入 → nlp_chat.py
    ↓
IntentRecognizer → 识别用户意图
    ↓
CommandParser → 解析为结构化命令
    ↓
LLMProcessor → 处理复杂查询
    ↓
ResponseGenerator → 生成自然语言回复
    ↓
QuickCommands → 快捷命令（/scan, /health, /evolve等）
    ↓
ContextManager → 维护对话上下文
```

---

## 四、模块清单（按层级）

### Layer 0 - 数据模型层 (4 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `models.py` | `scripts/core/` | MarketContext, Experience, TradingBrief, NewsEvent, SupplyDemandData, GeopoliticalRisk, FundamentalContext | 所有数据结构定义（含基本面） |
| `trend_scanner_config.py` | `scripts/core/config/` | TrendScannerConfig | 统一配置管理 |
| `control_variable.py` | `scripts/core/config/` | ControlVariableAnalyzer | 控制变量分析 |
| `module_registry.py` | `scripts/core/` | ModuleRegistry | 模块注册中心（统一管理所有模块） |

### Layer 1 - 感知层 (8 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `indicator_engine.py` | `scripts/indicators/` | IndicatorEngine | 自研35+指标 + TqSdk内置70+指标（含7维趋势强度） |
| `indicator_hub.py` | `scripts/indicators/` | IndicatorHub | 维度分组+字段映射+缓存 |
| `multi_dimension_screener.py` | `scripts/indicators/` | MultiDimensionScreener | 五维度评分+归一化+信号分类 |
| `macro_state.py` | `scripts/indicators/` | MacroStateDetector | 宏观状态检测 |
| `scoring_analytics.py` | `scripts/indicators/` | ScoringAnalytics | 打分分析 |
| `volatility_anchor.py` | `scripts/indicators/` | VolatilityAnchor | 波动率锚定 |
| `unified_data_router.py` | `scripts/core/data/` | UnifiedDataRouter | 9类数据智能路由+自动Fallback |
| `data_source.py` | `scripts/core/data/` | DataSourceFactory | 数据源适配器 |

**基本面子模块 (3 个模块)**:

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `news_crawler.py` | `scripts/fundamental/` | NewsCrawler | 新闻抓取（10+数据源：国际权威+国内产业） |
| `supply_demand.py` | `scripts/fundamental/` | SupplyDemandProvider | 供需数据接口 |
| `geopolitical.py` | `scripts/fundamental/` | GeopoliticalTracker | 地缘政治风险追踪 |

**风险评估子模块 (4 个模块)**:

| 模块 | 路径 | 主要类 | 职责 | 论文来源 |
|------|------|--------|------|----------|
| `crowding_detector.py` | `scripts/risk/` | CrowdingDetector | 拥挤度检测 | Algometrics |
| `deployment_risk.py` | `scripts/risk/` | DeploymentRiskEstimator | 部署风险评估 | Algometrics |
| `return_attributor.py` | `scripts/risk/` | ReturnAttributor | Barra风格收益归因 | KTD-Fin |
| `audit_trail.py` | `scripts/risk/` | AuditTrail | 决策审计轨迹 | TradeArena |

**V3.0方案子模块 (4 个模块)**:

| 模块 | 路径 | 主要类 | 职责 | 方案章节 |
|------|------|--------|------|----------|
| `conflict_resolver.py` | `scripts/data/` | DataConflictResolver | 多源数据冲突裁决 | 第一章1.4.1 |
| `anomaly_weighter.py` | `scripts/data/` | AnomalyWeighter | 异常值分层加权 | 第一章1.4.2 |
| `hallucination_detector.py` | `scripts/reasoning/` | HallucinationDetector | 幻觉检测 | 第二章2.3 |
| `adaptive_prompt_router.py` | `scripts/reasoning/` | AdaptivePromptRouter | 自适应Prompt路由 | 第二章2.1 |

### Layer 2 - 存储层 (8 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `data_store.py` | `scripts/core/data/` | DataStore | SQLite+DuckDB 双引擎存储 |
| `data_sync.py` | `scripts/core/data/` | DataSyncManager | 数据同步管理 |
| `data_validator.py` | `scripts/core/data/` | DataValidator | 数据质量验证 |
| `tqsdk_bridge.py` | `scripts/core/data/` | TqSdkBridge | TqSdk 数据桥接 |
| `tqsdk_worker.py` | `scripts/core/data/` | TqSdkWorker | TqSdk 工作进程 |
| `tqsdk_batch_kline.py` | `scripts/core/data/` | TqSdkBatchKline | TqSdk批量K线下载 |
| `duckdb_store.py` | `scripts/core/memory/` | DuckDBStore | DuckDB 分析型存储 |
| `sqlite_store.py` | `scripts/core/memory/` | SQLiteStore | SQLite 事务型存储 |

### Layer 3 - 记忆层 (10 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `manager.py` | `scripts/core/memory/` | UnifiedMemoryManager | 记忆系统唯一入口 |
| `memory_manager.py` | `scripts/core/memory/` | MemoryManager | 记忆管理器 |
| `experience.py` | `scripts/core/memory/` | ExperienceMemory | 经验记忆池 |
| `memory_bridge.py` | `scripts/core/memory/` | MemoryBridge | Scanner/Reasoner/Evolver 集成 |
| `memory_vectorizer.py` | `scripts/core/memory/` | MemoryVectorizer | 文本语义向量化 |
| `vector_store.py` | `scripts/core/memory/` | VectorStore | 向量存储 |
| `retriever.py` | `scripts/core/memory/` | MemoryRetriever | 多粒度检索 |
| `skill_reflection.py` | `scripts/core/memory/` | SkillAwareReflector | 技能反思 |
| `evolution.py` | `scripts/core/memory/` | EvolutionMemory | 进化记忆 |
| `llm_factory.py` | `scripts/core/memory/` | LLMFactory | LLM 工厂 |
| `factor_experience_db.py` | `scripts/evolution/` | FactorExperienceDB | 因子演化轨迹经验 |
| `vector_enhancement.py` | `scripts/evolution/` | VectorEnhancer | 向量增强 |
| `regime_gate.py` | `scripts/evolution_tools/` | RegimeGate | 机制门权重调整 |

### Layer 4 - 推理层 (11 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `reasoning_engine.py` | `scripts/reasoning/` | ReasoningEngine | LLM 推理引擎（含fallback降级） |
| `debater.py` | `scripts/reasoning/` | Debater | 辩论角色定义 |
| `debate_engine.py` | `scripts/reasoning/` | DebateReasoningEngine | 鹰鸽辩论纠偏引擎 |
| `brief.py` | `scripts/reasoning/` | BriefGenerator | 交易决策简报生成 |
| `belief_propagation.py` | `scripts/reasoning/` | BeliefPropagationManager | 信念传播（FinCon） |
| `conceptual_feedback.py` | `scripts/reasoning/` | ConceptualFeedbackGenerator | 概念性反馈 |
| `llm_reasoning.py` | `scripts/reasoning/` | LLMReasoner | LLM 推理器 |
| `reasoner.py` | `scripts/reasoning/` | ReasonerAgent | Reasoner Agent深度分析 |
| `scenario_analyzer.py` | `scripts/reasoning/` | ScenarioAnalyzer | 概率加权场景分析 |
| `market_analysis.py` | `scripts/reasoning/` | MarketAnalyzer | 市场分析 |
| `narrative_generator.py` | `scripts/reasoning/` | NarrativeGenerator | 叙事生成器 |

### Layer 5 - 策略层 (10 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `scanner.py` | `scripts/strategies/trend_following/` | TrendScanner | 3层融合趋势扫描器 |
| `strategy.py` | `scripts/strategies/trend_following/` | StrategyPool | 趋势策略池 |
| `carry_analyzer.py` | `scripts/strategies/carry/` | CarryAnalyzer | Carry策略：期限结构套利 |
| `arbitrage_analyzer.py` | `scripts/strategies/arbitrage/` | ArbitrageAnalyzer | 跨期/跨品种套利 |
| `strategy_portfolio.py` | `scripts/strategies/` | StrategyPortfolio | 多策略组合管理 |
| `risk_management.py` | `scripts/core/risk/` | RiskManager | 风险管理 |
| `position_health.py` | `scripts/core/risk/` | PositionHealthChecker | 持仓健康度 |
| `position_sizer.py` | `scripts/core/risk/` | PositionSizer | 仓位管理 |
| `execution.py` | `scripts/core/trading/` | ExecutionEngine | 执行引擎 |
| `portfolio.py` | `scripts/core/trading/` | PortfolioManager | 组合管理 |
| `positions_manager.py` | `scripts/core/trading/` | PositionsManager | 持仓管理 |

### Layer 6 - 进化层 (9 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `evolution_manager.py` | `scripts/evolution_tools/` | EvolutionManager | 进化管理器 |
| `trajectory_analysis.py` | `scripts/evolution_tools/` | TradeTrajectoryAnalyzer | 交易轨迹分析 |
| `trajectory_analyzer.py` | `scripts/evolution_tools/` | TrajectoryAnalyzer | 交易轨迹分析器 |
| `trade_journal.py` | `scripts/evolution_tools/` | TradeJournal | 交易日志 |
| `circuit_breaker.py` | `scripts/evolution_tools/` | CircuitBreaker | 策略级熔断 |
| `overfitting_audit.py` | `scripts/evolution_tools/` | OverfittingAuditor | 过拟合审计 |
| `overfitting_detector.py` | `scripts/evolution_tools/` | OverfittingDetector | 过拟合检测 |
| `meta_learner.py` | `scripts/core/meta/` | MetaLearningEngine | 元学习引擎 |
| `meta_skill_engine.py` | `scripts/core/meta/` | MetaSkillEngine | 元技能引擎 |
| `skill_reflection.py` | `scripts/core/memory/` | SkillAwareReflector | 技能反思 |
| `selective_update.py` | `scripts/core/utils/` | SelectiveUpdater | 选择性更新 |
| `silent_bypass_detector.py` | `scripts/core/utils/` | SilentBypassDetector | 静默旁路检测 |

### Layer 7 - 因子进化层 (23 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `factor_generator.py` | `scripts/evolution/` | FactorGenerator | LLM 因子生成 |
| `factor_evaluator.py` | `scripts/evolution/` | FactorEvaluator | 因子评估（IC/ICIR/t-stat） |
| `factor_executor.py` | `scripts/evolution/` | FactorExecutor | 因子执行 |
| `factor_gate.py` | `scripts/evolution/` | FactorGate | 因子准入门控 |
| `factor_evolution_engine.py` | `scripts/evolution/` | FactorEvolutionEngine | 因子进化引擎 |
| `factor_param_optimizer.py` | `scripts/evolution/` | FactorParamOptimizer | 因子参数优化 |
| `seed_factor_pool.py` | `scripts/evolution/` | SeedFactorPool | 种子因子池 |
| `multi_factor_model.py` | `scripts/evolution/` | MultiFactorModel | 多因子模型 |
| `factor_validator.py` | `scripts/evolution/` | FactorValidator | 因子代码验证+沙箱执行 |
| `factor_lifecycle.py` | `scripts/evolution/` | FactorLifecycle | 因子生命周期管理 |
| `factor_health_monitor.py` | `scripts/evolution/` | FactorHealthMonitor | 因子健康监控 |
| `factor_governance.py` | `scripts/evolution/` | FactorGovernance | 因子治理 |
| `factor_graph.py` | `scripts/evolution/` | FactorGraph | 因子依赖图 |
| `llm_factor_client.py` | `scripts/evolution/` | LLMFactorClient | LLM因子生成客户端 |
| `evolver.py` | `scripts/evolution/` | Evolver | 进化器主入口 |
| `visibility_graph.py` | `scripts/evolution/` | VGRSI, MultiTimeframeVGRSI | 可见图算法 |
| `visibility_graph_operator.py` | `scripts/evolution/` | VisibilityGraphOperator | 可见图算子 |
| `walk_forward_validator.py` | `scripts/evolution/` | WalkForwardValidator | 滚动前推验证 |
| `weight_optimizer.py` | `scripts/evolution/` | WeightOptimizer | 权重优化 |
| `vector_enhancement.py` | `scripts/evolution/` | VectorEnhancer | 向量增强 |
| `factor_experience_db.py` | `scripts/evolution/` | FactorExperienceDB | 因子经验数据库 |

### Layer 8 - 高级分析层 (12 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `data_validator.py` | `scripts/core/data/` | DataValidator | 数据质量验证 |
| `knowledge_anchors.py` | `scripts/core/utils/` | KnowledgeAnchorManager | 知识锚点体系 |
| `knowledge_ingestion.py` | `scripts/core/utils/` | KnowledgeIngestion | 知识摄取 |
| `volatility_anchor.py` | `scripts/indicators/` | VolatilityAnchor | 波动率锚定 |
| `regime_segmenter.py` | `scripts/evolution_tools/` | RegimeSegmenter | 分层机制检测 |
| `regime_gate.py` | `scripts/evolution_tools/` | RegimeGate | 机制门 |
| `rl_interface_designer.py` | `scripts/rl/` | RLInterfaceDesigner | RL 接口设计 |

### Layer 9 - 分析工具层 (11 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `scoring_analytics.py` | `scripts/indicators/` | ScoringAnalytics | 打分分析 |
| `weight_optimizer.py` | `scripts/evolution/` | WeightOptimizer | 权重优化 |
| `threshold_optimizer.py` | `scripts/core/` | ThresholdOptimizer | 阈值优化 |
| `control_variable.py` | `scripts/core/config/` | ControlVariableAnalyzer | 控制变量分析 |
| `overfitting_detector.py` | `scripts/evolution_tools/` | OverfittingDetector | 过拟合检测 |
| `strategy_health.py` | `scripts/evolution_tools/` | StrategyHealthChecker | 策略健康度 |
| `position_health.py` | `scripts/core/risk/` | PositionHealthChecker | 持仓健康度 |
| `position_sizer.py` | `scripts/core/risk/` | PositionSizer | 仓位管理 |
| `stop_loss.py` | `scripts/core/risk/` | StopLossCalculator | 止损管理 |
| `strategy_portfolio.py` | `scripts/strategies/` | StrategyPortfolio | 多策略组合 |

### Layer 10 - 主协调层 (14 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `navigator.py` | `scripts/core/` | TradingAssistant | 系统主入口，协调全流程 |
| `main.py` | `scripts/core/` | MainProcess | 独立运行模式入口 |
| `agent_base.py` | `scripts/core/` | AgentBase | Agent 基类定义 |
| `event_engine.py` | `scripts/core/event_engine/` | EventDrivenEngine | 事件驱动调度引擎 |
| `scheduler.py` | `scripts/core/event_engine/` | Scheduler | 定时任务调度器 |
| `resource_monitor.py` | `scripts/core/event_engine/` | ResourceMonitor | 资源监控器 |
| `data_worker.py` | `scripts/core/workers/` | DataWorker | 数据同步异步任务 |
| `signal_worker.py` | `scripts/core/workers/` | SignalWorker | 信号扫描异步任务 |
| `evolution_worker.py` | `scripts/core/workers/` | EvolutionWorker | 因子进化异步任务 |
| `strategy_worker.py` | `scripts/core/workers/` | StrategyWorker | 策略生成异步任务 |
| `nlp_chat.py` | `scripts/core/nlp/` | NLPChat | 自然语言交互入口 |
| `nlp_engine.py` | `scripts/core/nlp/` | NLPEngine | NLP引擎核心 |
| `intent_recognizer.py` | `scripts/core/nlp/` | IntentRecognizer | 意图识别 |
| `command_parser.py` | `scripts/core/nlp/` | CommandParser | 命令解析 |
| `llm_processor.py` | `scripts/core/nlp/` | LLMProcessor | LLM 处理器 |
| `response_generator.py` | `scripts/core/nlp/` | ResponseGenerator | 回复生成器 |
| `quick_commands.py` | `scripts/core/nlp/` | QuickCommands | 快捷命令 |
| `context_manager.py` | `scripts/core/nlp/` | ContextManager | 对话上下文管理 |

### 跨层 - RL模块 (8 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `base.py` | `scripts/rl/` | AgentBase, RLState, RLAction | RL 基类+生命周期（perceive→reason→act→reflect） |
| `agent_ppo.py` | `scripts/rl/` | AgentPPO | PPO 算法实现（GAE+RatioClipping+熵正则） |
| `networks.py` | `scripts/rl/` | ActorPPO, CriticPPO, StateNormalizer | 网络架构 |
| `futures_env.py` | `scripts/rl/` | FuturesTradingEnv, MultiAssetVecEnv | Gym 环境 |
| `trainer.py` | `scripts/rl/` | RLTrainer | 训练器 |
| `walk_forward_rl.py` | `scripts/rl/` | RLWalkForwardValidator | RL Walk-Forward 验证 |
| `scanner_integration.py` | `scripts/rl/` | RLSignalGenerator | RL→Scanner 信号集成 |
| `rl_interface_designer.py` | `scripts/rl/` | RLInterfaceDesigner | RL 接口设计（GIFT启发） |

### 跨层 - Tools 工具集 (7+ 个模块)

| 模块 | 路径 | 主要类 | 职责 |
|------|------|--------|------|
| `scan_opportunities.py` | `tools/core/` | CLI 主入口 | 扫描/Reasoner/进化/健康度 |
| `sync_data.py` | `tools/core/` | 数据同步工具 | DuckDB数据同步 |
| `sync_indicators.py` | `tools/core/` | 指标同步工具 | 技术指标批量同步 |
| `orchestrator.py` | `tools/core/` | OrchestratorAgent | 任务分发+结果聚合 |
| `run_reasoner.py` | `tools/core/` | - | Reasoner 运行脚本 |
| `run_debater.py` | `tools/core/` | - | Debater 运行脚本 |
| `run_evolver.py` | `tools/core/` | - | Evolver 运行脚本 |
| `train_ppo.py` | `tools/rl/` | - | PPO 训练脚本 |
| `tune_rl_hyperparams.py` | `tools/rl/` | - | RL 超参调优 |
| `auto_rl_pipeline.py` | `tools/rl/` | - | RL 自动化流水线 |

---

## 五、设计原则与论文映射

### 5.1 核心设计原则

1. **推理优先**: 所有约束由推理层实时推导，而非事先写死
2. **计算用脚本，推理用 Agent**: Scanner/Monitor 用纯 Python，只对有信号的品种触发 LLM
3. **双存储引擎**: SQLite 管事务，DuckDB 管分析
4. **三层记忆**: 短期(内存) / 工作(SQLite) / 长期(SQLite+DuckDB+向量)
5. **自优化闭环**: 经验 → 模式 → 规则 → 参数，自动进化
6. **可配置 LLM**: 支持 OpenAI/Anthropic/Ollama/WorkBuddy 一键切换
7. **技术面+基本面融合**: 技术指标提供入场时机，基本面提供方向判断
8. **事件驱动分析**: 重大事件（地缘政治、政策变化）优先于技术信号
9. **因子即代码**: 因子是 LLM 生成的可执行代码，沙箱验证后准入
10. **门控不可调**: 门控阈值预设，防 p-hacking

### 5.2 论文实现映射

| 论文 | 核心思想 | 实现模块 | 代码路径 |
|------|----------|----------|----------|
| **Agentic AI** (arXiv:2603.14288) | 闭环因子发现 | `FactorEvolutionEngine` | `scripts/evolution/` |
| **FactorEngine** (arXiv:2603.16365) | 因子即代码，三大分离 | `FactorGenerator` + `FactorEvaluator` | `scripts/evolution/` |
| **FinCon** | 信念传播，概念反馈 | `BeliefPropagationManager` | `scripts/reasoning/` |
| **GIFT** | LLM引导RL接口设计 | `RLInterfaceDesigner` | `scripts/rl/` |
| **Davey框架** | 蒙特卡洛/孵化/熔断/组合 | 4个模块 | `scripts/evolution_tools/` |

**详细映射请查看** [论文实现指南](paper_implementation_guide.md)

---

## 六、模块统计

| 层级 | 模块数 | 主要职责 |
|------|--------|----------|
| Layer 0 - 数据模型层 | 3 | 数据结构+配置定义 |
| Layer 1 - 感知层 | 11 (8+3基本面) | 技术指标、市场分析、基本面 |
| Layer 2 - 存储层 | 8 | 数据存储与同步 |
| Layer 3 - 记忆层 | 13 | 经验管理、向量检索 |
| Layer 4 - 推理层 | 11 | LLM 推理、辩论 |
| Layer 5 - 策略层 | 11 | 扫描、执行、风控、套利 |
| Layer 6 - 进化层 | 12 | 自优化、轨迹分析 |
| Layer 7 - 因子进化层 | 21 | 因子生成、评估、进化 |
| Layer 8 - 高级分析层 | 7 | 可见图、Walk-Forward、机制检测 |
| Layer 9 - 分析工具层 | 10 | KPI、回测、健康度 |
| Layer 10 - 主协调层 | 18 | 系统主入口+NLP+事件引擎+Workers |
| 跨层 - RL | 8 | PPO强化学习 |
| 跨层 - Tools | 10 | CLI工具集 |
| **总计** | **122** | |

---

## 七、数据路由体系

### 统一数据路由

9种数据类型的智能路由，自动 Fallback：

| 数据类型 | 路由优先级 | 说明 |
|----------|-----------|------|
| `kline` | DuckDB → TqSdk → Pytdx → CSV | K线数据 |
| `quote` | DuckDB → TqSdk → Pytdx → CSV | 实时行情 |
| `basis` | DuckDB → AkShare → CSV | 基差数据 |
| `seasonality` | DuckDB → AkShare → CSV | 季节性数据 |
| `inventory` | DuckDB → AkShare → CSV | 仓单数据 |
| `top_list` | DuckDB → AkShare → CSV | 龙虎榜数据 |
| `margin` | DuckDB → AkShare → CSV | 保证金数据 |
| `macro` | DuckDB → AkShare → CSV | 宏观经济数据 |
| `delivery` | DuckDB → AkShare → CSV | 交割数据 |

### 数据时效性检查

| 级别 | 滞后阈值 | 处理方式 |
|------|----------|----------|
| `fresh` | < 4小时 | 正常使用 |
| `stale` | 4-24小时 | 标注警告 |
| `critical` | > 24小时 | 先向用户确认 |

---

*本文档是 QuantNova 系统的架构总览，与实际代码结构完全对齐。*
