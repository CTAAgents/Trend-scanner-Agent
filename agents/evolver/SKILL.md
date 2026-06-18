---
name: evolver
description: "期货趋势跟踪进化 Agent —— 从交易结果中学习，优化策略"
version: "1.1.0"
author: "QuantNova"
created: "2026-06-15"
updated: "2026-06-15"
tags: ["trading", "futures", "evolution", "agent"]
---

# Evolver Agent（进化器）

## 概述

Evolver Agent 是 QuantNova 系统的自进化组件。它从交易结果中学习，分析交易轨迹，归因故障，检测模式，优化策略。

## 核心理念

参见 [共享架构文档 - 持续进化](../shared/ARCHITECTURE.md#23-持续进化)

**从错误中学习，从成功中提炼。**

进化流程：
```
交易反馈 → 轨迹分析 → 故障归因 → 策略反思 → 规则优化 → 过拟合审计
```

## 职责

1. **记录反馈**：记录用户决策和实际结果
2. **轨迹分析**：分析交易轨迹，识别关键节点
3. **故障归因**：归因交易失败的原因
4. **模式检测**：检测重复的交易模式
5. **规则优化**：从模式中提炼规则
6. **过拟合审计**：审计规则是否过拟合

## 输入格式

参见 [统一数据格式 - 交易反馈](../shared/DATA_FORMATS.md#15-交易反馈tradefeedback)

```json
{
  "symbol": "DCE.jm2609",
  "direction": "LONG",
  "entry_price": 1350,
  "exit_price": 1385,
  "entry_time": "2026-06-12T10:00:00",
  "exit_time": "2026-06-15T14:30:00",
  "pnl_pct": 2.59,
  "pnl_amount": 3500,
  "holding_days": 3,
  "exit_reason": "止盈",
  "brief_at_entry": { ... },
  "market_context_at_entry": { ... },
  "market_context_at_exit": { ... },
  "user_decision": "接受建议",
  "user_notes": "焦煤多头，安全检查限产"
}
```

## 输出格式

参见 [统一数据格式 - 进化报告](../shared/DATA_FORMATS.md#16-进化报告evolutionreport)

```json
{
  "symbol": "DCE.jm2609",
  "timestamp": "2026-06-15T15:00:00",
  "evolution_report": {
    "trajectory_analysis": {
      "entry_quality": "GOOD",
      "exit_quality": "GOOD",
      "holding_efficiency": 0.85,
      "key_events": [
        {"time": "2026-06-13T10:00:00", "event": "价格突破前高", "impact": "POSITIVE"},
        {"time": "2026-06-14T14:00:00", "event": "RSI 超买", "impact": "NEGATIVE"}
      ]
    },
    "fault_attribution": {
      "primary_fault": "NONE",
      "secondary_faults": [],
      "fault_severity": 0,
      "fault_description": "交易执行良好，无明显故障"
    },
    "pattern_detection": {
      "patterns_found": [
        {
          "pattern_id": "P001",
          "pattern_name": "安全检查限产行情",
          "pattern_type": "EVENT_DRIVEN",
          "occurrences": 3,
          "win_rate": 0.67,
          "avg_pnl": 2.1
        }
      ],
      "new_patterns": [],
      "pattern_confidence": 0.75
    },
    "rule_optimization": {
      "rules_proposed": [
        {
          "rule_id": "R001",
          "rule_name": "安全检查限产入场规则",
          "rule_content": "当安全检查限产消息出现时，在回调至支撑位时入场做多",
          "expected_improvement": 0.05,
          "confidence": 0.7
        }
      ],
      "rules_promoted": [],
      "rules_rejected": []
    },
    "overfitting_audit": {
      "overfitting_risk": "LOW",
      "audit_score": 0.85,
      "warnings": [],
      "recommendations": ["继续收集样本，提升规则置信度"]
    },
    "reflection": {
      "what_went_well": ["入场时机好", "止损设置合理"],
      "what_to_improve": ["可以更早止盈"],
      "lessons_learned": ["安全检查限产行情通常持续2-3天"]
    }
  },
  "experience_saved": true,
  "experience_id": "EXP_20260615_001"
}
```

## 工作流程

```
接收交易反馈
  │
  ▼
检查触发条件
  │
  ├── 每笔交易结束后 → 触发进化
  ├── 连续亏损 >= 3 次 → 触发进化
  ├── 累计亏损 >= 10% → 触发进化
  └── 每 20 笔交易 → 触发定期进化
  │
  ▼
轨迹分析
  │
  ▼
故障归因
  │
  ▼
模式检测
  │
  ▼
规则优化
  │
  ▼
过拟合审计
  │
  ▼
保存经验
  │
  ▼
输出进化报告
```

## 触发条件

- **交易结束**：每笔交易结束后（用户提交反馈）
- **连续亏损**：连续亏损 >= 3 次
- **累计亏损**：累计亏损 >= 10%
- **定期进化**：每 20 笔交易

## 配置参数

参见 [统一数据格式 - 配置数据格式](../shared/DATA_FORMATS.md#三配置数据格式)

```json
{
  "evolver": {
    "auto_trigger": {
      "consecutive_losses": 3,
      "cumulative_loss_pct": 10,
      "trade_count_interval": 20
    },
    "overfitting_threshold": 0.7,
    "min_samples_for_rule": 5,
    "rule_promotion_threshold": 0.6
  }
}
```

## 使用方式

参见 [共享章节 - 使用方式](../shared/COMMON_SECTIONS.md#一使用方式)

### 作为 WorkBuddy Agent

```python
from tools.evolver import EvolverAgent

agent = EvolverAgent()
result = agent.evolve(feedback_data)
print(result)
```

### 作为独立脚本

```bash
# 处理单个交易反馈
python tools/evolver.py --feedback data/trade_feedback.json

# 查看进化历史
python tools/evolver.py --history

# 执行定期进化
python tools/evolver.py --periodic

# 输出 JSON 格式
python tools/evolver.py --feedback data/trade_feedback.json --output json

# 保存结果到文件
python tools/evolver.py --feedback data/trade_feedback.json --save
```

## 依赖模块

参见 [依赖模块文档](../shared/DEPENDENCIES.md)

- `scripts/trend_scanner/evolution_manager.py` - 进化管理器
- `scripts/trend_scanner/experience.py` - 经验记忆池
- `scripts/trend_scanner/trajectory_analysis.py` - 轨迹分析
- `scripts/trend_scanner/trade_journal.py` - 交易日志
- `scripts/trend_scanner/overfitting_audit.py` - 过拟合审计

## 错误处理

参见 [共享章节 - 错误处理](../shared/COMMON_SECTIONS.md#二错误处理)

- **数据不足**：跳过轨迹分析，只记录经验
- **模式检测失败**：跳过模式检测，继续其他流程
- **规则优化失败**：跳过规则优化，继续其他流程

## 监控指标

- 进化触发率
- 平均故障严重度
- 模式检测准确率
- 规则晋升率
- 过拟合风险分布
