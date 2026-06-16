# Trend-Scanner-Agent v5.0 优化升级方案

> 版本：v1.0 | 创建日期：2026-06-16
> 论文基础：Agentic AI for Factor Investing (2603.14288) + FactorEngine (2603.16365)
> 当前聚焦：期货市场 | 未来方向：股票市场扩展

---

## 一、升级目标

### 1.1 核心目标

将系统从"LLM 生成因子 + 规则筛选"升级为**闭环迭代因子进化引擎**：

```
当前 (v4.0):  LLM 生成因子 → 验证 → 使用（单次）
目标 (v5.0):  生成 → 执行 → 评估 → 门控 → 记忆 → 反馈 → 再生成（闭环迭代）
```

### 1.2 三大核心改进

| 改进 | 来源 | 核心思想 |
|------|------|---------|
| 截面 IC/ICIR 因子评估 | Paper 1 + 2 | 从单品种时序指标升级为截面预测能力评估 |
| 闭环迭代进化引擎 | Paper 1 | Generate→Eval→Gate→Memory 闭环 |
| 逻辑-参数分离优化 | Paper 2 | LLM 负责创意，贝叶斯负责调参 |

### 1.3 远期方向

当前阶段聚焦期货市场（60+ 品种），验证闭环有效后，向股票市场扩展：
- A 股：3000+ 只股票，截面样本量更大，IC 统计更可靠
- 数据源：通达信 MCP（已接入）+ Tushare/AKShare
- 因子库：需要重新构建（股票因子 vs 期货因子差异大）

---

## 二、系统架构演进

### 2.1 v4.0 当前架构

```
scan_opportunities.py
  → DataSourceFactory.get_kline()
  → IndicatorEngine.compute_all()
  → MultiIndicatorConsensus.analyze()
  → 信号输出 (ER/TSI/R²/ADX)

FactorGenerator
  → LLM 生成因子代码
  → FactorValidator 验证
  → 输出因子代码（单次，无迭代）

Evolver Agent
  → TrajectoryAnalyzer 分析交易历史
  → 参数调整建议
  → 无因子进化能力
```

### 2.2 v5.0 目标架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    FactorEvolutionEngine (新增)                   │
│                                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │ 假设生成器 │→│ 执行引擎  │→│ 评估引擎  │→│ 门控决策  │     │
│  │ (已有)    │   │ (新增)   │   │ (新增)   │   │ (新增)   │     │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │
│       ↑                                              │           │
│       │         ┌──────────┐                         │           │
│       └─────────│ 记忆引擎  │←────────────────────────┘           │
│                 │ (已有)    │                                     │
│                 └──────────┘                                     │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    多因子组合模型 (新增)                           │
│  精英因子 → LightGBM/XGBoost → 组合信号 → 仓位建议              │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    scan_opportunities.py (增强)                   │
│  60 品种 × 多因子组合 → 综合信号 → 输出                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、Phase 实施计划

### Phase 1: 截面 IC/ICIR 因子评估体系

**目标**：从单品种时序指标升级为截面预测能力评估

**新增文件**：
- `scripts/trend_scanner/factor_evaluator.py` — 截面 IC/ICIR 计算引擎

**核心逻辑**：

```python
class FactorEvaluator:
    """截面因子评估器"""

    def compute_cross_sectional_ic(self, factor_values: pd.DataFrame,
                                    returns: pd.DataFrame) -> pd.Series:
        """
        计算每日截面 IC（因子值 vs 次日收益率的 Spearman 相关）

        Args:
            factor_values: DataFrame, index=date, columns=symbol, values=因子值
            returns: DataFrame, index=date, columns=symbol, values=次日收益率

        Returns:
            Series, index=date, values=IC
        """
        ic_series = pd.Series(index=factor_values.index, dtype=float)
        for date in factor_values.index:
            fv = factor_values.loc[date].dropna()
            ret = returns.loc[date].dropna()
            common = fv.index.intersection(ret.index)
            if len(common) >= 10:  # 最少 10 个品种
                ic_series[date] = fv[common].corr(ret[common], method='spearman')
        return ic_series

    def evaluate_factor(self, factor_values: pd.DataFrame,
                        returns: pd.DataFrame) -> Dict:
        """
        综合评估因子

        Returns:
            {
                'ic_mean': float,       # IC 均值
                'ic_std': float,        # IC 标准差
                'icir': float,          # IC 均值/IC 标准差
                'rank_ic_mean': float,  # Rank IC 均值
                'rank_icir': float,     # Rank ICIR
                'ic_positive_pct': float,  # IC > 0 的比例
                't_stat': float,        # t 统计量
                'long_short_sharpe': float,  # 多空组合 Sharpe
                'decision': str,        # 'promote' / 'observe' / '淘汰'
            }
        """
        ic = self.compute_cross_sectional_ic(factor_values, returns)
        # ... 计算各项指标
        # 门控决策
        icir = ic.mean() / ic.std() if ic.std() > 0 else 0
        if abs(icir) >= 1.0:
            decision = 'promote'
        elif abs(icir) < 0.5:
            decision = 'eliminate'
        else:
            decision = 'observe'
        return {...}
```

