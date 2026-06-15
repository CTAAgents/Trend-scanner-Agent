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


def scan_symbol(symbol: str, data_source, signal_filter: Dict[str, Any], use_dynamic_factors: bool = False) -> Optional[Dict[str, Any]]:
    """
    扫描单个品种，返回信号（如果有）
    
    参数:
        symbol: 品种代码
        data_source: 数据源实例
        signal_filter: 信号筛选条件
    
    返回:
        信号字典，无信号返回 None
    """
    try:
        # 标准化品种代码
        data_symbol = normalize_symbol(symbol)
        
        # 获取 K 线数据
        df = data_source.get_kline(data_symbol, days=120)
        if df is None or len(df) < 60:
            return None
        
        # 计算技术指标
        engine = IndicatorEngine(df)
        engine.compute_all()
        
        # 计算复合趋势强度（compute_all 不包含此步骤）
        composite = engine.get_trend_strength_composite()
        engine.df['trend_strength_composite'] = composite
        
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
        
        # 多头信号筛选
        if direction == "LONG":
            if er < er_min:
                return None
            if tsi < tsi_min:
                return None
            if trend_strength < trend_strength_min:
                return None
            if r_squared < r2_min:
                return None
        
        # 空头信号筛选
        elif direction == "SHORT":
            if er < er_min:
                return None
            if tsi > tsi_max:
                return None
            if trend_strength < trend_strength_min:
                return None
            if r_squared < r2_min:
                return None
        
        # 中性方向不产生信号
        else:
            return None
        
        # 判断趋势阶段
        try:
            trend_phase = TrendPhaseDetector.detect_phase(engine.df)
            phase_str = trend_phase.phase if hasattr(trend_phase, 'phase') else 'UNKNOWN'
        except:
            phase_str = 'UNKNOWN'
        
        # 判断信号强度
        if er > 0.7 and abs(tsi) > 30 and trend_strength > 0.7:
            signal_strength = "STRONG"
        elif er > 0.6 and abs(tsi) > 20:
            signal_strength = "MEDIUM"
        else:
            signal_strength = "WEAK"
        
        # 生成触发原因
        reasons = []
        if er >= er_min:
            reasons.append(f"ER={er:.2f}>={er_min}")
        if abs(tsi) >= abs(tsi_min if direction == "LONG" else tsi_max):
            reasons.append(f"TSI={tsi:.1f}")
        if trend_strength >= trend_strength_min:
            reasons.append(f"趋势强度={trend_strength:.2f}")
        if r_squared >= r2_min:
            reasons.append(f"R²={r_squared:.2f}")
        
        trigger_reason = " 且 ".join(reasons)
        
        return create_signal(
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
    
    except Exception as e:
        print(f"扫描 {symbol} 失败: {e}", file=sys.stderr)
        return None


def scan_all(symbols: List[str] = None) -> Dict[str, Any]:
    """
    扫描所有品种
    
    参数:
        symbols: 品种列表，None 则从配置读取
    
    返回:
        扫描结果字典
    """
    # 加载配置
    config = load_config()
    scanner_config = config.get("scanner", {})
    signal_filter = get_signal_filter()
    
    # 获取品种列表
    if symbols is None:
        symbols = scanner_config.get("symbols", [])
    
    if not symbols:
        print("错误: 未配置扫描品种列表", file=sys.stderr)
        return create_scan_result(0, [])
    
    # 获取数据源
    data_source = DataSourceFactory.create()
    
    # 扫描每个品种
    signals = []
    no_signal_symbols = []
    
    for symbol in symbols:
        result = scan_symbol(symbol, data_source, signal_filter)
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
    
    return scan_result


def main():
    parser = argparse.ArgumentParser(description="期货全品种趋势扫描")
    parser.add_argument("--symbols", type=str, help="品种列表（逗号分隔，如 RB,HC,JM）")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")
    parser.add_argument("--save", action="store_true", help="保存结果到 latest_scan.json")
    
    args = parser.parse_args()
    
    # 解析品种列表
    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    
    # 执行扫描
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始扫描...")
    result = scan_all(symbols)
    
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


if __name__ == "__main__":
    main()
