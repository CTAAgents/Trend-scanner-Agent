---
name: trend-scanner-agent
description: >
  推理重于规则的期货趋势跟踪 Agent v4.0。
  脚本+Agent 混合架构，动态因子生成，多角色协作，RL 接口自设计。
  数据源：TqSdk（首选）+ 通达信 MCP（备选）。
---

# Trend Scanner Agent

推理重于规则的期货趋势跟踪决策辅助系统 v4.0。

> 核心思想来源：FactorEngine、FinCon、GIFT 三篇论文

## 核心理念

**以人为本，推理为魂，规则为果。**

所有看似"规则"的内容（止损、仓位、入场条件）均由推理层根据当前市场状态动态生成，而非事先写死。系统不自动下单，只输出决策简报供人参考。

## 工作机制

### 整体架构（五层管线）

```
定时触发 (08:40 / 15:20 / 20:40)
    │
    ▼
┌─────────────────────────────────────────────┐
│  ① Scanner 脚本（纯 Python，无 LLM）         │
│  - TqSdk 拉取 17 个品种 120 日 K 线          │
│  - 计算 ER / TSI / R² / Hurst / RSI / ADX   │
│  - 复合趋势强度打分                           │
│  - 筛选条件过滤 → 有信号的品种才进入下一步     │
│  - 可选：加载动态因子（--use-dynamic-factors） │
│  输出 → data/latest_scan.json                │
└────────────────────┬────────────────────────┘
                     │ 有信号
                     ▼
┌─────────────────────────────────────────────┐
│  ② Reasoner Agent（LLM 推理）                │
│  - 接收信号 + 市场上下文 + 历史经验           │
│  - 生成交易决策简报：                         │
│    市场评估 → 操作方案 → 约束建议 → 置信度    │
│  - 置信度 < 0.7 时触发 Debater               │
│  输出 → data/latest_reasoning.json           │
└────────────────────┬────────────────────────┘
                     │ 置信度不足
                     ▼
┌─────────────────────────────────────────────┐
│  ③ Debater Agent（多角色协作，FinCon 思想）   │
│  四个角色独立分析后汇总辩论：                  │
│  - 分析师：技术面（趋势/动量/形态）           │
│  - 风控官：风险收益比/止损/仓位               │
│  - 基本面研究员：供需/政策/产业链              │
│  - 协调者：汇总分歧，修正方案                 │
│  角色间通过「概念性语言反馈」互相教学          │
│  输出 → data/latest_debate.json              │
└────────────────────┬────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  ④ Monitor 脚本（纯 Python，每 30 分钟）      │
│  - 读取持仓数据 config/positions.json         │
│  - 监控趋势强度下降 / ER 骤降 / RSI 超买     │
│  - 分级预警：HIGH / MEDIUM / LOW             │
│  输出 → data/latest_monitor.json             │
└────────────────────┬────────────────────────┘
                     │ 交易结束后
                     ▼
┌─────────────────────────────────────────────┐
│  ⑤ Evolver Agent（LLM 引导的 RL，GIFT 思想） │
│  - 轨迹分析：从交易历史提取成功/失败模式      │
│  - 失败学习：生成「避免规则」                 │
│  - RL 接口设计：LLM 设计状态空间和奖励函数    │
│  - 诊断修正：基于回滚诊断优化策略参数          │
│  - 信念更新：将学习成果写入投资信念库          │
└─────────────────────────────────────────────┘
```

### 数据流

| 阶段 | 输入 | 处理 | 输出 |
|------|------|------|------|
| Scanner | TqSdk K 线数据 | 指标计算 + 因子筛选 | `data/latest_scan.json` |
| Reasoner | 信号 + 经验库 | LLM 推理 | `data/latest_reasoning.json` |
| Debater | 决策简报 | 四角色辩论 | `data/latest_debate.json` |
| Monitor | 持仓数据 | 风险监控 | `data/latest_monitor.json` |
| Evolver | 交易结果 | 轨迹分析 + RL 优化 | 进化报告 |

