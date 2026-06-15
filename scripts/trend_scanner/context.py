"""
感知层 —— 上下文组装器

职责：从原始数据 + 技术指标 → 结构化 MarketContext
原则：只描述"市场现在是什么样"，不做"应该怎么做"的判断

感知层是推理层的眼睛和耳朵，不是大脑。
"""

import numpy as np
import pandas as pd
from typing import Optional, List

from .indicators import IndicatorEngine
from .models import (
    MarketContext, IndicatorSnapshot, MarketStructure,
    MomentumState, VolatilityState, TrendPhase,
)


class ContextAssembler:
    """
    上下文组装器

    将原始 OHLCV 数据 + 技术指标转换为结构化的 MarketContext。
    这是感知层的唯一出口，推理层的唯一入口。
    """

    def __init__(self, symbol: str, timeframe: str = "daily"):
        self.symbol = symbol
        self.timeframe = timeframe

    def assemble(self, df: pd.DataFrame, lookback: int = 120) -> MarketContext:
        """
        组装市场上下文

        参数:
            df: 包含 OHLCV 数据的 DataFrame（至少 lookback 行）
            lookback: 用于计算分位数等统计量的回看周期

        返回:
            MarketContext 结构化上下文
        """
        # 1. 计算技术指标
        engine = IndicatorEngine(df)
        df = engine.compute_all()

        # 2. 取最近一根K线
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # 3. 组装各维度状态
        snapshot = self._build_snapshot(latest)
        structure = self._build_structure(df, latest)
        momentum = self._build_momentum(df, latest)
        volatility = self._build_volatility(df, latest, lookback)

        # 4. 检测趋势阶段（核心状态）
        trend_phase = self._detect_trend_phase(df, latest, structure, momentum, volatility)

        # 5. 计算价格行为统计
        bars_since_high = self._bars_since_extreme(df['high'], 'high')
        bars_since_low = self._bars_since_extreme(df['low'], 'low')
        consec_up = self._consecutive_direction(df['close'], 'up')
        consec_down = self._consecutive_direction(df['close'], 'down')

        # 6. 计算日涨跌幅
        price_change_pct = 0.0
        if prev['close'] > 0:
            price_change_pct = (latest['close'] - prev['close']) / prev['close'] * 100

        # 7. 计算特征向量（用于经验检索）
        feature_vector = self._compute_feature_vector(df, latest)

        # 8. 组装上下文
        context = MarketContext(
            symbol=self.symbol,
            timestamp=str(latest.get('date', latest.name)),
            timeframe=self.timeframe,
            current_price=latest['close'],
            price_change_pct=price_change_pct,
            structure=structure,
            momentum=momentum,
            volatility=volatility,
            trend_phase=trend_phase,
            bars_since_high=bars_since_high,
            bars_since_low=bars_since_low,
            consecutive_up_days=consec_up,
            consecutive_down_days=consec_down,
            snapshot=snapshot,
            feature_vector=feature_vector,
        )

        return context

    # ──────────────────────────────────────────
    # 内部方法：构建各维度状态
    # ──────────────────────────────────────────

    def _build_snapshot(self, row) -> IndicatorSnapshot:
        """构建指标快照"""
        def safe(val, default=0.0):
            if pd.isna(val):
                return default
            return float(val)

        return IndicatorSnapshot(
            timestamp=str(row.get('date', '')),
            close=safe(row.get('close')),
            high=safe(row.get('high')),
            low=safe(row.get('low')),
            open=safe(row.get('open')),
            volume=safe(row.get('volume')),
            open_interest=safe(row.get('open_interest')),
            ema20=safe(row.get('ema20')),
            ema60=safe(row.get('ema60')),
            sma20=safe(row.get('sma20')),
            sma60=safe(row.get('sma60')),
            rsi=safe(row.get('rsi'), 50.0),
            macd=safe(row.get('macd')),
            macd_signal=safe(row.get('macd_signal')),
            macd_hist=safe(row.get('macd_hist')),
            stoch_k=safe(row.get('stoch_k'), 50.0),
            stoch_d=safe(row.get('stoch_d'), 50.0),
            cci=safe(row.get('cci')),
            atr=safe(row.get('atr')),
            bb_upper=safe(row.get('bb_upper')),
            bb_lower=safe(row.get('bb_lower')),
            bb_mid=safe(row.get('bb_mid')),
            adx=safe(row.get('adx')),
            plus_di=safe(row.get('plus_di')),
            minus_di=safe(row.get('minus_di')),
            # 七维趋势强度
            trend_strength_er=safe(row.get('er')),
            trend_strength_r2=safe(row.get('r_squared')),
            trend_strength_hurst=safe(row.get('hurst'), 0.5),
            trend_strength_adx_roc=safe(row.get('adx_roc')),
            trend_strength_ema_slope=safe(row.get('ema_slope_strength')),
            trend_strength_tsi=safe(row.get('tsi')),
            trend_strength_atr_ratio=safe(row.get('atr_ratio'), 1.0),
            trend_strength_composite=safe(row.get('trend_strength_composite')),
            dc_upper=safe(row.get('dc_upper')),
            dc_lower=safe(row.get('dc_lower')),
        )

    def _build_structure(self, df: pd.DataFrame, latest) -> MarketStructure:
        """构建市场结构（只描述，不判断）"""
        structure = MarketStructure()

        ema20 = latest.get('ema20', 0)
        ema60 = latest.get('ema60', 0)
        close = latest['close']

        # 均线排列
        if ema20 > 0 and ema60 > 0:
            gap_pct = (ema20 - ema60) / ema60 * 100

            # 检查斜率
            slope_20 = self._calc_slope(df['ema20'], 5)
            slope_60 = self._calc_slope(df['ema60'], 5)
            structure.ma_slope_20 = slope_20
            structure.ma_slope_60 = slope_60

            # 排列判断
            if ema20 > ema60:
                if slope_20 > 0 and slope_60 > 0:
                    structure.ma_arrangement = "STRONG_BULL"
                elif slope_20 > 0 or slope_60 > 0:
                    structure.ma_arrangement = "WEAK_BULL"
                else:
                    structure.ma_arrangement = "WEAK_BEAR"  # 伪多头
            else:
                if slope_20 < 0 and slope_60 < 0:
                    structure.ma_arrangement = "STRONG_BEAR"
                elif slope_20 < 0 or slope_60 < 0:
                    structure.ma_arrangement = "WEAK_BEAR"
                else:
                    structure.ma_arrangement = "WEAK_BULL"  # 伪空头

            # 价格位置
            if ema60 > 0:
                price_vs_ma_pct = (close - ema60) / ema60 * 100
                if price_vs_ma_pct > 1.0:
                    structure.price_vs_ma = "ABOVE"
                elif price_vs_ma_pct < -1.0:
                    structure.price_vs_ma = "BELOW"
                else:
                    structure.price_vs_ma = "NEAR"

        # 高低点结构
        structure.swing_structure = self._analyze_swing_structure(df)
        structure.recent_high = df['high'].iloc[-20:].max() if len(df) >= 20 else df['high'].max()
        structure.recent_low = df['low'].iloc[-20:].min() if len(df) >= 20 else df['low'].min()

        # 成交量
        if 'volume' in df.columns and len(df) >= 20:
            vol_ma = df['volume'].iloc[-20:].mean()
            current_vol = latest['volume']
            if vol_ma > 0:
                structure.volume_ratio = current_vol / vol_ma
                if structure.volume_ratio > 1.5:
                    structure.volume_trend = "INCREASING"
                elif structure.volume_ratio < 0.5:
                    structure.volume_trend = "DECREASING"

        # 持仓量
        if 'open_interest' in df.columns and len(df) >= 5:
            oi_now = latest['open_interest']
            oi_5d = df['open_interest'].iloc[-5]
            if oi_5d > 0:
                structure.oi_change_pct = (oi_now - oi_5d) / oi_5d * 100
                if structure.oi_change_pct > 5:
                    structure.oi_trend = "INCREASING"
                elif structure.oi_change_pct < -5:
                    structure.oi_trend = "DECREASING"

        return structure

    def _build_momentum(self, df: pd.DataFrame, latest) -> MomentumState:
        """构建动量状态（只描述，不判断）"""
        momentum = MomentumState()

        rsi = latest.get('rsi', 50)
        if not pd.isna(rsi):
            momentum.rsi_value = float(rsi)
            if rsi > 80:
                momentum.rsi_state = "OVERBOUGHT"
            elif rsi > 55:
                momentum.rsi_state = "STRONG"
            elif rsi < 20:
                momentum.rsi_state = "OVERSOLD"
            elif rsi < 45:
                momentum.rsi_state = "WEAK"
            else:
                momentum.rsi_state = "NEUTRAL"

        # MACD
        macd = latest.get('macd', 0)
        macd_signal = latest.get('macd_signal', 0)
        macd_hist = latest.get('macd_hist', 0)
        if not pd.isna(macd) and not pd.isna(macd_signal):
            if macd > macd_signal:
                momentum.macd_state = "BULLISH"
            else:
                momentum.macd_state = "BEARISH"

            # 柱状线趋势
            if len(df) >= 3:
                hist_prev = df['macd_hist'].iloc[-3]
                if not pd.isna(hist_prev) and not pd.isna(macd_hist):
                    if abs(macd_hist) > abs(hist_prev):
                        momentum.macd_histogram_trend = "EXPANDING"
                    elif abs(macd_hist) < abs(hist_prev):
                        momentum.macd_histogram_trend = "CONTRACTING"

        # STOCH
        stoch_k = latest.get('stoch_k', 50)
        if not pd.isna(stoch_k):
            if stoch_k > 80:
                momentum.stoch_state = "OVERBOUGHT"
            elif stoch_k > 55:
                momentum.stoch_state = "STRONG"
            elif stoch_k < 20:
                momentum.stoch_state = "OVERSOLD"
            elif stoch_k < 45:
                momentum.stoch_state = "WEAK"

        # CCI
        cci = latest.get('cci', 0)
        if not pd.isna(cci):
            if cci > 200:
                momentum.cci_state = "EXTREME_HIGH"
            elif cci > 100:
                momentum.cci_state = "HIGH"
            elif cci < -200:
                momentum.cci_state = "EXTREME_LOW"
            elif cci < -100:
                momentum.cci_state = "LOW"

        # 振荡器共振
        bullish = 0
        bearish = 0
        if momentum.rsi_state in ("STRONG", "OVERBOUGHT"):
            bullish += 1
        elif momentum.rsi_state in ("WEAK", "OVERSOLD"):
            bearish += 1
        if momentum.stoch_state in ("STRONG", "OVERBOUGHT"):
            bullish += 1
        elif momentum.stoch_state in ("WEAK", "OVERSOLD"):
            bearish += 1
        if momentum.cci_state in ("HIGH", "EXTREME_HIGH"):
            bullish += 1
        elif momentum.cci_state in ("LOW", "EXTREME_LOW"):
            bearish += 1

        momentum.resonance_count = max(bullish, bearish)
        if bullish >= 2 and bearish == 0:
            momentum.oscillator_resonance = "BULLISH"
        elif bearish >= 2 and bullish == 0:
            momentum.oscillator_resonance = "BEARISH"
        elif bullish > 0 and bearish > 0:
            momentum.oscillator_resonance = "MIXED"

        return momentum

    def _build_volatility(self, df: pd.DataFrame, latest, lookback: int) -> VolatilityState:
        """构建波动率状态"""
        vol = VolatilityState()

        close = latest['close']
        atr = latest.get('atr', 0)

        if close > 0 and not pd.isna(atr) and atr > 0:
            vol.atr_pct = atr / close * 100

            # ATR 分位数
            if len(df) >= lookback:
                atr_series = df['atr'].iloc[-lookback:].dropna()
                if len(atr_series) > 0:
                    vol.atr_percentile = (atr_series < atr).sum() / len(atr_series) * 100

        # 布林带宽度
        bb_upper = latest.get('bb_upper', 0)
        bb_lower = latest.get('bb_lower', 0)
        bb_mid = latest.get('bb_mid', 0)
        if bb_mid > 0 and not pd.isna(bb_upper) and not pd.isna(bb_lower):
            vol.bb_width = (bb_upper - bb_lower) / bb_mid
            if len(df) >= lookback:
                bb_width_series = ((df['bb_upper'] - df['bb_lower']) / df['bb_mid']).iloc[-lookback:].dropna()
                if len(bb_width_series) > 0:
                    vol.bb_width_percentile = (bb_width_series < vol.bb_width).sum() / len(bb_width_series) * 100

        # 波动率状态
        if vol.atr_percentile > 80:
            vol.regime = "EXTREME"
            vol.regime_confidence = 0.8
        elif vol.atr_percentile > 60:
            vol.regime = "HIGH"
            vol.regime_confidence = 0.7
        elif vol.atr_percentile < 20:
            vol.regime = "LOW"
            vol.regime_confidence = 0.7
        else:
            vol.regime = "NORMAL"
            vol.regime_confidence = 0.6

        return vol

    # ──────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────

    def _calc_slope(self, series: pd.Series, period: int) -> float:
        """计算斜率（百分比变化）"""
        if len(series) < period + 1:
            return 0.0
        current = series.iloc[-1]
        prev = series.iloc[-period - 1]
        if pd.isna(current) or pd.isna(prev) or prev == 0:
            return 0.0
        return (current - prev) / prev * 100

    def _analyze_swing_structure(self, df: pd.DataFrame) -> str:
        """分析高低点结构"""
        if len(df) < 20:
            return "NEUTRAL"

        highs = df['high'].iloc[-20:]
        lows = df['low'].iloc[-20:]

        # 简化判断：比较前半段和后半段的高低点
        mid = len(highs) // 2
        first_high = highs.iloc[:mid].max()
        second_high = highs.iloc[mid:].max()
        first_low = lows.iloc[:mid].min()
        second_low = lows.iloc[mid:].min()

        higher_high = second_high > first_high
        higher_low = second_low > first_low
        lower_high = second_high < first_high
        lower_low = second_low < first_low

        if higher_high and higher_low:
            return "HIGHER_HIGHS"
        elif lower_high and lower_low:
            return "LOWER_LOWS"
        elif higher_high or higher_low:
            return "MIXED_BULL"
        elif lower_high or lower_low:
            return "MIXED_BEAR"
        else:
            return "NEUTRAL"

    def _bars_since_extreme(self, series: pd.Series, extreme_type: str) -> int:
        """计算距离最近极值的K线数"""
        if len(series) < 2:
            return 0

        current = series.iloc[-1]
        if extreme_type == 'high':
            idx = series.idxmax()
        else:
            idx = series.idxmin()

        try:
            pos = series.index.get_loc(idx)
            return len(series) - 1 - pos
        except:
            return 0

    def _consecutive_direction(self, series: pd.Series, direction: str) -> int:
        """计算连续方向天数"""
        if len(series) < 2:
            return 0

        count = 0
        for i in range(len(series) - 1, 0, -1):
            if direction == 'up' and series.iloc[i] > series.iloc[i - 1]:
                count += 1
            elif direction == 'down' and series.iloc[i] < series.iloc[i - 1]:
                count += 1
            else:
                break

        return count

    def _compute_feature_vector(self, df: pd.DataFrame, latest) -> List[float]:
        """
        计算特征向量（用于经验检索的相似度计算）

        选择对趋势判断最有意义的特征，归一化到 [0, 1] 或 [-1, 1]
        """
        features = []

        # 1. 均线排列强度 (-1 to 1)
        ema20 = latest.get('ema20', 0)
        ema60 = latest.get('ema60', 0)
        if ema60 > 0:
            ma_gap = (ema20 - ema60) / ema60 * 100
            features.append(np.clip(ma_gap / 5, -1, 1))  # 归一化
        else:
            features.append(0.0)

        # 2. 价格位置 (-1 to 1)
        close = latest['close']
        if ema60 > 0:
            price_pos = (close - ema60) / ema60 * 100
            features.append(np.clip(price_pos / 5, -1, 1))
        else:
            features.append(0.0)

        # 3. RSI 归一化 (-1 to 1)
        rsi = latest.get('rsi', 50)
        if not pd.isna(rsi):
            features.append((rsi - 50) / 50)
        else:
            features.append(0.0)

        # 4. ADX 归一化 (0 to 1)
        adx = latest.get('adx', 0)
        if not pd.isna(adx):
            features.append(min(adx / 50, 1.0))
        else:
            features.append(0.0)

        # 5. ATR 百分比归一化 (0 to 1)
        atr = latest.get('atr', 0)
        if close > 0 and not pd.isna(atr):
            features.append(min(atr / close * 100 / 5, 1.0))
        else:
            features.append(0.0)

        # 6. MACD 柱状线归一化 (-1 to 1)
        macd_hist = latest.get('macd_hist', 0)
        if not pd.isna(macd_hist) and atr > 0:
            features.append(np.clip(macd_hist / atr / 2, -1, 1))
        else:
            features.append(0.0)

        # 7. 成交量比率 (0 to 1)
        if 'volume' in df.columns and len(df) >= 20:
            vol_ma = df['volume'].iloc[-20:].mean()
            vol_now = latest['volume']
            if vol_ma > 0:
                features.append(min(vol_now / vol_ma / 3, 1.0))
            else:
                features.append(0.5)
        else:
            features.append(0.5)

        # 8. 连续方向 (-1 to 1)
        consec_up = self._consecutive_direction(df['close'], 'up')
        consec_down = self._consecutive_direction(df['close'], 'down')
        features.append(np.clip((consec_up - consec_down) / 10, -1, 1))

        return features

    def _detect_trend_phase(
        self,
        df: pd.DataFrame,
        latest,
        structure: MarketStructure,
        momentum: MomentumState,
        volatility: VolatilityState,
    ) -> TrendPhase:
        """
        检测趋势阶段（核心状态）

        六阶段模型：
        - CONSOLIDATING：横盘整理，无明确趋势
        - EMERGING：趋势萌芽，信号初现
        - DEVELOPING：趋势发展，信号确认
        - MATURE：趋势成熟，动能充沛
        - FATIGUING：趋势衰竭，动能减弱
        - REVERSING：趋势反转，方向改变
        """
        adx = latest.get('adx', 0)
        if pd.isna(adx):
            adx = 0

        # ADX 状态
        adx_state = "NEUTRAL"
        if adx > 30:
            adx_state = "HIGH"
        elif adx > 25:
            adx_state = "RISING"
        elif adx < 15:
            adx_state = "LOW"
        else:
            adx_state = "NEUTRAL"

        # 均线斜率状态
        slope_20 = structure.ma_slope_20
        slope_60 = structure.ma_slope_60
        ma_slope_state = "FLAT"
        if slope_20 > 0 and slope_60 > 0:
            ma_slope_state = "BOTH_UP"
        elif slope_20 < 0 and slope_60 < 0:
            ma_slope_state = "BOTH_DOWN"
        elif (slope_20 > 0 and slope_60 < 0) or (slope_20 < 0 and slope_60 > 0):
            ma_slope_state = "MIXED"

        # MACD 动量
        macd_momentum = "NEUTRAL"
        if momentum.macd_histogram_trend == "EXPANDING":
            macd_momentum = "EXPANDING"
        elif momentum.macd_histogram_trend == "CONTRACTING":
            macd_momentum = "CONTRACTING"
        if momentum.macd_state in ("BULLISH_CROSS", "BEARISH_CROSS"):
            macd_momentum = "CROSSING"

        # 成交量确认
        volume_confirmation = structure.volume_trend == "INCREASING"

        # 综合判断趋势阶段
        phase = "CONSOLIDATING"
        confidence = 0.5
        reasoning_parts = []

        # 阶段判断逻辑
        if adx < 15:
            # 低 ADX → 震荡
            phase = "CONSOLIDATING"
            confidence = 0.7
            reasoning_parts.append(f"ADX={adx:.1f}偏低，市场缺乏方向")
        elif adx > 30 and ma_slope_state in ("BOTH_UP", "BOTH_DOWN"):
            # 高 ADX + 均线同向 → 成熟或衰竭
            if macd_momentum == "EXPANDING":
                phase = "MATURE"
                confidence = 0.8
                reasoning_parts.append(f"ADX={adx:.1f}高位，均线同向，MACD动能扩张")
            elif macd_momentum == "CONTRACTING":
                phase = "FATIGUING"
                confidence = 0.7
                reasoning_parts.append(f"ADX={adx:.1f}高位，但MACD动能收缩，趋势可能衰竭")
            else:
                phase = "MATURE"
                confidence = 0.7
                reasoning_parts.append(f"ADX={adx:.1f}高位，均线同向，趋势成熟")
        elif adx > 25 and ma_slope_state in ("BOTH_UP", "BOTH_DOWN"):
            # 中高 ADX + 均线同向 → 发展
            phase = "DEVELOPING"
            confidence = 0.7
            reasoning_parts.append(f"ADX={adx:.1f}中高位，均线同向，趋势发展")
        elif adx > 20 and ma_slope_state == "MIXED":
            # 中等 ADX + 均线矛盾 → 萌芽或反转
            if momentum.macd_state in ("BULLISH", "BEARISH"):
                phase = "EMERGING"
                confidence = 0.6
                reasoning_parts.append(f"ADX={adx:.1f}中位，均线矛盾但MACD有方向，趋势萌芽")
            else:
                phase = "REVERSING"
                confidence = 0.5
                reasoning_parts.append(f"ADX={adx:.1f}中位，均线矛盾，趋势可能反转")
        elif adx > 20 and ma_slope_state == "FLAT":
            # 中等 ADX + 均线走平 → 震荡或萌芽
            if momentum.oscillator_resonance in ("BULLISH", "BEARISH"):
                phase = "EMERGING"
                confidence = 0.5
                reasoning_parts.append(f"ADX={adx:.1f}中位，均线走平但动量有方向，趋势萌芽")
            else:
                phase = "CONSOLIDATING"
                confidence = 0.6
                reasoning_parts.append(f"ADX={adx:.1f}中位，均线走平，市场震荡")
        else:
            # 其他情况
            phase = "CONSOLIDATING"
            confidence = 0.5
            reasoning_parts.append(f"ADX={adx:.1f}，市场方向不明确")

        # 补充判断依据
        if structure.swing_structure in ("HIGHER_HIGHS", "LOWER_LOWS"):
            reasoning_parts.append(f"高低点结构：{structure.swing_structure}")
        if volume_confirmation:
            reasoning_parts.append("成交量确认趋势")
        if momentum.oscillator_resonance != "NEUTRAL":
            reasoning_parts.append(f"振荡器共振：{momentum.oscillator_resonance}")

        return TrendPhase(
            phase=phase,
            confidence=confidence,
            reasoning="；".join(reasoning_parts),
            adx_state=adx_state,
            ma_slope_state=ma_slope_state,
            macd_momentum=macd_momentum,
            volume_confirmation=volume_confirmation,
        )
