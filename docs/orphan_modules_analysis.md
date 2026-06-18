# 孤立模块分析报告

> 版本：v1.0 | 创建日期：2026-06-18
> 状态：分析中

## 一、现状分析

### 1.1 目录结构

```
scripts/
├── core/           # 核心层（已迁移）
├── indicators/     # 指标层（已迁移）
├── reasoning/      # 推理层（已迁移）
├── evolution/      # 进化层（已迁移）
├── strategies/     # 策略层（部分迁移）
├── evolution_tools/ # 进化工具（已迁移）
├── tools/          # 工具层（已迁移）
├── rl/            # RL层（已迁移）
├── fundamental/    # 基本面（已迁移）
└── trend_scanner/  # ⚠️ 88个文件待迁移
```

### 1.2 trend_scanner 目录文件统计

**总文件数**：88 个 Python 文件

**已迁移到新架构的文件**：约 30 个

**待迁移的孤立文件**：约 58 个

---

## 二、孤立模块分类

### 2.1 核心层模块（应迁移到 core/）

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| models.py | 数据模型定义 | core/models.py |
| knowledge_anchors.py | 知识锚点 | core/utils/ |
| knowledge_ingestion.py | 知识摄入 | core/utils/ |
| navigator.py | 导航器 | core/ |
| meta_learner.py | 元学习器 | core/ |
| meta_skill_engine.py | 元技能引擎 | core/ |

### 2.2 指标层模块（应迁移到 indicators/）

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| indicators.py | 技术指标 | indicators/indicator_engine.py |
| indicator_hub.py | 指标中心 | indicators/ |
| multi_dimension_screener.py | 多维度筛选 | indicators/ |
| volatility_anchor.py | 波动率锚点 | indicators/ |
| scoring_analytics.py | 评分分析 | indicators/ |

### 2.3 推理层模块（应迁移到 reasoning/）

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| reasoning.py | 推理引擎 | reasoning/reasoning_engine.py |
| debate_engine.py | 辩论引擎 | reasoning/ |
| scenario_analyzer.py | 场景分析 | reasoning/ |
| brief.py | 简报生成 | reasoning/ |
| llm_reasoning.py | LLM推理 | reasoning/ |
| narrative_generator.py | 叙事生成 | reasoning/ |
| conceptual_feedback.py | 概念反馈 | reasoning/ |
| belief_propagation.py | 信念传播 | reasoning/ |

### 2.4 进化层模块（应迁移到 evolution/）

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| factor_generator.py | 因子生成 | evolution/ |
| factor_evaluator.py | 因子评估 | evolution/ |
| factor_gate.py | 因子门控 | evolution/ |
| factor_evolution_engine.py | 因子进化引擎 | evolution/ |
| factor_param_optimizer.py | 参数优化 | evolution/ |
| seed_factor_pool.py | 种子因子池 | evolution/ |
| multi_factor_model.py | 多因子模型 | evolution/ |
| factor_experience_db.py | 因子经验库 | evolution/ |
| walk_forward_validator.py | Walk-Forward验证 | evolution/ |
| visibility_graph.py | 可见图 | evolution/ |
| factor_executor.py | 因子执行 | evolution/ |
| factor_governance.py | 因子治理 | evolution/ |
| factor_graph.py | 因子图 | evolution/ |
| factor_health_monitor.py | 因子健康监控 | evolution/ |
| factor_lifecycle.py | 因子生命周期 | evolution/ |
| factor_validator.py | 因子验证 | evolution/ |
| llm_factor_client.py | LLM因子客户端 | evolution/ |
| weight_optimizer.py | 权重优化 | evolution/ |
| vector_enhancement.py | 向量增强 | evolution/ |
| visibility_graph_operator.py | 可见图操作符 | evolution/ |

### 2.5 策略层模块（应迁移到 strategies/）

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| scanner.py | 扫描器 | strategies/trend_following/ |
| strategy.py | 策略 | strategies/trend_following/ |
| risk_management.py | 风险管理 | strategies/trend_following/ |
| execution.py | 执行引擎 | strategies/trend_following/ |
| position_sizer.py | 仓位管理 | strategies/trend_following/ |
| stop_loss.py | 止损管理 | strategies/trend_following/ |
| portfolio.py | 组合管理 | strategies/trend_following/ |
| strategy_portfolio.py | 策略组合 | strategies/ |

