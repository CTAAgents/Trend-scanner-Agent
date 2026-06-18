# QuantNova 论文实现指南

> 版本：v1.0 | 创建日期：2026-06-18
> 本文档详细记录 QuantNova 如何将论文思想转化为代码实现

---

## 一、概述

QuantNova 的设计哲学建立在5篇核心论文/著作之上。本文档梳理每篇论文的核心思想、对应的代码模块、以及模块间的调用关系，帮助开发者理解"为什么这样设计"。

---

## 二、论文实现映射

### 2.1 Agentic AI for Factor Investing (arXiv:2603.14288)

**论文核心思想**：
- 闭环迭代因子发现：Generate → Execute → Evaluate → Gate → Memory → Feedback
- Agent驱动的因子进化，而非人工规则

**实现模块**：`FactorEvolutionEngine`

**代码路径**：`scripts/evolution/factor_evolution_engine.py`

**实现细节**：
```python
class FactorEvolutionEngine:
    """
    闭环因子进化引擎
    实现论文中的 Generate → Execute → Evaluate → Gate → Memory → Feedback 循环
    """
    def evolve(self, rounds: int = 5) -> EvolutionResult:
        for _ in range(rounds):
            # Generate: 因子生成
            candidates = self.generator.generate()
            # Execute: 执行计算
            executed = self.executor.execute(candidates)
            # Evaluate: IC/ICIR评估
            evaluated = self.evaluator.evaluate(executed)
            # Gate: 门控决策
            passed = self.gate.decide(evaluated)
            # Memory: 经验记忆
            self.memory.store(passed)
            # Feedback: 概念反馈
            self.feedback.generate(passed)
```

**调用关系**：
```
FactorEvolutionEngine
  ├── FactorGenerator (Generate)
  ├── FactorExecutor (Execute)
  ├── FactorEvaluator (Evaluate)
  ├── FactorGate (Gate)
  ├── FactorExperienceDB (Memory)
  └── ConceptualFeedbackGenerator (Feedback)
```

---

### 2.2 FactorEngine (arXiv:2603.16365)

**论文核心思想**：
- 因子即代码：因子是可执行的代码片段，而非固定公式
- 三大分离：逻辑分离、执行分离、评估分离

**实现模块**：`FactorGenerator` + `FactorEvaluator`

**代码路径**：
- `scripts/evolution/factor_generator.py`
- `scripts/evolution/factor_evaluator.py`

**实现细节**：
- 因子代码由 LLM 动态生成，存储在 `data/factor_knowledge.json`
- 执行层独立于生成层，支持并行计算
- 评估层独立于执行层，IC/ICIR/Walk-Forward 评估互不干扰

**数据流**：
```
LLM生成因子代码 → 代码验证 → 执行计算 → IC/ICIR评估 → 门控决策
     ↓              ↓           ↓           ↓
 FactorGenerator  Validator  Executor   Evaluator
```

---

### 2.3 FinCon

**论文核心思想**：
- 概念性语言反馈：用自然语言（而非数值）描述策略表现
- 信念传播：多个Agent间的信念传递和修正

**实现模块**：`BeliefPropagationManager` + `ConceptualFeedbackGenerator`

**代码路径**：`scripts/reasoning/`

**实现细节**：
```python
class BeliefPropagationManager:
    """
    信念传播管理器
    实现多Agent间的信念传递
    """
    def propagate(self, beliefs: List[Belief]) -> List[Belief]:
        # 鹰派信念
        hawk_beliefs = self.hawk.analyze()
        # 鸽派信念
        dove_beliefs = self.dove.analyze()
        # 信念融合
        return self.fuse(hawk_beliefs, dove_beliefs)

class ConceptualFeedbackGenerator:
    """
    概念性反馈生成器
    用自然语言描述策略表现
    """
    def generate(self, performance: dict) -> str:
        # 生成概念性反馈："该因子在趋势市场表现良好，但在震荡市场失效"
        return self.llm.generate_feedback(performance)
```

**扩展应用**：
- `DebateReasoningEngine`（鹰鸽辩论纠偏）是信念传播的扩展应用
- 辩论双方（鹰/鸽）的信念通过传播机制融合

---

### 2.4 GIFT

**论文核心思想**：
- LLM 引导的 RL 接口设计：让 LLM 指导强化学习的探索方向

**实现模块**：`RLInterfaceDesigner`

**代码路径**：`scripts/rl/rl_interface_designer.py`

**实现细节**：
- LLM 分析市场状态，建议 RL Agent 的探索策略
- 辅助设计 RL 的状态空间、动作空间、奖励函数

**当前状态**：
- 作为辅助模块，非架构核心
- 系统选择 PPO 作为主算法，GIFT 提供接口设计建议

---

### 2.5 Kevin J. Davey《构建盈利的算法交易系统》

**核心思想**：
- 策略工厂七步框架：SMART目标 → 寻找优势 → 可行性测试 → 回溯测试 → 蒙特卡洛 → 孵化 → 实盘
- 机械执行：过程重于预测，稳健性优于优化性

