# 多 Agent 架构升级方案

> 版本：v3.0 | 创建日期：2026-06-15 | 更新：2026-06-15
> 状态：设计中

## 一、架构概览

### 1.1 当前架构（单体 Skill）

```
用户 → TradingAssistant (navigator.py)
         ├── ContextAssembler (context.py)
         ├── ExperienceMemory (experience.py)
         ├── ReasoningEngine (reasoning.py)
         ├── BriefGenerator (brief.py)
         └── EvolutionManager (evolution_manager.py)
```

问题：
- 所有逻辑在一个进程，无法并行
- 无法定时执行，需用户手动触发
- 无法持续监控持仓
- 辩论机制（debate_engine.py）无法真正并发

### 1.2 目标架构（脚本 + Agent 混合）

**核心设计原则**：计算用脚本，推理用 Agent。避免用 LLM 做纯计算浪费 token。

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

**Token 消耗对比**：

| 方案 | Scanner 调用 | Monitor 调用 | 每日总计 |
|------|-------------|-------------|----------|
| v1.0 纯 Agent | 150次 LLM | 288次 LLM | ~2M token |
| **v2.0 脚本+Agent** | 150次 Python + 5-10次 LLM | 288次 Python + 3-5次 LLM | **~100K token** |

## 二、Agent 定义

### 2.1 Orchestrator Agent（主协调器）

**职责**：
- 接收用户自然语言指令
- 解析用户意图，分发任务给专业 Agent
- 汇总各 Agent 结果，生成最终输出
- 管理 Agent Team 生命周期
- 维护配置和持仓数据

**工具访问**：
- TaskCreate/TaskList/TaskUpdate（任务管理）
- SendMessage（Agent 间通信）
- Bash（执行脚本、读写配置文件）
- Read/Write（读写 positions.json、config.json）

**状态**：
- 当前活跃 Agent 列表
- 任务队列
- 用户偏好（品种列表、风险阈值）

**触发方式**：
- 用户消息（自然语言指令）
- 定时事件（cron 触发扫描）
- 事件触发（持仓风险预警）

**决策逻辑**：

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

**优先级**：
1. HIGH 预警（立即处理）
2. 用户指令（实时响应）
3. 强信号（优先推理）
4. 中信号（排队处理）
5. 弱信号（仅记录）

---

### 2.2 Scanner 脚本 + 条件触发（非纯 Agent）

**设计变更**：Scanner 不是 Agent（无 LLM），是纯 Python 脚本。只在发现有信号的品种时，才触发 Reasoner Agent。

**职责**：
- 定时扫描期货全品种（纯 Python 计算）
- 调用 data_source.py 获取行情数据
- 调用 indicators.py 计算技术指标（含七维趋势强度）
- 调用 market_analysis.py 生成市场分析
- 筛选出有信号的品种（ER>0.6 且 TSI>20 等条件）
- 将有信号的品种提交给 Orchestrator，触发 Reasoner Agent

**执行方式**：
- 通过 WorkBuddy automation（cron）定时触发
- 执行 `tools/scan_opportunities.py` 脚本
- 脚本输出 JSON 格式的信号列表
- Orchestrator 读取输出，决定是否触发 Reasoner

**筛选条件**（可配置）：
```python
SIGNAL_FILTER = {
    'er_min': 0.6,              # 效率比阈值
    'tsi_min': 20,              # TSI 阈值（多头）
    'tsi_max': -20,             # TSI 阈值（空头）
    'trend_strength_min': 0.5,  # 复合趋势强度阈值
    'r2_min': 0.4,              # R² 阈值
}
```

**调度**：
- 每日 09:15（开盘前）：全品种预扫描
- 每日 09:30/10:30/13:30/14:30：盘中扫描
- 每日 15:15（收盘后）：收盘总结扫描

**输出格式**：
```json
{
  "scan_time": "2026-06-15T10:30:00",
  "total_scanned": 30,
  "signals": [
    {
      "symbol": "SHFE.rb2510",
      "trend_phase": "DEVELOPING",
      "trend_strength_composite": 0.72,
      "tsi": 25.3,
      "er": 0.65,
      "r_squared": 0.68,
      "direction": "LONG",
      "signal_strength": "STRONG",
      "trigger_reason": "ER>0.6 且 TSI>20 且 趋势发展阶段"
    }
  ],
  "no_signal_symbols": ["DCE.i2510", "CZCE.CF509", "..."]
}
```

---

