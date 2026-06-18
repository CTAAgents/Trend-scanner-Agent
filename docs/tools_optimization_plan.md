# Tools 目录优化计划

> 版本：v1.0 | 创建日期：2026-06-18
> 状态：分析中

## 一、现状分析

### 1.1 文件统计

**总文件数**：40 个 Python 文件 + 3 个部署脚本 + 2 个批处理文件

### 1.2 文件分类

| 类别 | 文件数 | 说明 |
|------|--------|------|
| **核心工具** | 4 个 | 主扫描器、数据同步、编排器 |
| **RL 工具** | 3 个 | PPO训练、超参调优、RL流水线 |
| **部署工具** | 3 个 | 部署脚本 |
| **监控工具** | 4 个 | 心跳、持仓监控、健康检查、告警 |
| **可视化工具** | 2 个 | 因子图、架构图 |
| **测试工具** | 4 个 | 简单测试脚本 |
| **运行器** | 6 个 | 各种 run_*.py |
| **因子工具** | 3 个 | VGRSI因子相关 |
| **杂项工具** | 11 个 | 其他工具 |

---

## 二、优化方案

### 2.1 目录重组

```
tools/
├── core/                    # 核心工具
│   ├── scan_opportunities.py
│   ├── sync_data.py
│   ├── sync_indicators.py
│   └── orchestrator.py
├── rl/                      # RL 工具
│   ├── train_ppo.py
│   ├── tune_rl_hyperparams.py
│   └── auto_rl_pipeline.py
├── monitor/                 # 监控工具
│   ├── heartbeat.py
│   ├── monitor_positions.py
│   ├── health_check.py
│   └── alert_manager.py
├── visualize/               # 可视化工具
│   ├── factor_graph_viz.py
│   └── generate_architecture_image.py
├── deploy/                  # 部署工具
│   ├── deploy.sh
│   ├── deploy.ps1
│   └── deploy_v4.sh
└── utils/                   # 杂项工具
    ├── data_formats.py
    ├── logger.py
    ├── token_budget.py
    └── ...
```

### 2.2 文件迁移计划

| 原文件 | 新位置 | 说明 |
|--------|--------|------|
| scan_opportunities.py | tools/core/ | 主扫描器 |
| sync_data.py | tools/core/ | 数据同步 |
| sync_indicators.py | tools/core/ | 指标同步 |
| orchestrator.py | tools/core/ | 编排器 |
| train_ppo.py | tools/rl/ | PPO训练 |
| tune_rl_hyperparams.py | tools/rl/ | 超参调优 |
| auto_rl_pipeline.py | tools/rl/ | RL流水线 |
| heartbeat.py | tools/monitor/ | 心跳监控 |
| monitor_positions.py | tools/monitor/ | 持仓监控 |
| health_check.py | tools/monitor/ | 健康检查 |
| alert_manager.py | tools/monitor/ | 告警管理 |
| factor_graph_viz.py | tools/visualize/ | 因子图可视化 |
| generate_architecture_image.py | tools/visualize/ | 架构图生成 |
| deploy.sh, deploy.ps1, deploy_v4.sh | tools/deploy/ | 部署脚本 |
| test_*.py | tests/ | 测试脚本 |

### 2.3 需要删除的文件

| 文件 | 原因 |
|------|------|
| scan_opportunities_v4.py | 旧版本，已被 scan_opportunities.py 替代 |
| start_auto_git_push.py | 旧的自动推送脚本 |
| start_auto_git_push.bat | 旧的批处理脚本 |

---

## 三、预期结果

| 指标 | 当前 | 优化后 |
|------|------|--------|
| tools/ 文件数 | 40+ | ~25 |
| 目录结构 | 扁平 | 分层 |
| 职责清晰度 | 低 | 高 |
| 可维护性 | 低 | 高 |

---

*本计划由 WorkBuddy 于 2026-06-18 创建*
