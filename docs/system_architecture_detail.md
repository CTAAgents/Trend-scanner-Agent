# QuantNova 系统架构详细文档

> 版本：v2.1.0 | 创建日期：2026-06-20 | 简化版
> 状态：核心闭环已验证

---

## 一、层级架构（10层）

```
┌─────────────────────────────────────────────────────────────────────┐
│                    QuantNova 层级架构 (v2.1.0)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 10: 配置层 (Configuration)                                   │
│  ├── trend_scanner_config.py - 扫描配置                             │
│  └── control_variable.py - 控制变量                                 │
│                                                                     │
│  Layer 9: 记忆层 (Memory)                                           │
│  ├── manager.py - 记忆管理器                                        │
│  ├── experience.py - 经验记忆                                       │
│  ├── duckdb_store.py - DuckDB存储                                  │
│  └── evolution.py - 进化记忆                                        │
│                                                                     │
│  Layer 8: 数据层 (Data)                                             │
│  ├── data_sync.py - 数据同步                                        │
│  ├── data_store.py - 数据存储                                       │
│  ├── data_validator.py - 数据校验                                   │
│  ├── futures_data_router.py - 期货数据路由                          │
│  └── securities_data_router.py - 证券数据路由                       │
│                                                                     │
│  Layer 7: 因子评估层 (Factor Evaluation)                            │
│  ├── factor_evaluator.py - 因子评估                                 │
│  ├── factor_validator.py - 因子验证                                 │
│  ├── factor_gate.py - 因子门控                                      │
│  └── evolver.py - 进化管理                                          │
│                                                                     │
│  Layer 6: 证券子系统 (Securities)                                   │
│  ├── provider.py - 证券数据提供者                                   │
│  ├── market_context.py - 市场上下文                                 │
│  ├── factor_library.py - 因子库                                     │
│  └── risk_manager.py - 风控管理                                     │
│                                                                     │
│  Layer 5: 期货子系统 (Futures)                                      │
│  ├── provider.py - 期货数据提供者                                   │
│  ├── market_context.py - 市场上下文                                 │
│  ├── factor_library.py - 因子库                                     │
│  └── risk_manager.py - 风控管理                                     │
│                                                                     │
│  Layer 4: 风控层 (Risk Control)                                     │
│  ├── crowding_detector.py - 拥挤度检测                              │
│  ├── deployment_risk.py - 部署风险                                  │
│  ├── return_attributor.py - 收益归因                                │
│  └── audit_trail.py - 审计轨迹                                      │
│                                                                     │
│  Layer 3: 推理层 (Reasoning)                                        │
│  ├── reasoner.py - LLM推理引擎                                      │
│  ├── debater.py - 辩论引擎                                          │
│  ├── brief.py - 简报生成                                            │
│  ├── scenario_analyzer.py - 场景分析                                │
│  └── prompt_router.py - Prompt路由                                  │
│                                                                     │
│  Layer 2: 基本面分析层 (Fundamental)                                │
│  ├── news_crawler.py - 新闻抓取                                     │
│  ├── supply_demand.py - 供需数据                                    │
│  └── geopolitical.py - 地缘政治                                    │
│                                                                     │
│  Layer 1: 指标计算层 (Indicators)                                   │
│  ├── indicator_engine.py - 指标引擎                                 │
│  ├── indicator_hub.py - 指标中心                                    │
│  ├── multi_dimension_screener.py - 多维筛选                         │
│  ├── scoring_analytics.py - 评分分析                                │
│  └── macro_state.py - 宏观状态                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、数据流

```
数据源（TqSdk/通达信MCP/AKShare）
    ↓
Layer 8: 数据层
    ├── data_sync.py - 同步数据
    ├── data_validator.py - 校验数据
    └── data_store.py - 存储数据
    ↓
Layer 1: 指标计算层
    ├── indicator_engine.py - 计算技术指标
    └── multi_dimension_screener.py - 多维筛选
    ↓
Layer 2: 基本面分析层
    ├── news_crawler.py - 抓取新闻
    ├── supply_demand.py - 获取供需数据
    └── geopolitical.py - 追踪地缘政治
    ↓
Layer 5/6: 市场子系统
    ├── provider.py - 获取市场数据
    └── market_context.py - 组装市场上下文
    ↓
Layer 9: 记忆层
    └── experience.py - 检索历史经验
    ↓
Layer 3: 推理层
    ├── reasoner.py - LLM推理
    ├── debater.py - 辩论验证
    └── brief.py - 生成简报
    ↓
Layer 4: 风控层
    ├── crowding_detector.py - 检测拥挤度
    ├── deployment_risk.py - 评估部署风险
    └── audit_trail.py - 记录审计轨迹
    ↓
Layer 7: 因子评估层
    ├── factor_evaluator.py - 评估因子效果
    └── evolver.py - 进化优化
    ↓
