---
name: trend-scanner-agent
description: >
  推理重于规则的期货趋势跟踪决策辅助系统 v5.0。
  闭环迭代因子进化引擎（Generate→Eval→Gate→Memory），
  截面 IC/ICIR 评估，贝叶斯参数优化，多因子组合模型。
  数据源：TqSdk（首选）+ 通达信 MCP（备选）+ 本地数据库缓存。
---

# Trend Scanner Agent v5.0

> 推理重于规则的期货趋势跟踪决策辅助系统

**新用户请查看 [用户手册](docs/USER_GUIDE.md)**

## 一句话概括

闭环迭代因子进化引擎 + 八层管线架构，TqSdk 拉取数据写入本地 DuckDB，纯 Python 做计算，LLM 做推理，每日自动扫描 60+ 非僵尸期货品种，信号输出附带仓位建议和止损价位。

## 核心理念

**以人为本，推理为魂，规则为果。**

所有看似"规则"的内容（止损、仓位、入场条件）均由推理层根据当前市场状态动态生成，而非事先写死。系统不自动下单，只输出决策简报供人参考。

## 快速开始

```bash
git clone https://github.com/CTAAgents/Trend-scanner-Agent.git
cd Trend-scanner-Agent
pip install -r requirements.txt

# 数据同步（首次使用必须执行）
python tools/sync_data.py sync --days 120

# 运行扫描
python tools/scan_opportunities.py --output text --save

# 因子评估
python tools/scan_opportunities.py --evaluate-factors

# 因子进化
python tools/scan_opportunities.py --evolve --evolve-rounds 5
```

## v5.0 新特性

- **闭环因子进化**: Generate → Eval → Gate → Memory 自动迭代
- **截面 IC/ICIR 评估**: 多品种截面预测能力量化
- **贝叶斯参数优化**: Optuna TPE 自动搜索最优参数
- **多因子组合**: LightGBM 非线性因子组合
- **种子因子池**: 研报知识注入 + 预置种子因子
- **失败经验库**: 从失败中学习，避免重复错误
- **全品种扫描**: 60+ 非僵尸品种，数据源健康检查

## 系统架构

```
数据层 → 感知层 → 因子进化层 → 推理层 → 执行层 → 进化层 → 记忆层
```

---

## 一、系统架构（详细）

### 1.1 整体架构（v5.0）

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Trend Scanner Agent v5.0                          │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    数据层（Data Layer）                        │   │
│  │  TqSdk → DuckDB/SQLite ← 通达信 MCP ← CSV                   │   │
│  │  DataSourceFactory（自动选择 + 健康检查）                      │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                  ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    感知层（Perception Layer）                  │   │
│  │  IndicatorEngine（35+ 技术指标）                              │   │
│  │  MacroStateDetector（宏观状态检测）                           │   │
│  │  TrendPhaseDetector（趋势阶段识别）                           │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                  ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    因子进化层（Factor Evolution Layer）        │   │
│  │                                                               │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │   │
│  │  │ 因子生成器   │→│ 因子执行器   │→│ 因子评估器   │       │   │
│  │  │ (Generator)  │   │ (Executor)  │   │ (Evaluator) │       │   │
│  │  └─────────────┘   └─────────────┘   └─────────────┘       │   │
│  │         ↑                                    │               │   │
│  │         │         ┌─────────────┐            │               │   │
│  │         │         │ 门控决策器  │←───────────┘               │   │
│  │         │         │   (Gate)    │                             │   │
│  │         │         └──────┬──────┘                             │   │
│  │         │                │                                    │   │
│  │  ┌──────┴──────────────┐ │ ┌─────────────┐                  │   │
│  │  │ 种子因子池          │ │ │ 经验数据库  │                  │   │
│  │  │ (SeedFactorPool)    │ │ │ (Experience)│                  │   │
│  │  └─────────────────────┘ │ └─────────────┘                  │   │
│  │                           ▼                                   │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │   │
│  │  │ 参数优化器   │   │ 多因子模型  │   │ 研报解析器  │       │   │
│  │  │ (Optimizer) │   │ (MultiFactor)│   │ (ReportParser)│     │   │
│  │  └─────────────┘   └─────────────┘   └─────────────┘       │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                  ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    推理层（Reasoning Layer）                   │   │
│  │  Reasoner Agent（LLM 推理 → 决策简报）                       │   │
│  │  Debater Agent（多角色协作辩论）                              │   │
│  │  Orchestrator Agent（主协调器）                               │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                  ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    执行层（Execution Layer）                   │   │
│  │  PositionSizer（仓位管理）                                    │   │
│  │  StopLossCalculator（动态止损）                               │   │
│  │  ExecutionEngine（执行引擎 + 风控）                           │   │
│  │  PortfolioManager（组合管理）                                 │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                  ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    进化层（Evolution Layer）                   │   │
│  │  StrategyHealthChecker（策略健康度）                          │   │
│  │  OverfittingDetector（过拟合检测）                            │   │
│  │  WalkForwardBacktester（Walk-Forward 回测）                   │   │
│  │  TrajectoryAnalyzer（轨迹分析）                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    记忆层（Memory Layer）                      │   │
│  │  MemoryBridge（集成桥接器）                                   │   │
│  │  SQLite（经验/规则/日志）                                     │   │
│  │  DuckDB（K线/指标/因子库）                                    │   │
│  │  VectorStore（向量检索）                                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心子系统

