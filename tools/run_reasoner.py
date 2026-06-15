"""
Reasoner 包装脚本 — 将 Scanner 信号转化为交易决策简报

读取 latest_scan.json 中的信号，对每个信号调用 TradingAssistant.analyze()，
生成交易决策简报并输出。

使用方式：
    python tools/run_reasoner.py                          # 处理所有信号
    python tools/run_reasoner.py --symbol DCE.jm2609      # 处理指定品种
    python tools/run_reasoner.py --scan-id scan_20260615_103000  # 处理指定扫描结果
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
from trend_scanner.navigator import TradingAssistant
from trend_scanner.models import TradingBrief

# 导入数据格式工具
from data_formats import read_scan_result, load_config


def normalize_symbol(symbol: str) -> str:
    """将配置格式的品种代码转换为数据源可识别的格式"""
    symbol = symbol.strip()
    if '.' in symbol:
        parts = symbol.split('.')
        if len(parts) == 2:
            return parts[1].upper()
    return symbol.upper()


def brief_to_dict(brief: TradingBrief) -> Dict[str, Any]:
    """将 TradingBrief 转换为字典格式"""
    result = {
        "market_assessment": {},
        "routes": [],
        "constraints": [],
        "uncertainty": {},
        "confidence": 0.0
    }
    
    # 市场评估
    if hasattr(brief, 'assessment') and brief.assessment:
        a = brief.assessment
        result["market_assessment"] = {
            "trend_direction": getattr(a, 'trend_direction', 'UNKNOWN'),
            "trend_phase": getattr(a, 'trend_phase', 'UNKNOWN'),
            "confidence": getattr(a, 'confidence', 0),
            "reasoning": getattr(a, 'reasoning', '')
        }
    
    # 操作方案
    if hasattr(brief, 'routes') and brief.routes:
        for route in brief.routes:
            result["routes"].append({
                "name": getattr(route, 'name', ''),
                "description": getattr(route, 'description', ''),
                "entry_condition": getattr(route, 'entry_condition', ''),
                "stop_loss": getattr(route, 'stop_loss', ''),
                "take_profit": getattr(route, 'take_profit', ''),
                "position_size": getattr(route, 'position_size', ''),
                "probability": getattr(route, 'probability', 0)
            })
    
    # 约束
    if hasattr(brief, 'constraints') and brief.constraints:
        for c in brief.constraints:
            result["constraints"].append({
                "type": getattr(c, 'type', ''),
                "value": getattr(c, 'value', ''),
                "reason": getattr(c, 'reason', '')
            })
    
    # 不确定性
    if hasattr(brief, 'uncertainty') and brief.uncertainty:
        u = brief.uncertainty
        result["uncertainty"] = {
            "level": getattr(u, 'level', 'UNKNOWN'),
            "factors": getattr(u, 'factors', [])
        }
    
    # 置信度
    if hasattr(brief, 'confidence'):
        result["confidence"] = brief.confidence
    
    return result


def run_reasoner_for_signal(signal: Dict[str, Any], assistant: TradingAssistant) -> Optional[Dict[str, Any]]:
    """
    对单个信号执行推理
    
    参数:
        signal: Scanner 输出的信号字典
        assistant: TradingAssistant 实例
    
    返回:
        推理结果字典
    """
    symbol = signal.get('symbol', '')
    data_symbol = normalize_symbol(symbol)
    
    print(f"  推理中: {symbol} ({signal.get('direction', '')})...", end="", flush=True)
    
    try:
        # 获取 K 线数据
        ds = DataSourceFactory.create()
        df = ds.get_kline(data_symbol, days=120)
        
        if df is None or len(df) < 60:
            print(f" 数据不足")
            return None
        
        # 执行推理
        brief = assistant.analyze(df, symbol=symbol)
        
        # 转换为字典
        result = brief_to_dict(brief)
        result["symbol"] = symbol
        result["direction"] = signal.get('direction', '')
        result["signal_strength"] = signal.get('signal_strength', '')
        result["trigger_reason"] = signal.get('trigger_reason', '')
        result["reasoning_time"] = datetime.now().isoformat()
        
        confidence = result.get('confidence', 0)
        print(f" 完成 (置信度: {confidence:.2f})")
        
        return result
    
    except Exception as e:
        print(f" 失败: {e}")
        return None


def run_reasoner(symbols: List[str] = None, scan_result: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    执行推理
    
    参数:
        symbols: 品种列表（如果提供，直接推理这些品种）
        scan_result: Scanner 输出结果（如果提供，从中提取信号）
    
    返回:
        推理结果列表
    """
    # 加载配置
    config = load_config()
    reasoner_config = config.get("reasoner", {})
    
    # 获取信号列表
    if scan_result:
        signals = scan_result.get('signals', [])
    elif symbols:
        # 直接对指定品种推理（跳过筛选）
        signals = [{"symbol": s, "direction": "UNKNOWN", "signal_strength": "MEDIUM", "trigger_reason": "用户指定"} for s in symbols]
    else:
        # 读取最新扫描结果
        scan_result = read_scan_result()
        if scan_result:
            signals = scan_result.get('signals', [])
        else:
            print("错误: 无扫描结果，请先运行 Scanner")
            return []
    
    if not signals:
        print("无信号需要推理")
        return []
    
    print(f"开始推理 {len(signals)} 个信号...")
    
    # 创建 TradingAssistant
    assistant = TradingAssistant()
    
    # 对每个信号执行推理
    results = []
    for signal in signals:
        result = run_reasoner_for_signal(signal, assistant)
        if result:
            results.append(result)
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Reasoner 包装脚本")
    parser.add_argument("--symbol", type=str, help="指定品种代码（如 DCE.jm2609）")
    parser.add_argument("--symbols", type=str, help="多个品种代码（逗号分隔）")
    parser.add_argument("--scan-id", type=str, help="指定扫描结果 ID（暂未实现）")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")
    parser.add_argument("--save", action="store_true", help="保存结果到 data/latest_reasoning.json")
    
    args = parser.parse_args()
    
    # 确定品种列表
    symbols = None
    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    
    # 执行推理
    results = run_reasoner(symbols=symbols)
    
    # 输出结果
    if args.output == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"\n推理完成: {len(results)} 个品种")
        print("=" * 60)
        for r in results:
            symbol = r.get('symbol', '')
            direction = r.get('direction', '')
            confidence = r.get('confidence', 0)
            print(f"\n【{symbol}】{direction} 方向 | 置信度: {confidence:.2f}")
            
            # 市场评估
            ma = r.get('market_assessment', {})
            if ma:
                print(f"  趋势阶段: {ma.get('trend_phase', 'N/A')}")
                print(f"  推理: {ma.get('reasoning', 'N/A')}")
            
            # 操作方案
            routes = r.get('routes', [])
            if routes:
                print(f"  操作方案:")
                for route in routes:
                    print(f"    - {route.get('name', '')}: {route.get('description', '')}")
            
            # 约束
            constraints = r.get('constraints', [])
            if constraints:
                print(f"  约束:")
                for c in constraints:
                    print(f"    - {c.get('value', '')}")
    
    # 保存结果
    if args.save and results:
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'latest_reasoning.json')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到 data/latest_reasoning.json")


if __name__ == "__main__":
    main()
