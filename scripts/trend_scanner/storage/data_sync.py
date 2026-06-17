"""
数据同步管理器

负责：
1. TqSdk 数据同步到本地数据库
2. 增量更新机制
3. 数据源优先级管理
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

import pandas as pd

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.storage.sqlite_store import SQLiteStore
from trend_scanner.storage.duckdb_store import DuckDBStore


class DataSyncManager:
    """数据同步管理器"""
    
    def __init__(self, sqlite_path: str = "data/meta.db", duckdb_path: str = "data/market.db"):
        """
        初始化同步管理器
        
        Args:
            sqlite_path: SQLite 数据库路径
            duckdb_path: DuckDB 数据库路径
        """
        self.sqlite = SQLiteStore(sqlite_path)
        self.duckdb = DuckDBStore(duckdb_path)
        
        # TqSdk 数据源（延迟初始化）
        self._tqsdk = None
    
    @property
    def tqsdk(self):
        """延迟初始化 TqSdk 数据源"""
        if self._tqsdk is None:
            from trend_scanner.tqsdk_bridge import TqSdkDataSource
            self._tqsdk = TqSdkDataSource()
        return self._tqsdk
    
    # ============================================================
    # 品种同步
    # ============================================================
    
    def sync_symbols(self) -> Dict[str, Any]:
        """
        同步品种元数据
        
        Returns:
            同步结果
        """
        print("[同步] 获取所有品种...")
        
        symbols = self.tqsdk.get_all_symbols()
        
        if not symbols:
            return {
                'success': False,
                'error': '无法获取品种列表',
                'count': 0
            }
        
        # 保存到 SQLite
        self.sqlite.upsert_symbols_batch(symbols)
        
        print(f"[同步] 成功同步 {len(symbols)} 个品种")
        
        return {
            'success': True,
            'count': len(symbols),
            'symbols': symbols
        }
    
    # ============================================================
    # 行情同步
    # ============================================================
    
    def sync_quotes(self, symbols: List[str] = None, min_oi: float = 0) -> Dict[str, Any]:
        """
        同步行情数据
        
        Args:
            symbols: 品种列表，None 则同步所有品种
            min_oi: 最小持仓量筛选
        
        Returns:
            同步结果
        """
        # 获取品种列表
        if symbols is None:
            db_symbols = self.sqlite.get_all_symbols(active_only=True)
            symbols = [s['tq_symbol'] for s in db_symbols if s.get('tq_symbol')]
        
        if not symbols:
            return {
                'success': False,
                'error': '没有品种需要同步',
                'count': 0
            }
        
        print(f"[同步] 获取 {len(symbols)} 个品种的行情...")

        # 分批获取行情（每批最多 10 个，避免 TqSdk 单次订阅过多超时）
        all_quotes = {}
        chunk_size = 10
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i:i+chunk_size]
            print(f"  批次 {i//chunk_size + 1}: {len(chunk)} 个品种...")
            batch_quotes = self.tqsdk.get_quotes_batch(chunk)
            if batch_quotes:
                all_quotes.update(batch_quotes)

        quotes = all_quotes
        
        if not quotes:
            return {
                'success': False,
                'error': '无法获取行情数据',
                'count': 0
            }
        
        # 保存到数据库
        synced_count = 0
        active_count = 0
        
        for tq_symbol, quote in quotes.items():
            # 从 tq_symbol 提取品种代码
            # 格式：KQ.m@SHFE.rb -> SHFE.rb
            symbol = tq_symbol.replace('KQ.m@', '')
            
            # 保存到 DuckDB
            self.duckdb.save_quote(symbol, quote)
            
            # 更新 SQLite 中的品种信息
            self.sqlite.update_symbol_quote(symbol, quote)
            
            synced_count += 1
            
            # 统计活跃品种
            oi = quote.get('open_interest', 0) or 0
            if oi >= min_oi:
                active_count += 1
        
        print(f"[同步] 成功同步 {synced_count} 个品种的行情，活跃品种 {active_count} 个")
        
        return {
            'success': True,
            'count': synced_count,
            'active_count': active_count,
            'min_oi': min_oi
        }
    
    # ============================================================
    # K线同步
    # ============================================================
    
    def sync_klines(self, symbols: List[str] = None, days: int = 120,
                   timeframe: str = 'daily', force: bool = False) -> Dict[str, Any]:
        """
        同步K线数据
        
        Args:
            symbols: 品种列表，None 则同步所有活跃品种
            days: 获取天数
            timeframe: 时间周期
            force: 强制全量同步
        
        Returns:
            同步结果
        """
        # 获取品种列表
        if symbols is None:
            db_symbols = self.sqlite.get_all_symbols(active_only=True)
            symbols = [s['symbol'] for s in db_symbols]
        
        if not symbols:
            return {
                'success': False,
                'error': '没有品种需要同步',
                'count': 0
            }
        
        print(f"[同步] 同步 {len(symbols)} 个品种的K线数据...")
        
        synced_count = 0
        failed_count = 0
        skipped_count = 0
        
        for i, symbol in enumerate(symbols, 1):
            try:
                # 检查同步状态
                if not force:
                    sync_status = self.sqlite.get_sync_status(symbol, timeframe)
                    if sync_status and sync_status.get('status') == 'success':
                        # 检查是否需要增量更新
                        latest_date = sync_status.get('latest_date')
                        if latest_date:
                            latest_date = datetime.fromisoformat(latest_date)
                            days_since = (datetime.now() - latest_date).days
                            
                            if days_since <= 1:
                                skipped_count += 1
                                continue
                            
                            # 增量更新
                            days = min(days, days_since + 5)  # 多取几天确保覆盖
                
                # 获取K线数据
                print(f"  [{i}/{len(symbols)}] 同步 {symbol}...")
                
                df = self.tqsdk.get_kline(symbol, days=days)
                
                if df is None or df.empty:
                    print(f"    [跳过] 无法获取数据")
                    self.sqlite.update_sync_status(symbol, timeframe, 'failed', 
                                                   error='无法获取数据')
                    failed_count += 1
                    continue
                
                # 保存到 DuckDB
                self.duckdb.save_klines(symbol, df, timeframe)
                
                # 计算并保存技术指标
                try:
                    from trend_scanner.indicators import IndicatorEngine
                    engine = IndicatorEngine(df)
                    engine.compute_all()
                    
                    # 获取指标列
                    indicator_cols = [col for col in engine.df.columns 
                                    if col not in ['date', 'open', 'high', 'low', 'close', 
                                                  'volume', 'open_interest']]
                    
                    if indicator_cols:
                        self.duckdb.save_indicators(symbol, engine.df, indicator_cols)
                except Exception as e:
                    print(f"    [警告] 指标计算失败: {e}")
                
                # 更新同步状态
                min_date = df['date'].min() if 'date' in df.columns else None
                max_date = df['date'].max() if 'date' in df.columns else None
                
                self.sqlite.update_sync_status(
                    symbol, timeframe, 'success',
                    earliest_date=str(min_date) if min_date else None,
                    latest_date=str(max_date) if max_date else None,
                    record_count=len(df)
                )
                
                synced_count += 1
                
                # 避免请求过快
                time.sleep(0.5)
                
            except Exception as e:
                print(f"    [错误] {symbol} 同步失败: {e}")
                self.sqlite.update_sync_status(symbol, timeframe, 'failed', error=str(e))
                failed_count += 1
        
        print(f"[同步] 完成：成功 {synced_count}，失败 {failed_count}，跳过 {skipped_count}")
        
        return {
            'success': True,
            'synced': synced_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'total': len(symbols)
        }
    
    # ============================================================
    # 全量同步
    # ============================================================
    
    def full_sync(self, days: int = 120, min_oi: float = 10000) -> Dict[str, Any]:
        """
        全量同步
        
        Args:
            days: K线天数
            min_oi: 最小持仓量
        
        Returns:
            同步结果
        """
        print("=" * 60)
        print("开始全量同步")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # 1. 同步品种
        print("\n[步骤1] 同步品种元数据...")
        symbol_result = self.sync_symbols()
        
        # 2. 同步行情
        print("\n[步骤2] 同步行情数据...")
        quote_result = self.sync_quotes(min_oi=min_oi)
        
        # 3. 同步K线（只同步活跃品种）
        print(f"\n[步骤3] 同步K线数据（持仓量≥{min_oi}的品种）...")
        active_symbols = self.sqlite.get_active_symbols(min_oi=min_oi)
        active_symbol_codes = [s['symbol'] for s in active_symbols]
        
        kline_result = self.sync_klines(symbols=active_symbol_codes, days=days, force=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print(f"全量同步完成，耗时 {duration:.1f} 秒")
        print("=" * 60)
        
        return {
            'success': True,
            'duration_seconds': duration,
            'symbols': symbol_result,
            'quotes': quote_result,
            'klines': kline_result,
            'statistics': self.get_statistics()
        }
    
    # ============================================================
    # 数据源查询
    # ============================================================
    
    def get_kline(self, symbol: str, days: int = 120,
                  timeframe: str = 'daily', allow_tqsdk_fallback: bool = True) -> Optional[pd.DataFrame]:
        """
        获取K线数据（优先从本地DB，其次从TqSdk）

        Args:
            symbol: 品种代码
            days: 获取天数
            timeframe: 时间周期
            allow_tqsdk_fallback: 是否允许 TqSdk 兜底（心跳模式可关闭以避免超时阻塞）

        Returns:
            DataFrame
        """
        # 1. 尝试从 DuckDB 获取
        df = self.duckdb.get_klines(symbol, days, timeframe)

        if df is not None and len(df) >= 60:
            return df

        # 2. 从 TqSdk 获取（可跳过）
        if not allow_tqsdk_fallback:
            return None

        print(f"  [数据源] 本地数据不足，从 TqSdk 获取 {symbol}...")
        df = self.tqsdk.get_kline(symbol, days=days)
        
        if df is not None and not df.empty:
            # 保存到本地
            self.duckdb.save_klines(symbol, df, timeframe)
            
            # 更新同步状态
            min_date = df['date'].min() if 'date' in df.columns else None
            max_date = df['date'].max() if 'date' in df.columns else None
            
            self.sqlite.update_sync_status(
                symbol, timeframe, 'success',
                earliest_date=str(min_date) if min_date else None,
                latest_date=str(max_date) if max_date else None,
                record_count=len(df)
            )
        
        return df
    
    def get_active_symbols(self, min_oi: float = 10000) -> List[Dict[str, Any]]:
        """
        获取活跃品种（优先从本地DB）
        
        Args:
            min_oi: 最小持仓量
        
        Returns:
            活跃品种列表
        """
        # 从 SQLite 获取（COALESCE 处理 NULL OI）
        symbols = self.sqlite.get_active_symbols(min_oi)
        
        # 如果 SQLite 的 OI 全为 NULL，尝试从 DuckDB quotes 表补充
        if symbols and all(s.get('open_interest') is None for s in symbols):
            print("[提示] symbols 表 OI 为空，从 DuckDB quotes 表补充...")
            for s in symbols:
                quote = self.duckdb.get_latest_quote(s['symbol'])
                if quote and quote.get('open_interest'):
                    s['open_interest'] = quote['open_interest']
            
            # 重新筛选
            symbols = [s for s in symbols if (s.get('open_interest') or 0) >= min_oi]
            symbols.sort(key=lambda x: x.get('open_interest') or 0, reverse=True)
        
        return symbols
    
    # ============================================================
    # 统计信息
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'sqlite': self.sqlite.get_statistics(),
            'duckdb': self.duckdb.get_statistics()
        }
    
    def print_statistics(self):
        """打印统计信息"""
        stats = self.get_statistics()
        
        print("\n" + "=" * 60)
        print("数据库统计信息")
        print("=" * 60)
        
        # SQLite 统计
        sqlite_stats = stats.get('sqlite', {})
        print("\n[SQLite - meta.db]")
        print(f"  品种总数: {sqlite_stats.get('total_symbols', 0)}")
        print(f"  活跃品种: {sqlite_stats.get('active_symbols', 0)}")
        print(f"  已同步品种: {sqlite_stats.get('synced_symbols', 0)}")
        print(f"  待同步品种: {sqlite_stats.get('pending_sync', 0)}")
        print(f"  分析记录: {sqlite_stats.get('total_analyses', 0)}")
        print(f"  今日分析: {sqlite_stats.get('today_analyses', 0)}")
        
        # DuckDB 统计
        duckdb_stats = stats.get('duckdb', {})
        
        klines = duckdb_stats.get('klines', {})
        print("\n[DuckDB - market.db]")
        print(f"  K线品种: {klines.get('symbols', 0)}")
        print(f"  K线记录: {klines.get('records', 0)}")
        print(f"  最早数据: {klines.get('earliest', 'N/A')}")
        print(f"  最新数据: {klines.get('latest', 'N/A')}")
        
        indicators = duckdb_stats.get('indicators', {})
        print(f"  指标品种: {indicators.get('symbols', 0)}")
        print(f"  指标类型: {indicators.get('indicator_types', 0)}")
        print(f"  指标记录: {indicators.get('records', 0)}")
        
        quotes = duckdb_stats.get('quotes', {})
        print(f"  行情品种: {quotes.get('symbols', 0)}")
        print(f"  行情记录: {quotes.get('records', 0)}")
        print(f"  最新行情: {quotes.get('latest', 'N/A')}")
        
        db_size = duckdb_stats.get('db_size_mb', 0)
        print(f"\n  数据库大小: {db_size:.2f} MB")


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数据同步管理器')
    parser.add_argument('action', choices=['sync', 'stats', 'symbols', 'quotes', 'klines'],
                       help='操作类型')
    parser.add_argument('--days', type=int, default=120, help='K线天数')
    parser.add_argument('--min-oi', type=float, default=10000, help='最小持仓量')
    parser.add_argument('--force', action='store_true', help='强制全量同步')
    
    args = parser.parse_args()
    
    # 创建同步管理器
    manager = DataSyncManager()
    
    if args.action == 'sync':
        # 全量同步
        result = manager.full_sync(days=args.days, min_oi=args.min_oi)
        print(f"\n同步结果: {result}")
        
    elif args.action == 'stats':
        # 打印统计信息
        manager.print_statistics()
        
    elif args.action == 'symbols':
        # 同步品种
        result = manager.sync_symbols()
        print(f"\n品种同步结果: {result}")
        
    elif args.action == 'quotes':
        # 同步行情
        result = manager.sync_quotes(min_oi=args.min_oi)
        print(f"\n行情同步结果: {result}")
        
    elif args.action == 'klines':
        # 同步K线
        active_symbols = manager.get_active_symbols(min_oi=args.min_oi)
        symbol_codes = [s['symbol'] for s in active_symbols]
        result = manager.sync_klines(symbols=symbol_codes, days=args.days, force=args.force)
        print(f"\nK线同步结果: {result}")


if __name__ == '__main__':
    main()
