# Davey 框架补充实施计划

> 版本：v1.0 | 创建日期：2026-06-17
> 状态：已完成

## 一、项目概述

### 1.1 目标

基于 Kevin J. Davey《构建盈利的算法交易系统》中的关键缺失模块，补充 QuantNova 系统的风控和验证能力。

### 1.2 背景

对比分析发现 Davey 框架中有 4 个关键模块我们尚未实现：

| 优先级 | 模块 | Davey 原文位置 | 核心价值 |
|--------|------|----------------|----------|
| **P0** | 蒙特卡洛模拟 | Step 5 | 评估最坏情况/破产风险 |
| **P0** | 策略孵化机制 | Step 6 | 回测到实盘的桥梁 |
| **P1** | 停止交易阈值 | Step 7 | 策略级熔断机制 |
| **P1** | 多策略组合管理 | Step 7 | 分散化权益曲线 |

### 1.3 范围

- 新增 4 个模块
- 新增 4 个测试文件
- 集成到现有系统（reasoner/scanner/portfolio）
- 更新文档

---

## 二、任务清单

| 任务 | 描述 | 状态 | 交付物 |
|------|------|------|--------|
| **T1** | 蒙特卡洛模拟模块 | 待实施 | `monte_carlo.py` + `test_monte_carlo.py` |
| **T2** | 策略孵化模块 | 待实施 | `strategy_incubator.py` + `test_strategy_incubator.py` |
| **T3** | 停止交易阈值模块 | 待实施 | `circuit_breaker.py` + `test_circuit_breaker.py` |
| **T4** | 多策略组合扩展 | 待实施 | 扩展 `portfolio.py` + `test_portfolio_extended.py` |
| **T5** | 系统集成 | 待实施 | 修改 reasoner/scanner 集成新模块 |
| **T6** | 文档更新 | 待实施 | 更新 SKILL.md/README.md/MEMORY.md |

---

## 三、技术设计

### 3.1 T1: 蒙特卡洛模拟模块

**文件**：`scripts/trend_scanner/monte_carlo.py`（新建）

**核心功能**：

```python
class MonteCarloSimulator:
    """蒙特卡洛模拟器"""
    
    def __init__(self, n_simulations: int = 10000, 
                 confidence_levels: List[float] = [0.95, 0.99]):
        self.n_simulations = n_simulations
        self.confidence_levels = confidence_levels
    
    def simulate(self, trades: List[float], 
                 initial_capital: float = 100000) -> MonteCarloResult:
        """
        对交易结果进行随机重排模拟
        
        参数:
            trades: 每笔交易的盈亏列表（如 [+500, -300, +800, ...]）
            initial_capital: 初始资金
            
        返回:
            MonteCarloResult 包含：
            - equity_curves: n_simulations 条模拟权益曲线
            - max_drawdown_distribution: 最大回撤分布
            - ruin_probability: 破产概率
            - percentile_stats: 各置信水平的统计量
            - worst_case: 最差情景
        """
    
    def calculate_ruin_probability(self, trades: List[float],
                                    ruin_threshold: float = 0.5) -> float:
        """
        计算破产概率
        
        参数:
            ruin_threshold: 破产阈值（如 0.5 表示资金降至50%为破产）
        """
    
    def calculate_expected_drawdown(self, trades: List[float]) -> Dict:
        """计算预期最大回撤分布"""
```

**数据模型**：

```python
@dataclass
class MonteCarloResult:
    """蒙特卡洛模拟结果"""
    n_simulations: int
    initial_capital: float
    final_capital_median: float
    final_capital_mean: float
    max_drawdown_median: float
    max_drawdown_95: float    # 95%置信水平
    max_drawdown_99: float    # 99%置信水平
    ruin_probability: float   # 破产概率
    sharpe_ratio_median: float
    win_rate_median: float
    worst_case: Dict          # 最差情景详情
    equity_curves: np.ndarray # 模拟权益曲线（可选保存）
```

**关键算法**：

1. **交易重排**：从 trades 列表中随机抽取（有放回），生成 n_simulations 条权益曲线
2. **破产检测**：权益降至 ruin_threshold 以下时标记为破产
3. **统计输出**：中位数、均值、标准差、各置信水平分位数

**集成点**：
- `reasoner.py`：在推理时注入蒙特卡洛评估结果
- `walk_forward_validator.py`：Walk-Forward 通过后自动运行蒙特卡洛验证

---

### 3.2 T2: 策略孵化模块

**文件**：`scripts/trend_scanner/strategy_incubator.py`（新建）

**核心功能**：