输出：交易决策简报
```

---

## 三、核心工作流程

### 3.1 日常扫描流程

```
1. 数据同步（15:30收盘后）
   ├── 期货数据：TqSdk获取K线
   ├── 证券数据：通达信MCP获取K线
   └── 基本面数据：AKShare获取库存/仓单
   ↓
2. 指标计算
   ├── 技术指标：EMA/RSI/MACD/ATR等
   └── 基本面指标：库存变化/仓单变化
   ↓
3. 信号生成
   ├── 加载最优参数（signal_params.json）
   ├── 应用参数生成信号
   └── 记录信号参数
   ↓
4. 辩论验证
   ├── 多头观点（鹰派）
   ├── 空头观点（鸽派）
   └── 辩论结论
   ↓
5. 风控检查
   ├── 仓位计算
   ├── 止损计算
   └── 风险等级评估
   ↓
6. 输出决策简报
```

### 3.2 因子进化流程

```
1. 因子评估
   ├── IC计算（因子与未来收益相关性）
   ├── ICIR计算（因子稳定性）
   └── 因子有效性判断
   ↓
2. 因子门控
   ├── 通过条件：|IC|>0.03, |ICIR|>0.5
   ├── 通过：进入因子库
   └── 未通过：丢弃或调整
   ↓
3. 进化优化
   ├── 参数调整
   ├── 组合优化
   └── 新因子生成
   ↓
4. 经验记忆
   ├── 记录因子参数
   ├── 记录表现指标
   └── 存储市场环境
```

### 3.3 自优化闭环

```
1. 交易执行
   ├── 记录入场价格
   ├── 记录仓位大小
   └── 记录止损位置
   ↓
2. 结果记录
   ├── 记录盈亏
   ├── 记录持仓时间
   └── 记录信号准确率
   ↓
3. 轨迹分析
   ├── 入场时机分析
   ├── 出场时机分析
   └── 仓位管理分析
   ↓
4. 故障归因
   ├── 信号错误
   ├── 时机错误
   └── 仓位错误
   ↓
5. LLM反思
   ├── 分析决策过程
   ├── 识别错误原因
   └── 生成改进方向
   ↓
6. 规则优化
   ├── 调整信号阈值
   ├── 优化仓位计算
   └── 改进止损止盈
   ↓
7. 过拟合审计
   ├── 检查样本内/外表现
   ├── 检查参数敏感性
   └── 检查市场环境适应性
   ↓
8. 经验存储
   ├── 记录规则变更
   ├── 记录表现对比
   └── 更新记忆系统
```

---

## 四、业务逻辑

### 4.1 信号生成逻辑

```python
# 自优化参数
params = load_params('signal_params.json')

# 多头条件
if ema_short > ema_long and rsi > params['bullish_rsi_threshold']:
    signal = '多头'
    strength = calculate_strength(rsi, ema_diff)

# 空头条件
elif ema_short < ema_long and rsi < params['bearish_rsi_threshold']:
    signal = '空头'
    strength = calculate_strength(rsi, ema_diff)

# 震荡
else:
    signal = '震荡'
    strength = 0
```

### 4.2 辩论逻辑

```python
# 多头观点（鹰派）
bull_case = {
    'technical': 'EMA金叉，RSI超卖反弹',
    'fundamental': '库存低位，需求支撑',
    'confidence': 0.7
}

# 空头观点（鸽派）
bear_case = {
    'technical': 'EMA死叉，趋势向下',
    'fundamental': '供应过剩，需求疲软',
    'confidence': 0.6
}

# 辩论结论
if bull_case['confidence'] > bear_case['confidence']:
    conclusion = '多头占优'
else:
    conclusion = '空头占优'
```

### 4.3 风控逻辑

```python
# 仓位计算
total_capital = 300000  # 30万
position_ratio = 0.30   # 30%仓位
per_symbol_capital = total_capital * position_ratio / num_symbols

# 止损计算（2*ATR）
stop_loss_distance = 2 * atr14
stop_loss_amount = lots * contract_multiplier * stop_loss_distance

# 风险等级
if signal_strength > 60:
    risk_level = '低风险'
elif signal_strength > 30:
    risk_level = '中风险'
else:
    risk_level = '高风险'
```

---

## 五、数据源优先级

| 市场 | 首选 | 第二 | 第三 |
|------|------|------|------|
| 期货K线 | TqSdk | 通达信MCP | - |
| 期货库存 | AKShare | - | - |
| 证券行情 | 通达信MCP | NeoData | WeStock |
| 宏观数据 | 通达信MCP | AKShare | - |
| 研报数据 | 通达信MCP | - | - |

---

## 六、模块依赖关系

```
indicators/ → 基础计算，无依赖
fundamental/ → 基础数据获取，无依赖
futures/ → 依赖 indicators/, fundamental/
securities/ → 依赖 indicators/, fundamental/
reasoning/ → 依赖所有子系统
risk/ → 依赖 reasoning/
evolution/ → 依赖 indicators/, reasoning/
core/data/ → 依赖数据源
core/memory/ → 依赖 core/data/
```

---

*本文档基于简化后的架构编写，反映当前系统状态。*