### 设计原则

**1. 推理重于规则** — 所有"规则"由推理层动态生成，不存在独立的规则层

**2. 计算用脚本，推理用 Agent** — Scanner/Monitor 是纯 Python 脚本（不调用 LLM），Reasoner/Debater/Evolver 是 LLM Agent

**3. 因子即代码（FactorEngine）** — 因子不是固定公式，而是 LLM 生成的可执行 Python 代码

**4. 概念性语言反馈（FinCon）** — Agent 间用自然语言反馈互相教学，而非数值奖励

**5. RL 接口自设计（GIFT）** — LLM 设计状态空间和奖励函数，选定后固定，测试时不再查询 LLM

## 架构

```
Orchestrator Agent（主协调）
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
  └── Evolver Agent（LLM 引导的 RL）  ← GIFT
        ├── 轨迹感知优化器
        ├── 状态空间设计
        ├── 奖励函数设计
        └── 诊断引导修正
```

## 特性

- **动态因子生成**：LLM 引导生成可执行因子代码，因子即代码（FactorEngine）
- **轨迹感知优化**：从交易历史中提取成功/失败模式，生成优化规则
- **研报知识注入**：研报 → 多 Agent 提取 → 验证 → 可执行因子程序
- **多角色协作**：分析师/风控官/基本面研究员对抗辩论（FinCon）
- **RL 接口自设计**：LLM 设计状态空间和奖励函数（GIFT）
- **概念性语言反馈**：Agent 间用自然语言反馈相互"教学"
- **心跳监控**：每 5 分钟检查市场状态变化，只在有信号时触发推理
- **Token 预算**：每日 850K token 预算，三级降级策略
- **健康检查**：数据源自动降级（TqSdk → 通达信 MCP）

## 核心模块

| 模块 | 路径 | 说明 |
|-----|------|------|
| 因子生成器 | `scripts/trend_scanner/factor_generator.py` | LLM 引导生成可执行因子代码 |
| LLM 客户端 | `scripts/trend_scanner/llm_factor_client.py` | 支持 OpenAI/Anthropic/本地/Mock |
| 因子验证器 | `scripts/trend_scanner/factor_validator.py` | 语法/结构/安全/性能验证 |
| 因子知识库 | `data/factor_knowledge.json` | 预置+动态因子存储 |
| 轨迹分析器 | `scripts/trend_scanner/trajectory_analyzer.py` | 失败模式识别/优化规则生成 |
| 研报解析器 | `scripts/trend_scanner/report_parser.py` | 观点提取/逻辑链/因子建议 |
| 概念反馈 | `scripts/trend_scanner/conceptual_feedback.py` | 自然语言反馈/信念管理 |
| 信念传播 | `scripts/trend_scanner/belief_propagation.py` | 信念更新/跨 Agent 传播 |
| RL 接口设计 | `scripts/trend_scanner/rl_interface_designer.py` | 状态空间/奖励函数/诊断修正 |

## 技术指标

7 维趋势强度指标：

| 指标 | 权重 | 说明 |
|------|------|------|
| TSI | 25% | 趋势强度指数 |
| ER | 25% | 效率比 |
| EMA 斜率 | 15% | 均线斜率强度 |
| ATR 比率 | 10% | 波动率比率 |
| R² | 10% | 拟合度 |
| Hurst | 8% | 赫斯特指数 |
| ADX ROC | 7% | ADX 变化率 |

## 信号筛选

只有同时满足以下条件的品种才会触发 LLM 推理：

| 指标 | 多头阈值 | 空头阈值 | 含义 |
|------|----------|----------|------|
| ER（效率比率） | ≥ 0.6 | ≥ 0.6 | 趋势有效性 |
| TSI（趋势强度） | ≥ 20 | ≤ -20 | 动量方向和强度 |
| 趋势强度复合 | ≥ 0.5 | ≥ 0.5 | 综合趋势评分 |
| R²（拟合度） | ≥ 0.4 | ≥ 0.4 | 趋势线性程度 |

