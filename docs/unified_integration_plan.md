# 统一整合实施方案

> 版本：v1.0 | 创建日期：2026-06-17
> 状态：进行中

## 一、概述

本文档合并两项独立工作流，按依赖关系重新排序为统一实施路线：

| 工作流 | 内容 | 目标 |
|--------|------|------|
| **A: quant-strategy-builder 整合** | 吸收方法论层（验证矩阵、检查点、交付清单） | 增强 Reasoner 推理框架的结构化程度和可追溯性 |
| **B: TqSdk 70 指标整合** | 接入 TqSdk ta 模块的完整指标体系 | 扩展交易信号的信息维度（成交量结构、多空博弈、通道系统） |

### 汇合点

两条工作流在 **Reasoner Agent** 处汇合：
- 方法论（A）提供推理框架模板
- 新指标（B）提供更宽的信息维度
- 最终效果：Reasoner 的输出既有结构化方法支撑，又有更丰富的市场信息输入

---

## 二、依赖关系图

```
Phase 1 (并行)
  ├── [A1] STRATEGY_DESIGN_METHODOLOGY.md   ─── 独立，无依赖
  └── [B1] 修复 sync_indicators.py          ─── 独立，无依赖
               │
Phase 2        │
  ├── [B2] indicator_hub.py                 ← 依赖 B1
  └── [B3] multi_dimension_screener.py      ← 依赖 B2
               │
Phase 3        │
  ├── [A2] Reasoner SKILL.md 增强           ← 依赖 A1 + B3
  ├── [A3] DATA_FORMATS.md 交付清单         ← 依赖 A1
  └── [A4] validation_matrix.py             ← 依赖 A1
               │
Phase 4        │
  ├── [B4] Scanner 接入新指标层             ← 依赖 B2 + B3
  └── [B5] Reasoner 上下文增强             ← 依赖 A2 + B3
```

---

## 三、Phase 1：方法论文档 + 指标计算基础（并行）

### [A1] 新建 STRATEGY_DESIGN_METHODOLOGY.md

**文件**：`agents/shared/STRATEGY_DESIGN_METHODOLOGY.md`

| 章节 | 来源 | 适配要点 |
|------|------|----------|
| 五步推理框架 | quant-strategy-builder 五阶段流水线 | Frame→Translate→Change→Proof→Deliver，映射到 Reasoner 现有推理流程 |
| 验证矩阵 | validation-matrix.md | 改动类型 → 最低验证标准 → 对接到 walk_forward_validator / overfitting_auditor / factor_evaluator |
| 中国市场约束检查点 | China-Market Checkpoints | 聚焦期货（主力换月、夜盘、保证金、交割月），A股部分标注远期 |
| 交付清单模板 | Delivery Checklist | 扩展 TradingBrief 输出字段 |

**产出物**：1 个 markdown 文件，纯文档，无代码修改。

### [B1] 修复 sync_indicators.py — 真正接入 TqSdk ta

**文件**：`tools/sync_indicators.py`（修改）

**问题**：当前代码全部是 pandas 手写，一行 tqsdk import 都没有。

**方案**：A. 子进程隔离。扩展 `tqsdk_worker.py`，增加 `--compute-indicators` 模式：
```
进程外：读取 DuckDB K线 → JSON IPC → tqsdk_worker.py
进程内：from tqsdk import ta → 批量计算 70 个指标 → JSON IPC 返回
进程外：接收结果 → 写入 DuckDB indicators 表
```

**关键约束**：
- TqSdk `ta` 模块的函数签名统一：`ta.XXX(df, n, ...)`
- 输入 DataFrame 必须有 open/high/low/close/volume 列
- 70 个指标分 8 类：均线(9)、趋势(6)、震荡(12)、动量(10)、波动率(5)、成交量(18)、通道(2)、其他(8)
- 期权相关（OPTION_GREEKS/IMPV/VALUE/VOLATILITY_CURVE）期货场景跳过

**产出物**：修改 `sync_indicators.py`，新增或修改 `tqsdk_worker.py`。

---

## 四、Phase 2：统一加载层 + 多维度筛选

### [B2] 新建 indicator_hub.py

**文件**：`scripts/trend_scanner/indicator_hub.py`（新建）

| 组件 | 功能 |
|------|------|
| `IndicatorHub.load(symbol)` | 从 DuckDB indicators 表读取预计算指标 + 运行 IndicatorEngine → 合并返回 |
| `IndicatorHub.get_dimension(dim)` | 按维度返回指标组：trend / momentum / volume / volatility / channel |
| `field_name_map` | TqSdk 输出列名 ↔ IndicatorEngine 列名的双向映射 |
| 缓存机制 | 同一品种同一交易日缓存计算结果 |

