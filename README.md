---
name: trend-scanner-agent
description: >
  推理重于规则的期货趋势跟踪决策辅助系统。
  统一数据路由 + 知识锚点 + 分级输出 + 套利分析 + LLM推理 + 闭环因子进化，
  数据源：TqSdk + Pytdx + AkShare + 本地数据库缓存。
  独立策略模块：Carry 策略（期限结构套利）。
---

# Trend Scanner Agent

> 推理重于规则的期货趋势跟踪决策辅助系统

**新用户请查看 [用户手册](docs/USER_GUIDE.md)** | **版本历史见 [CHANGELOG](docs/CHANGELOG.md)**

## 一句话概括

TqSdk 拉取数据写入本地 DuckDB，纯 Python 做计算，LLM 做推理，每日自动扫描 86 个主力合约（筛选非僵尸品种），输出交易决策简报附带仓位建议和止损价位。

## 核心理念

**以人为本，推理为魂，规则为果。**

所有看似"规则"的内容（止损、仓位、入场条件）均由推理层根据当前市场状态动态生成，而非事先写死。系统不自动下单，只输出决策简报供人参考。

---

## 快速开始

```bash
git clone https://github.com/CTAAgents/Trend-scanner-Agent.git
cd Trend-scanner-Agent
pip install -r requirements.txt

# 数据同步（首次使用必须执行）
python tools/sync_data.py sync --days 120

# 运行扫描
python tools/scan_opportunities.py --output text --save

# Reasoner深度分析（推荐）
python tools/scan_opportunities.py --reasoner --output text --save

# 持仓健康度评估
python tools/scan_opportunities.py --position-health

# 因子进化
python tools/scan_opportunities.py --evolve --evolve-rounds 5
```

---

## 系统架构

![系统架构](docs/architecture_diagram_v2.svg)

### 分层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 10 - 主协调层 (Orchestrator)                                   │
│   TradingAssistant - 系统主入口                                       │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 9 - 分析工具层 (Analytics)                                     │
│   PositionSizer + StopLoss + RiskManager + Backtester               │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 8 - 推理层 (Reasoning)                                         │
│   ReasoningEngine(LLM推理) + DebateEngine(多角色辩论)               │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 7 - 因子进化层 (Factor Evolution)                              │
│   FactorGenerator → FactorEvaluator → FactorEvolutionEngine         │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 6 - 策略层 (Strategy)                                          │
│   TrendScanner + RiskManager + ExecutionEngine                      │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 5 - 进化层 (Evolution)                                         │
│   EvolutionManager + TrajectoryAnalyzer + TradeJournal              │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 4 - 记忆层 (Memory)                                            │
│   UnifiedMemoryManager + MemoryBridge + ExperienceMemory            │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 3 - 感知层 (Perception)                                        │
│   IndicatorEngine(35+) + ContextAssembler + MacroStateDetector      │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 2 - 存储层 (Storage)                                           │
│   DuckDBStore + SQLiteStore + DataSyncManager                       │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 1 - 数据源层 (Data Sources)                                    │
│   TqSdk(首选) + Pytdx(备选) + AkShare + CSV(兜底)                   │
├─────────────────────────────────────────────────────────────────────┤
│ 基本面分析层 (Fundamental Analysis) - 新增                           │
│   NewsCrawler + SupplyDemandProvider + GeopoliticalTracker           │
└─────────────────────────────────────────────────────────────────────┘
```

### 独立策略模块

```
scripts/strategies/
├── __init__.py           # 策略模块导出
└── carry/                # Carry 策略（期限结构套利）
    ├── __init__.py
    └── carry_analyzer.py
