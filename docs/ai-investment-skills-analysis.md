# ai-investment-skills 仓库分析与融合建议

> 分析日期：2026-06-17
> 仓库地址：https://github.com/tellmefrankie/ai-investment-skills
> 目标：从该仓库中提取有用思想，与 QuantNova 项目融合

---

## 一、仓库概述

### 1.1 项目定位

这是一个为 **Claude Code** 和其他支持 SKILL.md 标准的 AI 智能体设计的**投资分析技能集合**，由个人投资者 @tellmefrankie 创建。

**核心价值**：经过 6+ 个月实战检验的 AI 投资分析工具包，每天在真实账户上运行。

### 1.2 核心问题解决

| 问题 | 解决方案 | 创新点 |
|------|----------|--------|
| 期权流分析失真 | 彩票期权过滤器 | 过滤 84%-98% 的投机性期权，揭示真实机构动向 |
| AI 构建误导性叙事 | 反叙事约束 | 强制数字证据、交叉验证、避免重复叙事 |
| 多智能体协调 | 多智能体协调器 | 并行管理、任务分配、结果综合 |
| 分析流程复杂 | 9 波分析管道 | 从宏观到微观的系统化分析流程 |

### 1.3 技能清单

| 技能 | 功能 | 核心数字 |
|------|------|----------|
| Options Flow Analyzer | P/C 比率扫描 + 彩票过滤 | 识别 XLI 5.32, RXRX 84% 彩票 |
| Investment Briefing Agent | 9 波晨间分析 | <5 分钟生成完整简报 |
| Multi-Agent Orchestrator | 并行智能体团队 | 4 个智能体，1 个共识输出 |
| EV Calculator | 概率加权场景分析 | 3 个场景 → 1 个决策 |
| News Sentiment Engine | 200+ RSS 文章评分 | 2 小时阅读 → 5 分钟摘要 |
| Price Monitor & Alert | 止损/止盈监控 | <2 秒警报发送 |

---

## 二、核心创新点深度分析

### 2.1 彩票期权过滤器（Lottery Option Filter）

**问题背景**：
- 传统 P/C 比率在散户活跃的股票中会产生误导性信号
- 例如：RXRX 原始 P/C = 0.38（看似极度看涨），但 84% 是彩票期权

**过滤逻辑**：
```
彩票期权定义：
- 价格：$0.01 - $0.05
- 行权价：深度虚值（delta < 0.15）
- 特征：投机性赌注，非对冲工具

过滤后：
- RXRX: P/C 0.38 → 2.14（温和看跌）
- CEG: P/C 1.06 → 59.2（极度看跌）
```

**价值**：揭示真实机构动向，避免散户噪音干扰。

### 2.2 反叙事约束（Anti-Narrative Harness）

**核心规则**：
1. **禁止叙事重复**：每次分析使用新鲜数据
2. **数字优于叙事**：用"P/C 0.55, real call 28%"替代"看涨"
3. **交叉验证**：任何价格/主张需要 2+ 来源
4. **卖出检查清单**：禁止恐慌性卖出，检查是否触底

**价值**：防止 AI 构建自洽但错误的市场叙事。

### 2.3 9 波分析管道（9-Wave Pipeline）

```
Wave 1: 宏观分析（S&P 500, VIX, 收益率, 美元, 美联储）
Wave 2: 板块轮动（11 个 S&P 板块，识别领导者/落后者）
Wave 3: 技术扫描（RSI, SMA, MACD, 支撑/阻力）
Wave 4: 新闻扫描（48 小时新闻，财报，分析师变动）
Wave 5: 机会发现（新的摇摆交易候选，按 EV 排序）
Wave 6: 批评审查（对抗性审查，反证搜索）
Wave 7: 组合模拟（牛市/基准/熊市场景建模）
Wave 8: 深度连接（跨资产相关性，隐藏关系）
Wave 9: 元批评（最终综合和行动计划）
```

**价值**：系统化的多维度分析框架。

### 2.4 多智能体协调模式

**工作流模式**：
- **研究与分析**：并行启动 3 个智能体（市场研究、用户研究、竞争分析）
- **构建与验证**：顺序启动（架构师 → 开发者 → QA → 批评者）
- **创业战情室**：同时启动所有团队，交叉验证

**价值**：高效利用多个专业智能体。

---

## 三、与 QuantNova 的对比分析

### 3.1 共同点

| 维度 | ai-investment-skills | QuantNova |
|------|----------------------|---------------------|
| **核心理念** | AI 辅助投资决策 | 推理重于规则的交易决策 |
| **多智能体** | 9 个专业智能体 | Reasoner/Debater/Evolver/Orchestrator |
| **分析框架** | 9 波分析管道 | 五维度筛选 + Reasoner 推理 |
| **质量约束** | 反叙事约束 | 辩论机制 + 风险评估 |
| **实战导向** | 6 个月真实账户 | 期货趋势跟踪实战 |

### 3.2 差异点

| 维度 | ai-investment-skills | QuantNova |
|------|----------------------|---------------------|
| **市场** | 美股（期权、股票） | 期货（商品、金融期货） |
| **数据源** | Polygon.io, Yahoo Finance | TqSdk, Pytdx, AkShare, DuckDB |
| **分析重点** | 期权流、情绪、新闻 | 技术指标、趋势强度、因子进化 |
| **架构** | SKILL.md 技能包 | Python 模块 + Agent 架构 |
| **自动化程度** | 每日自动运行 | 定时扫描 + 手动触发 |

---

## 四、吸收融合建议

### 4.1 高优先级融合（立即可实施）

#### A. 反叙事约束机制

