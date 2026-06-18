"""
上下文组装模块

感知层的核心组件，负责：
1. 计算技术指标
2. 组装 MarketContext
3. 集成基本面分析
4. 集成风险评估（Algometrics）
5. 集成收益归因（KTD-Fin）
6. 集成审计轨迹（TradeArena）
7. 集成V3.0方案（数据质量、幻觉检测、自适应Prompt）
8. 集成多智能体融合框架（三方辩论、论据评估）
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from .models import (
    FundamentalContext,
    IndicatorSnapshot,
    MarketContext,
    MarketStructure,
    MomentumState,
    TrendPhase,
    VolatilityState,
)
from .module_registry import get_module

logger = logging.getLogger(__name__)


class ContextAssembler:
    """
    上下文组装器

    将原始K线数据转换为结构化的 MarketContext，
    供推理层使用。
    """

    def __init__(self, symbol: str, timeframe: str = "daily"):
        """
        初始化上下文组装器

        Args:
            symbol: 品种代码
            timeframe: 时间周期
        """
        self.symbol = symbol
        self.timeframe = timeframe

        # 风险评估器（可选集成）
        self._crowding_detector = None
        self._deployment_risk_estimator = None
        self._return_attributor = None
        self._audit_trail = None
        
        # V3.0 方案模块（可选集成）
        self._conflict_resolver = None
        self._anomaly_weighter = None
        self._hallucination_detector = None
        self._prompt_router = None
        
        # 多智能体融合框架模块（可选集成）
        self._triad_debate_engine = None
        self._evidence_evaluator = None

        self._init_risk_modules()

    def _init_risk_modules(self):
        """初始化风险评估模块和V3.0方案模块"""
        try:
            # 使用模块注册中心加载模块
            self._crowding_detector = get_module("CrowdingDetector")
            self._deployment_risk_estimator = get_module("DeploymentRiskEstimator")
            self._return_attributor = get_module("ReturnAttributor")
            self._audit_trail = get_module("AuditTrail")
            
            # V3.0 方案模块
            self._conflict_resolver = get_module("DataConflictResolver")
            self._anomaly_weighter = get_module("AnomalyWeighter")
            self._hallucination_detector = get_module("HallucinationDetector")
            self._prompt_router = get_module("AdaptivePromptRouter")
            
            # 多智能体融合框架模块
            self._triad_debate_engine = get_module("TriadDebateEngine")
            self._evidence_evaluator = get_module("EvidenceEvaluator")

            logger.info("所有模块加载成功")
        except Exception as e:
            logger.warning(f"部分模块未找到，跳过集成: {e}")

    def assemble(
        self,
        df: pd.DataFrame,
        fundamental: Optional[FundamentalContext] = None,
    ) -> MarketContext:
        """
        组装市场上下文

        Args:
            df: 包含 OHLCV 数据的 DataFrame
            fundamental: 基本面上下文（可选）

        Returns:
            MarketContext: 结构化市场上下文
        """
        # 1. 计算技术指标
        snapshot = self._calculate_indicators(df)

        # 2. 分析市场结构
        structure = self._analyze_structure(df, snapshot)

        # 3. 分析动量状态
        momentum = self._analyze_momentum(snapshot)

        # 4. 分析波动率
        volatility = self._analyze_volatility(df, snapshot)

        # 5. 判断趋势阶段
        trend_phase = self._determine_trend_phase(
            structure, momentum, volatility, df
        )

        # 6. 计算价格行为统计
        price_stats = self._calculate_price_stats(df)

        # 7. 组装 MarketContext
        context = MarketContext(
            symbol=self.symbol,
            timestamp=str(df.index[-1]) if len(df) > 0 else "",
            timeframe=self.timeframe,
            current_price=float(df["close"].iloc[-1]) if len(df) > 0 else 0.0,
            price_change_pct=float(df["close"].pct_change().iloc[-1] * 100)
            if len(df) > 1
            else 0.0,
            structure=structure,
            momentum=momentum,
            volatility=volatility,
            trend_phase=trend_phase,
            snapshot=snapshot,
            bars_since_high=price_stats.get("bars_since_high", 0),
            bars_since_low=price_stats.get("bars_since_low", 0),
            consecutive_up_days=price_stats.get("consecutive_up_days", 0),
            consecutive_down_days=price_stats.get("consecutive_down_days", 0),
            fundamental=fundamental or FundamentalContext(),
        )

        # 8. 集成风险评估（Algometrics）
        context = self._integrate_risk_assessment(context, df)

        return context

    def _calculate_indicators(self, df: pd.DataFrame) -> IndicatorSnapshot:
        """计算技术指标快照"""
        if len(df) == 0:
            return IndicatorSnapshot(
                timestamp="",
                close=0.0,
                high=0.0,
                low=0.0,
                open=0.0,
                volume=0.0,
            )

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["volume"].values

        snapshot = IndicatorSnapshot(
            timestamp=str(df.index[-1]),
            close=float(close[-1]),
            high=float(high[-1]),
            low=float(low[-1]),
            open=float(df["open"].iloc[-1]),
            volume=float(volume[-1]),
        )

        # 简化的指标计算
        snapshot.ema20 = float(self._ema(close, 20)[-1]) if len(close) >= 20 else 0.0
        snapshot.ema60 = float(self._ema(close, 60)[-1]) if len(close) >= 60 else 0.0
        snapshot.rsi = float(self._rsi(close, 14)[-1]) if len(close) >= 15 else 50.0
        snapshot.atr = float(self._atr(high, low, close, 14)[-1]) if len(close) >= 15 else 0.0

        return snapshot

    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """计算EMA"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data, dtype=float)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        return ema

    def _rsi(self, data: np.ndarray, period: int) -> np.ndarray:
        """计算RSI"""
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.zeros(len(data))
        avg_loss = np.zeros(len(data))

        if len(gains) >= period:
            avg_gain[period] = np.mean(gains[:period])
            avg_loss[period] = np.mean(losses[:period])

            for i in range(period + 1, len(data)):
                avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
                avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

        rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100)
        rsi = 100 - 100 / (1 + rs)
        return rsi

    def _atr(
        self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
    ) -> np.ndarray:
        """计算ATR"""
        tr = np.maximum(high[1:] - low[1:], 
                       np.maximum(abs(high[1:] - close[:-1]), 
                                 abs(low[1:] - close[:-1])))
        tr = np.insert(tr, 0, high[0] - low[0])

        atr = np.zeros_like(tr)
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, len(tr)):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        return atr

    def _analyze_structure(
        self, df: pd.DataFrame, snapshot: IndicatorSnapshot
    ) -> MarketStructure:
        """分析市场结构"""
        structure = MarketStructure()

        if len(df) == 0:
            return structure

        close = df["close"].values

        # 均线排列
        if snapshot.ema20 > snapshot.ema60:
            structure.ma_arrangement = "BULLISH"
        elif snapshot.ema20 < snapshot.ema60:
            structure.ma_arrangement = "BEARISH"
        else:
            structure.ma_arrangement = "NEUTRAL"

        # 价格位置
        current_price = close[-1]
        if current_price > snapshot.ema20:
            structure.price_vs_ma = "ABOVE_EMA20"
        elif current_price > snapshot.ema60:
            structure.price_vs_ma = "BETWEEN_EMA"
        else:
            structure.price_vs_ma = "BELOW_EMA60"

        return structure

    def _analyze_momentum(self, snapshot: IndicatorSnapshot) -> MomentumState:
        """分析动量状态"""
        momentum = MomentumState()

        # RSI状态
        if snapshot.rsi > 70:
            momentum.rsi_state = "OVERBOUGHT"
        elif snapshot.rsi < 30:
            momentum.rsi_state = "OVERSOLD"
        else:
            momentum.rsi_state = "NEUTRAL"

        momentum.rsi_value = snapshot.rsi

        return momentum

    def _analyze_volatility(
        self, df: pd.DataFrame, snapshot: IndicatorSnapshot
    ) -> VolatilityState:
        """分析波动率"""
        volatility = VolatilityState()

        if len(df) == 0 or snapshot.atr == 0:
            return volatility

        current_price = df["close"].iloc[-1]
        if current_price > 0:
            volatility.atr_pct = (snapshot.atr / current_price) * 100

        # 波动率状态
        if volatility.atr_pct > 3:
            volatility.regime = "HIGH"
        elif volatility.atr_pct < 1:
            volatility.regime = "LOW"
        else:
            volatility.regime = "NORMAL"

        return volatility

    def _determine_trend_phase(
        self,
        structure: MarketStructure,
        momentum: MomentumState,
        volatility: VolatilityState,
        df: pd.DataFrame,
    ) -> TrendPhase:
        """判断趋势阶段"""
        phase = TrendPhase()

        # 简化的趋势判断
        if structure.ma_arrangement == "BULLISH":
            if momentum.rsi_state == "OVERBOUGHT":
                phase.phase = "MATURE"
                phase.confidence = 0.7
            else:
                phase.phase = "DEVELOPING"
                phase.confidence = 0.6
        elif structure.ma_arrangement == "BEARISH":
            if momentum.rsi_state == "OVERSOLD":
                phase.phase = "FATIGUING"
                phase.confidence = 0.7
            else:
                phase.phase = "DEVELOPING"
                phase.confidence = 0.6
        else:
            phase.phase = "CONSOLIDATING"
            phase.confidence = 0.5

        return phase

    def _calculate_price_stats(self, df: pd.DataFrame) -> dict:
        """计算价格行为统计"""
        stats = {
            "bars_since_high": 0,
            "bars_since_low": 0,
            "consecutive_up_days": 0,
            "consecutive_down_days": 0,
        }

        if len(df) == 0:
            return stats

        close = df["close"].values

        # 距离高点
        high_idx = np.argmax(close)
        stats["bars_since_high"] = len(close) - 1 - high_idx

        # 距离低点
        low_idx = np.argmin(close)
        stats["bars_since_low"] = len(close) - 1 - low_idx

        # 连续上涨/下跌天数
        if len(close) > 1:
            for i in range(len(close) - 1, 0, -1):
                if close[i] > close[i - 1]:
                    stats["consecutive_up_days"] += 1
                else:
                    break

            for i in range(len(close) - 1, 0, -1):
                if close[i] < close[i - 1]:
                    stats["consecutive_down_days"] += 1
                else:
                    break

        return stats

    def _integrate_risk_assessment(
        self, context: MarketContext, df: pd.DataFrame
    ) -> MarketContext:
        """
        集成风险评估、收益归因和V3.0方案

        1. 拥挤度检测（Algometrics）
        2. 部署风险评估（Algometrics）
        3. 收益归因（KTD-Fin）
        4. 审计轨迹记录（TradeArena）
        5. 数据质量评估（V3.0）
        6. 异常值检测（V3.0）
        """
        if self._crowding_detector is None:
            return context

        try:
            # 计算风险指标
            signal = context.trend_phase.confidence * (
                1 if context.structure.ma_arrangement == "BULLISH" else -1
            )
            market_volume = float(df["volume"].iloc[-1]) if len(df) > 0 else 1000
            price_change = context.price_change_pct
            order_flow = signal * market_volume * 0.1  # 简化估算

            # 检测拥挤度
            crowding_metrics = self._crowding_detector.detect(
                signal=signal,
                market_volume=market_volume,
                price_change=price_change,
                order_flow=order_flow,
            )

            # 更新上下文
            context.crowding_score = crowding_metrics.crowding_score
            context.crowding_level = crowding_metrics.level.value

            # 估算部署风险
            if self._deployment_risk_estimator is not None:
                from .risk.deployment_risk import ModelPerformance

                model = ModelPerformance(
                    model_name="current_strategy",
                    historical_accuracy=0.6,
                    signal_strength=abs(signal),
                    trading_frequency=0.5,
                    position_size=0.3,
                )
                assessment = self._deployment_risk_estimator.assess(model)
                context.deployment_risk = assessment.deployment_risk
                context.feedback_gap = assessment.feedback_gap

            # 收益归因（KTD-Fin）
            if self._return_attributor is not None and len(df) > 20:
                portfolio_returns = df["close"].pct_change().dropna()
                market_returns = portfolio_returns  # 简化：使用自身作为市场基准
                attribution = self._return_attributor.attribute(
                    portfolio_returns, market_returns
                )
                context.attribution_market_beta = attribution.market_beta
                context.attribution_style_exposure = attribution.style_exposure
                context.attribution_stock_alpha = attribution.stock_alpha
                context.attribution_r_squared = attribution.r_squared

            # V3.0 方案：数据质量评估
            if self._anomaly_weighter is not None and len(df) > 0:
                anomaly_results = self._anomaly_weighter.batch_detect(df)
                context.anomaly_count = sum(1 for r in anomaly_results if r.is_anomaly)
                
                # 计算数据可信度分数
                normal_count = sum(1 for r in anomaly_results if not r.is_anomaly)
                context.data_credibility_score = normal_count / len(anomaly_results) if anomaly_results else 1.0

            logger.debug(
                f"风险评估完成: 拥挤度={context.crowding_level}, "
                f"部署风险={context.deployment_risk:.3f}, "
                f"选股Alpha={context.attribution_stock_alpha:+.2%}, "
                f"异常数据点={context.anomaly_count}"
                f"选股Alpha={context.attribution_stock_alpha:+.2%}"
            )

        except Exception as e:
            logger.warning(f"风险评估失败: {e}")

        return context

    def create_audit_record(
        self,
        context: MarketContext,
        reasoning: str,
        signal: str,
        confidence: float,
        orders: list,
    ) -> Optional[str]:
        """
        创建审计轨迹记录

        Args:
            context: 市场上下文
            reasoning: 推理过程
            signal: 交易信号
            confidence: 置信度
            orders: 订单列表

        Returns:
            record_id: 审计记录ID
        """
        if self._audit_trail is None:
            return None

        try:
            from scripts.risk.audit_trail import AuditTrailBuilder

            builder = AuditTrailBuilder(self.symbol)
            record = (
                builder
                .set_observation(
                    market_data={"close": context.current_price},
                    indicators={"rsi": context.snapshot.rsi},
                    context=context.to_prompt_text(),
                )
                .set_planning(
                    reasoning=reasoning,
                    signal=signal,
                    confidence=confidence,
                )
                .set_risk_review(
                    risk_checks=[
                        {"crowding_score": context.crowding_score},
                        {"deployment_risk": context.deployment_risk},
                    ],
                    decision="APPROVED" if context.crowding_level != "CRITICAL" else "REJECTED",
                )
                .set_action(
                    orders=orders,
                    mode="SIMULATED",
                )
                .set_reflection(
                    outcome="PENDING",
                )
                .build()
            )

            record_id = self._audit_trail.record(record)
            logger.info(f"审计记录已创建: {record_id}")
            return record_id

        except Exception as e:
            logger.warning(f"创建审计记录失败: {e}")
            return None
