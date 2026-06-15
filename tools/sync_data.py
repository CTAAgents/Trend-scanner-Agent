#!/usr/bin/env python3
"""
数据同步脚本

功能：
1. 同步品种元数据
2. 同步行情数据
3. 同步K线数据
4. 查看统计信息

使用方式：
    python tools/sync_data.py sync                # 全量同步
    python tools/sync_data.py sync --days 30      # 同步30天K线
    python tools/sync_data.py sync --min-oi 5000  # 持仓量≥5000的品种
    python tools/sync_data.py stats               # 查看统计信息
    python tools/sync_data.py symbols             # 仅同步品种
    python tools/sync_data.py quotes              # 仅同步行情
    python tools/sync_data.py klines              # 仅同步K线
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.storage.data_sync import DataSyncManager


def main():
    parser = argparse.ArgumentParser(description='数据同步脚本')
    parser.add_argument('action', choices=['sync', 'stats', 'symbols', 'quotes', 'klines'],
                       help='操作类型')
    parser.add_argument('--days', type=int, default=120, help='K线天数（默认120天）')
    parser.add_argument('--min-oi', type=float, default=10000, help='最小持仓量阈值（默认10000手）')
    parser.add_argument('--force', action='store_true', help='强制全量同步')
    parser.add_argument('--db-dir', type=str, default='data', help='数据库目录')
    
    args = parser.parse_args()
    
    # 数据库路径
    sqlite_path = os.path.join(args.db_dir, 'meta.db')
    duckdb_path = os.path.join(args.db_dir, 'market.db')
    
    # 确保目录存在
    os.makedirs(args.db_dir, exist_ok=True)
    
    # 创建同步管理器
    manager = DataSyncManager(sqlite_path=sqlite_path, duckdb_path=duckdb_path)
    
    print("=" * 60)
    print("期货数据同步工具")
    print("=" * 60)
    print(f"SQLite: {sqlite_path}")
    print(f"DuckDB: {duckdb_path}")
    print(f"操作: {args.action}")
    print("=" * 60)
    
    if args.action == 'sync':
        # 全量同步
        result = manager.full_sync(days=args.days, min_oi=args.min_oi)
        
        print("\n" + "=" * 60)
        print("同步完成")
        print("=" * 60)
        
        # 打印统计信息
        manager.print_statistics()
        
    elif args.action == 'stats':
        # 打印统计信息
        manager.print_statistics()
        
    elif args.action == 'symbols':
        # 同步品种
        print("\n开始同步品种元数据...")
        result = manager.sync_symbols()
        
        if result.get('success'):
            print(f"\n成功同步 {result.get('count', 0)} 个品种")
        else:
            print(f"\n同步失败: {result.get('error')}")
            
    elif args.action == 'quotes':
        # 同步行情
        print(f"\n开始同步行情数据（持仓量≥{args.min_oi}）...")
        result = manager.sync_quotes(min_oi=args.min_oi)
        
        if result.get('success'):
            print(f"\n成功同步 {result.get('count', 0)} 个品种的行情")
            print(f"活跃品种: {result.get('active_count', 0)} 个")
        else:
            print(f"\n同步失败: {result.get('error')}")
            
    elif args.action == 'klines':
        # 同步K线
        print(f"\n开始同步K线数据（{args.days}天，持仓量≥{args.min_oi}）...")
        
        # 获取活跃品种
        active_symbols = manager.get_active_symbols(min_oi=args.min_oi)
        symbol_codes = [s['symbol'] for s in active_symbols]
        
        if not symbol_codes:
            print("没有活跃品种需要同步")
            return
        
        print(f"需要同步 {len(symbol_codes)} 个品种")
        result = manager.sync_klines(symbols=symbol_codes, days=args.days, force=args.force)
        
        print(f"\n同步完成:")
        print(f"  成功: {result.get('synced', 0)}")
        print(f"  失败: {result.get('failed', 0)}")
        print(f"  跳过: {result.get('skipped', 0)}")


if __name__ == '__main__':
    main()