**数据需求**：
- 60 个品种 × 120 天 K 线数据（已就绪，DuckDB 中有 23 个品种，正在同步剩余品种）
- 每日截面：60 个品种的因子值 + 次日收益率

**门控阈值**（参考 Paper 1，预设不可调）：

| 指标 | 晋升阈值 | 淘汰阈值 | 说明 |
|------|---------|---------|------|
| \|ICIR\| | >= 1.0 | < 0.5 | 核心指标 |
| IC > 0 比例 | >= 55% | < 45% | 方向一致性 |
| t 统计量 | >= 2.0 | < 1.0 | 统计显著性 |
| 多空 Sharpe | >= 1.0 | < 0.5 | 组合贡献 |

**交付物**：
- `scripts/trend_scanner/factor_evaluator.py`
- `tests/test_factor_evaluator.py`
- 评估报告模板

**预计工期**：3-5 天

---

### Phase 2: 闭环迭代因子进化引擎

**目标**：构建 Generate→Eval→Gate→Memory 闭环迭代机制

**新增文件**：
- `scripts/trend_scanner/factor_evolution_engine.py` — 闭环进化引擎

**核心逻辑**：

```python
class FactorEvolutionEngine:
    """闭环迭代因子进化引擎"""

    def __init__(self, generator, executor, evaluator, gate, memory):
        self.generator = generator      # FactorGenerator (已有)
        self.executor = executor        # FactorExecutor (新增)
        self.evaluator = evaluator      # FactorEvaluator (Phase 1)
        self.gate = gate                # FactorGate (新增)
        self.memory = memory            # MemoryBridge (已有)

    def evolve(self, max_rounds: int = 10, candidates_per_round: int = 5):
        """
        迭代进化主循环

        Args:
            max_rounds: 最大迭代轮数
            candidates_per_round: 每轮候选因子数
        """
        for round_num in range(1, max_rounds + 1):
            print(f"=== 迭代轮次 {round_num}/{max_rounds} ===")

            # [1] 生成候选因子
            # 注入历史反馈：哪些变量/算子有效，哪些无效
            feedback = self.memory.get_evolution_feedback()
            candidates = self.generator.generate_batch(
                count=candidates_per_round,
                feedback=feedback
            )

            # [2] 执行因子（计算截面因子值）
            factor_values = {}
            for candidate in candidates:
                values = self.executor.execute(candidate.code, self.kline_data)
                if values is not None:
                    factor_values[candidate.name] = values

            # [3] 评估因子
            evaluations = {}
            for name, values in factor_values.items():
                evaluations[name] = self.evaluator.evaluate_factor(
                    values, self.returns
                )

            # [4] 门控决策
            for name, eval_result in evaluations.items():
                decision = self.gate.decide(eval_result)
                self.memory.store_factor_evaluation(name, eval_result, decision)

                if decision == 'promote':
                    self.promoted_factors.append(name)
                    print(f"  [晋升] {name} ICIR={eval_result['icir']:.2f}")
                elif decision == 'eliminate':
                    print(f"  [淘汰] {name} ICIR={eval_result['icir']:.2f}")
                else:
                    print(f"  [观察] {name} ICIR={eval_result['icir']:.2f}")

            # [5] 检查终止条件
            if len(self.promoted_factors) >= 10:
                print(f"已晋升 {len(self.promoted_factors)} 个因子，提前终止")
                break

        return self.promoted_factors
```

**关键设计**：
- 每轮生成 5 个候选因子（不是 1 个，增加搜索多样性）
- 门控阈值预设不可调（防 p-hacking）
- 最多迭代 10 轮，避免无限搜索
- 每轮反馈注入下一轮的生成提示词

**交付物**：
- `scripts/trend_scanner/factor_evolution_engine.py`
- `scripts/trend_scanner/factor_executor.py` — 因子代码执行引擎
- `scripts/trend_scanner/factor_gate.py` — 门控决策模块
- `tests/test_factor_evolution.py`

