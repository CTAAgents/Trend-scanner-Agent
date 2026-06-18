"""
市场分析模块

提供市场状态判断、趋势阶段识别等功能：
- MultiIndicatorConsensus: 多指标共识系统
- TrendPhaseDetector: 趋势阶段识别器
- MarketStateClassifier: 市场状态分类器
"""

import numpy as np
import pandas as pd


# ============================================================
# 集中配置：所有阈值、权重、参数在此定义，避免重复
# ============================================================
class Config:
    """趋势跟踪系统配置（单一来源）"""

    # ---- 打分权重（2026-06-15 修正：符合策略自进化约束）----
    # 约束条件：
    # 1. 波动率权重 ≤ 15%（市场状态辅助，非独立方向信号）
    # 2. 领先信号权重 ≤ 10%（早期信号容易产生噪音）
    # 3. 趋势强度权重 ≤ 10%（ADX只是辅助，不区分方向）
    # 4. 趋势确认 + 动量健康 ≥ 70%（核心维度）
    DIMENSION_WEIGHTS = {
        "leading_signals": 0.10,  # 领先信号（EMA交叉、通道突破）≤10%
        "trend_confirmation": 0.45,  # 趋势确认（均线排列、高低点结构）核心
        "momentum_health": 0.30,  # 动量健康（RSI、STOCH、CCI）核心
        "volatility": 0.10,  # 波动率（ATR、布林带宽度）≤15%辅助
        "trend_strength": 0.05,  # 趋势强度（ADX）≤10%辅助
    }

    # 维度描述
    DIMENSION_DESCRIPTIONS = {
        "leading_signals": "领先信号（EMA交叉、通道突破）",
        "trend_confirmation": "趋势确认（均线排列、高低点结构）",
        "momentum_health": "动量健康（RSI、STOCH、CCI）",
        "volatility": "波动率（ATR、布林带宽度）",
        "trend_strength": "趋势强度（ADX）",
    }

    # ---- 超买超卖阈值 ----
    RSI_OVERBOUGHT_STRONG = 80  # RSI严重超买
    RSI_OVERBOUGHT = 70  # RSI超买
    RSI_OVERSOLD_STRONG = 20  # RSI严重超卖
    RSI_OVERSOLD = 30  # RSI超卖
    STOCH_OVERBOUGHT = 90  # STOCH严重超买
    STOCH_OVERSOLD = 10  # STOCH严重超卖
    CCI_OVERBOUGHT = 200  # CCI严重超买
    CCI_OVERSOLD = -200  # CCI严重超卖

    # ---- 趋势强度阈值 ----
    ADX_STRONG_TREND = 25  # ADX强趋势
    ADX_WEAK_TREND = 20  # ADX弱趋势
    ADX_NO_TREND = 15  # ADX无趋势

    # ---- 动量强度阈值 ----
    RSI_MOMENTUM_BULLISH = 55  # RSI多头动量阈值
    RSI_MOMENTUM_BEARISH = 45  # RSI空头动量阈值
    RSI_MOMENTUM_STRONG = 20  # RSI距50的强动量偏离
    STOCH_MOMENTUM_BULLISH = 55  # STOCH多头动量阈值
    STOCH_MOMENTUM_BEARISH = 45  # STOCH空头动量阈值
    CCI_MOMENTUM_BULLISH = 50  # CCI多头动量阈值
    CCI_MOMENTUM_BEARISH = -50  # CCI空头动量阈值
    OSCILLATOR_RESONANCE = 3  # 振荡器共振数量阈值

    # ---- 动量分段映射 ----
    RSI_SEGMENTS = [
        (80, 0.8),  # RSI > 80: 强势
        (70, 0.4),  # RSI > 70: 偏强
        (60, 0.2),  # RSI > 60: 略偏强
        (40, 0.0),  # RSI > 40: 中性
        (30, -0.2),  # RSI > 30: 略偏弱
        (20, -0.4),  # RSI > 20: 偏弱
        (0, -0.8),  # RSI <= 20: 弱势
    ]
    STOCH_SEGMENTS = [
        (80, 0.6),
        (60, 0.2),
        (40, 0.0),
        (20, -0.2),
        (0, -0.6),
    ]
    CCI_SEGMENTS = [
        (200, 0.8),
        (100, 0.4),
        (-100, 0.0),
        (-200, -0.4),
        (-999, -0.8),
    ]

    # ---- 波动率阈值 ----
    ATR_HIGH_VOL = 3.0  # ATR高波动（百分比）
    ATR_MEDIUM_VOL = 2.0  # ATR中等波动
    ATR_LOW_VOL = 1.0  # ATR低波动
    BB_HIGH_VOL = 0.05  # 布林带宽高波动
    BB_LOW_VOL = 0.02  # 布林带宽低波动

    # ---- 价格位置阈值 ----
    PRICE_ABOVE_MA = 0.5  # 价格在均线上方（百分比）
    PRICE_BELOW_MA = -0.5  # 价格在均线下方（百分比）

    # ---- 打分方向阈值 ----
    SCORE_BULLISH = 0.15  # 综合得分 > 此值 → 偏多
    SCORE_BEARISH = -0.15  # 综合得分 < 此值 → 偏空

    # ---- 均线粘合检测 ----
    MA_CONSOLIDATION_THRESHOLD = 0.005  # EMA20/60差值 < 价格0.5% → 粘合状态
    MA_CONSOLIDATION_ARRANGEMENT_DECAY = 0.3  # 粘合时排列权重衰减至30%
    MA_CONSOLIDATION_TREND_BOOST = 1.5  # 粘合时走势权重提升至150%
    MA_CONSOLIDATION_ADX_MAX = 20  # ADX低于此值时才触发粘合检测

    # ---- 滚动分位数自适应阈值 ----
    ROLLING_PERCENTILE_WINDOW = 120  # 滚动窗口长度
    ROLLING_PERCENTILE_HIGH = 0.70  # 高分位
    ROLLING_PERCENTILE_LOW = 0.30  # 低分位

    # ---- 因子相关性阈值 ----
    FACTOR_CORRELATION_THRESHOLD = 0.85  # 因子合并阈值

    # ---- 双轨验证折扣参数 ----
    DUAL_CHECK_MAX_DISCOUNT = 0.7  # 最大折扣（最多打到30%）
    DUAL_CHECK_STRONG_SIGNAL = 2.5  # 强信号阈值（保留强信号）

    # ---- 冷启动与统计防护 ----
    COLD_START_BARS = 120  # 冷启动期（前120根K线不交易）
    REGIME_DRIFT_THRESHOLD = 0.50  # 体制漂移阈值（波动率均值漂移>50%）
    REGIME_DRIFT_RESET_WINDOW = 60  # 漂移重置后保留的K线数
    EXTREME_VALUE_THRESHOLD = 3.0  # 极端值阈值（连续多根>±3σ）
    EXTREME_VALUE_CONSECUTIVE = 3  # 连续极端值次数

    # ---- 动态权重与因子扩展 ----
    # 波动率状态权重切换
    VOL_REGIME_HIGH_PERCENTILE = 0.80  # 高波动分位数
    VOL_REGIME_LOW_PERCENTILE = 0.20  # 低波动分位数
    VOL_REGIME_WINDOW = 250  # 波动率分位数窗口

    # 高波动权重配置（2026-06-15 修正：符合策略自进化约束）
    # 约束：波动率≤15%，领先信号≤10%，趋势强度≤10%，趋势确认+动量健康≥70%
    WEIGHTS_HIGH_VOL = {
        "leading_signals": 0.10,  # ≤10%约束
        "trend_confirmation": 0.40,  # 核心维度
        "momentum_health": 0.35,  # 核心维度（高波动时动量更重要）
        "volatility": 0.10,  # ≤15%辅助
        "trend_strength": 0.05,  # ≤10%约束
    }

    # 低波动权重配置（2026-06-15 修正：符合策略自进化约束）
    # 约束：波动率≤15%，领先信号≤10%，趋势强度≤10%，趋势确认+动量健康≥70%
    WEIGHTS_LOW_VOL = {
        "leading_signals": 0.08,  # ≤10%约束
        "trend_confirmation": 0.50,  # 核心维度（低波动时趋势确认更重要）
        "momentum_health": 0.30,  # 核心维度
        "volatility": 0.07,  # ≤15%辅助
        "trend_strength": 0.05,  # ≤10%约束
    }

    # 维度历史胜率自适应
    WIN_RATE_SMOOTHING = 2  # 拉普拉斯平滑参数
    WIN_RATE_LOOKBACK = 50  # 胜率统计窗口

    # 权重边界（2026-06-15 修正：符合策略自进化约束）
    # 核心约束：
    # 1. 波动率 ≤ 15%
    # 2. 领先信号 ≤ 10%
    # 3. 趋势强度 ≤ 10%
    # 4. 趋势确认 + 动量健康 ≥ 70%
    WEIGHT_BOUNDS = {
        "leading_signals": (0.05, 0.10),  # 5%-10%（硬约束≤10%）
        "trend_confirmation": (0.35, 0.55),  # 35%-55%（核心维度）
        "momentum_health": (0.20, 0.45),  # 20%-45%（核心维度）
        "volatility": (0.03, 0.15),  # 3%-15%（硬约束≤15%）
        "trend_strength": (0.03, 0.10),  # 3%-10%（硬约束≤10%）
    }

    # 成交量因子
    VOLUME_OBV_SLOPE_WINDOW = 20  # OBV斜率窗口
    VOLUME_VR_WINDOW = 20  # 成交量相对强度窗口
    VOLUME_MFI_WINDOW = 14  # MFI窗口


