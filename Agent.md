---
title: "QuantNova Agent Definition"
summary: "推理重于规则的期货趋势跟踪决策辅助系统 Agent"
---

# Agent.md - QuantNova 交易决策 Agent

## 定位

QuantNova 是一个**推理重于规则**的期货趋势跟踪决策辅助系统。系统不自动下单，只输出决策简报供人参考。

**核心理念**：以人为本，推理为魂，规则为果。

## 能力矩阵

| 层级 | 能力 | 核心模块 |
|------|------|----------|
| **感知** | 35+技术指标 + 7维趋势强度 + 基本面分析 | IndicatorEngine + MultiDimensionScreener + NewsCrawler |
| **记忆** | 经验检索 + 向量增强 + 知识锚点 | UnifiedMemoryManager + MemoryBridge |
| **推理** | LLM推理 + 鹰鸽辩论 + 场景分析 + 信念传播 | ReasoningEngine + DebateEngine + ScenarioAnalyzer |
| **策略** | 趋势跟踪 + Carry套利 + 跨品种套利 + 风控 | TrendScanner + CarryAnalyzer + ArbitrageAnalyzer |
| **进化** | 自优化闭环 + 因子进化 + 过拟合审计 | EvolutionManager + FactorEvolutionEngine |
| **协调** | 事件驱动 + NLP交互 + 异步Workers | EventDrivenEngine + NLPChat |

## 工作机制

### 五层管线（主流程）

```
ContextAssembler → ExperienceMemory → ReasoningEngine → DebateEngine → BriefGenerator
```

1. **ContextAssembler**: 组装 MarketContext（技术面+基本面+宏观状态）
2. **ExperienceMemory**: 检索历史相似经验
3. **ReasoningEngine**: LLM 推理生成初始判断
4. **DebateEngine**: 鹰鸽辩论纠偏（Hawk激进 vs Dove保守 → 分歧评分 → 仓位调整）
5. **BriefGenerator**: 输出 TradingBrief（MarketAssessment + Routes + Uncertainty）

### 因子进化闭环

```
Generate → Validate → Execute → Evaluate → Gate → Memory → Feedback → 循环
```

### 自优化闭环

```
交易 → 记录 → 轨迹分析 → 故障归因 → LLM反思 → 规则优化 → 过拟合审计 → 晋升 → 经验存储 → 闭环
```

## 输出格式

系统输出为**交易决策简报**（TradingBrief），包含：

- **MarketAssessment**: 市场评估（趋势状态+基本面评分+关键驱动因素）
- **Routes**: 操作方案（方向+品种+仓位建议+止损参考）
- **Uncertainty**: 不确定性标注（置信度+分歧评分+数据时效性）

**注意**: 系统不输出 BUY/SELL/HOLD 硬信号，只输出决策简报供人参考。

## 交互方式

| 方式 | 入口 | 说明 |
|------|------|------|
| CLI | `tools/core/scan_opportunities.py` | 命令行扫描+分析 |
| NLP | `scripts/core/nlp/nlp_chat.py` | 自然语言交互 |
| Web | `scripts/core/main.py --web` | 可视化界面 |
| API | `scripts/core/main.py --api` | 系统集成接口 |
| 自动 | `scripts/core/main.py` | 事件驱动独立运行 |

## 快速参考

- **完整文档**: [README.md](README.md)
- **架构总览**: [docs/system_architecture_overview.md](docs/system_architecture_overview.md)
- **测试状态**: [docs/TESTING.md](docs/TESTING.md)
- **变更记录**: [docs/CHANGELOG.md](docs/CHANGELOG.md)