### 2.6 进化工具模块（应迁移到 evolution_tools/）

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| evolution_manager.py | 进化管理器 | evolution_tools/ |
| trajectory_analysis.py | 轨迹分析 | evolution_tools/ |
| trade_journal.py | 交易日志 | evolution_tools/ |
| strategy_health.py | 策略健康度 | evolution_tools/ |
| overfitting_detector.py | 过拟合检测 | evolution_tools/ |
| overfitting_audit.py | 过拟合审计 | evolution_tools/ |
| circuit_breaker.py | 熔断器 | evolution_tools/ |
| trajectory_analyzer.py | 轨迹分析器 | evolution_tools/ |
| regime_gate.py | 机制门控 | evolution_tools/ |
| regime_segmenter.py | 机制分割 | evolution_tools/ |

### 2.7 工具模块（应迁移到 tools/）

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| monte_carlo.py | 蒙特卡洛 | tools/ |
| strategy_incubator.py | 策略孵化 | tools/ |
| backtest.py | 回测 | tools/ |
| report_parser.py | 报告解析 | tools/ |
| tiered_output.py | 分层输出 | tools/ |
| validation_matrix.py | 验证矩阵 | tools/ |

### 2.8 数据层模块（应迁移到 core/data/ 或 core/）

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| data_source.py | 数据源 | core/data/ |
| data_store.py | 数据存储 | core/data/ |
| unified_data_router.py | 统一数据路由器 | core/data/ |
| tqsdk_bridge.py | TqSdk桥接 | core/data/ |
| tqsdk_worker.py | TqSdk工作器 | core/data/ |
| tqsdk_batch_kline.py | TqSdk批量K线 | core/data/ |

### 2.9 记忆层模块（应迁移到 core/memory/）

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| memory_bridge.py | 记忆桥接 | core/memory/ |
| memory_vectorizer.py | 记忆向量化 | core/memory/ |
| experience.py | 经验 | core/memory/ |
| skill_reflection.py | 技能反思 | core/memory/ |

### 2.10 其他模块

| 文件 | 功能 | 建议位置 |
|------|------|----------|
| analytics.py | 分析 | tools/ |
| macro_state.py | 宏观状态 | indicators/ |
| market_analysis.py | 市场分析 | reasoning/ |
| control_variable.py | 控制变量 | core/ |
| selective_update.py | 选择性更新 | core/ |
| silent_bypass_detector.py | 静默绕过检测 | core/ |
| position_health.py | 持仓健康 | strategies/ |
| rl_interface_designer.py | RL接口设计 | rl/ |
| trend_scanner_config.py | 趋势扫描配置 | core/ |

---

## 三、迁移计划

### 3.1 Phase 1：核心层迁移

迁移 models.py, knowledge_*.py, navigator.py, meta_*.py 到 core/

### 3.2 Phase 2：指标层迁移

迁移 indicators.py, indicator_hub.py 等到 indicators/

### 3.3 Phase 3：推理层迁移

迁移 reasoning.py, debate_engine.py 等到 reasoning/

### 3.4 Phase 4：进化层迁移

迁移所有 factor_*.py 到 evolution/

### 3.5 Phase 5：策略层迁移

迁移 scanner.py, strategy.py 等到 strategies/

### 3.6 Phase 6：工具层迁移

迁移 monte_carlo.py, backtest.py 等到 tools/

### 3.7 Phase 7：数据层迁移

迁移 data_*.py, tqsdk_*.py 到 core/data/

### 3.8 Phase 8：记忆层迁移

迁移 memory_*.py, experience.py 到 core/memory/

### 3.9 Phase 9：清理

删除 trend_scanner 目录，更新所有引用

---

## 四、预期结果

| 指标 | 当前 | 迁移后 |
|------|------|--------|
| trend_scanner 文件数 | 88 | 0 |
| 新架构文件数 | ~50 | ~110 |
| 目录结构清晰度 | 低 | 高 |
| 模块职责明确度 | 低 | 高 |

---

*本报告由 WorkBuddy 于 2026-06-18 创建*
