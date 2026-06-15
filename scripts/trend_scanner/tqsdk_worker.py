"""
TqSdk 工作进程

解决 TqSdk 的 sys.exit() 问题：
- 在独立子进程中运行 TqSdk
- 通过 JSON 文件交换数据
- 主进程不会被 sys.exit() 终止

使用方式：
    python scripts/trend_scanner/tqsdk_worker.py --symbol RB --days 120 --output data/tqsdk_output.json
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))


def fetch_kline(symbol: str, days: int = 120, period: str = "daily") -> dict:
    """
    获取 K 线数据
    
    Args:
        symbol: 品种代码（如 "RB", "JM"）
        days: 获取天数
        period: 周期（daily/1h/15m 等）
    
    Returns:
        数据字典，包含 success, data, error 字段
    """
    try:
        from tqsdk import TqApi, TqAuth
        
        # 获取认证信息
        tq_user = os.environ.get('TQ_USER', '')
        tq_password = os.environ.get('TQ_PASSWORD', '')
        
        if not tq_user or not tq_password:
            return {
                'success': False,
                'error': 'TQ_USER 或 TQ_PASSWORD 环境变量未设置',
                'data': None
            }
        
        auth = TqAuth(tq_user, tq_password)
        
        # 主力合约映射
        MAIN_CONTRACT_MAP = {
            'RB': 'KQ.m@SHFE.rb',
            'HC': 'KQ.m@SHFE.hc',
            'I': 'KQ.m@DCE.i',
            'J': 'KQ.m@DCE.j',
            'JM': 'KQ.m@DCE.jm',
            'CU': 'KQ.m@SHFE.cu',
            'AL': 'KQ.m@SHFE.al',
            'ZN': 'KQ.m@SHFE.zn',
            'NI': 'KQ.m@SHFE.ni',
            'SC': 'KQ.m@INE.sc',
            'FU': 'KQ.m@SHFE.fu',
            'BU': 'KQ.m@SHFE.bu',
            'RU': 'KQ.m@SHFE.ru',
            'TA': 'KQ.m@CZCE.TA',
            'MA': 'KQ.m@CZCE.MA',
            'CF': 'KQ.m@CZCE.CF',
            'SR': 'KQ.m@CZCE.SR',
            'OI': 'KQ.m@CZCE.OI',
            'M': 'KQ.m@DCE.m',
            'Y': 'KQ.m@DCE.y',
            'P': 'KQ.m@DCE.p',
            'C': 'KQ.m@DCE.c',
            'CS': 'KQ.m@DCE.cs',
            'AU': 'KQ.m@SHFE.au',
            'AG': 'KQ.m@SHFE.ag',
        }
        
        # 获取 TqSdk 符号
        tq_symbol = MAIN_CONTRACT_MAP.get(symbol.upper())
        if not tq_symbol:
            # 尝试作为直接合约代码
            code = symbol.lower()
            if code.startswith('rb') or code.startswith('hc'):
                tq_symbol = f"SHFE.{code}"
            elif code.startswith('i') or code.startswith('j') or code.startswith('jm'):
                tq_symbol = f"DCE.{code}"
            elif code.startswith('cu') or code.startswith('al'):
                tq_symbol = f"SHFE.{code}"
            elif code.startswith('sc'):
                tq_symbol = f"INE.{code}"
            else:
                tq_symbol = symbol
        
        # 周期映射
        period_map = {
            'daily': 86400,
            '1h': 3600,
            '15m': 900,
            '5m': 300,
            '1m': 60,
        }
        dur_sec = period_map.get(period, 86400)
        
        # 获取数据
        api = TqApi(auth=auth)
        klines = api.get_kline_serial(tq_symbol, dur_sec, data_length=days)
        api.wait_update()
        
        if klines is None or len(klines) == 0:
            api.close()
            return {
                'success': False,
                'error': f'无法获取 {symbol} 的数据',
                'data': None
            }
        
        # 转换为标准格式
        import pandas as pd
        df = pd.DataFrame({
            'date': pd.to_datetime(klines['datetime'], unit='ns'),
            'open': klines['open'],
            'high': klines['high'],
            'low': klines['low'],
            'close': klines['close'],
            'volume': klines['volume'],
            'open_interest': klines['close_oi'],
        })
        
        # 去除无效数据
        df = df.dropna()
        df = df[df['close'] > 0]
        
        api.close()
        
        # 转换为字典
        data = {
            'symbol': symbol,
            'tq_symbol': tq_symbol,
            'period': period,
            'records': len(df),
            'columns': list(df.columns),
            'data': df.to_dict(orient='records')
        }
        
        return {
            'success': True,
            'error': None,
            'data': data
        }
        
    except SystemExit as e:
        # 捕获 TqSdk 的 sys.exit()
        return {
            'success': False,
            'error': f'TqSdk sys.exit: {e}',
            'data': None
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'data': None
        }


def fetch_quote(symbol: str) -> dict:
    """
    获取实时行情
    
    Args:
        symbol: 品种代码
    
    Returns:
        行情字典
    """
    try:
        from tqsdk import TqApi, TqAuth
        
        tq_user = os.environ.get('TQ_USER', '')
        tq_password = os.environ.get('TQ_PASSWORD', '')
        
        if not tq_user or not tq_password:
            return {
                'success': False,
                'error': 'TQ_USER 或 TQ_PASSWORD 环境变量未设置',
                'data': None
            }
        
        auth = TqAuth(tq_user, tq_password)
        
        # 主力合约映射
        MAIN_CONTRACT_MAP = {
            'RB': 'KQ.m@SHFE.rb',
            'I': 'KQ.m@DCE.i',
            'J': 'KQ.m@DCE.j',
            'JM': 'KQ.m@DCE.jm',
            'CU': 'KQ.m@SHFE.cu',
            'NI': 'KQ.m@SHFE.ni',
            'SC': 'KQ.m@INE.sc',
            'CF': 'KQ.m@CZCE.CF',
            'AU': 'KQ.m@SHFE.au',
            'AG': 'KQ.m@SHFE.ag',
        }
        
        tq_symbol = MAIN_CONTRACT_MAP.get(symbol.upper(), symbol)
        
        api = TqApi(auth=auth)
        quote = api.get_quote(tq_symbol)
        api.wait_update()
        
        data = {
            'symbol': symbol,
            'last_price': getattr(quote, 'last_price', 0),
            'open_interest': getattr(quote, 'open_interest', 0),
            'volume': getattr(quote, 'volume', 0),
            'bid_price1': getattr(quote, 'bid_price1', 0),
            'ask_price1': getattr(quote, 'ask_price1', 0),
            'highest': getattr(quote, 'highest', 0),
            'lowest': getattr(quote, 'lowest', 0),
            'pre_close': getattr(quote, 'pre_close', 0),
        }
        
        api.close()
        
        return {
            'success': True,
            'error': None,
            'data': data
        }
        
    except SystemExit as e:
        return {
            'success': False,
            'error': f'TqSdk sys.exit: {e}',
            'data': None
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'data': None
        }


def main():
    parser = argparse.ArgumentParser(description='TqSdk 工作进程')
    parser.add_argument('--action', choices=['kline', 'quote'], required=True, help='操作类型')
    parser.add_argument('--symbol', type=str, required=True, help='品种代码')
    parser.add_argument('--days', type=int, default=120, help='获取天数')
    parser.add_argument('--period', type=str, default='daily', help='周期')
    parser.add_argument('--output', type=str, required=True, help='输出文件路径')
    
    args = parser.parse_args()
    
    # 执行操作
    if args.action == 'kline':
        result = fetch_kline(args.symbol, args.days, args.period)
    elif args.action == 'quote':
        result = fetch_quote(args.symbol)
    else:
        result = {
            'success': False,
            'error': f'未知操作: {args.action}',
            'data': None
        }
    
    # 输出结果
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    
    # 打印状态
    if result['success']:
        print(f"SUCCESS: {args.action} {args.symbol}")
    else:
        print(f"FAILED: {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
