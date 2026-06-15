# Trend-scanner-Agent v4.0 实施计划

> 版本：v1.0 | 创建日期：2026-06-15
> 状态：进行中

## 一、项目概述

### 1.1 目标
基于 FactorEngine、FinCon、GIFT 三篇论文的核心思想，将 Trend-scanner-Agent 从 v3.0 升级到 v4.0，实现：
- **因子即代码**：Scanner 从固定指标升级为 LLM 生成的动态因子
- **多角色协作**：Debater 从单 Agent self-debate 升级为多角色对抗
- **RL 接口自设计**：Evolver 从规则优化升级为 LLM 引导的 RL 框架
- **知识注入闭环**：实现研报→因子→验证→入库的自动化流水线

### 1.2 当前架构
```
Orchestrator Agent（主协调）
  ├── Scanner 脚本（纯 Python）→ 固定技术指标
  ├── Reasoner Agent（LLM 推理）→ 生成决策简报
  ├── Debater Agent（self-debate）→ 单 Agent 内部辩论
  ├── Monitor 脚本（纯 Python）→ 持仓风险监控
  └── Evolver Agent（规则优化）→ 基于规则的参数调整
```

### 1.3 目标架构
```
Orchestrator Agent（主协调）
  ├── Scanner 脚本（纯 Python）
  │     ├── 传统技术指标计算
  │     └── 动态因子生成器（LLM 引导）  ← FactorEngine
  │
  ├── Reasoner Agent（LLM 推理）
  │     ├── 市场状态分析
  │     └── 知识注入（研报、经验）  ← FactorEngine
  │
  ├── Debater Agent（多角色协作）  ← FinCon
  │     ├── 分析师角色
  │     ├── 基本面研究员角色
  │     ├── 风控官角色
  │     └── 概念性语言反馈
  │
  ├── Monitor 脚本（纯 Python）
  │     └── 持仓风险监控
  │
  └── Evolver Agent（LLM 引导的 RL）  ← GIFT
        ├── 状态空间设计
        ├── 奖励函数设计
        ├── 诊断引导修正
        └── 轨迹感知优化
```

---

## 二、任务清单

### Phase 1: 动态因子生成模块（第 1-2 周）— 高优先级

| 任务 ID | 任务描述 | 状态 | 交付物 |
|---------|---------|------|--------|
| 1.1 | 创建因子生成器基础框架 | 待开始 | `scripts/trend_scanner/factor_generator.py` |
| 1.2 | 实现 LLM 因子生成接口 | 待开始 | `scripts/trend_scanner/llm_factor_client.py` |
| 1.3 | 创建因子验证模块 | 待开始 | `scripts/trend_scanner/factor_validator.py` |
| 1.4 | 建立因子知识库 | 待开始 | `data/factor_knowledge.json` |
| 1.5 | 与 Scanner 脚本集成 | 待开始 | 修改 `tools/scan_opportunities.py` |
| 1.6 | 编写单元测试 | 待开始 | `tests/test_factor_generator.py` |

### Phase 2: 轨迹感知优化器（第 2-3 周）— 高优先级

| 任务 ID | 任务描述 | 状态 | 交付物 |
|---------|---------|------|--------|
| 2.1 | 设计轨迹分析框架 | 待开始 | `scripts/trend_scanner/trajectory_analyzer.py` |
| 2.2 | 实现失败学习机制 | 待开始 | `scripts/trend_scanner/failure_learner.py` |
| 2.3 | 创建优化规则生成器 | 待开始 | `scripts/trend_scanner/optimization_rule_generator.py` |
| 2.4 | 与现有 Evolver 集成 | 待开始 | 修改 `agents/evolver.md` |
| 2.5 | 编写单元测试 | 待开始 | `tests/test_trajectory_analyzer.py` |

### Phase 3: 研报知识注入流水线（第 3-4 周）— 高优先级

| 任务 ID | 任务描述 | 状态 | 交付物 |
|---------|---------|------|--------|
| 3.1 | 创建研报解析模块 | 待开始 | `scripts/trend_scanner/report_parser.py` |
| 3.2 | 实现因子提取 Agent | 待开始 | `agents/factor_extractor.md` |
| 3.3 | 建立验证流水线 | 待开始 | `scripts/trend_scanner/validation_pipeline.py` |
| 3.4 | 与因子知识库集成 | 待开始 | 修改 `data/factor_knowledge.json` |
| 3.5 | 编写单元测试 | 待开始 | `tests/test_report_parser.py` |