## 目录结构

```
Trend-scanner-Agent/
├── SKILL.md                    # 项目文档（本文件）
├── config/
│   ├── config.json             # 统一配置
│   └── positions.json          # 持仓数据
├── scripts/trend_scanner/      # 核心计算包
│   ├── factor_generator.py     # 动态因子生成
│   ├── llm_factor_client.py    # LLM 客户端抽象层
│   ├── factor_validator.py     # 因子验证器
│   ├── trajectory_analyzer.py  # 轨迹感知优化器
│   ├── report_parser.py        # 研报知识注入
│   ├── conceptual_feedback.py  # 概念性语言反馈
│   ├── belief_propagation.py   # 信念传播
│   └── rl_interface_designer.py # RL 接口设计
├── tools/
│   ├── scan_opportunities.py   # Scanner（支持 --use-dynamic-factors）
│   ├── monitor_positions.py    # Monitor 持仓风险监控
│   ├── heartbeat.py            # 心跳监控
│   ├── orchestrator.py         # Orchestrator 调度
│   ├── deploy_v4.sh            # v4.0 部署脚本
│   └── data_formats.py         # 运行时数据格式定义
├── agents/
│   ├── orchestrator.md         # Orchestrator Agent
│   ├── reasoner.md             # Reasoner Agent
│   ├── debater.md              # Debater Agent v2.0（多角色协作）
│   ├── analyst_role.md         # 分析师角色定义
│   ├── risk_officer_role.md    # 风控官角色定义
│   └── evolver.md              # Evolver Agent v2.0（RL 集成）
├── tests/
│   ├── test_factor_generator.py
│   ├── test_trajectory_analyzer.py
│   ├── test_report_parser.py
│   ├── test_multi_debater.py
│   ├── test_rl_interface.py
│   ├── test_e2e_pipeline.py
│   ├── integration/test_full_pipeline.py
│   └── benchmark/test_performance.py
├── data/
│   ├── factor_knowledge.json   # 因子知识库
│   ├── latest_scan.json        # 最新扫描结果
│   ├── latest_reasoning.json   # 最新推理结果
│   ├── latest_debate.json      # 最新辩论结果
│   └── latest_monitor.json     # 最新监控结果
└── docs/
    ├── paper_analysis_improvements.md
    ├── implementation_plan.md
    └── CODE_STYLE.md
```

## 快速开始

### 环境要求

- Python 3.12+
- TqSdk（期货数据源，需配置 TQ_USER / TQ_PASSWORD 环境变量）
- WorkBuddy（Agent 调度平台）

### 安装

```bash
git clone https://github.com/CTAAgents/Trend-scanner-Agent.git
cd Trend-scanner-Agent
pip install -r requirements.txt
```

### 配置

编辑 `config/config.json`，设置品种列表和筛选阈值：

```json
{
  "scanner": {
    "symbols": ["SHFE.rb", "DCE.jm", "INE.sc"],
    "signal_filter": {
      "er_min": 0.6,
      "tsi_min": 20,
      "trend_strength_min": 0.5
    }
  }
}
```

### 提交持仓

```bash
python tools/positions_manager.py add --symbol DCE.jm2609 --direction LONG --price 1350
```

### 运行扫描

```bash
python tools/scan_opportunities.py --output text --save
# 启用动态因子
python tools/scan_opportunities.py --output text --save --use-dynamic-factors
```

### 完整流程

```bash
python tools/orchestrator.py full
```

## 调度

### 定时扫描

| 时间 | 任务 | 说明 |
|------|------|------|
| 08:40 | 盘前准备 | 全品种扫描 + 输出结果 |
| 15:20 | 日盘收盘 | 全品种扫描 + 输出总结 |
| 20:40 | 夜盘开盘 | 全品种扫描 + 输出结果 |

