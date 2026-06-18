# QuantNova 统一数据格式

> 版本：v1.0 | 创建日期：2026-06-15
> 所有 Agent 共享的数据格式规范

## 一、核心数据结构

### 1.1 信号格式（Signal）

**来源**：Scanner 脚本
**消费者**：Orchestrator → Reasoner Agent

```json
{
  "scan_time": "2026-06-15T10:30:00",
  "total_scanned": 30,
  "signals": [
    {
      "symbol": "SHFE.rb2510",
      "direction": "LONG",
      "trend_phase": "DEVELOPING",
      "trend_strength_composite": 0.72,
      "tsi": 25.3,
      "er": 0.65,
      "r_squared": 0.68,
      "signal_strength": "STRONG",
      "key_signals": ["ER>0.6", "TSI>20", "均线多头排列"],
      "risk_factors": ["RSI接近超买", "波动率扩张"],
      "trigger_reason": "ER>0.6 且 TSI>20 且 趋势发展阶段",
      "scan_id": "scan_20260615_103000"
    }
  ],
  "no_signal_symbols": ["DCE.i2510", "CZCE.CF509"]
}
```

### 1.2 交易决策简报（TradingBrief）

**来源**：Reasoner Agent
**消费者**：Debater Agent、用户

```json
{
  "symbol": "DCE.jm2609",
  "timestamp": "2026-06-15T10:30:05",
  "trend_phase": {
    "phase": "DEVELOPING",
    "label": "趋势发展",
    "confidence": 0.75
  },
  "assessment": {
    "summary": "焦煤处于趋势发展阶段，均线多头排列，动量充足",
    "signal_hint": "趋势确认，可考虑顺势入场"
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
    },
    {
      "route_id": "B",
      "name": "观望等待",
      "action": "等待更明确的信号或回调机会",
      "confidence": 0.28,
      "reasoning": "RSI 超买风险，等待回调",
      "constraints": [],
      "risks": ["可能错过趋势行情"]
    }
  ],
  "recommended_route": "A",
  "uncertainty": {
    "level": "MEDIUM",
    "factors": ["RSI 超买", "波动率扩张"]
  },
  "delivery_checklist": {
    "framework": "TqSdk / QuantNova v5.0",
    "market_hypothesis": "焦煤处于趋势发展阶段，均线多头排列，动量充足",
    "change_type": "new_entry",
    "change_description": "在回调至支撑位时入场做多，仓位30%",
    "validation_standard": "walk_forward",
    "falsification_condition": "如果价格跌破EMA20且ADX降至20以下，建议失效",
    "remaining_risks": ["夜盘跳空风险", "主力合约换月临近"]
  },
  "dimension_scores": {
    "trend": {"composite": 0.42, "direction": "BULLISH", "confidence": 0.72},
    "momentum": {"composite": 0.35, "direction": "BULLISH", "confidence": 0.65},
    "volume": {"composite": 0.28, "direction": "BULLISH", "confidence": 0.55},
    "volatility": {"composite": -0.10, "direction": "NEUTRAL", "confidence": 0.40},
    "channel": {"composite": 0.22, "direction": "BULLISH", "confidence": 0.60}
  },
  "warnings": [],
  "reasoning_model": "WorkBuddy Agent (default)",
  "experience_count": 3,
  "generation_time_ms": 1200
}
```

### 1.3 辩论结果（DebateResult）

**来源**：Debater Agent
**消费者**：用户、Evolver Agent

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

### 1.4 预警格式（Alert）

**来源**：Monitor 脚本
**消费者**：Orchestrator → Reasoner Agent

```json
{
  "monitor_time": "2026-06-15T10:30:00",
  "positions_monitored": 5,
  "alerts": [
    {
      "symbol": "DCE.jm2609",
      "type": "TREND_REVERSAL",
      "severity": "HIGH",
      "direction": "LONG",
      "entry_price": 1350,
      "current_price": 1320,
      "pnl_pct": -2.22,
      "indicators": {
        "tsi": -15.2,
        "tsi_prev_high": 28.5,
        "er": 0.35,
        "er_prev": 0.62
      },
      "trigger_reason": "TSI 顶背离 + ER 骤降"
    }
  ],
  "no_alert_positions": ["DCE.cs2607", "CZCE.CF609"]
}
```

### 1.5 交易反馈（TradeFeedback）

**来源**：用户
**消费者**：Evolver Agent

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

### 1.6 进化报告（EvolutionReport）

**来源**：Evolver Agent
**消费者**：用户、经验记忆池

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

### 1.7 多维度筛选结果（MultiDimensionResult）

**来源**：MultiDimensionScreener（Phase 2 新增）
**消费者**：Scanner → Reasoner Agent

```json
{
  "symbol": "DCE.jm",
  "timestamp": "2026-06-17T16:00:00",
  "overall_score": 0.234,
  "confidence": 0.58,
  "signal": "LONG",
  "dimensions": [
    {
      "name": "trend",
      "weight": 0.30,
      "composite": 0.42,
      "direction": "BULLISH",
      "confidence": 0.72,
      "top_indicators": {
        "adx": 0.75,
        "ma20_slope": 0.68,
        "spread_ma20_ma60": 0.55
      }
    },
    {
      "name": "momentum",
      "weight": 0.25,
      "composite": 0.35,
      "direction": "BULLISH",
      "confidence": 0.65,
      "top_indicators": {
        "macd": 0.62,
        "roc": 0.48,
        "rsi": 0.35
      }
    },
    {
      "name": "volume",
      "weight": 0.20,
      "composite": 0.28,
      "direction": "BULLISH",
      "confidence": 0.55,
      "top_indicators": {
        "obv": 0.70,
        "mfi": 0.35,
        "vr": 0.22
      }
    },
    {
      "name": "volatility",
      "weight": 0.15,
      "composite": -0.10,
      "direction": "NEUTRAL",
      "confidence": 0.40,
      "top_indicators": {
        "atr_ratio": -0.23,
        "bb_width": 0.10
      }
    },
    {
      "name": "channel",
      "weight": 0.10,
      "composite": 0.22,
      "direction": "BULLISH",
      "confidence": 0.60,
      "top_indicators": {
        "dc_upper": 0.45,
        "hcl_upper": 0.32
      }
    }
  ]
}
```