```python
class StrategyIncubator:
    """
    策略孵化器
    
    在投入真金白银前，用实盘数据进行最终验证。
    策略在实时市场环境中运行，但不承担风险，通常持续3-6个月。
    """
    
    def __init__(self, incubation_days: int = 90,
                 max_deviation: float = 0.3):
        """
        参数:
            incubation_days: 孵化期天数（默认90天）
            max_deviation: 最大允许偏差（回测 vs 实盘）
        """
    
    def start_incubation(self, strategy_id: str,
                          strategy_config: Dict) -> IncubationSession:
        """开始孵化会话"""
    
    def record_signal(self, strategy_id: str,
                       timestamp: pd.Timestamp,
                       signal: float, 
                       market_state: Dict) -> None:
        """记录实盘信号"""
    
    def evaluate(self, strategy_id: str) -> IncubationResult:
        """
        评估孵化结果
        
        对比回测预期 vs 实盘表现，输出：
        - 信号一致性
        - 延迟分析
        - 偏差统计
        - 是否通过孵化
        """
    
    def get_all_sessions(self) -> List[IncubationSession]:
        """获取所有孵化会话"""
```

**数据模型**：

```python
@dataclass
class IncubationSession:
    """孵化会话"""
    strategy_id: str
    start_time: pd.Timestamp
    end_time: Optional[pd.Timestamp]
    status: str  # "active" | "completed" | "failed"
    expected_sharpe: float
    expected_win_rate: float
    expected_max_drawdown: float
    actual_signals: List[Dict]  # 实盘信号记录
    
@dataclass
class IncubationResult:
    """孵化评估结果"""
    strategy_id: str
    passed: bool
    signal_consistency: float  # 信号一致性 (0-1)
    latency_avg: float         # 平均信号延迟（秒）
    deviation_sharpe: float    # 夏普偏差
    deviation_win_rate: float  # 胜率偏差
    deviation_drawdown: float  # 回撤偏差
    recommendation: str        # "approve" | "reject" | "extend"
    details: str
```

**孵化流程**：

```
1. 策略通过 Walk-Forward + 蒙特卡洛
2. 创建 IncubationSession，记录回测预期指标
3. 实盘运行策略（不交易），记录每个信号
4. 孵化期结束后，对比回测 vs 实盘
5. 偏差超过阈值 → reject，否则 → approve
```

**集成点**：
- `reasoner.py`：推理时检查策略是否通过孵化
- `config.json`：新增 `incubation` 配置段

---

### 3.3 T3: 停止交易阈值模块

**文件**：`scripts/trend_scanner/circuit_breaker.py`（新建）

**核心功能**：

```python
class CircuitBreaker:
    """
    策略级熔断机制
    
    为每个策略预设停止交易的阈值，防止失效策略造成灾难性亏损。
    """
    
    def __init__(self, config: Dict = None):
        """
        默认配置:
        - max_loss_per_strategy: 每策略最大亏损（如 $5000）
        - max_drawdown_pct: 最大回撤百分比（如 20%）
        - max_consecutive_losses: 最大连续亏损次数（如 10）
        - cooldown_days: 熔断后冷却期（如 30天）
        """
    
    def check(self, strategy_id: str,
              equity_curve: pd.Series,
              trades: List[Dict]) -> CircuitBreakerResult:
        """
        检查策略是否触发熔断
        
        返回:
            CircuitBreakerResult 包含：
            - triggered: bool
            - reason: str
            - metrics: Dict
        """
    
    def reset(self, strategy_id: str) -> None:
        """重置策略的熔断状态"""
    
    def get_status(self, strategy_id: str) -> Dict:
        """获取策略的熔断状态"""
    
    def get_all_status(self) -> Dict[str, Dict]:
        """获取所有策略的熔断状态"""
```

**数据模型**：

```python
@dataclass
class CircuitBreakerResult:
    """熔断检查结果"""
    strategy_id: str
    triggered: bool
    trigger_reason: str
    metrics: Dict  # 当前指标值
    cooldown_remaining: int  # 冷却剩余天数
    recommendation: str  # "continue" | "pause" | "terminate"
```

**熔断规则**：

| 规则 | 默认阈值 | 说明 |
|------|----------|------|
| 最大亏损 | $5000/合约 | 累计亏损超过阈值 |
| 最大回撤 | 20% | 权益回撤超过阈值 |
| 连续亏损 | 10次 | 连续亏损次数超过阈值 |
| 冷却期 | 30天 | 熔断后暂停交易的天数 |

**集成点**：
- `risk_management.py`：在每笔交易前检查熔断状态
- `scanner.py`：扫描时跳过已熔断的策略
- `config.json`：新增 `circuit_breaker` 配置段

---

### 3.4 T4: 多策略组合扩展

**文件**：扩展 `scripts/trend_scanner/portfolio.py`

**新增功能**：

