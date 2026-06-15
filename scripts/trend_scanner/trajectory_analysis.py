"""
交易轨迹分析模块

基于 skill-adaptor 的轨迹分析和故障归因概念，为趋势跟踪系统提供：
- TradeTrajectory: 交易轨迹数据结构
- TradeTrajectoryAnalyzer: 交易轨迹分析器
- TradeFaultAttributor: 交易故障归因器
- StrategyAdapter: 策略适配器（生成针对性更新 + 接受检查）

核心理念：
1. 步级别归因：精确定位到"在持仓的哪个阶段，哪个指标发出了错误信号"
2. 责任分数：量化每个策略对亏损的贡献度
3. 接受检查：更新前必须通过验证（奖励提升 + 无回归 + 人工确认）
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict
import json
import numpy as np
import pandas as pd


# ===========================================================================
# 数据结构定义
# ===========================================================================

class FaultType(Enum):
    """故障类型"""
    ENTRY_ERROR = "entry_error"                    # 入场错误：在错误的市场状态下入场
    INDICATOR_MISUSE = "indicator_misuse"          # 指标误用：指标给出错误信号
    TIMING_ERROR = "timing_error"                  # 时机错误：入场/出场时机不当
    RISK_MISMANAGEMENT = "risk_mismanagement"      # 风控失误：止损/仓位不当
    PHASE_MISMATCH = "phase_mismatch"              # 阶段错配：趋势阶段判断错误
    STRATEGY_CONFLICT = "strategy_conflict"        # 策略冲突：多个策略信号矛盾
    UNKNOWN = "unknown"


class AdaptationStatus(Enum):
    """适应状态"""
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass
class TrajectoryStep:
    """交易轨迹中的单个步骤"""
    step_id: int
    phase: str                    # "entry" / "holding" / "exit"
    timestamp: datetime = field(default_factory=datetime.now)
    price: float = 0.0
    indicators: Dict[str, float] = field(default_factory=dict)
    market_state: str = "UNKNOWN"
    trend_phase: str = "UNKNOWN"
    signal: str = "HOLD"
    strategy_votes: Dict[str, str] = field(default_factory=dict)
    reward: float = 0.0           # 该步骤的收益贡献
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeTrajectory:
    """完整交易轨迹"""
    trade_id: str
    symbol: str
    steps: List[TrajectoryStep] = field(default_factory=list)
    entry_step: Optional[TrajectoryStep] = None
    exit_step: Optional[TrajectoryStep] = None
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    success: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponsibilityScore:
    """策略责任分数"""
    strategy_name: str
    score: float                  # 0-1，责任程度
    fault_type: FaultType = FaultType.UNKNOWN
    reasoning: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Fault:
    """故障信息"""
    fault_id: str
    step_id: int
    fault_type: FaultType
    description: str
    responsible_strategies: List[ResponsibilityScore] = field(default_factory=list)
    is_actionable: bool = True
    severity: float = 0.0         # 0-1，故障严重程度


@dataclass
class AcceptanceCheck:
    """接受检查"""
    check_id: str
    description: str
    status: str = "pending"       # "pending" / "passed" / "failed"
    result: Optional[Dict[str, Any]] = None


@dataclass
class AdaptationProposal:
    """适应性更新提案"""
    proposal_id: str
    fault_id: str
    strategy_name: str
    adaptation_type: str          # "parameter" / "weight" / "rule"
    old_config: Dict[str, Any] = field(default_factory=dict)
    new_config: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    acceptance_checks: List[AcceptanceCheck] = field(default_factory=list)
    status: AdaptationStatus = AdaptationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)


# ===========================================================================
# 交易轨迹分析器
# ===========================================================================

class TradeTrajectoryAnalyzer:
    """
    交易轨迹分析器

    基于 skill-adaptor 的 TrajectoryAnalyzer 概念：
    - 分析交易的入场→持仓→出场决策序列
    - 提取每一步的指标状态和信号
    - 计算轨迹质量评分
    """

    def __init__(self):
        self.trajectories: List[TradeTrajectory] = []

    def build_trajectory(self, trade, df: pd.DataFrame = None) -> TradeTrajectory:
        """
        从 TradeRecord 构建交易轨迹

        参数:
            trade: TradeRecord 对象
            df: 可选的完整K线数据（用于分析持仓期间的指标变化）

        返回:
            TradeTrajectory 对象
        """
        steps = []

        # Step 0: 入场步骤
        entry_step = TrajectoryStep(
            step_id=0,
            phase="entry",
            timestamp=trade.entry_time,
            price=trade.entry_price,
            indicators={
                'adx': trade.adx_at_entry,
                'atr': trade.atr_at_entry,
            },
            market_state=trade.market_state_at_entry,
            trend_phase=trade.trend_phase_at_entry,
            signal=trade.entry_signal,
            strategy_votes=trade.strategy_votes_at_entry.copy(),
            metadata={
                'reliability_score': trade.reliability_score_at_entry,
                'phase_confidence': trade.phase_confidence_at_entry,
            }
        )
        steps.append(entry_step)

        # Step 1-N: 持仓期间步骤（如果有K线数据）
        if df is not None and len(df) > 0:
            holding_steps = self._analyze_holding_period(trade, df)
            steps.extend(holding_steps)

        # Step N+1: 出场步骤
        exit_step = TrajectoryStep(
            step_id=len(steps),
            phase="exit",
            timestamp=trade.exit_time or trade.entry_time,
            price=trade.exit_price,
            indicators={},
            signal=trade.exit_reason,
            reward=trade.pnl_pct,
            metadata={
                'exit_reason': trade.exit_reason,
                'holding_bars': trade.holding_bars,
                'max_favorable_excursion': trade.max_favorable_excursion,
                'max_adverse_excursion': trade.max_adverse_excursion,
            }
        )
        steps.append(exit_step)

        trajectory = TradeTrajectory(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            steps=steps,
            entry_step=entry_step,
            exit_step=exit_step,
            total_pnl=trade.pnl,
            total_pnl_pct=trade.pnl_pct,
            success=trade.pnl > 0,
            metadata={
                'direction': trade.direction,
                'quality_tags': trade.quality_tags,
            }
        )

        self.trajectories.append(trajectory)
        return trajectory

    def _analyze_holding_period(self, trade, df: pd.DataFrame) -> List[TrajectoryStep]:
        """分析持仓期间的指标变化"""
        steps = []

        if trade.entry_time is None or trade.exit_time is None:
            return steps

        # 找到入场和出场对应的K线索引
        try:
            if 'date' in df.columns:
                dates = pd.to_datetime(df['date'])
                entry_idx = (dates - trade.entry_time).abs().idxmin()
                exit_idx = (dates - trade.exit_time).abs().idxmin()
            else:
                return steps

            # 采样持仓期间的关键点（最多10个采样点）
            total_bars = exit_idx - entry_idx
            if total_bars <= 2:
                return steps

            sample_indices = np.linspace(
                entry_idx + 1,
                exit_idx - 1,
                min(10, total_bars - 2),
                dtype=int
            )

            for i, idx in enumerate(sample_indices):
                if idx >= len(df):
                    break
                row = df.iloc[idx]

                # 计算当前浮盈/浮亏
                current_price = row.get('close', 0)
                if trade.direction == "LONG":
                    unrealized_pnl_pct = (current_price - trade.entry_price) / trade.entry_price
                else:
                    unrealized_pnl_pct = (trade.entry_price - current_price) / trade.entry_price

                step = TrajectoryStep(
                    step_id=i + 1,
                    phase="holding",
                    price=current_price,
                    indicators={
                        'adx': row.get('adx', 0),
                        'rsi': row.get('rsi', 0),
                        'macd_hist': row.get('macd_hist', 0),
                        'ema20': row.get('ema20', 0),
                        'ema60': row.get('ema60', 0),
                    },
                    market_state=row.get('market_state', 'UNKNOWN'),
                    reward=unrealized_pnl_pct,
                    metadata={
                        'bar_index': idx,
                        'unrealized_pnl_pct': unrealized_pnl_pct,
                    }
                )
                steps.append(step)

        except Exception:
            pass

        return steps

    def compute_trajectory_metrics(self, trajectory: TradeTrajectory) -> Dict[str, Any]:
        """计算轨迹级指标"""
        if not trajectory.steps:
            return {}

        total_steps = len(trajectory.steps)
        holding_steps = [s for s in trajectory.steps if s.phase == "holding"]

        # 计算持仓期间的指标变化
        adx_values = [s.indicators.get('adx', 0) for s in holding_steps if s.indicators.get('adx', 0) > 0]
        rsi_values = [s.indicators.get('rsi', 0) for s in holding_steps if s.indicators.get('rsi', 0) > 0]

        # 轨迹质量评分
        quality_score = self._compute_quality_score(trajectory)

        return {
            'total_steps': total_steps,
            'holding_steps': len(holding_steps),
            'success': trajectory.success,
            'total_pnl_pct': trajectory.total_pnl_pct,
            'quality_score': quality_score,
            'adx_trend': self._compute_trend(adx_values),
            'rsi_range': (min(rsi_values), max(rsi_values)) if rsi_values else (0, 0),
            'strategy_consistency': self._compute_strategy_consistency(trajectory),
        }

    def _compute_quality_score(self, trajectory: TradeTrajectory) -> float:
        """计算轨迹质量评分 (0-100)"""
        score = 50.0  # 基础分

        if trajectory.success:
            score += 20  # 盈利加分

        # 持仓期间指标一致性
        holding_steps = [s for s in trajectory.steps if s.phase == "holding"]
        if holding_steps:
            # 指标方向一致性
            adx_values = [s.indicators.get('adx', 0) for s in holding_steps]
            if adx_values and all(v > 20 for v in adx_values):
                score += 10  # ADX持续有趋势

            # 价格方向一致性
            direction = trajectory.metadata.get('direction', 'LONG')
            prices = [s.price for s in holding_steps]
            if direction == "LONG" and all(prices[i] >= prices[i-1] * 0.99 for i in range(1, len(prices))):
                score += 10  # 多头持仓期间价格未大幅下跌
            elif direction == "SHORT" and all(prices[i] <= prices[i-1] * 1.01 for i in range(1, len(prices))):
                score += 10  # 空头持仓期间价格未大幅上涨

        # 风险控制评分
        mfe = trajectory.exit_step.metadata.get('max_favorable_excursion', 0) if trajectory.exit_step else 0
        mae = trajectory.exit_step.metadata.get('max_adverse_excursion', 0) if trajectory.exit_step else 0
        if mfe > 0 and mae > 0:
            risk_reward_ratio = mfe / mae
            if risk_reward_ratio > 2:
                score += 10
            elif risk_reward_ratio > 1:
                score += 5

        return min(100, max(0, score))

    def _compute_trend(self, values: List[float]) -> str:
        """计算数值序列的趋势"""
        if len(values) < 2:
            return "stable"
        diff = values[-1] - values[0]
        if diff > 5:
            return "increasing"
        elif diff < -5:
            return "decreasing"
        return "stable"

    def _compute_strategy_consistency(self, trajectory: TradeTrajectory) -> float:
        """计算策略信号一致性"""
        entry_step = trajectory.entry_step
        if not entry_step or not entry_step.strategy_votes:
            return 0.0

        votes = entry_step.strategy_votes
        bullish = sum(1 for v in votes.values() if "多" in v)
        bearish = sum(1 for v in votes.values() if "空" in v)
        total = len(votes)

        if total == 0:
            return 0.0

        return max(bullish, bearish) / total

    def analyze(self, trajectory: TradeTrajectory) -> Dict[str, Any]:
        """完整的轨迹分析"""
        metrics = self.compute_trajectory_metrics(trajectory)

        return {
            'trajectory_id': trajectory.trade_id,
            'symbol': trajectory.symbol,
            'success': trajectory.success,
            'metrics': metrics,
            'trajectory': trajectory,
        }


# ===========================================================================
# 交易故障归因器
# ===========================================================================

class TradeFaultAttributor:
    """
    交易故障归因器

    基于 skill-adaptor 的 FaultAttributor 概念：
    - 识别故障步骤（入场错误、持仓期间指标变化、出场错误）
    - 将责任归因到具体策略
    - 计算责任分数
    """

    def __init__(self, responsibility_threshold: float = 0.3):
        self.responsibility_threshold = responsibility_threshold
        self.faults: List[Fault] = []

    def attribute(self, trajectory: TradeTrajectory) -> Dict[str, Any]:
        """
        完整的故障归因流程

        返回:
            {
                'has_fault': bool,
                'faults': List[Fault],
                'first_actionable_fault': Optional[Fault],
                'strategy_responsibility': Dict[str, float],
                'trajectory_id': str,
            }
        """
        if trajectory.success:
            return {
                'has_fault': False,
                'faults': [],
                'first_actionable_fault': None,
                'strategy_responsibility': {},
                'trajectory_id': trajectory.trade_id,
            }

        # 识别故障步骤
        faults = self._identify_faults(trajectory)

        # 找到第一个可操作的故障
        first_actionable = None
        for fault in faults:
            if fault.is_actionable:
                first_actionable = fault
                break

        # 计算策略责任分数
        strategy_responsibility = self._calculate_strategy_responsibility(faults)

        self.faults.extend(faults)

        return {
            'has_fault': len(faults) > 0,
            'faults': faults,
            'first_actionable_fault': first_actionable,
            'strategy_responsibility': strategy_responsibility,
            'trajectory_id': trajectory.trade_id,
        }

    def _identify_faults(self, trajectory: TradeTrajectory) -> List[Fault]:
        """识别故障"""
        faults = []

        # 1. 入场故障检测
        entry_faults = self._check_entry_faults(trajectory)
        faults.extend(entry_faults)

        # 2. 持仓期间故障检测
        holding_faults = self._check_holding_faults(trajectory)
        faults.extend(holding_faults)

        # 3. 出场故障检测
        exit_faults = self._check_exit_faults(trajectory)
        faults.extend(exit_faults)

        return faults

    def _check_entry_faults(self, trajectory: TradeTrajectory) -> List[Fault]:
        """检查入场故障"""
        faults = []
        entry = trajectory.entry_step
        if not entry:
            return faults

        # 检查1: 在错误的市场状态下入场
        if entry.market_state == "RANGE_BOUND":
            faults.append(Fault(
                fault_id=f"{trajectory.trade_id}_entry_range",
                step_id=0,
                fault_type=FaultType.PHASE_MISMATCH,
                description=f"在震荡市(RANGE_BOUND)中入场，市场状态判断错误",
                is_actionable=True,
                severity=0.8,
                responsible_strategies=self._find_responsible_strategies(
                    entry.strategy_votes, "RANGE_BOUND", trajectory
                )
            ))

        # 检查2: 趋势阶段不支持入场
        if entry.trend_phase in ("FATIGUING", "REVERSING", "CONSOLIDATING"):
            faults.append(Fault(
                fault_id=f"{trajectory.trade_id}_entry_phase",
                step_id=0,
                fault_type=FaultType.PHASE_MISMATCH,
                description=f"在趋势阶段{entry.trend_phase}中入场，阶段判断错误",
                is_actionable=True,
                severity=0.7,
                responsible_strategies=self._find_responsible_strategies(
                    entry.strategy_votes, entry.trend_phase, trajectory
                )
            ))

        # 检查3: 策略信号冲突
        votes = entry.strategy_votes
        if votes:
            bullish = sum(1 for v in votes.values() if "多" in v)
            bearish = sum(1 for v in votes.values() if "空" in v)
            if bullish > 0 and bearish > 0 and abs(bullish - bearish) <= 1:
                faults.append(Fault(
                    fault_id=f"{trajectory.trade_id}_entry_conflict",
                    step_id=0,
                    fault_type=FaultType.STRATEGY_CONFLICT,
                    description=f"策略信号冲突: {bullish}看多 vs {bearish}看空",
                    is_actionable=True,
                    severity=0.6,
                    responsible_strategies=self._find_conflicting_strategies(
                        votes, trajectory
                    )
                ))

        # 检查4: ADX不足但入场
        adx = entry.indicators.get('adx', 0)
        if adx < 20 and entry.signal in ("BUY", "SELL"):
            faults.append(Fault(
                fault_id=f"{trajectory.trade_id}_entry_adx",
                step_id=0,
                fault_type=FaultType.INDICATOR_MISUSE,
                description=f"ADX={adx:.1f}<20时入场，趋势强度不足",
                is_actionable=True,
                severity=0.5,
                responsible_strategies=[ResponsibilityScore(
                    strategy_name="ADX_PCT",
                    score=0.8,
                    fault_type=FaultType.INDICATOR_MISUSE,
                    reasoning="ADX指标未能有效过滤弱趋势"
                )]
            ))

        return faults

    def _check_holding_faults(self, trajectory: TradeTrajectory) -> List[Fault]:
        """检查持仓期间故障"""
        faults = []
        holding_steps = [s for s in trajectory.steps if s.phase == "holding"]

        if len(holding_steps) < 2:
            return faults

        # 检查1: 持仓期间指标反转
        direction = trajectory.metadata.get('direction', 'LONG')
        adx_values = [s.indicators.get('adx', 0) for s in holding_steps]
        rsi_values = [s.indicators.get('rsi', 0) for s in holding_steps]

        # ADX持续下降
        if len(adx_values) >= 3:
            adx_trend = adx_values[-1] - adx_values[0]
            if adx_trend < -10 and adx_values[0] > 25:
                faults.append(Fault(
                    fault_id=f"{trajectory.trade_id}_holding_adx_decline",
                    step_id=holding_steps[0].step_id,
                    fault_type=FaultType.INDICATOR_MISUSE,
                    description=f"持仓期间ADX从{adx_values[0]:.1f}下降到{adx_values[-1]:.1f}，趋势衰减",
                    is_actionable=True,
                    severity=0.6,
                    responsible_strategies=[ResponsibilityScore(
                        strategy_name="ADX_PCT",
                        score=0.7,
                        fault_type=FaultType.INDICATOR_MISUSE,
                        reasoning="ADX未能及时提示趋势衰减"
                    )]
                ))

        # RSI超买/超卖未离场
        if rsi_values:
            if direction == "LONG" and any(r > 80 for r in rsi_values):
                faults.append(Fault(
                    fault_id=f"{trajectory.trade_id}_holding_rsi_overbought",
                    step_id=holding_steps[0].step_id,
                    fault_type=FaultType.TIMING_ERROR,
                    description=f"持仓期间RSI超买({max(rsi_values):.1f})但未及时离场",
                    is_actionable=True,
                    severity=0.4,
                    responsible_strategies=[ResponsibilityScore(
                        strategy_name="MOMENTUM",
                        score=0.5,
                        fault_type=FaultType.TIMING_ERROR,
                        reasoning="动量指标未能触发及时离场"
                    )]
                ))
            elif direction == "SHORT" and any(r < 20 for r in rsi_values):
                faults.append(Fault(
                    fault_id=f"{trajectory.trade_id}_holding_rsi_oversold",
                    step_id=holding_steps[0].step_id,
                    fault_type=FaultType.TIMING_ERROR,
                    description=f"持仓期间RSI超卖({min(rsi_values):.1f})但未及时离场",
                    is_actionable=True,
                    severity=0.4,
                    responsible_strategies=[ResponsibilityScore(
                        strategy_name="MOMENTUM",
                        score=0.5,
                        fault_type=FaultType.TIMING_ERROR,
                        reasoning="动量指标未能触发及时离场"
                    )]
                ))

        return faults

    def _check_exit_faults(self, trajectory: TradeTrajectory) -> List[Fault]:
        """检查出场故障"""
        faults = []
        exit_step = trajectory.exit_step
        if not exit_step:
            return faults

        # 检查1: 止损出场但MFE很大（过早离场）
        mfe = exit_step.metadata.get('max_favorable_excursion', 0)
        mae = exit_step.metadata.get('max_adverse_excursion', 0)
        exit_reason = exit_step.metadata.get('exit_reason', '')

        if exit_reason == "STOP_LOSS" and mfe > 0 and mae > 0:
            if mfe >= 2 * mae:  # MFE >= 2倍初始风险
                faults.append(Fault(
                    fault_id=f"{trajectory.trade_id}_exit_early",
                    step_id=exit_step.step_id,
                    fault_type=FaultType.TIMING_ERROR,
                    description=f"过早离场: MFE={mfe:.0f} >= 2*MAE={2*mae:.0f}，方向正确但止损被震出",
                    is_actionable=True,
                    severity=0.7,
                    responsible_strategies=[ResponsibilityScore(
                        strategy_name="RISK_CONTROL",
                        score=0.8,
                        fault_type=FaultType.RISK_MISMANAGEMENT,
                        reasoning="止损设置过紧，导致方向正确的交易被震出"
                    )]
                ))

        # 检查2: 止损距离不合理
        entry = trajectory.entry_step
        if entry and exit_reason == "STOP_LOSS":
            stop_distance = abs(entry.price - exit_step.price)
            atr = entry.indicators.get('atr', 0)
            if atr > 0 and stop_distance < 1.0 * atr:
                faults.append(Fault(
                    fault_id=f"{trajectory.trade_id}_exit_tight_stop",
                    step_id=exit_step.step_id,
                    fault_type=FaultType.RISK_MISMANAGEMENT,
                    description=f"止损距离({stop_distance:.1f}) < 1倍ATR({atr:.1f})，止损过紧",
                    is_actionable=True,
                    severity=0.6,
                    responsible_strategies=[ResponsibilityScore(
                        strategy_name="RISK_CONTROL",
                        score=0.7,
                        fault_type=FaultType.RISK_MISMANAGEMENT,
                        reasoning="止损设置不合理"
                    )]
                ))

        return faults

    def _find_responsible_strategies(self, votes: Dict[str, str],
                                     market_state: str,
                                     trajectory: TradeTrajectory) -> List[ResponsibilityScore]:
        """找到有责任的策略"""
        scores = []

        direction = trajectory.metadata.get('direction', 'LONG')
        for strategy, vote in votes.items():
            if market_state == "RANGE_BOUND":
                # 在震荡市中，看多或看空的策略都有责任
                if ("多" in vote and direction == "LONG") or ("空" in vote and direction == "SHORT"):
                    scores.append(ResponsibilityScore(
                        strategy_name=strategy,
                        score=0.6,
                        fault_type=FaultType.PHASE_MISMATCH,
                        reasoning=f"在震荡市中给出{vote}信号"
                    ))
            elif market_state in ("STRONG_UPTREND", "WEAK_UPTREND"):
                if "空" in vote and direction == "SHORT":
                    scores.append(ResponsibilityScore(
                        strategy_name=strategy,
                        score=0.7,
                        fault_type=FaultType.PHASE_MISMATCH,
                        reasoning=f"在上升趋势中给出看空信号"
                    ))
            elif market_state in ("STRONG_DOWNTREND", "WEAK_DOWNTREND"):
                if "多" in vote and direction == "LONG":
                    scores.append(ResponsibilityScore(
                        strategy_name=strategy,
                        score=0.7,
                        fault_type=FaultType.PHASE_MISMATCH,
                        reasoning=f"在下降趋势中给出看多信号"
                    ))

        return scores

    def _find_conflicting_strategies(self, votes: Dict[str, str],
                                      trajectory: TradeTrajectory) -> List[ResponsibilityScore]:
        """找到冲突的策略"""
        scores = []
        direction = trajectory.metadata.get('direction', 'LONG')

        for strategy, vote in votes.items():
            if direction == "LONG" and "空" in vote:
                scores.append(ResponsibilityScore(
                    strategy_name=strategy,
                    score=0.5,
                    fault_type=FaultType.STRATEGY_CONFLICT,
                    reasoning=f"在多头持仓中给出看空信号"
                ))
            elif direction == "SHORT" and "多" in vote:
                scores.append(ResponsibilityScore(
                    strategy_name=strategy,
                    score=0.5,
                    fault_type=FaultType.STRATEGY_CONFLICT,
                    reasoning=f"在空头持仓中给出看多信号"
                ))

        return scores

    def _calculate_strategy_responsibility(self, faults: List[Fault]) -> Dict[str, float]:
        """计算各策略的总责任分数"""
        responsibility = defaultdict(float)

        for fault in faults:
            for resp in fault.responsible_strategies:
                responsibility[resp.strategy_name] += resp.score * fault.severity

        # 归一化到 0-1
        total = sum(responsibility.values())
        if total > 0:
            return {k: v / total for k, v in responsibility.items()}

        return dict(responsibility)


# ===========================================================================
# 策略适配器
# ===========================================================================

class StrategyAdapter:
    """
    策略适配器

    基于 skill-adaptor 的 SkillAdapter 概念：
    - 生成有针对性的参数/权重调整建议
    - 通过接受检查验证变更
    - 支持回滚机制
    """

    def __init__(self):
        self.proposals: List[AdaptationProposal] = []

    def generate_proposals(self, fault_attribution: Dict[str, Any],
                          current_config: Dict[str, Any]) -> List[AdaptationProposal]:
        """
        根据故障归因生成适应性更新提案

        参数:
            fault_attribution: TradeFaultAttributor.attribute() 的返回结果
            current_config: 当前策略配置

        返回:
            AdaptationProposal 列表
        """
        proposals = []

        if not fault_attribution.get('has_fault'):
            return proposals

        faults = fault_attribution.get('faults', [])
        strategy_resp = fault_attribution.get('strategy_responsibility', {})

        for fault in faults:
            for resp in fault.responsible_strategies:
                if resp.score >= 0.3:  # 责任分数阈值
                    proposal = self._generate_single_proposal(
                        fault, resp, current_config
                    )
                    if proposal:
                        proposals.append(proposal)

        self.proposals.extend(proposals)
        return proposals

    def _generate_single_proposal(self, fault: Fault, resp: ResponsibilityScore,
                                  current_config: Dict[str, Any]) -> Optional[AdaptationProposal]:
        """生成单个适应性更新提案"""
        strategy = resp.strategy_name

        # 根据故障类型生成不同的调整建议
        if fault.fault_type == FaultType.PHASE_MISMATCH:
            return self._generate_phase_mismatch_proposal(fault, resp, current_config)
        elif fault.fault_type == FaultType.INDICATOR_MISUSE:
            return self._generate_indicator_proposal(fault, resp, current_config)
        elif fault.fault_type == FaultType.TIMING_ERROR:
            return self._generate_timing_proposal(fault, resp, current_config)
        elif fault.fault_type == FaultType.RISK_MISMANAGEMENT:
            return self._generate_risk_proposal(fault, resp, current_config)
        elif fault.fault_type == FaultType.STRATEGY_CONFLICT:
            return self._generate_conflict_proposal(fault, resp, current_config)

        return None

    def _generate_phase_mismatch_proposal(self, fault: Fault, resp: ResponsibilityScore,
                                          current_config: Dict[str, Any]) -> Optional[AdaptationProposal]:
        """生成阶段错配的调整提案"""
        # 降低该策略在震荡市中的权重
        current_weight = current_config.get('strategy_weights', {}).get(resp.strategy_name, 0.1)
        new_weight = max(0.05, current_weight * 0.7)  # 降低30%

        return AdaptationProposal(
            proposal_id=f"prop_{fault.fault_id}_{resp.strategy_name}",
            fault_id=fault.fault_id,
            strategy_name=resp.strategy_name,
            adaptation_type="weight",
            old_config={'weight': current_weight},
            new_config={'weight': new_weight},
            reasoning=f"阶段错配故障: {fault.description}，降低策略权重",
            acceptance_checks=[
                AcceptanceCheck(
                    check_id="backtest_validation",
                    description="回测验证新权重在类似市场状态下表现更好"
                ),
                AcceptanceCheck(
                    check_id="no_regression",
                    description="验证在其他市场状态下无显著回归"
                ),
            ]
        )

    def _generate_indicator_proposal(self, fault: Fault, resp: ResponsibilityScore,
                                     current_config: Dict[str, Any]) -> Optional[AdaptationProposal]:
        """生成指标误用的调整提案"""
        if resp.strategy_name == "ADX_PCT":
            # 调整 ADX 阈值
            current_threshold = current_config.get('signal_params', {}).get('adx_threshold', 20)
            new_threshold = current_threshold + 5  # 提高阈值，更严格过滤

            return AdaptationProposal(
                proposal_id=f"prop_{fault.fault_id}_{resp.strategy_name}",
                fault_id=fault.fault_id,
                strategy_name=resp.strategy_name,
                adaptation_type="parameter",
                old_config={'adx_threshold': current_threshold},
                new_config={'adx_threshold': new_threshold},
                reasoning=f"指标误用故障: {fault.description}，提高ADX阈值",
                acceptance_checks=[
                    AcceptanceCheck(
                        check_id="backtest_validation",
                        description="回测验证新阈值在弱趋势中减少假信号"
                    ),
                ]
            )

        return None

    def _generate_timing_proposal(self, fault: Fault, resp: ResponsibilityScore,
                                  current_config: Dict[str, Any]) -> Optional[AdaptationProposal]:
        """生成时机错误的调整提案"""
        if "止损" in fault.description or "过早离场" in fault.description:
            # 放宽止损
            current_atr_mult = current_config.get('risk_params', {}).get('atr_multiplier', 2.0)
            new_atr_mult = min(3.0, current_atr_mult + 0.5)

            return AdaptationProposal(
                proposal_id=f"prop_{fault.fault_id}_{resp.strategy_name}",
                fault_id=fault.fault_id,
                strategy_name=resp.strategy_name,
                adaptation_type="parameter",
                old_config={'atr_multiplier': current_atr_mult},
                new_config={'atr_multiplier': new_atr_mult},
                reasoning=f"时机错误故障: {fault.description}，放宽止损距离",
                acceptance_checks=[
                    AcceptanceCheck(
                        check_id="backtest_validation",
                        description="回测验证新止损参数在趋势行情中减少被震出"
                    ),
                ]
            )

        return None

    def _generate_risk_proposal(self, fault: Fault, resp: ResponsibilityScore,
                                current_config: Dict[str, Any]) -> Optional[AdaptationProposal]:
        """生成风控失误的调整提案"""
        if "止损过紧" in fault.description:
            current_atr_mult = current_config.get('risk_params', {}).get('atr_multiplier', 2.0)
            new_atr_mult = min(3.0, current_atr_mult + 0.5)

            return AdaptationProposal(
                proposal_id=f"prop_{fault.fault_id}_{resp.strategy_name}",
                fault_id=fault.fault_id,
                strategy_name=resp.strategy_name,
                adaptation_type="parameter",
                old_config={'atr_multiplier': current_atr_mult},
                new_config={'atr_multiplier': new_atr_mult},
                reasoning=f"风控失误故障: {fault.description}，放宽止损距离",
                acceptance_checks=[
                    AcceptanceCheck(
                        check_id="backtest_validation",
                        description="回测验证新止损参数"
                    ),
                ]
            )

        return None

    def _generate_conflict_proposal(self, fault: Fault, resp: ResponsibilityScore,
                                    current_config: Dict[str, Any]) -> Optional[AdaptationProposal]:
        """生成策略冲突的调整提案"""
        # 降低冲突策略的权重
        current_weight = current_config.get('strategy_weights', {}).get(resp.strategy_name, 0.1)
        new_weight = max(0.05, current_weight * 0.8)

        return AdaptationProposal(
            proposal_id=f"prop_{fault.fault_id}_{resp.strategy_name}",
            fault_id=fault.fault_id,
            strategy_name=resp.strategy_name,
            adaptation_type="weight",
            old_config={'weight': current_weight},
            new_config={'weight': new_weight},
            reasoning=f"策略冲突故障: {fault.description}，降低冲突策略权重",
            acceptance_checks=[
                AcceptanceCheck(
                    check_id="backtest_validation",
                    description="回测验证新权重"
                ),
            ]
        )

    def validate_proposal(self, proposal: AdaptationProposal,
                         validation_results: Dict[str, bool]) -> bool:
        """
        验证提案是否满足接受标准

        参数:
            proposal: 适应性更新提案
            validation_results: {check_id: passed} 字典

        返回:
            是否通过验证
        """
        all_passed = all(validation_results.values())

        if all_passed:
            proposal.status = AdaptationStatus.VALIDATED
        else:
            proposal.status = AdaptationStatus.REJECTED

        return all_passed

    def apply_proposal(self, proposal: AdaptationProposal,
                      current_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用提案到配置

        返回:
            更新后的配置
        """
        if proposal.status != AdaptationStatus.VALIDATED:
            return current_config

        updated_config = current_config.copy()

        if proposal.adaptation_type == "weight":
            if 'strategy_weights' not in updated_config:
                updated_config['strategy_weights'] = {}
            updated_config['strategy_weights'][proposal.strategy_name] = \
                proposal.new_config.get('weight', 0.1)

        elif proposal.adaptation_type == "parameter":
            if 'signal_params' not in updated_config:
                updated_config['signal_params'] = {}
            updated_config['signal_params'].update(proposal.new_config)

        proposal.status = AdaptationStatus.APPLIED
        return updated_config