**预计工期**：5-7 天

---

### Phase 3: 逻辑-参数分离的贝叶斯优化

**目标**：LLM 负责因子逻辑创意，贝叶斯优化负责参数调优

**新增文件**：
- `scripts/trend_scanner/factor_param_optimizer.py` — 参数优化器

**核心逻辑**：

```python
class FactorParamOptimizer:
    """因子参数贝叶斯优化器"""

    def optimize(self, factor_code: str, param_space: Dict,
                 kline_data: Dict, returns: pd.DataFrame,
                 n_trials: int = 100) -> Dict:
        """
        用 Optuna 贝叶斯优化因子参数

        Args:
            factor_code: 因子代码（含 params 占位符）
            param_space: 参数空间定义
                {
                    'window': {'type': 'int', 'low': 5, 'high': 60},
                    'decay': {'type': 'float', 'low': 0.5, 'high': 0.99},
                }
            kline_data: {symbol: DataFrame}
            returns: 收益率矩阵
            n_trials: 优化试验次数

        Returns:
            {
                'best_params': Dict,
                'best_icir': float,
                'optimization_history': List[Dict]
            }
        """
        import optuna

        def objective(trial):
            params = {}
            for name, spec in param_space.items():
                if spec['type'] == 'int':
                    params[name] = trial.suggest_int(name, spec['low'], spec['high'])
                elif spec['type'] == 'float':
                    params[name] = trial.suggest_float(name, spec['low'], spec['high'])

            # 用参数执行因子
            factor_values = self.executor.execute_with_params(
                factor_code, params, kline_data
            )
            if factor_values is None:
                return float('-inf')

            # 计算 ICIR
            eval_result = self.evaluator.evaluate_factor(factor_values, returns)
            return abs(eval_result['icir'])

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials)

        return {
            'best_params': study.best_params,
            'best_icir': study.best_value,
            'optimization_history': [
                {'trial': t.number, 'params': t.params, 'icir': t.value}
                for t in study.trials
            ]
        }
```

**与进化引擎集成**：
- 因子代码中参数声明为 `params['window']` 占位符
- 逻辑变异由 LLM 完成（宏进化）
- 参数优化由贝叶斯完成（微进化）
- 两者交替进行：LLM 修改逻辑 → 贝叶斯优化参数 → 评估 → 反馈

**依赖**：
- `optuna` 库（需安装）
- `scipy` 库（已有）

**交付物**：
- `scripts/trend_scanner/factor_param_optimizer.py`
- `tests/test_factor_param_optimizer.py`

**预计工期**：3-4 天

---

### Phase 4: 研报知识注入的种子因子库

**目标**：从研报中提取因子逻辑，构建高质量种子因子池

**增强文件**：
- `scripts/trend_scanner/report_parser.py` — 增强因子提取能力

**新增文件**：
- `scripts/trend_scanner/seed_factor_pool.py` — 种子因子池管理

**核心逻辑**：

```
研报 PDF
  ↓ report_parser.py (已有，增强)
结构化因子逻辑 (JSON)
  ↓ seed_factor_pool.py (新增)
  ├── 核心思想提取
  ├── 经济原理解释
  ├── 伪代码生成
  └── 代码生成 + 验证
  ↓
种子因子池 (>= 20 个有效种子)
  ↓ FactorEvolutionEngine (Phase 2)
演化优化后的因子
```

**种子因子池管理**：

```python
class SeedFactorPool:
    """种子因子池管理器"""

    def __init__(self, pool_path: str = "data/seed_factors.json"):
        self.pool_path = pool_path
        self.pool = self._load_pool()

    def add_seed(self, name: str, code: str, logic: str,
                 source: str, economic_rationale: str):
        """添加种子因子"""
        seed = {
            'name': name,
            'code': code,
            'logic': logic,
            'source': source,  # 来源研报
            'economic_rationale': economic_rationale,
            'status': 'pending',  # pending / validated / evolved
            'created_at': datetime.now().isoformat(),
        }
        self.pool.append(seed)
        self._save_pool()

    def get_pending_seeds(self) -> List[Dict]:
        """获取待验证的种子因子"""
        return [s for s in self.pool if s['status'] == 'pending']

    def update_status(self, name: str, status: str, eval_result: Dict = None):
        """更新种子状态"""
        for seed in self.pool:
            if seed['name'] == name:
                seed['status'] = status
                if eval_result:
                    seed['evaluation'] = eval_result
                break
        self._save_pool()
```