### Phase 4: 多角色 Debater 架构（第 4-5 周）— 中优先级

| 任务 ID | 任务描述 | 状态 | 交付物 |
|---------|---------|------|--------|
| 4.1 | 重构 Debater 为多角色框架 | 待开始 | 修改 `agents/debater.md` |
| 4.2 | 创建分析师角色 | 待开始 | `agents/analyst_role.md` |
| 4.3 | 创建风控官角色 | 待开始 | `agents/risk_officer_role.md` |
| 4.4 | 实现概念性语言反馈 | 待开始 | `scripts/trend_scanner/conceptual_feedback.py` |
| 4.5 | 实现信念传播机制 | 待开始 | `scripts/trend_scanner/belief_propagation.py` |
| 4.6 | 编写单元测试 | 待开始 | `tests/test_multi_debater.py` |

### Phase 5: LLM 引导的 RL 接口设计（第 5-6 周）— 中优先级

| 任务 ID | 任务描述 | 状态 | 交付物 |
|---------|---------|------|--------|
| 5.1 | 设计 RL 接口框架 | 待开始 | `scripts/trend_scanner/rl_interface_designer.py` |
| 5.2 | 实现状态空间设计 | 待开始 | `scripts/trend_scanner/state_space_designer.py` |
| 5.3 | 实现奖励函数设计 | 待开始 | `scripts/trend_scanner/reward_function_designer.py` |
| 5.4 | 实现诊断引导修正 | 待开始 | `scripts/trend_scanner/diagnostic_refiner.py` |
| 5.5 | 与现有 Evolver 集成 | 待开始 | 修改 `agents/evolver.md` |
| 5.6 | 编写单元测试 | 待开始 | `tests/test_rl_interface.py` |

### Phase 6: 集成测试与优化（第 6-7 周）

| 任务 ID | 任务描述 | 状态 | 交付物 |
|---------|---------|------|--------|
| 6.1 | 端到端集成测试 | 待开始 | `tests/integration/test_full_pipeline.py` |
| 6.2 | 性能基准测试 | 待开始 | `tests/benchmark/test_performance.py` |
| 6.3 | 文档更新 | 待开始 | 更新 `SKILL.md`、`README.md` |
| 6.4 | 部署脚本 | 待开始 | `tools/deploy_v4.sh` |

---

## 三、技术设计

### 3.1 动态因子生成模块

#### 3.1.1 架构设计
```python
# scripts/trend_scanner/factor_generator.py

class FactorGenerator:
    """LLM 引导的因子生成器"""
    
    def __init__(self, llm_client, validator):
        self.llm_client = llm_client
        self.validator = validator
        self.factor_knowledge = self._load_factor_knowledge()
    
    def generate_factor(self, market_context: str, research_report: str = None) -> dict:
        """生成可执行的因子代码"""
        # 1. 构建 prompt
        prompt = self._build_generation_prompt(market_context, research_report)
        
        # 2. 调用 LLM 生成因子代码
        factor_code = self.llm_client.generate(prompt)
        
        # 3. 验证因子代码
        validation_result = self.validator.validate(factor_code)
        
        # 4. 如果验证失败，进行修正
        if not validation_result['is_valid']:
            factor_code = self._refine_factor(factor_code, validation_result['errors'])
        
        return {
            'code': factor_code,
            'metadata': self._extract_metadata(factor_code),
            'validation': validation_result
        }
    
    def _build_generation_prompt(self, market_context: str, research_report: str = None) -> str:
        """构建因子生成 prompt"""
        prompt = f"""
你是一个量化因子挖掘专家。请根据以下市场上下文生成一个可执行的因子代码。

## 市场上文
{market_context}

## 因子要求
1. 因子必须是 Python 函数，接收 DataFrame 作为输入
2. 因子返回 Series，值在 [-1, 1] 之间
3. 因子逻辑必须清晰，可解释
4. 优先使用技术指标和价量数据

## 输出格式
```python
def factor(df: pd.DataFrame) -> pd.Series:
    \"\"\"
    因子描述：...
    逻辑：...
    \"\"\"
    # 实现代码
    return result