### 2.3 Reasoner Agent（推理器）

**职责**：
- 接收 Scanner Agent 的信号
- 调用 ReasoningEngine 进行 LLM 推理
- 调用 BriefGenerator 生成交易决策简报
- 输出简报给 Orchestrator

**工具访问**：
- Bash（执行 Python 脚本）
- 无直接数据源访问（信号来自 Scanner）

**输入**：MarketContext + ExperienceMatch[]
**输出**：TradingBrief（交易决策简报）

**推理流程**：
```
MarketContext → 经验检索 → LLM 推理 → 生成方案 → 动态约束 → 简报
```

**特殊能力**：
- 支持自定义 LLM（OpenAI、DeepSeek、本地模型）
- 支持 WorkBuddy Agent 作为推理后端
- 推理结果带置信度和推理链

---

### 2.4 Debater Agent（辩论器）

**设计变更**：单 Agent 内部 self-debate，不拆分为独立的鹰派/鸽派 Agent（减少通信开销和 token 消耗）。

**职责**：
- 接收 Reasoner Agent 的初步方案
- 在单次推理中依次生成鹰派和鸽派论点
- 进行 1 轮辩论（LLM 内部 self-debate）
- 输出修正后的方案 + 辩论记录

**工具访问**：
- Bash（执行 Python 脚本）

**输入**：TradingBrief + MarketContext（摘要，非完整数据）
**输出**：修正后的 TradingBrief + 辩论记录

**辩论流程**（单 Agent 内部完成）：
```
初始方案
  → [LLM 内部] 鹰派论点：看空理由、风险因素、反转信号
  → [LLM 内部] 鸽派论点：看多理由、趋势确认、动量支撑
  → [LLM 内部] 综合判断：修正方案 + 分歧度 + 条件层级
```

**触发条件**：
- 仅当置信度 < 0.7 时触发（节省 token）
- 持仓金额 > 阈值时触发（高价值场景）
- 用户显式要求时触发

**Token 优化**：相比 v1.0 的多 Agent 多轮辩论，v2.0 的单 Agent self-debate 节省约 60% token。

---

### 2.5 Monitor 脚本 + 条件触发（非纯 Agent）

**设计变更**：Monitor 不是 Agent（无 LLM），是纯 Python 脚本。只在检测到风险信号时，才触发 Reasoner Agent 生成预警简报。

**职责**：
- 读取 positions.json 获取当前持仓
- 监控持仓品种的价格和指标变化
- 检测止损/止盈触发条件
- 检测趋势反转信号（TSI 背离、ER 下降等）
- 触发预警时调用 Orchestrator → Reasoner Agent

**执行方式**：
- 通过 WorkBuddy automation（cron）定时触发
- 执行 `tools/monitor_positions.py` 脚本
- 脚本输出 JSON 格式的预警列表

**调度**：
- 每 30 分钟：持仓品种监控（纯 Python）
- 事件触发：价格突破止损/止盈线时立即预警