**现状**：QuantNova 的 Debater Agent 已有多角色辩论，但缺少系统化的反叙事规则。

**融合方案**：
```python
# 在 reasoning.py 中添加反叙事约束
ANTI_NARRATIVE_RULES = {
    "no_repetition": "禁止重复使用相同的市场叙事",
    "numbers_over_words": "用具体数字替代模糊描述（如'ER=0.65'替代'趋势强'）",
    "cross_verification": "任何主张需要 2+ 数据源验证",
    "sell_checklist": "卖出前必须检查：是否触底？是否有新催化剂？",
}
```

**实施位置**：`reasoning.py` 的 `_build_user_prompt()` 方法

#### B. 概率加权场景分析（EV Calculator 思想）

**现状**：QuantNova 的 Reasoner 输出操作建议，但缺少概率加权的场景分析。

**融合方案**：
```python
# 在 Reasoner 输出中添加场景分析
def generate_scenarios(signal, indicators):
    """生成牛市/基准/熊市场景"""
    scenarios = {
        "bull": {
            "probability": calculate_bull_prob(indicators),
            "target": signal.entry_price * 1.15,  # +15%
            "catalyst": "趋势确认突破",
        },
        "base": {
            "probability": calculate_base_prob(indicators),
            "target": signal.entry_price * 1.05,  # +5%
            "catalyst": "正常波动",
        },
        "bear": {
            "probability": calculate_bear_prob(indicators),
            "target": signal.stop_loss,  # 止损位
            "catalyst": "趋势反转",
        },
    }
    return scenarios
```

**实施位置**：新增 `scripts/trend_scanner/scenario_analyzer.py`

### 4.2 中优先级融合（1-2 周内实施）

#### C. 模块化技能架构（SKILL.md 思想）

**现状**：QuantNova 的模块已较完善，但缺少标准化的技能接口。

**融合方案**：
- 为每个核心模块创建 SKILL.md 描述文件
- 标准化输入/输出格式
- 支持外部智能体调用

**实施位置**：`skills/` 目录，每个技能一个 SKILL.md

#### D. 期权流分析（针对期货期权）

**现状**：QuantNova 有套利分析模块，但缺少期货期权流分析。

**融合方案**：
```python
# 新增期货期权流分析
class FuturesOptionsFlowAnalyzer:
    """期货期权流分析器"""
    
    def analyze_options_flow(self, symbol):
        """分析期货期权流"""
        # 1. 获取期权数据（通过 TqSdk 或 AkShare）
        # 2. 过滤彩票期权（深度虚值、低权利金）
        # 3. 计算调整后 P/C 比率
        # 4. 识别异常（P/C 偏移 > 0.3, OI 激增 > 30%）
        # 5. 分类情绪（看涨/看跌/中性）
        pass
```

**实施位置**：新增 `scripts/trend_scanner/options_flow_analyzer.py`

### 4.3 低优先级融合（长期规划）

#### E. 新闻情绪引擎

**现状**：QuantNova 有宏观数据模块，但缺少新闻情绪分析。

**融合方案**：
- 集成 RSS 新闻源
- 使用 LLM 进行情绪评分
- 按品种/板块聚合新闻情绪

#### F. 价格监控警报

**现状**：QuantNova 有持仓健康度评估，但缺少实时价格监控。

**融合方案**：
- 集成 Telegram/微信通知
- 支持止损/止盈触发
- 实时警报发送

---

## 五、实施路线图

### Phase 1：反叙事约束（1-2 天）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 添加反叙事规则 | reasoning.py | 0.5 天 |
| 修改 Debater 逻辑 | debate_engine.py | 0.5 天 |
| 测试验证 | test_reasoning.py | 0.5 天 |

### Phase 2：场景分析（3-5 天）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 新增场景分析器 | scenario_analyzer.py | 2 天 |
| 集成到 Reasoner | reasoning.py | 1 天 |
| 测试验证 | test_scenario_analyzer.py | 1 天 |

### Phase 3：期权流分析（1-2 周）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 新增期权流分析器 | options_flow_analyzer.py | 3 天 |
| 集成数据源 | unified_data_router.py | 2 天 |
| 测试验证 | test_options_flow.py | 2 天 |

### Phase 4：模块化技能（2-3 周）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 创建 SKILL.md 文件 | skills/*.md | 3 天 |
| 标准化接口 | 各模块 | 5 天 |
| 文档更新 | docs/ | 2 天 |

---

## 六、预期收益

| 融合项 | 预期收益 | 风险 |
|--------|----------|------|
| 反叙事约束 | 提高分析准确性，减少误导性结论 | 低 |
| 场景分析 | 提供概率加权的决策依据 | 中 |
| 期权流分析 | 增加市场情绪维度 | 高（数据源依赖） |
| 模块化技能 | 提高可扩展性和可维护性 | 低 |

---

## 七、总结

**ai-investment-skills 仓库的核心价值**：

1. **彩票期权过滤器**：独特的算法，揭示真实机构动向
2. **反叙事约束**：防止 AI 构建误导性叙事
3. **9 波分析管道**：系统化的多维度分析框架
4. **多智能体协调**：高效利用多个专业智能体

**与 QuantNova 的融合策略**：

- **立即实施**：反叙事约束、场景分析
- **中期实施**：期权流分析、模块化技能
- **长期规划**：新闻情绪引擎、价格监控警报

**关键启示**：

> "从真实的交易错误中学习，而不是从理论中学习。"
> —— ai-investment-skills 作者

该仓库的所有创新都来自实战经验，这与 QuantNova 的"推理重于规则"理念高度一致。

---

*本分析由 WorkBuddy 于 2026-06-17 生成*