```
"""
        if research_report:
            prompt += f"\n## 研报参考\n{research_report}\n"
        
        return prompt
    
    def _refine_factor(self, factor_code: str, errors: list) -> str:
        """修正因子代码"""
        refine_prompt = f"""
因子代码存在以下问题：
{errors}

请修正因子代码：
{factor_code}
"""
        return self.llm_client.generate(refine_prompt)
    
    def _extract_metadata(self, factor_code: str) -> dict:
        """提取因子元数据"""
        # 从代码中提取因子名称、描述、逻辑等
        pass
    
    def _load_factor_knowledge(self) -> dict:
        """加载因子知识库"""
        import json
        with open('data/factor_knowledge.json', 'r', encoding='utf-8') as f:
            return json.load(f)
```

#### 3.1.2 因子知识库结构
```json
{
  "factors": [
    {
      "id": "factor_001",
      "name": "动量突破因子",
      "code": "def factor(df): return df['close'].pct_change(5) * (df['volume'] / df['volume'].rolling(20).mean())",
      "description": "结合价格动量和成交量放大，捕捉突破信号",
      "logic": "5日收益率 * 成交量比率",
      "source": "研报_20260601",
      "performance": {
        "ic": 0.05,
        "icir": 1.2,
        "stability": 0.8,
        "sharpe": 1.5
      },
      "regime_effectiveness": {
        "trending": 0.9,
        "ranging": 0.3,
        "volatile": 0.6
      },
      "created_at": "2026-06-15",
      "last_updated": "2026-06-15"
    }
  ],
  "metadata": {
    "version": "1.0",
    "total_factors": 1,
    "last_updated": "2026-06-15"
  }
}
```

### 3.2 轨迹感知优化器

#### 3.2.1 架构设计
```python
# scripts/trend_scanner/trajectory_analyzer.py

class TrajectoryAnalyzer:
    """轨迹感知的优化器"""
    
    def __init__(self, trade_history: list):
        self.trade_history = trade_history
        self.patterns = {}
        self.failure_cases = []
        self.success_cases = []
    
    def analyze_trajectory(self) -> dict:
        """分析交易轨迹"""
        # 1. 分类成功和失败案例
        self._classify_cases()
        
        # 2. 提取模式
        self._extract_patterns()
        
        # 3. 生成优化规则
        optimization_rules = self._generate_optimization_rules()
        
        return {
            'patterns': self.patterns,
            'optimization_rules': optimization_rules,
            'failure_analysis': self._analyze_failures(),
            'success_factors': self._analyze_successes()
        }
    
    def _classify_cases(self):
        """分类成功和失败案例"""
        for trade in self.trade_history:
            if trade['pnl'] > 0:
                self.success_cases.append(trade)
            else:
                self.failure_cases.append(trade)
    
    def _extract_patterns(self):
        """提取模式"""
        # 提取成功模式
        self.patterns['success'] = self._extract_success_patterns()
        
        # 提取失败模式
        self.patterns['failure'] = self._extract_failure_patterns()
    
    def _extract_success_patterns(self) -> list:
        """提取成功模式"""
        patterns = []
        
        # 分析成功案例的共同特征
        for case in self.success_cases:
            # 提取市场状态、入场时机、持仓时间等特征
            pattern = {
                'market_state': case.get('market_state'),
                'entry_timing': case.get('entry_timing'),
                'holding_period': case.get('holding_period'),
                'volatility': case.get('volatility')
            }
            patterns.append(pattern)
        
        return patterns
    
    def _extract_failure_patterns(self) -> list:
        """提取失败模式"""
        patterns = []
        
        # 分析失败案例的共同特征
        for case in self.failure_cases:
            # 提取市场状态、入场时机、持仓时间等特征
            pattern = {
                'market_state': case.get('market_state'),
                'entry_timing': case.get('entry_timing'),
                'holding_period': case.get('holding_period'),
                'volatility': case.get('volatility'),
                'failure_reason': case.get('failure_reason')
            }
            patterns.append(pattern)
        
        return patterns
    
    def _generate_optimization_rules(self) -> list:
        """生成优化规则"""
        rules = []
        
        # 基于失败模式生成避免规则
        for pattern in self.patterns['failure']:
            rule = {
                'type': 'avoidance',
                'condition': f"当市场状态为 {pattern['market_state']} 且波动率为 {pattern['volatility']} 时",
                'action': "避免入场或减小仓位",
                'reason': pattern.get('failure_reason', '历史失败案例')
            }
            rules.append(rule)
        
        # 基于成功模式生成增强规则
        for pattern in self.patterns['success']:
            rule = {
                'type': 'enhancement',
                'condition': f"当市场状态为 {pattern['market_state']} 且波动率为 {pattern['volatility']} 时",
                'action': "增加仓位或延长持仓",
                'reason': '历史成功案例'
            }
            rules.append(rule)
        
        return rules
    
    def _analyze_failures(self) -> dict:
        """分析失败案例"""
        if not self.failure_cases:
            return {'count': 0, 'analysis': '无失败案例'}
        
        # 统计失败原因
        failure_reasons = {}
        for case in self.failure_cases:
            reason = case.get('failure_reason', '未知')
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        
        return {
            'count': len(self.failure_cases),
            'failure_reasons': failure_reasons,
            'avg_loss': sum(case['pnl'] for case in self.failure_cases) / len(self.failure_cases)
        }
    
    def _analyze_successes(self) -> dict:
        """分析成功案例"""
        if not self.success_cases:
            return {'count': 0, 'analysis': '无成功案例'}
        
        return {
            'count': len(self.success_cases),
            'avg_profit': sum(case['pnl'] for case in self.success_cases) / len(self.success_cases),
            'success_factors': self._extract_success_factors()
        }
    
    def _extract_success_factors(self) -> list:
        """提取成功因素"""
        # 分析成功案例的共同因素
        factors = []
        
        # 示例：分析入场时机
        entry_timings = [case.get('entry_timing') for case in self.success_cases if case.get('entry_timing')]
        if entry_timings:
            most_common_timing = max(set(entry_timings), key=entry_timings.count)
            factors.append(f"最佳入场时机: {most_common_timing}")
        
        return factors
```