#### 因子进化子系统（v5.0 新增）

```
闭环迭代: Generate → Execute → Evaluate → Gate → Memory → Feedback → Generate

候选来源（5 级优先级）:
  1. 内置因子库（第 1 轮）
  2. 种子因子池（待验证种子）
  3. LLM 因子生成（FactorGenerator + 经验反馈注入）
  4. 因子知识库
  5. 规则变体生成

门控决策（三元，阈值预设不可调）:
  - 晋升: |ICIR| >= 1.0 且至少 2 项指标达标
  - 淘汰: |ICIR| < 0.5 且至少 2 项指标不达标
  - 观察: 其余

评估指标:
  - 截面 IC（Spearman 秩相关）
  - ICIR（IC 均值/IC 标准差）
  - t 统计量
  - 多空 Sharpe
```

#### 多因子组合子系统（v5.0 新增）

```
单因子 ICIR < 0.5 → 多因子组合 → LightGBM 非线性组合 → 综合信号

模型类型:
  - LightGBM（梯度提升树，默认）
  - Ridge（线性回归）
  - 等权（基准）

评估:
  - 训练/测试集时间序列分割（70/30）
  - OOS IC/ICIR/多空 Sharpe
  - 特征重要性排序
```

### 1.3 设计原则

| 原则 | 含义 | 体现 |
|------|------|------|
| 推理重于规则 | 所有"规则"由推理层动态生成 | 不存在独立的规则层 |
| 计算用脚本，推理用 Agent | 确定性计算不调 LLM | Scanner/Monitor 是纯 Python |
| 数据本地化 | TqSdk 数据写入本地 DuckDB | 避免重复 API 调用 |
| 因子即代码 | 因子是 LLM 生成的可执行代码 | FactorEngine 思想 |
| 逻辑-参数分离 | LLM 负责创意，贝叶斯负责调参 | 三大分离思想 |
| 门控不可调 | 门控阈值预设，防 p-hacking | Paper 1 透明门控 |
| 从失败中学习 | 经验库记录失败轨迹，注入生成器 | FactorEngine 轨迹感知 |

---

## 二、模块清单

### 2.1 v5.0 因子进化子系统（8 个模块）

| 模块 | 文件 | 功能 |
|------|------|------|
| FactorEvaluator | `factor_evaluator.py` | 截面 IC/ICIR 评估引擎 |
| FactorExecutor | `factor_executor.py` | 因子代码安全执行引擎 |
| FactorGate | `factor_gate.py` | 三元门控决策器 |
| FactorEvolutionEngine | `factor_evolution_engine.py` | 闭环迭代进化引擎 |
| FactorParamOptimizer | `factor_param_optimizer.py` | 贝叶斯参数优化器 |
| SeedFactorPool | `seed_factor_pool.py` | 种子因子池管理 |
| MultiFactorModel | `multi_factor_model.py` | 多因子组合模型 |
| FactorExperienceDB | `factor_experience_db.py` | 失败经验库 |

### 2.2 因子生成与验证（4 个模块）

