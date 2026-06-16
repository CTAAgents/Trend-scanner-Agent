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
    
    args = parser.parse_args()
    
    # 解析品种列表
    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    
    # 执行扫描
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始扫描...")
    result = scan_all(symbols, use_dynamic_factors=args.use_dynamic_factors)
    
    # 输出结果
    if args.output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"扫描完成: {result['total_scanned']} 个品种")
        print(f"发现信号: {result['signal_count']} 个")
        print("-" * 60)
        
        if result['signals']:
            for sig in result['signals']:
                print(f"  {sig['symbol']:<20} {sig['direction']:<8} {sig['signal_strength']:<8} "
                      f"ER={sig['er']:.2f} TSI={sig['tsi']:.1f} R²={sig['r_squared']:.2f}")
                print(f"    原因: {sig['trigger_reason']}")
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


if __name__ == "__main__":
    main()