### 3.3 研报知识注入流水线

#### 3.3.1 架构设计
```python
# scripts/trend_scanner/report_parser.py

class ReportParser:
    """研报解析器"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    def parse_report(self, report_content: str) -> dict:
        """解析研报内容"""
        # 1. 提取关键观点
        key_viewpoints = self._extract_key_viewpoints(report_content)
        
        # 2. 提取数据和逻辑
        data_logic = self._extract_data_logic(report_content)
        
        # 3. 生成因子建议
        factor_suggestions = self._generate_factor_suggestions(key_viewpoints, data_logic)
        
        return {
            'key_viewpoints': key_viewpoints,
            'data_logic': data_logic,
            'factor_suggestions': factor_suggestions
        }
    
    def _extract_key_viewpoints(self, report_content: str) -> list:
        """提取关键观点"""
        prompt = f"""
请从以下研报中提取关键观点，每个观点用一句话概括：

{report_content}

输出格式：
1. 观点1
2. 观点2
...
"""
        response = self.llm_client.generate(prompt)
        
        # 解析响应
        viewpoints = []
        for line in response.split('\n'):
            if line.strip() and line[0].isdigit():
                viewpoint = line.split('.', 1)[1].strip()
                viewpoints.append(viewpoint)
        
        return viewpoints
    
    def _extract_data_logic(self, report_content: str) -> dict:
        """提取数据和逻辑"""
        prompt = f"""
请从以下研报中提取关键数据和逻辑关系：

{report_content}

输出格式：
```json
{
  "data_points": [
    {"metric": "指标名", "value": "数值", "context": "上下文"}
  ],
  "logic_chains": [
    {"cause": "原因", "effect": "结果", "mechanism": "机制"}
  ]
}
```
"""
        response = self.llm_client.generate(prompt)
        
        # 解析 JSON 响应
        try:
            import json
            data_logic = json.loads(response)
            return data_logic
        except:
            return {'data_points': [], 'logic_chains': []}
    
    def _generate_factor_suggestions(self, key_viewpoints: list, data_logic: dict) -> list:
        """生成因子建议"""
        prompt = f"""
基于以下关键观点和数据逻辑，生成因子建议：

## 关键观点
{key_viewpoints}

## 数据逻辑
{data_logic}

请生成 2-3 个因子建议，每个建议包含：
1. 因子名称
2. 因子逻辑描述
3. 预期效果
4. 实现难度

输出格式：
```json
[
  {
    "name": "因子名称",
    "description": "因子逻辑描述",
    "expected_effect": "预期效果",
    "implementation_difficulty": "低/中/高"
  }
]
```
"""
        response = self.llm_client.generate(prompt)
        
        # 解析 JSON 响应
        try:
            import json
            suggestions = json.loads(response)
            return suggestions
        except:
            return []
```

