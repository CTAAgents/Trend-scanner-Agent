"""
Monitor 脚本 — 持仓风险详细分析

读取 positions.json，对每个持仓品种进行详细的风险分析。
输出风险评估报告，包括趋势状态、关键指标、预警信号。

与 heartbeat.py 的区别：
- heartbeat.py: 快速检查，每 5 分钟运行，只输出变化
- monitor_positions.py: 详细分析，按需运行，输出完整报告

使用方式：
    python tools/monitor_positions.py                    # 分析所有持仓
    python tools/monitor_positions.py --symbol DCE.jm2609  # 分析指定品种
    python tools/monitor_positions.py --output json      # 输出 JSON 格式
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from trend_scanner.data_source import DataSourceFactory
from trend_scanner.indicators import IndicatorEngine

# 导入数据格式工具
from data_formats import load_config

# 文件路径
POSITIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'positions.json')


def load_positions() -> List[Dict[str, Any]]:
    """加载持仓数据"""
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('positions', [])


def normalize_symbol(symbol: str) -> str:
    """将配置格式的品种代码转换为数据源可识别的格式"""
    symbol = symbol.strip()
    if '.' in symbol:
        parts = symbol.split('.')
        if len(parts) == 2:
            return parts[1].upper()
    return symbol.upper()


def analyze_position(pos: Dict[str, Any], data_source) -> Dict[str, Any]:
    """
    分析单个持仓品种的风险状态
    
    参数:
        pos: 持仓数据
        data_source: 数据源实例
    
    返回:
        分析结果字典
    """
    symbol = pos.get('symbol', '')
    direction = pos.get('direction', '')
    entry_price = pos.get('entry_price', 0)
    data_symbol = normalize_symbol(symbol)
    
    result = {
        'symbol': symbol,
        'direction': direction,
        'entry_price': entry_price,
        'analysis_time': datetime.now().isoformat(),
        'status': 'UNKNOWN',
        'risk_level': 'UNKNOWN',
        'indicators': {},
        'alerts': [],
        'recommendations': []
    }
    
    try:
        # 获取数据
        df = None
        try:
            df = data_source.get_kline(data_symbol, days=120)
        except SystemExit:
            # TqSdk 可能会调用 sys.exit()，尝试使用 CSV 数据源
            print(f"[警告] TqSdk 获取 {data_symbol} 数据失败，尝试 CSV 数据源...", flush=True)
            try:
                csv_source = CsvSource()
                df = csv_source.get_kline(data_symbol, days=120)
            except Exception as e:
                print(f"[错误] CSV 数据源也失败: {e}", flush=True)
        except Exception as e:
            print(f"[错误] 获取 {data_symbol} 数据失败: {e}", flush=True)
        
        if df is None or len(df) < 60:
            result['status'] = 'DATA_INSUFFICIENT'
            result['alerts'].append('数据不足，无法分析')
            return result
        
        # 计算指标
        engine = IndicatorEngine(df)
        engine.compute_all()
        composite = engine.get_trend_strength_composite()
        engine.df['trend_strength_composite'] = composite
        
        latest = engine.df.iloc[-1]
        prev = engine.df.iloc[-2] if len(engine.df) > 1 else latest
        
        # 提取指标
        current_price = float(latest.get('close', 0))
        er = float(latest.get('er', 0))
        tsi = float(latest.get('tsi', 0))
        r_squared = float(latest.get('r_squared', 0))
        hurst = float(latest.get('hurst', 0.5))
        trend_strength = float(composite.iloc[-1])
        rsi = float(latest.get('rsi', 50))
        adx = float(latest.get('adx', 0))
        atr = float(latest.get('atr', 0))
        
        # 前一日指标
        prev_er = float(prev.get('er', 0))
        prev_tsi = float(prev.get('tsi', 0))
        prev_trend_strength = float(composite.iloc[-2]) if len(composite) > 1 else trend_strength
        
        # 计算变化
        er_change = er - prev_er
        tsi_change = tsi - prev_tsi
        strength_change = trend_strength - prev_trend_strength
        
        # 计算盈亏
        pnl_pct = 0
        if entry_price > 0:
            if direction == 'LONG':
                pnl_pct = (current_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - current_price) / entry_price * 100
        
        # 存储指标
        result['indicators'] = {
            'current_price': round(current_price, 1),
            'pnl_pct': round(pnl_pct, 2),
            'er': round(er, 3),
            'er_change': round(er_change, 3),
            'tsi': round(tsi, 2),
            'tsi_change': round(tsi_change, 2),
            'r_squared': round(r_squared, 3),
            'hurst': round(hurst, 3),
            'trend_strength': round(trend_strength, 3),
            'strength_change': round(strength_change, 3),
            'rsi': round(rsi, 1),
            'adx': round(adx, 1),
            'atr': round(atr, 1)
        }
        
        # 评估风险级别
        risk_score = 0
        
        # 趋势强度下降
        if strength_change < -0.2:
            risk_score += 3
            result['alerts'].append(f'趋势强度骤降 {strength_change:.3f}')
        elif strength_change < -0.1:
            risk_score += 1
            result['alerts'].append(f'趋势强度下降 {strength_change:.3f}')
        
        # ER 下降
        if er_change < -0.15:
            risk_score += 2
            result['alerts'].append(f'ER 骤降 {er_change:.3f}')
        
        # TSI 背离
        if direction == 'LONG' and tsi_change < -10:
            risk_score += 2
            result['alerts'].append(f'RSI 下降 {tsi_change:.1f}，动量减弱')
        elif direction == 'SHORT' and tsi_change > 10:
            risk_score += 2
            result['alerts'].append(f'RSI 上升 {tsi_change:.1f}，动量减弱')
        
        # RSI 超买/超卖
        if direction == 'LONG' and rsi > 70:
            risk_score += 1
            result['alerts'].append(f'RSI={rsi:.1f} 超买')
        elif direction == 'SHORT' and rsi < 30:
            risk_score += 1
            result['alerts'].append(f'RSI={rsi:.1f} 超卖')
        
        # 确定风险级别
        if risk_score >= 5:
            result['risk_level'] = 'HIGH'
            result['status'] = 'RISK_HIGH'
        elif risk_score >= 3:
            result['risk_level'] = 'MEDIUM'
            result['status'] = 'RISK_MEDIUM'
        else:
            result['risk_level'] = 'LOW'
            result['status'] = 'RISK_LOW'
        
        # 生成建议
        if result['risk_level'] == 'HIGH':
            result['recommendations'].append('建议减仓或平仓')
            result['recommendations'].append('趋势反转信号明确，不宜继续持有')
        elif result['risk_level'] == 'MEDIUM':
            result['recommendations'].append('建议收紧止损')
            result['recommendations'].append('密切关注趋势变化')
        else:
            result['recommendations'].append('趋势健康，可继续持有')
            if pnl_pct > 5:
                result['recommendations'].append('盈利可观，可考虑部分止盈')
    
    except Exception as e:
        result['status'] = 'ERROR'
        result['alerts'].append(f'分析失败: {e}')
    
    return result


def monitor_positions(symbols: List[str] = None) -> List[Dict[str, Any]]:
    """
    分析所有持仓
    
    参数:
        symbols: 品种列表（筛选）
    
    返回:
        分析结果列表
    """
    print("[调试] monitor_positions 函数开始", flush=True)
    
    # 加载持仓
    print("[调试] 加载持仓...", flush=True)
    positions = load_positions()
    print(f"[调试] 持仓数量: {len(positions)}", flush=True)
    
    if not positions:
        print("当前无持仓", flush=True)
        return []
    
    # 筛选
    if symbols:
        positions = [p for p in positions if p.get('symbol') in symbols]
    
    if not positions:
        print("无匹配的持仓", flush=True)
        return []
    
    print(f"分析 {len(positions)} 个持仓品种...", flush=True)
    
    # 获取数据源
    print("[调试] 创建数据源...", flush=True)
    data_source = DataSourceFactory.create()
    print(f"[调试] 数据源创建成功: {type(data_source)}", flush=True)
    
    # 分析每个持仓
    results = []
    for i, pos in enumerate(positions):
        print(f"[调试] 分析持仓 {i+1}/{len(positions)}: {pos.get('symbol')}", flush=True)
        result = analyze_position(pos, data_source)
        results.append(result)
    
    print(f"[调试] 分析完成", flush=True)
    return results


def main():
    print("[调试] main 函数开始", flush=True)
    parser = argparse.ArgumentParser(description="持仓风险详细分析")
    parser.add_argument("--symbol", type=str, help="指定品种代码")
    parser.add_argument("--symbols", type=str, help="多个品种代码（逗号分隔）")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")
    parser.add_argument("--save", action="store_true", help="保存结果到 data/latest_monitor.json")
    
    print("[调试] 解析参数...", flush=True)
    args = parser.parse_args()
    print(f"[调试] 参数: {args}", flush=True)
    
    # 确定品种列表
    symbols = None
    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    
    print(f"[调试] 品种列表: {symbols}", flush=True)
    
    # 执行分析
    print("[调试] 开始执行分析...", flush=True)
    results = monitor_positions(symbols=symbols)
    print(f"[调试] 分析完成，结果数量: {len(results)}", flush=True)
    
    # 输出结果
    if args.output == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"\n持仓风险分析报告")
        print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        for r in results:
            symbol = r.get('symbol', '')
            direction = r.get('direction', '')
            risk_level = r.get('risk_level', 'UNKNOWN')
            indicators = r.get('indicators', {})
            
            # 风险级别标记
            risk_mark = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(risk_level, '⚪')
            
            print(f"\n{risk_mark} 【{symbol}】{direction} 方向")
            print(f"  风险级别: {risk_level}")
            print(f"  当前价: {indicators.get('current_price', 0):.1f} | 盈亏: {indicators.get('pnl_pct', 0):+.2f}%")
            print(f"  ER: {indicators.get('er', 0):.3f} ({indicators.get('er_change', 0):+.3f})")
            print(f"  TSI: {indicators.get('tsi', 0):.2f} ({indicators.get('tsi_change', 0):+.2f})")
            print(f"  趋势强度: {indicators.get('trend_strength', 0):.3f} ({indicators.get('strength_change', 0):+.3f})")
            print(f"  RSI: {indicators.get('rsi', 0):.1f} | ADX: {indicators.get('adx', 0):.1f}")
            
            # 预警
            alerts = r.get('alerts', [])
            if alerts:
                print(f"  ⚠️ 预警:")
                for alert in alerts:
                    print(f"    - {alert}")
            
            # 建议
            recommendations = r.get('recommendations', [])
            if recommendations:
                print(f"  💡 建议:")
                for rec in recommendations:
                    print(f"    - {rec}")
        
        # 汇总
        high_count = sum(1 for r in results if r.get('risk_level') == 'HIGH')
        medium_count = sum(1 for r in results if r.get('risk_level') == 'MEDIUM')
        low_count = sum(1 for r in results if r.get('risk_level') == 'LOW')
        
        print(f"\n汇总: 🔴 高风险 {high_count} | 🟡 中风险 {medium_count} | 🟢 低风险 {low_count}")
    
    # 保存结果
    if args.save and results:
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                  'data', 'latest_monitor.json')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到 data/latest_monitor.json")


if __name__ == "__main__":
    print("[调试] 脚本开始执行", flush=True)
    try:
        main()
    except SystemExit as e:
        print(f"[调试] SystemExit: {e}", flush=True)
    except Exception as e:
        print(f"[致命错误] {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
