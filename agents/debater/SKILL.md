---
name: debater
description: "期货趋势跟踪辩论 Agent —— 通过鹰派/鸽派辩论修正决策偏差"
version: "1.1.0"
author: "QuantNova"
created: "2026-06-15"
updated: "2026-06-15"
tags: ["trading", "futures", "debate", "agent"]
---

# Debater Agent（辩论器）

## 概述

Debater Agent 是 QuantNova 系统的偏差修正组件。它通过鹰派/鸽派双视角辩论，修正 Reasoner Agent 的初始方案，提升决策质量。

## 核心理念

参见 [共享架构文档 - 辩论修正](../shared/ARCHITECTURE.md#22-辩论修正)

**辩论 = 偏差修正**

参考论文：MacroEconomists (arXiv: 2606.08283)
- 辩论可以修正认知偏差
- Δ Sharpe = +0.044
- 分歧度 = 置信度

## 职责

1. **接收方案**：从 Reasoner Agent 接收初始交易方案
2. **鹰派分析**：从风险角度审视方案，提出反对意见
3. **鸽派分析**：从机会角度审视方案，提出支持意见
4. **辩论整合**：综合两方观点，修正方案
5. **输出修正方案**：输出修正后的方案 + 辩论记录

## 设计变更

**v2.0 设计**：单 Agent 内部 self-debate，不拆分为独立的鹰派/鸽派 Agent。

**理由**：
- 减少通信开销
- 节省 token 消耗（约 60%）
- 简化系统复杂度

## 输入格式

参见 [统一数据格式 - 交易决策简报](../shared/DATA_FORMATS.md#12-交易决策简报tradingbrief)

```json
{
  "symbol": "DCE.jm2609",
  "timestamp": "2026-06-15T10:30:05",
  "trend_phase": {
    "phase": "DEVELOPING",
    "label": "趋势发展",
    "confidence": 0.75
  },
  "routes": [
    {
      "route_id": "A",
      "name": "顺势做多",
      "action": "在回调至支撑位时入场做多",
      "confidence": 0.72,
      "reasoning": "趋势发展阶段，动量充足，均线支撑",
      "constraints": [
        {"type": "stop_loss", "value": 1320, "reason": "ATR 止损"},
        {"type": "position_size", "value": 0.3, "reason": "中等仓位"}
      ],
      "risks": ["RSI 接近超买", "波动率扩张"]
    }
  ],
  "recommended_route": "A",
  "warnings": []
}
```

## 输出格式

参见 [统一数据格式 - 辩论结果](../shared/DATA_FORMATS.md#13-辩论结果debateresult)

```json
{
  "symbol": "DCE.jm2609",
  "timestamp": "2026-06-15T10:30:10",
  "original_brief": { ... },
  "debate_result": {
    "hawk_arguments": [
      "RSI 接近超买区域，回调风险增大",
      "波动率扩张，可能预示趋势反转",
      "持仓量下降，多头动能减弱"
    ],
    "dove_arguments": [
      "趋势发展阶段，均线多头排列",
      "ER>0.6，趋势效率高",
      "成交量放大，趋势确认"
    ],
    "synthesis": "趋势整体健康，但短期存在回调风险",
    "divergence": 0.35,
    "condition_levels": [
      "如果 RSI 突破 70，建议减仓",
      "如果价格跌破 EMA20，建议止损"
    ]
  },
  "revised_brief": { ... },
  "revision_summary": "辩论修正：降低仓位（0.3→0.25），收紧止损（1320→1310）"
}
```

## 工作流程

```
接收 Reasoner 简报
  │
  ▼
检查触发条件
  │
  ├── 置信度 < 0.7 → 触发辩论
  ├── 持仓金额 > 阈值 → 触发辩论
  ├── 用户显式要求 → 触发辩论
  └── 否则 → 跳过辩论，直接输出
  │
  ▼
生成鹰派论点
  │
  ▼
生成鸽派论点
  │
  ▼
综合判断，修正方案
  │
  ▼
计算分歧度
  │
  ▼
输出修正方案 + 辩论记录
```

## 触发条件

- **置信度触发**：推荐路线置信度 < 0.7
- **金额触发**：持仓金额 > 阈值（可配置）
- **用户触发**：用户显式要求辩论

## 配置参数

参见 [统一数据格式 - 配置数据格式](../shared/DATA_FORMATS.md#三配置数据格式)

```json
{
  "debater": {
    "debate_trigger_confidence": 0.7,
    "debate_trigger_amount": 100000,
    "max_debate_rounds": 1,
    "hawk_weight": 0.5,
    "dove_weight": 0.5
  }
}
```

## 使用方式

参见 [共享章节 - 使用方式](../shared/COMMON_SECTIONS.md#一使用方式)

### 作为 WorkBuddy Agent

```python
from tools.debater import DebaterAgent

agent = DebaterAgent()
result = agent.debate(brief_data)
print(result)
```

### 作为独立脚本

```bash
# 辩论单个简报
python tools/debater.py --brief data/latest_brief.json

# 强制辩论（忽略触发条件）
python tools/debater.py --brief data/latest_brief.json --force

# 输出 JSON 格式
python tools/debater.py --brief data/latest_brief.json --output json

# 保存结果到文件
python tools/debater.py --brief data/latest_brief.json --save
```

## 依赖模块

参见 [依赖模块文档](../shared/DEPENDENCIES.md)

- `scripts/trend_scanner/debate_engine.py` - 辩论引擎
- `scripts/trend_scanner/reasoning.py` - LLM Provider
- `scripts/trend_scanner/models.py` - 数据模型

## 错误处理

参见 [共享章节 - 错误处理](../shared/COMMON_SECTIONS.md#二错误处理)

- **LLM 调用失败**：跳过辩论，输出原始简报
- **辩论超时**：跳过辩论，输出原始简报
- **解析失败**：跳过辩论，输出原始简报

## Token 预算

参见 [共享架构文档 - Token 预算](../shared/ARCHITECTURE.md#13-token-预算)

- 每次辩论消耗约 3000-6000 token
- 每日预算 200K token（约 30-60 次辩论）
- 达到预算 80% 时停止辩论

## 监控指标

- 辩论触发率
- 平均分歧度
- 修正幅度
- Token 消耗量
- 辩论后决策准确率
