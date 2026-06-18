# 策略设计方法论

> 版本：v1.0 | 创建日期：2026-06-17
> 来源：quant-strategy-builder (itsadrianxv) 方法论吸收 + 本系统实战经验提炼
> 适用范围：Reasoner Agent 推理框架、Evolver Agent 优化决策、Debater Agent 辩论参照

---

## 一、核心哲学

### 1.1 三原则

| 原则 | 含义 | 系统落地 |
|------|------|----------|
| **最小改动面** | 优先复用已有参数和扩展点，不创造新抽象层 | Reasoner 输出建议时，默认参数调优优于策略逻辑变更 |
| **证据驱动交付** | 每个改动必须附带最低成本的验证证明 | 引用 validation_matrix 匹配改动类型的最低验证标准 |
| **中国市场优先** | 主力换月、夜盘、保证金、交割月等微观结构是一等公民 | 作为 Step 2（Translate）的检查点逐项验证 |

### 1.2 与系统核心理念的关系

```
推理重于规则（系统核心理念）
    │
    ├── 推理框架 ← 本方法论提供的五步结构化流程
    ├── 约束生成 ← 中国市场检查点
    ├── 验证标准 ← 验证矩阵
    └── 交付规范 ← 交付清单模板
```

本方法论不替代系统的"推理优先"理念，而是为它提供**可复用的结构化外壳**，使每次推理都有迹可循、可量化评估、可事后审计。

---

## 二、五步推理框架

Reasoner Agent 的推理流程按五步展开。每一步有明确的输入、输出和验证点。

### Step 1: Frame The Edge（框定优势）

**目标**：明确当前交易机会的 alpha 来源和边界条件。

| 分析维度 | 具体问题 | 信息来源 |
|----------|----------|----------|
| 品种特征 | 黑色/能化/有色？受什么驱动？ | 品种元数据 + 历史经验 |
| 市场阶段 | 趋势发展/趋势成熟/震荡/转折？ | 多维度筛选得分（Phase 3）+ 趋势强度复合指标 |
| 持仓背景 | 已有仓位？方向？ | positions.json |
| 时间背景 | 日盘/夜盘？临近交割月？合约到期？ | 交易日历 + 合约信息 |

**输出**：一段不超过 3 句话的优势假说，例如：

> "焦煤JM处于趋势发展阶段（ADX=32，TSI=45），但效率比率下降至0.24暗示动能衰减。当前多仓存在趋势继续 vs 反转的博弈窗口。"

### Step 2: Translate Into Parts（翻译为决策模块）

**目标**：将模糊的交易想法翻译为可量化、可验证的决策模块。

| 决策模块 | 当前状态 | 变化方向 | 量化指标 |
|----------|----------|----------|----------|
| **信号层** | 多维度筛选得分 | 趋势/动量/成交量/波动率/通道 | 各维度得分 + 综合得分 |
| **经验层** | 历史相似度检索 | 相似场景的胜率/盈亏比 | 记忆系统相似度 |
| **风控层** | 波动率锚点 | 止损距离 | ATR × Z系数 |
| **约束层** | 中国市场检查点（见第四节） | 逐项验证 | 通过/不通过 |

**中国市场约束检查点**（逐项验证，不可跳过）：

| 检查项 | 当前状态 | 对决策的影响 |
|--------|----------|-------------|
| 主力合约有效性 | 是否在主力合约上？ | 非主力→流动性折价 |
| 换月窗口 | 距下次换月还有多少天？ | <7天→考虑提前移仓 |
| 夜盘连续性 | 品种是否有夜盘？ | 无夜盘→隔夜跳空风险更高 |
| 保证金水平 | 当前保证金比例？ | 影响仓位计算 |
| 交割月边界 | 是否临近交割月？ | 个人户需提前平仓 |
| 合约乘数 | 每点价值？ | 影响盈亏计算 |

### Step 3: Choose Smallest Safe Change（选择最小安全改动）

**目标**：在可行的操作方案中选择改动面最小的。

**改动优先级**（从低风险到高风险）：

```
1. 参数调优（止损位、仓位比例、信号阈值）
2. 已有策略的过滤器调整（增加/减少确认条件）
3. 新指标添加（增加一个维度的观察）
4. 策略逻辑变更（改变进出场规则）
5. 全新的策略方向（开新仓、做相反方向）
```

**决策矩阵**：

| 场景 | 已有仓位 | 最小安全改动 |
|------|----------|-------------|
| 趋势延续，信号强化 | 有同向仓位 | 维持仓位，上调止损 |
| 趋势延续，信号弱化 | 有同向仓位 | 维持仓位，收紧止损 |
| 趋势转弱，信号反转 | 有同向仓位 | 减仓 50%，剩余仓位设保本止损 |
| 趋势确认反转 | 有同向仓位 | 全部平仓 |
| 强信号出现 | 无仓位 | 小仓位试探（正常仓位的 30%），待确认后加仓 |
| 弱信号出现 | 无仓位 | 不操作，继续观察 |

