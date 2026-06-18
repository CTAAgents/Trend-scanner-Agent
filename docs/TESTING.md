# 测试文档

> 版本：v2.0 | 创建日期：2026-06-17
> 最后更新：2026-06-18
> 状态：全面梳理，与实际代码结构对齐

## 测试概览

| 指标 | 数值 |
|------|------|
| **总测试数** | 544+ |
| **通过** | 544+ |
| **跳过** | 1 |
| **失败** | 0 |
| **覆盖率** | 100%（核心模块） |

## 测试文件清单

### 单元测试（369+ 个）

| 测试文件 | 测试数 | 覆盖模块 |
|----------|--------|----------|
| `test_factor_generator.py` | 22 | FactorGenerator, FactorKnowledgeManager |
| `test_trajectory_analyzer.py` | 11 | TrajectoryAnalyzer |
| `test_report_parser.py` | 16 | ReportParser |
| `test_multi_debater.py` | 22 | ConceptualFeedbackGenerator, BeliefPropagationManager |
| `test_rl_interface.py` | 15 | RLInterfaceDesigner |
| `test_factor_evaluator.py` | 18 | FactorEvaluator |
| `test_factor_evolution.py` | 15 | FactorEvolutionEngine |
| `test_memory_system.py` | 12 | MemoryBridge, SQLiteStore, DuckDBStore |
| `test_visibility_graph.py` | 23 | VisibilityGraph, VGRSI, MultiTimeframeVGRSI |
| `test_walk_forward_validator.py` | 17 | WalkForwardValidator |
| `test_phase3_phase4.py` | 22 | FactorParamOptimizer, SeedFactorPool, MultiFactorModel |
| `test_phase5_phase6.py` | 20 | MultiFactorModel, FactorExperienceDB |
| `test_visibility_graph_operator.py` | 17 | VisibilityGraphOperator |
| `test_multi_timeframe_vgrsi_factor.py` | 10 | MultiTimeframeVGRSIFactor |
| `test_volatility_anchor.py` | 14 | VolatilityAnchor |
| `test_unified_data_router.py` | 68 | UnifiedDataRouter（DuckDB/TqSdk/Pytdx/AkShare 路由） |
| `test_validation_matrix.py` | 19 | ValidationMatrix（7种改动类型验证标准+红线检查） |
| `test_indicator_hub.py` | 15 | IndicatorHub（维度分组+字段映射+缓存+维度加载） |
| `test_multi_dimension_screener.py` | 29 | MultiDimensionScreener（五维度评分+归一化+信号分类） |
| `test_monte_carlo.py` | 24 | MonteCarloSimulator（交易重排+破产概率+回撤分布） |
| `test_strategy_incubator.py` | 18 | StrategyIncubator（孵化会话+信号记录+评估） |
| `test_circuit_breaker.py` | 16 | CircuitBreaker（熔断规则+冷却期+状态管理） |
| `test_strategy_portfolio.py` | 20 | StrategyPortfolio（权重优化+分散化+相关性） |
| **test_trend_scanner_config.py** | 31 | TrendScannerConfig（统一配置） |
| **test_rl_base.py** | 19 | AgentBase, ReplayBuffer, FuturesTradingEnv |
| **test_ppo.py** | 30 | AgentPPO, ActorPPO, CriticPPO, RLTrainer |
| **test_walk_forward_rl.py** | 11 | RLWalkForwardValidator |
| **test_scanner_integration.py** | 11 | RLSignalGenerator, integrate_rl_signal_to_scanner |
| **test_scenario_analyzer.py** | 11 | ScenarioAnalyzer（概率加权场景分析） |
| **test_carry_analyzer.py** | 19 | CarryAnalyzer（Carry策略：期限结构套利） |
| **test_fundamental.py** | 25 | 基本面分析（新闻抓取+供需数据+地缘政治+上下文组装+推理层集成） |
| **test_risk_integration.py** | 13 | 风险模块集成（拥挤度检测+部署风险评估+ContextAssembler集成） |
| **test_paper_integration.py** | 11 | 论文集成（收益归因+审计轨迹系统） |

### 端到端测试（20 个）

| 测试文件 | 测试数 | 说明 |
|----------|--------|------|
| `test_e2e_pipeline.py` | 14 | 完整管道端到端测试 |
| **test_e2e_rl_pipeline.py** | 6 | RL 端到端流程测试 |

### 集成测试（22 个）

| 测试文件 | 测试数 | 说明 |
|----------|--------|------|
| `test_full_pipeline.py` | 22 | 全流程集成测试 |

### 性能基准（20 个）

| 测试文件 | 测试数 | 说明 |
|----------|--------|------|
| `test_performance.py` | 20 | GBM 数据生成、内存用量、端到端管道 |

### 记忆系统（12 个）

| 测试文件 | 测试数 | 说明 |
|----------|--------|------|
| `test_memory_system.py` | 12 | 记忆系统各组件测试 |

## 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_visibility_graph.py -v

# 运行带覆盖率报告
python -m pytest tests/ --cov=scripts --cov-report=html
```

## 测试规范

### 测试命名

- 测试文件：`test_<module_name>.py`
- 测试类：`Test<ClassName>`
- 测试方法：`test_<function_name>_<scenario>`

### 测试覆盖

每个测试应覆盖：
1. **正常场景**：标准输入，预期输出
2. **边界条件**：空数据、单点数据、最大值/最小值
3. **异常场景**：无效输入、错误处理

### 测试数据

- 使用 `np.random.seed(42)` 确保可复现
- 避免依赖外部数据源
- 使用 mock 或 fixture 隔离依赖

---

*本文档记录 QuantNova 项目的测试状态和规范。*