class MultiIndicatorConsensus:
    """
    多指标共识系统 - 降低对单一指标依赖，提升容错能力

    设计原则：
    1. 多指标投票：20+指标独立判断，多数一致才确认
    2. 冲突检测：指标矛盾时降低信心
    3. 健康度检查：指标缺失或异常时自动降级
    4. 分层确认：趋势强度、方向、动量分别确认
    """

    # 指标分组
    TREND_INDICATORS = ["adx", "plus_di", "minus_di", "cci", "highs_lows", "macd"]
    MA_INDICATORS = ["ema20", "ema60", "sma5", "sma10", "sma20", "sma60", "sma100"]
    OSCILLATOR_INDICATORS = ["rsi", "stoch_k", "stoch_d", "williams_r", "ultimate_osc", "roc"]
    MOMENTUM_INDICATORS = ["macd", "macd_hist", "bull_power", "bear_power", "stochrsi_k"]

    @classmethod
    def _safe_val(cls, val, default=0):
        """安全获取值"""
        if isinstance(val, pd.Series):
            val = val.iloc[-1]
        if pd.isna(val):
            return default
        return float(val)

    @classmethod
    def check_indicator_health(cls, df: pd.DataFrame) -> dict:
        """检查指标健康度"""
        all_indicators = cls.TREND_INDICATORS + cls.MA_INDICATORS + cls.OSCILLATOR_INDICATORS + cls.MOMENTUM_INDICATORS

        available = []
        missing = []
        abnormal = []

        for ind in all_indicators:
            if ind in df.columns:
                val = df[ind].iloc[-1]
                if pd.isna(val):
                    abnormal.append(ind)
                else:
                    available.append(ind)
            else:
                missing.append(ind)

        health_score = len(available) / len(all_indicators) * 100

        return {
            "health_score": health_score,
            "available_count": len(available),
            "missing_count": len(missing),
            "abnormal_count": len(abnormal),
            "missing": missing,
            "abnormal": abnormal,
        }

    @classmethod
    def _vote_trend_strength(cls, df: pd.DataFrame) -> dict:
        """
        趋势强度投票（时序动量为核心）

        核心理念：趋势跟踪的本质是时序动量
        - 均线：度量动量的方向和强度
        - 通道：度量动量的突破和延续
        - ADX：仅作为参考性指标

        权重设计：
        - 均线排列+走势：4票（核心，度量动量方向和强度）
        - 通道位置+突破：3票（核心，度量动量突破和延续）
        - 布林带：1票（波动率确认）
        - ADX：0票（仅信息性，不参与投票）

        重要改进（v2.5）：
        - 不仅看均线排列，还要看均线走势
        - EMA20 > EMA60 但两者都在下降 → 伪多头，实际空头趋势
        - EMA20 < EMA60 但两者都在上升 → 伪空头，实际多头趋势
        """
        votes = {"strong": 0, "weak": 0, "none": 0}
        details = []
        close = cls._safe_val(df.get("close"))

        # ---- 核心指标1：均线动量（4票）----
        ema20 = cls._safe_val(df.get("ema20"))
        ema60 = cls._safe_val(df.get("ema60"))

        # 获取均线斜率和趋势方向（如果有）
        ema20_slope = cls._safe_val(df.get("ema20_slope"))
        ema60_slope = cls._safe_val(df.get("ema60_slope"))
        ma_trend_direction = df["ma_trend_direction"].iloc[-1] if "ma_trend_direction" in df.columns else "NEUTRAL"

        if ema20 > 0 and ema60 > 0:
            # 使用新的趋势方向判断
            if ma_trend_direction == "STRONG_BULLISH":
                # 真多头：多头排列 + 两条均线都上升
                votes["strong"] += 4
                details.append(f"真多头排列（EMA20斜率{ema20_slope:.2f}%，EMA60斜率{ema60_slope:.2f}%）→强(×4)")
            elif ma_trend_direction == "FALSE_BULLISH":
                # 伪多头：多头排列 + 两条均线都下降 → 实际空头趋势
                votes["weak"] += 2
                details.append(f"伪多头排列（EMA20>{ema60:.0f}但两者都在下降）→弱(×2)")
            elif ma_trend_direction == "WEAK_BULLISH":
                # 弱多头：多头排列 + 一升一降
                votes["weak"] += 3
                details.append("弱多头排列（一升一降）→弱(×3)")
            elif ma_trend_direction == "STRONG_BEARISH":
                # 真空头：空头排列 + 两条均线都下降
                votes["strong"] += 4
                details.append(f"真空头排列（EMA20斜率{ema20_slope:.2f}%，EMA60斜率{ema60_slope:.2f}%）→强(×4)")
            elif ma_trend_direction == "FALSE_BEARISH":
                # 伪空头：空头排列 + 两条均线都上升 → 实际多头趋势
                votes["weak"] += 2
                details.append(f"伪空头排列（EMA20<{ema60:.0f}但两者都在上升）→弱(×2)")
            elif ma_trend_direction == "WEAK_BEARISH":
                # 弱空头：空头排列 + 一升一降
                votes["weak"] += 3
                details.append("弱空头排列（一升一降）→弱(×3)")
            else:
                # 回退到原始逻辑（如果没有斜率数据）
                if ema20 > ema60:
                    # 多头排列
                    if ema20_slope > 1 and ema60_slope > 0:
                        votes["strong"] += 4
                        details.append(f"多头排列+短均线斜率{ema20_slope:.1f}%→强(×4)")
                    elif ema20_slope > 0:
                        votes["weak"] += 3
                        details.append("多头排列+斜率向上→弱(×3)")
                    else:
                        votes["weak"] += 2
                        details.append("多头排列+斜率走平→弱(×2)")
                if ema20 > ema60:
                    # 空头排列
                    if ema20_slope < -1 and ema60_slope < 0:
                        votes["strong"] += 4
                        details.append(f"空头排列+短均线斜率{ema20_slope:.1f}%→强(×4)")
                    elif ema20_slope < 0:
                        votes["weak"] += 3
                        details.append("空头排列+斜率向下→弱(×3)")
                    else:
                        votes["weak"] += 2
                        details.append("空头排列+斜率走平→弱(×2)")
                else:
                    votes["none"] += 1
                    details.append("均线交织→无")
        else:
            votes["none"] += 1
            details.append("均线数据不足")

        # ---- 核心指标2：通道动量（3票）----
        if "dc_upper" in df.columns and "dc_lower" in df.columns:
            dc_upper = cls._safe_val(df.get("dc_upper"))
            dc_lower = cls._safe_val(df.get("dc_lower"))
            if close > 0 and dc_upper > dc_lower:
                channel_pos = (close - dc_lower) / (dc_upper - dc_lower) * 100
                channel_width = (dc_upper - dc_lower) / close * 100

                # 价格在通道中的位置
                if channel_pos > 80:
                    votes["strong"] += 3
                    details.append(f"价格在通道上沿({channel_pos:.0f}%)→强(×3)")
                elif channel_pos > 60:
                    votes["weak"] += 2
                    details.append(f"价格在通道中上({channel_pos:.0f}%)→弱(×2)")
                elif channel_pos < 20:
                    votes["strong"] += 3
                    details.append(f"价格在通道下沿({channel_pos:.0f}%)→强(×3)")
                elif channel_pos < 40:
                    votes["weak"] += 2
                    details.append(f"价格在通道中下({channel_pos:.0f}%)→弱(×2)")
                else:
                    votes["none"] += 1
                    details.append(f"价格在通道中部({channel_pos:.0f}%)")

                # 通道宽度（波动率）
                if channel_width > 5:
                    details.append(f"通道宽{channel_width:.1f}%→高波动")
                elif channel_width < 2:
                    details.append(f"通道宽{channel_width:.1f}%→低波动")

        # ---- 确认指标：布林带（1票）----
        bb_width = cls._safe_val(df.get("bb_width"))
        if bb_width > 0.05:
            votes["strong"] += 1
            details.append(f"BB宽={bb_width:.3f}→高波动(×1)")
        elif bb_width > 0.02:
            votes["weak"] += 1
            details.append(f"BB宽={bb_width:.3f}→中波动(×1)")
        else:
            votes["none"] += 1
            details.append(f"BB宽={bb_width:.3f}→低波动")

        # ---- 四维趋势强度（2票，替代纯ADX）----
        # 初始权重：ER(40%) + R²(30%) + Hurst(15%) + ADX ROC(15%)
        er = cls._safe_val(df.get("er"))
        r2 = cls._safe_val(df.get("r_squared"))
        hurst = cls._safe_val(df.get("hurst"))
        adx_roc = cls._safe_val(df.get("adx_roc"))

        # 计算四维复合评分（加权平均）
        composite = 0.0
        valid_dims = 0

        if not pd.isna(er):
            composite += 0.4 * er
            valid_dims += 1
        if not pd.isna(r2):
            composite += 0.3 * r2
            valid_dims += 1
        if not pd.isna(hurst):
            # Hurst > 0.5 表示趋势性，映射到 [0, 1]
            hurst_score = max(0, (hurst - 0.5) * 2)  # [0.5, 1] → [0, 1]
            composite += 0.15 * hurst_score
            valid_dims += 1
        if not pd.isna(adx_roc):
            # ADX ROC 正值表示趋势增强，sigmoid 映射到 [0, 1]
            adx_roc_score = 1 / (1 + np.exp(-adx_roc * 2))
            composite += 0.15 * adx_roc_score
            valid_dims += 1

        if valid_dims >= 3:
            # 至少3个维度有效时才投票
            if composite >= 0.7:
                votes["strong"] += 2
                details.append(f"四维趋势强度={composite:.2f}→强趋势(×2)")
            elif composite >= 0.5:
                votes["strong"] += 1
                details.append(f"四维趋势强度={composite:.2f}→有效趋势(×1)")
            elif composite >= 0.3:
                votes["weak"] += 1
                details.append(f"四维趋势强度={composite:.2f}→趋势萌芽(×1)")
            else:
                votes["none"] += 1
                details.append(f"四维趋势强度={composite:.2f}→深度震荡")

            # 记录各维度详情
            details.append(f"[四维] ER={er:.2f}, R²={r2:.2f}, Hurst={hurst:.2f}, ADX ROC={adx_roc:.2f}")
        else:
            # 维度不足时，回退到 ADX 分位数
            adx_pct = cls._safe_val(df.get("adx_pct"))
            adx = cls._safe_val(df.get("adx"))
            if not pd.isna(adx_pct):
                if adx_pct >= 0.85:
                    votes["strong"] += 2
                    details.append(f"ADX分位{adx_pct:.0%}→极强趋势(×2)")
                elif adx_pct >= 0.65:
                    votes["strong"] += 1
                    details.append(f"ADX分位{adx_pct:.0%}→有效趋势(×1)")
                elif adx_pct >= 0.3:
                    votes["weak"] += 1
                    details.append(f"ADX分位{adx_pct:.0%}→趋势萌芽(×1)")
                else:
                    votes["none"] += 1
                    details.append(f"ADX分位{adx_pct:.0%}→深度震荡")
            details.append(f"[参考] ADX={adx:.1f}(四维数据不足，回退ADX)")

        return {"votes": votes, "details": details}

    @classmethod
    def _vote_trend_direction(cls, df: pd.DataFrame) -> dict:
        """
        趋势方向投票（领先指标优先 + 渐进确认）

        核心理念（来自交易员实战经验）：
        - 不要等待所有条件都满足才开单，行情大概率已经走了很远
        - 领先指标触发时就进场，确认指标用于调整仓位大小
        - 宁愿进场后止损，也不愿错过趋势的前30%

        信号分级：
        - 领先信号（立即进场）：EMA交叉、通道突破
        - 确认信号（调整仓位）：均线排列、高低点结构、MACD
        - 过滤信号（风险控制）：RSI超买超卖（只警告，不阻止方向判断）
        """
        votes = {"bullish": 0, "bearish": 0, "neutral": 0}
        details = []
        close = cls._safe_val(df.get("close"))

        # ---- 领先指标1：EMA交叉（+3票，最高优先级）----
        # EMA交叉是最及时的趋势启动信号
        ema20 = cls._safe_val(df.get("ema20"))
        ema60 = cls._safe_val(df.get("ema60"))

        if len(df) >= 5 and "ema20" in df.columns and "ema60" in df.columns:
            ema20_prev = df["ema20"].iloc[-5]
            ema60_prev = df["ema60"].iloc[-5]

            if not pd.isna(ema20_prev) and not pd.isna(ema60_prev):
                # 金叉：EMA20上穿EMA60
                if ema20_prev < ema60_prev and ema20 > ema60:
                    votes["bullish"] += 3
                    details.append("EMA20金叉EMA60→趋势启动(领先×3)")
                # 死叉：EMA20下穿EMA60
                elif ema20_prev > ema60_prev and ema20 < ema60:
                    votes["bearish"] += 3
                    details.append("EMA20死叉EMA60→趋势启动(领先×3)")

        # ---- 领先指标2：通道突破（+2票）----
        # 价格突破唐奇安通道是趋势延续的早期信号
        if "dc_upper" in df.columns and "dc_lower" in df.columns:
            dc_upper = cls._safe_val(df.get("dc_upper"))
            dc_lower = cls._safe_val(df.get("dc_lower"))
            if close > 0 and dc_upper > dc_lower:
                # 突破上轨
                if close > dc_upper * 0.98:
                    votes["bullish"] += 2
                    details.append("价格接近/突破通道上轨→趋势延续(领先×2)")
                # 突破下轨
                elif close < dc_lower * 1.02:
                    votes["bearish"] += 2
                    details.append("价格接近/跌破通道下轨→趋势延续(领先×2)")

        # ---- 确认指标1：均线排列+走势（+2票）----
        # 均线排列确认趋势方向，但滞后于交叉
        ema20_slope = cls._safe_val(df.get("ema20_slope"))
        ema60_slope = cls._safe_val(df.get("ema60_slope"))
        ma_trend_direction = df["ma_trend_direction"].iloc[-1] if "ma_trend_direction" in df.columns else "NEUTRAL"

        if ema20 > 0 and ema60 > 0:
            if ma_trend_direction == "STRONG_BULLISH":
                votes["bullish"] += 2
                details.append(f"真多头排列（斜率{ema20_slope:.2f}%）→多(确认×2)")
            elif ma_trend_direction == "FALSE_BULLISH":
                votes["bearish"] += 2
                details.append("伪多头排列（两者都在下降）→空(确认×2)")
            elif ma_trend_direction == "WEAK_BULLISH":
                votes["bullish"] += 1
                details.append("弱多头排列（一升一降）→弱多(确认×1)")
            elif ma_trend_direction == "STRONG_BEARISH":
                votes["bearish"] += 2
                details.append(f"真空头排列（斜率{ema20_slope:.2f}%）→空(确认×2)")
            elif ma_trend_direction == "FALSE_BEARISH":
                votes["bullish"] += 2
                details.append("伪空头排列（两者都在上升）→多(确认×2)")
            elif ma_trend_direction == "WEAK_BEARISH":
                votes["bearish"] += 1
                details.append("弱空头排列（一升一降）→弱空(确认×1)")
            else:
                if ema20 > ema60:
                    votes["bullish"] += 1
                    details.append("多头排列→多(确认×1)")
                elif ema20 < ema60:
                    votes["bearish"] += 1
                    details.append("空头排列→空(确认×1)")

        # ---- 确认指标2：高低点结构（+2票）----
        swing_structure = df["swing_structure"].iloc[-1] if "swing_structure" in df.columns else "NEUTRAL"
        if swing_structure == "BULLISH":
            votes["bullish"] += 2
            details.append("高低点结构:高点抬高+低点抬高→上升趋势(确认×2)")
        elif swing_structure == "BEARISH":
            votes["bearish"] += 2
            details.append("高低点结构:高点降低+低点降低→下降趋势(确认×2)")

        # ---- 确认指标3：MACD（+1票）----
        macd = cls._safe_val(df.get("macd"))
        macd_signal = cls._safe_val(df.get("macd_signal"))
        if macd > macd_signal:
            votes["bullish"] += 1
            details.append("MACD金叉→多(确认×1)")
        elif macd < macd_signal:
            votes["bearish"] += 1
            details.append("MACD死叉→空(确认×1)")

        # ---- 过滤信号：RSI（不投票，只警告）----
        # RSI超买超卖不是方向判断，是风险过滤
        rsi = cls._safe_val(df.get("rsi"))
        if rsi > Config.RSI_OVERBOUGHT:
            details.append(f"RSI={rsi:.0f}超买（不追涨，但不阻止方向判断）")
        elif rsi < Config.RSI_OVERSOLD:
            details.append(f"RSI={rsi:.0f}超卖（不追空，但不阻止方向判断）")

        return {"votes": votes, "details": details}

    @classmethod
    def _vote_momentum(cls, df: pd.DataFrame) -> dict:
        """
        动量健康度投票（趋势跟踪核心）

        核心理念：
        1. 尽早发现趋势启动
        2. 避免超买做多、超卖做空
        3. 避免动量衰竭时逆向进场
        4. 顺势而为

        投票维度：
        - 趋势启动信号（早期发现）
        - 超买超卖过滤（避免极端位置）
        - 动量延续性（避免衰竭）
        - 背离检测（趋势反转预警）
        """
        votes = {"healthy": 0, "diverging": 0, "weak": 0}
        details = []
        warnings = []

        close = cls._safe_val(df.get("close"))
        ema20 = cls._safe_val(df.get("ema20"))
        ema60 = cls._safe_val(df.get("ema60"))

        # ---- 1. 趋势启动信号（早期发现）----
        if len(df) >= 5 and "ema20" in df.columns:
            ema20_prev = df["ema20"].iloc[-5]
            ema60_prev = df["ema60"].iloc[-5] if "ema60" in df.columns else ema60

            if not pd.isna(ema20_prev) and not pd.isna(ema60_prev):
                # EMA20 上穿 EMA60
                if ema20_prev < ema60_prev and ema20 > ema60:
                    votes["healthy"] += 2
                    details.append("EMA20上穿EMA60→趋势启动(×2)")
                # EMA20 下穿 EMA60
                elif ema20_prev > ema60_prev and ema20 < ema60:
                    votes["healthy"] += 2
                    details.append("EMA20下穿EMA60→趋势启动(×2)")
                # 价格突破近期高点
                if len(df) >= 20:
                    recent_high = df["high"].iloc[-20:-1].max()
                    recent_low = df["low"].iloc[-20:-1].min()
                    if close > recent_high:
                        votes["healthy"] += 1
                        details.append("突破20日高点→趋势延续(×1)")
                    elif close < recent_low:
                        votes["healthy"] += 1
                        details.append("跌破20日低点→趋势延续(×1)")

        # ---- 2. 超买超卖过滤（趋势市中不是离场信号，是不增仓信号）----
        # 修正：在真正的强趋势里，RSI可以持续超买数周。
        # RSI>70不是不做多的理由，是不追涨的理由。
        # 手里有仓位的继续持有（止损上移保护利润），空仓的等回调再进。
        rsi = cls._safe_val(df.get("rsi"))
        stoch_k = cls._safe_val(df.get("stoch_k"))
        cci = cls._safe_val(df.get("cci"))

        # 判断是否处于强趋势（ADX>25 或 均线排列一致）
        adx = cls._safe_val(df.get("adx"))
        ema20 = cls._safe_val(df.get("ema20"))
        ema60 = cls._safe_val(df.get("ema60"))
        strong_trend = adx > Config.ADX_STRONG_TREND or (
            ema20 > 0 and ema60 > 0 and ((ema20 > ema60 * 1.01) or (ema20 < ema60 * 0.99))
        )

        # RSI 超买超卖
        if rsi > Config.RSI_OVERBOUGHT_STRONG:
            if strong_trend:
                # 趋势市：不是离场信号，是不增仓信号
                votes["weak"] += 1  # 降低权重但不反转
                warnings.append(f"RSI={rsi:.0f}严重超买（趋势市）→不追涨，持仓止损上移")
            else:
                # 震荡市：真正的超买信号
                votes["weak"] += 2
                warnings.append(f"RSI={rsi:.0f}严重超买（震荡市）→避免做多")
        elif rsi > Config.RSI_OVERBOUGHT:
            if strong_trend:
                votes["weak"] += 0  # 趋势市不扣分
                warnings.append(f"RSI={rsi:.0f}超买（趋势市）→继续持有，不追涨")
            else:
                votes["weak"] += 1
                warnings.append(f"RSI={rsi:.0f}超买（震荡市）→谨慎做多")
        elif rsi < Config.RSI_OVERSOLD_STRONG:
            if strong_trend:
                votes["weak"] += 1
                warnings.append(f"RSI={rsi:.0f}严重超卖（趋势市）→不追空，持仓止损下移")
            else:
                votes["weak"] += 2
                warnings.append(f"RSI={rsi:.0f}严重超卖（震荡市）→避免做空")
        elif rsi < Config.RSI_OVERSOLD:
            if strong_trend:
                votes["weak"] += 0
                warnings.append(f"RSI={rsi:.0f}超卖（趋势市）→继续持有，不追空")
            else:
                votes["weak"] += 1
                warnings.append(f"RSI={rsi:.0f}超卖（震荡市）→谨慎做空")
        else:
            votes["healthy"] += 1

        # STOCH 超买超卖（同样区分趋势市和震荡市）
        if stoch_k > Config.STOCH_OVERBOUGHT:
            if strong_trend:
                votes["weak"] += 0  # 趋势市不扣分
                warnings.append(f"STOCH={stoch_k:.0f}严重超买（趋势市）→不追涨")
            else:
                votes["weak"] += 1
                warnings.append(f"STOCH={stoch_k:.0f}严重超买（震荡市）→避免做多")
        elif stoch_k < Config.STOCH_OVERSOLD:
            if strong_trend:
                votes["weak"] += 0
                warnings.append(f"STOCH={stoch_k:.0f}严重超卖（趋势市）→不追空")
            else:
                votes["weak"] += 1
                warnings.append(f"STOCH={stoch_k:.0f}严重超卖（震荡市）→避免做空")
        else:
            votes["healthy"] += 1

        # CCI 超买超卖（同样区分趋势市和震荡市）
        if cci > Config.CCI_OVERBOUGHT:
            if strong_trend:
                votes["weak"] += 0
                warnings.append(f"CCI={cci:.0f}严重超买（趋势市）→不追涨")
            else:
                votes["weak"] += 1
                warnings.append(f"CCI={cci:.0f}严重超买（震荡市）→避免做多")
        elif cci < Config.CCI_OVERSOLD:
            if strong_trend:
                votes["weak"] += 0
                warnings.append(f"CCI={cci:.0f}严重超卖（趋势市）→不追空")
            else:
                votes["weak"] += 1
                warnings.append(f"CCI={cci:.0f}严重超卖（震荡市）→避免做空")
        else:
            votes["healthy"] += 1

        # ---- 2b. 动量强度度量（RSI/STOCH/CCI 不只是超买超卖，也是动量指标）----
        # 核心理念（来自交易员经验）：
        # - RSI > 50 = 多头动量，RSI < 50 = 空头动量
        # - RSI 距离50越远，动量越强
        # - RSI 从高位回落 = 动量衰退（即使仍在50以上）
        # - 多个振荡器同时 > 50 或 < 50 = 动量共振

        # RSI 动量方向
        if rsi > Config.RSI_MOMENTUM_BULLISH:
            votes["healthy"] += 1
            details.append(f"RSI={rsi:.0f}>{Config.RSI_MOMENTUM_BULLISH}→多头动量(×1)")
        elif rsi < Config.RSI_MOMENTUM_BEARISH:
            votes["healthy"] += 1
            details.append(f"RSI={rsi:.0f}<{Config.RSI_MOMENTUM_BEARISH}→空头动量(×1)")

        # RSI 动量强度（距离50的偏离）
        rsi_distance = abs(rsi - 50)
        if rsi_distance > Config.RSI_MOMENTUM_STRONG:
            votes["healthy"] += 1
            details.append(f"RSI距50偏离{rsi_distance:.0f}→动量强(×1)")

        # 多振荡器动量共振（RSI/STOCH/CCI 同向）
        bullish_oscillators = 0
        bearish_oscillators = 0
        if rsi > Config.RSI_MOMENTUM_BULLISH:
            bullish_oscillators += 1
        elif rsi < Config.RSI_MOMENTUM_BEARISH:
            bearish_oscillators += 1
        if stoch_k > Config.STOCH_MOMENTUM_BULLISH:
            bullish_oscillators += 1
        elif stoch_k < Config.STOCH_MOMENTUM_BEARISH:
            bearish_oscillators += 1
        if not pd.isna(cci):
            if cci > Config.CCI_MOMENTUM_BULLISH:
                bullish_oscillators += 1
            elif cci < Config.CCI_MOMENTUM_BEARISH:
                bearish_oscillators += 1

        if bullish_oscillators >= Config.OSCILLATOR_RESONANCE:
            votes["healthy"] += 2
            details.append("RSI/STOCH/CCI共振偏多→动量强(×2)")
        elif bearish_oscillators >= Config.OSCILLATOR_RESONANCE:
            votes["healthy"] += 2
            details.append("RSI/STOCH/CCI共振偏空→动量强(×2)")
        elif bullish_oscillators >= 2:
            votes["healthy"] += 1
            details.append("2/3振荡器偏多→动量中等(×1)")
        elif bearish_oscillators >= 2:
            votes["healthy"] += 1
            details.append("2/3振荡器偏空→动量中等(×1)")

        # RSI 动量衰退检测（价格新高但RSI未新高）
        if len(df) >= 10:
            rsi_current = df["rsi"].iloc[-1]
            rsi_prev_high = df["rsi"].iloc[-10:-1].max()
            price_current = df["close"].iloc[-1]
            price_prev_high = df["close"].iloc[-10:-1].max()

            if price_current >= price_prev_high * 0.99 and rsi_current < rsi_prev_high * 0.9:
                votes["diverging"] += 1
                warnings.append(f"价格接近前高但RSI从{rsi_prev_high:.0f}降至{rsi_current:.0f}→动量衰退")

        # ---- 3. 动量延续性（避免衰竭）----
        macd_hist = cls._safe_val(df.get("macd_hist"))
        macd_hist_prev = df["macd_hist"].iloc[-2] if "macd_hist" in df.columns else 0

        if not pd.isna(macd_hist_prev):
            # MACD 柱状线方向
            if macd_hist > 0:
                if macd_hist > macd_hist_prev:
                    votes["healthy"] += 2
                    details.append("MACD柱放大→动量增强(×2)")
                elif macd_hist < macd_hist_prev * 0.7:
                    votes["diverging"] += 1
                    warnings.append("MACD柱收缩→动量衰减")
                else:
                    votes["healthy"] += 1
            elif macd_hist < 0:
                if macd_hist < macd_hist_prev:
                    votes["healthy"] += 2
                    details.append("MACD柱放大→动量增强(×2)")
                elif macd_hist > macd_hist_prev * 0.7:
                    votes["diverging"] += 1
                    warnings.append("MACD柱收缩→动量衰减")
                else:
                    votes["healthy"] += 1

        # ---- 4. 背离检测（趋势反转预警）----
        if len(df) >= 10 and "rsi" in df.columns:
            # 价格新高但 RSI 未新高 → 顶背离
            price_high_5 = df["close"].iloc[-5:].max()
            price_high_10 = df["close"].iloc[-10:].max()
            rsi_high_5 = df["rsi"].iloc[-5:].max()
            rsi_high_10 = df["rsi"].iloc[-10:].max()

            if price_high_5 >= price_high_10 and rsi_high_5 < rsi_high_10 * 0.95:
                votes["diverging"] += 2
                warnings.append("价格新高RSI未新高→顶背离预警")
            elif price_high_5 <= price_high_10 * 0.98 and rsi_high_5 > rsi_high_10:
                votes["diverging"] += 1
                details.append("价格未新高RSI新高→动量强劲")

        # ---- 5. 趋势方向与动量一致性 ----
        if ema20 > 0 and ema60 > 0:
            trend_up = ema20 > ema60
            momentum_up = macd_hist > 0

            if (trend_up and momentum_up) or (not trend_up and not momentum_up):
                votes["healthy"] += 1
                details.append("趋势与动量同向→健康")
            elif trend_up and not momentum_up:
                votes["diverging"] += 1
                warnings.append("趋势向上但动量向下→潜在背离")
            elif not trend_up and momentum_up:
                votes["diverging"] += 1
                warnings.append("趋势向下但动量向上→潜在背离")

        return {"votes": votes, "details": details, "warnings": warnings}

    @classmethod
    def _score_secondary_factors(
        cls, df: pd.DataFrame, direction_vote: dict, momentum_vote: dict
    ) -> dict[str, list[float]]:
        """
        二级因子打分系统

        每个维度包含多个二级因子，每个因子独立打分 (-1 到 +1)
        维度得分 = 因子得分的中位数（更稳健，不受异常因子影响）

        连续化实现：使用 tanh、clip、线性插值代替离散跳变
        减少毛刺，提高信号稳定性

        返回:
            字典，key=维度名，value=该维度所有二级因子的得分列表
        """
        close = cls._safe_val(df.get("close"))
        ema20 = cls._safe_val(df.get("ema20"))
        ema60 = cls._safe_val(df.get("ema60"))
        ema20_slope = cls._safe_val(df.get("ema20_slope"))
        ema60_slope = cls._safe_val(df.get("ema60_slope"))
        rsi = cls._safe_val(df.get("rsi"))
        stoch_k = cls._safe_val(df.get("stoch_k"))
        stoch_d = cls._safe_val(df.get("stoch_d"))
        cci = cls._safe_val(df.get("cci"))
        adx = cls._safe_val(df.get("adx"))
        atr = cls._safe_val(df.get("atr"))
        bb_upper = cls._safe_val(df.get("bb_upper"))
        bb_lower = cls._safe_val(df.get("bb_lower"))
        bb_mid = cls._safe_val(df.get("bb_mid"))

        # 判断是否为趋势市（用于RSI超买超卖条件判断）
        ma_trend = df["ma_trend_direction"].iloc[-1] if "ma_trend_direction" in df.columns else "NEUTRAL"
        is_strong_trend = adx > 25 and ma_trend in (
            "STRONG_BULLISH",
            "STRONG_BEARISH",
            "FALSE_BULLISH",
            "FALSE_BEARISH",
        )

        # 辅助函数：clip
        def clip(x, lo, hi):
            return max(lo, min(hi, x))

        factors = {
            "leading_signals": [],
            "trend_confirmation": [],
            "momentum_health": [],
            "volatility": [],
            "trend_strength": [],
        }

        # ============================================================
        # 1. 领先信号维度 (权重20%)
        # ============================================================

        # L1: EMA20/60分离度（连续化：tanh映射）
        # f1 = tanh(k1 * (EMA20-EMA60) / (λ*C))
        if ema20 > 0 and ema60 > 0 and close > 0:
            k1 = 4.0
            lam = 0.004
            separation = (ema20 - ema60) / (lam * close)
            f_l1 = np.tanh(k1 * separation)
            factors["leading_signals"].append(float(f_l1))

        # L2: EMA斜率变化（连续化：ATR归一化）
        # f2 = clip(s / (ATR * γ), -0.5, 0.5)
        if len(df) >= 2 and "ema20" in df.columns and atr > 0:
            ema20_now = df["ema20"].iloc[-1]
            ema20_prev = df["ema20"].iloc[-2]
            if not pd.isna(ema20_now) and not pd.isna(ema20_prev):
                s = ema20_now - ema20_prev
                gamma = 1.5
                f_l2 = clip(s / (atr * gamma), -0.5, 0.5)
                factors["leading_signals"].append(float(f_l2))

        # L3: 布林带相对位置（连续化：线性映射）
        # p = (C - BBmid) / ((BBup - BBlow) / 2)
        # f3 = clip(p, -1, 1) * gate
        if close > 0 and bb_upper > 0 and bb_lower > 0 and bb_upper > bb_lower:
            bb_half = (bb_upper - bb_lower) / 2
            p = (close - bb_mid) / bb_half if bb_half > 0 else 0
            # 中间区半幅输出，减少边缘摩擦
            gate = 0.5 if abs(p) < 0.7 else 1.0
            f_l3 = clip(p, -1, 1) * gate
            factors["leading_signals"].append(float(f_l3))

        # L4: 突破幅度（加成因子）
        # f4 = clip(amt / 0.05, 0, 1) * sign(突破方向)
        if close > 0 and bb_upper > 0 and bb_lower > 0:
            if close > bb_upper:
                amt = (close - bb_upper) / bb_upper
                f_l4 = clip(amt / 0.05, 0, 1)
                factors["leading_signals"].append(float(f_l4))
            elif close < bb_lower:
                amt = (bb_lower - close) / bb_lower
                f_l4 = -clip(amt / 0.05, 0, 1)
                factors["leading_signals"].append(float(f_l4))
            else:
                factors["leading_signals"].append(0.0)

        # ============================================================
        # 2. 趋势确认维度 (权重35%)
        # ============================================================

        # T1: 均线排列清晰度（保留离散，因排列本身是离散结构）
        if ema20 > 0 and ema60 > 0:
            if ma_trend == "STRONG_BULLISH":
                factors["trend_confirmation"].append(1.0)
            elif ma_trend == "FALSE_BULLISH":
                factors["trend_confirmation"].append(-0.5)
            elif ma_trend == "WEAK_BULLISH":
                factors["trend_confirmation"].append(0.5)
            elif ma_trend == "STRONG_BEARISH":
                factors["trend_confirmation"].append(-1.0)
            elif ma_trend == "FALSE_BEARISH":
                factors["trend_confirmation"].append(0.5)
            elif ma_trend == "WEAK_BEARISH":
                factors["trend_confirmation"].append(-0.5)
            else:
                factors["trend_confirmation"].append(0.0)

        # T2: 均线斜率方向（连续化：斜率大小反映力度）
        # f2 = sign(s20+s60) * clip((|s20|+|s60|)/(2*θ), 0, 1)
        if not pd.isna(ema20_slope) and not pd.isna(ema60_slope):
            theta = 0.0015
            s20 = ema20_slope / 100  # 转为小数
            s60 = ema60_slope / 100
            magnitude = (abs(s20) + abs(s60)) / (2 * theta)
            direction = np.sign(s20 + s60)
            f_t2 = direction * clip(magnitude, 0, 1)
            factors["trend_confirmation"].append(float(f_t2))

        # T3: 价格vs长均线（连续化：线性映射）
        # f3 = clip((C-EMA60)/(ρ*C), -1, 1)
        if close > 0 and ema60 > 0:
            rho = 0.015
            f_t3 = clip((close - ema60) / (rho * close), -1, 1)
            factors["trend_confirmation"].append(float(f_t3))

        # T4: 高低点结构（连续化：累积计数）
        # 最近N=10根K线：HH=新高次数，LL=新低次数
        # f4 = clip((HH-LL)/5, -1, 1)
        if len(df) >= 10:
            recent_highs = df["high"].iloc[-10:]
            recent_lows = df["low"].iloc[-10:]
            hh_count = 0
            ll_count = 0
            for i in range(1, len(recent_highs)):
                if recent_highs.iloc[i] > recent_highs.iloc[i - 1]:
                    hh_count += 1
                if recent_lows.iloc[i] < recent_lows.iloc[i - 1]:
                    ll_count += 1
            f_t4 = clip((hh_count - ll_count) / 5, -1, 1)
            factors["trend_confirmation"].append(float(f_t4))

        # T5: 趋势持续天数（连续化：线性映射）
        # f5 = clip(days/50, 0, 1) * sign(排列方向)
        if ema20 > 0 and ema60 > 0 and len(df) >= 20:
            trend_days = 0
            trend_sign = 0
            if ma_trend in ("STRONG_BULLISH", "FALSE_BULLISH", "WEAK_BULLISH"):
                trend_sign = 1
                for i in range(len(df) - 1, max(0, len(df) - 100), -1):
                    if df["ema20"].iloc[i] > df["ema60"].iloc[i]:
                        trend_days += 1
                    else:
                        break
            elif ma_trend in ("STRONG_BEARISH", "FALSE_BEARISH", "WEAK_BEARISH"):
                trend_sign = -1
                for i in range(len(df) - 1, max(0, len(df) - 100), -1):
                    if df["ema20"].iloc[i] < df["ema60"].iloc[i]:
                        trend_days += 1
                    else:
                        break

            f_t5 = clip(trend_days / 50, 0, 1) * trend_sign
            factors["trend_confirmation"].append(float(f_t5))

        # ============================================================
        # 3. 动量健康维度 (权重25%)
        # ============================================================

        # M1: RSI方向（连续化：线性映射）
        # f1 = clip((RSI(14)-50)/10, -1, 1)
        if rsi > 0:
            f_m1 = clip((rsi - 50) / 10, -1, 1)
            factors["momentum_health"].append(float(f_m1))

        # M2: RSI超买超卖（条件化：仅在非趋势市中生效）
        # is_trend = (ADX>25 and |T1|==1)
        # if not is_trend: f2 = -0.5 if RSI>80 else (+0.5 if RSI<20 else 0)
        if rsi > 0:
            if not is_strong_trend:
                if rsi > 80:
                    factors["momentum_health"].append(-0.5)
                elif rsi < 20:
                    factors["momentum_health"].append(0.5)
                else:
                    factors["momentum_health"].append(0.0)
            else:
                factors["momentum_health"].append(0.0)

        # M3: STOCH方向（连续化：gap映射）
        # gap = %K - %D; f3 = clip(gap/15, -0.5, 0.5)
        if stoch_k > 0 and not pd.isna(stoch_d):
            gap = stoch_k - stoch_d
            f_m3 = clip(gap / 15, -0.5, 0.5)
            # 极端区锚定
            if stoch_k > 80:
                f_m3 = max(f_m3, 0.55)
            elif stoch_k < 20:
                f_m3 = min(f_m3, -0.55)
            factors["momentum_health"].append(float(f_m3))

        # M4: CCI方向（连续化：线性缩放）
        # f4 = clip(CCI(20)/150, -0.5, 0.5)
        if not pd.isna(cci):
            f_m4 = clip(cci / 150, -0.5, 0.5)
            factors["momentum_health"].append(float(f_m4))

        # M5: 振荡器共振
        # votes = sign(M1)+sign(M3)+sign(M4); f5 = clip(votes/3, -1, 1)
        mom_factors = factors["momentum_health"][:]
        if len(mom_factors) >= 2:
            votes = sum(np.sign(f) for f in mom_factors)
            f_m5 = clip(votes / 3, -1, 1)
            factors["momentum_health"].append(float(f_m5))

        # ============================================================
        # 4. 波动率维度 (权重≤15%)
        # ============================================================
        # 2026-06-14 智能波动率评分逻辑：
        # - 波动率本身没有方向，但起作用的方向应该和动量方向一致
        # - 当RSI处于极端区域时，波动率扩张可能是赶顶/赶底信号
        # - 当RSI处于正常区域时，波动率作为方向放大器

        # 获取动量方向
        momentum_votes = momentum_vote.get("votes", {})
        momentum_healthy = momentum_votes.get("healthy", 0)
        momentum_weak = momentum_votes.get("weak", 0)
        momentum_diverging = momentum_votes.get("diverging", 0)

        # 动量方向判断
        if momentum_healthy > momentum_weak * 1.5:
            momentum_direction = 1.0  # 动量偏多
        elif momentum_weak > momentum_healthy * 1.5:
            momentum_direction = -1.0  # 动量偏空
        else:
            momentum_direction = 0.0  # 动量中性

        # 计算波动率状态
        atr_change = 0.0
        bb_width = 0.0
        vol_expanding = False

        if "atr" in df.columns and len(df) >= 2:
            atr_now = df["atr"].iloc[-1]
            atr_prev = df["atr"].iloc[-2]
            if not pd.isna(atr_now) and not pd.isna(atr_prev) and atr_prev > 0:
                atr_change = (atr_now - atr_prev) / atr_prev

        if close > 0 and bb_upper > 0 and bb_lower > 0 and bb_mid > 0:
            bb_width = (bb_upper - bb_lower) / bb_mid

        vol_expanding = atr_change > 0 and bb_width > 0.035

        # ========== 智能波动率评分 ==========
        if rsi > 70:  # RSI超买区域
            if vol_expanding:
                # 超买 + 波动率扩张 = 赶顶风险
                f_vol = -0.5
                factors["volatility"].append(f_vol)
            else:
                # 超买 + 波动率收缩 = 动能衰竭
                f_vol = -0.3
                factors["volatility"].append(f_vol)

        elif rsi < 30:  # RSI超卖区域
            if vol_expanding:
                # 超卖 + 波动率扩张 = 赶底风险
                f_vol = -0.5
                factors["volatility"].append(f_vol)
            else:
                # 超卖 + 波动率收缩 = 恐慌消退，可能反弹
                f_vol = 0.3
                factors["volatility"].append(f_vol)

        else:  # RSI正常区域 (30-70)
            # 波动率作为方向放大器
            if vol_expanding:
                # 波动率扩张，强化动量方向
                f_vol = 0.3 * momentum_direction
                factors["volatility"].append(f_vol)
            else:
                # 波动率收缩，趋势健康
                f_vol = 0.2 * momentum_direction
                factors["volatility"].append(f_vol)

        # 额外检查：动量背离时波动率警告
        if momentum_diverging > 0 and vol_expanding:
            # 动量背离 + 波动率扩张 = 高风险
            factors["volatility"].append(-0.3)

        # ============================================================
        # 5. 趋势强度维度 (权重10%)
        # ============================================================

        # 趋势方向系数（2026-06-14 新增）
        # ADX高只表示趋势强，不区分多空。需要乘以方向系数：
        # - 空头趋势时，高ADX应该强化空头（负分）
        # - 多头趋势时，高ADX应该强化多头（正分）
        votes = direction_vote.get("votes", {})
        bullish_votes = votes.get("bullish", 0)
        bearish_votes = votes.get("bearish", 0)
        if bullish_votes > bearish_votes:
            trend_direction = 1.0  # 多头
        elif bearish_votes > bullish_votes:
            trend_direction = -1.0  # 空头
        else:
            trend_direction = 0.0  # 中性

        # S1: ADX绝对值（连续化：中心化映射）
        # f1 = clip((ADX-22.5)/10, -1, 1) * direction
        if adx > 0:
            f_s1 = clip((adx - 22.5) / 10, -1, 1) * trend_direction
            factors["trend_strength"].append(float(f_s1))

        # S2: ADX方向（连续化：归一化变化）
        # ΔADX = ADX - ADX[1]; f2 = clip(ΔADX/5, -0.5, 0.5) * direction
        if "adx" in df.columns and len(df) >= 2:
            adx_now = df["adx"].iloc[-1]
            adx_prev = df["adx"].iloc[-2]
            if not pd.isna(adx_now) and not pd.isna(adx_prev):
                delta_adx = adx_now - adx_prev
                f_s2 = clip(delta_adx / 5, -0.5, 0.5) * trend_direction
                factors["trend_strength"].append(float(f_s2))

        # S3: ADX分位数
        # q = percentile(ADX, 50); f3 = (+0.5 if q>0.7 else (-0.5 if q<0.3 else 0)) * direction
        if "adx" in df.columns and len(df) >= 50:
            adx_values = df["adx"].iloc[-50:].dropna()
            if len(adx_values) > 0:
                adx_rank = (adx_values < adx).sum() / len(adx_values)
                if adx_rank > 0.7:
                    factors["trend_strength"].append(0.5 * trend_direction)
                elif adx_rank < 0.3:
                    factors["trend_strength"].append(-0.5 * trend_direction)
                else:
                    factors["trend_strength"].append(0.0)

        # 1.4 因子平滑（EMA α=0.3）
        # 对离散因子做指数平滑，减少跳变，提高信号稳定性
        factors = cls._smooth_factors(df, factors)

        return factors

    @classmethod
    def _smooth_factors(
        cls, df: pd.DataFrame, factors: dict[str, list[float]], alpha: float = 0.3
    ) -> dict[str, list[float]]:
        """
        因子平滑（EMA）

        使用指数移动平均对因子进行平滑，减少跳变：
        f_smooth = α * f_raw + (1-α) * f_smooth_prev

        参数:
            df: DataFrame（用于获取历史因子值）
            factors: 当前因子值
            alpha: 平滑系数（0.3~0.5）

        返回:
            平滑后的因子值
        """
        # 检查是否有历史因子值
        if not hasattr(cls, "_prev_factors") or cls._prev_factors is None:
            cls._prev_factors = factors
            return factors

        smoothed = {}
        for dim_name, factor_list in factors.items():
            if dim_name not in cls._prev_factors:
                smoothed[dim_name] = factor_list
                continue

            prev_list = cls._prev_factors[dim_name]
            smoothed_list = []

            for i, f_raw in enumerate(factor_list):
                if i < len(prev_list):
                    # EMA平滑
                    f_smooth = alpha * f_raw + (1 - alpha) * prev_list[i]
                    smoothed_list.append(f_smooth)
                else:
                    smoothed_list.append(f_raw)

            smoothed[dim_name] = smoothed_list

        # 保存当前因子值作为下次的前值
        cls._prev_factors = smoothed

        return smoothed

    @classmethod
    def _get_rolling_percentile(cls, df: pd.DataFrame, col: str, percentile: float, window: int = 120) -> float:
        """
        获取滚动分位数（用于自适应阈值）

        参数:
            df: DataFrame
            col: 列名
            percentile: 分位数（0~1）
            window: 滚动窗口长度

        返回:
            分位数值
        """
        if col not in df.columns or len(df) < window:
            return np.nan

        values = df[col].iloc[-window:].dropna()
        if len(values) < 10:
            return np.nan

        return float(np.percentile(values, percentile * 100))

    @classmethod
    def _merge_correlated_factors(
        cls, factors: dict[str, list[float]], threshold: float = 0.85
    ) -> dict[str, list[float]]:
        """
        合并高度相关的因子（3.1 去除冗余因子）

        如果同一维度内两个因子相关系数 > threshold，合并为一个

        参数:
            factors: 因子字典
            threshold: 相关性阈值

        返回:
            合并后的因子字典
        """
        merged = {}

        for dim_name, factor_list in factors.items():
            if len(factor_list) <= 1:
                merged[dim_name] = factor_list
                continue

            # 检查因子间的相关性
            # 简化实现：如果两个因子符号相同且差值<0.3，认为高度相关
            keep = []
            for i, f in enumerate(factor_list):
                is_redundant = False
                for j in range(len(keep)):
                    f_kept = factor_list[keep[j]]
                    # 如果两个因子符号相同且差值<0.3，认为高度相关
                    if np.sign(f) == np.sign(f_kept) and abs(f - f_kept) < 0.3:
                        is_redundant = True
                        break
                if not is_redundant:
                    keep.append(i)

            merged[dim_name] = [factor_list[i] for i in keep]

        return merged

    @classmethod
    def _calc_dual_check_discount(cls, dimension_scores: dict, pos: float) -> float:
        """
        双轨验证精细化（3.4）

        根据投票一致性和信号幅度计算折扣系数

        参数:
            dimension_scores: 维度得分
            pos: 当前仓位信号

        返回:
            折扣系数 [0.3, 1.0]
        """
        # 计算各维度方向
        signs = []
        for dim in dimension_scores.values():
            score = dim.get("score", 0)
            if abs(score) > 0.1:  # 忽略微弱信号
                signs.append(np.sign(score))

        if not signs:
            return 1.0

        # 投票一致性：同意多数方向的维度占比
        majority_sign = np.sign(sum(signs))
        agree_count = sum(1 for s in signs if s == majority_sign)
        agree_ratio = agree_count / len(signs) if signs else 0.5

        # 信号幅度
        signal_strength = abs(pos)

        # 矛盾程度
        conflict_level = (1 - agree_ratio) * (1 - signal_strength)

        # 折扣系数：冲突越严重折扣越大
        discount = 1 - conflict_level * Config.DUAL_CHECK_MAX_DISCOUNT

        # 强信号保护：如果信号很强，折扣较小
        if signal_strength > 0.7:
            discount = max(discount, 0.8)

        return max(0.3, min(1.0, discount))

    @classmethod
    def _mad_standardize(cls, scores: list[float], lookback: int = 120) -> list[float]:
        """
        MAD标准化替代Z-score（3.3）

        MAD对异常值更稳健，与中层MAD过滤理念一致

        参数:
            scores: 维度得分列表
            lookback: 滚动窗口长度

        返回:
            标准化后的z值列表
        """
        if len(scores) < 3:
            return [0.0] * len(scores)

        median = np.median(scores)
        mad = np.median(np.abs(scores - median))

        # 1.4826使MAD近似标准差
        if mad < 1e-10:
            return [0.0] * len(scores)

        z = [(s - median) / (mad * 1.4826 + 1e-10) for s in scores]
        z = [max(-3, min(3, zi)) for zi in z]  # Winsorize ±3σ

        return z

    @classmethod
    def _check_cold_start(cls, df: pd.DataFrame) -> dict:
        """
        5.1 冷启动检测

        前N根K线不产生交易信号，仅用于积累滚动统计量

        参数:
            df: DataFrame

        返回:
            is_cold_start: 是否处于冷启动期
            bars_remaining: 剩余冷启动K线数
            progress: 冷启动进度（0~1）
        """
        n_bars = len(df)
        cold_start_bars = Config.COLD_START_BARS

        if n_bars < cold_start_bars:
            return {
                "is_cold_start": True,
                "bars_remaining": cold_start_bars - n_bars,
                "progress": n_bars / cold_start_bars,
            }
        else:
            return {
                "is_cold_start": False,
                "bars_remaining": 0,
                "progress": 1.0,
            }

    @classmethod
    def _check_regime_drift(cls, df: pd.DataFrame) -> dict:
        """
        5.2 滚动窗体制漂移检测

        当市场结构发生明显变化（波动率均值漂移>50%）时，触发窗口重置

        参数:
            df: DataFrame

        返回:
            drift_detected: 是否检测到漂移
            vol_ratio: 当前波动率与历史波动率的比值
            action: 建议操作（none/reset/warning）
        """
        if "atr" not in df.columns or len(df) < 120:
            return {"drift_detected": False, "vol_ratio": 1.0, "action": "none"}

        # 计算近期波动率（最近20根）
        recent_vol = df["atr"].iloc[-20:].mean()

        # 计算历史波动率（前100根）
        historical_vol = df["atr"].iloc[-120:-20].mean()

        if historical_vol <= 0:
            return {"drift_detected": False, "vol_ratio": 1.0, "action": "none"}

        vol_ratio = recent_vol / historical_vol

        # 检测漂移
        drift_detected = abs(vol_ratio - 1.0) > Config.REGIME_DRIFT_THRESHOLD

        if drift_detected:
            if vol_ratio > 1.5:
                action = "reset"  # 波动率大幅上升，重置窗口
            elif vol_ratio < 0.5:
                action = "reset"  # 波动率大幅下降，重置窗口
            else:
                action = "warning"  # 轻微漂移，警告
        else:
            action = "none"

        return {
            "drift_detected": drift_detected,
            "vol_ratio": round(vol_ratio, 3),
            "action": action,
        }

    @classmethod
    def _check_extreme_values(cls, df: pd.DataFrame, dimension_scores: dict) -> dict:
        """
        5.3 极端值保护

        若某维度连续多根超出±3σ，标记为"不稳定"，暂时从融合中移除

        参数:
            df: DataFrame
            dimension_scores: 维度得分

        返回:
            unstable_dimensions: 不稳定的维度列表
            is_any_unstable: 是否有不稳定维度
        """
        unstable_dimensions = []

        # 检查每个维度的z分数
        all_scores = [d["score"] for d in dimension_scores.values()]
        z_scores = cls._mad_standardize(all_scores)

        dim_names = list(dimension_scores.keys())
        for i, (dim_name, z) in enumerate(zip(dim_names, z_scores)):
            if abs(z) > Config.EXTREME_VALUE_THRESHOLD:
                # 检查历史数据中是否连续极端
                if hasattr(cls, "_extreme_count"):
                    if dim_name not in cls._extreme_count:
                        cls._extreme_count[dim_name] = 0
                    cls._extreme_count[dim_name] += 1
                else:
                    cls._extreme_count = {dim_name: 1}

                if cls._extreme_count.get(dim_name, 0) >= Config.EXTREME_VALUE_CONSECUTIVE:
                    unstable_dimensions.append(dim_name)
            else:
                # 重置计数
                if hasattr(cls, "_extreme_count") and dim_name in cls._extreme_count:
                    cls._extreme_count[dim_name] = 0

        return {
            "unstable_dimensions": unstable_dimensions,
            "is_any_unstable": len(unstable_dimensions) > 0,
        }

    @classmethod
    def _get_vol_regime_weights(cls, df: pd.DataFrame) -> dict:
        """
        6.1 波动率状态权重切换

        根据当前ATR分位数动态调整维度权重：
        - 高波动（>80%分位）：领先信号权重提升至30%
        - 低波动（<20%分位）：趋势确认权重提升至40%
        - 正常波动：保持默认权重

        参数:
            df: DataFrame

        返回:
            weights: 动态权重字典
            vol_regime: 波动率状态（high/normal/low）
        """
        if "atr" not in df.columns or len(df) < Config.VOL_REGIME_WINDOW:
            return Config.DIMENSION_WEIGHTS.copy(), "normal"

        atr_values = df["atr"].iloc[-Config.VOL_REGIME_WINDOW :].dropna()
        if len(atr_values) < 50:
            return Config.DIMENSION_WEIGHTS.copy(), "normal"

        current_atr = df["atr"].iloc[-1]
        if pd.isna(current_atr):
            return Config.DIMENSION_WEIGHTS.copy(), "normal"

        # 计算分位数
        percentile = (atr_values < current_atr).sum() / len(atr_values)

        if percentile > Config.VOL_REGIME_HIGH_PERCENTILE:
            return Config.WEIGHTS_HIGH_VOL.copy(), "high"
        elif percentile < Config.VOL_REGIME_LOW_PERCENTILE:
            return Config.WEIGHTS_LOW_VOL.copy(), "low"
        else:
            return Config.DIMENSION_WEIGHTS.copy(), "normal"

    @classmethod
    def _calc_dimension_win_rates(cls, df: pd.DataFrame, dimension_scores: dict) -> dict:
        """
        6.2 维度历史胜率自适应

        维护每个维度过去N次信号的胜率（方向预测准确率）

        参数:
            df: DataFrame
            dimension_scores: 维度得分

        返回:
            win_rates: 各维度胜率字典
        """
        # 初始化胜率统计
        if not hasattr(cls, "_dimension_stats"):
            cls._dimension_stats = {}

        # 获取当前价格方向
        if len(df) < 2:
            return {dim: 0.5 for dim in dimension_scores}

        current_direction = np.sign(df["close"].iloc[-1] - df["close"].iloc[-2])

        # 更新各维度胜率
        for dim_name, dim in dimension_scores.items():
            score = dim.get("score", 0)
            dim_direction = np.sign(score)

            if dim_name not in cls._dimension_stats:
                cls._dimension_stats[dim_name] = {"correct": 0, "total": 0}

            # 判断预测是否正确
            if dim_direction != 0:  # 只统计有方向的预测
                cls._dimension_stats[dim_name]["total"] += 1
                if dim_direction == current_direction:
                    cls._dimension_stats[dim_name]["correct"] += 1

        # 计算胜率（拉普拉斯平滑）
        win_rates = {}
        for dim_name, stats in cls._dimension_stats.items():
            correct = stats["correct"] + Config.WIN_RATE_SMOOTHING
            total = stats["total"] + Config.WIN_RATE_SMOOTHING * 2
            win_rates[dim_name] = correct / total if total > 0 else 0.5

        return win_rates

    @classmethod
    def _apply_win_rate_weights(cls, dimension_scores: dict, win_rates: dict) -> dict:
        """
        应用胜率自适应权重

        参数:
            dimension_scores: 维度得分
            win_rates: 各维度胜率

        返回:
            调整后的维度得分
        """
        adjusted = {}
        for dim_name, dim in dimension_scores.items():
            win_rate = win_rates.get(dim_name, 0.5)
            # 胜率高的维度权重提升，胜率低的维度权重降低
            weight_multiplier = win_rate / 0.5  # 归一化到1附近
            adjusted[dim_name] = dim.copy()
            new_weight = dim["weight"] * weight_multiplier

            # 应用权重边界（2026-06-14 新增：防止动态权重异常）
            if dim_name in Config.WEIGHT_BOUNDS:
                lo, hi = Config.WEIGHT_BOUNDS[dim_name]
                new_weight = max(lo, min(hi, new_weight))

            adjusted[dim_name]["weight"] = round(new_weight, 4)
            adjusted[dim_name]["weighted"] = round(dim["score"] * adjusted[dim_name]["weight"], 2)

        # 重新归一化权重
        total_weight = sum(d["weight"] for d in adjusted.values())
        if total_weight > 0:
            for dim_name in adjusted:
                adjusted[dim_name]["weight"] = round(adjusted[dim_name]["weight"] / total_weight, 4)
                adjusted[dim_name]["weighted"] = round(adjusted[dim_name]["score"] * adjusted[dim_name]["weight"], 2)

        # 归一化后再次应用权重边界（2026-06-14 新增）
        # 归一化可能使权重超出边界，需要再次裁剪
        needs_renormalize = False
        for dim_name in adjusted:
            if dim_name in Config.WEIGHT_BOUNDS:
                lo, hi = Config.WEIGHT_BOUNDS[dim_name]
                if adjusted[dim_name]["weight"] < lo or adjusted[dim_name]["weight"] > hi:
                    adjusted[dim_name]["weight"] = round(max(lo, min(hi, adjusted[dim_name]["weight"])), 4)
                    adjusted[dim_name]["weighted"] = round(
                        adjusted[dim_name]["score"] * adjusted[dim_name]["weight"], 2
                    )
                    needs_renormalize = True

        # 如果裁剪了，再次归一化
        if needs_renormalize:
            total_weight = sum(d["weight"] for d in adjusted.values())
            if total_weight > 0:
                for dim_name in adjusted:
                    adjusted[dim_name]["weight"] = round(adjusted[dim_name]["weight"] / total_weight, 4)
                    adjusted[dim_name]["weighted"] = round(
                        adjusted[dim_name]["score"] * adjusted[dim_name]["weight"], 2
                    )

        return adjusted

    @classmethod
    def _add_volume_factors(cls, df: pd.DataFrame) -> dict:
        """
        6.3 成交量因子引入

        新增三个成交量因子：
        - OBV趋势：能量潮确认价格趋势
        - 成交量相对强度：放量/缩量信号
        - MFI：资金流向强度

        参数:
            df: DataFrame

        返回:
            volume_factors: 成交量因子字典
        """
        factors = {}

        # OBV趋势
        if "volume" in df.columns and len(df) >= Config.VOLUME_OBV_SLOPE_WINDOW:
            close_diff = df["close"].diff()
            obv = (np.sign(close_diff) * df["volume"]).cumsum()
            obv_slope = obv.iloc[-Config.VOLUME_OBV_SLOPE_WINDOW :].diff().mean()
            obv_std = obv.iloc[-Config.VOLUME_OBV_SLOPE_WINDOW :].std()
            if obv_std > 0:
                factors["obv_trend"] = float(np.tanh(obv_slope / obv_std))
            else:
                factors["obv_trend"] = 0.0

        # 成交量相对强度
        if "volume" in df.columns and len(df) >= Config.VOLUME_VR_WINDOW:
            vol_sma = df["volume"].rolling(Config.VOLUME_VR_WINDOW).mean()
            current_vol = df["volume"].iloc[-1]
            if vol_sma.iloc[-1] > 0:
                vr = current_vol / vol_sma.iloc[-1]
                factors["volume_ratio"] = float(np.clip((vr - 1) * 2, -1, 1))
            else:
                factors["volume_ratio"] = 0.0

        # MFI（资金流向强度）
        if "volume" in df.columns and len(df) >= Config.VOLUME_MFI_WINDOW:
            typical_price = (df["high"] + df["low"] + df["close"]) / 3
            money_flow = typical_price * df["volume"]
            positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
            negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)

            positive_sum = positive_flow.rolling(Config.VOLUME_MFI_WINDOW).sum()
            negative_sum = negative_flow.rolling(Config.VOLUME_MFI_WINDOW).sum()

            if negative_sum.iloc[-1] > 0:
                mfi = 100 - (100 / (1 + positive_sum.iloc[-1] / negative_sum.iloc[-1]))
                factors["mfi"] = float(np.clip((mfi - 50) / 50, -1, 1))
            else:
                factors["mfi"] = 0.0

        return factors

    @classmethod
    def consensus(cls, df: pd.DataFrame) -> dict:
        """
        多指标共识判断

        返回:
            state: STRONG_UPTREND / STRONG_DOWNTREND / WEAK_UPTREND / WEAK_DOWNTREND / RANGE_BOUND
            confidence: 0-100 置信度
            direction: 1(多) / -1(空) / 0(中性)
            strength: strong / weak / none
            health: 指标健康度
            conflict_level: 冲突程度 low / medium / high
            evidence: 详细证据
        """
        # 0. 冷启动检测（5.1）
        cold_start = cls._check_cold_start(df)
        if cold_start["is_cold_start"]:
            return {
                "state": "COLD_START",
                "confidence": 0,
                "direction": 0,
                "strength": "none",
                "health": {"health_score": 0},
                "conflict_level": "none",
                "evidence": [
                    f"冷启动期：剩余{cold_start['bars_remaining']}根K线，进度{cold_start['progress'] * 100:.0f}%"
                ],
                "warnings": ["冷启动期不产生交易信号"],
                "actionable": False,
                "votes": {
                    "strength": {"strong": 0, "weak": 0, "none": 0},
                    "direction": {"bullish": 0, "bearish": 0, "neutral": 0},
                    "momentum": {"healthy": 0, "diverging": 0, "weak": 0},
                },
                "dimension_scores": {},
                "composite_score": 0,
                "filtered_dimensions": {},
                "filtered_out": [],
                "filtered_composite": 0,
                "score_direction": 0,
                "is_consolidation": False,
                "dual_check_discount": 1.0,
                "z_scores": [],
                "cold_start": cold_start,
            }

        # 1. 检查指标健康度
        health = cls.check_indicator_health(df)

        # 2. 趋势强度投票
        strength_vote = cls._vote_trend_strength(df)

        # 3. 趋势方向投票
        direction_vote = cls._vote_trend_direction(df)

        # 4. 动量健康度投票
        momentum_vote = cls._vote_momentum(df)

        # 5. 综合判断
        sv = strength_vote["votes"]
        dv = direction_vote["votes"]
        mv = momentum_vote["votes"]

        # 趋势强度
        if sv["strong"] >= 3:
            strength = "strong"
        elif sv["weak"] >= 2:
            strength = "weak"
        else:
            strength = "none"

        # 趋势方向（领先信号优先）
        # 只要有领先信号（EMA交叉或通道突破）就判断方向
        # 不需要所有指标都确认
        total_bull = dv["bullish"]
        total_bear = dv["bearish"]

        # 领先信号判断（EMA交叉+3票，通道突破+2票）
        # 只要领先信号有≥2票，就判断方向
        leading_bull = 0
        leading_bear = 0
        for detail in direction_vote["details"]:
            if "领先" in detail and "多" in detail:
                leading_bull += 1
            elif "领先" in detail and "空" in detail:
                leading_bear += 1

        # 方向判断：领先信号优先，确认信号辅助
        if leading_bull > 0 and total_bull > total_bear:
            direction = 1  # 有领先多头信号 + 总体偏多
        elif leading_bear > 0 and total_bear > total_bull:
            direction = -1  # 有领先空头信号 + 总体偏空
        elif total_bull > total_bear + 1:
            direction = 1  # 虽无领先信号，但确认信号足够多
        elif total_bear > total_bull + 1:
            direction = -1
        else:
            direction = 0

        # 冲突检测
        conflict_level = "low"
        if total_bull > 0 and total_bear > 0 and abs(total_bull - total_bear) <= 1:
            conflict_level = "high"
        elif abs(total_bull - total_bear) <= 2:
            conflict_level = "medium"

        # ---- 二级因子打分系统 ----
        # 每个维度包含多个二级因子，维度得分 = 因子得分的中位数
        dimension_scores = {}
        secondary_factors = cls._score_secondary_factors(df, direction_vote, momentum_vote)

        # 3.1 去除冗余因子：合并高度相关的因子
        secondary_factors = cls._merge_correlated_factors(secondary_factors, Config.FACTOR_CORRELATION_THRESHOLD)

        # 6.3 成交量因子引入
        volume_factors = cls._add_volume_factors(df)
        if volume_factors:
            # 将成交量因子加入动量健康维度
            if "momentum_health" not in secondary_factors:
                secondary_factors["momentum_health"] = []
            for vf_name, vf_value in volume_factors.items():
                secondary_factors["momentum_health"].append(vf_value)

        # 6.1 波动率状态权重切换
        dynamic_weights, vol_regime = cls._get_vol_regime_weights(df)

        # 更新维度分数（使用二级因子中位数）
        for dim_name, factors in secondary_factors.items():
            if factors:
                # 使用中位数代替平均值，更稳健
                dim_score = float(np.median(factors))
                dim_score = max(-1, min(1, dim_score))
            else:
                dim_score = 0

            w = dynamic_weights.get(dim_name, Config.DIMENSION_WEIGHTS[dim_name])
            dimension_scores[dim_name] = {
                "score": round(dim_score, 2),
                "weight": w,
                "weighted": round(dim_score * w, 2),
                "description": Config.DIMENSION_DESCRIPTIONS[dim_name],
                "factors": [round(f, 2) for f in factors],
            }

        # 6.2 维度历史胜率自适应
        win_rates = cls._calc_dimension_win_rates(df, dimension_scores)
        dimension_scores = cls._apply_win_rate_weights(dimension_scores, win_rates)

        # ---- 均线粘合检测与权重动态调整 ----
        # 当EMA20/60差值<价格0.5%且ADX<20时，排列维度权重衰减，走势/价格位置权重提升
        # 解决：均线粘合期排列维度权重过高导致方向判断滞后于价格行为的问题
        ema20 = cls._safe_val(df.get("ema20"))
        ema60 = cls._safe_val(df.get("ema60"))
        close_val = cls._safe_val(df.get("close"))
        adx_val = cls._safe_val(df.get("adx"))

        is_consolidation = False
        if close_val > 0 and ema20 > 0 and ema60 > 0:
            ma_gap_pct = abs(ema20 - ema60) / close_val
            if ma_gap_pct < Config.MA_CONSOLIDATION_THRESHOLD and adx_val < Config.MA_CONSOLIDATION_ADX_MAX:
                is_consolidation = True
                # 衰减趋势确认维度（包含排列信号），提升动量维度
                dimension_scores["trend_confirmation"]["weight"] = round(
                    Config.DIMENSION_WEIGHTS["trend_confirmation"] * Config.MA_CONSOLIDATION_ARRANGEMENT_DECAY, 4
                )
                dimension_scores["trend_confirmation"]["weighted"] = round(
                    dimension_scores["trend_confirmation"]["score"] * dimension_scores["trend_confirmation"]["weight"],
                    2,
                )
                dimension_scores["momentum_health"]["weight"] = round(
                    Config.DIMENSION_WEIGHTS["momentum_health"] * Config.MA_CONSOLIDATION_TREND_BOOST, 4
                )
                dimension_scores["momentum_health"]["weighted"] = round(
                    dimension_scores["momentum_health"]["score"] * dimension_scores["momentum_health"]["weight"], 2
                )

        # 计算加权总分
        composite_score = sum(d["weighted"] for d in dimension_scores.values())
        composite_score = round(composite_score, 2)

        # 5.2 体制漂移检测
        regime_drift = cls._check_regime_drift(df)

        # 5.3 极端值保护
        extreme_check = cls._check_extreme_values(df, dimension_scores)
        if extreme_check["is_any_unstable"]:
            # 移除不稳定维度
            for dim_name in extreme_check["unstable_dimensions"]:
                if dim_name in dimension_scores:
                    del dimension_scores[dim_name]

        # ---- 三层融合架构（工业界标准方案）----
        # 底层：MAD标准化（替代Z-score，更稳健）
        # 中层：投票过滤共识（剔除异常信号 + 强信号保护）
        # 顶层：对剩余维度进行加权打分 + 双轨验证折扣

        # 3.3 底层：MAD标准化（替代Z-score）
        all_scores = [d["score"] for d in dimension_scores.values()]
        z_scores = cls._mad_standardize(all_scores)

        # 中层：MAD异常过滤
        if len(all_scores) >= 3:
            median_score = np.median(all_scores)
            mad = np.median([abs(s - median_score) for s in all_scores])

            # 动态阈值：基于波动率调整
            atr = cls._safe_val(df.get("atr"))
            close = cls._safe_val(df.get("close"))
            if close > 0 and atr > 0 and atr / close * 100 > 2:
                mad_threshold = 5.0  # 极端行情豁免
            else:
                mad_threshold = 3.0  # 正常阈值

            # 过滤异常维度（增加强信号保护）
            filtered_dimensions = {}
            filtered_out = []
            dim_names = list(dimension_scores.keys())

            for i, (dim_name, dim) in enumerate(dimension_scores.items()):
                z = z_scores[i] if i < len(z_scores) else 0
                is_outlier = abs(dim["score"] - median_score) > mad * mad_threshold and mad > 0
                is_strong_signal = abs(z) > Config.DUAL_CHECK_STRONG_SIGNAL

                if is_outlier and not is_strong_signal:
                    # 异常但非强信号 → 过滤
                    filtered_out.append(dim_name)
                elif is_outlier and is_strong_signal:
                    # 异常但强信号 → 检查方向一致性
                    majority_sign = np.sign(median_score)
                    if np.sign(dim["score"]) == majority_sign or len(filtered_dimensions) < 2:
                        filtered_dimensions[dim_name] = dim
                    else:
                        filtered_out.append(dim_name)
                else:
                    filtered_dimensions[dim_name] = dim

            # 如果过滤后维度不足3个，保留所有维度（防止过度过滤）
            if len(filtered_dimensions) < 3:
                filtered_dimensions = dimension_scores
                filtered_out = []
        else:
            filtered_dimensions = dimension_scores
            filtered_out = []

        # 顶层：对剩余维度重新计算加权总分
        if filtered_dimensions:
            # 重新归一化权重
            total_weight = sum(d["weight"] for d in filtered_dimensions.values())
            if total_weight > 0:
                filtered_composite = sum(d["score"] * d["weight"] / total_weight for d in filtered_dimensions.values())
            else:
                filtered_composite = composite_score
        else:
            filtered_composite = composite_score

        # 3.4 双轨验证折扣
        dual_check_discount = cls._calc_dual_check_discount(dimension_scores, filtered_composite)
        filtered_composite = filtered_composite * dual_check_discount

        filtered_composite = round(filtered_composite, 2)

        # 打分方向判断（使用过滤后的分数）
        if filtered_composite > Config.SCORE_BULLISH:
            score_direction = 1
        elif filtered_composite < Config.SCORE_BEARISH:
            score_direction = -1
        else:
            score_direction = 0

        # 置信度计算
        if strength == "strong":
            base_confidence = 80
        elif strength == "weak":
            base_confidence = 60
        else:
            base_confidence = 40

        # 方向一致性加成
        direction_consensus = max(total_bull, total_bear) / (total_bull + total_bear + 1)
        confidence = base_confidence * direction_consensus

        # 健康度调整
        confidence *= health["health_score"] / 100

        # 冲突惩罚
        if conflict_level == "high":
            confidence *= 0.6
        elif conflict_level == "medium":
            confidence *= 0.8

        # 动量健康加成/减成
        if mv["healthy"] >= 3:
            confidence *= 1.15
        elif mv["healthy"] >= 2:
            confidence *= 1.05
        elif mv["diverging"] >= 2:
            confidence *= 0.75
        elif mv["diverging"] >= 1:
            confidence *= 0.85

        # 动量警告惩罚
        momentum_warnings = mv.get("warnings", [])
        warning_count = len(momentum_warnings)
        if warning_count >= 3:
            confidence *= 0.6
        elif warning_count >= 2:
            confidence *= 0.75
        elif warning_count >= 1:
            confidence *= 0.9

        confidence = min(100, max(0, confidence))

        # 状态判定
        if strength == "strong" and direction == 1:
            state = "STRONG_UPTREND"
        elif strength == "strong" and direction == -1:
            state = "STRONG_DOWNTREND"
        elif strength == "weak" and direction == 1:
            state = "WEAK_UPTREND"
        elif strength == "weak" and direction == -1:
            state = "WEAK_DOWNTREND"
        else:
            state = "RANGE_BOUND"

        # 收集证据
        evidence = []
        evidence.append(
            f"健康度: {health['health_score']:.0f}% ({health['available_count']}/{health['available_count'] + health['missing_count']}指标)"
        )
        evidence.append(f"强度投票: 强{sv['strong']} 弱{sv['weak']} 无{sv['none']}")
        evidence.append(f"方向投票: 多{dv['bullish']} 空{dv['bearish']} 中{dv['neutral']}")
        evidence.append(f"动量投票: 健康{mv['healthy']} 背离{mv['diverging']} 弱{mv['weak']}")
        evidence.append(f"冲突程度: {conflict_level}")
        if is_consolidation:
            evidence.append(
                f"⚠️ 均线粘合: EMA20/60差值<{Config.MA_CONSOLIDATION_THRESHOLD * 100:.1f}%，排列权重衰减至{Config.MA_CONSOLIDATION_ARRANGEMENT_DECAY * 100:.0f}%"
            )
        evidence.extend(strength_vote["details"])
        evidence.extend(direction_vote["details"])
        evidence.extend(momentum_vote["details"])

        # 添加警告信息
        warnings = []
        if momentum_warnings:
            warnings.extend(momentum_warnings)

        return {
            "state": state,
            "confidence": round(confidence, 1),
            "direction": direction,
            "strength": strength,
            "health": health,
            "conflict_level": conflict_level,
            "evidence": evidence,
            "warnings": warnings,
            "actionable": warning_count < 2 and conflict_level != "high",
            "votes": {"strength": sv, "direction": dv, "momentum": mv},
            "dimension_scores": dimension_scores,
            "composite_score": composite_score,
            "filtered_dimensions": filtered_dimensions,
            "filtered_out": filtered_out,
            "filtered_composite": filtered_composite,
            "score_direction": score_direction,
            "is_consolidation": is_consolidation,
            "dual_check_discount": round(dual_check_discount, 3),
            "z_scores": [round(z, 3) for z in z_scores],
            "cold_start": cold_start,
            "regime_drift": regime_drift,
            "extreme_check": extreme_check,
            "vol_regime": vol_regime,
            "volume_factors": volume_factors,
            "win_rates": win_rates,
        }


