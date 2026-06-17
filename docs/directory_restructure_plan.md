# 目录分层重组计划

> 版本：v1.0 | 创建日期：2026-06-17
> 状态：进行中

---

## 一、目标

将 `scripts/trend_scanner/` 下的 89 个 .py 文件按逻辑分层重组，提高代码可维护性和可扩展性。

## 二、设计原则

1. **逻辑分层**：按功能模块分组，而非文件类型
2. **依赖清晰**：下层不依赖上层，同层尽量独立
3. **接口统一**：通过 AgentBase 提供标准接口
4. **向后兼容**：保留原有导入路径，通过 __init__.py 重导出

## 三、目录结构

```
scripts/trend_scanner/
├── core/                    # 核心抽象层
│   ├── __init__.py
│   ├── agent_base.py        # Agent 基类（已创建）
│   ├── config.py            # 统一配置管理
│   └── types.py             # 数据类型定义
│
├── data/                    # 数据层
│   ├── __init__.py
│   ├── sources/             # 数据源适配器
│   │   ├── __init__.py
│   │   ├── base.py          # DataSource 基类
│   │   ├── tqsdk.py         # TqSdk 数据源
│   │   ├── csv.py           # CSV 数据源
│   │   └── factory.py       # 数据源工厂
│   ├── storage/             # 数据存储
│   │   ├── __init__.py
│   │   ├── duckdb_store.py
│   │   ├── sqlite_store.py
│   │   └── data_sync.py
│   └── router.py            # 统一数据路由
│
├── analysis/                # 分析层
│   ├── __init__.py
│   ├── indicators/          # 技术指标
│   │   ├── __init__.py
│   │   ├── engine.py        # IndicatorEngine
│   │   └── hub.py           # IndicatorHub
│   ├── market/              # 市场分析
│   │   ├── __init__.py
│   │   ├── regime.py        # RegimeDetector
│   │   └── state.py         # MarketStateClassifier
│   └── screener.py          # 多维度筛选
│
├── reasoning/               # 推理层
│   ├── __init__.py
│   ├── reasoner.py          # ReasoningEngine
│   ├── llm_provider.py      # LLM 提供者
│   └── prompts.py           # Prompt 模板
│
├── trading/                 # 交易层
│   ├── __init__.py
│   ├── signals/             # 信号生成
│   │   ├── __init__.py
│   │   ├── scanner.py       # TrendScanner
│   │   └── generator.py     # SignalGenerator
│   ├── execution/           # 执行引擎
│   │   ├── __init__.py
│   │   ├── engine.py        # ExecutionEngine
│   │   └── risk_guard.py    # RiskGuard
│   └── position/            # 仓位管理
│       ├── __init__.py
│       ├── sizer.py         # PositionSizer
│       └── stop_loss.py     # StopLossCalculator
│
├── evolution/               # 进化层
│   ├── __init__.py
│   ├── factor/              # 因子进化
│   │   ├── __init__.py
│   │   ├── generator.py     # FactorGenerator
│   │   ├── evaluator.py     # FactorEvaluator
│   │   └── evolution.py     # FactorEvolutionEngine
│   ├── strategy/            # 策略进化
│   │   ├── __init__.py
│   │   ├── health.py        # StrategyHealthChecker
│   │   └── portfolio.py     # StrategyPortfolio
│   └── monitor.py           # 监控（SelfMonitor, CircuitBreaker）
│
├── rl/                      # 强化学习层（已创建）
│   ├── __init__.py
│   ├── base.py
│   ├── networks.py
│   ├── agent_ppo.py
│   ├── futures_env.py
│   ├── trainer.py
│   ├── walk_forward_rl.py
│   └── scanner_integration.py
│
├── memory/                  # 记忆层
│   ├── __init__.py
│   ├── experience.py        # 经验记忆
│   ├── knowledge.py         # 知识库
│   └── bridge.py            # 记忆桥接器
│
└── utils/                   # 工具层
    ├── __init__.py
    ├── output.py            # 输出格式化
    ├── validation.py        # 验证矩阵
    └── logging.py           # 日志工具
```

## 四、迁移计划

### Phase 1: 创建目录结构（当前）
- [x] 创建 core/ 目录和 AgentBase
- [ ] 创建 data/ 目录结构
- [ ] 创建 analysis/ 目录结构
- [ ] 创建 reasoning/ 目录结构
- [ ] 创建 trading/ 目录结构
- [ ] 创建 evolution/ 目录结构
- [ ] 创建 utils/ 目录结构

### Phase 2: 迁移文件
- [ ] 迁移数据层文件
- [ ] 迁移分析层文件
- [ ] 迁移推理层文件
- [ ] 迁移交易层文件
- [ ] 迁移进化层文件
- [ ] 迁移工具层文件

### Phase 3: 更新导入
- [ ] 更新所有文件的导入路径
- [ ] 更新测试文件的导入
- [ ] 更新工具脚本的导入

### Phase 4: 清理验证
- [ ] 运行所有测试
- [ ] 验证功能完整性
- [ ] 更新文档

## 五、迁移原则

1. **保持功能不变**：只移动文件，不修改业务逻辑
2. **向后兼容**：在原位置保留重导出
3. **逐步迁移**：每次只迁移一个模块
4. **测试验证**：每步迁移后运行测试

## 六、风险控制

1. **导入路径破坏**：通过 __init__.py 重导出
2. **循环依赖**：使用延迟导入
3. **测试失败**：逐步迁移，每步验证

---

**开始实施**：从 Phase 1 开始，逐步创建目录结构。