```python
class StrategyPortfolio:
    """
    多策略组合管理器
    
    扩展现有 PortfolioManager，增加策略层面的管理：
    - 策略间相关性控制
    - 策略权重动态调整
    - 组合权益曲线分析
    - 策略级风险预算
    """
    
    def __init__(self, max_strategies: int = 10,
                 max_correlation: float = 0.7,
                 rebalance_frequency: int = 30):
        """
        参数:
            max_strategies: 最大策略数
            max_correlation: 策略间最大相关性
            rebalance_frequency: 再平衡频率（天）
        """
    
    def add_strategy(self, strategy_id: str,
                      weight: float,
                      equity_curve: pd.Series) -> None:
        """添加策略到组合"""
    
    def remove_strategy(self, strategy_id: str) -> None:
        """从组合中移除策略"""
    
    def calculate_portfolio_equity(self) -> pd.Series:
        """计算组合权益曲线"""
    
    def calculate_diversification_ratio(self) -> float:
        """计算分散化比率"""
    
    def optimize_weights(self, target_vol: float = 0.15) -> Dict[str, float]:
        """
        优化策略权重（等风险贡献或目标波动率）
        """
    
    def analyze_correlation(self) -> pd.DataFrame:
        """分析策略间相关性"""
    
    def get_portfolio_stats(self) -> Dict:
        """获取组合统计（夏普/回撤/胜率等）"""
```

**集成点**：
- `scan_opportunities.py`：扫描后可选输出组合建议
- `reasoner.py`：推理时考虑组合层面的风险

---

## 四、测试用例

### T1: 蒙特卡洛模拟测试

| 测试场景 | 输入 | 预期输出 | 状态 |
|----------|------|----------|------|
| 全盈利交易 | [100, 200, 300] | 破产概率=0 | 待实施 |
| 全亏损交易 | [-100, -200, -300] | 破产概率=1 | 待实施 |
| 混合交易 | [+500, -300, +800, -200] | 破产概率<0.5 | 待实施 |
| 空交易列表 | [] | 返回空结果 | 待实施 |
| 大样本统计 | 1000笔随机交易 | 95%CI合理 | 待实施 |

### T2: 策略孵化测试

| 测试场景 | 输入 | 预期输出 | 状态 |
|----------|------|----------|------|
| 信号一致 | 回测+实盘信号相同 | passed=True | 待实施 |
| 信号偏差大 | 回测+实盘信号差异>30% | passed=False | 待实施 |
| 孵化期不足 | 运行<30天 | status="active" | 待实施 |
| 孵化期完成 | 运行>=90天 | status="completed" | 待实施 |

### T3: 停止交易阈值测试

| 测试场景 | 输入 | 预期输出 | 状态 |
|----------|------|----------|------|
| 未触发 | 亏损<$5000 | triggered=False | 待实施 |
| 触发亏损 | 亏损>$5000 | triggered=True | 待实施 |
| 触发回撤 | 回撤>20% | triggered=True | 待实施 |
| 触发连续亏损 | 连续10次亏损 | triggered=True | 待实施 |
| 冷却期 | 熔断后30天内 | cooldown_remaining>0 | 待实施 |

### T4: 多策略组合测试

| 测试场景 | 输入 | 预期输出 | 状态 |
|----------|------|----------|------|
| 单策略 | 1个策略 | 组合=该策略 | 待实施 |
| 多策略 | 3个不相关策略 | 分散化比率>1 | 待实施 |
| 高相关策略 | 2个相关>0.7的策略 | 警告或降低权重 | 待实施 |
| 权重优化 | 目标波动率15% | 权重总和=1 | 待实施 |

---

## 五、时间表

| 阶段 | 时间 | 交付物 | 验证指标 |
|------|------|--------|----------|
| **Phase 1** | Day 1-2 | T1 蒙特卡洛模块 | 5个测试通过 |
| **Phase 2** | Day 3-4 | T2 策略孵化模块 | 4个测试通过 |
| **Phase 3** | Day 5 | T3 停止交易阈值 | 5个测试通过 |
| **Phase 4** | Day 6-7 | T4 多策略组合扩展 | 4个测试通过 |
| **Phase 5** | Day 8 | T5 系统集成 | 集成测试通过 |
| **Phase 6** | Day 9 | T6 文档更新 | 文档完整 |

---

## 六、进度跟踪

### 2026-06-17
- [x] 完成对比分析（docs/davey_comparison.md）
- [x] 完成实施计划（本文档）
- [ ] Phase 1: 蒙特卡洛模拟模块
- [ ] Phase 2: 策略孵化模块
- [ ] Phase 3: 停止交易阈值模块
- [ ] Phase 4: 多策略组合扩展
- [ ] Phase 5: 系统集成
- [ ] Phase 6: 文档更新

---

## 七、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 蒙特卡洛计算量大 | 性能问题 | 使用 NumPy 向量化 + 可选采样 |
| 孵化期需要长期运行 | 验证周期长 | 支持加速孵化（压缩时间窗口） |
| 熔断阈值难以设定 | 过于敏感/迟钝 | 提供默认值 + 用户可配置 |
| 组合优化复杂度高 | 实现难度大 | 先实现等权重，再优化 |

---

*本文档为 Davey 框架补充的实施路线图，每次代码修改前参考本文档和对应模块的详细设计。*