### Step 4: Decide The Proof Up Front（预先定义验证标准）

**目标**：在给出建议的同时，定义该建议被"证伪"的条件和应执行的最低验证标准。

引用第五节「验证矩阵」，根据改动类型匹配验证要求：

```
改动类型: adjust_position（调整仓位）
  → 最低验证: 1 次聚焦回测 + 1 个回归测试
  → 检查要点: 仓位限制、敞口检查、换手率
  → 红线: 盈亏改善伴随换手率同步恶化且未解释
```

每个 Reasoner 输出应包含"如果 X 发生，则建议失效"的明确条件。

### Step 5: Summarize Like A Research Engineer（研究员式交付）

**目标**：以研究员的标准交付交易决策简报，而非交易指令。

**交付结构**（对齐 DATA_FORMATS.md 中的 TradingBrief + delivery_checklist）：

```json
{
  "market_assessment": "市场评估（3-5句）",
  "routes": [
    {
      "route_id": "A",
      "name": "方案名称",
      "action": "具体操作",
      "confidence": 0.72,
      "reasoning": "推理过程",
      "constraints": ["约束条件1", "约束条件2"],
      "risks": ["风险1", "风险2"]
    }
  ],
  "delivery_checklist": {
    "framework": "TqSdk / QuantNova v5.0",
    "market_hypothesis": "当前市场阶段及优势假说",
    "change_type": "adjust_position|add_indicator|modify_threshold|new_entry|exit",
    "change_description": "改了什么，为什么这样改",
    "validation_standard": "walk_forward|factor_evaluation|overfitting_audit",
    "falsification_condition": "什么条件下该建议应被推翻",
    "remaining_risks": ["未验证的风险"]
  }
}
```

---

## 三、中国市场约束检查点

### 3.1 商品期货（一等公民）

| 约束类别 | 检查项 | 系统实现 |
|----------|--------|----------|
| **合约选择** | 主力合约识别 | TqSdk KQ.m@ 主力连续 |
| **换月触发** | 持仓量迁移信号 | 对比主力/次主力 OI |
| **夜盘** | 交易时段连续性 | SHFE/DCE/CZCE/INE 夜盘品种清单 |
| **保证金** | 动态保证金比例 | 交易所保证金率 + 期货公司上浮 |
| **手续费** | 双向收取 | 万1.2 + 1跳滑点（回测假设） |
| **交割月** | 个人户平仓时限 | 交割月前最后一个交易日 |
| **合约乘数** | 每点价值 | RB=10, JM=60, I=100 等 |
| **涨跌停** | 日内波动上限 | 各品种涨跌停板幅度 |

### 3.2 回测约束（防止过拟合）

| 约束 | 检查方式 |
|------|----------|
| 前视偏差 | 指标计算只用历史数据 |
| 幸存偏差 | 包含已退市/不活跃品种 |
| 数据频率一致性 | 日线回测用日线信号 |
| 费用模型 | 包含佣金+滑点+保证金成本 |

### 3.3 A股（远期扩展，暂不落地）

T+1、100股整手、集合竞价、涨跌停、ST 处理——保留为远期 checklist，当前系统聚焦期货。

---

## 四、验证矩阵

### 4.1 改动类型 → 最低验证标准

| 改动类型 | 最低验证 | 检查要点 | 系统验证器 | 红线 |
|----------|----------|----------|-----------|------|
| `adjust_position`<br>（调仓） | 1 次聚焦回测 +<br>1 个回归测试 | 仓位限制、敞口检查、换手率 | `walk_forward_validator` | 盈亏改善伴随换手率恶化且未解释 |
| `add_indicator`<br>（加指标） | 固定 fixture 的单元测试 | 数值稳定性、前视偏差、NaN 处理 | `factor_evaluator` | 前视偏差、幸存偏差 |
| `modify_threshold`<br>（改阈值） | 聚焦回测 +<br>1 个回归测试 | 交易次数、胜率、换手率、基准差 | `walk_forward_validator` | 仅靠单一日历区间证明有效 |
| `new_entry`<br>（新入场） | 聚焦回测 +<br>Walk-Forward 验证 | 跨周期稳定性 | `walk_forward_validator` | 样本外表现显著劣于样本内 |
| `exit`<br>（退出） | 回归测试 | 平仓后品种走势跟踪 | `walk_forward_validator` | N/A |
| `strategy_logic`<br>（策略逻辑） | Walk-Forward +<br>蒙特卡洛 | 全维度回归测试 | `walk_forward_validator` +<br>`overfitting_auditor` | 逻辑在框架适配器和核心逻辑中重复 |
| `risk_parameter`<br>（风控参数） | 风险集成测试 +<br>聚焦回测 | 尾部损失、敞口截断 | `walk_forward_validator` | N/A |