**输出格式**：
```json
{
  "monitor_time": "2026-06-15T10:30:00",
  "positions_monitored": 5,
  "alerts": [
    {
      "symbol": "DCE.jm2609",
      "type": "TREND_REVERSAL",
      "severity": "HIGH",
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

**TqSdk 连接策略**：
- Scanner 脚本和 Monitor 脚本共享同一个 TqSdk 连接实例
- 通过 `data_source.py` 的单例模式管理连接
- 错开调度时间，避免同时连接冲突

---

### 2.6 Evolver Agent（进化器）

**职责**：
- 记录交易反馈（用户决策 + 实际结果）
- 分析交易轨迹，归因故障
- 检测交易模式，晋升规则
- 执行自进化流程

**工具访问**：
- Bash（执行 Python 脚本）

**输入**：UserFeedback + TradingBrief + MarketContext
**输出**：进化报告（提案、模式、规则、反思）

**进化流程**：
```
交易反馈 → 轨迹分析 → 故障归因 → 策略反思 → 规则优化 → 过拟合审计
```

**触发条件**：
- 每笔交易结束后（用户提交反馈）
- 连续亏损 >= 3 次
- 累计亏损 >= 10%
- 每 20 笔交易定期进化

---

## 三、共享模块

以下模块被多个组件共享，保持为独立 Python 包：

| 模块 | 使用者 | 说明 |
|------|--------|------|
| `indicators.py` | Scanner 脚本, Monitor 脚本 | 技术指标计算 |
| `context.py` | Scanner 脚本, Reasoner Agent | 上下文组装 |
| `market_analysis.py` | Scanner 脚本, Monitor 脚本 | 市场分析 |
| `models.py` | 全部 | 数据模型定义 |
| `strategy.py` | Scanner 脚本, Reasoner Agent | 策略池 |
| `experience.py` | Reasoner Agent, Evolver Agent | 经验记忆池 |
| `data_source.py` | Scanner 脚本, Monitor 脚本 | 数据源适配器（单例） |
| `data_store.py` | 全部 | 数据持久化 |

**共享原则**：
- 共享模块只做计算，不做决策
- 共享模块无状态（输入→输出，不修改全局状态）
- 共享模块的测试独立于 Agent

**TqSdk 连接单例**：
- `data_source.py` 实现单例模式，全局只有一个 TqSdk 连接
- Scanner 脚本和 Monitor 脚本通过单例访问数据源
- 错开调度时间（Scanner 整点运行，Monitor 半点运行），避免并发冲突

---

## 四、持仓数据流

### 4.1 当前方案（手动提交）

```
用户每日收盘后手动提交持仓 → positions.json → Monitor 脚本读取
```

**数据格式**（positions.json）：
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

**提交方式**：用户通过对话告知系统当前持仓，系统更新 positions.json。

### 4.2 未来方案（接入真实账户）

```
TqSdk 账户 API → 实时持仓查询 → positions.json → Monitor 脚本读取
```

**迁移路径**：
- Phase 1：手动提交（当前）
- Phase 2：TqSdk 账户 API 自动查询持仓
- Phase 3：支持多账户

### 4.3 持仓数据读写权限

| 操作 | 执行者 | 说明 |
|------|--------|------|
| 写入持仓 | 用户（手动）/ TqSdk API（自动） | 只有用户或系统可以修改持仓 |
| 读取持仓 | Monitor 脚本, Orchestrator | 只读访问 |
| 记录反馈 | Evolver Agent | 交易结束后记录结果 |

---

## 五、Agent 间通信

### 5.1 通信方式

**脚本 → Agent**：脚本输出 JSON 文件，Orchestrator 读取后决定是否触发 Agent。

**Agent → Agent**：使用 WorkBuddy 的 `SendMessage` 工具。

```
Scanner 脚本 --[JSON文件]--> Orchestrator --[摘要]--> Reasoner Agent
Reasoner Agent --[简报]--> Orchestrator
Orchestrator --[简报]--> Debater Agent（必要时）
Debater Agent --[修正简报]--> Orchestrator
Monitor 脚本 --[JSON文件]--> Orchestrator --[摘要]--> Reasoner Agent
Evolver Agent --[进化报告]--> Orchestrator
```

### 5.2 数据传递策略

**原则**：Agent 间只传递摘要，不传完整 MarketContext。

```
完整数据（35+ 指标）→ 存在共享文件中（latest_scan.json）
摘要数据（5-8 个关键字段）→ 通过 SendMessage 传递
```

**摘要格式**：
```json
{
  "symbol": "SHFE.rb2510",
  "direction": "LONG",
  "trend_phase": "DEVELOPING",
  "trend_strength_composite": 0.72,
  "key_signals": ["ER>0.6", "TSI>20", "均线多头排列"],
  "risk_factors": ["RSI接近超买", "波动率扩张"],
  "scan_id": "scan_20260615_103000"
}
```

Reasoner Agent 如需完整数据，通过 scan_id 从共享文件中读取。

### 5.3 消息格式

所有 Agent 间通信使用 JSON 格式：

```json
{
  "type": "signal|brief|alert|evolution_report",
  "source": "scanner|reasoner|debater|monitor|evolver",
  "timestamp": "2026-06-15T10:30:00",
  "payload": { ... },
  "metadata": {
    "confidence": 0.75,
    "processing_time_ms": 1200
  }
}
```

### 5.4 状态同步

**共享状态存储**：
- 经验记忆池：SQLite 数据库（evolution.db）
- 持仓状态：JSON 文件（positions.json）
- 扫描结果：JSON 文件（latest_scan.json）
- 监控结果：JSON 文件（latest_monitor.json）

**同步策略**：
- 写入者负责更新文件
- 读取者每次读取最新版本
- 单写多读模式（Scanner 写 latest_scan.json，Monitor 写 latest_monitor.json）

---

## 六、用户交互模型

### 6.1 交互方式

用户通过自然语言与 Orchestrator Agent 交互，无需记忆结构化命令。

**示例对话**：

```
用户：帮我扫描一下黑色系
Orchestrator：[执行 Scanner 脚本，筛选黑色系品种] → 输出信号列表

