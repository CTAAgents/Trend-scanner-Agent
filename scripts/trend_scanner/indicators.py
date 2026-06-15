"""
技术指标计算模块

提供35+个技术指标的计算，包括：
- 趋势指标：EMA, SMA, ADX, ADXR, +DI, -DI, ADX_Pct, ER, R², Hurst, ADX ROC
- 震荡指标：RSI, STOCH, STOCHRSI, Williams %R, CCI, Ultimate Oscillator
- 动量指标：MACD, ROC, Bull/Bear Power
- 波动率指标：ATR, Bollinger Bands
- 通道指标：Donchian Channel, Highs/Lows

支持 TA-Lib 加速（可选）和纯 pandas 实现。
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np

# 尝试导入TA-Lib
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


class IndicatorEngine:
    """技术指标计算引擎（纯pandas + 可选TA-Lib）"""

    def __init__(self, df: pd.DataFrame, ma_periods: Optional[Dict[str, int]] = None):
        self.df = df.copy()
        self.ma_periods = ma_periods or {'short': 20, 'medium': 60, 'long': 120}
        self._ensure_ohlcv()

    def _ensure_ohlcv(self):
        """标准化列名"""
        cols = self.df.columns.str.lower()
        rename_map = {}
        for c in self.df.columns:
            cl = c.lower()
            if cl in ['open', 'high', 'low', 'close', 'volume']:
                rename_map[c] = cl
        self.df.rename(columns=rename_map, inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col not in self.df.columns:
                raise ValueError(f"数据缺少必要列: {col}")

    def add_ema(self, period: int = 20, col_name: Optional[str] = None):
        col = col_name or f'ema{period}'
        if HAS_TALIB:
            self.df[col] = talib.EMA(self.df['close'].values, timeperiod=period)
        else:
            self.df[col] = self.df['close'].ewm(span=period, adjust=False).mean()
        return self

    def add_atr(self, period: int = 14):
        if HAS_TALIB:
            self.df['atr'] = talib.ATR(
                self.df['high'].values,
                self.df['low'].values,
                self.df['close'].values,
                timeperiod=period
            )
        else:
            high, low, close = self.df['high'], self.df['low'], self.df['close']
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            self.df['atr'] = tr.rolling(period).mean()  # SMA(14)，与文华一致
        return self

    def add_adx(self, period: int = 14, adx_period: int = 6):
        """
        计算 DMI 指标（+DI, -DI, ADX, ADXR）

        完全采用文华财经标准公式：
        TR  := SUM(MAX(MAX(HIGH-LOW, ABS(HIGH-REF(CLOSE,1))), ABS(LOW-REF(CLOSE,1))), N);
        HD  := HIGH - REF(HIGH, 1);
        LD  := REF(LOW, 1) - LOW;
        DMP := SUM(IFELSE(HD>0 && HD>LD, HD, 0), N);
        DMM := SUM(IFELSE(LD>0 && LD>HD, LD, 0), N);
        PDI := DMP * 100 / TR;
        MDI := DMM * 100 / TR;
        ADX := MA(ABS(MDI-PDI)/(MDI+PDI)*100, M);
        ADXR:= (ADX + REF(ADX, M)) / 2;

        参数:
            period: DI 计算周期 N（默认14）
            adx_period: ADX 平滑周期 M（默认6，文华标准）
        """
        high, low, close = self.df['high'], self.df['low'], self.df['close']

        # ---- 方向运动 HD, LD ----
        hd = high - high.shift(1)
        ld = low.shift(1) - low

        # ---- +DM, -DM（条件筛选） ----
        plus_dm = hd.where((hd > 0) & (hd > ld), 0)
        minus_dm = ld.where((ld > 0) & (ld > hd), 0)

        # ---- TR（真实波幅） ----
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr_raw = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ---- SUM 累加（文华标准，非 SMA 均值） ----
        tr_sum = tr_raw.rolling(period).sum()
        dmp_sum = plus_dm.rolling(period).sum()
        dmm_sum = minus_dm.rolling(period).sum()

        # ---- +DI, -DI ----
        plus_di = dmp_sum * 100 / tr_sum
        minus_di = dmm_sum * 100 / tr_sum

        # ---- DX ----
        di_sum = plus_di + minus_di
        dx = (minus_di - plus_di).abs() * 100 / di_sum

        # ---- ADX = MA(DX, M) ----
        self.df['adx'] = dx.rolling(adx_period).mean()

        # ---- ADXR = (ADX + REF(ADX, M)) / 2 ----
        self.df['adxr'] = (self.df['adx'] + self.df['adx'].shift(adx_period)) / 2

        self.df['plus_di'] = plus_di
        self.df['minus_di'] = minus_di
        return self

    def add_adx_pct(self, roll_window: Optional[int] = None, method: str = 'rank',
                    timeframe: str = 'auto', holding_period: str = 'medium'):
        """
        计算 ADX 滚动历史分位数（相对位置）

        核心逻辑：
        - 不用固定20/25/40绝对值
        - 对每根K线的ADX值，在滚动N周期历史ADX序列里算分位数
        - 取值0~1，0.65以上为有效趋势，0.85以上为极端强势

        窗口参数自动选择（无需手动配置）：
        - 根据交易周期级别自动选择默认窗口
        - 根据持仓周期微调
        - 处理新品种（K线不足）的回退逻辑

        参数:
            roll_window: 滚动回溯窗口（None=自动选择）
            method: 计算方法
                - 'rank': 滚动秩分位（工业首选，CTA标配）
                - 'zscore': Z-score标准化（平稳指数专用）
                - 'minmax': 滚动极值缩放（仅可视化）
                - 'ewma': 指数加权分位（短线自适应）
            timeframe: 数据周期（用于自动选择窗口）
                - 'auto': 自动检测（根据数据特征）
                - '1d': 日线
                - '1h': 1小时线
                - '4h': 4小时线
                - '30m': 30分钟线
                - '15m': 15分钟线
                - '5m': 5分钟线
            holding_period: 持仓周期（用于微调窗口）
                - 'long': 长线（数月）
                - 'medium': 中线（2-6周）
                - 'short': 短线（5-10天）
                - 'scalping': 日内（不建议使用分位）
        """
        if 'adx' not in self.df.columns:
            raise ValueError("必须先调用 add_adx() 计算 ADX")

        # ---- 自动检测数据周期 ----
        if timeframe == 'auto':
            timeframe = self._detect_timeframe()

        # ---- 根据周期和持仓选择默认窗口 ----
        if roll_window is None:
            roll_window = self._select_adx_window(timeframe, holding_period)

        # ---- 检查最小样本要求 ----
        min_samples = 40  # 分位数统计最少40根K线
        if len(self.df) < min_samples:
            print(f"警告: 数据量不足({len(self.df)}根)，分位数计算可能不稳定")

        # ---- 检查新品种回退逻辑 ----
        if len(self.df) < roll_window:
            # K线不足时，临时切回绝对值模式
            print(f"信息: 数据量({len(self.df)}根)不足滚动窗口({roll_window}根)，")
            print(f"       回退到ADX绝对值模式（ADX≥25为趋势，ADX<20为震荡）")
            # 直接使用ADX绝对值作为分位数的替代
            self.df['adx_pct'] = np.where(self.df['adx'] >= 25, 0.7,
                                          np.where(self.df['adx'] >= 20, 0.5, 0.3))
            self.df['adx_pct_level'] = pd.cut(
                self.df['adx_pct'],
                bins=[0, 0.3, 0.65, 0.85, 1.0],
                labels=['DEEP_RANGE', 'EMERGING', 'TRENDING', 'EXTREME']
            )
            return self

        adx = self.df['adx']

        if method == 'rank':
            # 方法1：滚动秩分位（最常用，CTA标配）
            self.df['adx_pct'] = adx.rolling(window=roll_window).rank(pct=True)

        elif method == 'zscore':
            # 方法2：Z-score标准化
            roll_mean = adx.rolling(window=roll_window).mean()
            roll_std = adx.rolling(window=roll_window).std()
            self.df['adx_pct'] = (adx - roll_mean) / roll_std
            self.df['adx_pct'] = 1 / (1 + np.exp(-self.df['adx_pct']))

        elif method == 'minmax':
            # 方法3：滚动极值Min-Max缩放（仅可视化）
            roll_min = adx.rolling(window=roll_window).min()
            roll_max = adx.rolling(window=roll_window).max()
            roll_range = roll_max - roll_min
            self.df['adx_pct'] = (adx - roll_min) / roll_range.replace(0, np.nan)

        elif method == 'ewma':
            # 方法4：指数加权EWMA动态分位
            ewma_rank = adx.ewm(span=roll_window, adjust=False).mean()
            ewma_std = adx.rolling(window=roll_window).std()
            z_score = (adx - ewma_rank) / ewma_std.replace(0, np.nan)
            self.df['adx_pct'] = 1 / (1 + np.exp(-z_score))

        else:
            raise ValueError(f"不支持的分位计算方法: {method}")

        # 标记分位数等级
        self.df['adx_pct_level'] = pd.cut(
            self.df['adx_pct'],
            bins=[0, 0.3, 0.65, 0.85, 1.0],
            labels=['DEEP_RANGE', 'EMERGING', 'TRENDING', 'EXTREME']
        )

        return self

    def _detect_timeframe(self) -> str:
        """自动检测数据周期"""
        if len(self.df) < 2:
            return '1d'  # 默认日线

        # 计算K线之间的时间间隔
        if 'date' in self.df.columns:
            try:
                dates = pd.to_datetime(self.df['date'])
                avg_interval = dates.diff().dt.total_seconds().mean()
            except:
                avg_interval = 86400  # 默认1天
        else:
            # 尝试从索引推断
            avg_interval = 86400  # 默认1天

        # 根据平均间隔判断周期
        if avg_interval >= 86400 * 0.8:  # 约1天
            return '1d'
        elif avg_interval >= 3600 * 3:  # 约3小时以上
            return '4h'
        elif avg_interval >= 3600 * 1.5:  # 约1.5-3小时
            return '2h'
        elif avg_interval >= 3600 * 0.8:  # 约1小时
            return '1h'
        elif avg_interval >= 1800 * 0.8:  # 约30分钟
            return '30m'
        elif avg_interval >= 900 * 0.8:  # 约15分钟
            return '15m'
        else:
            return '5m'

    def _select_adx_window(self, timeframe: str, holding_period: str) -> int:
        """
        根据周期级别和持仓周期选择默认窗口

        参考用户提供的标准化参数表：
        - 日线-长线：250根
        - 日线-中线：120根
        - 日线-短线：60根
        - 4H：60-80根
        - 2H：50-70根
        - 1H：45-60根
        - 15m/5m：不建议使用分位
        """
        # 基础窗口映射
        base_windows = {
            '1d': {'long': 250, 'medium': 120, 'short': 60},
            '4h': {'long': 80, 'medium': 60, 'short': 45},
            '2h': {'long': 70, 'medium': 50, 'short': 35},
            '1h': {'long': 60, 'medium': 45, 'short': 30},
            '30m': {'long': 45, 'medium': 30, 'short': 20},
            '15m': {'long': 30, 'medium': 20, 'short': 15},
            '5m': {'long': 20, 'medium': 15, 'short': 10},
        }

        # 获取基础窗口
        window = base_windows.get(timeframe, {}).get(holding_period, 120)

        # 波动率微调（简化版）
        if 'adx' in self.df.columns and len(self.df) >= 20:
            adx_recent = self.df['adx'].iloc[-20:].mean()
            if not pd.isna(adx_recent):
                # 高波动品种（ADX中枢高）：窗口向下微调
                if adx_recent > 30:
                    window = max(40, int(window * 0.85))
                # 低波动品种（ADX中枢低）：窗口向上微调
                elif adx_recent < 15:
                    window = min(250, int(window * 1.15))

        return window

    def add_donchian(self, period: int = 20):
        self.df['dc_upper'] = self.df['high'].rolling(period).max()
        self.df['dc_lower'] = self.df['low'].rolling(period).min()
        self.df['dc_middle'] = (self.df['dc_upper'] + self.df['dc_lower']) / 2
        return self

    def add_macd(self, fast: int = 12, slow: int = 26, signal: int = 9):
        if HAS_TALIB:
            macd, signal_line, hist = talib.MACD(
                self.df['close'].values,
                fastperiod=fast, slowperiod=slow, signalperiod=signal
            )
            self.df['macd'] = macd
            self.df['macd_signal'] = signal_line
            self.df['macd_hist'] = hist
        else:
            ema_fast = self.df['close'].ewm(span=fast, adjust=False).mean()
            ema_slow = self.df['close'].ewm(span=slow, adjust=False).mean()
            self.df['macd'] = ema_fast - ema_slow
            self.df['macd_signal'] = self.df['macd'].ewm(span=signal, adjust=False).mean()
            self.df['macd_hist'] = self.df['macd'] - self.df['macd_signal']
        return self

    def add_bollinger(self, period: int = 20, std_dev: float = 2.0):
        if HAS_TALIB:
            upper, middle, lower = talib.BBANDS(
                self.df['close'].values,
                timeperiod=period, nbdevup=std_dev, nbdevdn=std_dev
            )
            self.df['bb_upper'] = upper
            self.df['bb_middle'] = middle
            self.df['bb_lower'] = lower
        else:
            middle = self.df['close'].rolling(period).mean()
            std = self.df['close'].rolling(period).std()
            self.df['bb_upper'] = middle + std_dev * std
            self.df['bb_middle'] = middle
            self.df['bb_lower'] = middle - std_dev * std
        self.df['bb_width'] = (self.df['bb_upper'] - self.df['bb_lower']) / self.df['bb_middle']
        return self

    # ---- 新增指标 ----

    def add_rsi(self, period: int = 14):
        """
        RSI 相对强弱指标（Wilder's RSI）

        使用 Wilder's smoothing 方法，与文华财经、通达信一致。
        Wilder's smoothing 本质是 EMA，alpha = 1/period。

        与 SMA-RSI 的区别：
        - SMA-RSI：所有K线等权重，对近期和远期数据一视同仁
        - Wilder-RSI：近期数据权重更高，远期数据权重递减
        - 在趋势市中，Wilder-RSI 通常比 SMA-RSI 更平滑
        - 在转折点，Wilder-RSI 反应更快
        """
        # 数据不足时返回空值
        if len(self.df) < period + 2:
            self.df['rsi'] = np.nan
            return self

        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta.where(delta < 0, 0))

        # Wilder's smoothing: avg = (prev_avg * (period-1) + current) / period
        avg_gain = pd.Series(index=self.df.index, dtype=float)
        avg_loss = pd.Series(index=self.df.index, dtype=float)

        # 第一个值用 SMA 初始化
        avg_gain.iloc[period] = gain.iloc[1:period+1].mean()
        avg_loss.iloc[period] = loss.iloc[1:period+1].mean()

        # 后续值用 Wilder's smoothing
        for i in range(period + 1, len(self.df)):
            avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period-1) + gain.iloc[i]) / period
            avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period-1) + loss.iloc[i]) / period

        rs = avg_gain / avg_loss
        self.df['rsi'] = 100 - (100 / (1 + rs))
        return self

    def add_stoch(self, k_period: int = 9, d_period: int = 6):
        """STOCH 随机指标"""
        low_min = self.df['low'].rolling(k_period).min()
        high_max = self.df['high'].rolling(k_period).max()
        self.df['stoch_k'] = 100 * (self.df['close'] - low_min) / (high_max - low_min)
        self.df['stoch_d'] = self.df['stoch_k'].rolling(d_period).mean()
        return self

    def add_stochrsi(self, period: int = 14, smooth_k: int = 3, smooth_d: int = 3):
        """STOCHRSI 随机RSI（使用 Wilder's RSI）"""
        # 先确保 RSI 已计算
        if 'rsi' not in self.df.columns:
            self.add_rsi(period)

        rsi = self.df['rsi']
        rsi_min = rsi.rolling(period).min()
        rsi_max = rsi.rolling(period).max()
        stochrsi_k = 100 * (rsi - rsi_min) / (rsi_max - rsi_min)
        self.df['stochrsi_k'] = stochrsi_k.rolling(smooth_k).mean()
        self.df['stochrsi_d'] = self.df['stochrsi_k'].rolling(smooth_d).mean()
        return self

    def add_williams_r(self, period: int = 14):
        """Williams %R 威廉指标"""
        high_max = self.df['high'].rolling(period).max()
        low_min = self.df['low'].rolling(period).min()
        self.df['williams_r'] = -100 * (high_max - self.df['close']) / (high_max - low_min)
        return self

    def add_cci(self, period: int = 14):
        """CCI 商品通道指数"""
        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        tp_sma = tp.rolling(period).mean()
        tp_mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        self.df['cci'] = (tp - tp_sma) / (0.015 * tp_mad)
        return self

    def add_highs_lows(self, period: int = 14):
        """Highs/Lows 新高/新低指标"""
        highest = self.df['high'].rolling(period).max()
        lowest = self.df['low'].rolling(period).min()
        self.df['highs_lows'] = highest - lowest
        return self

    def add_ultimate_oscillator(self):
        """Ultimate Oscillator 终极震荡指标"""
        close_prev = self.df['close'].shift(1)
        tr1 = self.df['high'] - self.df['low']
        tr2 = (self.df['high'] - close_prev).abs()
        tr3 = (self.df['low'] - close_prev).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        bp = self.df['close'] - pd.concat([self.df['low'], close_prev], axis=1).min(axis=1)

        avg7 = bp.rolling(7).sum() / tr.rolling(7).sum()
        avg14 = bp.rolling(14).sum() / tr.rolling(14).sum()
        avg28 = bp.rolling(28).sum() / tr.rolling(28).sum()

        self.df['ultimate_osc'] = 100 * (4 * avg7 + 2 * avg14 + avg28) / 7
        return self

    def add_roc(self, period: int = 10):
        """ROC 变动率指标"""
        self.df['roc'] = (self.df['close'] - self.df['close'].shift(period)) / self.df['close'].shift(period) * 100
        return self

    def add_bull_bear_power(self, period: int = 13):
        """Bull/Bear Power 牛熊力量"""
        ema = self.df['close'].ewm(span=period, adjust=False).mean()
        self.df['bull_power'] = self.df['high'] - ema
        self.df['bear_power'] = self.df['low'] - ema
        return self

    def add_sma(self, period: int, col_name: Optional[str] = None):
        """SMA 简单移动平均"""
        col = col_name or f'sma{period}'
        self.df[col] = self.df['close'].rolling(period).mean()
        return self

    def add_ma_slope(self, col_name: str, lookback: int = 5):
        """
        计算均线斜率（百分比变化）

        核心理念：均线不仅要考虑排列，还要考虑走势
        - EMA20 > EMA60 但两者都在下降 → 空头趋势（伪多头排列）
        - EMA20 < EMA60 但两者都在上升 → 多头趋势（伪空头排列）

        参数:
            col_name: 均线列名（如 'ema20', 'ema60'）
            lookback: 回溯周期（默认5根K线）
        """
        if col_name not in self.df.columns:
            raise ValueError(f"列 {col_name} 不存在，请先计算均线")

        ma = self.df[col_name]
        ma_prev = ma.shift(lookback)

        # 斜率 = (当前值 - N周期前值) / N周期前值 * 100
        slope_col = f'{col_name}_slope'
        self.df[slope_col] = (ma - ma_prev) / ma_prev.abs().replace(0, np.nan) * 100

        return self

    def add_ma_spread(self, fast_col: str = 'ema20', slow_col: str = 'ema60', lookback: int = 5):
        """
        计算均线间距及其变化率

        核心理念：均线间距的变化方向比绝对值更重要
        - 间距在扩大 → 趋势在加强
        - 间距在缩小 → 趋势在减弱（可能即将反转）

        参数:
            fast_col: 快速均线列名
            slow_col: 慢速均线列名
            lookback: 回溯周期（默认5根K线）
        """
        if fast_col not in self.df.columns or slow_col not in self.df.columns:
            raise ValueError(f"列 {fast_col} 或 {slow_col} 不存在，请先计算均线")

        fast = self.df[fast_col]
        slow = self.df[slow_col]

        # 均线间距（百分比）
        spread_col = f'spread_{fast_col}_{slow_col}'
        self.df[spread_col] = (fast - slow) / slow.abs().replace(0, np.nan) * 100

        # 间距变化率
        spread_change_col = f'{spread_col}_change'
        spread_prev = self.df[spread_col].shift(lookback)
        self.df[spread_change_col] = self.df[spread_col] - spread_prev

        return self

    def add_ma_trend_direction(self, fast_col: str = 'ema20', slow_col: str = 'ema60',
                                slope_lookback: int = 5, spread_lookback: int = 5):
        """
        综合判断均线趋势方向（考虑排列+走势+价格位置）

        核心逻辑：
        1. 排列方向：fast > slow → 多头排列，fast < slow → 空头排列
        2. 走势方向：两条均线的斜率方向
        3. 价格位置：价格相对于均线的位置（新增）
        4. 综合判断：
           - 真多头：多头排列 + 两条均线都上升 + 价格在均线上方
           - 伪多头：多头排列 + 两条均线都下降 + 价格在均线下方
           - 弱多头/空头：混合信号

        参数:
            fast_col: 快速均线列名
            slow_col: 慢速均线列名
            slope_lookback: 斜率回溯周期
            spread_lookback: 间距变化回溯周期
        """
        # 先确保斜率和间距已计算
        if f'{fast_col}_slope' not in self.df.columns:
            self.add_ma_slope(fast_col, slope_lookback)
        if f'{slow_col}_slope' not in self.df.columns:
            self.add_ma_slope(slow_col, slope_lookback)
        if f'spread_{fast_col}_{slow_col}' not in self.df.columns:
            self.add_ma_spread(fast_col, slow_col, spread_lookback)

        close = self.df['close']
        fast = self.df[fast_col]
        slow = self.df[slow_col]
        fast_slope = self.df[f'{fast_col}_slope']
        slow_slope = self.df[f'{slow_col}_slope']
        spread_change = self.df[f'spread_{fast_col}_{slow_col}_change']

        # ---- 价格位置分析（新增）----
        # 价格相对于快速均线的位置
        price_vs_fast = (close - fast) / fast.abs().replace(0, np.nan) * 100
        # 价格相对于慢速均线的位置
        price_vs_slow = (close - slow) / slow.abs().replace(0, np.nan) * 100

        # 价格位置分类
        # 上方：价格 > 均线 且偏离 > 0.5%
        # 下方：价格 < 均线 且偏离 > 0.5%
        # 附近：偏离 ≤ 0.5%
        price_above_fast = price_vs_fast > 0.5
        price_below_fast = price_vs_fast < -0.5

        price_above_slow = price_vs_slow > 0.5
        price_below_slow = price_vs_slow < -0.5

        # 综合判断（加入价格位置）
        conditions = [
            # 真多头：多头排列 + 两条均线都上升 + 价格在均线上方
            (fast > slow) & (fast_slope > 0) & (slow_slope > 0) & price_above_fast,
            # 伪多头：多头排列 + 两条均线都下降 + 价格在均线下方
            (fast > slow) & (fast_slope < 0) & (slow_slope < 0) & price_below_fast,
            # 弱多头：多头排列 + 一升一降，或价格在均线附近
            (fast > slow) & ((fast_slope > 0) ^ (slow_slope > 0)),
            # 真空头：空头排列 + 两条均线都下降 + 价格在均线下方
            (fast < slow) & (fast_slope < 0) & (slow_slope < 0) & price_below_fast,
            # 伪空头：空头排列 + 两条均线都上升 + 价格在均线上方
            (fast < slow) & (fast_slope > 0) & (slow_slope > 0) & price_above_fast,
            # 弱空头：空头排列 + 一升一降
            (fast < slow) & ((fast_slope > 0) ^ (slow_slope > 0)),
        ]
        choices = ['STRONG_BULLISH', 'FALSE_BULLISH', 'WEAK_BULLISH',
                   'STRONG_BEARISH', 'FALSE_BEARISH', 'WEAK_BEARISH']

        self.df['ma_trend_direction'] = np.select(conditions, choices, default='NEUTRAL')

        # 趋势强度评分（0-100）
        slope_score = (fast_slope.abs() + slow_slope.abs()) / 2 * 10
        spread_score = spread_change.abs() * 20
        # 价格位置加成：价格远离均线时趋势更强
        price_position_score = (price_vs_fast.abs() + price_vs_slow.abs()) / 2 * 2
        self.df['ma_trend_strength'] = (slope_score + spread_score + price_position_score).clip(0, 100)

        # 价格位置指标（供其他模块使用）
        self.df['price_vs_ema20'] = price_vs_fast
        self.df['price_vs_ema60'] = price_vs_slow

        return self

    def compute_all(self) -> pd.DataFrame:
        p = self.ma_periods
        (self
         # 均线（EMA20/60 用于趋势信号，SMA 用于多周期参考）
         .add_ema(p['short'], 'ema20')
         .add_ema(p['medium'], 'ema60')
         .add_sma(5, 'sma5')
         .add_sma(10, 'sma10')
         .add_sma(20, 'sma20')
         .add_sma(60, 'sma60')
         .add_sma(100, 'sma100')
         # 均线斜率和趋势方向（3根K线回溯，更敏感）
         .add_ma_slope('ema20', 3)
         .add_ma_slope('ema60', 3)
         .add_ma_spread('ema20', 'ema60', 3)
         .add_ma_trend_direction('ema20', 'ema60', 3, 3)
         # 趋势指标
         .add_atr(14)
         .add_adx(14)
         .add_adx_pct(120)  # ADX 滚动历史分位数
         .add_donchian(20)
         .add_macd(12, 26, 9)
         .add_bollinger(20, 2)
         .add_cci(14)
         .add_highs_lows(14)
         # 震荡指标
         .add_rsi(14)
         .add_stoch(9, 6)
         .add_stochrsi(14)
         .add_williams_r(14)
         .add_ultimate_oscillator()
         .add_roc(10)
         .add_bull_bear_power(13)
         # 高低点结构分析（趋势确认，40根K线回溯）
         .add_swing_structure(40)
         # 七维趋势强度指标（替代 ADX 单一指标）
         .add_efficiency_ratio(20)
         .add_r_squared(20)
         .add_hurst_exponent(50)
         .add_adx_roc(5)
         .add_ema_slope_strength('ema20', 'atr')
         .add_tsi(25, 13)
         .add_atr_ratio(6, 24))
        return self.df

    def add_swing_structure(self, lookback: int = 40):
        """
        高低点结构分析（趋势跟踪核心确认方法）

        核心理念（来自趋势跟踪大师）：
        - 上升趋势 = 高点依次抬高 + 低点依次抬高
        - 下降趋势 = 高点依次降低 + 低点依次降低
        - 横盘 = 高低点无序

        这是最原始、最可靠的趋势确认方法，比任何指标都更直接。

        改进：
        - 使用2根K线窗口识别摆动点（平衡灵敏度和稳定性）
        - lookback=40根K线（约2个月），确保有足够摆动点
        - 只分析lookback周期内的摆动点

        参数:
            lookback: 回溯周期（默认40根K线）
        """
        if len(self.df) < lookback:
            self.df['swing_higher_highs'] = 0
            self.df['swing_higher_lows'] = 0
            self.df['swing_lower_highs'] = 0
            self.df['swing_lower_lows'] = 0
            self.df['swing_structure'] = 'NEUTRAL'
            return self

        high = self.df['high']
        low = self.df['low']

        # 使用2根K线窗口识别摆动点
        window = 2
        swing_highs = []
        swing_lows = []

        # 只在lookback范围内识别摆动点
        start = max(window, len(self.df) - lookback)
        end = len(self.df) - window

        for i in range(start, end):
            # 摆动高点：比左右window根K线都高
            is_high = True
            for j in range(1, window + 1):
                if high.iloc[i] <= high.iloc[i-j] or high.iloc[i] <= high.iloc[i+j]:
                    is_high = False
                    break
            if is_high:
                swing_highs.append((i, high.iloc[i]))

            # 摆动低点：比左右window根K线都低
            is_low = True
            for j in range(1, window + 1):
                if low.iloc[i] >= low.iloc[i-j] or low.iloc[i] >= low.iloc[i+j]:
                    is_low = False
                    break
            if is_low:
                swing_lows.append((i, low.iloc[i]))

        # 分析最近的高低点结构（取最近3个）
        recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows

        # 判断高点是否依次抬高
        higher_highs = 0
        lower_highs = 0
        if len(recent_highs) >= 2:
            for i in range(1, len(recent_highs)):
                if recent_highs[i][1] > recent_highs[i-1][1]:
                    higher_highs += 1
                elif recent_highs[i][1] < recent_highs[i-1][1]:
                    lower_highs += 1

        # 判断低点是否依次抬高
        higher_lows = 0
        lower_lows = 0
        if len(recent_lows) >= 2:
            for i in range(1, len(recent_lows)):
                if recent_lows[i][1] > recent_lows[i-1][1]:
                    higher_lows += 1
                elif recent_lows[i][1] < recent_lows[i-1][1]:
                    lower_lows += 1

        # 写入最后一行的值
        self.df['swing_higher_highs'] = higher_highs
        self.df['swing_higher_lows'] = higher_lows
        self.df['swing_lower_highs'] = lower_highs
        self.df['swing_lower_lows'] = lower_lows

        # 综合判断结构
        if higher_highs > 0 and higher_lows > 0 and lower_highs == 0 and lower_lows == 0:
            structure = 'BULLISH'  # 高点抬高 + 低点抬高 = 上升趋势
        elif lower_highs > 0 and lower_lows > 0 and higher_highs == 0 and higher_lows == 0:
            structure = 'BEARISH'  # 高点降低 + 低点降低 = 下降趋势
        elif higher_highs > 0 and lower_lows > 0:
            structure = 'EXPANDING'  # 高点抬高 + 低点降低 = 扩张（波动加大）
        elif lower_highs > 0 and higher_lows > 0:
            structure = 'CONTRACTING'  # 高点降低 + 低点抬高 = 收敛（三角形）
        else:
            structure = 'NEUTRAL'

        self.df['swing_structure'] = structure

        return self

    # ================================================================
    # 四维趋势强度指标（替代 ADX 单一指标）
    # ================================================================

    def add_efficiency_ratio(self, period: int = 20):
        """
        效率比（Efficiency Ratio）

        ER = |Close[N] - Close[0]| / Σ|Close[i] - Close[i-1]|

        范围：[0, 1]
        - ER→1：每单位波动都是有效方向运动（强趋势）
        - ER→0：波动被抵消（震荡）

        优势：无平滑，即期反应，对反转敏感
        """
        close = self.df['close']
        direction = (close - close.shift(period)).abs()
        volatility = close.diff().abs().rolling(period).sum()
        self.df['er'] = (direction / volatility.replace(0, np.nan)).fillna(0)
        return self

    def add_r_squared(self, period: int = 20):
        """
        趋势拟合度（R² of Linear Regression）

        对近 N 根 K 线的收盘价做线性回归，取 R²

        范围：[0, 1]
        - R²→1：价格紧密跟随趋势线（趋势清晰）
        - R²→0：价格远离趋势线（震荡或反转）

        优势：不依赖方向（上涨/下跌均可拟合），对反转敏感
        """
        close = self.df['close']
        r2_values = np.full(len(close), np.nan)

        for i in range(period - 1, len(close)):
            y = close.iloc[i - period + 1:i + 1].values
            x = np.arange(period, dtype=float)
            # 线性回归
            slope, intercept = np.polyfit(x, y, 1)
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            if ss_tot > 0:
                r2_values[i] = 1 - ss_res / ss_tot
            else:
                r2_values[i] = 0.0

        self.df['r_squared'] = r2_values
        return self

    def add_hurst_exponent(self, period: int = 50):
        """
        Hurst 指数（R/S 分析法）

        H > 0.5：趋势性（持续性）
        H < 0.5：均值回归（反持续性）
        H ≈ 0.5：随机游走

        使用简化 R/S 方法计算：
        1. 将窗口内收益率分为若干子序列
        2. 计算每个子序列的 R/S 值
        3. 对 log(R/S) vs log(n) 做线性回归，斜率即 H
        """
        close = self.df['close']
        returns = close.pct_change()
        hurst_values = np.full(len(close), np.nan)

        # 子序列长度列表
        sub_periods = [period // 4, period // 3, period // 2, period]

        for i in range(period - 1, len(close)):
            window = returns.iloc[i - period + 1:i + 1].values
            window = window[~np.isnan(window)]
            if len(window) < period // 2:
                continue

            rs_values = []
            ns = []
            for n in sub_periods:
                if n > len(window) or n < 4:
                    continue
                # 将窗口分为 len(window)//n 个子序列
                num_chunks = len(window) // n
                if num_chunks < 1:
                    continue
                rs_list = []
                for c in range(num_chunks):
                    chunk = window[c * n:(c + 1) * n]
                    mean_c = np.mean(chunk)
                    cumdev = np.cumsum(chunk - mean_c)
                    r = np.max(cumdev) - np.min(cumdev)
                    s = np.std(chunk, ddof=1) if np.std(chunk, ddof=1) > 0 else 1e-10
                    rs_list.append(r / s)
                if rs_list:
                    rs_values.append(np.mean(rs_list))
                    ns.append(n)

            if len(rs_values) >= 2:
                log_ns = np.log(ns)
                log_rs = np.log(rs_values)
                slope, _ = np.polyfit(log_ns, log_rs, 1)
                hurst_values[i] = np.clip(slope, 0, 1)

        self.df['hurst'] = hurst_values
        return self

    def add_adx_roc(self, period: int = 5):
        """
        ADX 变化率（Rate of Change）

        ROC = (ADX[t] - ADX[t-N]) / N

        范围：无界
        - 正值：ADX 上升（趋势增强）
        - 负值：ADX 下降（趋势衰减）

        优势：保留 ADX 信息，降低滞后
        """
        if 'adx' not in self.df.columns:
            raise ValueError("必须先调用 add_adx() 计算 ADX")

        self.df['adx_roc'] = (self.df['adx'] - self.df['adx'].shift(period)) / period
        return self

    def add_ema_slope_strength(self, ema_col: str = 'ema20', atr_col: str = 'atr'):
        """
        EMA 斜率强度（Slope Strength）

        公式：(EMA[t] - EMA[t-1]) / ATR

        用 ATR 归一化斜率，消除波动率影响：
        - > 0.3：强多头趋势（角度陡、推进稳）
        - 0.1 ~ 0.3：弱多头
        - -0.1 ~ 0.1：震荡（无趋势）
        - < -0.3：强空头

        优势：斜率先于 ADX 拐头，提前 3-5 根 K 线
        """
        if ema_col not in self.df.columns:
            raise ValueError(f"必须先计算 {ema_col}")
        if atr_col not in self.df.columns:
            raise ValueError(f"必须先计算 {atr_col}")

        slope = self.df[ema_col] - self.df[ema_col].shift(1)
        atr = self.df[atr_col].replace(0, np.nan)
        self.df['ema_slope_strength'] = (slope / atr).fillna(0)
        return self

    def add_tsi(self, long_period: int = 25, short_period: int = 13):
        """
        True Strength Index (TSI) —— 双平滑动量

        公式：
        Momentum = Close - Close[1]
        DoubleSmoothed = EMA(EMA(Momentum, long), short)
        TSI = DoubleSmoothed / EMA(ABS(Momentum), long) * 100

        范围：[-100, 100]
        - TSI > 20：强多头
        - TSI < -20：强空头
        - ±10 内：震荡

        优势：
        - 双平滑去噪，比 MACD 灵敏、比 RSI 稳定
        - 背离是反转最强信号（价格新高+TSI不新高=顶背离）
        - 比 ADX 快 2-3 根 K 线，反转误判少一半
        """
        close = self.df['close']
        mom = close - close.shift(1)

        # 双平滑动量
        double_smoothed = mom.ewm(span=long_period, adjust=False).mean() \
            .ewm(span=short_period, adjust=False).mean()

        # 双平滑绝对动量
        abs_smoothed = mom.abs().ewm(span=long_period, adjust=False).mean()

        self.df['tsi'] = (double_smoothed / abs_smoothed.replace(0, np.nan) * 100).fillna(0)
        return self

    def add_atr_ratio(self, short_period: int = 6, long_period: int = 24):
        """
        ATR 比率（ATR Ratio）—— 波动率扩张度量

        公式：ATR(short) / ATR(long)

        范围：[0, +∞)
        - > 1.5：波动率扩张 → 强趋势（启动/加速）
        - 0.8 ~ 1.5：震荡
        - < 0.5：波动率极致收缩 → 突破前夜

        优势：
        - 趋势启动比 ADX 早 5-8 根 K 线
        - 波动率收缩→扩张是趋势启动最早信号
        - 趋势末期 ATR 比率先降，提前预警顶部
        """
        high, low, close = self.df['high'], self.df['low'], self.df['close']

        # 计算 TR
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr_short = tr.rolling(short_period).mean()
        atr_long = tr.rolling(long_period).mean()

        self.df['atr_ratio'] = (atr_short / atr_long.replace(0, np.nan)).fillna(1.0)
        return self

    def get_trend_strength_composite(self, weights: Optional[Dict[str, float]] = None) -> pd.Series:
        """
        七维复合趋势强度评分

        核心组合（用户推荐）：TSI（动量强度）+ ER（趋势纯度）
        辅助组合：EMA 斜率（推进效率）+ ATR 比率（波动率扩张）+ R² + Hurst + ADX ROC

        初始权重（冷启动默认值，LLM 推理层可动态调整）：
        - tsi: 25%（动量净强度，反转最准，背离清晰）
        - er: 25%（趋势纯度，无滞后，路径效率）
        - ema_slope: 15%（推进效率，斜率先拐，提前 3-5K）
        - atr_ratio: 10%（波动率扩张，启动最早，提前 5-8K）
        - r2: 10%（趋势拟合度，反转敏感）
        - hurst: 8%（机制状态，趋势 vs 震荡）
        - adx_roc: 7%（保留 ADX 信息，动量加速）

        参数:
            weights: 自定义权重字典

        返回:
            pd.Series: 复合评分 [0, 1]
        """
        default_weights = {
            'tsi': 0.25, 'er': 0.25, 'ema_slope': 0.15,
            'atr_ratio': 0.10, 'r2': 0.10, 'hurst': 0.08, 'adx_roc': 0.07
        }
        w = weights or default_weights

        # === 归一化各指标到 [0, 1] ===

        # TSI: sigmoid 映射 [-100, 100] → [0, 1]
        tsi = self.df.get('tsi', pd.Series(0, index=self.df.index))
        tsi_norm = 1 / (1 + np.exp(-tsi / 20))

        # ER: 已经是 [0, 1]
        er = self.df.get('er', pd.Series(0, index=self.df.index))

        # EMA 斜率强度: sigmoid 映射
        ema_slope = self.df.get('ema_slope_strength', pd.Series(0, index=self.df.index))
        ema_slope_norm = 1 / (1 + np.exp(-ema_slope * 3))

        # ATR 比率: 映射 [0.5, 2.0] → [0, 1]
        atr_ratio = self.df.get('atr_ratio', pd.Series(1.0, index=self.df.index))
        atr_ratio_norm = ((atr_ratio - 0.5) / 1.5).clip(0, 1)

        # R²: 已经是 [0, 1]
        r2 = self.df.get('r_squared', pd.Series(0, index=self.df.index))

        # Hurst: 已经是 [0, 1]
        hurst = self.df.get('hurst', pd.Series(0.5, index=self.df.index))

        # ADX ROC: sigmoid 映射
        adx_roc = self.df.get('adx_roc', pd.Series(0, index=self.df.index))
        adx_roc_norm = 1 / (1 + np.exp(-adx_roc * 2))

        # === 加权求和 ===
        composite = (
            w.get('tsi', 0) * tsi_norm.fillna(0.5) +
            w.get('er', 0) * er.fillna(0) +
            w.get('ema_slope', 0) * ema_slope_norm.fillna(0.5) +
            w.get('atr_ratio', 0) * atr_ratio_norm.fillna(0.5) +
            w.get('r2', 0) * r2.fillna(0) +
            w.get('hurst', 0) * hurst.fillna(0.5) +
            w.get('adx_roc', 0) * adx_roc_norm.fillna(0.5)
        )

        return composite.clip(0, 1)


# ===========================================================================
# 多指标综合判断系统（容错架构）