---

## 四、测试用例

### 4.1 动态因子生成模块测试

#### 4.1.1 单元测试
```python
# tests/test_factor_generator.py

import pytest
import pandas as pd
from scripts.trend_scanner.factor_generator import FactorGenerator

class TestFactorGenerator:
    """因子生成器测试"""
    
    def test_generate_factor_with_market_context(self):
        """测试基于市场上下文生成因子"""
        generator = FactorGenerator(llm_client=MockLLMClient(), validator=MockValidator())
        
        market_context = """
        当前市场处于上升趋势，成交量放大，RSI 接近超买区域。
        建议关注动量突破和成交量确认的因子。
        """
        
        result = generator.generate_factor(market_context)
        
        assert 'code' in result
        assert 'metadata' in result
        assert 'validation' in result
        assert result['validation']['is_valid'] == True
    
    def test_generate_factor_with_research_report(self):
        """测试基于研报生成因子"""
        generator = FactorGenerator(llm_client=MockLLMClient(), validator=MockValidator())
        
        market_context = "市场处于震荡状态"
        research_report = """
        研报指出，当前市场波动率较低，适合使用均值回归策略。
        建议关注布林带突破和RSI超买超卖的因子。
        """
        
        result = generator.generate_factor(market_context, research_report)
        
        assert 'code' in result
        assert '研报' in result['metadata']['source']
    
    def test_validate_factor_code(self):
        """测试因子代码验证"""
        validator = FactorValidator()
        
        # 有效因子代码
        valid_code = """
def factor(df):
    return df['close'].pct_change(5)
"""
        result = validator.validate(valid_code)
        assert result['is_valid'] == True
        
        # 无效因子代码
        invalid_code = """
def factor(df):
    return df['close']  # 未归一化
"""
        result = validator.validate(invalid_code)
        assert result['is_valid'] == False
        assert '归一化' in result['errors'][0]
    
    def test_factor_performance_metrics(self):
        """测试因子性能指标计算"""
        validator = FactorValidator()
        
        # 创建测试数据
        import pandas as pd
        import numpy as np
        
        np.random.seed(42)
        dates = pd.date_range('2026-01-01', periods=100)
        prices = np.cumsum(np.random.randn(100)) + 100
        df = pd.DataFrame({'close': prices}, index=dates)
        
        # 测试因子
        def test_factor(df):
            return df['close'].pct_change(5)
        
        metrics = validator.calculate_performance_metrics(test_factor, df)
        
        assert 'ic' in metrics
        assert 'icir' in metrics
        assert 'stability' in metrics
```

#### 4.1.2 集成测试
```python
# tests/integration/test_factor_pipeline.py

import pytest
from scripts.trend_scanner.factor_generator import FactorGenerator
from scripts.trend_scanner.factor_validator import FactorValidator
from scripts.trend_scanner.factor_knowledge_manager import FactorKnowledgeManager

class TestFactorPipeline:
    """因子流水线集成测试"""
    
    def test_full_pipeline(self):
        """测试完整因子生成流水线"""
        # 1. 初始化组件
        llm_client = MockLLMClient()
        validator = FactorValidator()
        knowledge_manager = FactorKnowledgeManager()
        
        generator = FactorGenerator(llm_client, validator)
        
        # 2. 生成因子
        market_context = "市场处于上升趋势"
        factor_result = generator.generate_factor(market_context)
        
        # 3. 验证因子
        assert factor_result['validation']['is_valid'] == True
        
        # 4. 保存到知识库
        knowledge_manager.add_factor(factor_result)
        
        # 5. 验证保存成功
        factors = knowledge_manager.get_factors()
        assert len(factors) > 0
        assert factors[-1]['code'] == factor_result['code']
```

### 4.2 轨迹感知优化器测试

