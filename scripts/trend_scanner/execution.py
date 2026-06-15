"""
执行引擎模块

提供持仓状态机、硬风控、交易可行性过滤、日志归因等实战功能：
- PositionState: 持仓状态机（FLAT/LONG/SHORT）
- RiskGuard: 硬风控层（止损/熔断/波动率仓位上限）
- TradeFilter: 交易可行性过滤（涨跌停/点差/成交量）
- ExecutionLog: 结构化日志
- ExecutionEngine: 执行引擎（整合状态机+风控+过滤+日志）
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import json
import numpy as np
import pandas as pd


class State(Enum):
    """持仓状态"""
    FLAT = 'FLAT'
    LONG = 'LONG'
    SHORT = 'SHORT'


class PositionState:
    """
    持仓状态机

    核心思想：用纪律代替数学抖动
    - 入场需要"够强"的信号（hysteresis）
    - 出场需要"理由"（止损/趋势崩溃/信号消失）
    - 防止在零附近反复横跳
    """

    def __init__(self, enter_threshold: float = 0.35,
                 exit_threshold: float = 0.15,
                 atr_stop_multiplier: float = 2.0,
                 trend_break_threshold: float = 0.6,
                 max_holding_bars: int = 30):
        """
        参数:
            enter_threshold: 入场门槛（|pos| > 此值才允许开仓）
            exit_threshold: 信号消失门槛（|pos| < 此值且无其他出场理由时平仓）
            atr_stop_multiplier: ATR止损倍数
            trend_break_threshold: 趋势崩溃阈值（S_trend反向且|S_trend| > 此值）
            max_holding_bars: 最大持仓周期（K线数）
        """
        self.enter_threshold = enter_threshold
        self.exit_threshold = exit_threshold
        self.atr_stop_multiplier = atr_stop_multiplier
        self.trend_break_threshold = trend_break_threshold
        self.max_holding_bars = max_holding_bars

        # 状态
        self.state = State.FLAT
        self.entry_price = 0.0
        self.entry_bar = 0
        self.holding_bars = 0
        self.stop_loss = 0.0
        self.direction = 0  # 1=多, -1=空, 0=无

    def reset(self):
        """重置状态"""
        self.state = State.FLAT
        self.entry_price = 0.0
        self.entry_bar = 0
        self.holding_bars = 0
        self.stop_loss = 0.0
        self.direction = 0

    def update(self, pos: float, current_price: float, atr: float,
               s_trend: float, bar_index: int = 0) -> Dict:
        """
        更新状态机

        参数:
            pos: 当前目标仓位信号 [-1, 1]
            current_price: 当前价格
            atr: 当前ATR
            s_trend: 趋势确认维度得分 [-1, 1]
            bar_index: 当前K线索引

        返回:
            action: HOLD/OPEN_LONG/OPEN_SHORT/CLOSE/STOP_LOSS/TREND_BREAK/TIME_STOP
            reason: 出场原因
            target_size: 目标仓位大小 [0, 1]
        """
        action = 'HOLD'
        reason = ''
        target_size = 0.0

        # 更新持仓天数
        if self.state != State.FLAT:
            self.holding_bars += 1

        # ============================================================
        # 持仓中：检查出场条件
        # ============================================================
        if self.state == State.LONG:
            # 1. 硬止损
            if atr > 0 and current_price <= self.stop_loss:
                action = 'STOP_LOSS'
                reason = f'价格{current_price:.0f}跌破止损{self.stop_loss:.0f}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}

            # 2. 趋势崩溃
            if s_trend < -self.trend_break_threshold:
                action = 'TREND_BREAK'
                reason = f'趋势崩溃：S_trend={s_trend:+.2f} < -{self.trend_break_threshold}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}

            # 3. 时间止损
            if self.holding_bars >= self.max_holding_bars:
                action = 'TIME_STOP'
                reason = f'持仓{self.holding_bars}根K线，超过最大持仓周期{self.max_holding_bars}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}

            # 4. 信号消失（pos方向改变或幅度衰减）
            if pos < -self.exit_threshold:
                action = 'CLOSE'
                reason = f'信号反转：pos={pos:+.2f}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}
            elif abs(pos) < self.exit_threshold:
                action = 'CLOSE'
                reason = f'信号消失：|pos|={abs(pos):.2f} < {self.exit_threshold}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}

            # 5. 持仓中：目标仓位（只允许减仓/维持，不允许漂成空）
            target_size = max(0, min(1, pos))
            return {'action': 'HOLD', 'reason': '', 'target_size': target_size}

        elif self.state == State.SHORT:
            # 1. 硬止损
            if atr > 0 and current_price >= self.stop_loss:
                action = 'STOP_LOSS'
                reason = f'价格{current_price:.0f}突破止损{self.stop_loss:.0f}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}

            # 2. 趋势崩溃
            if s_trend > self.trend_break_threshold:
                action = 'TREND_BREAK'
                reason = f'趋势崩溃：S_trend={s_trend:+.2f} > +{self.trend_break_threshold}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}

            # 3. 时间止损
            if self.holding_bars >= self.max_holding_bars:
                action = 'TIME_STOP'
                reason = f'持仓{self.holding_bars}根K线，超过最大持仓周期{self.max_holding_bars}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}

            # 4. 信号消失
            if pos > self.exit_threshold:
                action = 'CLOSE'
                reason = f'信号反转：pos={pos:+.2f}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}
            elif abs(pos) < self.exit_threshold:
                action = 'CLOSE'
                reason = f'信号消失：|pos|={abs(pos):.2f} < {self.exit_threshold}'
                self.reset()
                return {'action': action, 'reason': reason, 'target_size': 0.0}

            # 5. 持仓中：目标仓位（只允许减仓/维持，不允许漂成多）
            target_size = max(-1, min(0, pos))
            return {'action': 'HOLD', 'reason': '', 'target_size': target_size}

        # ============================================================
        # 空仓：检查入场条件
        # ============================================================
        else:  # FLAT
            if abs(pos) > self.enter_threshold:
                if pos > 0:
                    action = 'OPEN_LONG'
                    reason = f'多头信号：pos={pos:+.2f} > {self.enter_threshold}'
                    self.state = State.LONG
                    self.direction = 1
                else:
                    action = 'OPEN_SHORT'
                    reason = f'空头信号：pos={pos:+.2f} < -{self.enter_threshold}'
                    self.state = State.SHORT
                    self.direction = -1

                self.entry_price = current_price
                self.entry_bar = bar_index
                self.holding_bars = 0

                # 设置止损
                if atr > 0:
                    if self.direction == 1:
                        self.stop_loss = current_price - self.atr_stop_multiplier * atr
                    else:
                        self.stop_loss = current_price + self.atr_stop_multiplier * atr

                target_size = abs(pos)
                return {'action': action, 'reason': reason, 'target_size': target_size}

            return {'action': 'HOLD', 'reason': '', 'target_size': 0.0}

    def get_state_info(self) -> Dict:
        """获取当前状态信息"""
        return {
            'state': self.state.value,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'holding_bars': self.holding_bars,
            'stop_loss': self.stop_loss,
        }


class RiskGuard:
    """
    硬风控层

    独立于信号的风控机制：
    - 日亏损熔断
    - 连续亏损降权
    - 波动率仓位上限
    - 闪崩检测
    """

    def __init__(self, max_daily_loss: float = 0.02,
                 max_consecutive_losses: int = 3,
                 target_volatility: float = 0.20,
                 crash_threshold_atr: float = 4.0):
        """
        参数:
            max_daily_loss: 日最大亏损比例（2%）
            max_consecutive_losses: 最大连续亏损次数
            target_volatility: 目标年化波动率（20%）
            crash_threshold_atr: 闪崩检测阈值（ATR倍数）
        """
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.target_volatility = target_volatility
        self.crash_threshold_atr = crash_threshold_atr

        # 状态
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.trading_disabled = False
        self.disable_until_bar = 0

    def check_daily_loss(self, current_pnl: float, equity: float) -> bool:
        """
        检查日亏损熔断

        返回: True=触发熔断，需强平
        """
        self.daily_pnl = current_pnl
        if equity > 0 and current_pnl < -self.max_daily_loss * equity:
            self.trading_disabled = True
            return True
        return False

    def check_consecutive_losses(self, is_loss: bool) -> float:
        """
        检查连续亏损，返回仓位乘数

        返回: 仓位乘数 [0.5, 1.0]
        """
        if is_loss:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        if self.consecutive_losses >= self.max_consecutive_losses:
            # 连续亏损越多，仓位越小
            multiplier = max(0.5, 1.0 - 0.1 * self.consecutive_losses)
            return multiplier
        return 1.0

    def calc_vol_position_limit(self, realized_vol: float) -> float:
        """
        基于波动率计算仓位上限

        参数:
            realized_vol: 已实现年化波动率

        返回: 仓位上限 [0.25, 1.0]
        """
        if realized_vol <= 0:
            return 1.0
        vol_factor = self.target_volatility / realized_vol
        return np.clip(vol_factor, 0.25, 1.0)

    def detect_crash(self, candle_range: float, atr: float) -> bool:
        """
        检测闪崩/异常行情

        参数:
            candle_range: 当前K线振幅（high-low）
            atr: 当前ATR

        返回: True=检测到闪崩
        """
        if atr > 0 and candle_range > self.crash_threshold_atr * atr:
            return True
        return False

    def is_trading_allowed(self, current_bar: int) -> bool:
        """检查是否允许交易"""
        if self.trading_disabled and current_bar < self.disable_until_bar:
            return False
        self.trading_disabled = False
        return True

    def disable_trading(self, until_bar: int):
        """禁止交易直到指定K线"""
        self.trading_disabled = True
        self.disable_until_bar = until_bar


class TradeFilter:
    """
    交易可行性过滤

    在发单前检查市场条件，过滤不可执行的信号：
    - 涨跌停检测
    - 点差异常检测
    - 成交量过低检测
    """

    def __init__(self, max_spread_pct: float = 0.5,
                 min_volume: int = 100,
                 limit_threshold_pct: float = 0.09):
        """
        参数:
            max_spread_pct: 最大点差百分比（0.5%）
            min_volume: 最小成交量
            limit_threshold_pct: 涨跌停阈值百分比（9%）
        """
        self.max_spread_pct = max_spread_pct
        self.min_volume = min_volume
        self.limit_threshold_pct = limit_threshold_pct

    def check_feasibility(self, open_price: float, high: float, low: float,
                          close: float, volume: int, prev_close: float = 0) -> Dict:
        """
        检查交易可行性

        参数:
            open_price: 开盘价
            high: 最高价
            low: 最低价
            close: 收盘价
            volume: 成交量
            prev_close: 前收盘价（用于涨跌停检测）

        返回:
            feasible: 是否可行
            reason: 不可行原因
            spread_pct: 点差百分比
        """
        reasons = []

        # 1. 涨跌停检测
        if prev_close > 0:
            change_pct = abs(close - prev_close) / prev_close
            if change_pct >= self.limit_threshold_pct:
                reasons.append(f'接近涨跌停：涨跌幅{change_pct*100:.1f}%')

        # 2. 点差异常检测
        if close > 0:
            spread_pct = (high - low) / close * 100
            if spread_pct > self.max_spread_pct:
                reasons.append(f'点差异常：振幅{spread_pct:.2f}% > {self.max_spread_pct}%')
        else:
            spread_pct = 0

        # 3. 成交量过低检测
        if volume < self.min_volume:
            reasons.append(f'成交量过低：{volume} < {self.min_volume}')

        return {
            'feasible': len(reasons) == 0,
            'reasons': reasons,
            'spread_pct': round(spread_pct, 3),
        }

    def calc_slippage(self, price: float, atr: float, volume: int,
                      target_size: float) -> float:
        """
        计算滑点估计

        参数:
            price: 当前价格
            atr: 当前ATR
            volume: 成交量
            target_size: 目标仓位大小

        返回: 估计滑点（价格单位）
        """
        # 基础滑点：ATR的0.1%
        base_slippage = atr * 0.001 if atr > 0 else price * 0.0001

        # 成交量调整：成交量越低，滑点越大
        if volume > 0:
            volume_factor = max(1.0, 1000 / volume)
        else:
            volume_factor = 10.0

        # 仓位大小调整：仓位越大，滑点越大
        size_factor = 1.0 + abs(target_size) * 0.5

        return base_slippage * volume_factor * size_factor


class ExecutionLog:
    """
    执行日志（4.1 结构化日志）

    记录每一根K线的决策过程，用于归因分析
    日志包含：状态、仓位、维度得分、z分数、MAD掩码、动作、原因
    """

    def __init__(self, max_logs: int = 1000):
        self.logs = []
        self.max_logs = max_logs
        self.filter_stats = {
            'total_signals': 0,
            'filtered_count': 0,
            'filtered_reasons': {},
            'dimension_filter_count': {},
        }

    def log(self, timestamp, state, pos, target_size, dimensions, z_scores,
            mad_mask, vote_sign, conflict, discount, action, reason,
            entry_price=0, current_price=0, pnl=0, filtered_out=None):
        """记录一条日志"""
        entry = {
            'timestamp': str(timestamp),
            'state': state,
            'pos_target': round(pos, 3),
            'pos_executed': round(target_size, 3),
            'dimensions': {k: round(v, 3) for k, v in dimensions.items()},
            'z_scores': [round(z, 3) for z in z_scores] if z_scores else [],
            'mad_mask': mad_mask,
            'vote_sign': vote_sign,
            'conflict': conflict,
            'discount': round(discount, 3),
            'entry_price': round(entry_price, 2),
            'current_price': round(current_price, 2),
            'pnl': round(pnl, 2),
            'action': action,
            'reason': reason,
        }
        self.logs.append(entry)

        # 统计过滤事件
        self.filter_stats['total_signals'] += 1
        if action == 'FILTERED':
            self.filter_stats['filtered_count'] += 1
            if reason not in self.filter_stats['filtered_reasons']:
                self.filter_stats['filtered_reasons'][reason] = 0
            self.filter_stats['filtered_reasons'][reason] += 1

        # 统计维度过滤
        if filtered_out:
            for dim in filtered_out:
                if dim not in self.filter_stats['dimension_filter_count']:
                    self.filter_stats['dimension_filter_count'][dim] = 0
                self.filter_stats['dimension_filter_count'][dim] += 1

        # 限制日志数量
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]

        return entry

    def get_recent(self, n: int = 10) -> List[Dict]:
        """获取最近n条日志"""
        return self.logs[-n:]

    def get_factor_attribution(self, n: int = 50) -> Dict:
        """
        4.2 因子贡献归因

        统计各维度对最终信号的贡献度

        参数:
            n: 统计最近n条日志

        返回:
            各维度贡献度排名
        """
        if not self.logs:
            return {}

        recent = self.logs[-n:]
        attribution = {}

        for log in recent:
            dims = log.get('dimensions', {})
            for dim_name, score in dims.items():
                if dim_name not in attribution:
                    attribution[dim_name] = {
                        'total_contribution': 0,
                        'positive_count': 0,
                        'negative_count': 0,
                        'avg_score': 0,
                        'scores': [],
                    }
                attribution[dim_name]['total_contribution'] += abs(score)
                attribution[dim_name]['scores'].append(score)
                if score > 0:
                    attribution[dim_name]['positive_count'] += 1
                elif score < 0:
                    attribution[dim_name]['negative_count'] += 1

        # 计算平均值和排名
        for dim_name, stats in attribution.items():
            if stats['scores']:
                stats['avg_score'] = round(np.mean(stats['scores']), 3)
            stats['total_contribution'] = round(stats['total_contribution'], 2)

        # 按贡献度排序
        sorted_attribution = dict(sorted(
            attribution.items(),
            key=lambda x: x[1]['total_contribution'],
            reverse=True
        ))

        return sorted_attribution

    def get_filter_statistics(self) -> Dict:
        """
        4.3 过滤事件统计

        返回:
            过滤频率、原因分布、维度过滤统计
        """
        total = self.filter_stats['total_signals']
        if total == 0:
            return {'filter_rate': 0, 'reasons': {}, 'dimension_filters': {}}

        return {
            'total_signals': total,
            'filtered_count': self.filter_stats['filtered_count'],
            'filter_rate': round(self.filter_stats['filtered_count'] / total * 100, 2),
            'reasons': self.filter_stats['filtered_reasons'],
            'dimension_filters': self.filter_stats['dimension_filter_count'],
        }

    def export_csv(self, path: str):
        """导出为CSV"""
        import pandas as pd
        df = pd.DataFrame(self.logs)
        df.to_csv(path, index=False)

    def export_json(self, path: str):
        """导出为JSON"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.logs, f, ensure_ascii=False, indent=2)


