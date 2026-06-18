# QuantNova 共享架构文档

> 版本：v1.0 | 创建日期：2026-06-15
> 所有 Agent 共享的架构规范和核心理念

## 一、系统架构

### 1.1 整体架构

```
用户
 │
 ▼
Orchestrator Agent（主协调，轻量）
 │
 ├──→ Scanner 脚本（纯 Python，无 LLM）
 │      ├── 扫描全品种，计算指标
 │      ├── 筛选出有信号的品种
 │      └── 只对有信号的品种触发 Reasoner Agent
 │
 ├──→ Reasoner Agent（LLM 推理）
 │      ├── 接收有信号的品种
 │      ├── 生成交易决策简报
 │      └── 必要时触发 Debater Agent
 │
 ├──→ Debater Agent（单 Agent 内部 self-debate）
 │      ├── 鹰派/鸽派论点生成
 │      ├── 多轮辩论（LLM 内部完成）
 │      └── 输出修正方案
 │
 ├──→ Monitor 脚本（纯 Python，无 LLM）
 │      ├── 监控持仓品种价格/指标
 │      ├── 检测止损/止盈/反转信号
 │      └── 触发预警时调用 Reasoner Agent
 │
 └──→ Evolver Agent（LLM 反思）
        ├── 记录交易反馈
        ├── 归因故障
        └── 优化策略
```

### 1.2 核心设计原则

**计算用脚本，推理用 Agent。避免用 LLM 做纯计算浪费 token。**

| 组件 | 类型 | Token 消耗 | 说明 |
|------|------|-----------|------|
| Scanner | 脚本 | 0 | 纯 Python 计算 |
| Monitor | 脚本 | 0 | 纯 Python 计算 |
| Reasoner | Agent | 2000-5000 | LLM 推理 |
| Debater | Agent | 3000-6000 | LLM 辩论 |
| Evolver | Agent | 2000-4000 | LLM 反思 |
| Orchestrator | Agent | 500-1000 | 任务分发 |

### 1.3 Token 预算

| 组件 | 每日预算 | 说明 |
|------|---------|------|
| Reasoner Agent | 500K token | 约 100-250 次推理 |
| Debater Agent | 200K token | 约 30-60 次辩论 |
| Evolver Agent | 100K token | 约 25-50 次进化 |
| Orchestrator | 50K token | 任务分发和汇总 |
| **合计** | **850K token/天** | |

## 二、核心理念

### 2.1 推理优先

**推理是一切的上游，规则只是推理的临时产物。**

所有约束（止损、仓位、入场条件）均由推理层根据当前市场状态和历史经验实时推导，而非事先写死。

### 2.2 辩论修正

**辩论 = 偏差修正**

参考论文：MacroEconomists (arXiv: 2606.08283)
- 辩论可以修正认知偏差
- Δ Sharpe = +0.044
- 分歧度 = 置信度

### 2.3 持续进化

**从错误中学习，从成功中提炼。**

进化流程：
```
交易反馈 → 轨迹分析 → 故障归因 → 策略反思 → 规则优化 → 过拟合审计
```

## 三、数据流

### 3.0 数据时效性检查（2026-06-17 新增）

**所有分析操作前必须执行数据时效性检查**：

```
数据时效性检查（必须）
  │
  ├── 检查系统数据最新时间
  │     └── 对比当前时间
  │
  ├── 数据滞后 > 1 天？
  │     ├── 是 → 提示用户，等待确认
  │     │        ├── 用户确认 → 标注数据截止时间，继续分析
  │     │        └── 用户拒绝 → 执行数据同步后重新检查
  │     └── 否 → 继续分析
  │
  └── 输出结果时标注数据截止时间
```

### 3.1 信号流

```
数据时效性检查 → Scanner 脚本 → latest_scan.json → Orchestrator → Reasoner Agent → TradingBrief
                                                                                  ↓
                                                                        Debater Agent → 修正后 TradingBrief
```

### 3.2 预警流

```
Monitor 脚本 → latest_monitor.json → Orchestrator → Reasoner Agent → 预警简报
```

### 3.3 反馈流

```
用户反馈 → Orchestrator → Evolver Agent → 进化报告
```

## 四、通信协议

### 4.1 脚本 → Agent

脚本输出 JSON 文件，Orchestrator 读取后决定是否触发 Agent。

### 4.2 Agent → Agent

使用 WorkBuddy 的 `SendMessage` 工具。

### 4.3 数据传递策略

**原则**：Agent 间只传递摘要，不传完整 MarketContext。

```
完整数据（35+ 指标）→ 存在共享文件中（latest_scan.json）
摘要数据（5-8 个关键字段）→ 通过 SendMessage 传递
```

## 五、错误处理

### 5.1 脚本层错误

| 错误类型 | 处理方式 |
|----------|----------|
| TqSdk 连接失败 | 自动切换通达信 MCP，记录日志 |
| 数据为空 | 跳过该品种，不触发 Agent |
| 数据滞后 > 1 天 | **向用户确认**，标注数据截止时间后继续或先同步 |
| 指标计算异常 | 使用默认值，标记为不可靠 |
| positions.json 不存在 | 使用空持仓列表，提示用户提交 |

### 5.2 Agent 层错误

| 错误类型 | 处理方式 |
|----------|----------|
| Agent 调用超时（30s） | 重试 1 次，仍失败则跳过 |
| LLM 推理失败 | 降级为无推理的纯信号输出 |
| Agent 崩溃 | 记录日志，不影响其他 Agent |
| Token 预算耗尽 | 停止触发新 Agent，等待次日重置 |

## 六、监控指标

### 6.1 系统级指标

- 指令处理成功率
- 平均响应时间
- Agent 调用次数
- Token 消耗量

### 6.2 Agent 级指标

| Agent | 指标 |
|-------|------|
| Reasoner | 推理成功率、平均推理时间、置信度分布 |
| Debater | 辩论触发率、平均分歧度、修正幅度 |
| Evolver | 进化触发率、平均故障严重度、模式检测准确率 |
| Orchestrator | 指令处理成功率、用户满意度 |