用户：分析一下焦煤
Orchestrator：[触发 Reasoner Agent] → 输出焦煤决策简报

用户：我今天平了焦煤多头，赚了 3.5%
Orchestrator：[更新 positions.json + 触发 Evolver Agent] → "已记录，焦煤多头 +3.5%"

用户：把 ER 阈值调到 0.5
Orchestrator：[更新 config.json] → "已调整 ER 阈值为 0.5，下次扫描生效"

用户：现在持仓是什么情况
Orchestrator：[读取 positions.json + 触发 Monitor 脚本] → 输出持仓概览
```

### 6.2 意图识别

Orchestrator 通过 LLM 推理识别用户意图，映射到系统操作：

| 用户意图 | 示例表述 | 系统操作 |
|----------|----------|----------|
| 扫描 | "扫描黑色系"、"看看今天有什么机会" | 执行 Scanner 脚本 |
| 分析 | "分析焦煤"、"RB2501 怎么样" | 触发 Reasoner Agent |
| 持仓 | "持仓情况"、"我的仓位" | 读取 positions.json + Monitor |
| 反馈 | "平了焦煤，赚了3.5%" | 更新 positions.json + Evolver |
| 配置 | "把 ER 调到 0.5"、"扫描频率改成每天3次" | 更新 config.json |
| 进化 | "跑一下进化"、"反思一下最近的交易" | 触发 Evolver Agent |

### 6.3 输出方式

- **日常扫描结果**：静默（无信号时不打扰）
- **有信号时**：在对话中输出简报摘要
- **风险预警**：立即推送通知（HIGH 级别）
- **用户主动查询**：详细输出

---

## 七、配置管理

### 7.1 配置文件结构

配置存储在 `config.json` 中，不硬编码：

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
    "max_tokens_per_day": 500000
  },
  "evolver": {
    "auto_trigger": {
      "consecutive_losses": 3,
      "cumulative_loss_pct": 10,
      "trade_count_interval": 20
    }
  },
  "token_budget": {
    "daily_limit": 850000,
    "warn_at_pct": 80,
    "stop_at_pct": 100
  }
}
```

### 7.2 动态配置

用户可在对话中自然语言修改配置，Orchestrator 解析意图后更新 config.json：

| 用户表述 | 解析结果 | 操作 |
|----------|----------|------|
| "把 ER 阈值调到 0.5" | scanner.signal_filter.er_min = 0.5 | 更新 config.json |
| "扫描频率改成每天3次" | scanner.schedule = ["09:15", "11:30", "14:30"] | 更新 config.json |
| "监控频率改成15分钟" | monitor.interval_minutes = 15 | 更新 config.json |
| "暂停扫描" | scanner.enabled = false | 更新 config.json |
| "恢复扫描" | scanner.enabled = true | 更新 config.json |

### 7.3 配置热加载

- 脚本层（Scanner/Monitor）：每次执行时读取 config.json，无需重启
- Agent 层（Reasoner/Debater/Evolver）：Orchestrator 在触发时传递最新配置

---

## 八、脚本触发和结果回传

### 8.1 触发机制

```
Orchestrator Agent
  │
  ├── 定时触发（cron）
  │     ├── 创建 WorkBuddy automation（Scanner）
  │     ├── 创建 WorkBuddy automation（Monitor）
  │     └── automation 执行脚本，输出 JSON 到文件
  │
  └── 事件触发（用户指令/预警）
        └── Orchestrator 直接通过 Bash 执行脚本
```

### 8.2 结果回传

**方式**：脚本输出 JSON 文件，Orchestrator 读取。

```
Scanner 脚本 → latest_scan.json → Orchestrator 读取
Monitor 脚本 → latest_monitor.json → Orchestrator 读取
```

**Orchestrator 读取逻辑**：
1. 执行脚本（Bash）
2. 等待完成
3. 读取输出文件（latest_scan.json / latest_monitor.json）
4. 根据输出内容决定下一步操作

### 8.3 错误处理

- 脚本超时（60s）→ 记录日志，跳过本次
- 脚本异常退出 → 记录错误，下次重试
- 输出文件不存在 → 使用上次缓存（如有）

---

## 九、数据生命周期管理