#### 4.2.1 单元测试
```python
# tests/test_trajectory_analyzer.py

import pytest
from scripts.trend_scanner.trajectory_analyzer import TrajectoryAnalyzer

class TestTrajectoryAnalyzer:
    """轨迹分析器测试"""
    
    def test_analyze_trajectory(self):
        """测试轨迹分析"""
        # 创建测试交易历史
        trade_history = [
            {
                'symbol': 'DCE.jm2609',
                'direction': 'LONG',
                'entry_price': 1500,
                'exit_price': 1550,
                'pnl': 50,
                'market_state': 'trending',
                'entry_timing': 'breakout',
                'holding_period': 5,
                'volatility': 'medium'
            },
            {
                'symbol': 'DCE.jm2609',
                'direction': 'LONG',
                'entry_price': 1550,
                'exit_price': 1520,
                'pnl': -30,
                'market_state': 'ranging',
                'entry_timing': 'pullback',
                'holding_period': 3,
                'volatility': 'low',
                'failure_reason': '市场震荡，趋势不明确'
            }
        ]
        
        analyzer = TrajectoryAnalyzer(trade_history)
        result = analyzer.analyze_trajectory()
        
        assert 'patterns' in result
        assert 'optimization_rules' in result
        assert 'failure_analysis' in result
        assert 'success_factors' in result
        
        # 验证失败分析
        assert result['failure_analysis']['count'] == 1
        assert '市场震荡' in result['failure_analysis']['failure_reasons']
    
    def test_generate_optimization_rules(self):
        """测试优化规则生成"""
        trade_history = [
            {
                'symbol': 'DCE.jm2609',
                'direction': 'LONG',
                'pnl': -30,
                'market_state': 'ranging',
                'volatility': 'low',
                'failure_reason': '市场震荡，趋势不明确'
            }
        ]
        
        analyzer = TrajectoryAnalyzer(trade_history)
        result = analyzer.analyze_trajectory()
        
        # 验证生成了避免规则
        avoidance_rules = [r for r in result['optimization_rules'] if r['type'] == 'avoidance']
        assert len(avoidance_rules) > 0
        assert '市场状态为 ranging' in avoidance_rules[0]['condition']
```

### 4.3 研报知识注入流水线测试

#### 4.3.1 单元测试
```python
# tests/test_report_parser.py

import pytest
from scripts.trend_scanner.report_parser import ReportParser

class TestReportParser:
    """研报解析器测试"""
    
    def test_parse_report(self):
        """测试研报解析"""
        parser = ReportParser(llm_client=MockLLMClient())
        
        report_content = """
        焦煤市场分析报告
        
        当前焦煤市场处于上升趋势，主要受以下因素驱动：
        1. 安全检查限产导致供应收紧
        2. 焦化利润支撑需求
        3. 钢厂补库需求增加
        
        数据显示，焦煤库存处于历史低位，港口库存下降 20%。
        预计短期内价格将继续上涨，目标位 1600 元/吨。
        """
        
        result = parser.parse_report(report_content)
        
        assert 'key_viewpoints' in result
        assert 'data_logic' in result
        assert 'factor_suggestions' in result
        
        # 验证关键观点提取
        assert len(result['key_viewpoints']) > 0
        assert any('安全检查' in vp for vp in result['key_viewpoints'])
        
        # 验证因子建议生成
        assert len(result['factor_suggestions']) > 0
```

---

## 五、时间表

### 第 1 周：动态因子生成模块（基础框架）
- **Day 1-2**：创建因子生成器基础框架（任务 1.1）
- **Day 3-4**：实现 LLM 因子生成接口（任务 1.2）
- **Day 5**：创建因子验证模块（任务 1.3）

### 第 2 周：动态因子生成模块（集成与测试）
- **Day 1-2**：建立因子知识库（任务 1.4）
- **Day 3-4**：与 Scanner 脚本集成（任务 1.5）
- **Day 5**：编写单元测试（任务 1.6）

### 第 3 周：轨迹感知优化器
- **Day 1-2**：设计轨迹分析框架（任务 2.1）
- **Day 3-4**：实现失败学习机制（任务 2.2）
- **Day 5**：创建优化规则生成器（任务 2.3）

### 第 4 周：轨迹感知优化器（集成）+ 研报知识注入（启动）
- **Day 1-2**：与现有 Evolver 集成（任务 2.4）
- **Day 3**：编写轨迹分析器测试（任务 2.5）
- **Day 4-5**：创建研报解析模块（任务 3.1）

### 第 5 周：研报知识注入流水线
- **Day 1-2**：实现因子提取 Agent（任务 3.2）
- **Day 3-4**：建立验证流水线（任务 3.3）
- **Day 5**：与因子知识库集成（任务 3.4）