| 模块 | 文件 | 功能 |
|------|------|------|
| FactorGenerator | `factor_generator.py` | LLM 引导的因子生成器 |
| FactorValidator | `factor_validator.py` | 因子代码验证器 |
| FactorKnowledgeManager | `factor_generator.py` | 因子知识库管理 |
| ReportParser | `report_parser.py` | 研报解析器 |

### 2.3 核心扫描与推理（6 个模块）

| 模块 | 文件 | 功能 |
|------|------|------|
| TrendScanner | `scanner.py` | 主扫描器（趋势强度计算） |
| IndicatorEngine | `indicators.py` | 35+ 技术指标计算 |
| MacroStateDetector | `macro_state.py` | 宏观状态检测 |
| ReasoningEngine | `reasoning.py` | LLM 推理引擎 |
| DebateReasoningEngine | `debate_engine.py` | 多角色辩论引擎 |
| TradingAssistant | `navigator.py` | 主协调器 |

### 2.4 执行与风控（5 个模块）

| 模块 | 文件 | 功能 |
|------|------|------|
| PositionSizer | `position_sizer.py` | 仓位管理（凯利/自适应） |
| StopLossCalculator | `stop_loss.py` | 动态止损（ATR/移动/时间） |
| ExecutionEngine | `execution.py` | 执行引擎 + 风控 |
| PortfolioManager | `portfolio.py` | 组合管理 |
| RiskManager | `risk_management.py` | 风险管理 |

### 2.5 进化与健康（5 个模块）

| 模块 | 文件 | 功能 |
|------|------|------|
| StrategyHealthChecker | `strategy_health.py` | 策略健康度评估 |
| OverfittingDetector | `overfitting_detector.py` | 过拟合检测 |
| WalkForwardBacktester | `backtest.py` | Walk-Forward 回测 |
| TrajectoryAnalyzer | `trajectory_analyzer.py` | 轨迹分析器 |
| EvolutionManager | `evolution_manager.py` | 进化管理器 |

### 2.6 数据与记忆（6 个模块）

| 模块 | 文件 | 功能 |
|------|------|------|
| DataSourceFactory | `data_source.py` | 数据源工厂（自动选择） |
| MemoryBridge | `memory_bridge.py` | 记忆系统桥接器 |
| DataSyncManager | `storage/data_sync.py` | 数据同步管理 |
| DuckDBStore | `storage/duckdb_store.py` | DuckDB 存储 |
| SQLiteStore | `storage/sqlite_store.py` | SQLite 存储 |
| TqSdkBridge | `tqsdk_bridge.py` | TqSdk 进程隔离桥接 |

### 2.7 其他模块（10 个）

| 模块 | 文件 | 功能 |
|------|------|------|
| BeliefPropagationManager | `belief_propagation.py` | 信念传播（FinCon） |
| ConceptualFeedbackGenerator | `conceptual_feedback.py` | 概念性反馈 |
| RLInterfaceDesigner | `rl_interface_designer.py` | RL 接口设计（GIFT） |
| LLMClient | `llm_factor_client.py` | LLM 客户端基类 |
| MultiIndicatorConsensus | `market_analysis.py` | 多指标共识 |
| MemoryVectorizer | `memory_vectorizer.py` | 记忆向量化 |
| RegimeGate | `regime_gate.py` | 机制门 |
| RegimeSegmenter | `regime_segmenter.py` | 分层机制检测 |
| SelectiveUpdater | `selective_update.py` | 选择性更新 |
| SilentBypassDetector | `silent_bypass_detector.py` | 静默旁路检测 |

---

## 三、CLI 使用手册

### 3.1 主入口：scan_opportunities.py

```bash
python tools/scan_opportunities.py [选项]
```

#### 扫描选项

| 参数 | 说明 | 示例 |
|------|------|------|
| `--symbols` | 指定品种（逗号分隔） | `--symbols RB,I,JM` |
| `--output` | 输出格式 | `--output text` 或 `--output json` |
| `--save` | 保存结果到文件 | `--save` |
| `--use-dynamic-factors` | 启用动态因子 | `--use-dynamic-factors` |

#### 因子评估与进化

