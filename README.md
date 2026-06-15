# Trend Scanner Agent

推理重于规则的期货趋势跟踪决策辅助系统。

## 核心理念

**以人为本，LLM为眼，规则为果。**

所有看似"规则"的内容（止损、仓位、入场条件）均由推理层根据当前市场状态动态生成，而非事先写死。

## 架构

```
Orchestrator Agent（主协调）
  ├── Scanner 脚本（纯 Python）→ 条件触发 Reasoner
  ├── Reasoner Agent（LLM 推理）→ 生成决策简报
  ├── Debater Agent（self-debate）→ 修正方案
  ├── Monitor 脚本（纯 Python）→ 条件触发预警
  └── Evolver Agent（LLM 反思）→ 优化策略
```

## 特性

- **心跳监控**：每 5 分钟检查市场状态变化，只在有信号时触发推理
- **辩论机制**：鹰派/鸽派对抗性推理，修正方案并输出分歧度
- **经验进化**：从交易结果中学习，自动优化策略参数
- **Token 预算**：每日 850K token 预算，三级降级策略
- **健康检查**：数据源自动降级（TqSdk → 通达信 MCP）

## 目录结构

```
Trend-scanner-Agent/
├── SOUL.md                     # Agent 灵魂定义
├── Agent.md                    # Agent 能力定义
├── USER.md                     # 用户偏好
├── SKILL.md                    # 入口注册
├── agents/                     # Agent 定义
│   ├── orchestrator.md         # 主协调器
│   ├── reasoner.md             # LLM 推理
│   ├── debater.md              # 鹰派/鸽派辩论
│   └── evolver.md              # 经验进化
├── tools/                      # 工具脚本
│   ├── scan_opportunities.py   # Scanner（纯 Python）
│   ├── heartbeat.py            # 心跳监控（纯 Python）
│   ├── monitor_positions.py    # 持仓分析
│   ├── run_reasoner.py         # Reasoner 包装
│   ├── run_debater.py          # Debater 包装
│   ├── run_evolver.py          # Evolver 包装
│   ├── orchestrator.py         # Orchestrator 调度
│   ├── positions_manager.py    # 持仓管理
│   ├── data_formats.py         # 数据格式
│   ├── logger.py               # 统一日志
│   ├── token_budget.py         # Token 预算
│   └── health_check.py         # 健康检查
├── scripts/trend_scanner/      # 核心计算包（41 个模块）
├── config/                     # 配置文件
│   ├── config.json             # 统一配置
│   └── positions.json          # 持仓数据
├── data/                       # 运行时数据
├── logs/                       # 日志文件
└── docs/                       # 文档
    ├── ARCHITECTURE.md         # 架构设计
    └── OPERATIONS.md           # 运维文档
```

## 快速开始

### 1. 环境要求

- Python 3.12+
- TqSdk（期货数据源）
- WorkBuddy（Agent 调度平台）

### 2. 配置

编辑 `config/config.json`：

```json
{
  "scanner": {
    "symbols": ["SHFE.rb", "DCE.jm", "INE.sc"],
    "signal_filter": {
      "er_min": 0.6,
      "tsi_min": 20,
      "trend_strength_min": 0.5
    }
  }
}
```

### 3. 提交持仓

```bash
python tools/positions_manager.py add --symbol DCE.jm2609 --direction LONG --price 1350
```

### 4. 运行扫描

```bash
python tools/scan_opportunities.py --output text --save
```

### 5. 完整流程

```bash
python tools/orchestrator.py full
```

## 调度

### Cron 调度（3 个）

| 时间 | 任务 | 说明 |
|------|------|------|
| 08:40 | 盘前准备 | 全品种扫描 + 输出结果 |
| 15:20 | 日盘收盘 | 全品种扫描 + 输出总结 |
| 20:40 | 夜盘开盘 | 全品种扫描 + 输出结果 |

### 心跳监控

- 频率：每 5 分钟
- 时段：09:00-11:30, 13:30-15:00, 21:00-23:00
- 功能：检测持仓预警和新信号

## Token 预算

每日预算：850,000 token

| 使用率 | 动作 |
|--------|------|
| < 80% | 正常运行 |
| 80-90% | 停止 Debater Agent |
| 90-100% | 只保留 Scanner 脚本 |
| >= 100% | 停止所有 Agent |

## 数据源

- **首选**：TqSdk（期货实时行情、主力合约）
- **备选**：通达信 MCP（A股/港股/美股/期货）
- **兜底**：本地 CSV

## 技术指标

7 维趋势强度指标：

| 指标 | 权重 | 说明 |
|------|------|------|
| TSI | 25% | 趋势强度指数 |
| ER | 25% | 效率比 |
| EMA 斜率 | 15% | 均线斜率强度 |
| ATR 比率 | 10% | 波动率比率 |
| R² | 10% | 拟合度 |
| Hurst | 8% | 赫斯特指数 |
| ADX ROC | 7% | ADX 变化率 |

## 常用命令

```bash
# 健康检查
python tools/health_check.py check
python tools/health_check.py report

# 扫描
python tools/scan_opportunities.py --output text --save

# 心跳
python tools/heartbeat.py --output text

# 持仓管理
python tools/positions_manager.py list
python tools/positions_manager.py add --symbol DCE.jm2609 --direction LONG --price 1350

# 推理
python tools/run_reasoner.py --symbol SHFE.rb --output text

# 辩论
python tools/run_debater.py --output text --save

# 进化
python tools/run_evolver.py status
python tools/run_evolver.py feedback --symbol DCE.jm2609 --result profit --pnl 3.5

# Token 预算
python tools/token_budget.py status

# 完整流程
python tools/orchestrator.py full
```

## 文档

- [架构设计](docs/ARCHITECTURE.md) - 详细的架构设计文档
- [运维文档](docs/OPERATIONS.md) - 部署、监控、故障排查

## 与 v1 Skill 的关系

- **共享模块**：`scripts/trend_scanner/` 是核心计算包，v1 和 v2 共用
- **v1 保留**：原 Skill 继续可用，作为回退方案
- **v2 增量**：Agent 层是新增的调度层，不影响 v1 代码

## 许可证

MIT License
