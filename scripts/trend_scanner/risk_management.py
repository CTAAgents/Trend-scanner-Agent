"""
风险管理模块

提供止损计算、仓位管理、离场信号生成等功能：
- RiskManager: 风险管理器
- ExitSignalGenerator: 离场信号生成器
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from .market_analysis import TrendPhaseDetector


class RiskManager:
    """风险管理：止损计算、仓位管理"""

    def __init__(self, account_equity: float = 1_000_000,
                 risk_per_trade: float = 0.01,
                 atr_multiplier: float = 2.0):
        self.account_equity = account_equity
        self.risk_per_trade = risk_per_trade
        self.atr_multiplier = atr_multiplier

    def calc_stop(self, entry: float, atr: float, direction: int) -> float:
        distance = atr * self.atr_multiplier
        if direction == 1:
            return entry - distance
        return entry + distance

    def calc_take_profit(self, entry: float, stop: float, direction: int,
                         rr_ratio: float = 2.5) -> float:
        risk = abs(entry - stop)
        reward = risk * rr_ratio
        if direction == 1:
            return entry + reward
        return entry - reward

    def calc_position(self, entry: float, stop: float,
                      point_value: float = 10.0,
                      margin_per_lot: float = 5000.0) -> Tuple[int, float, float]:
        risk_amount = self.account_equity * self.risk_per_trade
        stop_distance = abs(entry - stop)
        if stop_distance == 0:
            return 0, 0, 0
        risk_per_lot = stop_distance * point_value
        lots = int(risk_amount / risk_per_lot)
        max_margin = self.account_equity * 0.30
        max_lots_margin = int(max_margin / margin_per_lot)
        lots = min(lots, max_lots_margin)
        actual_risk = lots * risk_per_lot
        margin_used = lots * margin_per_lot
        return max(0, lots), actual_risk, margin_used

    def adjust_by_signal(self, base_lots: int, signal_strength: str,
                         adx_value: float) -> int:
        adx_mult = 1.0 if adx_value >= 35 else (0.8 if adx_value >= 25 else 0.5)
        strength_mult = {'STRONG': 1.0, 'MEDIUM': 0.7, 'WEAK': 0.4}.get(signal_strength, 0.5)
        return max(0, int(base_lots * adx_mult * strength_mult))

    def calc_progressive_position(self, entry: float, stop: float,
                                   phase: str, confirmation_level: int = 0,
                                   point_value: float = 10.0,
                                   margin_per_lot: float = 5000.0) -> Tuple[int, float, float]:
        """
        渐进式仓位管理（艾德·斯科塔 1/3 法则）

        核心理念（来自趋势跟踪大师）：
        - 先用小仓位试探，看看趋势是否成立
        - 趋势确认后再加仓
        - 不要一次性满仓

        参数:
            entry: 入场价
            stop: 止损价
            phase: 趋势阶段（EMERGING/DEVELOPING/MATURE）
            confirmation_level: 确认级别（0=初始试探, 1=趋势确认, 2=强势确认）
            point_value: 每点价值
            margin_per_lot: 每手保证金

        返回:
            (lots, actual_risk, margin_used)
        """
        # 计算总可开仓位
        total_lots, total_risk, total_margin = self.calc_position(
            entry, stop, point_value, margin_per_lot
        )

        if total_lots <= 0:
            return 0, 0, 0

        # 根据确认级别分配仓位
        if confirmation_level == 0:
            # 初始试探：1/3 仓位
            lots = max(1, total_lots // 3)
        elif confirmation_level == 1:
            # 趋势确认：2/3 仓位
            lots = max(1, total_lots * 2 // 3)
        else:
            # 强势确认：满仓
            lots = total_lots

        # 根据趋势阶段微调
        phase_mult = {
            'EMERGING': 0.6,   # 萌芽期：谨慎
            'DEVELOPING': 1.0, # 发展期：标准
            'MATURE': 0.5,     # 成熟期：减仓
        }.get(phase, 0.8)

        lots = max(1, int(lots * phase_mult))

        actual_risk = lots * abs(entry - stop) * point_value
        margin_used = lots * margin_per_lot

        return lots, actual_risk, margin_used

    def calc_stop_by_phase(self, entry: float, atr: float, direction: int,
                           phase: str) -> float:
        """基于趋势阶段计算动态止损"""
        mult = TrendPhaseDetector.STOP_MULTIPLIER.get(phase, 2.0)
        distance = atr * mult
        if direction == 1:
            return entry - distance
        return entry + distance

    def adjust_position_by_phase(self, base_lots: int, phase: str,
                                 reliability_score: int) -> int:
        """基于趋势阶段和可靠性调整仓位"""
        phase_mult = TrendPhaseDetector.POSITION_MULTIPLIER.get(phase, 0.0)
        reliability_mult = reliability_score / 100.0
        return max(0, int(base_lots * phase_mult * reliability_mult))


# ===========================================================================
# 数据持久化层 (SQLite + 可选 DuckDB)
# ===========================================================================

class ExitSignalGenerator:
    """
    动量衰竭离场信号生成器

    核心原则：
    1. 尽量在动量衰竭时离场
    2. 避免过早离场（使用多指标确认）
    3. 避免过晚离场（使用跟踪止损）

    离场信号类型：
    - MOMENTUM_EXHAUSTION: 动量衰竭（主要离场信号）
    - TRAILING_STOP: 跟踪止损（保护利润）
    - REVERSAL_SIGNAL: 反转信号（趋势可能反转）
    - PROFIT_TARGET: 目标盈利（达到预期收益）
    """

    # 离场信号权重
    EXIT_WEIGHTS = {
        'MOMENTUM_EXHAUSTION': 0.40,  # 动量衰竭
        'TRAILING_STOP': 0.25,        # 跟踪止损
        'REVERSAL_SIGNAL': 0.20,      # 反转信号
        'PROFIT_TARGET': 0.15         # 目标盈利
    }

    @classmethod
    def _safe_val(cls, val, default=0):
        if isinstance(val, pd.Series):
            val = val.iloc[-1]
        if pd.isna(val):
            return default
        return float(val)

    @classmethod
    def detect_momentum_exhaustion(cls, df: pd.DataFrame, direction: int) -> Dict:
        """
        检测动量衰竭信号

        参数:
            df: 包含指标的DataFrame
            direction: 当前持仓方向 (1=多头, -1=空头)

        返回:
            {
                'signal': True/False,
                'strength': 0-100,
                'reasons': [原因列表],
                'suggested_action': 'EXIT' / 'HOLD' / 'REDUCE'
            }
        """
        if len(df) < 20:
            return {'signal': False, 'strength': 0, 'reasons': [], 'suggested_action': 'HOLD'}

        latest = df.iloc[-1]
        close = cls._safe_val(latest.get('close'))
        if close <= 0:
            return {'signal': False, 'strength': 0, 'reasons': [], 'suggested_action': 'HOLD'}

        exhaustion_score = 0
        reasons = []

        # ---- 1. MACD 柱状线衰竭 ----
        macd_hist = cls._safe_val(latest.get('macd_hist'))
        macd_hist_prev = cls._safe_val(df['macd_hist'].iloc[-2]) if 'macd_hist' in df.columns else 0
        macd_hist_prev3 = cls._safe_val(df['macd_hist'].iloc[-4]) if len(df) >= 4 and 'macd_hist' in df.columns else 0

        if direction > 0:  # 多头持仓
            if macd_hist > 0 and macd_hist < macd_hist_prev * 0.7:
                exhaustion_score += 25
                reasons.append(f"MACD柱收缩{((1-macd_hist/macd_hist_prev)*100):.0f}%→动量减弱")
            if macd_hist > 0 and macd_hist < macd_hist_prev3 * 0.5:
                exhaustion_score += 15
                reasons.append("MACD柱连续收缩→动量持续衰减")
            if macd_hist > 0 and macd_hist_prev < 0:
                exhaustion_score += 20
                reasons.append("MACD柱由负转正后又收缩→假突破")
        else:  # 空头持仓
            if macd_hist < 0 and macd_hist > macd_hist_prev * 0.7:
                exhaustion_score += 25
                reasons.append(f"MACD柱收缩{((1-abs(macd_hist)/abs(macd_hist_prev))*100):.0f}%→动量减弱")
            if macd_hist < 0 and macd_hist > macd_hist_prev3 * 0.5:
                exhaustion_score += 15
                reasons.append("MACD柱连续收缩→动量持续衰减")

        # ---- 2. RSI 超买超卖回归 ----
        rsi = cls._safe_val(latest.get('rsi'))
        rsi_prev = cls._safe_val(df['rsi'].iloc[-2]) if 'rsi' in df.columns else rsi

        if direction > 0:  # 多头持仓
            if rsi > 70 and rsi < rsi_prev:
                exhaustion_score += 20
                reasons.append(f"RSI={rsi:.0f}从超买区回落→动量减弱")
            elif rsi > 60 and rsi < rsi_prev - 5:
                exhaustion_score += 10
                reasons.append(f"RSI从{rsi_prev:.0f}降至{rsi:.0f}→动量减弱")
        else:  # 空头持仓
            if rsi < 30 and rsi > rsi_prev:
                exhaustion_score += 20
                reasons.append(f"RSI={rsi:.0f}从超卖区反弹→动量减弱")
            elif rsi < 40 and rsi > rsi_prev + 5:
                exhaustion_score += 10
                reasons.append(f"RSI从{rsi_prev:.0f}升至{rsi:.0f}→动量减弱")

        # ---- 3. 均线乖离过大（回归风险）----
        ema20 = cls._safe_val(latest.get('ema20'))
        ema60 = cls._safe_val(latest.get('ema60'))

        if ema20 > 0 and ema60 > 0:
            ma_deviation = (ema20 - ema60) / ema60 * 100
            if direction > 0 and ma_deviation > 5:
                exhaustion_score += 15
                reasons.append(f"EMA20偏离EMA60 {ma_deviation:.1f}%→回归风险")
            elif direction < 0 and ma_deviation < -5:
                exhaustion_score += 15
                reasons.append(f"EMA20偏离EMA60 {ma_deviation:.1f}%→回归风险")

        # ---- 4. 价格与通道上/下轨距离 ----
        if 'dc_upper' in df.columns and 'dc_lower' in df.columns:
            dc_upper = cls._safe_val(latest.get('dc_upper'))
            dc_lower = cls._safe_val(latest.get('dc_lower'))
            if dc_upper > dc_lower:
                channel_pos = (close - dc_lower) / (dc_upper - dc_lower) * 100
                if direction > 0 and channel_pos > 90:
                    exhaustion_score += 15
                    reasons.append(f"价格在通道上沿{channel_pos:.0f}%→可能回调")
                elif direction < 0 and channel_pos < 10:
                    exhaustion_score += 15
                    reasons.append(f"价格在通道下沿{channel_pos:.0f}%→可能反弹")

        # ---- 5. 成交量背离 ----
        if 'volume' in df.columns and len(df) >= 21:
            vol = cls._safe_val(latest.get('volume'))
            vol_ma = df['volume'].iloc[-21:].mean()
            if vol_ma > 0:
                vol_ratio = vol / vol_ma
                price_change = (close - cls._safe_val(df['close'].iloc[-2])) / close * 100

                if direction > 0 and price_change > 0 and vol_ratio < 0.7:
                    exhaustion_score += 10
                    reasons.append(f"价涨缩量(量比{vol_ratio:.1f})→上涨乏力")
                elif direction < 0 and price_change < 0 and vol_ratio < 0.7:
                    exhaustion_score += 10
                    reasons.append(f"价跌缩量(量比{vol_ratio:.1f})→下跌乏力")

        # ---- 6. ADX 趋势强度下降（参考指标）----
        adx = cls._safe_val(latest.get('adx'))
        adx_prev5 = cls._safe_val(df['adx'].iloc[-5]) if len(df) >= 5 and 'adx' in df.columns else adx
        if adx < adx_prev5 - 3 and adx < 25:
            exhaustion_score += 10
            reasons.append(f"ADX从{adx_prev5:.1f}降至{adx:.1f}→趋势减弱")

        # ---- 判定离场信号 ----
        exhaustion_score = min(100, exhaustion_score)

        if exhaustion_score >= 60:
            suggested_action = 'EXIT'
        elif exhaustion_score >= 40:
            suggested_action = 'REDUCE'
        else:
            suggested_action = 'HOLD'

        return {
            'signal': exhaustion_score >= 40,
            'strength': exhaustion_score,
            'reasons': reasons,
            'suggested_action': suggested_action
        }

    @classmethod
    def detect_trailing_stop(cls, df: pd.DataFrame, direction: int,
                             entry_price: float, current_stop: float) -> Dict:
        """
        跟踪止损检测

        参数:
            direction: 持仓方向
            entry_price: 入场价格
            current_stop: 当前止损价

        返回:
            {
                'new_stop': 新止损价,
                'triggered': 是否触发,
                'reason': 原因
            }
        """
        if len(df) < 5:
            return {'new_stop': current_stop, 'triggered': False, 'reason': '数据不足'}

        latest = df.iloc[-1]
        close = cls._safe_val(latest.get('close'))
        atr = cls._safe_val(latest.get('atr'))

        if close <= 0 or atr <= 0:
            return {'new_stop': current_stop, 'triggered': False, 'reason': '数据异常'}

        # 计算新的跟踪止损
        if direction > 0:  # 多头
            # 跟踪止损 = 最高价 - 2×ATR
            recent_high = df['high'].iloc[-10:].max()
            new_stop = recent_high - 2 * atr

            # 止损只能上移，不能下移
            new_stop = max(new_stop, current_stop)

            # 检查是否触发
            triggered = close < new_stop
            reason = f"价格{close:.2f}跌破跟踪止损{new_stop:.2f}" if triggered else "未触发"

        else:  # 空头
            # 跟踪止损 = 最低价 + 2×ATR
            recent_low = df['low'].iloc[-10:].min()
            new_stop = recent_low + 2 * atr

            # 止损只能下移，不能上移
            new_stop = min(new_stop, current_stop)

            # 检查是否触发
            triggered = close > new_stop
            reason = f"价格{close:.2f}突破跟踪止损{new_stop:.2f}" if triggered else "未触发"

        return {
            'new_stop': round(new_stop, 2),
            'triggered': triggered,
            'reason': reason
        }

    @classmethod
    def detect_reversal_signal(cls, df: pd.DataFrame, direction: int) -> Dict:
        """
        反转信号检测

        返回:
            {
                'signal': True/False,
                'strength': 0-100,
                'reasons': [原因列表]
            }
        """
        if len(df) < 20:
            return {'signal': False, 'strength': 0, 'reasons': []}

        latest = df.iloc[-1]
        reversal_score = 0
        reasons = []

        # ---- 1. 价格反转形态 ----
        close = cls._safe_val(latest.get('close'))
        open_price = cls._safe_val(latest.get('open'))
        high = cls._safe_val(latest.get('high'))
        low = cls._safe_val(latest.get('low'))

        body = abs(close - open_price)
        total_range = high - low

        if total_range > 0:
            # 长上影线（多头反转信号）
            upper_shadow = high - max(close, open_price)
            if upper_shadow > body * 2 and direction > 0:
                reversal_score += 20
                reasons.append("长上影线→多头反转信号")

            # 长下影线（空头反转信号）
            lower_shadow = min(close, open_price) - low
            if lower_shadow > body * 2 and direction < 0:
                reversal_score += 20
                reasons.append("长下影线→空头反转信号")

        # ---- 2. 均线死叉/金叉 ----
        ema20 = cls._safe_val(latest.get('ema20'))
        ema60 = cls._safe_val(latest.get('ema60'))
        ema20_prev = cls._safe_val(df['ema20'].iloc[-2]) if 'ema20' in df.columns else ema20
        ema60_prev = cls._safe_val(df['ema60'].iloc[-2]) if 'ema60' in df.columns else ema60

        if direction > 0:  # 多头持仓，检测死叉
            if ema20_prev > ema60_prev and ema20 < ema60:
                reversal_score += 25
                reasons.append("EMA20下穿EMA60→死叉反转信号")
        else:  # 空头持仓，检测金叉
            if ema20_prev < ema60_prev and ema20 > ema60:
                reversal_score += 25
                reasons.append("EMA20上穿EMA60→金叉反转信号")

        # ---- 3. MACD 背离 ----
        if len(df) >= 20:
            macd = cls._safe_val(latest.get('macd'))
            macd_signal = cls._safe_val(latest.get('macd_signal'))

            # 价格新高但MACD未新高（顶背离）
            price_high_20 = df['close'].iloc[-20:].max()
            macd_high_20 = df['macd'].iloc[-20:].max() if 'macd' in df.columns else macd

            if direction > 0 and close >= price_high_20 * 0.99 and macd < macd_high_20 * 0.9:
                reversal_score += 20
                reasons.append("价格接近新高但MACD未同步→顶背离")

            # 价格新低但MACD未新低（底背离）
            price_low_20 = df['close'].iloc[-20:].min()
            macd_low_20 = df['macd'].iloc[-20:].min() if 'macd' in df.columns else macd

            if direction < 0 and close <= price_low_20 * 1.01 and macd > macd_low_20 * 0.9:
                reversal_score += 20
                reasons.append("价格接近新低但MACD未同步→底背离")

        # ---- 4. RSI 极端反转 ----
        rsi = cls._safe_val(latest.get('rsi'))
        rsi_prev = cls._safe_val(df['rsi'].iloc[-2]) if 'rsi' in df.columns else rsi

        if direction > 0 and rsi > 70 and rsi < rsi_prev:
            reversal_score += 15
            reasons.append(f"RSI={rsi:.0f}从超买区回落→反转信号")
        elif direction < 0 and rsi < 30 and rsi > rsi_prev:
            reversal_score += 15
            reasons.append(f"RSI={rsi:.0f}从超卖区反弹→反转信号")

        reversal_score = min(100, reversal_score)

        return {
            'signal': reversal_score >= 40,
            'strength': reversal_score,
            'reasons': reasons
        }

    @classmethod
    def generate_exit_signal(cls, df: pd.DataFrame, direction: int,
                             entry_price: float, current_stop: float,
                             target_profit: float = 0.05) -> Dict:
        """
        综合离场信号生成

        参数:
            direction: 持仓方向
            entry_price: 入场价格
            current_stop: 当前止损价
            target_profit: 目标盈利比例（默认5%）

        返回:
            {
                'exit_signal': True/False,
                'exit_type': 离场类型,
                'confidence': 0-100,
                'reasons': [原因列表],
                'new_stop': 新止损价,
                'suggested_action': 'EXIT' / 'HOLD' / 'REDUCE'
            }
        """
        # 1. 动量衰竭检测
        exhaustion = cls.detect_momentum_exhaustion(df, direction)

        # 2. 跟踪止损检测
        trailing = cls.detect_trailing_stop(df, direction, entry_price, current_stop)

        # 3. 反转信号检测
        reversal = cls.detect_reversal_signal(df, direction)

        # 4. 目标盈利检测
        close = cls._safe_val(df.iloc[-1].get('close'))
        if entry_price > 0:
            profit_pct = (close - entry_price) / entry_price * 100 if direction > 0 else \
                        (entry_price - close) / entry_price * 100
            profit_target_reached = profit_pct >= target_profit * 100
        else:
            profit_pct = 0
            profit_target_reached = False

        # 5. 综合判断
        exit_signal = False
        exit_type = None
        confidence = 0
        all_reasons = []

        # 优先级：跟踪止损 > 反转信号 > 动量衰竭 > 目标盈利
        if trailing['triggered']:
            exit_signal = True
            exit_type = 'TRAILING_STOP'
            confidence = 90
            all_reasons.append(trailing['reason'])
        elif reversal['signal'] and reversal['strength'] >= 60:
            exit_signal = True
            exit_type = 'REVERSAL_SIGNAL'
            confidence = reversal['strength']
            all_reasons.extend(reversal['reasons'])
