# Changelog

> 版本号管理遵循 [VERSION_MANAGEMENT.md](VERSION_MANAGEMENT.md)
> 版本号唯一定义位置：`scripts/trend_scanner/__version__.py`

---

## v0.1.0 (2026-06-17)

**新架构版 — FinClaw整合 + 统一数据路由 + 知识锚点 + 分级输出 + 套利分析**

### 新增

- **统一数据路由层** (`unified_data_router.py`)
  - 9种数据类型智能路由（K线/行情/基差/季节性/仓单/龙虎榜/保证金/宏观/交割）
  - 自动Fallback机制（DuckDB → TqSdk → Pytdx → AkShare → CSV）
  - 配置驱动路由优先级（`config.json data_routing`段）
  - 数据时效性检查（fresh/stale/critical三级）
  - 远程数据自动回写本地DuckDB

- **知识锚点体系** (`knowledge_anchors.py`)
  - 13个默认锚点覆盖6个维度（momentum/trend/volatility/volume/basis/seasonality）
  - 为LLM因子生成提供种子+验证规则
  - SQLite持久化存储

- **分级输出机制** (`tiered_output.py`)
  - formal/standard/brief三级输出
  - JSON格式支持API/前端消费
  - 集成到Reasoner Agent

- **套利分析模块** (`arbitrage_analyzer.py`)
  - 12个预定义价差对（跨期+跨品种）
  - Z-Score信号 + 协整检验
  - 价差百分位分析

- **数据源扩展**
  - PytdxSource：通达信Python直连（pytdx库）
  - AkShareSource：基差/季节性/龙虎榜/保证金/宏观数据

- **分析维度补充**
  - 龙虎榜（多空持仓排名）
  - 保证金（交易所/经纪商比例）
  - 宏观经济（GDP/CPI/PMI + 品种关联）
  - 交割数据（交割月/仓单/距交割天数）

### 改进

- **孤立模块集成**：6个模块接入核心系统
  - knowledge_anchors → reasoning.py（知识锚点注入推理prompt）
  - tiered_output → reasoner.py（分级输出）
  - arbitrage_analyzer → scan_opportunities.py（--arbitrage参数）
  - belief_propagation → debater.py（信念传播）
  - conceptual_feedback → debater.py（概念性反馈）
  - rl_interface_designer → evolver.py（RL接口诊断）

- **版本管理**
  - 版本号重置为v0.1.0（开发阶段）
  - 消除所有文件中的版本号硬编码
  - 单一来源原则：`__version__.py`为唯一定义位置
  - 新增版本号管理规范文档

### 修复

- **AkShare API调用**
  - get_basis(): 使用`futures_spot_price()`获取基差数据
  - get_margin(): 使用`futures_fees_info()`获取保证金和手续费
  - get_macro(): 修复CPI/PMI数据解析，添加品种-宏观关联映射

### 测试

- 总计475个测试全部通过
- 新增111个测试（unified_data_router=76, phase3_4_5=35）

---

## 前序版本（v1.0 ~ v6.0）

> 版本号已合并精简，详见`scripts/trend_scanner/__version__.py`中的VERSION_HISTORY

| 版本 | 日期 | 关键变更 |
|------|------|---------|
| v6.0.0 | 2026-06-16 | Reasoner Agent深度分析 + 持仓健康度评估 |
| v5.0.0 | 2026-06-16 | 闭环迭代因子进化引擎 |
| v3.2.x | 2026-06-14 | 五路径框架 + 控制变量隔离 |
| v3.0.0 | 2026-06-14 | 推理优先架构重写 |
| v2.0.0 | 2026-06-01 | 自适应系统 |
| v1.0.0 | 2026-05-15 | 初始版本 |

---

*本文件记录 QuantNova 项目的变更历史。*
