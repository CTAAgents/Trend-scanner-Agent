---
name: trend-scanner-agent
description: >
  推理重于规则的期货趋势跟踪 Agent。
  自动扫描、智能推理、持仓监控、经验进化。
  从 Skill 升级为 Agent，支持定时调度和自主运行。
  数据源：TqSdk（首选）+ 通达信 MCP（备选）。
---

# 趋势跟踪 Agent

> 版本：v2.0.0 | 状态：开发中

## 定位

从 `trend-tracking-scanner` Skill 升级为 Agent，具备：

- **定时扫描**：每日自动扫描全品种，无需手动触发
- **智能推理**：只对有信号的品种触发 LLM 推理
- **持仓监控**：自动监控持仓风险，分级预警
- **经验进化**：从交易结果中学习，自动优化策略

## 架构

```
Orchestrator Agent（主协调）
  ├── Scanner 脚本（纯 Python）→ 条件触发 Reasoner
  ├── Reasoner Agent（LLM 推理）→ 生成决策简报
  ├── Debater Agent（self-debate）→ 修正方案
  ├── Monitor 脚本（纯 Python）→ 条件触发预警
  └── Evolver Agent（LLM 反思）→ 优化策略
```

## 目录结构

```
E:\Trend-scanner-Agent\
├── SKILL.md                    # Agent 文档
├── config/
│   ├── config.json             # 配置文件（可动态调整）
│   └── positions.json          # 持仓数据
├── scripts/
│   └── trend_scanner/          # 核心包（符号链接到 v1）
├── tools/
│   ├── scan_opportunities.py   # Scanner 脚本
│   └── monitor_positions.py    # Monitor 脚本
├── agents/
│   ├── orchestrator.md         # Orchestrator Agent 定义
│   ├── reasoner.md             # Reasoner Agent 定义
│   ├── debater.md              # Debater Agent 定义
│   └── evolver.md              # Evolver Agent 定义
├── tests/                      # 测试文件
├── data/                       # 运行时数据
├── docs/
│   └── ARCHITECTURE.md         # 架构设计文档
└── memory/                     # 记忆系统
```

## 与 v1 Skill 的关系

- **共享模块**：`scripts/trend_scanner/` 是核心计算包，v1 和 v2 共用
- **v1 保留**：原 Skill 继续可用，作为回退方案
- **v2 增量**：Agent 层是新增的调度层，不影响 v1 代码

## 配置

所有参数存放在 `config/config.json`，用户可在对话中动态调整：

- Scanner 品种列表和筛选阈值
- Monitor 监控频率和预警阈值
- Token 预算
- 数据保留策略

详见 `config/config.json`。
