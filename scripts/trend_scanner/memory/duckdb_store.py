"""
DuckDB 分析型存储

职责：
- 存储 K 线时序数据、技术指标历史、因子库
- 提供高性能聚合查询
- 支持向量化分析

表结构：
- klines: K线数据表（列式存储）
- indicators: 技术指标历史表
- factor_library: 因子库表
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

try:
    import duckdb
    import pandas as pd
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


class DuckDBStore:
    """DuckDB 分析型存储"""
    
    def __init__(self, db_path: str):
        """
        初始化 DuckDB 存储
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn = None
        
        if not HAS_DUCKDB:
            print("[警告] DuckDB 未安装，分析功能将不可用")
            return
        
        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 连接数据库
        self.conn = duckdb.connect(db_path)
    
    def init_tables(self):
        """初始化表结构"""
        if not self.conn:
            return
        
        # 1. K线数据表
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS klines (
            symbol VARCHAR NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            timeframe VARCHAR NOT NULL,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            open_interest DOUBLE,
            source VARCHAR DEFAULT 'tqsdk',
            created_at TIMESTAMP DEFAULT current_timestamp
        )
        """)
        
        # 2. 技术指标历史表
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS indicators (
            symbol VARCHAR NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            indicator_name VARCHAR NOT NULL,
            value DOUBLE,
            parameters VARCHAR,
            created_at TIMESTAMP DEFAULT current_timestamp
        )
        """)
        
        # 3. 因子库表
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS factor_library (
            factor_id VARCHAR PRIMARY KEY,
            factor_name VARCHAR NOT NULL,
            factor_type VARCHAR NOT NULL,
            expression VARCHAR NOT NULL,
            parameters VARCHAR,
            ic_mean DOUBLE,
            ic_std DOUBLE,
            ir DOUBLE,
            turnover DOUBLE,
            status VARCHAR DEFAULT 'active',
            confidence DOUBLE DEFAULT 0.5,
            created_at TIMESTAMP DEFAULT current_timestamp,
            last_evaluated_at TIMESTAMP
        )
        """)
        
        # 创建索引
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_klines_symbol_time ON klines(symbol, timestamp)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_symbol_name ON indicators(symbol, indicator_name)")
        except:
            pass  # DuckDB 索引语法可能不同
    
    # ========== K线数据操作 ==========
    
    def insert_klines(self, klines: List[Dict[str, Any]]):
        """批量插入 K 线数据"""
        if not self.conn or not klines:
            return
        
        # 转换为 DataFrame
        df = pd.DataFrame(klines)
        
        # 插入数据
        self.conn.execute("""
        INSERT INTO klines (symbol, timestamp, timeframe, open, high, low, close, volume, open_interest, source)
        SELECT symbol, timestamp, timeframe, open, high, low, close, volume, open_interest, source
        FROM df
        """)
    
    def get_klines(
        self,
        symbol: str,
        timeframe: str = 'daily',
        start_date: str = None,
        end_date: str = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """获取 K 线数据"""
        if not self.conn:
            return pd.DataFrame()
        
        query = """
        SELECT * FROM klines
        WHERE symbol = ? AND timeframe = ?
        """
        params = [symbol, timeframe]
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        return self.conn.execute(query, params).fetchdf()
    
    # ========== 技术指标操作 ==========
    
    def insert_indicators(self, indicators: List[Dict[str, Any]]):
        """批量插入技术指标"""
        if not self.conn or not indicators:
            return
        
        df = pd.DataFrame(indicators)
        
        self.conn.execute("""
        INSERT INTO indicators (symbol, timestamp, indicator_name, value, parameters)
        SELECT symbol, timestamp, indicator_name, value, parameters
        FROM df
        """)
    
    def get_indicators(
        self,
        symbol: str,
        indicator_name: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> pd.DataFrame:
        """获取技术指标"""
        if not self.conn:
            return pd.DataFrame()
        
        query = """
        SELECT * FROM indicators
        WHERE symbol = ?
        """
        params = [symbol]
        
        if indicator_name:
            query += " AND indicator_name = ?"
            params.append(indicator_name)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC"
        
        return self.conn.execute(query, params).fetchdf()
    
    # ========== 因子库操作 ==========
    
    def insert_factor(self, factor: Dict[str, Any]):
        """插入一个因子"""
        if not self.conn:
            return
        
        self.conn.execute("""
        INSERT OR REPLACE INTO factor_library (
            factor_id, factor_name, factor_type, expression, parameters,
            ic_mean, ic_std, ir, turnover, status, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            factor.get('factor_id'),
            factor.get('factor_name'),
            factor.get('factor_type'),
            factor.get('expression'),
            json.dumps(factor.get('parameters', {})),
            factor.get('ic_mean'),
            factor.get('ic_std'),
            factor.get('ir'),
            factor.get('turnover'),
            factor.get('status', 'active'),
            factor.get('confidence', 0.5)
        ))
    
    def get_factor_performance(self) -> List[Dict[str, Any]]:
        """获取因子性能"""
        if not self.conn:
            return []
        
        result = self.conn.execute("""
        SELECT * FROM factor_library
        WHERE status = 'active'
        ORDER BY ir DESC
        """).fetchdf()
        
        return result.to_dict('records') if not result.empty else []
    
    # ========== 分析查询 ==========
    
    def analyze_performance(self, symbol: str = None, days: int = 30) -> Dict[str, Any]:
        """分析交易性能"""
        if not self.conn:
            return {}
        
        # 这里需要从 SQLite 获取交易数据进行分析
        # 由于 DuckDB 主要用于时序数据分析，交易数据在 SQLite 中
        # 这里提供一个示例框架
        
        return {
            'symbol': symbol,
            'analysis_period_days': days,
            'note': '交易性能分析需要从 SQLite 获取数据'
        }
    
    def analyze_correlation(self, symbols: List[str], days: int = 30) -> pd.DataFrame:
        """分析品种相关性"""
        if not self.conn or not symbols:
            return pd.DataFrame()
        
        # 获取各品种的收盘价
        placeholders = ','.join(['?' for _ in symbols])
        query = f"""
        SELECT symbol, timestamp, close
        FROM klines
        WHERE symbol IN ({placeholders})
        AND timestamp >= current_date - INTERVAL '{days} days'
        ORDER BY timestamp
        """
        
        df = self.conn.execute(query, symbols).fetchdf()
        
        if df.empty:
            return pd.DataFrame()
        
        # 转换为宽表并计算相关性
        pivot = df.pivot(index='timestamp', columns='symbol', values='close')
        return pivot.corr()
    
    def analyze_volatility(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        """分析波动率"""
        if not self.conn:
            return {}
        
        query = f"""
        SELECT 
            AVG((high - low) / close * 100) as avg_daily_range,
            STDDEV((high - low) / close * 100) as std_daily_range,
            MAX((high - low) / close * 100) as max_daily_range,
            MIN((high - low) / close * 100) as min_daily_range
        FROM klines
        WHERE symbol = ?
        AND timestamp >= current_date - INTERVAL '{days} days'
        """
        
        result = self.conn.execute(query, [symbol]).fetchone()
        
        if result:
            return {
                'symbol': symbol,
                'avg_daily_range': result[0],
                'std_daily_range': result[1],
                'max_daily_range': result[2],
                'min_daily_range': result[3]
            }
        return {}
    
    # ========== 内部方法 ==========
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
