# 模块集成设计文档

> 版本：v1.0 | 创建日期：2026-06-17
> 状态：待实施

## 一、问题概述

### 1.1 现状

论文吸收任务（arXiv:2605.01300）已完成所有模块的实现和测试，但存在 **4 个孤立模块** 未集成到核心系统：

| 模块 | 文件 | 状态 |
|------|------|------|
| Walk-Forward 验证框架 | `walk_forward_validator.py` | 孤立 |
| 可见图算子注入因子生成器 | `visibility_graph_operator.py` | 孤立 |
| 多周期 VGRSI 一致性因子 | `visibility_graph.py` (类) | 完全孤立 |
| 波动幅度止损锚点 | `volatility_anchor.py` | 孤立 |

### 1.2 目标

将所有孤立模块集成到核心系统，使其能够被正常使用。

---

## 二、集成方案

### 2.1 导出新模块到 `__init__.py`

**目标**: 让新模块可以被其他模块正常 import。

**修改文件**: `scripts/trend_scanner/__init__.py`

**导出内容**:
```python
from .visibility_graph import VGRSI, MultiTimeframeVGRSI, MultiTimeframeVGRSIFactor, consensus_factor
from .walk_forward_validator import WalkForwardValidator, WalkForwardConfig
from .visibility_graph_operator import VisibilityGraphOperator
from .volatility_anchor import VolatilityAnchor
```

### 2.2 Walk-Forward 验证集成到因子进化引擎

**目标**: 在因子评估阶段使用 Walk-Forward 验证，防止参数过拟合。

**修改文件**: `scripts/trend_scanner/factor_evolution_engine.py`

**集成方式**:
1. 在 `FactorEvolutionEngine.__init__()` 中初始化 `WalkForwardValidator`
2. 在 `evaluate_factor()` 方法中，当启用 Walk-Forward 时，使用滚动窗口验证
3. 只有通过 Walk-Forward 验证的因子才能被晋升

**伪代码**:
```python
class FactorEvolutionEngine:
    def __init__(self, ..., use_walk_forward=False):
        if use_walk_forward:
            self.walk_forward_validator = WalkForwardValidator()
    
    def evaluate_factor(self, factor_code, prices):
        # 原有评估逻辑
        ic, icir = self._calculate_ic_icir(factor_code, prices)
        
        # Walk-Forward 验证（可选）
        if self.use_walk_forward:
            wf_result = self.walk_forward_validator.validate(
                prices, factor_func, param_space, optimize_func
            )
            if wf_result.pass_rate < 0.5:
                return {'status': 'rejected', 'reason': 'Walk-Forward 验证失败'}
        
        return {'ic': ic, 'icir': icir, ...}
```

### 2.3 可见图算子集成到因子生成器

**目标**: 在 LLM prompt 中注入可见图算子描述，扩展因子搜索空间。

**修改文件**: `scripts/trend_scanner/factor_generator.py`

**集成方式**:
1. 在 `FactorGenerator.__init__()` 中初始化 `VisibilityGraphOperator`
2. 在 `_build_generation_prompt()` 方法中，追加可见图算子描述和示例

**伪代码**:
```python
class FactorGenerator:
    def __init__(self, ...):
        self.visibility_operator = VisibilityGraphOperator()
    
    def _build_generation_prompt(self, market_context, research_report=None):
        # 原有 prompt
        base_prompt = super()._build_generation_prompt(...)
        
        # 追加可见图算子描述
        visibility_desc = self.visibility_operator.get_operator_descriptions()
        visibility_examples = self.visibility_operator.get_example_factors()
        
        enhanced_prompt = f"""
{base_prompt}

## 可见图类因子范式（新增）

### 可用算子
{visibility_desc}

### 示例因子
{visibility_examples}
"""
        return enhanced_prompt
```

### 2.4 多周期 VGRSI 因子纳入种子因子池

**目标**: 将 MultiTimeframeVGRSIFactor 作为种子因子，参与因子进化。

**新增文件**: `tools/add_multi_timeframe_vgrsi_factor.py`

**集成方式**:
1. 创建脚本将因子代码添加到 `data/seed_factors.json`
2. 因子代码使用 `consensus_factor()` 函数

**因子代码模板**:
```python
def factor(df, window_m1=50, window_m5=100, window_m30=150):
    """多周期 VGRSI 一致性因子"""
    from scripts.trend_scanner.visibility_graph import consensus_factor
    
    # 需要多时间框架数据，这里使用单时间框架模拟
    # 实际使用时需要提供多时间框架数据
    prices_dict = {
        'M1': df['close'],
    }
    
    result = consensus_factor(prices_dict)
    return result['consensus']
```

### 2.5 波动幅度止损锚点集成到 Reasoner

**目标**: 在 Reasoner 推理时，提供波动幅度止损锚点作为参考。

**修改文件**: `scripts/trend_scanner/reasoning.py`

**集成方式**:
1. 在 `ReasoningEngine.__init__()` 中初始化 `VolatilityAnchor`
2. 在 `generate_trading_brief()` 方法中，计算波动幅度锚点
3. 将锚点信息注入 Reasoner 的 prompt

**伪代码**:
```python
class ReasoningEngine:
    def __init__(self, ...):
        self.volatility_anchor = VolatilityAnchor(window=20, multiplier=2.0)
    
    def generate_trading_brief(self, market_context, positions):
        # 计算波动幅度锚点
        for pos in positions:
            df = self.get_price_data(pos['symbol'])
            anchor_info = self.volatility_anchor.get_anchor_info(
                df, pos['entry_price'], pos['direction']
            )
            pos['volatility_anchor'] = anchor_info
        
        # 构建 prompt
        prompt = f"""
        市场上下文：{market_context}
        
        持仓信息（含波动幅度止损锚点）：
        {positions}
        
        请根据以上信息生成交易决策简报。
        波动幅度止损锚点是基于近期市场波动计算的参考值，你可以根据当前市场状态调整。
        """
        
        return self.llm_client.generate(prompt)
```

---

## 三、集成顺序

| 步骤 | 任务 | 依赖 | 验证方式 |
|------|------|------|----------|
| 1 | 导出新模块到 `__init__.py` | 无 | import 测试 |
| 2 | 纳入多周期 VGRSI 因子到种子因子池 | 无 | 种子因子池包含新因子 |
| 3 | 集成可见图算子到因子生成器 | 步骤 1 | LLM prompt 包含算子描述 |
| 4 | 集成 Walk-Forward 验证到因子进化引擎 | 步骤 1 | 因子评估使用 Walk-Forward |
| 5 | 集成波动幅度止损锚点到 Reasoner | 步骤 1 | Reasoner prompt 包含锚点信息 |

---

## 四、测试计划

### 4.1 集成测试

- 测试 `__init__.py` 导出是否正常
- 测试因子进化引擎是否使用 Walk-Forward 验证
- 测试因子生成器是否包含可见图算子描述
- 测试 Reasoner 是否包含波动幅度锚点信息

### 4.2 端到端测试

- 测试完整流程：扫描 → 因子生成 → 因子评估 → 因子进化
- 验证新模块在实际流程中是否正常工作

---

## 五、风险提示

1. **兼容性**: 修改核心模块可能影响现有功能
2. **性能**: Walk-Forward 验证会增加计算时间
3. **复杂度**: 集成后系统复杂度增加

---

*本文档是模块集成的设计规范。*
