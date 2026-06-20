---
title: "QuantNova Agent Definition"
summary: "推理重于规则的量化交易决策辅助系统 Agent（简化版）"
---

# Agent.md - QuantNova 交易决策 Agent

## 定位

QuantNova 是一个**推理重于规则**的量化交易决策辅助系统，支持期货和证券双市场。系统不自动下单，只输出决策简报供人参考。

**核心理念**：以人为本，推理为魂，规则为果。

**核心原则**（必须遵守）：
1. **数据第一原则**：绝对禁止使用模拟数据，分析必须使用真实数据
2. **系统分析原则**：所有分析必须基于QuantNova系统开展
3. **推理重于规则**：规则动态生成，非硬编码
4. **辩论验证原则**：所有交易建议必须经过多方辩论才可以向用户提交
5. **自优化原则**：多空判断方法需要系统自优化

## 架构（简化后）

```
核心闭环：扫描 → 推理 → 辩论 → 风控
├── 期货子系统（TqSdk）
├── 证券子系统（通达信MCP）
├── 推理引擎 + 辩论引擎
├── 因子评估
├── 指标计算
├── 基本面分析
├── 风控模块
└── 记忆系统
```

**简化成果**：104个文件 / 41,973行代码

## 能力矩阵

| 模块 | 功能 |
|------|------|
| **indicators/** | 35+技术指标计算 |
| **reasoning/** | LLM推理 + 鹰鸽辩论 |
| **fundamental/** | 基本面分析（库存/仓单/宏观/研报） |
| **risk/** | 风控模块（止损/仓位/熔断） |
| **core/memory/** | 经验记忆系统 |
| **futures/** | 期货子系统（Provider+Strategy） |
| **securities/** | 证券子系统（Provider+Strategy） |

## 核心工作流

```
1. 数据获取（TqSdk/通达信MCP）
   ↓
2. 指标计算（EMA/RSI/MACD等）
   ↓
3. 信号生成（自优化参数）
   ↓
4. 辩论验证（鹰鸽对抗）
   ↓
5. 风控检查（止损/仓位）
   ↓
6. 输出决策简报
```

## 输出格式

系统输出为**交易决策简报**，包含：
- 市场评估
- 操作建议（方向+品种+仓位+止损）
- 风险提示
- 置信度

## 数据源

| 市场 | 首选 | 第二 |
|------|------|------|
| 期货 | TqSdk | 通达信MCP |
| 证券 | 通达信MCP | NeoData |
| 基本面 | AKShare | 通达信MCP |

## 快速参考

- **架构总览**: [docs/system_architecture_overview.md](docs/system_architecture_overview.md)
- **全景档案**: [docs/quantnova_system_overview.md](docs/quantnova_system_overview.md)
- **变更记录**: [docs/CHANGELOG.md](docs/CHANGELOG.md)