**注意**：IndicatorHub 不替代 IndicatorEngine。IndicatorEngine 继续负责 C 类高级指标（ER/R²/Hurst/TSI/ADX分位数等），IndicatorHub 只做加载+合并，不重复计算。

### [B3] 新建 multi_dimension_screener.py

**文件**：`scripts/trend_scanner/multi_dimension_screener.py`（新建）

**数据模型**：
```python
@dataclass
class DimensionScore:
    name: str          # 维度名称
    weight: float      # 权重 (0-1)
    indicators: Dict[str, float]  # 各指标归一化得分
    composite: float   # 维度综合分
    signal: str        # 方向信号: BULLISH / BEARISH / NEUTRAL

@dataclass
class MultiDimensionResult:
    symbol: str
    dimensions: List[DimensionScore]
    overall_score: float   # 综合得分 (-1 到 +1)
    confidence: float       # 置信度 (0-1)
    signal: str             # LONG / SHORT / NEUTRAL
```

**权重框架**：

| 维度 | 权重 | 指标 | 判定逻辑 |
|------|------|------|----------|
| 趋势 | 30% | ADX, DMI(+DI/-DI), SAR, EMA20斜率, DKX | ADX>25偏多, ADX>40强趋势 |
| 动量 | 25% | MACD(DIF/DEA/柱), ROC, MTM, RSI, ADTM | MACD金叉+柱放大偏多 |
| 成交量 | 20% | OBV趋势, MFI, VR, AD累积, WVAD | OBV同向确认, MFI在50以上偏多 |
| 波动率 | 15% | ATR比率, BOLL位置, BBIBOLL宽度, PRICEOSC | ATR扩张+突破BOLL上轨偏多 |
| 通道 | 10% | Donchian位置, HCL方向, B3612趋势, ENV位置 | 价格在通道上沿附近偏多 |

**归一化规则**：
- 有界指标（RSI/MFI/VR）：线性映射到 (-1, +1)，以 50 为中性点
- 方向性指标（DI+/DI-/MACD柱）：符号即信号，幅度做置信度
- 通道/均线位置：价格在均线上方为正，下方为负
- 成交量指标：背离扣分，同向加分

**产出物**：1 个新模块 + 配套测试文件 `tests/test_multi_dimension_screener.py`。

---

## 五、Phase 3：Reasoner 推理框架增强 + 验证矩阵

### [A2] Reasoner SKILL.md 推理流程增强

**文件**：`agents/reasoner/SKILL.md`（修改）

**改动点**：

1. **在"推理流程"章节中嵌入五步框架**：

```
原流程：接收信号 → 检索经验 → LLM 推理 → 生成简报

新流程（五步框架）：
  Step 1. Frame The Edge（框定优势）
    - 品种特征（黑色/能化/有色）
    - 当前市场阶段（趋势/震荡/转折）
    - 持仓背景（已有仓位则加权）
  
  Step 2. Translate Into Parts（翻译为决策模块）
    - 多维度筛选得分 → 趋势/动量/成交量/波动率/通道
    - 历史经验相似度 → 经验记忆检索
    - 止损锚点 → 波动率锚点参考
    - 市场约束 → 夜盘/主力切换/交割月
  
  Step 3. Choose Smallest Safe Change（选择最小安全改动）
    - 已有仓位 → 调整 vs 维持 vs 退出
    - 无仓位 → 是否入场
    - 改动原则：参数调优优先于策略逻辑变更
  
  Step 4. Decide The Proof Up Front（预先定义验证标准）
    - 引用 validation_matrix 匹配改动类型的验证要求
    - 标注建议信心等级对应的历史胜率区间
  
  Step 5. Summarize Like A Research Engineer（研究员式交付）
    - 输出 TradingBrief + delivery_checklist
```

2. **增加交付清单输出要求**：在输出格式中新增 `delivery_checklist` 字段。

3. **里程碑演进路线图**（已有的"技术演进路线图"保持不动，仅补充本次改动描述）。

### [A3] DATA_FORMATS.md 交付清单扩展

**文件**：`agents/shared/DATA_FORMATS.md`（修改）

**新增**：在 TradingBrief 数据结构中增加 `delivery_checklist` 字段：