```

**Carry 策略**：赚取期货曲线形态（Contango/Backwardation）带来的展期收益，与趋势跟踪策略并行运行。

### 设计原则

| 原则 | 含义 |
|------|------|
| 推理重于规则 | 所有"规则"由推理层动态生成 |
| 计算用脚本，推理用 Agent | 确定性计算不调 LLM |
| 数据本地化 | TqSdk 数据写入本地 DuckDB |
| 因子即代码 | 因子是 LLM 生成的可执行代码 |
| 门控不可调 | 门控阈值预设，防 p-hacking |

### 层级关系图

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 10: 主协调层 (Orchestrator)                              │
│                              TradingAssistant - 系统主入口                                 │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          ↓ 调用
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 9: RL 强化学习层 (RL)                                    │
│                    AgentPPO + FuturesTradingEnv + RLSignalGenerator                      │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          ↓ 信号
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 8: 推理层 (Reasoning)                                   │
│              ReasoningEngine + DebateEngine + ScenarioAnalyzer + BriefGenerator         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          ↓ 推理结果
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 7: 因子进化层 (Factor Evolution)                        │
│     FactorGenerator → FactorEvaluator → FactorGate → FactorEvolutionEngine              │
│                              ↓ 验证后的因子 ↓ 经验反馈                                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
          ↑ 因子有效性验证                              ↑ 策略调整建议
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 6: 策略层 (Strategy)                                    │
│              TrendScanner + RiskManager + ExecutionEngine + PortfolioManager            │
└─────────────────────────────────────────────────────────────────────────────────────────┘
          ↑ 策略表现反馈                              ↓ 交易记录
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 5: 进化工具层 (Evolution Tools)                         │
│          EvolutionManager + TrajectoryAnalyzer + TradeJournal + CircuitBreaker         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
          ↑ 经验教训                                ↓ 策略调整
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 4: 记忆层 (Memory)                                      │
│         UnifiedMemoryManager + MemoryBridge + ExperienceMemory + KnowledgeAnchors      │
└─────────────────────────────────────────────────────────────────────────────────────────┘
          ↑ 历史经验                                ↓ 技术指标
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 3: 感知层 (Perception)                                  │
│              IndicatorEngine(80+) + ContextAssembler + MacroStateDetector               │
└─────────────────────────────────────────────────────────────────────────────────────────┘
          ↑ 指标数据                                ↓ K线数据
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 2: 存储层 (Storage)                                     │
│              DuckDBStore + SQLiteStore + DataSyncManager + DataValidator                │
└─────────────────────────────────────────────────────────────────────────────────────────┘
          ↑ 数据存储                                ↓ 原始数据
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            Layer 1: 数据源层 (Data Sources)                              │
│              TqSdk(首选) + Pytdx(备选) + AkShare + CSV(兜底)                            │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 数据流方向

| 数据流 | 方向 | 说明 |
|--------|------|------|
| **数据层 → 存储层** | ↑ | 原始行情数据写入 DuckDB |
| **存储层 → 感知层** | ↑ | K线数据供指标计算 |
| **感知层 → 记忆层** | ↑ | 技术指标存入记忆 |
| **记忆层 → 进化层** | ↑ | 历史经验供策略学习 |
| **进化层 → 策略层** | ↑ | 验证后的因子供策略使用 |
| **策略层 → 推理层** | ↑ | 策略信号供推理分析 |
| **推理层 → RL层** | ↑ | 推理结果供RL决策 |
| **RL层 → 主协调层** | ↑ | 最终信号供系统协调 |
| **主协调层 → 各层** | ↓ | 系统主入口调用各层 |
| **策略层 ↔ 进化层** | ↔ | 策略表现反馈，因子有效性验证 |
| **进化层 ↔ 记忆层** | ↔ | 经验教训存储，历史经验查询 |

---

## CLI 使用手册

### 主入口：scan_opportunities.py

```bash
python tools/scan_opportunities.py [选项]
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `--symbols` | 指定品种 | `--symbols RB,I,JM` |
| `--output` | 输出格式 | `--output text` |
| `--reasoner` | Reasoner深度分析 | `--reasoner` |
| `--use-rl` | 启用 RL 信号 | `--use-rl` |
| `--evaluate-factors` | 因子评估 | `--evaluate-factors` |
| `--evolve` | 因子进化 | `--evolve --evolve-rounds 5` |
| `--position-health` | 持仓健康度 | `--position-health` |
| `--arbitrage` | 套利分析 | `--arbitrage` |
| `--health-check` | 策略健康度 | `--health-check` |

### 常用命令

```bash
# 日常扫描
python tools/scan_opportunities.py --output text --save

# Reasoner深度分析（推荐）
python tools/scan_opportunities.py --reasoner --output text --save

# 指定品种 + Reasoner
python tools/scan_opportunities.py --symbols RB,I,JM --reasoner --output text

# 使用 RL 信号扫描（需要先训练模型）
python tools/scan_opportunities.py --use-rl

# 因子进化
python tools/scan_opportunities.py --evolve --evolve-rounds 5

# 套利分析
python tools/scan_opportunities.py --arbitrage --output text

# 持仓健康度
python tools/scan_opportunities.py --position-health
```

### RL 策略训练

```bash
# 训练 PPO 策略
python tools/train_ppo.py --symbol RB --days 200 --train-steps 10000

# 多品种并行训练
python tools/train_ppo.py --symbol I,J,JM --multi-asset

# Walk-Forward 验证
python tools/train_ppo.py --symbol RB --walk-forward

# 超参调优
python tools/tune_rl_hyperparams.py --symbol RB --trials 20
```

### 数据同步

```bash
python tools/sync_data.py sync --days 120 --min-oi 10000
python tools/sync_data.py stats
```

---

## 工作流

### 日常扫描

```
数据同步 → 全品种扫描 → 信号筛选 → Reasoner推理 → 决策简报
```

### 因子进化

```
种子因子 → 生成候选 → 执行计算 → IC/ICIR评估 → 门控决策 → 经验记忆
```

---

## 配置文件

| 文件 | 用途 |
|------|------|
| `config/config.json` | 主配置（品种/筛选条件/数据路由） |
| `config/positions.json` | 持仓配置 |
| `data/market.db` | DuckDB：K线/指标/因子库 |
| `data/meta.db` | SQLite：品种元数据/经验/日志 |

---

## 测试

```bash
python -m pytest tests/ -v
```

**测试状态**: 544+ 个测试全部通过

---

## 论文基础

1. **Agentic AI for Factor Investing** (arXiv:2603.14288) — 闭环迭代因子发现引擎
2. **FactorEngine** (arXiv:2603.16365) — 因子即代码，三大分离
3. **FinCon** — 概念性语言反馈，信念传播机制
4. **GIFT** — LLM 引导的 RL 接口设计

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [用户手册](docs/USER_GUIDE.md) | 安装、配置、使用指南 |
| [系统架构](docs/system_architecture_overview.md) | 详细架构设计 |
| [版本管理规范](docs/VERSION_MANAGEMENT.md) | 版本号管理原则 |
| [版本历史](docs/CHANGELOG.md) | 完整变更记录 |
| [编码规范](docs/CODE_STYLE.md) | 代码风格指南 |
| [测试文档](docs/TESTING.md) | 测试覆盖与运行 |