class ExecutionEngine:
    """
    执行引擎

    整合状态机、风控、交易可行性过滤、日志，提供完整的执行生命周期

    核心原则：
    1. signal[t] → execute[t+1] open（禁止未来函数）
    2. 交易前必须通过可行性过滤
    3. 所有决策都有日志记录
    """

    def __init__(self, enter_threshold: float = 0.35,
                 exit_threshold: float = 0.15,
                 atr_stop_multiplier: float = 2.0,
                 max_daily_loss: float = 0.02,
                 target_volatility: float = 0.20,
                 max_spread_pct: float = 0.5,
                 min_volume: int = 100):
        """
        参数:
            enter_threshold: 入场门槛
            exit_threshold: 出场门槛
            atr_stop_multiplier: ATR止损倍数
            max_daily_loss: 日最大亏损比例
            target_volatility: 目标年化波动率
            max_spread_pct: 最大点差百分比
            min_volume: 最小成交量
        """
        self.state_machine = PositionState(
            enter_threshold=enter_threshold,
            exit_threshold=exit_threshold,
            atr_stop_multiplier=atr_stop_multiplier,
        )
        self.risk_guard = RiskGuard(
            max_daily_loss=max_daily_loss,
            target_volatility=target_volatility,
        )
        self.trade_filter = TradeFilter(
            max_spread_pct=max_spread_pct,
            min_volume=min_volume,
        )
        self.logger = ExecutionLog()

        # 执行价格假设：signal[t] → execute[t+1] open
        self.pending_signal = None
        self.pending_reason = None

    def execute(self, pos: float, current_price: float, atr: float,
                s_trend: float, bar_index: int = 0,
                dimensions: Dict = None, z_scores: List = None,
                mad_mask: List = None, vote_sign: int = 0,
                conflict: bool = False, discount: float = 1.0,
                realized_vol: float = 0.0,
                open_price: float = 0, high: float = 0, low: float = 0,
                volume: int = 0, prev_close: float = 0,
                filtered_out: List = None) -> Dict:
        """
        执行一次决策

        核心原则：signal[t] → execute[t+1] open
        当前K线计算信号，下一K线开盘价执行

        参数:
            pos: 目标仓位信号 [-1, 1]
            current_price: 当前价格（用于止损判断）
            atr: 当前ATR
            s_trend: 趋势确认维度得分 [-1, 1]
            bar_index: 当前K线索引
            dimensions: 各维度得分
            z_scores: 标准化后的维度值
            mad_mask: MAD过滤掩码
            vote_sign: 投票方向
            conflict: 是否冲突
            discount: 折扣系数
            realized_vol: 已实现波动率
            open_price: 开盘价（用于执行价格）
            high: 最高价
            low: 最低价
            volume: 成交量
            prev_close: 前收盘价

        返回:
            包含action、reason、target_size等的完整决策结果
        """
        # 1. 检查风控
        if not self.risk_guard.is_trading_allowed(bar_index):
            result = {
                'action': 'BLOCKED',
                'reason': '交易被禁止（日亏损熔断）',
                'target_size': 0.0,
                'execute_price': open_price if open_price > 0 else current_price,
            }
            self.logger.log(bar_index, self.state_machine.state.value, pos, 0.0,
                          dimensions or {}, z_scores or [], mad_mask or [],
                          vote_sign, conflict, discount, 'BLOCKED', result['reason'])
            return result

        # 2. 闪崩检测
        candle_range = high - low if high > 0 and low > 0 else current_price * 0.01
        if atr > 0 and self.risk_guard.detect_crash(candle_range, atr):
            if self.state_machine.state != State.FLAT:
                result = {
                    'action': 'CRASH_REDUCE',
                    'reason': '检测到异常行情，减仓',
                    'target_size': 0.0,
                    'execute_price': open_price if open_price > 0 else current_price,
                }
                self.state_machine.reset()
                self.logger.log(bar_index, 'FLAT', pos, 0.0,
                              dimensions or {}, z_scores or [], mad_mask or [],
                              vote_sign, conflict, discount, 'CRASH_REDUCE', result['reason'])
                return result

        # 3. 交易可行性过滤（1.3）
        if open_price > 0 and high > 0 and low > 0:
            feasibility = self.trade_filter.check_feasibility(
                open_price, high, low, current_price, volume, prev_close
            )
            if not feasibility['feasible']:
                result = {
                    'action': 'FILTERED',
                    'reason': f'交易不可行：{"; ".join(feasibility["reasons"])}',
                    'target_size': 0.0,
                    'execute_price': open_price,
                }
                self.logger.log(bar_index, self.state_machine.state.value, pos, 0.0,
                              dimensions or {}, z_scores or [], mad_mask or [],
                              vote_sign, conflict, discount, 'FILTERED', result['reason'])
                return result

        # 4. 波动率仓位上限
        vol_limit = self.risk_guard.calc_vol_position_limit(realized_vol)

        # 5. 状态机决策
        state_result = self.state_machine.update(pos, current_price, atr, s_trend, bar_index)

        # 6. 应用波动率仓位上限
        target_size = state_result['target_size'] * vol_limit * discount

        # 7. 连续亏损降权
        if state_result['action'] in ('STOP_LOSS', 'CLOSE'):
            is_loss = (self.state_machine.state == State.LONG and current_price < self.state_machine.entry_price) or \
                      (self.state_machine.state == State.SHORT and current_price > self.state_machine.entry_price)
            loss_multiplier = self.risk_guard.check_consecutive_losses(is_loss)
            target_size *= loss_multiplier

        # 8. 计算滑点
        slippage = 0
        if open_price > 0 and atr > 0 and volume > 0:
            slippage = self.trade_filter.calc_slippage(open_price, atr, volume, target_size)

        # 9. 执行价格：signal[t] → execute[t+1] open
        # 当前K线的信号，用下一K线的开盘价执行
        execute_price = open_price if open_price > 0 else current_price
        if state_result['action'] in ('OPEN_LONG', 'OPEN_SHORT'):
            # 开仓：加上滑点
            if state_result['action'] == 'OPEN_LONG':
                execute_price += slippage
            else:
                execute_price -= slippage

        # 10. 记录日志
        self.logger.log(
            bar_index, self.state_machine.state.value, pos, target_size,
            dimensions or {}, z_scores or [], mad_mask or [],
            vote_sign, conflict, discount,
            state_result['action'], state_result['reason'],
            self.state_machine.entry_price, execute_price, 0,
            filtered_out=filtered_out
        )

        return {
            'action': state_result['action'],
            'reason': state_result['reason'],
            'target_size': round(target_size, 3),
            'state': self.state_machine.state.value,
            'entry_price': self.state_machine.entry_price,
            'stop_loss': self.state_machine.stop_loss,
            'holding_bars': self.state_machine.holding_bars,
            'vol_limit': round(vol_limit, 3),
            'execute_price': round(execute_price, 2),
            'slippage': round(slippage, 4),
        }

    def generate_signal(self, pos: float, bar_index: int = 0) -> Dict:
        """
        生成信号（不执行）

        用于日线收盘决策 → 次日开盘执行的模式
        信号在当前K线生成，但不立即执行，等待下一K线开盘

        参数:
            pos: 目标仓位信号 [-1, 1]
            bar_index: 当前K线索引

        返回:
            signal: 信号类型
            pending: 是否有待执行信号
        """
        self.pending_signal = pos
        self.pending_reason = f'Signal generated at bar {bar_index}'

        return {
            'signal': 'LONG' if pos > 0 else ('SHORT' if pos < 0 else 'FLAT'),
            'pos': round(pos, 3),
            'pending': True,
            'bar_index': bar_index,
        }

    def execute_pending(self, open_price: float, atr: float, s_trend: float,
                        bar_index: int = 0, volume: int = 0) -> Dict:
        """
        执行待处理信号

        用于日线收盘决策 → 次日开盘执行的模式
        在下一K线开盘时执行之前生成的信号

        参数:
            open_price: 开盘价
            atr: 当前ATR
            s_trend: 趋势确认维度得分
            bar_index: 当前K线索引
            volume: 成交量

        返回:
            执行结果
        """
        if self.pending_signal is None:
            return {
                'action': 'NO_SIGNAL',
                'reason': '没有待执行的信号',
                'target_size': 0.0,
            }

        # 执行信号
        result = self.execute(
            pos=self.pending_signal,
            current_price=open_price,
            atr=atr,
            s_trend=s_trend,
            bar_index=bar_index,
            open_price=open_price,
            volume=volume,
        )

        # 清除待执行信号
        self.pending_signal = None
        self.pending_reason = None

        return result
