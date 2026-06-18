---
name: orchestrator
description: "期货趋势跟踪主协调器 —— 接收用户指令，分发任务，汇总结果"
version: "1.1.0"
author: "QuantNova"
created: "2026-06-15"
updated: "2026-06-15"
tags: ["trading", "futures", "orchestrator", "agent"]
---

# Orchestrator Agent（主协调器）

## 概述

Orchestrator Agent 是 QuantNova 系统的主协调器。它接收用户自然语言指令，解析意图，分发任务给专业 Agent，汇总结果，生成最终输出。

## 核心理念

参见 [共享架构文档 - 整体架构](../shared/ARCHITECTURE.md#11-整体架构)

**协调一切，但不做具体工作。**

Orchestrator 是系统的"大脑"，负责：
- 接收用户指令
- 解析意图
- 分发任务
- 汇总结果
- 管理配置

## 职责

1. **用户指令解析**：解析自然语言指令，识别意图
2. **任务分发**：将任务分发给专业 Agent 或脚本
3. **结果汇总**：汇总各 Agent 的结果，生成最终输出
4. **配置管理**：维护配置和持仓数据
5. **生命周期管理**：管理 Agent Team 生命周期

## 输入格式

### 用户指令

```
帮我扫描一下黑色系
分析一下焦煤
我今天平了焦煤多头，赚了 3.5%
把 ER 阈值调到 0.5
现在持仓是什么情况
```

### Scanner 信号

参见 [统一数据格式 - 信号格式](../shared/DATA_FORMATS.md#11-信号格式signal)

### Monitor 预警

参见 [统一数据格式 - 预警格式](../shared/DATA_FORMATS.md#14-预警格式alert)

## 输出格式

### 扫描结果

```
[扫描结果]

扫描时间: 2026-06-15 10:30
扫描品种: 30 个
发现信号: 3 个

[STRONG] 信号:
  - SHFE.rb2510 (LONG) - 趋势发展阶段，ER>0.6，TSI>20
  - DCE.jm2609 (LONG) - 趋势确认，均线多头排列

[MEDIUM] 信号:
  - DCE.i2510 (LONG) - 趋势萌芽，等待确认

无信号: 27 个品种
```

### 分析结果

```
[分析报告] 焦煤 (DCE.jm2609)

趋势阶段: 趋势发展 (置信度: 75%)
当前价格: 1385
推荐方案: 顺势做多 (置信度: 72%)

操作建议:
  - 在回调至支撑位时入场做多
  - 止损: 1320 (ATR 止损)
  - 仓位: 30% (中等仓位)

风险提示:
  - RSI 接近超买
  - 波动率扩张

辩论修正: 无 (置信度足够高)
```

### 持仓概览

```
[持仓概览]

更新时间: 2026-06-15 15:30
持仓数量: 5 个

品种        方向    入场价    当前价    盈亏    持仓天数
------------------------------------------------------------
DCE.jm2609  LONG    1350      1385      +2.59%  3
CZCE.CF609  SHORT   15000     14800     +1.33%  5
DCE.cs2607  LONG    2800      2850      +1.79%  2
SHFE.ni2607 SHORT   120000    121000    -0.83%  1
DCE.y2609   SHORT   8500      8400      +1.18%  4

总盈亏: +1.21%
```

## 工作流程

```
接收事件
  │
  ├── 用户自然语言指令
  │     ├── 解析意图（扫描/分析/持仓/反馈/配置调整）
  │     ├── 分发给对应 Agent 或脚本
  │     └── 汇总结果，回复用户
  │
  ├── Scanner 脚本输出信号
  │     ├── 无信号 → 静默（不打扰用户）
  │     ├── 弱信号（1个，置信度<0.7）→ 记录，不触发 Reasoner
  │     ├── 中信号（1-3个，置信度0.7-0.85）→ 触发 Reasoner
  │     └── 强信号（>3个或置信度>0.85）→ 触发 Reasoner + Debater
  │
  ├── Monitor 脚本输出预警
  │     ├── LOW → 记录日志
  │     ├── MEDIUM → 推送通知给用户
  │     └── HIGH → 推送通知 + 触发 Reasoner 生成预警简报
  │
  └── 用户提交持仓反馈
        └── 更新 positions.json + 触发 Evolver Agent
```

## 意图识别

| 用户意图 | 示例表述 | 系统操作 |
|----------|----------|----------|
| 扫描 | "扫描黑色系"、"看看今天有什么机会" | 执行 Scanner 脚本 |
| 分析 | "分析焦煤"、"RB2501 怎么样" | 触发 Reasoner Agent |
| 持仓 | "持仓情况"、"我的仓位" | 读取 positions.json + Monitor |
| 反馈 | "平了焦煤，赚了3.5%" | 更新 positions.json + Evolver |
| 配置 | "把 ER 调到 0.5"、"扫描频率改成每天3次" | 更新 config.json |
| 进化 | "跑一下进化"、"反思一下最近的交易" | 触发 Evolver Agent |

## 配置参数

参见 [统一数据格式 - 配置数据格式](../shared/DATA_FORMATS.md#三配置数据格式)

```json
{
  "orchestrator": {
    "auto_scan": true,
    "auto_monitor": true,
    "notify_on_signal": true,
    "notify_on_alert": true,
    "silent_mode": false
  }
}
```

## 使用方式

参见 [共享章节 - 使用方式](../shared/COMMON_SECTIONS.md#一使用方式)

### 作为 WorkBuddy Agent

```python
from tools.orchestrator import OrchestratorAgent

agent = OrchestratorAgent()
result = agent.process_user_input("帮我扫描一下黑色系")
print(result)
```

### 作为独立脚本

```bash
# 处理用户指令
python tools/orchestrator.py --input "帮我扫描一下黑色系"

# 查看系统状态
python tools/orchestrator.py --status

# 执行扫描
python tools/orchestrator.py --scan
```

## 依赖模块

参见 [依赖模块文档](../shared/DEPENDENCIES.md)

- `tools/reasoner.py` - Reasoner Agent
- `tools/debater.py` - Debater Agent
- `tools/evolver.py` - Evolver Agent
- `tools/monitor_positions.py` - Monitor 脚本
- `scripts/trend_scanner/data_source.py` - 数据源

## 错误处理

参见 [共享章节 - 错误处理](../shared/COMMON_SECTIONS.md#二错误处理)

- **Agent 调用失败**：返回错误信息给用户
- **数据源不可用**：提示用户检查数据源配置
- **配置错误**：提示用户检查配置文件

## 监控指标

- 指令处理成功率
- 平均响应时间
- Agent 调用次数
- 用户满意度
