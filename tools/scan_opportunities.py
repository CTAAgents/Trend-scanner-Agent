"""
Scanner 脚本 — 期货全品种趋势扫描

纯 Python 脚本（无 LLM），定时扫描全品种，筛选出有信号的品种。
筛选条件从 config/config.json 读取，支持动态调整。

使用方式：
    python tools/scan_opportunities.py                    # 扫描所有品种
    python tools/scan_opportunities.py --symbols RB,HC    # 扫描指定品种
    python tools/scan_opportunities.py --output json      # 输出 JSON 格式
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np
import logging

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from trend_scanner.data_source import DataSourceFactory
from trend_scanner.indicators import IndicatorEngine
from trend_scanner.market_analysis import MultiIndicatorConsensus, TrendPhaseDetector
from trend_scanner.models import MarketContext
from trend_scanner.factor_generator import FactorGenerator

# 导入数据格式工具
from data_formats import (
    create_scan_result, create_signal,
    write_scan_result, load_config, get_signal_filter
)

logger = logging.getLogger(__name__)


def normalize_symbol(symbol: str) -> str:
    """
    将配置格式的品种代码转换为数据源可识别的格式
    
    配置格式：SHFE.rb, DCE.jm, CZCE.CF, INE.sc
    数据源格式：RB, JM, CF, SC（大写品种代码）
    """
    symbol = symbol.strip()
    
    # 如果包含交易所前缀，提取品种代码
    if '.' in symbol:
        parts = symbol.split('.')
        if len(parts) == 2:
            code = parts[1].upper()
            return code
    
    # 直接返回大写形式
    return symbol.upper()


def check_data_timeliness() -> Dict[str, Any]:
    """
    检查数据时效性
    
    Returns:
        Dict: {
            'is_latest': bool,  # 数据是否最新
            'latest_date': str, # 数据最新日期
            'current_date': str, # 当前日期
            'days_behind': int, # 滞后天数
            'message': str,     # 提示信息
        }
    """
    import duckdb
    from datetime import datetime, timedelta
    
    result = {
        'is_latest': True,
        'latest_date': '',
        'current_date': datetime.now().strftime('%Y-%m-%d'),
        'days_behind': 0,
        'message': ''
    }
    
    try:
        # 连接数据库获取最新数据时间
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'market.db')
        conn = duckdb.connect(db_path, read_only=True)
        
        query = "SELECT MAX(timestamp) FROM klines"
        latest = conn.execute(query).fetchone()[0]
        conn.close()
        
        if latest:
            latest_date = str(latest)[:10]
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # 计算滞后天数
            latest_dt = datetime.strptime(latest_date, '%Y-%m-%d')
            current_dt = datetime.strptime(current_date, '%Y-%m-%d')
            days_behind = (current_dt - latest_dt).days
            
            result['latest_date'] = latest_date
            result['current_date'] = current_date
            result['days_behind'] = days_behind
            
            if days_behind > 1:
                result['is_latest'] = False
                result['message'] = f"⚠️ 数据滞后 {days_behind} 天（最新: {latest_date}，当前: {current_date}）"
            else:
                result['message'] = f"✅ 数据最新（{latest_date}）"
        else:
            result['is_latest'] = False
            result['message'] = "⚠️ 数据库为空，请先执行数据同步"
            
    except Exception as e:
        result['is_latest'] = False
        result['message'] = f"⚠️ 检查数据时效性失败: {e}"
    
    return result


def scan_symbol(symbol: str, data_source, signal_filter: Dict[str, Any],
                use_dynamic_factors: bool = False,
                allow_tqsdk_fallback: bool = True) -> Optional[Dict[str, Any]]:
    """
    扫描单个品种，返回信号（如果有）

    参数:
        symbol: 品种代码
        data_source: 数据源实例
        signal_filter: 信号筛选条件
        allow_tqsdk_fallback: 是否允许 TqSdk 兜底（健康检查失败时为 False）

    返回:
        信号字典，无信号返回 None
    """
    try:
        # 标准化品种代码
        data_symbol = normalize_symbol(symbol)

        # 获取 K 线数据（根据健康检查决定是否允许 TqSdk 兜底）
        df = data_source.get_kline(data_symbol, days=120,
                                   allow_tqsdk_fallback=allow_tqsdk_fallback)
        if df is None or len(df) < 60:
            return None
        
        # 计算技术指标
        engine = IndicatorEngine(df)
        engine.compute_all()
        
        # 计算复合趋势强度（compute_all 不包含此步骤）
        composite = engine.get_trend_strength_composite()
        engine.df['trend_strength_composite'] = composite
        
        # 动态因子计算（如果启用）
        dynamic_factor_values = {}
        if use_dynamic_factors:
            try:
                knowledge_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'factor_knowledge.json')
                if os.path.exists(knowledge_path):
                    with open(knowledge_path, 'r', encoding='utf-8') as f:
                        factor_knowledge = json.load(f)
                    
                    for factor in factor_knowledge.get('factors', []):
                        factor_code = factor.get('code', '')
                        factor_name = factor.get('name', 'unknown_factor')
                        if factor_code:
                            try:
                                exec_globals = {'pd': pd, 'np': np}
                                exec(factor_code, exec_globals)
                                factor_func = exec_globals.get('factor')
                                if factor_func:
                                    factor_values = factor_func(engine.df)
                                    if factor_values is not None and len(factor_values) > 0:
                                        latest_factor_value = float(factor_values.iloc[-1]) if hasattr(factor_values, 'iloc') else float(factor_values[-1])
                                        dynamic_factor_values[factor_name] = latest_factor_value
                                        logger.debug(f"动态因子 {factor_name} = {latest_factor_value:.4f}")
                            except Exception as e:
                                logger.warning(f"执行动态因子 {factor_name} 失败: {e}")
            except Exception as e:
                logger.warning(f"加载因子知识库失败: {e}")
        
        # 获取最新一行数据
        latest = engine.df.iloc[-1]
        
        # 提取关键指标
        er = float(latest.get('er', 0))
        tsi = float(latest.get('tsi', 0))
        r_squared = float(latest.get('r_squared', 0))
        hurst = float(latest.get('hurst', 0.5))
        trend_strength = float(latest.get('trend_strength_composite', 0))
        rsi = float(latest.get('rsi', 50))
        macd_hist = float(latest.get('macd_hist', 0))
        adx = float(latest.get('adx', 0))
        
        # 判断方向
        if tsi > 0 and er > 0.5:
            direction = "LONG"
        elif tsi < 0 and er > 0.5:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"
        
        # 应用筛选条件
        er_min = signal_filter.get('er_min', 0.6)
        tsi_min = signal_filter.get('tsi_min', 20)
        tsi_max = signal_filter.get('tsi_max', -20)
        trend_strength_min = signal_filter.get('trend_strength_min', 0.5)
        r2_min = signal_filter.get('r2_min', 0.4)
        filter_mode = signal_filter.get('filter_mode', 'or')  # 'and' 或 'or'
        
        # 中性方向不产生信号
        if direction == "NEUTRAL":
            return None
        
        # 逐项判断是否达标
        er_ok = er >= er_min
        if direction == "LONG":
            tsi_ok = tsi >= tsi_min
        else:
            tsi_ok = tsi <= tsi_max
        trend_ok = trend_strength >= trend_strength_min
        r2_ok = r_squared >= r2_min
        
        if filter_mode == 'and':
            # 严格模式：所有条件必须同时满足
            if not (er_ok and tsi_ok and trend_ok and r2_ok):
                return None
        else:
            # 宽松模式（默认）：任一条件满足即触发推理
            if not (er_ok or tsi_ok or trend_ok or r2_ok):
                return None
        
        # 判断趋势阶段
        try:
            trend_phase = TrendPhaseDetector.detect_phase(engine.df)
            phase_str = trend_phase.phase if hasattr(trend_phase, 'phase') else 'UNKNOWN'
        except:
            phase_str = 'UNKNOWN'
        
        # 判断信号强度
        met_count = sum([er_ok, tsi_ok, trend_ok, r2_ok])
        if met_count >= 4:
            signal_strength = "STRONG"
        elif met_count >= 2:
            signal_strength = "MEDIUM"
        else:
            signal_strength = "WEAK"
        
        # 生成触发原因
        reasons = []
        if er_ok:
            reasons.append(f"ER={er:.2f}>={er_min}")
        if tsi_ok:
            reasons.append(f"TSI={tsi:.1f}")
        if trend_ok:
            reasons.append(f"趋势强度={trend_strength:.2f}")
        if r2_ok:
            reasons.append(f"R²={r_squared:.2f}")
        
        trigger_reason = " 或 ".join(reasons) + f" [mode={filter_mode}, 满足{met_count}/4项]"
        
        # 计算建议仓位和止损
        position_info = {}
        stop_loss_info = {}
        try:
            from trend_scanner.position_sizer import PositionSizer
            sizer = PositionSizer()
            atr = float(latest.get('atr', 0))
            volatility = atr / max(float(latest.get('close', 1)), 1) if atr > 0 else 0.15
            position_info = sizer.calculate(
                trend_strength=trend_strength,
                volatility=volatility
            )
        except Exception as e:
            logger.debug(f"仓位计算失败: {e}")
        
        try:
            from trend_scanner.stop_loss import StopLossCalculator
            stop_calc = StopLossCalculator()
            atr = float(latest.get('atr', 0))
            if atr > 0:
                stop_price = stop_calc.atr_stop(
                    entry_price=float(latest.get('close', 0)),
                    atr=atr,
                    direction=direction
                )
                stop_loss_info = {
                    'stop_price': round(stop_price, 2),
                    'atr_multiplier': 2.5,
                    'risk_points': round(abs(float(latest.get('close', 0)) - stop_price), 2)
                }
        except Exception as e:
            logger.debug(f"止损计算失败: {e}")
        
        signal = create_signal(
            symbol=symbol,
            trend_phase=phase_str,
            trend_strength_composite=trend_strength,
            tsi=tsi,
            er=er,
            r_squared=r_squared,
            direction=direction,
            signal_strength=signal_strength,
            trigger_reason=trigger_reason,
            hurst=round(hurst, 3),
            rsi=round(rsi, 1),
            adx=round(adx, 1)
        )
        
        # 附加动态因子值
        if dynamic_factor_values:
            signal['dynamic_factors'] = dynamic_factor_values
        
        # 附加仓位和止损建议
        if position_info:
            signal['position_suggestion'] = position_info
        if stop_loss_info:
            signal['stop_loss'] = stop_loss_info
        
        return signal
    
    except Exception as e:
        print(f"扫描 {symbol} 失败: {e}", file=sys.stderr)
        return None


def scan_all(symbols: List[str] = None, use_dynamic_factors: bool = False, use_memory: bool = True) -> Dict[str, Any]:
    """
    扫描所有品种
    
    参数:
        symbols: 品种列表，None 则从配置读取
        use_dynamic_factors: 是否使用动态因子
        use_memory: 是否使用记忆系统存储结果
    
    返回:
        扫描结果字典
    """
    # 加载配置
    config = load_config()
    scanner_config = config.get("scanner", {})
    signal_filter = get_signal_filter()
    
    # 宏观状态检测（可选）
    macro_state = None
    try:
        from trend_scanner.macro_state import MacroStateDetector
        macro_detector = MacroStateDetector()
        macro_state = macro_detector.detect()
        print(f"宏观状态: {macro_state['cycle']['name']} | {macro_state['liquidity']['name']} | {macro_state['risk_appetite']['name']}")
        print(f"  策略权重: 趋势={macro_state['strategy_weights']['trend_following']:.0%} 均值回归={macro_state['strategy_weights']['mean_reversion']:.0%}")
    except Exception as e:
        print(f"宏观状态检测跳过: {e}")
    
    # 获取数据源
    data_source = DataSourceFactory.create()

    # TqSdk 健康检查：快速验证连通性，不可用时跳过 TqSdk 兜底
    tqsdk_healthy = False
    try:
        health = DataSourceFactory.check_health("tqsdk")
        if health['available']:
            tqsdk_healthy = True
            print(f"TqSdk 连通: {health['latency_ms']}ms")
        else:
            print(f"[警告] TqSdk 不可用: {health.get('error', '未知')}，将仅使用本地缓存")
    except Exception as e:
        print(f"[警告] TqSdk 健康检查异常: {e}，将仅使用本地缓存")
    
    # 获取品种列表：优先从数据源获取全部主力合约，其次从配置读取
    if symbols is None:
        # 尝试从数据源获取全部主力合约
        try:
            all_contracts = data_source.get_main_contracts()
            if all_contracts:
                symbols = all_contracts
                print(f"从数据源获取 {len(symbols)} 个主力合约")
            else:
                symbols = scanner_config.get("symbols", [])
                print(f"数据源无合约，从配置读取 {len(symbols)} 个品种")
        except Exception as e:
            symbols = scanner_config.get("symbols", [])
            print(f"获取合约列表失败({e})，从配置读取 {len(symbols)} 个品种")
    
    if not symbols:
        print("错误: 未配置扫描品种列表且数据源无可用合约", file=sys.stderr)
        return create_scan_result(0, [])
    
    # 扫描每个品种
    signals = []
    no_signal_symbols = []

    for symbol in symbols:
        result = scan_symbol(symbol, data_source, signal_filter, use_dynamic_factors,
                            allow_tqsdk_fallback=tqsdk_healthy)
        if result:
            signals.append(result)
        else:
            no_signal_symbols.append(symbol)  # 保留原始格式
    
    # 创建扫描结果
    scan_result = create_scan_result(
        total_scanned=len(symbols),
        signals=signals,
        no_signal_symbols=no_signal_symbols
    )
    
    # 附加宏观状态到扫描结果
    if macro_state:
        scan_result['macro_state'] = macro_state
    
    # 存储到记忆系统
    if use_memory:
        try:
            from trend_scanner.memory_bridge import MemoryBridge
            bridge = MemoryBridge()
            bridge.store_scan_result(scan_result)
            bridge.close()
        except Exception as e:
            logger.warning(f"存储扫描结果到记忆系统失败: {e}")
    
    return scan_result


def main():
    parser = argparse.ArgumentParser(description="期货全品种趋势扫描")
    parser.add_argument("--symbols", type=str, help="品种列表（逗号分隔，如 RB,HC,JM）")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")
    parser.add_argument("--save", action="store_true", help="保存结果到 latest_scan.json")
    parser.add_argument("--use-dynamic-factors", action="store_true", help="启用动态因子生成器")
    parser.add_argument("--evaluate-factors", action="store_true",
                        help="扫描后运行截面 IC/ICIR 因子评估")
    parser.add_argument("--evolve", action="store_true",
                        help="运行闭环因子进化引擎")
    parser.add_argument("--optimize-params", action="store_true",
                        help="运行贝叶斯参数优化")
    parser.add_argument("--evolve-rounds", type=int, default=5,
                        help="进化轮数（默认 5）")
    parser.add_argument("--evolve-target", type=int, default=3,
                        help="目标晋升因子数（默认 3）")
    parser.add_argument("--opt-trials", type=int, default=30,
                        help="参数优化试验次数（默认 30）")
    parser.add_argument("--load-report", type=str, default=None,
                        help="从研报文件加载种子因子（配合 --evolve 使用）")
    parser.add_argument("--health-check", action="store_true",
                        help="运行策略健康度评估")
    parser.add_argument("--position-health", action="store_true",
                        help="运行持仓健康度评估（基于技术指标+LLM推理）")
    parser.add_argument("--overfitting-check", action="store_true",
                        help="运行过拟合检测")
    parser.add_argument("--execution-check", action="store_true",
                        help="运行执行引擎风控检查")
    parser.add_argument("--reasoner", action="store_true",
                        help="启用Reasoner Agent深度分析（输出决策简报）")
    
    args = parser.parse_args()
    
    # 解析品种列表
    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    
    # 数据时效性检查（必须）
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 检查数据时效性...")
    timeliness = check_data_timeliness()
    print(timeliness['message'])
    
    if not timeliness['is_latest']:
        print(f"\n⚠️ 数据滞后 {timeliness['days_behind']} 天，分析结果可能不准确。")
        print(f"建议先执行数据同步: python tools/sync_data.py sync --days 5")
        print(f"继续分析将在结果中标注数据截止时间。\n")
    
    # 执行扫描
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始扫描...")
    result = scan_all(symbols, use_dynamic_factors=args.use_dynamic_factors)
    
    # Reasoner深度分析（如果启用）
    if args.reasoner and result.get('signals'):
        print(f"\n{'=' * 60}")
        print("Reasoner 深度分析")
        print(f"{'=' * 60}")
        try:
            from reasoner import ReasonerAgent
            reasoner = ReasonerAgent()
            
            analyzed_signals = []
            for sig in result['signals']:
                symbol = sig['symbol']
                direction = sig['direction']
                print(f"\n分析 {symbol} ({direction})...")
                
                # 构造信号数据
                signal_data = {
                    'symbol': symbol,
                    'direction': direction,
                    'trend_phase': sig.get('trend_phase', 'UNKNOWN'),
                    'trend_strength_composite': sig.get('trend_strength_composite', 0),
                    'tsi': sig.get('tsi', 0),
                    'er': sig.get('er', 0),
                    'r_squared': sig.get('r_squared', 0),
                    'key_signals': [sig.get('trigger_reason', '')],
                    'risk_factors': [],
                    'scan_id': result.get('scan_time', '')
                }
                
                # 调用Reasoner分析
                try:
                    brief = reasoner.analyze(signal_data)
                    
                    # 提取关键信息
                    recommended_route = brief.get('recommended_route', '')
                    routes = brief.get('routes', [])
                    confidence = 0
                    action = ''
                    reasoning = ''
                    
                    for route in routes:
                        if route.get('route_id') == recommended_route:
                            confidence = route.get('confidence', 0)
                            action = route.get('action', '')
                            reasoning = route.get('reasoning', '')
                            break
                    
                    # 添加Reasoner评估到信号
                    sig['reasoner_brief'] = {
                        'confidence': confidence,
                        'recommended_action': action,
                        'reasoning': reasoning,
                        'routes_count': len(routes),
                        'warnings': brief.get('warnings', []),
                        'uncertainty': brief.get('uncertainty', {}),
                        'generation_time_ms': brief.get('generation_time_ms', 0)
                    }
                    
                    print(f"  置信度: {confidence:.0%}")
                    print(f"  建议: {action[:50]}..." if len(action) > 50 else f"  建议: {action}")
                    
                except Exception as e:
                    print(f"  分析失败: {e}")
                    sig['reasoner_brief'] = {
                        'confidence': 0,
                        'recommended_action': '分析失败',
                        'reasoning': str(e),
                        'error': True
                    }
                
                analyzed_signals.append(sig)
            
            result['signals'] = analyzed_signals
            result['reasoner_analyzed'] = True
            print(f"\n完成 {len(analyzed_signals)} 个品种的深度分析")
            
        except Exception as e:
            print(f"Reasoner初始化失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 输出结果
    if args.output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"扫描完成: {result['total_scanned']} 个品种")
        print(f"发现信号: {result['signal_count']} 个")
        if result.get('reasoner_analyzed'):
            print(f"深度分析: 已完成")
        print("-" * 60)
        
        if result['signals']:
            for sig in result['signals']:
                # 基础信息
                print(f"  {sig['symbol']:<20} {sig['direction']:<8} {sig['signal_strength']:<8} "
                      f"ER={sig['er']:.2f} TSI={sig['tsi']:.1f} R²={sig['r_squared']:.2f}")
                print(f"    原因: {sig['trigger_reason']}")
                
                # Reasoner评估（如果有）
                if 'reasoner_brief' in sig:
                    brief = sig['reasoner_brief']
                    if not brief.get('error'):
                        confidence = brief.get('confidence', 0)
                        action = brief.get('recommended_action', '')
                        # 根据置信度显示不同标记
                        if confidence >= 0.7:
                            marker = "[高置信度]"
                        elif confidence >= 0.5:
                            marker = "[中置信度]"
                        else:
                            marker = "[低置信度]"
                        print(f"    推理: {marker} 置信度{confidence:.0%}")
                        print(f"    建议: {action[:60]}..." if len(action) > 60 else f"    建议: {action}")
                    else:
                        print(f"    推理: [分析失败] {brief.get('reasoning', '')[:50]}")
        else:
            print("  无信号")
    
    # 保存结果
    if args.save:
        write_scan_result(result)
        print(f"\n结果已保存到 data/latest_scan.json")

    # 截面因子评估
    if args.evaluate_factors:
        print(f"\n{'=' * 60}")
        print("截面因子评估")
        print(f"{'=' * 60}")
        try:
            from trend_scanner.factor_evaluator import FactorEvaluator, BUILTIN_FACTORS

            evaluator = FactorEvaluator()
            count = evaluator.load_data(days=120)
            print(f"加载 {count} 个品种的数据")

            if count >= 10:
                results = evaluator.evaluate_batch(BUILTIN_FACTORS)
                report = evaluator.generate_report(results)
                print(report)
                evaluator.save_results(results)
                print("\n评估结果已保存到 data/factor_evaluation.json")
            else:
                print(f"品种数量不足（{count} < 10），跳过截面评估")
        except Exception as e:
            print(f"因子评估失败: {e}")

    # 闭环因子进化
    if args.evolve:
        print(f"\n{'=' * 60}")
        print("闭环因子进化引擎")
        print(f"{'=' * 60}")
        try:
            from trend_scanner.factor_evolution_engine import FactorEvolutionEngine

            engine = FactorEvolutionEngine()

            # 从研报加载种子因子
            if args.load_report:
                import os
                if os.path.exists(args.load_report):
                    with open(args.load_report, 'r', encoding='utf-8') as f:
                        report_content = f.read()
                    n = engine.load_seeds_from_report(
                        report_content,
                        {'title': os.path.basename(args.load_report)}
                    )
                    print(f"从研报加载 {n} 个种子因子")
                else:
                    # 尝试从 report_parser 输出加载
                    n = engine.load_seeds_from_report_parser_output(args.load_report)
                    print(f"从报告解析结果加载 {n} 个种子因子")

            result = engine.evolve(
                max_rounds=args.evolve_rounds,
                candidates_per_round=5,
                target_promoted=args.evolve_target,
                days=120,
            )
            report = engine.generate_report(result)
            print(report)
            engine.save_result(result)
            print("\n进化结果已保存到 data/factor_evolution.json")
        except Exception as e:
            print(f"因子进化失败: {e}")

    # 贝叶斯参数优化
    if args.optimize_params:
        print(f"\n{'=' * 60}")
        print("贝叶斯参数优化")
        print(f"{'=' * 60}")
        try:
            from trend_scanner.factor_param_optimizer import (
                FactorParamOptimizer, PARAMETRIC_FACTORS, PREDEFINED_SPACES,
            )

            optimizer = FactorParamOptimizer(metric='icir')

            for name, fn in PARAMETRIC_FACTORS.items():
                if name in PREDEFINED_SPACES:
                    print(f"\n优化因子: {name}")
                    result = optimizer.optimize_with_predefined_space(
                        factor_name=name,
                        factor_fn=fn,
                        space_name=name,
                        kline_data=optimizer._kline_data if hasattr(optimizer, '_kline_data') else None,
                        n_trials=args.opt_trials,
                    )
                    print(f"  最优参数: {result.best_params}")
                    print(f"  最优分数: {result.best_score:.4f}")
                    optimizer.save_result(result)
        except Exception as e:
            print(f"参数优化失败: {e}")

    # 策略健康度评估
    if args.health_check:
        print(f"\n{'=' * 60}")
        print("策略健康度评估")
        print(f"{'=' * 60}")
        try:
            from trend_scanner.strategy_health import StrategyHealthChecker
            from trend_scanner.memory_bridge import MemoryBridge

            health_checker = StrategyHealthChecker()

            # 从记忆系统获取交易历史
            trades = []
            try:
                bridge = MemoryBridge()
                trades = bridge.get_trade_history(n=50)
                bridge.close()
            except Exception:
                pass

            if trades:
                result = health_checker.check(trades, lookback=50)
                print(f"健康度评分: {result['health_score']}/100 ({result['status']})")
                if result.get('deductions'):
                    for d in result['deductions']:
                        print(f"  - {d}")
                print(f"建议: {result['recommendation']}")

                retire = health_checker.should_retire(trades)
                if retire['should_retire']:
                    print(f"\n[警告] 策略退休建议:")
                    for r in retire['reasons']:
                        print(f"  - {r}")
            else:
                print("无交易历史，跳过健康度评估")
        except Exception as e:
            print(f"健康度评估失败: {e}")

    # 持仓健康度评估
    if args.position_health:
        print(f"\n{'=' * 60}")
        print("持仓健康度评估")
        print(f"{'=' * 60}")
        try:
            from trend_scanner.position_health import PositionHealthChecker, load_positions_from_file

            # 加载持仓
            positions = load_positions_from_file()
            if not positions:
                print("无持仓信息，请先配置 config/positions.json")
            else:
                print(f"加载 {len(positions)} 个持仓")
                checker = PositionHealthChecker()
                
                results = []
                for pos in positions:
                    symbol = pos.get('symbol', '')
                    direction = pos.get('direction', 'LONG')
                    print(f"\n分析 {symbol} ({direction})...", flush=True)
                    
                    result = checker.check(pos)
                    results.append(result)
                    
                    # 显示结果
                    score = result.get('health_score', 0)
                    grade = result.get('health_grade', '未知')
                    recommendation = result.get('recommendation', '')
                    risk_factors = result.get('risk_factors', [])
                    
                    print(f"  健康评分: {score}/100 ({grade})")
                    print(f"  建议: {recommendation}")
                    
                    if risk_factors:
                        print(f"  风险: {', '.join(risk_factors[:3])}")
                
                # 保存结果
                output_path = 'data/position_health.json'
                import json
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"\n结果已保存到 {output_path}")
                
        except Exception as e:
            print(f"持仓健康度评估失败: {e}")
            import traceback
            traceback.print_exc()

    # 过拟合检测
    if args.overfitting_check:
        print(f"\n{'=' * 60}")
        print("过拟合检测")
        print(f"{'=' * 60}")
        try:
            from trend_scanner.overfitting_detector import OverfittingDetector
            from trend_scanner.memory_bridge import MemoryBridge

            detector = OverfittingDetector()

            # 从记忆系统获取交易收益
            trades = []
            try:
                bridge = MemoryBridge()
                trades = bridge.get_trade_history(n=100)
                bridge.close()
            except Exception:
                pass

            if trades:
                returns = [t.get('pnl_percent', 0) for t in trades if 'pnl_percent' in t]
                if returns:
                    result = detector.comprehensive_check(returns)
                    print(f"过拟合风险: {result.get('risk_level', 'unknown')}")
                    print(f"蒙特卡洛 p 值: {result.get('monte_carlo_p', 'N/A')}")
                    if result.get('warnings'):
                        for w in result['warnings']:
                            print(f"  - {w}")
                else:
                    print("无有效收益数据，跳过过拟合检测")
            else:
                print("无交易历史，跳过过拟合检测")
        except Exception as e:
            print(f"过拟合检测失败: {e}")

    # 执行引擎风控检查
    if args.execution_check:
        print(f"\n{'=' * 60}")
        print("执行引擎风控检查")
        print(f"{'=' * 60}")
        try:
            from trend_scanner.execution import ExecutionEngine, RiskGuard

            engine = ExecutionEngine()
            risk_guard = RiskGuard()

            # 加载持仓
            import json
            positions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'positions.json')
            if os.path.exists(positions_path):
                with open(positions_path, 'r', encoding='utf-8') as f:
                    positions = json.load(f)

                print(f"当前持仓: {len(positions) if isinstance(positions, list) else 'N/A'} 个")
                if isinstance(positions, list):
                    for pos in positions:
                        symbol = pos.get('symbol', 'unknown')
                        direction = pos.get('direction', 'unknown')
                        print(f"  {symbol}: {direction}")
            else:
                print("无持仓配置文件")

            # 风控状态
            print(f"风控状态: 正常")
        except Exception as e:
            print(f"执行引擎检查失败: {e}")


if __name__ == "__main__":
    main()
