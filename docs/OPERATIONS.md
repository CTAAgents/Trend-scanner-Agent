# 运维文档

> 版本：v1.0 | 创建日期：2026-06-15

## 一、部署

### 1.1 环境要求

- Python 3.12+
- TqSdk（期货数据源）
- WorkBuddy（Agent 调度平台）

### 1.2 目录结构

```
E:\QuantNova\
├── agents/                     # Agent 定义
├── tools/                      # 脚本工具
├── scripts/trend_scanner/      # 核心计算包
├── config/                     # 配置文件
├── data/                       # 运行时数据
├── logs/                       # 日志文件
└── docs/                       # 文档
```

### 1.3 配置文件

- `config/config.json`：统一配置（Scanner/Monitor/Reasoner/Debater/Evolver 参数）
- `config/positions.json`：持仓数据（用户手动提交）

## 二、日常运维

### 2.1 启动流程

1. 检查数据源连接：`python tools/health_check.py check`
2. 检查健康状态：`python tools/health_check.py report`
3. 启动心跳监控：`python tools/heartbeat.py --loop`

### 2.2 Cron 调度

| 时间 | 任务 | 说明 |
|------|------|------|
| 08:40 | 盘前准备 | 全品种扫描 + 输出结果 |
| 15:20 | 日盘收盘 | 全品种扫描 + 输出总结 |
| 20:40 | 夜盘开盘 | 全品种扫描 + 输出结果 |

### 2.3 心跳监控

- 频率：每 5 分钟
- 时段：09:00-11:30, 13:30-15:00, 21:00-23:00
- 功能：检测持仓预警和新信号

## 三、监控

### 3.1 Token 预算

- 每日预算：850,000 token
- 查看状态：`python tools/token_budget.py status`
- 记录使用：`python tools/token_budget.py record --component reasoner --tokens 5000`

降级策略：
| 使用率 | 动作 |
|--------|------|
| < 80% | 正常运行 |
| 80-90% | 停止 Debater Agent |
| 90-100% | 只保留 Scanner 脚本 |
| >= 100% | 停止所有 Agent |

### 3.2 日志

- 位置：`logs/YYYY-MM-DD.jsonl`
- 格式：JSON Lines
- 追踪：每条日志携带 trace_id

查看日志：
```bash
# 查看今天的日志
cat logs/2026-06-15.jsonl

# 按组件筛选
grep '"component":"scanner"' logs/2026-06-15.jsonl

# 按级别筛选
grep '"level":"ERROR"' logs/2026-06-15.jsonl
```

### 3.3 错误统计

- 位置：`data/error_log.json`
- 查看：`python tools/health_check.py report`

## 四、故障排查

### 4.1 TqSdk 连接失败

**症状**：Scanner 脚本报错 "TqSdk 连接失败"

**排查步骤**：
1. 检查网络连接
2. 检查 TQ_USER 和 TQ_PASSWORD 环境变量
3. 检查 TqSdk 服务状态
4. 降级到通达信 MCP

**降级方案**：
- 通达信 MCP 已配置为备选数据源
- 系统会自动降级，无需手动干预

### 4.2 Agent 超时

**症状**：Reasoner/Debater 脚本执行超时

**排查步骤**：
1. 检查 LLM 服务状态
2. 检查网络延迟
3. 查看错误日志：`data/error_log.json`

**重试机制**：
- 默认重试 2 次
- 超时时间：60 秒
- 重试间隔：2 秒

### 4.3 Token 预算耗尽

**症状**：Agent 停止运行

**排查步骤**：
1. 查看预算状态：`python tools/token_budget.py status`
2. 检查各组件使用量
3. 等待次日重置或手动调整预算

**手动调整**：
- 编辑 `config/config.json` 中的 `token_budget.daily_limit`
- 或等待次日自动重置

### 4.4 持仓数据丢失

**症状**：Monitor 脚本报错 "positions.json 不存在"

**恢复步骤**：
1. 重新提交持仓：`python tools/positions_manager.py add --symbol DCE.jm2609 --direction LONG --price 1350`
2. 或手动编辑 `config/positions.json`

## 五、维护

### 5.1 日志清理

- 日志保留 7 天
- 手动清理：删除 `logs/` 目录下的旧文件

### 5.2 数据清理

- `data/latest_scan.json`：每次扫描覆盖
- `data/latest_monitor.json`：每次监控覆盖
- `data/heartbeat_state.json`：心跳状态，持续更新
- `data/evolution_state.json`：进化状态，永久保留

### 5.3 配置更新

用户可在对话中自然语言修改配置：
- "把 ER 阈值调到 0.5"
- "扫描频率改成每天3次"
- "监控频率改成15分钟"

或手动编辑 `config/config.json`

## 六、常用命令

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
python tools/token_budget.py record --component reasoner --tokens 5000

# 完整流程
python tools/orchestrator.py full
```