**交付物**：
- `scripts/trend_scanner/seed_factor_pool.py`
- 增强 `scripts/trend_scanner/report_parser.py`
- 种子因子池初始数据（从已有研报提取）

**预计工期**：3-5 天

---

### Phase 5: 多因子组合模型

**目标**：从单因子信号升级为多因子组合预测

**新增文件**：
- `scripts/trend_scanner/multi_factor_model.py` — 多因子组合模型

**核心逻辑**：

```python
class MultiFactorModel:
    """多因子组合模型"""

    def __init__(self, model_type: str = 'lightgbm'):
        self.model_type = model_type
        self.model = None
        self.factor_names = []

    def train(self, factor_values: pd.DataFrame, returns: pd.DataFrame):
        """
        训练多因子模型

        Args:
            factor_values: DataFrame, index=date, columns=[factor1, factor2, ...]
                           每行是某日所有品种的因子值（展平）
            returns: Series, 对应的次日收益率
        """
        if self.model_type == 'lightgbm':
            import lightgbm as lgb
            self.model = lgb.LGBMRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
            )
        self.model.fit(factor_values, returns)

    def predict(self, factor_values: pd.DataFrame) -> pd.Series:
        """预测组合信号"""
        return pd.Series(
            self.model.predict(factor_values),
            index=factor_values.index
        )

    def get_feature_importance(self) -> Dict[str, float]:
        """获取因子重要性"""
        return dict(zip(self.factor_names, self.model.feature_importances_))
```

**与扫描器集成**：
- `scan_opportunities.py` 使用多因子组合信号替代单一指标
- 综合信号 = LightGBM(因子1, 因子2, ..., 因子N)
- 信号强度由模型预测值决定

**交付物**：
- `scripts/trend_scanner/multi_factor_model.py`
- `tests/test_multi_factor_model.py`

**预计工期**：3-4 天

---

### Phase 6: 失败经验库 + 轨迹感知生成

**目标**：从失败中学习，避免重复错误

**增强文件**：
- `scripts/trend_scanner/trajectory_analyzer.py` — 增强因子失败分析
- `scripts/trend_scanner/factor_generator.py` — 注入失败经验

**新增文件**：
- `scripts/trend_scanner/factor_experience_db.py` — 因子经验数据库

**核心逻辑**：

```python
class FactorExperienceDB:
    """因子经验数据库"""

    def __init__(self, db_path: str = "data/factor_experience.json"):
        self.db_path = db_path
        self.experiences = self._load()

    def record_evolution_trajectory(self, factor_id: str,
                                     trajectory: List[Dict]):
        """
        记录因子演化轨迹

        trajectory 示例:
        [
            {'round': 1, 'logic': 'simple_momentum', 'icir': 0.3, 'decision': 'observe'},
            {'round': 2, 'logic': 'adaptive_momentum', 'icir': 0.8, 'decision': 'promote'},
            {'round': 3, 'logic': 'adaptive_momentum+volume', 'icir': 0.6, 'decision': 'eliminate'},
        ]
        """
        experience = {
            'factor_id': factor_id,
            'trajectory': trajectory,
            'failure_patterns': self._extract_failure_patterns(trajectory),
            'success_patterns': self._extract_success_patterns(trajectory),
            'lessons': self._extract_lessons(trajectory),
        }
        self.experiences.append(experience)
        self._save()

    def get_failure_lessons(self, limit: int = 10) -> List[str]:
        """获取最近的失败教训（用于注入生成器提示词）"""
        lessons = []
        for exp in self.experiences[-limit:]:
            lessons.extend(exp.get('lessons', []))
        return lessons

    def get_success_patterns(self, limit: int = 10) -> List[str]:
        """获取最近的成功模式"""
        patterns = []
        for exp in self.experiences[-limit:]:
            patterns.extend(exp.get('success_patterns', []))
        return patterns
```

**与生成器集成**：
- 因子生成时，注入最近 10 条失败教训
- LLM 提示词增加："以下是你之前尝试过的失败方案，请避免类似模式"
- 实现"从失败中学习"

**交付物**：
- `scripts/trend_scanner/factor_experience_db.py`
- 增强 `scripts/trend_scanner/factor_generator.py`

**预计工期**：2-3 天

---

## 四、时间线总览