### 1.8 交付清单（delivery_checklist）

**来源**：Reasoner Agent（嵌入 TradingBrief 内）
**定义**：参见 [策略设计方法论 - 交付清单模板](STRATEGY_DESIGN_METHODOLOGY.md#五交付清单模板)

```json
{
  "delivery_checklist": {
    "framework": "TqSdk / QuantNova v5.0",
    "market_hypothesis": "焦煤处于趋势发展阶段，均线多头排列，动量充足",
    "change_type": "new_entry",
    "change_description": "在回调至支撑位时入场做多，仓位30%",
    "validation_standard": "walk_forward",
    "falsification_condition": "如果价格跌破EMA20且ADX降至20以下，建议失效",
    "remaining_risks": ["夜盘跳空风险", "主力合约换月临近"]
  }
}
```

**change_type 枚举**：见 [验证矩阵 - 改动类型](STRATEGY_DESIGN_METHODOLOGY.md#41-改动类型--最低验证标准)

**validation_standard 枚举**：`walk_forward` | `factor_evaluation` | `overfitting_audit`

## 二、持仓数据格式

### 2.1 positions.json

```json
{
  "updated_at": "2026-06-15T15:30:00",
  "positions": [
    {
      "symbol": "DCE.jm2609",
      "direction": "LONG",
      "entry_price": 1350,
      "current_price": 1385,
      "holding_days": 3,
      "pnl_pct": 2.59,
      "notes": "焦煤多头，关注安全检查限产"
    }
  ]
}
```

## 三、配置数据格式

### 3.1 config.json

```json
{
  "scanner": {
    "symbols": ["SHFE.rb", "SHFE.hc", "DCE.jm", "DCE.i", "CZCE.CF"],
    "schedule": ["09:15", "09:30", "10:30", "13:30", "14:30", "15:15"],
    "signal_filter": {
      "er_min": 0.6,
      "tsi_min": 20,
      "tsi_max": -20,
      "trend_strength_min": 0.5,
      "r2_min": 0.4
    }
  },
  "monitor": {
    "interval_minutes": 30,
    "alert_thresholds": {
      "LOW": {"trend_strength_drop": 0.15},
      "MEDIUM": {"trend_strength_drop": 0.25, "tsi_divergence": true},
      "HIGH": {"trend_strength_drop": 0.35, "er_below": 0.3}
    }
  },
  "reasoner": {
    "llm_type": "workbuddy_agent",
    "debate_trigger_confidence": 0.7,
    "max_tokens_per_day": 500000,
    "experience_top_k": 5,
    "experience_similarity_threshold": 0.6
  },
  "debater": {
    "debate_trigger_confidence": 0.7,
    "debate_trigger_amount": 100000,
    "max_debate_rounds": 1,
    "hawk_weight": 0.5,
    "dove_weight": 0.5
  },
  "evolver": {
    "auto_trigger": {
      "consecutive_losses": 3,
      "cumulative_loss_pct": 10,
      "trade_count_interval": 20
    },
    "overfitting_threshold": 0.7,
    "min_samples_for_rule": 5,
    "rule_promotion_threshold": 0.6
  },
  "orchestrator": {
    "auto_scan": true,
    "auto_monitor": true,
    "notify_on_signal": true,
    "notify_on_alert": true,
    "silent_mode": false
  },
  "token_budget": {
    "daily_limit": 850000,
    "warn_at_pct": 80,
    "stop_at_pct": 100
  }
}
```

## 四、枚举值定义

### 4.1 趋势阶段（TrendPhase）

| 值 | 中文 | 说明 |
|----|------|------|
| EMERGING | 趋势萌芽 | 趋势刚开始形成 |
| DEVELOPING | 趋势发展 | 趋势正在发展中 |
| MATURE | 趋势成熟 | 趋势已经成熟 |
| FATIGUING | 趋势衰竭 | 趋势开始衰竭 |
| REVERSING | 趋势反转 | 趋势正在反转 |
| CONSOLIDATING | 横盘整理 | 无明显趋势 |

### 4.2 信号强度（SignalStrength）

| 值 | 说明 |
|----|------|
| STRONG | 强信号（置信度 > 0.85） |
| MEDIUM | 中信号（置信度 0.7-0.85） |
| WEAK | 弱信号（置信度 < 0.7） |

### 4.3 预警级别（AlertSeverity）

| 值 | 说明 |
|----|------|
| HIGH | 高风险，需要立即处理 |
| MEDIUM | 中风险，需要关注 |
| LOW | 低风险，仅记录 |

### 4.4 方向（Direction）

| 值 | 说明 |
|----|------|
| LONG | 多头 |
| SHORT | 空头 |
| FLAT | 空仓 |

### 4.5 预警类型（AlertType）

| 值 | 说明 |
|----|------|
| TREND_REVERSAL | 趋势反转 |
| ER_DROP | 效率比骤降 |
| TREND_WEAK | 趋势减弱 |
| PROFIT_REVERSAL | 盈利回撤 |
| RSI_OVERBOUGHT | RSI 超买 |
| RSI_OVERSOLD | RSI 超卖 |
| MA_CROSS | 均线交叉 |
| VOLATILITY_HIGH | 波动率扩大 |
| ADX_WEAK | ADX 趋势减弱 |