| 参数 | 说明 | 示例 |
|------|------|------|
| `--evaluate-factors` | 截面 IC/ICIR 评估 | `--evaluate-factors` |
| `--evolve` | 闭环因子进化 | `--evolve --evolve-rounds 5` |
| `--evolve-rounds` | 进化轮数（默认 5） | `--evolve-rounds 10` |
| `--evolve-target` | 目标晋升数（默认 3） | `--evolve-target 5` |
| `--optimize-params` | 贝叶斯参数优化 | `--optimize-params --opt-trials 50` |
| `--opt-trials` | 优化试验次数（默认 30） | `--opt-trials 100` |
| `--load-report` | 从研报加载种子因子 | `--load-report report.txt` |

#### 风控与健康

| 参数 | 说明 | 示例 |
|------|------|------|
| `--health-check` | 策略健康度评估 | `--health-check` |
| `--overfitting-check` | 过拟合检测 | `--overfitting-check` |
| `--execution-check` | 执行引擎风控检查 | `--execution-check` |

### 3.2 常用命令

```bash
# 1. 日常扫描（60 个非僵尸品种）
python tools/scan_opportunities.py --output text --save

# 2. 指定品种扫描
python tools/scan_opportunities.py --symbols RB,I,JM,CU --output text

# 3. 因子评估
python tools/scan_opportunities.py --evaluate-factors

# 4. 因子进化（5 轮，目标 3 个晋升因子）
python tools/scan_opportunities.py --evolve --evolve-rounds 5 --evolve-target 3

# 5. 从研报加载种子因子并进化
python tools/scan_opportunities.py --evolve --load-report data/report.txt

# 6. 参数优化
python tools/scan_opportunities.py --optimize-params --opt-trials 50

# 7. 策略健康度检查
python tools/scan_opportunities.py --health-check

# 8. 过拟合检测
python tools/scan_opportunities.py --overfitting-check

# 9. 组合使用：扫描 + 评估 + 健康检查
python tools/scan_opportunities.py --evaluate-factors --health-check --save
```

### 3.3 数据同步

```bash
# 全量同步（品种 + 行情 + K线）
python tools/sync_data.py sync --days 120 --min-oi 10000

# 仅同步行情
python tools/sync_data.py quotes --min-oi 10000

# 仅同步 K 线
python tools/sync_data.py klines --days 120 --force

# 查看统计
python tools/sync_data.py stats
```

### 3.4 其他工具

```bash
# 心跳监控
python tools/heartbeat.py

# Evolver（策略进化）
python tools/run_evolver.py evolve
python tools/run_evolver.py status

# Reasoner（推理）
python tools/run_reasoner.py --symbol DCE.jm2609
```

---

## 四、工作流

### 4.1 日常扫描工作流

```
08:40 定时触发
  ↓
[1] 数据同步（sync_data.py）
  - TqSdk 拉取最新行情
  - 更新 DuckDB K 线数据
  ↓
[2] 全品种扫描（scan_opportunities.py）
  - 60 个非僵尸品种
  - 计算 35+ 技术指标
  - 宏观状态检测 → 策略权重调整
  - 信号筛选（OR 模式）
  - 仓位建议 + 止损价位
  ↓
[3] 因子评估（--evaluate-factors）
  - 截面 IC/ICIR 计算
  - 门控决策（晋升/观察/淘汰）
  ↓
[4] 信号输出
  - 有信号 → 推送 Reasoner Agent
  - 无信号 → 静默
```

### 4.2 因子进化工作流

```
[1] 种子因子准备
  - 内置因子库（7 个基础因子）
  - 种子因子池（5 个预置 + 研报提取）
  - LLM 生成（需要 API）
  ↓
[2] 闭环迭代（--evolve）
  for round in 1..max_rounds:
    ↓
    [2.1] 生成候选因子（5 个/轮）
    ↓
    [2.2] 执行因子（计算截面值）
    ↓
    [2.3] 评估因子（IC/ICIR/t-stat/Sharpe）
    ↓
    [2.4] 门控决策（晋升/观察/淘汰）
    ↓
    [2.5] 记忆更新（经验库 + 种子状态）
    ↓
    [2.6] 反馈注入下一轮
  ↓
[3] 晋升因子入库
  - 因子知识库保存
  - 种子因子池状态更新
  ↓
[4] 参数优化（--optimize-params）
  - Optuna TPE 搜索最优参数
  - 固定参数写回因子代码
```

### 4.3 策略进化工作流

