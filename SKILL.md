---
name: trend-scanner-agent
description: >
  推理重于规则的期货趋势跟踪 Agent v4.0。
  脚本+Agent 混合架构，动态因子生成，多角色协作，RL 接口自设计。
  数据源：TqSdk（首选）+ 通达信 MCP（备选）。
---

# 趋势跟踪 Agent

> 版本：v4.0.0 | 状态：开发中
> 核心思想来源：FactorEngine、FinCon、GIFT 三篇论文

## 定位

从 `trend-tracking-scanner` Skill 升级为 Agent，具备：

- **定时扫描**：每日自动扫描全品种，无需手动触发
- **智能推理**：只对有信号的品种触发 LLM 推理
- **持仓监控**：自动监控持仓风险，分级预警
- **经验进化**：从交易结果中学习，自动优化策略
- **动态因子**：LLM 引导生成可执行因子代码（FactorEngine）
- **多角色协作**：分析师/风控官/基本面研究员对抗辩论（FinCon）
- **RL 接口自设计**：LLM 设计状态空间和奖励函数（GIFT）

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
  │     ├── 分析师角色
  │     ├── 基本面研究员角色
  │     ├── 风控官角色
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

## 核心模块

| 模块 | 路径 | 版本 | 说明 |
|-----|------|------|------|
| 因子生成器 | `scripts/trend_scanner/factor_generator.py` | v1.0 | LLM 引导生成可执行因子代码 |
| LLM 客户端 | `scripts/trend_scanner/llm_factor_client.py` | v1.0 | 支持 OpenAI/Anthropic/本地/Mock |
| 因子验证器 | `scripts/trend_scanner/factor_validator.py` | v1.0 | 语法/结构/安全/性能验证 |
| 因子知识库 | `data/factor_knowledge.json` | v1.0 | 预置+动态因子存储 |
| 轨迹分析器 | `scripts/trend_scanner/trajectory_analyzer.py` | v1.0 | 失败模式识别/优化规则生成 |
| 研报解析器 | `scripts/trend_scanner/report_parser.py` | v1.0 | 观点提取/逻辑链/因子建议 |
| 概念反馈 | `scripts/trend_scanner/conceptual_feedback.py` | v1.0 | 自然语言反馈/信念管理 |
| 信念传播 | `scripts/trend_scanner/belief_propagation.py` | v1.0 | 信念更新/跨 Agent 传播 |
| RL 接口设计 | `scripts/trend_scanner/rl_interface_designer.py` | v1.0 | 状态空间/奖励函数/诊断修正 |

## 目录结构

```
E:\Trend-scanner-Agent\
├── SKILL.md                    # Agent 文档（本文件）
├── config/
│   ├── config.json             # 配置文件
│   └── positions.json          # 持仓数据
├── scripts/
│   └── trend_scanner/          # 核心计算包
│       ├── factor_generator.py     # Phase 1: 动态因子生成
│       ├── llm_factor_client.py    # Phase 1: LLM 客户端抽象层
│       ├── factor_validator.py     # Phase 1: 因子验证器
│       ├── trajectory_analyzer.py  # Phase 2: 轨迹感知优化器
│       ├── report_parser.py        # Phase 3: 研报知识注入
│       ├── conceptual_feedback.py  # Phase 4: 概念性语言反馈
│       ├── belief_propagation.py   # Phase 4: 信念传播
│       └── rl_interface_designer.py # Phase 5: RL 接口设计
├── tools/
│   ├── scan_opportunities.py   # Scanner 脚本
│   ├── scan_opportunities_v4.py # Scanner v4（集成动态因子）
│   └── monitor_positions.py    # Monitor 脚本
├── agents/
│   ├── orchestrator.md         # Orchestrator Agent
│   ├── reasoner.md             # Reasoner Agent
│   ├── debater.md              # Debater Agent（多角色）
│   └── evolver.md              # Evolver Agent v2.0（RL 集成）
├── tests/
│   ├── test_factor_generator.py    # Phase 1 测试
│   ├── test_trajectory_analyzer.py # Phase 2 测试
│   ├── test_report_parser.py       # Phase 3 测试
│   ├── test_multi_debater.py       # Phase 4 测试
│   ├── test_rl_interface.py        # Phase 5 测试
│   ├── integration/
│   │   └── test_full_pipeline.py   # Phase 6: 端到端集成测试
│   └── benchmark/
│       └── test_performance.py     # Phase 6: 性能基准测试
├── data/
│   └── factor_knowledge.json   # 因子知识库
├── docs/
│   ├── paper_analysis_improvements.md  # 论文分析报告
│   ├── implementation_plan.md          # 实施计划
│   └── CODE_STYLE.md                   # 代码规范
└── memory/                     # 记忆系统
```

## 配置

所有参数存放在 `config/config.json`，用户可在对话中动态调整：

- Scanner 品种列表和筛选阈值
- Monitor 监控频率和预警阈值
- Token 预算
- 数据保留策略

详见 `config/config.json`。

## 测试覆盖

| 测试文件 | 测试数量 | 状态 |
|---------|---------|------|
| test_factor_generator.py | 22 | 通过 |
| test_trajectory_analyzer.py | 11 | 通过 |
| test_report_parser.py | 16 | 通过 |
| test_multi_debater.py | 22 | 通过 |
| test_rl_interface.py | 15 | 通过 |
| test_full_pipeline.py（集成） | 22 | 通过 |
| test_performance.py（基准） | 8 | 通过 |
| **总计** | **116** | **全部通过** |

## 与 v1 Skill 的关系

- **共享模块**：`scripts/trend_scanner/` 是核心计算包，v1 和 v4 共用
- **v1 保留**：原 Skill 继续可用，作为回退方案
- **v4 增量**：新增动态因子/轨迹分析/研报注入/多角色/RL 接口五个模块

## 技术演进路线图

| 优先级 | 方向 | 当前状态 | 目标 | 实施要点 |
|-------|------|---------|------|---------|
| P0 | 动态因子生成 | ✅ 已完成 | LLM 生成因子代码 | FactorEngine 思想 |
| P0 | 轨迹感知优化 | ✅ 已完成 | 从交易历史提取模式 | 失败学习+规则生成 |
| P0 | 研报知识注入 | ✅ 已完成 | 研报→因子→验证→入库 | 多 Agent 提取 |
| P1 | 多角色 Debater | ✅ 已完成 | 分析师/风控/研究员对抗 | FinCon 思想 |
| P1 | RL 接口自设计 | ✅ 已完成 | LLM 设计状态/奖励 | GIFT 思想 |
| P2 | 集成测试 | ✅ 已完成 | 端到端+性能基准 | 116 测试全部通过 |
| P3 | TqSdk 集成 | 待实施 | 实时数据对接 | subprocess 隔离 |
| P3 | 部署脚本 | 待实施 | 自动化部署 | deploy_v4.sh |
