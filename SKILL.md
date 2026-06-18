---
name: quantnova
description: >
  推理重于规则的期货趋势跟踪决策辅助系统。
  Davey框架补充（蒙特卡洛+策略孵化+熔断+组合管理） +
  基本面分析模块（新闻抓取+供需数据+地缘政治追踪） +
  统一数据路由 + 知识锚点 + 分级输出 + 套利分析 +
  Reasoner Agent 深度分析 + 持仓健康度评估 + 闭环迭代因子进化引擎，
  每日自动扫描主力合约，筛选非僵尸品种（持仓量>=10000），
  数据源：TqSdk（首选）+ Pytdx（备选）+ AkShare（基差/季节性/龙虎榜）+ 本地数据库缓存。
  独立策略模块：趋势跟踪、Carry策略（期限结构套利）、套利策略（跨期/跨品种）。
  跨层支撑：RL强化学习、NLP自然语言交互、事件驱动引擎、Workers异步任务池。
---

# QuantNova

> 推理重于规则的期货趋势跟踪决策辅助系统
> 完整文档请查看 [README.md](README.md) 和 [系统架构总览](docs/system_architecture_overview.md)

## 快速开始

```bash
# 数据同步（首次使用必须执行）
python tools/core/sync_data.py sync --days 120

# 运行扫描
python tools/core/scan_opportunities.py --output text --save

# Reasoner深度分析（推荐）
python tools/core/scan_opportunities.py --reasoner --output text --save

# 持仓健康度评估
python tools/core/scan_opportunities.py --position-health

# 因子评估
python tools/core/scan_opportunities.py --evaluate-factors

# 因子进化
python tools/core/scan_opportunities.py --evolve --evolve-rounds 5

# 自然语言交互
python scripts/core/nlp/nlp_chat.py

# RL训练
python tools/rl/train_ppo.py --symbol RB --days 200 --train-steps 10000
```

## 核心能力

| 能力 | 命令 | 来源模块 |
|------|------|----------|
| 全品种扫描 | `--output text --save` | Layer 5 趋势扫描器 |
| **技术指标计算** | 自动触发 | Layer 1 IndicatorEngine (自研35+ + TqSdk内置70+) |
| **五维度筛选评分** | `--use-multi-dimension` | Layer 1 MultiDimensionScreener |
| **Reasoner深度分析** | `--reasoner --output text --save` | Layer 4 ReasoningEngine |
| **鹰鸽辩论纠偏** | 自动触发 | Layer 4 DebateEngine |
| **基本面分析** | 自动触发 | Layer 1 基本面子模块 |
| **持仓健康度评估** | `--position-health` | Layer 9 PositionHealth |
| **RL 策略信号** | `--use-rl` | 跨层 RL模块 |
| **蒙特卡洛模拟** | 内置（自动触发） | Davey Step 5 |
| **策略孵化** | 内置（自动触发） | Davey Step 6 |
| **停止交易阈值** | 内置（自动触发） | Davey Step 7 CircuitBreaker |
| **多策略组合** | 内置（自动触发） | Davey Step 7 StrategyPortfolio |
| 因子评估 | `--evaluate-factors` | Layer 7 FactorEvaluator |
| 因子进化 | `--evolve` | Layer 7 FactorEvolutionEngine |
| 参数优化 | `--optimize-params` | Layer 7 FactorParamOptimizer |
| 策略健康检查 | `--health-check` | Layer 9 StrategyHealth |
| 过拟合检测 | `--overfitting-check` | Layer 9 OverfittingDetector |
| 套利分析 | `--arbitrage` | Layer 5 ArbitrageAnalyzer |
| Carry策略 | 内置 | Layer 5 CarryAnalyzer |
| 自然语言交互 | `nlp_chat.py` | 跨层 NLP模块 |

## Davey 框架模块

基于 Kevin J. Davey《构建盈利的算法交易系统》补充的4个风控模块：

| 模块 | 文件 | 功能 |
|------|------|------|
| 蒙特卡洛模拟 | `evolution_tools/circuit_breaker.py` | 交易重排→破产概率/置信区间/最差情景 |
| 策略孵化 | `evolution_tools/strategy_health.py` | 实盘数据验证3-6个月，对比回测预期 |
| 停止交易阈值 | `evolution_tools/circuit_breaker.py` | 策略级熔断（最大亏损/回撤/连续亏损） |
| 多策略组合 | `strategies/strategy_portfolio.py` | 策略权重优化/相关性控制/分散化 |

## RL 强化学习模块

借鉴 ElegantRL 架构设计的强化学习模块，支持 PPO 策略训练和集成：

| 模块 | 文件 | 功能 |
|------|------|------|
| AgentBase | `rl/base.py` | Agent 基类，定义 perceive→reason→act→reflect 生命周期 |
| PPO Agent | `rl/agent_ppo.py` | PPO 算法实现（GAE + Ratio Clipping + 熵正则化） |
| 网络架构 | `rl/networks.py` | ActorPPO、CriticPPO、StateNormalizer |
| Gym 环境 | `rl/futures_env.py` | FuturesTradingEnv、MultiAssetVecEnv |
| 训练器 | `rl/trainer.py` | RLTrainer、evaluate_agent |
| Walk-Forward 验证 | `rl/walk_forward_rl.py` | RLWalkForwardValidator（IS/OOS 一致性检查） |
| Scanner 集成 | `rl/scanner_integration.py` | RLSignalGenerator、integrate_rl_signal_to_scanner |
| RL 接口设计 | `rl/rl_interface_designer.py` | RLInterfaceDesigner（GIFT启发） |

## 基本面分析模块

| 模块 | 文件 | 功能 |
|------|------|------|
| 新闻抓取 | `fundamental/news_crawler.py` | 10+数据源（国际：华尔街/路透/彭博/CNN；国内：财新/新浪/央广/东财/雪球） |
| 供需数据 | `fundamental/supply_demand.py` | 库存/产量/消费数据 |
| 地缘政治追踪 | `fundamental/geopolitical.py` | 战争/制裁/关税/和平协议 |

## 事件驱动引擎

| 模块 | 文件 | 功能 |
|------|------|------|
| 事件引擎 | `core/event_engine/event_engine.py` | DATA_UPDATE/SIGNAL/FACTOR_EVOLUTION等6种事件类型 |
| 调度器 | `core/event_engine/scheduler.py` | 定时任务注册+智能休眠 |
| 资源监控 | `core/event_engine/resource_monitor.py` | 内存/CPU/Token预算追踪 |

## 触发词

趋势扫描、期货扫描、因子评估、因子进化、参数优化、持仓健康度、Reasoner分析、蒙特卡洛、策略孵化、熔断、组合管理、基本面分析、套利分析、Carry策略、自然语言交互

---

**完整文档：[README.md](README.md)** | **架构总览：[docs/system_architecture_overview.md](docs/system_architecture_overview.md)** | **测试：[docs/TESTING.md](docs/TESTING.md)** | **变更：[docs/CHANGELOG.md](docs/CHANGELOG.md)**