### 第 6 周：研报知识注入（完成）+ 多角色 Debater（启动）
- **Day 1**：编写研报解析器测试（任务 3.5）
- **Day 2-3**：重构 Debater 为多角色框架（任务 4.1）
- **Day 4-5**：创建分析师角色（任务 4.2）

### 第 7 周：多角色 Debater
- **Day 1-2**：创建风控官角色（任务 4.3）
- **Day 3-4**：实现概念性语言反馈（任务 4.4）
- **Day 5**：实现信念传播机制（任务 4.5）

### 第 8 周：多角色 Debater（完成）+ RL 接口设计（启动）
- **Day 1**：编写多角色 Debater 测试（任务 4.6）
- **Day 2-3**：设计 RL 接口框架（任务 5.1）
- **Day 4-5**：实现状态空间设计（任务 5.2）

### 第 9 周：RL 接口设计
- **Day 1-2**：实现奖励函数设计（任务 5.3）
- **Day 3-4**：实现诊断引导修正（任务 5.4）
- **Day 5**：与现有 Evolver 集成（任务 5.5）

### 第 10 周：集成测试与优化
- **Day 1-2**：编写 RL 接口测试（任务 5.6）
- **Day 3**：端到端集成测试（任务 6.1）
- **Day 4**：性能基准测试（任务 6.2）
- **Day 5**：文档更新（任务 6.3）

---

## 六、进度跟踪

### 2026-06-15
- [x] 创建实施计划文档
- [ ] 开始实施 Phase 1: 动态因子生成模块

### 待更新
- [ ] 完成因子生成器基础框架
- [ ] 完成 LLM 因子生成接口
- [ ] 完成因子验证模块
- [ ] 完成因子知识库
- [ ] 完成与 Scanner 脚本集成
- [ ] 完成单元测试

---

## 七、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 生成因子质量不稳定 | 因子效果差 | 建立严格的验证机制，只保留 IC>0.03 的因子 |
| 多角色协作增加 token 消耗 | 成本增加 | 仅在高价值场景触发多角色辩论 |
| RL 框架复杂度高 | 开发周期长 | 分阶段实施，先实现基础框架 |
| 知识注入可能引入噪声 | 决策质量下降 | 建立知识过滤机制，只注入经过验证的知识 |

---

## 八、验收标准

### 8.1 动态因子生成模块
- [ ] 能够根据市场上下文生成有效的因子代码
- [ ] 因子代码通过验证（IC>0.03，代码可执行）
- [ ] 因子知识库正常工作，支持增删改查
- [ ] 与 Scanner 脚本集成，能够使用生成的因子

### 8.2 轨迹感知优化器
- [ ] 能够分析交易历史，提取成功和失败模式
- [ ] 能够生成优化规则（避免规则和增强规则）
- [ ] 与现有 Evolver 集成，能够应用优化规则

### 8.3 研报知识注入流水线
- [ ] 能够解析研报内容，提取关键观点和数据逻辑
- [ ] 能够生成因子建议
- [ ] 与因子知识库集成，能够保存和检索因子

### 8.4 多角色 Debater 架构
- [ ] 支持分析师、风控官等多角色协作
- [ ] 实现概念性语言反馈机制
- [ ] 决策质量提升（决策修正率降低 15-25%）

### 8.5 LLM 引导的 RL 接口设计
- [ ] 能够自动设计状态空间和奖励函数
- [ ] 实现诊断引导修正机制
- [ ] 策略参数优化效果提升（夏普比率提升 0.2-0.5）

---

## 九、总结

本实施计划基于三篇论文的核心思想，将 Trend-scanner-Agent 从 v3.0 升级到 v4.0。通过分阶段实施，逐步引入动态因子生成、轨迹感知优化、研报知识注入、多角色协作和 RL 接口设计，构建更智能、更自适应的趋势跟踪系统。

**关键成功因素**：
1. 严格的验证机制，确保生成的因子和规则质量
2. 分阶段实施，降低风险
3. 充分的测试覆盖，保证系统稳定性
4. 持续的进度跟踪，及时调整计划

**下一步行动**：
1. 确认实施计划
2. 开始实施 Phase 1: 动态因子生成模块
3. 定期 review 进度，调整计划

---

*本实施计划基于论文分析改进文档，结合项目实际需求制定。*