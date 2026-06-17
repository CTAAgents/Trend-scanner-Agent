# FinClaw 与 Trend-scanner-Agent 整合分析报告

> 版本：v1.0 | 日期：2026-06-17
> 分析对象：[aifinlab/FinClaw](https://github.com/aifinlab/FinClaw)
> 目标：识别可吸纳的优秀思路，规划实施方案，规避已知缺陷

---

## 一、FinClaw 全貌速览

### 1.1 定位

FinClaw 是上海财大 AIFinLab 出品的**金融垂直 Skill 仓库**，基于 OpenClaw Agent OS 运行。核心不是框架代码，而是 **1000+ 个 SKILL.md 定义文件**，覆盖银行/证券/保险/基金/期货/信托六大行业。

### 1.2 架构骨架

```
FinClaw/
├── finclaw.md          ← Agent 入口定义（安装脚本跳转）
├── SOUL.md             ← Agent 人格定义
├── install.sh          ← CLI 安装脚本
├── skills/             ← 核心资产
│   ├── SKILLS_CATALOG.md   ← 817 个 skill 分类目录
│   ├── cn-stock-data/      ← 统一数据抽象层
│   │   ├── SKILL.md
│   │   └── scripts/cn_stock_data.py
│   ├── a-share-futures-analysis/  ← 股指期货基差分析
│   │   ├── SKILL.md
│   │   └── references/futures-guide.md
│   ├── futures-volume-analyzer/   ← 成交持仓分析
│   ├── futures-position-tracker/  ← 龙虎榜持仓追踪
│   ├── futures-arbitrage-analyzer/← 套利分析
│   ├── futures-risk-analyzer/     ← 风险分析
│   ├── ... (1000+ skill 目录)
│   └── a-share-factor-analysis/   ← 因子分析
│       ├── SKILL.md
│       └── scripts/factor_analyzer.py
├── assets/             ← 演示视频
└── images/             ← 截图和 Logo
```

### 1.3 Skill 结构范式

每个 Skill 目录 = `SKILL.md` + `references/` + 可选 `scripts/`

**SKILL.md 格式**：
```yaml
---
name: skill-name
description: 一句话能力描述 + 触发词
---
### 数据源
（Python 代码片段 / CLI 命令 / akshare 调用）

### Workflow (5 steps)
Step 1: 数据获取
Step 2: 计算/分析
Step 3: ...
Step N: 综合研判 & 输出

### 风格说明
| 维度 | formal | brief |
...

### 关键规则
1. ...
2. ...
```

**关键特征**：绝大多数 Skill **没有真正的代码执行**——数据获取用 Python 代码片段示意，分析步骤用自然语言描述，输出格式用 Markdown 表格定义。本质是**结构化 Prompt 工程**。

### 1.4 期货套件（10 个 Skill）

| Skill | 能力 | 数据源 | 代码深度 |
|-------|------|--------|---------|
| futures-market-overview | 五大交易所市场概览 | 交易所数据 | 无代码 |
| commodity-futures-analyzer | 季节性/基差分析 | 交易所数据 | 无代码 |
| financial-futures-analyzer | 股指期货基差 | 中金所 | 无代码 |
| futures-volume-analyzer | 成交持仓分析 | 交易所 | 无代码 |
| futures-position-tracker | 龙虎榜持仓追踪 | 交易所 | 无代码 |
| futures-arbitrage-analyzer | 跨品种/跨期套利 | 历史价差 | 无代码 |
| futures-risk-analyzer | VaR/波动率 | 历史数据 | 无代码 |
| futures-margin-calculator | 保证金计算 | 交易所标准 | 无代码 |
| futures-macro-correlation | 宏观相关性 | 历史统计 | 无代码 |
| futures-delivery-analyzer | 交割分析 | 合约信息 | 无代码 |

**总结**：期货套件 10 个 Skill 全部是 Prompt 模板，无真实计算脚本。覆盖面广但深度为零。

---

## 二、FinClaw 优秀思路识别

### 2.1 统一数据抽象层（cn-stock-data） ★★★★★

**这是 FinClaw 最有价值的设计**。

```
用户请求 → cn-stock-data（统一入口）→ 智能路由 → efinance / akshare / adata / ashare / snowball
```

核心设计：
- **统一代码格式**：`SH600519` → 自动推断市场
- **统一字段名**：英文 snake_case（date, open, close...）
- **智能路由 + 自动 Fallback**：每种数据类型有优先级链
- **统一返回格式**：`{ok, source, fallback_used, code, data_type, count, data}`

**与我们的关系**：我们的数据源优先级是 `TqSdk → DuckDB → 通达信MCP → CSV`，概念类似但实现分散在多个模块（tqsdk_bridge.py, storage/duckdb_store.py, tdx_connector）。FinClaw 的统一入口 + 智能路由模式值得借鉴。

### 2.2 Skill 组织范式（SKILL.md + references/）★★★☆☆

**每个能力 = 一个 SKILL.md + 一份专业指南**，目录即分类。

优点：
- 粒度细、可独立调用
- references/ 提供领域知识锚点
- 触发词机制让 Skill 发现变得自然

局限：
- 缺乏 Skill 间的编排能力（无 pipeline/chain）
- 无法表达 Skill 之间的依赖关系
- references/ 内容是静态文档，不参与计算

**与我们的关系**：我们的 Agent 架构（Reasoner/Debater/Evolver/Orchestrator）已实现了动态编排，远超 FinClaw 的静态 Skill 列表。但我们的 **因子种子池** 和 **研报知识库** 可以借鉴 references/ 的知识锚点模式。

### 2.3 期货分析维度覆盖 ★★★☆☆

FinClaw 期货套件覆盖的维度我们部分缺失：

| 维度 | FinClaw | 我们 | 差距 |
|------|---------|------|------|
| 市场概览 | ✅ | ✅ Scanner | 持平 |
| 基差分析 | ✅ | ❌ | **缺失** |
| 季节性分析 | ✅ | ❌ | **缺失** |
| 龙虎榜持仓 | ✅ | 部分 TqSdk | **可加强** |
| 跨期/跨品种套利 | ✅ | ❌ | **缺失** |
| 保证金计算 | ✅ | ❌ | **缺失** |
| 宏观相关性 | ✅ | ❌ | **缺失** |
| 交割分析 | ✅ | ❌ | **缺失** |
| VaR 风险分析 | ✅ | 部分 | **可加强** |
| 技术指标 | ❌ | ✅ 32个 | **我们领先** |
| 因子进化引擎 | ❌ | ✅ | **我们领先** |
| 可见图指标 | ❌ | ✅ | **我们领先** |
| Walk-Forward 验证 | ❌ | ✅ | **我们领先** |
| 波动率锚点止损 | ❌ | ✅ | **我们领先** |
| 多角色辩论 | ❌ | ✅ | **我们领先** |
| 自优化记忆 | ❌ | ✅ | **我们领先** |

**结论**：FinClaw 覆盖了"分析面"（基差/季节性/套利/宏观），我们覆盖了"量化面"（指标/因子/回测/进化）。互补性强。

### 2.4 输出模式双风格（formal / brief）★★★☆☆

FinClaw 部分高级 Skill 提供 formal（研报级）和 brief（快查级）两种输出模式。

**与我们的关系**：我们的 Reasoner 输出已经比较结构化，但没有明确的分级输出机制。可以借鉴。

### 2.5 因子分析脚本（factor_analyzer.py）★★☆☆☆

实现了：
- IC/IR 计算（Spearman）
- 五分组回测
- 换手率分析
- 多空组合收益

**评估**：功能正确但非常基础。我们的 factor_evaluator.py 已包含截面 IC/ICIR + Walk-Forward + 贝叶斯优化，远超其水平。**不需要借鉴**。

---

## 三、FinClaw 缺陷识别（需规避）

### 3.1 Prompt-Only 无真实执行 ★★★★☆

**最致命的缺陷**：1000+ Skill 中，超过 99% 没有可执行代码。

- 数据获取：Python 代码片段写在 SKILL.md 里，**需要 LLM 手动调用**
- 分析计算：用自然语言描述步骤，**依赖 LLM 自行推理**
- 结果输出：Markdown 表格模板，**由 LLM 填充**

这意味着：
1. **不可复现**：同一 Skill 在不同 LLM / 不同会话中输出完全不同
2. **不可验证**：无法自动化测试输出正确性
3. **不可量化**：无法评估 Skill 的预测准确率 / IC
4. **不可进化**：无法基于历史表现优化 Prompt

**我们的优势**：计算用脚本，推理用 Agent。脚本输出确定性数据，Agent 基于数据推理。这正是要坚守的。

### 3.2 数据源薄弱（对期货）★★★★☆

FinClaw 期货数据全部来自 AkShare / efinance——这些库以 A 股数据为主，期货覆盖：
- 无 Tick 级数据
- 无分时数据
- 无实时行情推送
- 无持仓量/成交量的可靠来源
- 无产业链/现货价格数据

**我们已有 TqSdk 直连 + 通达信 MCP，数据质量远超 FinClaw**。

### 3.3 无回测/无验证/无自改进 ★★★★★

FinClaw 的 Skill 没有：
- 回测框架
- 样本外验证
- IC/IR 评估
- 参数优化
- 过拟合检测
- 交易日志 → 反馈闭环
- 任何形式的自改进机制

**我们的 v5/v6 核心就是闭环迭代因子进化引擎 + Walk-Forward 验证 + 轨迹感知优化器 + 自优化记忆系统**。这是系统级差距。

### 3.4 模板堆叠，缺乏深度 ★★★☆☆

817 个 Skill 中，大量是模板化变体（如银行 T121-T250 系列），真正的专业深度有限：
- "一句话能力描述"占 80%+ 的 Skill 内容
- 无真正的金融工程逻辑
- 无可量化的效果评估

**规避策略**：我们不追求 Skill 数量，每个模块必须有测试覆盖 + 可量化的效果指标。

### 3.5 无跨 Skill 编排能力 ★★★☆☆

Skill 之间没有 pipeline、chain、DAG 等编排机制。1000+ 个 Skill 是一盘散沙，靠 LLM 自行选择调用哪些。

**我们的 Orchestrator + TaskList + 多 Agent 团队协调已解决这个问题**。

---

## 四、整合实施方案

### 4.1 整合原则

| 原则 | 说明 |
|------|------|
| **吸其骨架，不搬其肉体** | 借鉴架构思想和分析维度，不直接复制 Prompt |
| **脚本化 > Prompt化** | 任何新功能必须先写计算脚本，再用 Agent 推理 |
| **TqSdk 为本** | 数据源不走 AkShare，但路由模式可借鉴 |
| **进化闭环** | 每个新能力必须接入因子评估/验证体系 |

### 4.2 实施路线图

#### Phase 1: 统一数据路由层（优先级：P0）

**借鉴**：cn-stock-data 的统一入口 + 智能路由 + 自动 Fallback

**实施**：
```
scripts/trend_scanner/data_router.py   ← 新增
```

设计：
```python
class DataRouter:
    """统一期货数据路由层
    
    数据类型路由优先级：
    K线：  DuckDB → TqSdk → 通达信MCP → CSV
    行情：  DuckDB → TqSdk → 通达信MCP
    持仓：  TqSdk → 通达信MCP → AkShare
    基差：  AkShare → 通达信MCP（新增）
    季节性： AkShare → 本地CSV（新增）
    """
    def get_kline(self, symbol, freq, start, end) -> dict
    def get_quote(self, symbols) -> dict
    def get_positions(self, symbol) -> dict
    def get_basis(self, symbol) -> dict  # 新增
    def get_seasonality(self, symbol) -> dict  # 新增
```

**收益**：
- 统一数据访问接口，消除各模块的直接依赖
- 自动 Fallback 提高可用性
- 统一返回格式 `{ok, source, fallback_used, data}`

**工作量**：约 3 天（提取现有 tqsdk_bridge/duckdb_store/tdx 调用为统一接口）

---

#### Phase 2: 期货分析维度扩展（优先级：P1）

**借鉴**：FinClaw 期货套件覆盖的 6 个缺失维度

**实施**：

| 维度 | 新脚本 | 数据源 | 集成方式 |
|------|--------|--------|---------|
| **基差分析** | `scripts/trend_scanner/basis_analyzer.py` | TqSdk(近远月) | Scanner → Reasoner |
| **季节性分析** | `scripts/trend_scanner/seasonality_analyzer.py` | AkShare(历史合约) | Scanner 种子因子 |
| **龙虎榜持仓** | `scripts/trend_scanner/position_tracker.py` | TqSdk + 交易所 | Scanner → Reasoner |
| **保证金计算** | `scripts/trend_scanner/margin_calculator.py` | 交易所标准 | 仓位管理 |
| **宏观相关性** | `scripts/trend_scanner/macro_correlation.py` | NeoData/AkShare | Reasoner 上下文 |
| **交割分析** | `scripts/trend_scanner/delivery_analyzer.py` | 合约信息 | Reasoner 上下文 |

**核心要求**：
1. 每个分析器必须是**可独立运行的 Python 脚本**，输出 JSON
2. 必须有对应的**测试文件**，测试覆盖率 ≥ 80%
3. 通过 DataRouter 统一获取数据
4. 分析结果注入 Reasoner 的 `_build_user_prompt()`

**工作量**：约 10 天（6 个分析器，每个 1.5 天）

---

#### Phase 3: 知识锚点体系（优先级：P2）

**借鉴**：FinClaw 的 `references/` 知识指南模式

**实施**：
```
references/
├── futures-guide.md          ← 期货交易基础知识
├── basis-trading-guide.md   ← 基差交易方法论
├── seasonality-guide.md     ← 季节性规律手册
├── arbitrage-guide.md        ← 套利交易手册
├── macro-correlation-guide.md ← 宏观对商品的影响机制
└── delivery-guide.md         ← 交割规则与影响
```

**与 FinClaw 的区别**：
- FinClaw 的 references 是给 LLM 读的纯文本
- 我们的 references 是**因子种子 + 验证规则 + 搜索空间约束**的三位一体

每个 reference 文件格式：
```markdown
# 基差交易方法论

## 核心原理
...

## 可编码的信号
| 信号 | 计算方式 | 因子类型 | 搜索空间 |
|------|---------|---------|---------|
| 基差率 | (F-S)/S | mean_reversion | [-0.05, 0.05] |
| 期限结构斜率 | (F_far - F_near)/F_near | carry | [-0.03, 0.03] |

## 因子进化注入规则
- basis_rate 作为种子因子加入 factor_seed_pool
- IC 评估周期：20 日截面
- Gate 阈值：|mean_IC| > 0.02, ICIR > 0.5

## 参考
- [FinClaw a-share-futures-analysis](https://github.com/aifinlab/FinClaw/tree/main/skills/a-share-futures-analysis)
```

**工作量**：约 3 天

---

#### Phase 4: 分级输出机制（优先级：P3）

**借鉴**：FinClaw 的 formal/brief 双模式

**实施**：在 Reasoner 的 `generate_brief()` 中增加输出模式参数：

```python
class OutputMode(Enum):
    BRIEF = "brief"       # 快查级：品种+方向+置信度+止损（3-5 行）
    STANDARD = "standard" # 标准级：当前输出（默认）
    FORMAL = "formal"     # 研报级：完整分析+图表+风险+套利机会
```

**工作量**：约 1 天

---

#### Phase 5: 套利分析模块（优先级：P3）

**借鉴**：FinClaw 的 futures-arbitrage-analyzer

**实施**：
```
scripts/trend_scanner/arbitrage_analyzer.py
```

覆盖：
- 跨期套利（近月-远月价差）
- 跨品种套利（螺纹-热卷、豆油-棕榈等）
- 期现套利（基差回归）

输出套利信号 + Z-Score + 历史分位 → 注入 Reasoner

**工作量**：约 3 天

---

### 4.3 不做的事项（明确规避）

| 事项 | 原因 |
|------|------|
| ❌ 直接安装 FinClaw Skills | 我们的 TqSdk 数据质量远超 AkShare |
| ❌ 复制 SKILL.md Prompt | 计算必须用脚本，不能靠 Prompt |
| ❌ 引入 OpenClaw 依赖 | 我们用 WorkBuddy 生态，无需额外框架 |
| ❌ 追求 Skill 数量 | 6 个高质量分析器 > 1000 个 Prompt 模板 |
| ❌ 用 AkShare 作主力数据源 | 期货数据覆盖不足，仅作基差/季节性的辅助源 |
| ❌ 银行/保险/信托 Skill | 与期货趋势跟踪无关 |

---

## 五、核心结论

### 5.1 FinClaw 对我们的价值

**不是代码库，是需求分析参考**。FinClaw 的 1000+ Skill 本质上是金融行业的"需求清单"——它告诉我们在期货领域，专业交易者关注哪些分析维度。但它没有能力真正执行这些分析。

### 5.2 我们相对 FinClaw 的核心优势

| 维度 | FinClaw | 我们 |
|------|---------|------|
| 计算深度 | 无（Prompt-only） | 深度（脚本+因子引擎+回测） |
| 数据质量 | AkShare（免费、延迟、缺期货） | TqSdk 直连（实时、Tick级） |
| 因子进化 | 无 | 完整闭环（Generate→Eval→Gate→Memory） |
| 验证体系 | 无 | Walk-Forward + 贝叶斯优化 + 过拟合检测 |
| 自我改进 | 无 | 轨迹感知 + 自优化记忆 + 交易日志反馈 |
| 编排能力 | 无（散沙式 Skill 列表） | Orchestrator + 多 Agent 协作 |

### 5.3 可吸纳的精华（排序）

1. **统一数据路由模式** → Phase 1（最高 ROI）
2. **6 个期货分析维度** → Phase 2（补齐分析面短板）
3. **知识锚点体系** → Phase 3（将方法论编码为可进化因子）
4. **分级输出** → Phase 4（低成本高收益）
5. **套利分析** → Phase 5（扩展交易场景）

### 5.4 总工作量评估

| Phase | 工作量 | 测试要求 | 依赖 |
|-------|--------|---------|------|
| Phase 1 | 3 天 | data_router 全覆盖测试 | 无 |
| Phase 2 | 10 天 | 每个分析器 ≥ 80% 覆盖率 | Phase 1 |
| Phase 3 | 3 天 | 因子注入测试 | Phase 2 |
| Phase 4 | 1 天 | 输出模式测试 | 无 |
| Phase 5 | 3 天 | 套利信号测试 | Phase 1 |
| **合计** | **~20 天** | | |

---

## 六、下一步

等待掌柜确认：
1. 是否认同上述 5 个 Phase 的优先级排序？
2. Phase 1（统一数据路由层）是否立即启动？
3. 基差/季节性/AkShare 辅助源是否可接受？（仅作补充，不动 TqSdk 主力地位）
4. 是否需要我先做一个 Phase 1 的 Demo 验证？
