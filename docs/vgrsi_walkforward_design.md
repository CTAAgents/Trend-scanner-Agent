# VGRSI 因子与 Walk-Forward 验证框架设计文档

> 版本：v1.2 | 创建日期：2026-06-17 | 更新日期：2026-06-17
> 状态：已完成（P0/P1/P2/P3 全部完成）

## 一、项目概述

### 1.1 目标

吸收论文 "Visibility Graphs Can Make Money in Financial Markets" (arXiv:2605.01300) 的核心思想，实现 VGRSI 因子并集成到系统的因子进化引擎中。同时实现 Walk-Forward 验证框架，用于防止参数过拟合。

### 1.2 背景

论文提出 VGRSI (Visibility Graph Relative Strength Index)，将金融时间序列转换为可见图网络，利用价格点之间的几何可见关系替代传统 RSI 的简单价格变化。回测显示 Sharpe 比率 2.55-3.6，最大回撤 10-18%。

### 1.3 范围

- 实现 VGRSI 因子（A0/A1 两种聚合模式）
- 实现 Walk-Forward 验证框架
- 将 VGRSI 因子添加到种子因子池
- 编写完整测试用例

---

## 二、技术设计

### 2.1 VGRSI 因子

#### 核心算法

**可见性关系判断**（论文公式 1）：

```
p[k] < p[j] + (p[i] - p[j]) * (j - k) / (j - i)
对所有 k ∈ (i, j)
```

其中：
- p[i], p[j] 分别是时间点 i 和 j 的价格
- p[k] 是中间点 k 的价格
- 如果所有中间点都在连接线以下，则 j 从 i 可见

#### 两种聚合模式

**A0（均值聚合）- 趋势持续性**：
```
VGRSI_pos(i) = mean(f(i,j)) for j where f(i,j) > 0
VGRSI_neg(i) = mean(|f(i,j)|) for j where f(i,j) < 0
VGRSI(i) = 100 * VGRSI_pos / (VGRSI_pos + VGRSI_neg)
```

**A1（比率聚合）- 突破脉冲**：
```
VGRSI_pos(i) = count(j where f(i,j) > 0) / count(j where f(i,j) < 0)
VGRSI_neg(i) = 1
VGRSI(i) = 100 * VGRSI_pos / (VGRSI_pos + VGRSI_neg)
```

#### 接口定义

```python
class VisibilityGraph:
    @staticmethod
    def backward_visibility(prices: np.ndarray, i: int, j: int) -> bool
    @staticmethod
    def compute_visibility_matrix(prices: np.ndarray, window_size: int) -> Dict[int, list]

class VGRSI:
    def __init__(self, window_size=100, aggregation_mode='A0', 
                 threshold_upper=70, threshold_lower=30)
    def calculate(self, prices: np.ndarray) -> np.ndarray
    def generate_signals(self, vgrsi_values: np.ndarray) -> np.ndarray

class MultiTimeframeVGRSI:
    def __init__(self, timeframe_configs, threshold_upper, threshold_lower)
    def calculate_multi_timeframe(self, prices_dict: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]
    def generate_consensus_signals(self, prices_dict: Dict[str, np.ndarray]) -> np.ndarray
```

### 2.2 Walk-Forward 验证框架

#### 核心逻辑

- **优化窗口（IS）**: 30 天
- **测试窗口（OOS）**: 7 天
- **步长**: 7 天
- **滚动方式**: 每 7 天向前滚动一次

#### 验证标准

| 指标 | 阈值 | 说明 |
|------|------|------|
| 最小交易次数 | 5 | OOS 窗口内至少 5 次交易 |
| 最小夏普比率 | 0.5 | OOS Sharpe >= 0.5 |
| 最大回撤 | 20% | OOS 最大回撤 <= 20% |
| 最小胜率 | 40% | OOS 胜率 >= 40% |
| IS/OOS 一致性 | 50% | OOS Sharpe >= IS Sharpe * 50% |