### 9.1 数据保留策略

| 数据 | 保留策略 | 说明 |
|------|----------|------|
| `latest_scan.json` | 只保留最新一次 | 每次覆盖 |
| `latest_monitor.json` | 只保留最新一次 | 每次覆盖 |
| `positions.json` | 只保留当前持仓 | 平仓后移除 |
| `evolution.db` | 永久保留 | 经验记忆池，持续增长 |
| `config.json` | 永久保留 | 配置文件 |
| `scan_history/` | 保留 30 天 | 历史扫描结果（用于回测） |
| `brief_history/` | 保留 90 天 | 历史决策简报（用于复盘） |
| `logs/` | 保留 7 天 | 运行日志 |

### 9.2 清理机制

- Orchestrator 每日收盘后自动清理过期数据
- evolution.db 超过 100MB 时，触发知识蒸馏（Evolver Agent）

---

## 十、多时间框架支持

### 10.1 当前方案（MVP）

Scanner 只扫描日线级别。入场时机由用户自行判断。

### 10.2 未来扩展

```
Scanner 日线扫描 → 定方向（趋势确认）
  └── 有信号的品种 → Scanner 小时线扫描 → 定入场时机
```

**实现方式**：
- config.json 中添加 `timeframes` 配置
- Scanner 支持多周期扫描（日线为主，小时线为辅）
- 信号需要日线和小时线同时确认才触发

---

## 十一、实施计划

### Phase 1：基础设施（2-3天）

- [ ] 实现 TqSdk 连接单例模式（data_source.py）
- [ ] 创建 positions.json 数据格式和读写工具
- [ ] 创建 latest_scan.json / latest_monitor.json 数据格式
- [ ] 实现 Scanner 筛选条件配置化

### Phase 2：Scanner 脚本（2-3天）

- [ ] 封装 scan_opportunities.py 为可独立运行的脚本
- [ ] 实现结构化 JSON 输出
- [ ] 实现信号筛选逻辑（ER/TSI/趋势强度阈值）
- [ ] 添加 cron 定时调度（WorkBuddy automation）
- [ ] 测试多品种扫描

### Phase 3：Reasoner Agent（2-3天）

- [ ] 创建 Reasoner Agent 的 SKILL.md
- [ ] 封装 TradingAssistant.analyze() 为 Agent 可调用的脚本
- [ ] 实现摘要数据接收 → 完整数据读取 → 推理 → 简报输出
- [ ] 实现 Agent 间消息格式
- [ ] 测试推理质量

### Phase 4：Debater Agent（1-2天）

- [ ] 创建 Debater Agent 的 SKILL.md
- [ ] 实现单 Agent 内部 self-debate prompt
- [ ] 实现置信度触发条件
- [ ] 测试辩论质量

### Phase 5：Monitor 脚本（2-3天）

- [ ] 创建 tools/monitor_positions.py
- [ ] 实现持仓读取和风险检测逻辑
- [ ] 实现预警触发条件
- [ ] 添加 cron 定时调度
- [ ] 测试预警准确性

### Phase 6：Evolver Agent（2-3天）

- [ ] 创建 Evolver Agent 的 SKILL.md
- [ ] 封装 evolution_manager.py 为 Agent
- [ ] 实现交易反馈记录流程
- [ ] 实现自进化触发条件
- [ ] 测试进化流程

### Phase 7：Orchestrator 集成（2-3天）

- [ ] 创建 Orchestrator Agent 的 SKILL.md
- [ ] 实现 Scanner 输出 → Reasoner 触发流程
- [ ] 实现 Monitor 输出 → 预警推送流程
- [ ] 实现用户指令解析和分发
- [ ] 端到端测试

### Phase 8：监控和运维（1-2天）

- [ ] 实现统一日志格式
- [ ] 实现 token 消耗统计和预算控制
- [ ] 实现 Agent 健康检查
- [ ] 编写运维文档

---

## 十二、迁移策略

### 6.1 渐进式迁移

```
Phase 1-2: Scanner Agent 独立运行，验证扫描能力
Phase 3:   Reasoner Agent 接入，验证推理质量
Phase 4:   Debater Agent 接入，验证辩论机制
Phase 5:   Monitor Agent 接入，验证监控能力
Phase 6:   Evolver Agent 接入，验证进化流程
Phase 7:   全链路集成，替换原 TradingAssistant
```

### 6.2 回退方案