**实现模块**：4个风控模块

| Davey步骤 | 实现模块 | 代码路径 |
|-----------|----------|----------|
| 蒙特卡洛模拟 | `MonteCarloSimulator` | `scripts/evolution_tools/` |
| 策略孵化 | `StrategyIncubator` | `scripts/evolution_tools/` |
| 熔断机制 | `CircuitBreaker` | `scripts/evolution_tools/` |
| 多策略组合 | `StrategyPortfolio` | `scripts/strategies/` |

**实现细节**：
```python
class CircuitBreaker:
    """
    策略级熔断器
    当策略连续亏损达到阈值时，自动停止交易
    """
    def check(self, trades: List[Trade]) -> CircuitBreakerResult:
        # 检查最大回撤
        if self.max_drawdown > self.threshold:
            return CircuitBreakerResult(stop=True, reason="max_drawdown")
        # 检查连续亏损
        if self.consecutive_losses > self.max_losses:
            return CircuitBreakerResult(stop=True, reason="consecutive_losses")
        return CircuitBreakerResult(stop=False)

class StrategyPortfolio:
    """
    多策略组合管理
    固定比例头寸规模法 + 多市场/多时间框架分散
    """
    def allocate(self, strategies: List[Strategy]) -> List[Allocation]:
        # 等权分配
        weight = 1.0 / len(strategies)
        return [Allocation(strategy=s, weight=weight) for s in strategies]
```

---

## 三、哲学根基：推理重于规则

所有论文实现都遵循系统的核心哲学：**"推理重于规则"**。

| 论文 | 与"推理重于规则"的关系 |
|------|----------------------|
| Agentic AI | 因子进化由 Agent 驱动，不是人工规则 |
| FactorEngine | 因子由 LLM 生成，不是预设公式 |
| FinCon | 反馈是概念性的，不是数值阈值 |
| GIFT | RL 接口由 LLM 设计，不是手工定义 |
| Davey | 风控规则虽然机械执行，但其参数由推理层动态调整 |

**设计原则对照**：

| 原则 | 含义 | 论文来源 |
|------|------|----------|
| 推理重于规则 | 所有"规则"由推理层动态生成 | FinCon, GIFT |
| 因子即代码 | 因子是 LLM 生成的可执行代码 | FactorEngine |
| 门控不可调 | 门控阈值预设，防 p-hacking | Agentic AI |
| 技术面+基本面融合 | 技术指标提供时机，基本面提供方向 | 系统扩展 |
| 事件驱动 | 重大事件优先于技术信号 | 系统扩展 |

---

## 四、模块依赖关系图

```
                    ┌─────────────────────────────────────┐
                    │         LLM 推理层 (Layer 4)        │
                    │  ReasoningEngine + DebateEngine     │
                    └──────────────┬──────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│  因子进化层 (6)  │    │   策略层 (5)        │    │  RL层 (9)       │
│ FactorEvolution  │    │ TrendScanner        │    │ AgentPPO        │
│ Engine           │◄───│ CarryAnalyzer       │────│ WalkForwardRL   │
└────────┬────────┘    │ ArbitrageAnalyzer   │    └─────────────────┘
         │             └─────────────────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────────────┐
│  进化工具层 (7)  │    │   分析工具层 (8)    │
│ EvolutionManager │    │ StrategyHealth      │
│ CircuitBreaker   │    │ OverfittingDetector │
│ TradeJournal     │    │ PositionHealth      │
└─────────────────┘    └─────────────────────┘
         │                        │
         └───────────┬────────────┘
                     ▼
            ┌─────────────────┐
            │   记忆层 (3)    │
            │ UnifiedMemory   │
            │ Manager         │
            └─────────────────┘
```

---

## 五、扩展模块（非论文来源）

以下模块是系统迭代中新增的，非原始论文来源：

| 模块 | 功能 | 设计动机 |
|------|------|----------|
| 基本面分析 | 新闻抓取+供需数据+地缘政治 | 技术面+基本面融合 |
| 事件驱动引擎 | 事件优先级调度 | 重大事件优先于技术信号 |
| NLP模块 | 自然语言交互 | 用户体验优化 |
| Carry策略 | 期限结构套利 | 策略多元化 |
| 套利策略 | 跨期/跨品种价差 | 策略多元化 |

---

## 六、总结

QuantNova 的设计建立在坚实的论文基础之上，同时通过系统迭代扩展了原始论文未覆盖的领域。核心哲学"推理重于规则"贯穿所有模块，确保系统的一致性和可扩展性。

**关键洞察**：
1. 论文提供了设计原则，而非具体实现细节
2. 系统在保留论文核心思想的同时，进行了工程化适配
3. 扩展模块与原始论文思想兼容，而非冲突
4. "推理层"是统一所有模块的哲学框架

---

*本文档由 WorkBuddy 于 2026-06-18 创建，基于 QuantNova v0.1.0 版本*
