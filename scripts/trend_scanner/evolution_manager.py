"""
进化管理器 —— 连接推理架构与自进化能力

核心职责：
1. 记录每次分析和交易结果
2. 轨迹分析与故障归因
3. 经验积累与模式检测
4. 策略反思与规则优化
5. 过拟合审计与静默旁路检测

进化流程：
  分析 → 记录 → 归因 → 反思 → 优化 → 验证
"""

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd

from .models import (
    MarketContext, TradingBrief, UserFeedback,
    Experience, Route,
)
from .experience import ExperienceMemory
from .evolution import EnhancedEvolutionEngine
from .trajectory_analysis import (
    TradeTrajectoryAnalyzer, TradeFaultAttributor, StrategyAdapter
)
from .trade_journal import TradeJournal, PatternDetector, RulePromoter
from .skill_reflection import SkillAwareReflector
from .meta_skill_engine import MetaSkillEngine
from .overfitting_audit import OverfittingAuditor
from .silent_bypass_detector import SilentBypassDetector


class EvolutionManager:
    """
    进化管理器 —— 连接推理架构与自进化能力

    在 v3.0 推理优先架构中，进化管理器负责：
    1. 记录每次分析的上下文和建议
    2. 记录用户的实际操作和结果
    3. 分析交易轨迹，归因故障
    4. 积累经验，检测模式
    5. 反思策略，优化规则
    """

    def __init__(self, experience_memory: ExperienceMemory = None,
                 db_path: str = "evolution.db"):
        """
        初始化进化管理器

        参数:
            experience_memory: 经验记忆池（与推理层共享）
            db_path: 进化数据存储路径
        """
        # 经验记忆池（与推理层共享）
        self.experience_memory = experience_memory or ExperienceMemory(db_path=db_path)

        # 进化引擎
        self.evolution_engine = EnhancedEvolutionEngine()

        # 子模块
        self.trajectory_analyzer = TradeTrajectoryAnalyzer()
        self.fault_attributor = TradeFaultAttributor()
        self.strategy_adapter = StrategyAdapter()
        self.trade_journal = TradeJournal()
        self.pattern_detector = PatternDetector()
        self.rule_promoter = RulePromoter()
        self.skill_reflector = SkillAwareReflector()
        self.meta_skill_engine = MetaSkillEngine()
        self.overfitting_auditor = OverfittingAuditor()
        self.silent_bypass_detector = SilentBypassDetector()

        # 进化状态
        self.evolution_history = []
        self.last_evolution_time = None
        self.evolution_count = 0

    def record_analysis(self, context: MarketContext, brief: TradingBrief):
        """
        记录一次分析结果

        参数:
            context: 市场上下文
            brief: 交易决策简报
        """
        record = {
            'timestamp': datetime.now().isoformat(),
            'symbol': context.symbol,
            'trend_phase': context.trend_phase.phase,
            'phase_confidence': context.trend_phase.confidence,
            'routes': [
                {
                    'route_id': r.route_id,
                    'name': r.name,
                    'action': r.action,
                    'confidence': r.confidence,
                }
                for r in brief.routes
            ],
            'recommended_route': brief.recommended_route,
            'warnings': brief.warnings,
        }

        # 存储到交易日志
        self.trade_journal.log_analysis(record)

        return record

    def record_feedback(self, feedback: UserFeedback,
                        context: MarketContext = None,
                        brief: TradingBrief = None):
        """
        记录用户反馈

        参数:
            feedback: 用户反馈
            context: 当时的市场上下文（可选）
            brief: 当时的交易决策简报（可选）
        """
        # 1. 创建经验记录
        experience = Experience(
            experience_id=feedback.feedback_id,
            timestamp=feedback.timestamp,
            symbol=feedback.symbol,
            context_snapshot=context.to_dict() if context else {},
            trend_phase=context.trend_phase.phase if context else 'UNKNOWN',
            phase_confidence=context.trend_phase.confidence if context else 0.5,
            action_taken=feedback.actual_action,
            action_reasoning=f"用户选择方案{feedback.chosen_route}",
            entry_price=feedback.entry_price,
            exit_price=feedback.exit_price,
            pnl_pct=feedback.pnl_pct,
            holding_days=feedback.holding_days,
            max_drawdown_pct=0,  # 需要从交易记录中计算
            max_profit_pct=max(0, feedback.pnl_pct),
            risk_adjusted_return=feedback.pnl_pct,  # 简化计算
            feature_vector=context.feature_vector if context else [],
        )

        # 2. 存入经验记忆池
        self.experience_memory.add_experience(experience)

        # 3. 记录到交易日志
        self.trade_journal.log_trade_outcome(feedback)

        # 4. 触发进化检查
        self._check_evolution_trigger(feedback)

        return experience

    def _check_evolution_trigger(self, feedback: UserFeedback):
        """
        检查是否触发进化

        触发条件：
        1. 连续亏损 >= 3 次
        2. 累计亏损 >= 10%
        3. 距离上次进化 >= 20 笔交易
        """
        # 获取最近的交易记录
        recent_trades = self.trade_journal.get_recent_trades(n=20)

        if len(recent_trades) < 3:
            return

        # 检查连续亏损
        consecutive_losses = 0
        for trade in reversed(recent_trades):
            if trade.get('outcome') == 'LOSS':
                consecutive_losses += 1
            else:
                break

        if consecutive_losses >= 3:
            self.run_evolution(reason=f"连续亏损{consecutive_losses}次")
            return

        # 检查累计亏损
        total_pnl = sum(t.get('pnl_pct', 0) for t in recent_trades[-10:])
        if total_pnl <= -10:
            self.run_evolution(reason=f"近10笔累计亏损{total_pnl:.1f}%")
            return

        # 检查交易数量
        if self.evolution_count == 0 or len(recent_trades) - self.evolution_count >= 20:
            self.run_evolution(reason="定期进化（每20笔交易）")

    def run_evolution(self, reason: str = "手动触发",
                      df: pd.DataFrame = None) -> Dict[str, Any]:
        """
        执行进化流程

        参数:
            reason: 触发原因
            df: K线数据（用于轨迹分析）

        返回:
            进化结果
        """
        start_time = time.time()

        # 获取所有交易记录
        all_trades = self.trade_journal.get_all_trades()
        current_config = self._get_current_config()

        # 执行增强版进化
        evolution_result = self.evolution_engine.run_enhanced_evolution(
            trades=all_trades,
            current_config=current_config,
            df=df,
        )

        # 补充：技能感知反思
        if evolution_result.get('faults'):
            for fault in evolution_result['faults']:
                reflection = self.skill_reflector.reflect_on_failure(
                    fault=fault,
                    current_guidance=current_config.get('guidance', {}),
                )
                evolution_result.setdefault('reflections', []).append(reflection)

        # 补充：过拟合审计
        if len(all_trades) >= 30:
            audit_report = self.overfitting_auditor.audit(
                trades=all_trades,
                config=current_config,
            )
            evolution_result['audit_report'] = audit_report

        # 补充：静默旁路检测
        strategy_usage = self._analyze_strategy_usage(all_trades)
        bypass_report = self.silent_bypass_detector.detect(
            strategy_usage=strategy_usage,
            config=current_config,
        )
        evolution_result['bypass_report'] = bypass_report

        # 更新状态
        self.evolution_count = len(all_trades)
        self.last_evolution_time = datetime.now()
        self.evolution_history.append({
            'timestamp': self.last_evolution_time.isoformat(),
            'reason': reason,
            'trades_count': len(all_trades),
            'result_summary': {
                'proposals_count': len(evolution_result.get('proposals', [])),
                'patterns_count': len(evolution_result.get('patterns', [])),
                'rules_count': len(evolution_result.get('rules', [])),
                'reflections_count': len(evolution_result.get('reflections', [])),
            },
            'duration_ms': int((time.time() - start_time) * 1000),
        })

        # 应用优化建议
        self._apply_evolution_result(evolution_result)

        return evolution_result

    def _get_current_config(self) -> Dict[str, Any]:
        """获取当前策略配置"""
        # 从经验记忆池中提取当前使用的策略参数
        return {
            'enter_threshold': 0.35,
            'exit_threshold': 0.15,
            'atr_stop_multiplier': 2.0,
            'max_position_size': 0.1,
            'guidance': {
                'trend_following': '顺势操作，等待确认信号',
                'risk_management': '严格止损，控制仓位',
            },
        }

    def _analyze_strategy_usage(self, trades: List[Dict]) -> Dict[str, Any]:
        """分析策略使用情况"""
        usage = {
            'total_trades': len(trades),
            'by_action': {},
            'by_phase': {},
            'win_rate_by_action': {},
            'avg_pnl_by_action': {},
        }

        for trade in trades:
            action = trade.get('action', 'UNKNOWN')
            phase = trade.get('trend_phase', 'UNKNOWN')
            outcome = trade.get('outcome', 'UNKNOWN')
            pnl = trade.get('pnl_pct', 0)

            # 按动作统计
            usage['by_action'][action] = usage['by_action'].get(action, 0) + 1
            usage['by_phase'][phase] = usage['by_phase'].get(phase, 0) + 1

            # 计算胜率
            if action not in usage['win_rate_by_action']:
                usage['win_rate_by_action'][action] = {'wins': 0, 'total': 0}
            usage['win_rate_by_action'][action]['total'] += 1
            if outcome == 'WIN':
                usage['win_rate_by_action'][action]['wins'] += 1

            # 计算平均收益
            if action not in usage['avg_pnl_by_action']:
                usage['avg_pnl_by_action'][action] = []
            usage['avg_pnl_by_action'][action].append(pnl)

        # 计算胜率和平均收益
        for action in usage['win_rate_by_action']:
            stats = usage['win_rate_by_action'][action]
            stats['rate'] = stats['wins'] / stats['total'] if stats['total'] > 0 else 0

        for action in usage['avg_pnl_by_action']:
            pnls = usage['avg_pnl_by_action'][action]
            usage['avg_pnl_by_action'][action] = sum(pnls) / len(pnls) if pnls else 0

        return usage

    def _apply_evolution_result(self, result: Dict[str, Any]):
        """应用进化结果"""
        # 1. 应用规则晋升
        if result.get('rules'):
            for rule in result['rules']:
                if rule.get('promoted'):
                    # 将晋升的规则存入经验记忆池
                    self.experience_memory.add_rule(rule)

        # 2. 更新策略权重
        if result.get('proposals'):
            accepted_proposals = [
                p for p in result['proposals']
                if p.get('status') == 'ACCEPTED'
            ]
            if accepted_proposals:
                # 应用接受的策略适配建议
                for proposal in accepted_proposals:
                    self._apply_strategy_adaptation(proposal)

        # 3. 记录反思结果
        if result.get('reflections'):
            for reflection in result['reflections']:
                if reflection.get('revision_action') == 'UPDATE_RULE':
                    # 更新技能指导
                    self._update_guidance(reflection)

    def _apply_strategy_adaptation(self, proposal: Dict[str, Any]):
        """应用策略适配建议"""
        # 记录适配历史
        self.trade_journal.log_adaptation(proposal)

    def _update_guidance(self, reflection: Dict[str, Any]):
        """更新技能指导"""
        # 记录指导更新
        self.trade_journal.log_guidance_update(reflection)

    def get_evolution_status(self) -> Dict[str, Any]:
        """获取进化状态"""
        return {
            'evolution_count': self.evolution_count,
            'last_evolution_time': self.last_evolution_time.isoformat() if self.last_evolution_time else None,
            'total_experiences': self.experience_memory.get_experience_count(),
            'evolution_history': self.evolution_history[-5:],  # 最近5次进化
        }

    def get_experience_stats(self) -> Dict[str, Any]:
        """获取经验统计"""
        return {
            'total_experiences': self.experience_memory.get_experience_count(),
            'phase_distribution': self.experience_memory.get_phase_distribution(),
            'action_distribution': self._get_action_distribution(),
            'win_rate': self._get_overall_win_rate(),
        }

    def _get_action_distribution(self) -> Dict[str, int]:
        """获取动作分布"""
        # 由于 ExperienceMemory 没有 get_all_experiences 方法，
        # 我们返回一个基于 phase_distribution 的近似值
        phase_dist = self.experience_memory.get_phase_distribution()
        # 将阶段分布转换为动作分布的近似
        return {
            'estimated_from_phases': sum(phase_dist.values()),
            'phase_distribution': phase_dist,
        }

    def _get_overall_win_rate(self) -> float:
        """获取总体胜率"""
        # 由于 ExperienceMemory 没有 get_all_experiences 方法，
        # 我们无法直接计算胜率，返回默认值
        return 0.0


class EvolutionManagerFactory:
    """进化管理器工厂"""

    @staticmethod
    def create(experience_memory: ExperienceMemory = None,
               db_path: str = "evolution.db") -> EvolutionManager:
        """创建进化管理器"""
        return EvolutionManager(
            experience_memory=experience_memory,
            db_path=db_path,
        )