class TrendPhaseDetector:
    """
    趋势阶段识别器（多指标确认版）

    使用多维度指标确认趋势阶段，提升容错能力：
    1. ADX + ADXR 趋势强度变化
    2. 均线排列 + 间距变化
    3. MACD 柱状线动量
    4. RSI 超买超卖
    5. STOCH 位置
    6. 价格与均线距离
    7. CCI 超买超卖
    """

    PHASES = ["CONSOLIDATING", "EMERGING", "DEVELOPING", "MATURE", "FATIGUING", "REVERSING"]

    POSITION_MULTIPLIER = {
        "EMERGING": 0.6,
        "DEVELOPING": 1.0,
        "MATURE": 0.5,
        "FATIGUING": 0.0,
        "REVERSING": 0.0,
        "CONSOLIDATING": 0.0,
        "UNKNOWN": 0.0,
    }

    STOP_MULTIPLIER = {
        "EMERGING": 1.5,
        "DEVELOPING": 2.0,
        "MATURE": 1.5,
        "FATIGUING": 1.0,
        "REVERSING": 1.0,
        "CONSOLIDATING": 1.0,
        "UNKNOWN": 2.0,
    }

    phase_params = {
        "fatiguing_adx_threshold": 20,
        "developing_adx_threshold": 30,
        "mature_adx_slope_threshold": -1,
        "emerging_adx_lower": 20,
        "emerging_adx_upper": 30,
    }

    @classmethod
    def set_phase_params(cls, **kwargs):
        for key, value in kwargs.items():
            if key in cls.phase_params:
                cls.phase_params[key] = value

    @classmethod
    def detect(cls, df: pd.DataFrame, market_state: str) -> tuple[str, float, int, dict, list, list]:
        """
        多指标确认的趋势阶段识别

        返回: (phase, phase_confidence, reliability_score, breakdown, alerts, evidence)
        """
        latest = df.iloc[-1]

        # 获取指标值（安全获取）
        def safe(key, default=0):
            val = latest.get(key, default)
            return default if pd.isna(val) else float(val)

        adx = safe("adx")
        adxr = safe("adxr")
        ema20 = safe("ema20")
        ema60 = safe("ema60")

        macd = safe("macd")
        macd_signal = safe("macd_signal")
        macd_hist = safe("macd_hist")
        rsi = safe("rsi")
        stoch_k = safe("stoch_k")
        cci = safe("cci")
        close = safe("close")

        # 计算斜率
        adx_slope = 0
        if len(df) >= 5 and "adx" in df.columns:
            adx_slope = (adx - df["adx"].iloc[-5]) / max(adx, 0.01) * 100 if not pd.isna(df["adx"].iloc[-5]) else 0

        # MACD 柱状线历史
        macd_hist_prev = safe("macd_hist", 0)
        macd_hist_prev3 = df["macd_hist"].iloc[-4] if len(df) >= 4 and "macd_hist" in df.columns else 0

        # 均线间距
        spread_20_60 = abs(ema20 - ema60) / ema60 * 100 if ema60 > 0 else 0

        phase = "CONSOLIDATING"
        phase_confidence = 0.5
        breakdown = {}
        alerts = []
        evidence = []

        # ---- 多指标确认检查 ----

        # 1. 反转期检测（最高优先级）
        if len(df) >= 2:
            price_change = (close - df["close"].iloc[-2]) / df["close"].iloc[-2] * 100
            if abs(price_change) > 3:
                phase = "REVERSING"
                phase_confidence = min(0.95, 0.7 + abs(price_change) / 20)
                evidence.append(f"单日反向{price_change:.1f}%，触发反转检测")
                return phase, phase_confidence, 50, breakdown, alerts, evidence

        # 2. 衰竭期检测（多指标确认）
        fatigue_score = 0
        if adx < cls.phase_params["fatiguing_adx_threshold"]:
            fatigue_score += 1
            evidence.append(f"ADX={adx:.1f}低于阈值{cls.phase_params['fatiguing_adx_threshold']}")
        if adx_slope < -2:
            fatigue_score += 1
            evidence.append(f"ADX斜率={adx_slope:.1f}快速下降")
        if macd_hist * macd_hist_prev < 0:
            fatigue_score += 1
            evidence.append("MACD柱状线变号")
        if rsi < 40 or rsi > 60:
            fatigue_score += 1
            evidence.append(f"RSI={rsi:.0f}偏离中性区")

        if fatigue_score >= 3:
            phase = "FATIGUING"
            phase_confidence = min(0.9, 0.5 + fatigue_score * 0.1)
            evidence.append(f"衰竭信号{fatigue_score}/4")

        # 3. 成熟期检测
        if phase == "CONSOLIDATING":
            mature_score = 0
            if adx >= cls.phase_params["fatiguing_adx_threshold"] + 5:
                mature_score += 1
            if adx_slope < cls.phase_params["mature_adx_slope_threshold"]:
                mature_score += 1
                evidence.append("ADX开始下降")
            if abs(macd_hist) < abs(macd_hist_prev3) * 0.7 if macd_hist_prev3 != 0 else False:
                mature_score += 1
                evidence.append("MACD柱状线收缩")
            if rsi > 70 or rsi < 30:
                mature_score += 1
                evidence.append(f"RSI={rsi:.0f}超买/超卖")

            if mature_score >= 2:
                phase = "MATURE"
                phase_confidence = min(0.85, 0.5 + mature_score * 0.1)
                evidence.append(f"成熟期信号{mature_score}/4")

        # 4. 发展期检测
        if phase == "CONSOLIDATING":
            dev_score = 0
            if adx >= cls.phase_params["developing_adx_threshold"]:
                dev_score += 1
            if adx_slope >= cls.phase_params["mature_adx_slope_threshold"]:
                dev_score += 1
            aligned = (ema20 > ema60) or (ema20 < ema60)
            if aligned:
                dev_score += 1
                evidence.append("均线排列整齐")
            if macd_hist > 0 and macd_hist > macd_hist_prev:
                dev_score += 1
                evidence.append("MACD柱放大")

            if dev_score >= 3:
                phase = "DEVELOPING"
                phase_confidence = min(0.9, 0.6 + dev_score * 0.1)
                evidence.append(f"发展期信号{dev_score}/4")

        # 5. 萌芽期检测
        if phase == "CONSOLIDATING":
            emerge_score = 0
            if cls.phase_params["emerging_adx_lower"] <= adx < cls.phase_params["emerging_adx_upper"]:
                emerge_score += 1
            if adx_slope > 0:
                emerge_score += 1
                evidence.append("ADX上升中")
            if cci > 100 or cci < -100:
                emerge_score += 1
                evidence.append(f"CCI={cci:.0f}突破")
            if stoch_k > 80 or stoch_k < 20:
                emerge_score += 1
                evidence.append(f"STOCH={stoch_k:.0f}极端区")

            if emerge_score >= 2:
                phase = "EMERGING"
                phase_confidence = min(0.85, 0.5 + emerge_score * 0.1)
                evidence.append(f"萌芽期信号{emerge_score}/4")

        # 6. 假突破回退检测
        if phase in ["EMERGING", "DEVELOPING"]:
            if len(df) >= 4:
                dc_upper = df["dc_upper"].iloc[-4] if "dc_upper" in df.columns else close * 1.02
                dc_lower = df["dc_lower"].iloc[-4] if "dc_lower" in df.columns else close * 0.98
                if close < dc_upper and close > dc_lower:
                    # 检查是否在突破后3根K线内回到区间
                    breakout_high = df["high"].iloc[-4] if "dc_upper" in df.columns else 0
                    if close < breakout_high * 0.98:
                        phase = "CONSOLIDATING"
                        phase_confidence = 0.6
                        evidence.append("假突破回退")
                        alerts.append("FALSE_BREAKOUT")

        # 7. 可靠性评分
        reliability_score = cls._calculate_reliability(df, phase, latest)

        breakdown = {
            "phase": phase,
            "adx": adx,
            "adx_slope": adx_slope,
            "ema_spread": spread_20_60,
            "macd_hist": macd_hist,
            "rsi": rsi,
            "cci": cci,
            "stoch_k": stoch_k,
        }

        return phase, phase_confidence, reliability_score, breakdown, alerts, evidence

    @classmethod
    def _calculate_reliability(cls, df: pd.DataFrame, phase: str, latest) -> int:
        """计算趋势可靠性评分（0-100）"""
        score = 0

        def safe(key, default=0):
            val = latest.get(key, default)
            return default if pd.isna(val) else float(val)

        # 1. 趋势强度 (25%)
        adx = safe("adx")
        if adx >= 30:
            score += 25
        elif adx >= 20:
            score += 15
        elif adx >= 15:
            score += 10

        # 2. 均线排列 (20%)
        ema20 = safe("ema20")
        ema60 = safe("ema60")

        if (ema20 > ema60) or (ema20 < ema60):
            score += 20
        elif ema20 > ema60 or ema20 < ema60:
            score += 10

        # 3. 动量健康 (20%)
        macd = safe("macd")
        macd_signal = safe("macd_signal")
        if (macd > macd_signal and macd > 0) or (macd < macd_signal and macd < 0):
            score += 20
        elif macd > macd_signal or macd < macd_signal:
            score += 10

        # 4. RSI 位置 (15%)
        rsi = safe("rsi")
        if 40 <= rsi <= 60:
            score += 15
        elif 30 <= rsi <= 70:
            score += 10
        else:
            score += 5

        # 5. CCI 确认 (10%)
        cci = safe("cci")
        if abs(cci) > 100:
            score += 10
        elif abs(cci) > 50:
            score += 5

        # 6. STOCH 确认 (10%)
        stoch_k = safe("stoch_k")
        if 20 <= stoch_k <= 80:
            score += 10
        else:
            score += 5

        return min(100, score)


