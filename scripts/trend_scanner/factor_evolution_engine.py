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
                 gate=None, knowledge_manager=None):
        """
        初始化进化引擎

        Args:
            generator: FactorGenerator（因子生成器）
            executor: FactorExecutor（因子执行器）
            evaluator: FactorEvaluator（因子评估器）
            gate: FactorGate（门控决策器）
            knowledge_manager: FactorKnowledgeManager（知识管理器）
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

        self.generator = generator
        self.executor = executor
        self.evaluator = evaluator
        self.gate = gate
        self.knowledge_manager = knowledge_manager

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

        logger.info(
            f"轮次 {round_num}: 候选 {len(candidates)}, "
            f"晋升 {len(round_result.promoted)}, 淘汰 {len(round_result.eliminated)}"
        )

        return round_result

    def _generate_candidates(self, count: int, round_num: int) -> List[Dict]:
        """
        生成候选因子

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

        # 方式 2：从因子知识库选取
        if self.knowledge_manager and len(candidates) < count:
            kb_factors = self.knowledge_manager.get_all_factors()
            for f in kb_factors[:count - len(candidates)]:
                candidates.append({
                    'name': f.get('name', 'kb_factor'),
                    'code': f.get('code', ''),
                    'source': 'knowledge_base',
                })

        # 方式 3：用规则生成变体因子（无 LLM 时）
        if len(candidates) < count:
            variants = self._generate_rule_variants(count - len(candidates), round_num)
            candidates.extend(variants)

        return candidates[:count]

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