### 心跳监控

- 频率：每 5 分钟
- 时段：09:00-11:30, 13:30-15:00, 21:00-23:00
- 功能：检测持仓预警和新信号

## Token 预算

每日预算：850,000 token

| 使用率 | 动作 |
|--------|------|
| < 80% | 正常运行 |
| 80-90% | 停止 Debater Agent |
| 90-100% | 只保留 Scanner 脚本 |
| >= 100% | 停止所有 Agent |

## 数据源

- **首选**：TqSdk（期货实时行情、主力合约）
- **备选**：通达信 MCP（A股/港股/美股/期货）
- **兜底**：本地 CSV

## 常用命令

```bash
# 健康检查
python tools/health_check.py check
python tools/health_check.py report

# 扫描
python tools/scan_opportunities.py --output text --save

# 心跳
python tools/heartbeat.py --output text

# 持仓管理
python tools/positions_manager.py list
python tools/positions_manager.py add --symbol DCE.jm2609 --direction LONG --price 1350

# 推理
python tools/run_reasoner.py --symbol SHFE.rb --output text

# 辩论
python tools/run_debater.py --output text --save

# 进化
python tools/run_evolver.py status
python tools/run_evolver.py feedback --symbol DCE.jm2609 --result profit --pnl 3.5

# Token 预算
python tools/token_budget.py status

# 完整流程
python tools/orchestrator.py full

# 部署验证
./tools/deploy_v4.sh
./tools/deploy_v4.sh --dry-run
```

## 测试覆盖

| 测试文件 | 测试数量 | 状态 |
|---------|---------|------|
| test_factor_generator.py | 22 | 通过 |
| test_trajectory_analyzer.py | 11 | 通过 |
| test_report_parser.py | 16 | 通过 |
| test_multi_debater.py | 22 | 通过 |
| test_rl_interface.py | 15 | 通过 |
| test_e2e_pipeline.py（端到端） | 14 | 通过 |
| test_full_pipeline.py（集成） | 22 | 通过 |
| test_performance.py（基准） | 20 | 通过 |
| test_memory_system.py（记忆） | 12 | 通过 |
| **总计** | **154** | **全部通过** |

## 技术演进

基于三篇论文的核心思想：

| 论文 | 核心思想 | 对应模块 |
|-----|---------|---------|
| FactorEngine (2603.16365) | 因子即代码、知识注入 | Phase 1/3 |
| FinCon (2407.06567) | 概念性语言反馈、多角色协作 | Phase 4 |
| GIFT (2606.08450) | LLM 引导的 RL 接口设计 | Phase 5 |

### 实施状态

| 方向 | 状态 | 说明 |
|------|------|------|
| 动态因子生成 | ✅ | LLM 生成因子代码 |
| 轨迹感知优化 | ✅ | 从交易历史提取模式 |
| 研报知识注入 | ✅ | 研报→因子→验证→入库 |
| 多角色 Debater | ✅ | 分析师/风控/研究员对抗 |
| RL 接口自设计 | ✅ | LLM 设计状态/奖励 |
| 集成测试 | ✅ | 154 测试全部通过 |
| 部署脚本 | ✅ | deploy_v4.sh |
| 真实 LLM 集成 | 待实施 | 当前使用 Mock/规则模式 |

## 与 v1 Skill 的关系

- **共享模块**：`scripts/trend_scanner/` 是核心计算包，v1 和 v4 共用
- **v1 保留**：原 Skill 继续可用，作为回退方案
- **v4 增量**：新增动态因子/轨迹分析/研报注入/多角色/RL 接口五个模块

## 文档

- [论文分析报告](docs/paper_analysis_improvements.md) — FactorEngine/FinCon/GIFT 深度分析
- [实施计划](docs/implementation_plan.md) — Phase 1-6 详细计划与进度
- [代码规范](docs/CODE_STYLE.md) — 编码行为准则 v1.3

## 许可证

MIT License