#### 接口定义

```python
@dataclass
class WalkForwardConfig:
    optimization_window: int = 30
    test_window: int = 7
    step_size: int = 7
    min_trades: int = 5
    min_sharpe: float = 0.5
    max_drawdown: float = 0.2
    min_win_rate: float = 0.4

class WalkForwardValidator:
    def __init__(self, config: WalkForwardConfig)
    def validate(self, prices: pd.Series, factor_func: Callable, 
                 param_space: Dict, optimize_func: Callable) -> WalkForwardResult
```

---

## 三、文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `scripts/trend_scanner/visibility_graph.py` | 模块 | VGRSI 因子实现 |
| `scripts/trend_scanner/walk_forward_validator.py` | 模块 | Walk-Forward 验证框架 |
| `tests/test_visibility_graph.py` | 测试 | VGRSI 单元测试（23 个） |
| `tests/test_walk_forward_validator.py` | 测试 | Walk-Forward 单元测试（17 个） |
| `tools/add_vgrsi_factor.py` | 工具 | 添加 VGRSI 到种子因子池 |

---

## 四、与现有系统的集成

### 4.1 因子进化引擎

VGRSI 作为种子因子进入候选池，参与 Generate→Eval→Gate→Memory 闭环。

### 4.2 参数优化

Walk-Forward 验证与贝叶斯优化互补：
- 贝叶斯负责搜索最优参数
- Walk-Forward 负责验证参数的泛化能力

### 4.3 因子生成器

可见图算子可注入因子生成器的 prompt，扩展因子搜索空间。

---

## 五、风险提示

1. **回测可信度**: 论文只测了 3 个资产、2 年数据，样本有限
2. **参数敏感性**: VGRSI 有 6+ 个参数，需要滚动优化
3. **多周期信号稀疏**: 三周期同时确认的条件很严格，信号可能稀疏

---

## 六、任务进度

| 优先级 | 任务 | 状态 | 完成日期 | 说明 |
|--------|------|------|----------|------|
| P0 | VGRSI 因子实现 + 纳入因子库 | ✅ 完成 | 2026-06-17 | visibility_graph.py + 种子因子池 |
| P1 | Walk-Forward 验证框架 | ✅ 完成 | 2026-06-17 | walk_forward_validator.py |
| P1 | 可见图算子注入因子生成器 | ✅ 完成 | 2026-06-17 | visibility_graph_operator.py |
| P2 | 多周期 VGRSI 一致性因子 | ✅ 完成 | 2026-06-17 | MultiTimeframeVGRSIFactor 类 |
| P3 | 波动幅度中位数作为止损锚点 | ✅ 完成 | 2026-06-17 | volatility_anchor.py |

---

## 七、后续任务设计（待实施）

### 7.1 可见图算子注入因子生成器（P1）

**目标**: 在 `factor_generator.py` 的 LLM prompt 中增加"可见图类因子"作为可选范式。

**设计要点**:
- 将可见性关系计算封装为 `VisibilityGraph` 工具类
- LLM 可基于此范式自由组合：可见性 + 均值、可见性 + 波动率等
- 扩展因子搜索空间，突破传统技术指标的组合限制

### 7.2 多周期 VGRSI 一致性因子（P2）

**目标**: 将 MultiTimeframeVGRSI 的共识信号封装为独立因子。

**设计要点**:
- 使用 M1、M5、M30 三个时间框架
- 只有三周期同向确认才产生信号
- 作为复合因子纳入多因子模型

### 7.3 波动幅度中位数作为止损锚点（P3）

**目标**: 在 Reasoner 推理时提供止损参考锚点。

**设计要点**:
- 计算近期 N 根 K 线高度的中位数
- 乘以系数 Z 作为止损参考
- Reasoner 可动态调整 N 和 Z

---

*本文档是 VGRSI 因子和 Walk-Forward 验证框架的设计规范。*