```
Week 1 (6/16-6/22):
  Phase 1: 截面 IC/ICIR 因子评估体系
  ├── factor_evaluator.py
  ├── 门控阈值定义
  └── 与现有扫描器集成

Week 2 (6/23-6/29):
  Phase 2: 闭环迭代因子进化引擎
  ├── factor_evolution_engine.py
  ├── factor_executor.py
  ├── factor_gate.py
  └── 与 FactorGenerator 集成

Week 3 (6/30-7/6):
  Phase 3: 贝叶斯参数优化
  ├── factor_param_optimizer.py
  └── 与进化引擎集成

Week 4 (7/7-7/13):
  Phase 4: 研报种子因子库
  ├── seed_factor_pool.py
  └── report_parser.py 增强

Week 5 (7/14-7/20):
  Phase 5: 多因子组合模型
  ├── multi_factor_model.py
  └── 与 scan_opportunities.py 集成

Week 6 (7/21-7/27):
  Phase 6: 失败经验库
  ├── factor_experience_db.py
  └── 与因子生成器集成

Week 7+:
  集成测试 + 性能优化 + 文档更新
```

---

## 五、股票市场扩展规划（远期）

### 5.1 差异分析

| 维度 | 期货 | 股票 |
|------|------|------|
| 品种数量 | 60+ | 3000+ (A 股) |
| 截面样本 | 小（IC 统计不稳定） | 大（IC 统计可靠） |
| 因子类型 | 趋势/动量/波动率 | 价值/质量/动量/规模 |
| 数据源 | TqSdk + 通达信 MCP | Tushare + AKShare + 通达信 MCP |
| 交易机制 | T+0, 双向 | T+1, 单向（融券除外） |
| 持仓周期 | 短（日内~数周） | 中长（数周~数月） |

### 5.2 扩展路径

```
Phase A: 数据层扩展
  ├── 接入股票数据源（Tushare/AKShare）
  ├── 构建股票 K 线数据库（DuckDB）
  └── 股票因子库（价值/质量/动量/规模）

Phase B: 因子层扩展
  ├── 股票特有因子：PE/PB/ROE/市值/换手率
  ├── 行业中性化处理
  └── 市值分层回测

Phase C: 模型层扩展
  ├── 多因子模型适配（LightGBM 已支持）
  ├── 行业轮动策略
  └── 组合优化（均值-方差）
```

### 5.3 复用性设计

当前期货系统的以下模块可直接复用于股票：
- FactorEvolutionEngine（闭环进化引擎）
- FactorEvaluator（截面 IC/ICIR 评估）
- FactorParamOptimizer（贝叶斯参数优化）
- MultiFactorModel（多因子组合模型）
- MemoryBridge（记忆系统）

需要新增/修改的模块：
- DataSource（股票数据源适配器）
- FactorGenerator（股票因子语法）
- IndicatorEngine（股票特有指标）

---

## 六、风险与约束

### 6.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| IC 统计不稳定（60 品种样本小） | 门控决策不可靠 | 延长评估窗口（120 天），降低阈值 |
| LLM 生成因子质量不稳定 | 候选因子无效 | 增加候选数量（每轮 10 个），引入种子因子 |
| 贝叶斯优化过拟合 | 参数在 OOS 失效 | Walk-Forward 验证，IS/OOS 分离 |
| 进化引擎 LLM 成本高 | API 费用增加 | 限制迭代轮数（10 轮），本地模型兜底 |

### 6.2 工程约束

- 系统 Python 版本：3.12.9（系统级，不可更改）
- 新增依赖：optuna（贝叶斯优化）、lightgbm（多因子模型）
- 数据库：DuckDB（K 线）、SQLite（元数据），无需新增
- LLM：WorkBuddy Mimo-V2.5-Pro（已有）

---

## 七、成功指标

| 阶段 | 指标 | 目标值 |
|------|------|-------|
| Phase 1 完成 | 因子评估器可用 | 10 个因子评估报告 |
| Phase 2 完成 | 闭环进化可运行 | 1 轮完整迭代（5 候选→评估→门控） |
| Phase 3 完成 | 参数优化可运行 | 1 个因子优化完成（ICIR 提升 >= 20%） |
| Phase 4 完成 | 种子因子池 >= 20 | 从 3 份研报提取 20+ 种子 |
| Phase 5 完成 | 多因子模型可用 | OOS Sharpe >= 1.5 |
| Phase 6 完成 | 失败经验库可用 | 10 条失败经验记录 |
| 全部完成 | 系统 ICIR >= 1.0 | OOS 年化 Sharpe >= 2.0 |