# 保持向后兼容的 MarketStateClassifier
class MarketStateClassifier:
    """
    市场状态分类器（兼容旧接口，内部使用 MultiIndicatorConsensus）
    """

    adx_strong_threshold = 25
    adx_weak_threshold = 20
    channel_period = 20
    rsi_period = 14

    @classmethod
    def set_thresholds(cls, adx_strong: int = 25, adx_weak: int = 20, channel_period: int = 20, rsi_period: int = 14):
        cls.adx_strong_threshold = adx_strong
        cls.adx_weak_threshold = adx_weak
        cls.channel_period = channel_period
        cls.rsi_period = rsi_period

    @classmethod
    def classify(cls, df: pd.DataFrame) -> tuple[str, list[str]]:
        """使用多指标共识进行分类"""
        result = MultiIndicatorConsensus.consensus(df)
        return result["state"], result["evidence"]


# ===========================================================================
# 大模型推理层（混合模式）
# ===========================================================================


class LLMReasoningLayer:
    """
    大模型推理层（混合模式）

    核心理念：大模型推理优先，代码执行辅助

    大模型负责：
    - 理解市场含义
    - 综合判断趋势状态
    - 深度分析交易原因
    - 智能调整策略参数

    代码负责：
    - 指标计算
    - 数据处理
    - 参数执行
    - 结果验证

    支持两种大模型接入方式：
    1. 用户传入调用函数（推荐）
    2. 自动检测 WorkBuddy 环境（回退）
    """

    # 允许的状态值
    VALID_STATES = ["STRONG_UPTREND", "STRONG_DOWNTREND", "WEAK_UPTREND", "WEAK_DOWNTREND", "RANGE_BOUND"]

    # 允许的阶段值
    VALID_PHASES = ["CONSOLIDATING", "EMERGING", "DEVELOPING", "MATURE", "FATIGUING", "REVERSING"]

    def __init__(self, use_llm: bool = False):
        """
        初始化大模型推理层

        参数:
            use_llm: 是否启用大模型推理（False时使用纯代码逻辑）
        """
        self.use_llm = use_llm
        self.llm_provider = None
        self.llm_call_count = 0
        self.llm_error_count = 0

    def set_llm_provider(self, provider):
        """
        设置大模型提供者

        支持两种方式：
        1. 传入可调用对象（函数/lambda），签名为 (prompt: str) -> str
        2. 传入对象，需要实现 generate(prompt: str) -> str 方法

        示例:
            # 方式1：传入函数
            def my_llm_call(prompt):
                return "模型返回的JSON字符串"
            llm_layer.set_llm_provider(my_llm_call)

            # 方式2：传入对象
            class MyLLM:
                def generate(self, prompt):
                    return "模型返回的JSON字符串"
            llm_layer.set_llm_provider(MyLLM())
        """
        self.llm_provider = provider

    def _call_llm(self, prompt: str) -> str | None:
        """
        调用大模型

        返回:
            大模型返回的字符串，失败返回None
        """
        if self.llm_provider is None:
            return None

        try:
            self.llm_call_count += 1

            # 支持两种调用方式
            if callable(self.llm_provider):
                # 方式1：可调用对象（函数/lambda）
                result = self.llm_provider(prompt)
            elif hasattr(self.llm_provider, "generate"):
                # 方式2：对象的 generate 方法
                result = self.llm_provider.generate(prompt)
            else:
                print("大模型提供者不支持，需要是可调用对象或有generate方法")
                return None

            return result if isinstance(result, str) else str(result)

        except Exception as e:
            self.llm_error_count += 1
            print(f"大模型调用失败: {e}")
            return None

    def _parse_json_response(self, response: str) -> dict | None:
        """解析大模型返回的JSON"""
        if not response:
            return None

        try:
            # 尝试直接解析
            import json

            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON部分（大模型可能返回包含JSON的文本）
        import re

        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _prepare_market_state_input(self, df: pd.DataFrame) -> str:
        """准备市场状态判断的prompt"""
        latest = df.iloc[-1]

        def safe(key, default=0):
            val = latest.get(key, default)
            return default if pd.isna(val) else float(val)

        # 计算价格行为
        close = safe("close")
        ema20 = safe("ema20")
        ema60 = safe("ema60")

        # 计算成交量比率
        vol_ratio = 1.0
        if "volume" in df.columns and len(df) >= 21:
            vol = safe("volume")
            vol_ma = df["volume"].iloc[-21:].mean()
            if not pd.isna(vol_ma) and vol_ma > 0:
                vol_ratio = vol / vol_ma

        # 计算价格变化
        prev_close = df["close"].iloc[-2] if len(df) >= 2 else close
        price_change = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0

        prompt = f"""你是一个专业的趋势跟踪分析师。请根据以下技术指标，**深度分析**市场状态。

## 当前市场数据

**价格信息**：
- 收盘价: {close:.2f}（日涨跌: {price_change:+.2f}%）
- 在EMA20{"上方" if close > ema20 else "下方"}（距离: {abs(close - ema20) / ema20 * 100:.1f}%）
- 在EMA60{"上方" if close > ema60 else "下方"}（距离: {abs(close - ema60) / ema60 * 100:.1f}%）
- 在EMA60下方（距离: {abs(close - ema60) / ema60 * 100:.1f}%）

**趋势指标**：
- ADX: {safe("adx"):.1f}（>25=有趋势，>40=强趋势）
- ADXR: {safe("adxr"):.1f}
- 均线排列: {"多头(EMA20>EMA60)" if ema20 > ema60 else "空头(EMA20<EMA60)" if ema20 < ema60 else "纠缠"}

**动量指标**：
- RSI: {safe("rsi"):.1f}（>70超买，<30超卖）
- MACD: {safe("macd"):.2f}（信号线: {safe("macd_signal"):.2f}）
- MACD柱: {safe("macd_hist"):.2f}（>0多头动量，<0空头动量）
- CCI: {safe("cci"):.1f}（>100超买，<-100超卖）
- STOCH K: {safe("stoch_k"):.1f}

**成交量**：
- 量比: {vol_ratio:.2f}（>1.2放量，<0.8缩量）

## 你的推理任务

请**不要机械读数**，而是**理解这些指标的含义**：

1. **这些指标在说什么？**（不要只列数字，要解释含义）
2. **市场处于什么状态？**（趋势/震荡/转折）
3. **趋势强度如何？**（强/弱/无）
4. **动量方向是什么？**（多头/空头/中性）
5. **有哪些关键信号？**（启动/延续/反转/衰竭）
6. **有哪些风险？**（超买超卖/背离/假突破）

## 输出格式（JSON）

```json
{{
    "state": "STRONG_UPTREND/STRONG_DOWNTREND/WEAK_UPTREND/WEAK_DOWNTREND/RANGE_BOUND",
    "confidence": 0-100的置信度,
    "reasoning": "详细的推理过程（100字以内，解释指标含义而非列举数字）",
    "key_factors": ["关键因素1", "关键因素2", "关键因素3"],
    "risks": ["风险1", "风险2"],
    "suggestion": "操作建议（50字以内）"
}}
```"""
        return prompt

    def _prepare_trend_phase_input(self, df: pd.DataFrame, market_state: str) -> str:
        """准备趋势阶段识别的prompt"""
        latest = df.iloc[-1]

        def safe(key, default=0):
            val = latest.get(key, default)
            return default if pd.isna(val) else float(val)

        # 计算ADX斜率
        adx = safe("adx")
        adx_prev5 = df["adx"].iloc[-5] if len(df) >= 5 and "adx" in df.columns else adx
        if not pd.isna(adx_prev5) and adx_prev5 > 0:
            adx_slope = (adx - adx_prev5) / adx_prev5 * 100
        else:
            adx_slope = 0

        # 计算通道位置
        close = safe("close")
        dc_upper = safe("dc_upper")
        dc_lower = safe("dc_lower")
        channel_position = (close - dc_lower) / (dc_upper - dc_lower) * 100 if dc_upper > dc_lower else 50

        prompt = f"""你是一个专业的趋势跟踪分析师。请根据以下信息判断趋势所处阶段。

当前市场状态: {market_state}

技术指标：
- ADX: {adx:.1f} (5周期前: {adx_prev5:.1f})
- ADX变化率: {adx_slope:+.1f}%
- EMA20偏离EMA60: {abs(safe("ema20") - safe("ema60")) / safe("ema60") * 100:.2f}%
- MACD柱: {safe("macd_hist"):.2f}
- RSI: {safe("rsi"):.1f}
- CCI: {safe("cci"):.1f}
- STOCH K: {safe("stoch_k"):.1f}
- 通道位置: {channel_position:.0f}%

趋势阶段定义：
- CONSOLIDATING: 震荡期，无明确方向
- EMERGING: 萌芽期，刚突破，最具性价比
- DEVELOPING: 发展期，趋势确认，最佳持仓期
- MATURE: 成熟期，动能衰减，风险增大
- FATIGUING: 衰竭期，失去动力，准备反转
- REVERSING: 反转期，方向改变，旧趋势结束

请判断当前趋势阶段，返回JSON格式：
{{
    "phase": "阶段名称",
    "confidence": 0-100的置信度,
    "reasoning": "你的推理过程（50字以内）",
    "evidence": ["证据1", "证据2", "证据3"],
    "next_phase": "下一个可能的阶段",
    "next_phase_probability": 0-1的概率
}}"""
        return prompt

    def _prepare_attribution_input(self, trade: dict, market_context: dict) -> str:
        """准备归因分析的prompt"""
        prompt = f"""你是一个专业的交易归因分析师。请分析以下交易的成败原因。

交易信息：
- 品种: {trade.get("symbol", "未知")}
- 方向: {trade.get("direction", "未知")}
- 入场价: {trade.get("entry_price", 0)}
- 出场价: {trade.get("exit_price", 0)}
- 盈亏: {trade.get("pnl_pct", 0):.2f}%
- 持仓周期: {trade.get("holding_bars", 0)}根K线
- 出场原因: {trade.get("exit_reason", "未知")}

市场环境：
- 入场时市场状态: {market_context.get("market_state_at_entry", "未知")}
- 入场时趋势阶段: {market_context.get("trend_phase_at_entry", "未知")}

请分析这笔交易，返回JSON格式：
{{
    "result": "WIN/LOSS/BREAKEVEN",
    "strengths": ["做对了什么1", "做对了什么2"],
    "weaknesses": ["做错了什么1", "做错了什么2"],
    "root_cause": "根本原因（30字以内）",
    "improvement": "改进建议（30字以内）",
    "market_regime": "趋势市/震荡市/转折市",
    "strategy_effectiveness": 0-100的策略有效性评分
}}"""
        return prompt

    def _prepare_evolution_input(self, kpi: dict, current_config: dict) -> str:
        """准备进化决策的prompt"""
        prompt = f"""你是一个专业的量化策略优化师。请根据以下绩效数据建议参数调整。

当前绩效：
- 夏普比率: {kpi.get("sharpe_ratio", 0):.2f}
- 胜率: {kpi.get("win_rate", 0):.1f}%
- 盈亏比: {kpi.get("profit_factor", 0):.2f}
- 最大回撤: {kpi.get("max_drawdown", 0):.1f}%
- 总交易次数: {kpi.get("total_trades", 0)}

当前配置：
- 均线周期: {current_config.get("ma_periods", {})}
- 策略权重: {current_config.get("strategy_weights", {})}
- ADX阈值: {current_config.get("adx_threshold", 20)}

请建议参数调整，返回JSON格式：
{{
    "adjustments": [
        {{"param": "参数名", "old": "旧值", "new": "新值", "reason": "调整原因"}}
    ],
    "overall_strategy": "整体策略建议（30字以内）",
    "risk_warning": "风险提示（30字以内）",
    "confidence": 0-100的建议置信度
}}"""
        return prompt

    def validate_market_state(self, result: dict) -> tuple[bool, str]:
        """验证市场状态判断结果"""
        # 1. 状态值验证
        if result.get("state") not in self.VALID_STATES:
            return False, f"无效状态: {result.get('state')}"

        # 2. 置信度验证
        confidence = result.get("confidence", 0)
        if not (0 <= confidence <= 100):
            return False, f"置信度超出范围: {confidence}"

        # 3. 推理过程验证（必须有，且不能太短）
        reasoning = result.get("reasoning", "")
        if not reasoning or len(reasoning) < 20:
            return False, "推理过程过短或缺失（至少20字）"

        # 4. 关键因子验证
        key_factors = result.get("key_factors", [])
        if len(key_factors) < 2:
            return False, f"关键因子不足: {len(key_factors)}"

        # 5. 风险提示验证（可选但建议有）
        risks = result.get("risks", [])
        if len(risks) == 0:
            # 没有风险提示不算错误，但降低置信度
            result["confidence"] = max(0, result.get("confidence", 0) - 10)

        # 6. 操作建议验证（必须有）
        suggestion = result.get("suggestion", "")
        if not suggestion or len(suggestion) < 10:
            return False, "操作建议过短或缺失（至少10字）"

        return True, "验证通过"

    def validate_trend_phase(self, result: dict) -> tuple[bool, str]:
        """验证趋势阶段识别结果"""
        if result.get("phase") not in self.VALID_PHASES:
            return False, f"无效阶段: {result.get('phase')}"
        confidence = result.get("confidence", 0)
        if not (0 <= confidence <= 100):
            return False, f"置信度超出范围: {confidence}"
        evidence = result.get("evidence", [])
        if len(evidence) < 2:
            return False, f"证据不足: {len(evidence)}"
        return True, "验证通过"

    def validate_attribution(self, result: dict) -> tuple[bool, str]:
        """验证归因分析结果"""
        if result.get("result") not in ["WIN", "LOSS", "BREAKEVEN"]:
            return False, f"无效结果: {result.get('result')}"
        if not result.get("root_cause"):
            return False, "缺少根本原因"
        if not result.get("improvement"):
            return False, "缺少改进建议"
        return True, "验证通过"

    def validate_evolution(self, result: dict) -> tuple[bool, str]:
        """验证进化决策结果"""
        adjustments = result.get("adjustments", [])
        if not adjustments:
            return False, "缺少参数调整建议"
        for adj in adjustments:
            if not all(k in adj for k in ["param", "old", "new", "reason"]):
                return False, f"调整项格式错误: {adj}"
        return True, "验证通过"

    def classify_with_llm(self, df: pd.DataFrame) -> dict:
        """使用大模型进行市场状态判断"""
        code_result = MultiIndicatorConsensus.consensus(df)

        if not self.use_llm or self.llm_provider is None:
            return {"code_result": code_result, "llm_result": None, "final_result": code_result, "used_llm": False}

        prompt = self._prepare_market_state_input(df)
        response = self._call_llm(prompt)
        llm_result = self._parse_json_response(response)

        if llm_result is not None:
            is_valid, error_msg = self.validate_market_state(llm_result)
            if is_valid:
                return {
                    "code_result": code_result,
                    "llm_result": llm_result,
                    "final_result": llm_result,
                    "used_llm": True,
                }
            else:
                print(f"大模型结果验证失败: {error_msg}")

        return {"code_result": code_result, "llm_result": llm_result, "final_result": code_result, "used_llm": False}

    def detect_phase_with_llm(self, df: pd.DataFrame, market_state: str) -> dict:
        """使用大模型进行趋势阶段识别"""
        code_result = TrendPhaseDetector.detect(df, market_state)

        if not self.use_llm or self.llm_provider is None:
            return {"code_result": code_result, "llm_result": None, "final_result": code_result, "used_llm": False}

        prompt = self._prepare_trend_phase_input(df, market_state)
        response = self._call_llm(prompt)
        llm_result = self._parse_json_response(response)

        if llm_result is not None:
            is_valid, error_msg = self.validate_trend_phase(llm_result)
            if is_valid:
                return {
                    "code_result": code_result,
                    "llm_result": llm_result,
                    "final_result": llm_result,
                    "used_llm": True,
                }
            else:
                print(f"大模型结果验证失败: {error_msg}")

        return {"code_result": code_result, "llm_result": llm_result, "final_result": code_result, "used_llm": False}

    def analyze_attribution_with_llm(self, trade: dict, market_context: dict) -> dict:
        """使用大模型进行归因分析"""
        # 代码层简单归因
        code_result = {
            "result": "WIN" if trade.get("pnl_pct", 0) > 0 else "LOSS",
            "strengths": [],
            "weaknesses": [],
            "root_cause": "需要大模型深度分析",
            "improvement": "需要大模型深度分析",
            "market_regime": market_context.get("market_state_at_entry", "UNKNOWN"),
            "strategy_effectiveness": 50,
        }

        if not self.use_llm or self.llm_provider is None:
            return {"code_result": code_result, "llm_result": None, "final_result": code_result, "used_llm": False}

        prompt = self._prepare_attribution_input(trade, market_context)
        response = self._call_llm(prompt)
        llm_result = self._parse_json_response(response)

        if llm_result is not None:
            is_valid, error_msg = self.validate_attribution(llm_result)
            if is_valid:
                return {
                    "code_result": code_result,
                    "llm_result": llm_result,
                    "final_result": llm_result,
                    "used_llm": True,
                }
            else:
                print(f"大模型结果验证失败: {error_msg}")

        return {"code_result": code_result, "llm_result": llm_result, "final_result": code_result, "used_llm": False}

    def evolve_with_llm(self, kpi: dict, current_config: dict) -> dict:
        """使用大模型进行进化决策"""
        # 代码层简单建议
        code_result = {
            "adjustments": [],
            "overall_strategy": "需要大模型分析",
            "risk_warning": "需要大模型分析",
            "confidence": 50,
        }
