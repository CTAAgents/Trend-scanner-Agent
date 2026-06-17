"""
闭环迭代因子进化引擎

基于 Agentic AI for Factor Investing (2603.14288) 的闭环架构：
    Generate → Execute → Evaluate → Gate → Memory → Feedback → Generate ...

核心设计：
1. 每轮生成多个候选因子（增加搜索多样性）
2. 门控阈值预设不可调（防 p-hacking）
3. 失败经验注入下一轮生成（从失败中学习）
4. 最多 N 轮迭代，避免无限搜索

版本：v1.0
创建日期：2026-06-16
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field, asdict

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class EvolutionRound:
    """单轮进化记录"""
    round_num: int
    candidates: List[Dict]           # 候选因子信息
    evaluations: Dict[str, Dict]     # 评估结果
    decisions: List[Dict]            # 门控决策
    promoted: List[str]              # 本轮晋升的因子
    eliminated: List[str]            # 本轮淘汰的因子
    timestamp: str = ''


@dataclass
class EvolutionResult:
    """进化结果"""
    total_rounds: int
    total_candidates: int
    promoted_factors: List[Dict]
    rounds: List[EvolutionRound]
    duration_seconds: float
    status: str  # 'completed' / 'early_stop' / 'max_rounds'


class FactorEvolutionEngine:
    """
    闭环迭代因子进化引擎

    主循环：
        for round in 1..max_rounds:
            1. 生成候选因子（注入历史反馈）
            2. 执行因子（计算截面值）
            3. 评估因子（IC/ICIR/t-stat）
            4. 门控决策（晋升/观察/淘汰）
            5. 记忆更新（记录轨迹）
            6. 检查终止条件
    """

    def __init__(self, generator=None, executor=None, evaluator=None,
                 gate=None, knowledge_manager=None,
                 seed_pool=None, experience_db=None,
                 report_parser=None, trajectory_analyzer=None,
                 use_walk_forward=False, walk_forward_config=None):
        """
        初始化进化引擎

        Args:
            generator: FactorGenerator（因子生成器，支持 LLM 生成）
            executor: FactorExecutor（因子执行器）
            evaluator: FactorEvaluator（因子评估器）
            gate: FactorGate（门控决策器）
            knowledge_manager: FactorKnowledgeManager（知识管理器）
            seed_pool: SeedFactorPool（种子因子池）
            experience_db: FactorExperienceDB（经验数据库）
            report_parser: ReportParser（研报解析器）
            trajectory_analyzer: TrajectoryAnalyzer（轨迹分析器）
            use_walk_forward: 是否启用 Walk-Forward 验证
            walk_forward_config: Walk-Forward 配置
        """
        # 延迟导入，避免循环依赖
        if generator is None:
            from trend_scanner.factor_generator import FactorGenerator
            generator = FactorGenerator()
        if executor is None:
            from trend_scanner.factor_executor import FactorExecutor
            executor = FactorExecutor()
        if evaluator is None:
            from trend_scanner.factor_evaluator import FactorEvaluator
            evaluator = FactorEvaluator()
        if gate is None:
            from trend_scanner.factor_gate import FactorGate
            gate = FactorGate()
        if seed_pool is None:
            from trend_scanner.seed_factor_pool import SeedFactorPool
            seed_pool = SeedFactorPool()
        if experience_db is None:
            from trend_scanner.factor_experience_db import FactorExperienceDB
            experience_db = FactorExperienceDB()
        if report_parser is None:
            try:
                from trend_scanner.report_parser import ReportParser
                report_parser = ReportParser()
            except Exception:
                report_parser = None
        if trajectory_analyzer is None:
            try:
                from trend_scanner.trajectory_analyzer import TrajectoryAnalyzer
                trajectory_analyzer = TrajectoryAnalyzer()
            except Exception:
                trajectory_analyzer = None

        self.generator = generator
        self.executor = executor
        self.evaluator = evaluator
        self.gate = gate
        self.knowledge_manager = knowledge_manager
        self.seed_pool = seed_pool
        self.experience_db = experience_db
        self.report_parser = report_parser
        self.trajectory_analyzer = trajectory_analyzer

        # Walk-Forward 验证（v6.0 新增）
        self.use_walk_forward = use_walk_forward
        if use_walk_forward:
            from .walk_forward_validator import WalkForwardValidator, WalkForwardConfig
            config = walk_forward_config or WalkForwardConfig()
            self.walk_forward_validator = WalkForwardValidator(config)
            logger.info("Walk-Forward 验证已启用")
        else:
            self.walk_forward_validator = None

        # 进化状态
        self.promoted_factors: List[Dict] = []
        self.rounds: List[EvolutionRound] = []
        self.feedback_history: List[str] = []

    def evolve(self, kline_data: Dict[str, pd.DataFrame] = None,
               max_rounds: int = 10,
               candidates_per_round: int = 5,
               target_promoted: int = 5,
               db_path: str = None,
               days: int = 120) -> EvolutionResult:
        """
        运行闭环进化

        Args:
            kline_data: {symbol: DataFrame}，不提供则从 DuckDB 加载
            max_rounds: 最大迭代轮数
            candidates_per_round: 每轮候选因子数
            target_promoted: 目标晋升因子数（达到后提前终止）
            db_path: DuckDB 路径（不提供 kline_data 时使用）
            days: 数据天数

        Returns:
            EvolutionResult
        """
        import time
        start_time = time.time()

        # 加载数据
        if kline_data is None:
            # 如果提供了 db_path，设置到 evaluator
            if db_path:
                self.evaluator.db_path = db_path
            count = self.evaluator.load_data(days=days)
            logger.info(f"从 DuckDB 加载 {count} 个品种的数据")
            if count < 10:
                return EvolutionResult(
                    total_rounds=0, total_candidates=0,
                    promoted_factors=[], rounds=[],
                    duration_seconds=0,
                    status='insufficient_data'
                )
            kline_data = self.evaluator._kline_data
        else:
            self.evaluator.set_data(kline_data)
            # 使用 evaluator 处理后的数据（日期已归一化）
            kline_data = self.evaluator._kline_data

        # 迭代进化
        for round_num in range(1, max_rounds + 1):
            logger.info(f"=== 进化轮次 {round_num}/{max_rounds} ===")

            round_result = self._evolve_one_round(
                round_num=round_num,
                kline_data=kline_data,
                candidates_per_round=candidates_per_round,
            )

            self.rounds.append(round_result)

            # 检查终止条件
            if len(self.promoted_factors) >= target_promoted:
                logger.info(f"已晋升 {len(self.promoted_factors)} 个因子，提前终止")
                break

        duration = time.time() - start_time

        status = 'completed' if len(self.promoted_factors) >= target_promoted else 'max_rounds'

        return EvolutionResult(
            total_rounds=len(self.rounds),
            total_candidates=sum(len(r.candidates) for r in self.rounds),
            promoted_factors=self.promoted_factors,
            rounds=self.rounds,
            duration_seconds=duration,
            status=status,
        )

    def _evolve_one_round(self, round_num: int,
                           kline_data: Dict[str, pd.DataFrame],
                           candidates_per_round: int) -> EvolutionRound:
        """
        执行一轮进化

        Args:
            round_num: 当前轮次
            kline_data: K 线数据
            candidates_per_round: 候选因子数

        Returns:
            EvolutionRound
        """
        round_result = EvolutionRound(
            round_num=round_num,
            candidates=[],
            evaluations={},
            decisions=[],
            promoted=[],
            eliminated=[],
            timestamp=datetime.now().isoformat(),
        )

        # [1] 生成候选因子
        candidates = self._generate_candidates(candidates_per_round, round_num)
        round_result.candidates = [
            {'name': c.get('name', f'factor_{i}'), 'source': c.get('source', 'unknown')}
            for i, c in enumerate(candidates)
        ]

        # [2] 执行因子 + [3] 评估因子
        evaluations = {}
        for candidate in candidates:
            name = candidate.get('name', f'factor_{round_num}_{len(evaluations)}')
            code = candidate.get('code', '')
            fn = candidate.get('function')

            if fn is not None:
                # 直接使用函数
                eval_result = self.evaluator.evaluate(name, fn)
                evaluations[name] = {
                    'ic_mean': eval_result.ic_mean,
                    'ic_std': eval_result.ic_std,
                    'icir': eval_result.icir,
                    'rank_ic_mean': eval_result.rank_ic_mean,
                    'rank_icir': eval_result.rank_icir,
                    'ic_positive_pct': eval_result.ic_positive_pct,
                    't_stat': eval_result.t_stat,
                    'long_short_sharpe': eval_result.long_short_sharpe,
                    'ic_days': eval_result.ic_days,
                    'cross_section_size_avg': eval_result.cross_section_size_avg,
                }
            elif code:
                # 从代码执行
                factor_values = self.executor.execute(code, kline_data)
                if factor_values is not None:
                    # 用评估器计算 IC
                    returns = self.evaluator._returns
                    ic = self.evaluator.compute_cross_sectional_ic(factor_values)

                    if len(ic) > 0:
                        import numpy as np
                        from scipy import stats as sp_stats

                        ic_mean = float(ic.mean())
                        ic_std = float(ic.std())
                        icir = ic_mean / ic_std if ic_std > 0 else 0
                        n = len(ic)
                        t_stat = ic_mean / (ic_std / np.sqrt(n)) if ic_std > 0 else 0

                        evaluations[name] = {
                            'ic_mean': ic_mean,
                            'ic_std': ic_std,
                            'icir': icir,
                            'rank_ic_mean': ic_mean,
                            'rank_icir': icir,
                            'ic_positive_pct': float((ic > 0).mean()),
                            't_stat': float(t_stat),
                            'long_short_sharpe': 0,  # 简化计算
                            'ic_days': len(ic),
                            'cross_section_size_avg': float(
                                factor_values.notna().sum(axis=1).mean()
                            ),
                        }

        round_result.evaluations = evaluations

        # [3.5] Walk-Forward 验证（可选）
        if self.use_walk_forward and self.walk_forward_validator:
            for name, eval_data in evaluations.items():
                # 找到对应的候选因子
                candidate = next((c for c in candidates if c.get('name') == name), {})
                fn = candidate.get('function')
                
                if fn is not None:
                    # 使用 Walk-Forward 验证
                    try:
                        # 获取价格数据（使用第一个品种的数据）
                        first_symbol = list(kline_data.keys())[0]
                        prices = kline_data[first_symbol]['close']
                        
                        # 执行 Walk-Forward 验证
                        wf_result = self.walk_forward_validator.validate(
                            prices=prices,
                            factor_func=fn,
                            param_space={},
                            optimize_func=lambda p, ps: {}
                        )
                        
                        # 将 Walk-Forward 结果添加到评估数据中
                        eval_data['walk_forward_pass_rate'] = wf_result.pass_rate
                        eval_data['walk_forward_oos_sharpe'] = wf_result.avg_oos_sharpe
                        eval_data['walk_forward_passed'] = wf_result.pass_rate >= 0.5
                        
                        logger.info(f"因子 {name} Walk-Forward 验证: "
                                   f"通过率={wf_result.pass_rate:.2%}, "
                                   f"OOS Sharpe={wf_result.avg_oos_sharpe:.3f}")
                    except Exception as e:
                        logger.warning(f"因子 {name} Walk-Forward 验证失败: {e}")
                        eval_data['walk_forward_passed'] = False

        # [4] 门控决策
        decisions = self.gate.decide_batch(evaluations)
        round_result.decisions = [
            {
                'factor_name': d.factor_name,
                'decision': d.decision,
                'score': d.score,
                'reasons': d.reasons,
            }
            for d in decisions
        ]

        # 分类结果
        for d in decisions:
            if d.decision == 'promote':
                # Walk-Forward 验证检查（如果启用）
                if self.use_walk_forward:
                    eval_data = evaluations.get(d.factor_name, {})
                    if not eval_data.get('walk_forward_passed', True):
                        # Walk-Forward 验证失败，降级为观察
                        logger.info(f"因子 {d.factor_name} Walk-Forward 验证失败，降级为观察")
                        d.decision = 'observe'
                        d.reasons.append('Walk-Forward 验证未通过')
                        continue
                
                round_result.promoted.append(d.factor_name)
                # 保存到晋升列表
                factor_info = next(
                    (c for c in candidates if c.get('name') == d.factor_name), {}
                )
                self.promoted_factors.append({
                    'name': d.factor_name,
                    'score': d.score,
                    'metrics': d.metrics,
                    'reasons': d.reasons,
                    'code': factor_info.get('code', ''),
                    'source': factor_info.get('source', 'unknown'),
                    'promoted_at': datetime.now().isoformat(),
                    'round': round_num,
                })
                # 反馈：成功模式
                self.feedback_history.append(
                    f"第{round_num}轮: {d.factor_name} 晋升, ICIR={d.metrics.get('icir', 0):.2f}"
                )
            elif d.decision == 'eliminate':
                round_result.eliminated.append(d.factor_name)
                # 反馈：失败模式
                self.feedback_history.append(
                    f"第{round_num}轮: {d.factor_name} 淘汰, 原因: {', '.join(d.reasons[:2])}"
                )

        # [5] 保存到知识库
        if self.knowledge_manager:
            for d in decisions:
                if d.decision == 'promote':
                    factor_info = next(
                        (c for c in candidates if c.get('name') == d.factor_name), {}
                    )
                    if factor_info.get('code'):
                        from trend_scanner.factor_generator import FactorResult
                        result = FactorResult(
                            code=factor_info['code'],
                            metadata={'name': d.factor_name, 'description': '进化引擎生成'},
                            validation={'is_valid': True},
                            source='evolution_engine',
                        )
                        self.knowledge_manager.add_factor(result)

        # [6] 记录到经验数据库
        if self.experience_db:
            for d in decisions:
                trajectory = [{
                    'round': round_num,
                    'factor_name': d.factor_name,
                    'logic': '',
                    'params': {},
                    'icir': d.metrics.get('icir', 0),
                    't_stat': d.metrics.get('t_stat', 0),
                    'decision': d.decision,
                    'reasons': d.reasons,
                    'timestamp': datetime.now().isoformat(),
                }]
                self.experience_db.record_trajectory(
                    factor_id=f"{d.factor_name}_r{round_num}",
                    trajectory=trajectory,
                )

        # [7] 更新种子因子池状态
        if self.seed_pool:
            for d in decisions:
                if d.decision == 'promote':
                    self.seed_pool.update_status(d.factor_name, 'validated', d.metrics)
                elif d.decision == 'eliminate':
                    self.seed_pool.update_status(d.factor_name, 'discarded', d.metrics)

        logger.info(
            f"轮次 {round_num}: 候选 {len(candidates)}, "
            f"晋升 {len(round_result.promoted)}, 淘汰 {len(round_result.eliminated)}"
        )

        return round_result

    def _generate_candidates(self, count: int, round_num: int) -> List[Dict]:
        """
        生成候选因子

        候选来源优先级：
        1. 内置因子库（第 1 轮）
        2. 种子因子池（待验证的种子）
        3. LLM 因子生成（FactorGenerator，需要 LLM 客户端）
        4. 因子知识库
        5. 规则变体生成

        Args:
            count: 候选数量
            round_num: 当前轮次

        Returns:
            [{name, code, function, source}]
        """
        candidates = []

        # 方式 1：从内置因子库选取（第 1 轮）
        if round_num == 1:
            from trend_scanner.factor_evaluator import BUILTIN_FACTORS
            for name, fn in list(BUILTIN_FACTORS.items())[:count]:
                candidates.append({
                    'name': name,
                    'function': fn,
                    'source': 'builtin',
                })

        # 方式 2：从种子因子池选取（待验证的种子）
        if self.seed_pool and len(candidates) < count:
            pending = self.seed_pool.get_pending_seeds()
            for seed in pending[:count - len(candidates)]:
                fn = self._compile_seed_code(seed.code)
                if fn:
                    candidates.append({
                        'name': seed.name,
                        'function': fn,
                        'source': f'seed_pool:{seed.source}',
                    })

        # 方式 3：LLM 因子生成（需要 LLM 客户端可用）
        if self.generator and self.generator.llm_client and len(candidates) < count:
            # 构建反馈上下文
            feedback_prompt = ""
            if self.experience_db:
                feedback_prompt = self.experience_db.generate_feedback_prompt()

            market_context = f"进化轮次 {round_num}，已晋升 {len(self.promoted_factors)} 个因子"
            if feedback_prompt:
                market_context += f"\n\n{feedback_prompt}"

            try:
                result = self.generator.generate_factor(market_context)
                if result and result.code and 'def factor' in result.code:
                    fn = self._compile_seed_code(result.code)
                    if fn:
                        name = result.metadata.get('name', f'llm_factor_r{round_num}')
                        candidates.append({
                            'name': name,
                            'function': fn,
                            'code': result.code,
                            'source': 'llm_generated',
                        })
                        logger.info(f"LLM 生成因子: {name}")
            except Exception as e:
                logger.debug(f"LLM 因子生成失败: {e}")

        # 方式 4：从因子知识库选取
        if self.knowledge_manager and len(candidates) < count:
            kb_factors = self.knowledge_manager.get_all_factors()
            for f in kb_factors[:count - len(candidates)]:
                candidates.append({
                    'name': f.get('name', 'kb_factor'),
                    'code': f.get('code', ''),
                    'source': 'knowledge_base',
                })

        # 方式 5：用规则生成变体因子（无 LLM 时）
        if len(candidates) < count:
            variants = self._generate_rule_variants(count - len(candidates), round_num)
            candidates.extend(variants)

        return candidates[:count]

    def _compile_seed_code(self, code: str):
        """编译种子因子代码为函数"""
        try:
            import pandas as pd
            import numpy as np
            exec_globals = {'pd': pd, 'np': np}
            exec(code, exec_globals)
            return exec_globals.get('factor')
        except Exception as e:
            logger.debug(f"编译种子因子代码失败: {e}")
            return None

    def _generate_rule_variants(self, count: int, round_num: int) -> List[Dict]:
        """
        用规则生成因子变体（无 LLM 时的降级方案）

        通过组合不同的窗口期、指标类型生成变体。

        Args:
            count: 需要生成的数量
            round_num: 当前轮次（用于确定性种子）

        Returns:
            [{name, code, source}]
        """
        import random
        random.seed(42 + round_num)  # 确定性种子

        variants = []

        # 动量因子变体
        windows = [5, 10, 15, 20, 30, 40, 60]
        for w in random.sample(windows, min(3, count)):
            code = f'''def factor(df):
    """动量因子 {w} 日"""
    import pandas as pd
    return df['close'].pct_change({w}).fillna(0)
'''
            variants.append({
                'name': f'momentum_{w}d',
                'code': code,
                'source': f'rule_variant_r{round_num}',
            })

        # 波动率因子变体
        vol_windows = [5, 10, 20, 30]
        for w in random.sample(vol_windows, min(2, count - len(variants))):
            code = f'''def factor(df):
    """波动率因子 {w} 日（负号：低波动做多）"""
    import pandas as pd
    return -df['close'].pct_change().rolling({w}).std().fillna(0)
'''
            variants.append({
                'name': f'volatility_{w}d',
                'code': code,
                'source': f'rule_variant_r{round_num}',
            })

        # 量价相关性变体
        if len(variants) < count:
            code = '''def factor(df):
    """量价相关性因子"""
    import pandas as pd
    ret = df['close'].pct_change()
    vol = df['volume'].pct_change()
    return ret.rolling(20).corr(vol).fillna(0)
'''
            variants.append({
                'name': 'volume_price_corr_20d',
                'code': code,
                'source': f'rule_variant_r{round_num}',
            })

        # RSI 变体
        if len(variants) < count:
            for period in [7, 14, 21]:
                code = f'''def factor(df):
    """RSI 因子 {period} 日"""
    import pandas as pd
    import numpy as np
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling({period}).mean()
    loss = (-delta.where(delta < 0, 0)).rolling({period}).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return ((rsi - 50) / 50).fillna(0)
'''
                variants.append({
                    'name': f'rsi_{period}d',
                    'code': code,
                    'source': f'rule_variant_r{round_num}',
                })
                if len(variants) >= count:
                    break

        # 趋势强度变体
        if len(variants) < count:
            code = '''def factor(df):
    """趋势强度因子 EMA20/EMA60"""
    import pandas as pd
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    ema60 = df['close'].ewm(span=60, adjust=False).mean()
    return ((ema20 - ema60) / df['close']).fillna(0)
'''
            variants.append({
                'name': 'trend_strength_ema',
                'code': code,
                'source': f'rule_variant_r{round_num}',
            })

        return variants[:count]

    def load_seeds_from_report(self, report_content: str,
                                report_metadata: Dict = None) -> int:
        """
        从研报内容中提取因子并加载到种子池

        Args:
            report_content: 研报文本内容
            report_metadata: 研报元数据（标题、来源等）

        Returns:
            提取的因子数量
        """
        if not self.report_parser:
            logger.warning("研报解析器未初始化")
            return 0

        if not self.seed_pool:
            logger.warning("种子因子池未初始化")
            return 0

        try:
            # 解析研报
            analysis = self.report_parser.parse_report(report_content, report_metadata)

            count = 0
            for suggestion in analysis.factor_suggestions:
                # 将因子建议转为代码（如果解析器没有直接生成代码，则跳过）
                if hasattr(suggestion, 'code') and suggestion.code:
                    self.seed_pool.add_seed(
                        name=suggestion.name,
                        code=suggestion.code,
                        logic=suggestion.logic,
                        economic_rationale=suggestion.expected_effect,
                        source=f"report:{analysis.title}",
                    )
                    count += 1

            logger.info(f"从研报中提取 {count} 个种子因子")
            return count

        except Exception as e:
            logger.error(f"研报解析失败: {e}")
            return 0

    def load_seeds_from_report_parser_output(self, path: str = None) -> int:
        """
        从 report_parser 的输出文件中加载种子因子

        Args:
            path: report_factors.json 路径

        Returns:
            加载数量
        """
        if not self.seed_pool:
            return 0
        return self.seed_pool.load_from_report_parser(path)

    def analyze_trade_trajectories(self, trade_records: List[Dict]) -> Dict:
        """
        分析交易轨迹，提取失败/成功模式

        Args:
            trade_records: 交易记录列表

        Returns:
            分析结果
        """
        if not self.trajectory_analyzer:
            logger.warning("轨迹分析器未初始化")
            return {}

        try:
            # 转换为 TradeRecord 对象
            from trend_scanner.trajectory_analyzer import TradeRecord
            records = []
            for t in trade_records:
                record = TradeRecord(
                    trade_id=t.get('trade_id', ''),
                    symbol=t.get('symbol', ''),
                    direction=t.get('direction', ''),
                    entry_price=t.get('entry_price', 0),
                    exit_price=t.get('exit_price', 0),
                    entry_time=t.get('entry_time', ''),
                    exit_time=t.get('exit_time', ''),
                    pnl=t.get('pnl', 0),
                    pnl_percent=t.get('pnl_percent', 0),
                    holding_period=t.get('holding_period', 0),
                    market_state=t.get('market_state', ''),
                    trend_phase=t.get('trend_phase', ''),
                    volatility=t.get('volatility', ''),
                    er=t.get('er', 0),
                    tsi=t.get('tsi', 0),
                    rsi=t.get('rsi', 0),
                    adx=t.get('adx', 0),
                    max_drawdown=t.get('max_drawdown', 0),
                    sharpe_ratio=t.get('sharpe_ratio', 0),
                    failure_reason=t.get('failure_reason'),
                )
                records.append(record)

            # 分析轨迹
            analysis = self.trajectory_analyzer.analyze(records)

            # 将分析结果注入经验数据库
            if self.experience_db and analysis:
                patterns = analysis.get('patterns', [])
                for pattern in patterns:
                    self.experience_db.record_trajectory(
                        factor_id=f"trade_pattern_{pattern.get('type', 'unknown')}",
                        trajectory=[{
                            'round': 0,
                            'factor_name': pattern.get('name', ''),
                            'logic': pattern.get('description', ''),
                            'params': {},
                            'icir': 0,
                            't_stat': 0,
                            'decision': 'observe',
                            'reasons': [pattern.get('insight', '')],
                            'timestamp': datetime.now().isoformat(),
                        }],
                    )

            return analysis

        except Exception as e:
            logger.error(f"交易轨迹分析失败: {e}")
            return {}

    def generate_report(self, result: EvolutionResult) -> str:
        """
        生成进化报告

        Args:
            result: EvolutionResult

        Returns:
            格式化的报告文本
        """
        lines = []
        lines.append("=" * 70)
        lines.append("因子进化报告")
        lines.append(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"总轮次: {result.total_rounds}")
        lines.append(f"总候选: {result.total_candidates}")
        lines.append(f"耗时: {result.duration_seconds:.1f} 秒")
        lines.append(f"状态: {result.status}")
        lines.append("=" * 70)

        # 每轮详情
        for r in result.rounds:
            lines.append(f"\n--- 轮次 {r.round_num} ---")
            lines.append(f"  候选: {len(r.candidates)}")
            lines.append(f"  晋升: {len(r.promoted)}")
            lines.append(f"  淘汰: {len(r.eliminated)}")

            for d in r.decisions:
                lines.append(f"    {d['factor_name']}: {d['decision']} (score={d['score']:.2f})")
                if d.get('reasons'):
                    lines.append(f"      原因: {', '.join(d['reasons'][:2])}")

        # 晋升因子汇总
        if result.promoted_factors:
            lines.append(f"\n{'=' * 70}")
            lines.append(f"晋升因子 ({len(result.promoted_factors)} 个)")
            lines.append(f"{'=' * 70}")
            for f in result.promoted_factors:
                lines.append(f"  {f['name']}: score={f['score']:.2f}, source={f['source']}")
                if f.get('metrics'):
                    m = f['metrics']
                    lines.append(f"    ICIR={m.get('icir', 0):.2f}, t={m.get('t_stat', 0):.2f}")

        lines.append(f"\n{'=' * 70}")
        return '\n'.join(lines)

    def save_result(self, result: EvolutionResult, path: str = None):
        """
        保存进化结果到 JSON

        Args:
            result: EvolutionResult
            path: 保存路径
        """
        if path is None:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'data', 'factor_evolution.json'
            )

        data = {
            'evolution_time': datetime.now().isoformat(),
            'total_rounds': result.total_rounds,
            'total_candidates': result.total_candidates,
            'duration_seconds': result.duration_seconds,
            'status': result.status,
            'promoted_factors': result.promoted_factors,
            'rounds': [asdict(r) for r in result.rounds],
            'feedback_history': self.feedback_history,
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"进化结果已保存到 {path}")


# ============================================================
# 命令行入口
# ============================================================

def main():
    """命令行入口"""
    import argparse
    import sys

    # 确保 scripts 目录在路径中
    scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    parser = argparse.ArgumentParser(description='因子进化引擎')
    parser.add_argument('--db', type=str, default=None, help='DuckDB 路径')
    parser.add_argument('--days', type=int, default=120, help='数据天数')
    parser.add_argument('--rounds', type=int, default=5, help='最大轮数')
    parser.add_argument('--candidates', type=int, default=5, help='每轮候选数')
    parser.add_argument('--target', type=int, default=3, help='目标晋升数')
    parser.add_argument('--save', action='store_true', help='保存结果')

    args = parser.parse_args()

    # 初始化引擎
    engine = FactorEvolutionEngine()

    # 运行进化
    print(f"开始因子进化 (轮次={args.rounds}, 候选={args.candidates}, 目标={args.target})")
    result = engine.evolve(
        db_path=args.db,
        days=args.days,
        max_rounds=args.rounds,
        candidates_per_round=args.candidates,
        target_promoted=args.target,
    )

    # 输出报告
    report = engine.generate_report(result)
    print(report)

    # 保存结果
    if args.save:
        engine.save_result(result)
        print("\n结果已保存到 data/factor_evolution.json")


if __name__ == '__main__':
    main()