- 保留现有 `TradingAssistant` 类不变
- Agent 层是增量，不影响现有代码
- 如果 Agent 方案失败，可随时回退到纯 Skill 模式

### 6.3 兼容性

- 现有 1181 个测试用例继续有效
- 共享模块（indicators.py 等）不需要修改
- Agent 只是新增的调度层

---

## 十三、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Token 消耗过高 | 成本增加 | Scanner/Monitor 用脚本，只对有信号的品种触发 Agent；每日 token 预算 |
| TqSdk 连接冲突 | 数据获取失败 | 单例模式 + 错开调度时间 |
| Agent 通信延迟 | 响应变慢 | 异步通信，超时机制（30s） |
| 状态文件损坏 | 数据不一致 | 写入前备份，异常时回退 |
| 单 Agent 崩溃 | 部分功能不可用 | 故障隔离，脚本层不受 Agent 崩溃影响 |
| 调试困难 | 排障耗时 | 统一日志格式，消息 ID 追踪链路 |

## 十四、错误处理策略

### 9.1 脚本层错误

| 错误类型 | 处理方式 |
|----------|----------|
| TqSdk 连接失败 | 自动切换通达信 MCP，记录日志 |
| 数据为空 | 跳过该品种，不触发 Agent |
| 指标计算异常 | 使用默认值，标记为不可靠 |
| positions.json 不存在 | 使用空持仓列表，提示用户提交 |

### 9.2 Agent 层错误

| 错误类型 | 处理方式 |
|----------|----------|
| Agent 调用超时（30s） | 重试 1 次，仍失败则跳过 |
| LLM 推理失败 | 降级为无推理的纯信号输出 |
| Agent 崩溃 | 记录日志，不影响其他 Agent |
| Token 预算耗尽 | 停止触发新 Agent，等待次日重置 |

## 十五、Token 预算控制

### 10.1 每日预算

| 组件 | 预算 | 说明 |
|------|------|------|
| Reasoner Agent | 500K token | 约 10-15 次推理 |
| Debater Agent | 200K token | 约 5-10 次辩论 |
| Evolver Agent | 100K token | 约 2-3 次进化 |
| Orchestrator | 50K token | 任务分发和汇总 |
| **合计** | **850K token/天** | |

### 10.2 降级策略

- Token 消耗达到 80%：停止 Debater Agent（跳过辩论）
- Token 消耗达到 90%：只保留 Scanner 脚本（无推理）
- Token 消耗达到 100%：停止所有 Agent，等待次日重置

## 十六、日志和可观测性

### 11.1 统一日志格式

```json
{
  "timestamp": "2026-06-15T10:30:00",
  "component": "scanner|reasoner|debater|monitor|evolver|orchestrator",
  "level": "INFO|WARN|ERROR",
  "message": "扫描完成，发现 3 个信号",
  "context": {
    "scan_id": "scan_20260615_103000",
    "symbols_scanned": 30,
    "signals_found": 3
  }
}
```

### 11.2 消息追踪

每条 Agent 间消息携带 trace_id，用于追踪完整链路：

```
scan_20260615_103000
  → reasoner_20260615_103005
    → debater_20260615_103010
      → brief_20260615_103015
```

## 十七、测试策略

| 测试类型 | 范围 | 工具 |
|----------|------|------|
| 单元测试 | 共享模块（indicators.py 等） | pytest（已有 1181 个） |
| 脚本测试 | Scanner/Monitor 脚本输出格式 | pytest + Mock 数据 |
| Agent 测试 | Agent 行为和消息格式 | Mock Agent + 端到端测试 |
| 集成测试 | 完整链路（扫描→推理→输出） | 测试环境 + 模拟数据 |
| 性能测试 | Token 消耗、延迟、并发 | 统计脚本 |

---

## 十八、预期收益

| 指标 | 当前（Skill） | 升级后（脚本+Agent） |
|------|--------------|---------------------|
| 扫描频率 | 手动触发 | 每日 5 次自动扫描 |
| 持仓监控 | 无 | 每 30 分钟自动监控 |
| 辩论机制 | 串行模拟 | 单 Agent self-debate |
| 多品种并行 | 不支持 | 脚本层并行 |
| 自进化触发 | 手动 | 自动（连续亏损/定期） |
| 故障隔离 | 无 | 脚本层不受 Agent 崩溃影响 |
| Token 消耗 | ~50K/次 | ~850K/天（可控） |
| 数据源 | 单一 | TqSdk 单例 + 通达信降级 |