### 4.2 验证器对应关系

| 系统验证器 | 适用改动 | 输入 | 输出 |
|-----------|----------|------|------|
| `walk_forward_validator` | adjust_position, new_entry, strategy_logic | 策略参数 + K线数据 | IS/OOS Sharpe, 胜率, 最大回撤 |
| `factor_evaluator` | add_indicator | 因子序列 + 收益率 | IC, ICIR, 分层收益, 换手率 |
| `overfitting_auditor` | strategy_logic | 回测结果 | 过拟合概率, 参数敏感度 |
| `trajectory_analyzer` | 全部（事后审计） | 交易轨迹 | 归因分析, 模式检测 |

### 4.3 置信度与验证标准对应

| 置信度区间 | 历史平均胜率 | 最低验证要求 |
|-----------|------------|-------------|
| HIGH (≥0.75) | ≥55% | Walk-Forward 验证 + 交叉验证 |
| MEDIUM (0.5-0.75) | 45-55% | 聚焦回测 + 1 回归测试 |
| LOW (<0.5) | <45% | 单元测试 + 逻辑审查 |

---

## 五、交付清单模板

每个 Reasoner 输出必须包含的 `delivery_checklist` 字段定义：

```json
{
  "delivery_checklist": {
    "framework": "<数据框架>",
    "market_hypothesis": "<一句话描述当前市场假说>",
    "change_type": "<adjust_position|add_indicator|modify_threshold|new_entry|exit|strategy_logic|risk_parameter>",
    "change_description": "<具体改了什么，为什么>",
    "validation_standard": "<walk_forward|factor_evaluation|overfitting_audit>",
    "falsification_condition": "<在什么条件下该建议失效>",
    "remaining_risks": [
      "<未在推理中充分验证的风险1>",
      "<未在推理中充分验证的风险2>"
    ]
  }
}
```

**字段说明**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `framework` | 是 | 数据框架名称，当前固定为 "TqSdk / QuantNova v5.0" |
| `market_hypothesis` | 是 | 一句话概括当前市场假设，如"焦煤JM处于趋势发展末期，效率比率0.24暗示动能衰减" |
| `change_type` | 是 | 参见验证矩阵的改动类型枚举 |
| `change_description` | 是 | 1-2句话描述改了什么 |
| `validation_standard` | 是 | 应该执行的最低验证标准 |
| `falsification_condition` | 是 | 什么条件下这个建议应该被推翻。**这是交付清单的核心价值——提前定义"我错了"的判断标准** |
| `remaining_risks` | 是 | 未在推理中充分验证的风险（如夜盘跳空、宏观事件） |

---

## 六、方法论演进

### 6.1 当前适用版本

Reasoner Agent v5.0，基于 TqSdk 数据源 + DuckDB 本地缓存。

### 6.2 已知局限

| 局限 | 影响 | 缓解措施 |
|------|------|----------|
| 交付清单的 `falsification_condition` 依赖 LLM 推理质量 | 可能过于模糊 | 后续通过 Evolver 反馈逐步校准 |
| 验证矩阵的 `adjust_position` 类改动当前缺乏自动化验证流程 | 验证标准无法自动执行 | Phase C (A4) 落地的 validation_matrix.py 解决 |
| 中国市场检查点的部分字段硬编码（如合约乘数） | 新品种上市需手动更新 | 后续考虑从交易所数据自动获取 |

### 6.3 下一步演进

| 优先级 | 方向 | 依赖 |
|--------|------|------|
| P0 | Phase C: validation_matrix.py 代码落地 | Phase A 本文件完成 |
| P1 | Phase B: Reasoner SKILL.md 嵌入五步框架 | Phase A 本文件完成 |
| P2 | 多维度筛选信号（Phase 2-3）融入 Step 2 | TqSdk 70 指标整合 |

---

## 七、参考文献

- quant-strategy-builder (itsadrianxv/quant-strategy-builder-skill): 策略设计方法论原始来源
- Agentic AI for Factor Investing (arXiv:2603.14288): 因子进化引擎理论基础
- MacroEconomists (arXiv:2606.08283): 辩论修正认知偏差 (Δ Sharpe = +0.044)

---

*本文档为共享文档，Reasoner/Debater/Evolver Agent 均可引用。每次修改策略设计相关流程时，优先参考本文档的验证矩阵和约束检查点。*
