"""
主扫描器模块

提供趋势扫描和自适应趋势系统功能：
- TrendScanner: 趋势扫描器（集成三层融合架构）
- AdaptiveTrendSystem: 自适应趋势系统
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

import os

from .indicators import IndicatorEngine
from .market_analysis import MultiIndicatorConsensus, TrendPhaseDetector, MarketStateClassifier
from .strategy import StrategyPool
from .risk_management import RiskManager
from .models import TradeSignal, ScoringFeedback
from .data_store import DataStore, ConfigManager

# 延迟导入多维度模块（避免循环依赖 + 数据库路径问题）
_indicator_hub = None
_multi_dimension_screener = None
_md_import_tried = False


def _ensure_md_modules():
    """确保多维度模块已导入（惰性初始化）"""
    global _indicator_hub, _multi_dimension_screener, _md_import_tried
    if _md_import_tried:
        return _indicator_hub is not None

    _md_import_tried = True
    try:
        from .indicator_hub import IndicatorHub
        from .multi_dimension_screener import MultiDimensionScreener

        # 数据库路径推导
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "market.db"
        )
        if not os.path.exists(db_path):
            # 回退到相对路径
            db_path = os.path.join("data", "market.db")

        _indicator_hub = IndicatorHub(db_path=db_path)
        _multi_dimension_screener = MultiDimensionScreener()
        return True
    except ImportError as e:
        print(f"[Scanner] 多维度模块导入失败（DuckDB 不可用？）: {e}", flush=True)
        return False
    except Exception as e:
        print(f"[Scanner] 多维度模块初始化失败: {e}", flush=True)
        return False


class TrendScanner:
    """
    趋势扫描器主类

    集成三层融合架构（工业界标准方案）：
    1. 底层：每个维度分数标准化（Z-score + Winsorize）
    2. 中层：投票过滤共识（MAD异常过滤）
    3. 顶层：加权打分，输出连续仓位信号

    核心理念：
    - 投票保证鲁棒性，打分保留梯度
    - 领先信号优先，确认信号辅助
    - 趋势行情确认后，尽可能早地参与
    """

    def __init__(self, account_equity: float = 1_000_000,
                 risk_per_trade: float = 0.01,
                 point_value: float = 10.0,
                 margin_per_lot: float = 5000.0,
                 strategy_weights: Optional[Dict[str, float]] = None,
                 ma_periods: Optional[Dict[str, int]] = None,
                 data_store: Optional[DataStore] = None):
        self.equity = account_equity
        self.risk_pct = risk_per_trade
        self.point_value = point_value
        self.margin_per_lot = margin_per_lot
        self.strategy_weights = strategy_weights
        self.ma_periods = ma_periods or {'short': 20, 'medium': 60, 'long': 120}
        self.data_store = data_store
        self.config_manager = ConfigManager(data_store) if data_store else None

    def load_data(self, path: str) -> pd.DataFrame:
        df = pd.read_csv(path)
        for col in df.columns:
            if 'date' in col.lower() or 'time' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col])
                    df = df.sort_values(by=col)
                    break
                except Exception:
                    pass
        return df.reset_index(drop=True)

    def analyze(self, df: pd.DataFrame, symbol: str = "UNKNOWN",
                use_multi_dimension: bool = False) -> Dict:
        """
        分析市场状态并生成交易信号

        使用三层融合架构：
        1. 底层：指标标准化
        2. 中层：MAD异常过滤
        3. 顶层：加权打分 + 投票验证

        Args:
            df: OHLCV DataFrame
            symbol: 品种代码（如 'DCE.jm'）
            use_multi_dimension: 是否启用多维度筛选评分（五维度）
                当启用时，额外计算 trend/momentum/volume/volatility/channel
                五维度评分，作为信号的附加置信度证据。

        返回:
            包含信号、仓位、风险参数、三层融合结果的完整字典
        """
        min_bars = self.ma_periods.get('long', 120)
        if len(df) < min_bars:
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'market_state': 'UNKNOWN',
                'signal': 'HOLD',
                'strength': 'NONE',
                'composite_score': 0,
                'score_direction': 0,
                'evidence': [f'数据量不足（需≥{min_bars}根K线）'],
                'position': None,
            }

        # 1. 计算指标
        engine = IndicatorEngine(df, ma_periods=self.ma_periods)
        df = engine.compute_all()
        latest = df.iloc[-1]

        # 2. 市场状态分类
        market_state, state_evidence = MarketStateClassifier.classify(df)

        # 3. 趋势阶段识别
        phase, phase_conf, reliability, breakdown, alerts, phase_evidence = \
            TrendPhaseDetector.detect(df, market_state)

        # 4. 三层融合分析
        consensus_result = MultiIndicatorConsensus.consensus(df)

        # 提取三层融合结果
        composite_score = consensus_result.get('composite_score', 0)
        filtered_composite = consensus_result.get('filtered_composite', composite_score)
        score_direction = consensus_result.get('score_direction', 0)
        dimension_scores = consensus_result.get('dimension_scores', {})
        filtered_dimensions = consensus_result.get('filtered_dimensions', dimension_scores)
        filtered_out = consensus_result.get('filtered_out', [])
        vote_direction = consensus_result.get('direction', 0)
        vote_strength = consensus_result.get('strength', 'none')
        conflict_level = consensus_result.get('conflict_level', 'low')

        # 5. 策略信号生成
        pool = StrategyPool(df, weights=self.strategy_weights)
        signal_str, confidence, votes, vote_evidence = pool.run_all()

        # 6. 基于三层融合调整信号
        # 投票与打分一致 → 高置信度
        # 投票与打分矛盾 → 降低仓位
        if vote_direction == score_direction and vote_direction != 0:
            # 一致：高置信度
            fusion_bonus = 15
            fusion_note = '投票与打分一致→高置信度'
        elif vote_direction != 0 and score_direction != 0 and vote_direction != score_direction:
            # 矛盾：降低仓位
            fusion_bonus = -20
            fusion_note = '投票与打分矛盾→降低仓位'
        else:
            fusion_bonus = 0
            fusion_note = '投票与打分中性'

        # 7. 基于阶段调整信号
        if market_state == 'RANGE_BOUND' or phase in ('FATIGUING', 'REVERSING', 'CONSOLIDATING'):
            signal_str = 'HOLD'
            strength = 'NONE'
            confidence = max(0, confidence - 40)
            if phase == 'FATIGUING':
                vote_evidence.append('趋势进入衰竭期，暂停交易')
            elif phase == 'REVERSING':
                vote_evidence.append('趋势方向可能反转，观望等待')
            else:
                vote_evidence.append('ADX不足/均线纠缠，趋势策略休眠')
        else:
            # 使用打分方向调整信号
            if score_direction == 1 and signal_str == 'SELL':
                signal_str = 'HOLD'
                vote_evidence.append(f'打分方向偏多({filtered_composite:+.2f})，空头信号降级')
            elif score_direction == -1 and signal_str == 'BUY':
                signal_str = 'HOLD'
                vote_evidence.append(f'打分方向偏空({filtered_composite:+.2f})，多头信号降级')

            strength = 'STRONG' if confidence >= 80 else ('MEDIUM' if confidence >= 50 else 'WEAK')

        # 8. 计算仓位
        entry = latest['close']
        atr = latest.get('atr', 0)
        stop = 0.0
        take_profit = 0.0
        lots = 0
        position_pct = 0.0

        if signal_str in ('BUY', 'SELL') and atr > 0:
            direction = 1 if signal_str == 'BUY' else -1
            risk_mgr = RiskManager(self.equity, self.risk_pct)

            # 基于趋势阶段计算动态止损
            stop = risk_mgr.calc_stop_by_phase(entry, atr, direction, phase)

            take_profit = risk_mgr.calc_take_profit(entry, stop, direction)

            # 使用渐进式仓位管理（1/3法则）
            confirmation_level = 0  # 默认初始试探
            if fusion_bonus > 0:
                confirmation_level = 1  # 投票打分一致，趋势确认
            if fusion_bonus > 10 and vote_strength == 'strong':
                confirmation_level = 2  # 强势确认

            lots, actual_risk, margin_used = risk_mgr.calc_progressive_position(
                entry, stop, phase, confirmation_level,
                self.point_value, self.margin_per_lot
            )

            # 基于信号强度、ADX、趋势阶段和可靠性综合调整仓位
            lots = risk_mgr.adjust_by_signal(lots, strength, latest.get('adx', 0))
            lots = risk_mgr.adjust_position_by_phase(lots, phase, reliability)

            # 基于打分调整仓位（连续仓位管理）
            # composite_score 范围 -1 到 +1，映射到 0.5 到 1.5 的仓位倍数
            score_multiplier = 0.5 + abs(filtered_composite)
            score_multiplier = min(1.5, max(0.5, score_multiplier))
            lots = max(1, int(lots * score_multiplier))

            position_pct = (lots * self.margin_per_lot) / self.equity if self.equity > 0 else 0

        all_evidence = state_evidence + vote_evidence + phase_evidence
        if lots == 0 and signal_str in ('BUY', 'SELL'):
            all_evidence.append('计算仓位为0，信号降级为观望')
            signal_str = 'HOLD'
            strength = 'NONE'

        # 9. 构建三层融合报告
        fusion_report = {
            'layer1_standardized': {
                dim_name: {
                    'score': dim['score'],
                    'weight': dim['weight'],
                    'weighted': dim['weighted'],
                    'description': dim['description'],
                }
                for dim_name, dim in dimension_scores.items()
            },
            'layer2_filtered': {
                'filtered_out': filtered_out,
                'remaining_dimensions': list(filtered_dimensions.keys()),
                'mad_threshold': '5x' if any('ATR' in str(e) for e in all_evidence) else '3x',
            },
            'layer3_weighted': {
                'composite_score': composite_score,
                'filtered_composite': filtered_composite,
                'score_direction': score_direction,
                'fusion_bonus': fusion_bonus,
                'fusion_note': fusion_note,
            },
        }

        # 10. 多维度筛选评分（可选，v5.1 新增）
        multi_dimension = None
        if use_multi_dimension and _ensure_md_modules():
            try:
                # 加载指标
                wide_df = _indicator_hub.load(symbol)
                if wide_df is not None and len(wide_df) > 0:
                    # 执行多维度评分
                    md_result = _multi_dimension_screener.score(symbol, wide_df)
                    multi_dimension = md_result.to_dict()

                    # 多维度评分作为附加证据注入
                    md_signal = md_result.signal
                    md_score = md_result.overall_score
                    md_confidence = md_result.confidence

                    # 注入维度明细到证据列表
                    dim_details = [
                        f"{d.name}: {d.composite:+.3f} ({d.direction})"
                        for d in md_result.dimensions
                    ]
                    all_evidence.append(
                        f"[多维度] {symbol} 综合={md_score:+.3f} "
                        f"信号={md_signal} 置信度={md_confidence:.0%} "
                        f"| {' | '.join(dim_details)}"
                    )

                    # 多维度指示成交量结构
                    vol_score = None
                    for d in md_result.dimensions:
                        if d.name == 'volume':
                            vol_score = d.composite
                            break
                    if vol_score is not None:
                        if vol_score > 0.3:
                            all_evidence.append(f"[量能] 成交量结构偏多 (score={vol_score:+.3f})")
                        elif vol_score < -0.3:
                            all_evidence.append(f"[量能] 成交量结构偏空 (score={vol_score:+.3f})")
                        else:
                            all_evidence.append(f"[量能] 成交量结构中性 (score={vol_score:+.3f})")

                    # 如果多维度与信号一致，提升置信度
                    if md_signal == "LONG" and signal_str == "BUY":
                        confidence = min(100, confidence + 5)
                        all_evidence.append(
                            f"[多维度确认] 五维度评分偏多({md_score:+.3f})，与多头信号一致"
                        )
                    elif md_signal == "SHORT" and signal_str == "SELL":
                        confidence = min(100, confidence + 5)
                        all_evidence.append(
                            f"[多维度确认] 五维度评分偏空({md_score:+.3f})，与空头信号一致"
                        )
                    elif md_signal in ("LONG", "SHORT") and signal_str == "HOLD":
                        all_evidence.append(
                            f"[多维度提示] 五维度评分{md_signal}({md_score:+.3f})，"
                            f"但传统信号为HOLD，建议关注"
                        )
                    elif md_signal == "NEUTRAL" and signal_str in ("BUY", "SELL"):
                        all_evidence.append(
                            f"[多维度警告] 五维度评分中性，{signal_str}信号可能不可靠，"
                            f"建议降低仓位或观望"
                        )
                        # 降低置信度
                        if signal_str in ("BUY", "SELL") and strength == "STRONG":
                            strength = "MEDIUM"
                            confidence = max(30, confidence - 15)
                        elif signal_str in ("BUY", "SELL") and strength == "MEDIUM":
                            strength = "WEAK"
                            confidence = max(20, confidence - 10)

            except ValueError as e:
                all_evidence.append(f"[多维度] 指标加载失败: {e}")
            except Exception as e:
                all_evidence.append(f"[多维度] 评分计算异常: {e}")
                import traceback
                traceback.print_exc()

        result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'market_state': market_state,
            'phase': phase,
            'phase_confidence': phase_conf,
            'reliability': reliability,
            'signal': signal_str,
            'strength': strength,
            'confidence': confidence,
            'composite_score': composite_score,
            'filtered_composite': filtered_composite,
            'score_direction': score_direction,
            'vote_direction': vote_direction,
            'conflict_level': conflict_level,
            'fusion_report': fusion_report,
            'multi_dimension': multi_dimension,
            'evidence': all_evidence,
            'alerts': alerts,
            'position': {
                'entry': entry,
                'stop': stop,
                'take_profit': take_profit,
                'lots': lots,
                'position_pct': position_pct,
                'confirmation_level': confirmation_level if signal_str in ('BUY', 'SELL') else 0,
            } if signal_str in ('BUY', 'SELL') else None,
        }

        # 10. 保存到 DataStore（如果可用）
        if self.data_store:
            try:
                self.data_store.save_klines(symbol, df)
                self.data_store.save_signal(symbol, result)

                # 记录打分反馈
                feedback = ScoringFeedback(
                    feedback_id=f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    symbol=symbol,
                    composite_score=composite_score,
                    filtered_composite=filtered_composite,
                    score_direction=score_direction,
                    confidence=confidence,
                    dimension_scores={
                        dim_name: dim['score']
                        for dim_name, dim in dimension_scores.items()
                    },
                    market_state=market_state,
                    trend_phase=phase,
                    volatility_regime=vol_regime if 'vol_regime' in locals() else 'normal',
                )
                self.data_store.save_scoring_feedback(feedback)
            except Exception as e:
                import traceback
                print(f"保存数据失败: {e}")
                traceback.print_exc()

        return result

    def analyze_to_signal(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> TradeSignal:
        """
        分析并返回 TradeSignal 对象（兼容旧接口）
        """
        result = self.analyze(df, symbol)

        pos = result.get('position') or {}

        return TradeSignal(
            symbol=result['symbol'],
            timestamp=result['timestamp'],
            market_state=result['market_state'],
            signal=result['signal'],
            strength=result['strength'],
            supporting_evidence=result['evidence'],
            entry_price=pos.get('entry', 0.0),
            stop_loss=pos.get('stop', 0.0),
            take_profit=pos.get('take_profit', 0.0),
            position_pct=pos.get('position_pct', 0.0),
            confidence_score=result.get('confidence', 0),
        )


class AdaptiveTrendSystem:
    """
    自适应趋势系统

    集成三层融合架构 + 进化系统
    """

    def __init__(self, scanner: TrendScanner = None):
        self.scanner = scanner or TrendScanner()
        self.trades = []
        self.config = {}

    def run_cycle(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict:
        """
        运行一个完整的交易周期

        流程：
        1. 三层融合分析
        2. 生成信号
        3. 执行交易（模拟）
        4. 记录结果
        5. 进化调整
        """
        # 1. 分析
        result = self.scanner.analyze(df, symbol)

        # 2. 记录
        self.trades.append(result)

        return result

    def get_evolution_status(self) -> Dict:
        """获取进化状态"""
        return {
            'total_trades': len(self.trades),
            'trades': self.trades[-10:] if self.trades else [],
        }