```
交易结束后
  ↓
[1] 记录交易反馈
  - 交易结果（盈亏/持仓时间/市场状态）
  - 存入记忆系统
  ↓
[2] 策略健康度评估（--health-check）
  - 夏普比率 / 最大回撤 / 胜率趋势
  - 连续亏损 / 盈亏比
  - 退役判断
  ↓
[3] 过拟合检测（--overfitting-check）
  - 蒙特卡洛模拟
  - 参数敏感性测试
  - 样本内外对比
  ↓
[4] 轨迹分析
  - 从交易历史提取成功/失败模式
  - 注入经验数据库
  ↓
[5] 进化决策
  - 参数调整 vs 接口重设计
  - 渐进式改进
```

---

## 五、数据流

### 5.1 数据源优先级

```
TqSdk（首选，实时行情）
  ↓ 失败
DuckDB 本地缓存（K 线/指标）
  ↓ 失败
通达信 MCP（备选）
  ↓ 失败
CSV（兜底）
```

### 5.2 健康检查机制

```python
# 扫描前自动执行
health = DataSourceFactory.check_health("tqsdk")
if health['available']:
    # 使用 TqSdk 兜底
else:
    # 仅使用本地缓存，跳过 TqSdk
```

### 5.3 TqSdk 超时机制

```
单品种超时: 20 秒（deadline=10s + 连接开销）
批量操作: 120 秒（固定）
行情批量: 分 10 个一批调用
K 线获取: ~16 秒/品种（含 deadline 等待）
```

---

## 六、配置文件

### 6.1 config/config.json

```json
{
  "scanner": {
    "symbols": ["RB", "I", "J", "JM", "CU", ...],
    "filter_mode": "or",
    "er_min": 0.6,
    "tsi_min": 20,
    "r2_min": 0.4
  },
  "llm": {
    "api_key": "...",
    "base_url": "...",
    "model": "..."
  }
}
```

### 6.2 数据库文件

| 文件 | 用途 |
|------|------|
| `data/market.db` | DuckDB：K 线/指标/行情 |
| `data/meta.db` | SQLite：品种元数据/同步状态 |
| `data/latest_scan.json` | 最新扫描结果 |
| `data/latest_reasoning.json` | 最新推理结果 |
| `data/latest_debate.json` | 最新辩论结果 |
| `data/factor_evaluation.json` | 因子评估结果 |
| `data/factor_evolution.json` | 因子进化结果 |
| `data/seed_factors.json` | 种子因子池 |
| `data/factor_experience.json` | 因子经验库 |
| `data/factor_knowledge.json` | 因子知识库 |

---

## 七、测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行 v5.0 因子进化测试
python -m pytest tests/test_factor_evaluator.py tests/test_factor_evolution.py tests/test_phase3_phase4.py tests/test_phase5_phase6.py -v

# 运行特定测试
python -m pytest tests/test_factor_evaluator.py -v
```

**测试状态**: 58 个 v5.0 测试全部通过

---

## 八、版本历史

| 版本 | 日期 | 关键变更 |
|------|------|---------|
| v5.0.0 | 2026-06-16 | 闭环迭代因子进化引擎，截面 IC/ICIR 评估，贝叶斯参数优化，多因子组合模型 |
| v3.2.2 | 2026-06-14 | 分歧度和条件层级记录 |
| v3.0.0 | 2026-06-14 | 推理优先架构重写 |
| v2.0.0 | 2026-06-01 | 自适应系统 |
| v1.0.0 | 2026-05-15 | 初始版本 |

---

## 九、论文基础

本系统的设计基于以下学术论文：

1. **Agentic AI for Factor Investing** (arXiv:2603.14288)
   - 闭环迭代因子发现引擎
   - 严格 IS/OOS 分离
   - 透明门控机制（三元决策）

2. **FactorEngine** (arXiv:2603.16365)
   - 程序级因子表示（因子即代码）
   - 三大分离：逻辑-参数分离、LLM-贝叶斯分离、LLM-本地分离
   - 知识注入引导模块（研报→因子）
   - 经验知识库 + 轨迹感知优化

3. **FinCon** (概念性语言反馈)
   - Agent 间用自然语言互相教学
   - 信念传播机制

4. **GIFT** (LLM 引导的 RL 接口设计)
   - LLM 设计状态空间和奖励函数
   - 诊断引导修正