```json
{
  "delivery_checklist": {
    "framework": "TqSdk / QuantNova",
    "market_hypothesis": "焦煤JM当前处于趋势发展阶段，但效率比率下降至0.24，趋势动能衰减",
    "change_type": "adjust_position",
    "change_description": "建议减仓50%，从2500→1250",
    "validation_standard": "walk_forward_validation",
    "validation_result": "待执行",
    "remaining_risks": [
      "夜盘跳空风险",
      "主力合约切换临近（9月合约）",
      "整体市场偏空环境"
    ]
  }
}
```

### [A4] 新建 validation_matrix.py

**文件**：`scripts/trend_scanner/validation_matrix.py`（新建）

**设计要点**：
- 不替代现有验证器（walk_forward / overfitting_audit / factor_evaluator），而是它们的统一调度层
- Reasoner 在输出建议时可以引用它来标注"该建议需要什么级别的验证"

**数据模型**：
```python
VALIDATION_MATRIX = {
    "adjust_position": {
        "minimum": "unit_test + 1 regression_backtest",
        "checks": ["position_limit", "exposure_check", "turnover_check"],
        "red_flags": ["turnover_ratio_up_pnl_up_unexplained"],
        "validator": "walk_forward_validator"
    },
    "add_indicator": {
        "minimum": "unit_test_with_fixture",
        "checks": ["numerical_stability", "lookahead_bias", "nan_handling"],
        "red_flags": ["lookahead_bias", "survivorship_bias"],
        "validator": "factor_evaluator"
    },
    # ... 其他改动类型
}
```

**产出物**：1 个新模块 + 配套测试。

---

## 六、Phase 4：Scanner 集成 + Reasoner 上下文

### [B4] Scanner 接入新指标层

**文件**：
- `scripts/trend_scanner/scanner.py`（修改）
- `config/config.json`（修改）

**改动要点**：
1. `scanner.py` 的 `analyze()` 增加 `use_multi_dimension` 参数
2. 当启用时，走路径：IndicatorHub → MultiDimensionScreener → 多维度评分
3. 多维度评分作为信号的附加置信度证据
4. 保持向后兼容：默认仍使用原有信号生成逻辑

### [B5] Reasoner 上下文增强

**文件**：`scripts/trend_scanner/context.py`（修改）

**改动要点**：
1. `ContextAssembler` 在组装推理上下文时注入多维度筛选结果
2. 新增上下文字段：
   - `dimension_scores`：五维度得分明细
   - `volume_structure`：成交量结构分析（OBV趋势、MFI位置）
   - `money_flow`：资金流向信号（多空博弈指标）
3. LLM 推理时可感知成交量结构、多空博弈等新维度

---

## 七、测试策略

| Phase | 测试内容 | 测试类型 | 预计数量 |
|-------|----------|----------|----------|
| B1 | sync_indicators 计算结果与 TqSdk ta 模块对比 | 单元测试 | 5-8 |
| B2 | IndicatorHub 合并逻辑、字段映射 | 单元测试 | 8-10 |
| B3 | MultiDimensionScreener 维度评分、边界条件 | 单元测试 | 12-15 |
| A4 | validation_matrix 路由逻辑、匹配规则 | 单元测试 | 6-8 |
| B4 | Scanner 新路径端到端 | 集成测试 | 3-5 |

---

## 八、不做什么（明确边界）

| 不做 | 原因 |
|------|------|
| 不引入框架适配器（vnpy/rqalpha 等） | TqSdk 绑定已完善 |
| 不复制 quant-strategy-builder 的 prompt-gallery | 我们已有独立的信号体系 |
| 不实现基差/库存/季节性数据管道 | 独立需求，另行评估 |
| 不替代 IndicatorEngine | IndicatorHub 是合并层，IndicatorEngine 继续负责高级指标 |
| 不修改 scanner 默认行为 | 新指标层通过参数开关引入，向后兼容 |

---

## 九、里程碑

| 里程碑 | Phase | 关键交付物 | 可验证指标 |
|--------|-------|-----------|-----------|
| M1: 基础设施就绪 | 1 | METHODOLOGY.md + 修复的 sync_indicators | sync_indicators 成功计算 70 个 TqSdk 指标 |
| M2: 新信号维度 | 2 | IndicatorHub + MultiDimensionScreener | 多维度评分可区分趋势/震荡品种 |
| M3: 推理框架升级 | 3 | Reasoner 五步框架 + 交付清单 + 验证矩阵 | Reasoner 输出含 delivery_checklist 字段 |
| M4: 全链路贯通 | 4 | Scanner + Reasoner 融入新指标 | 端到端流程输出多维度评分 |

---

*本文档为统一整合的实施路线图，每次代码修改前参考本文档和对应模块的详细设计。*
