"""
SQLite 存储模块

存储事务型数据：
- 品种元数据
- 配置信息
- 交易日志
- 同步状态
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class SQLiteStore:
    """SQLite 存储管理器"""
    
    def __init__(self, db_path: str = "data/meta.db"):
        """
        初始化 SQLite 存储
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()
    
    def _ensure_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    
    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn
    
    def _init_db(self):
        """初始化数据库表结构"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            # 1. 品种元数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    symbol VARCHAR(20) PRIMARY KEY,
                    exchange VARCHAR(10) NOT NULL,
                    variety VARCHAR(20) NOT NULL,
                    tq_symbol VARCHAR(50),
                    name VARCHAR(50),
                    
                    -- 合约信息
                    contract_size DOUBLE,
                    price_tick DOUBLE,
                    margin_rate DOUBLE,
                    
                    -- 状态
                    is_active BOOLEAN DEFAULT 1,
                    is_main_contract BOOLEAN DEFAULT 1,
                    
                    -- 最新行情（缓存）
                    last_price DOUBLE,
                    open_interest DOUBLE,
                    volume DOUBLE,
                    last_quote_time TIMESTAMP,
                    
                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. 同步状态表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_status (
                    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol VARCHAR(20) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL DEFAULT 'daily',
                    
                    -- 同步范围
                    earliest_date DATE,
                    latest_date DATE,
                    record_count INTEGER DEFAULT 0,
                    
                    -- 同步状态
                    status VARCHAR(20) DEFAULT 'pending',
                    last_sync_time TIMESTAMP,
                    last_error TEXT,
                    
                    -- 元数据
                    source VARCHAR(20) DEFAULT 'tqsdk',
                    
                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(symbol, timeframe)
                )
            """)
            
            # 3. 分析结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol VARCHAR(20) NOT NULL,
                    analysis_time TIMESTAMP NOT NULL,
                    
                    -- 信号信息
                    direction VARCHAR(10),
                    trend_phase VARCHAR(20),
                    signal_strength VARCHAR(10),
                    
                    -- 指标值
                    er DOUBLE,
                    tsi DOUBLE,
                    r_squared DOUBLE,
                    trend_strength DOUBLE,
                    rsi DOUBLE,
                    adx DOUBLE,
                    
                    -- Agent 分析
                    brief_json TEXT,
                    debate_json TEXT,
                    
                    -- 状态
                    status VARCHAR(20) DEFAULT 'success',
                    error_message TEXT,
                    
                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 4. 配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    config_key VARCHAR(50) PRIMARY KEY,
                    config_value TEXT NOT NULL,
                    config_type VARCHAR(20) DEFAULT 'json',
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_exchange ON symbols(exchange)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_variety ON symbols(variety)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_status_symbol ON sync_status(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_symbol ON analysis_results(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_time ON analysis_results(analysis_time)")
            
            conn.commit()
            
        finally:
            conn.close()
    
    # ============================================================
    # 品种元数据操作
    # ============================================================
    
    def upsert_symbol(self, symbol_info: Dict[str, Any]):
        """
        插入或更新品种信息
        
        Args:
            symbol_info: 品种信息字典
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO symbols (symbol, exchange, variety, tq_symbol, name, is_active, is_main_contract)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    exchange = excluded.exchange,
                    variety = excluded.variety,
                    tq_symbol = excluded.tq_symbol,
                    name = excluded.name,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                symbol_info.get('symbol'),
                symbol_info.get('exchange'),
                symbol_info.get('variety'),
                symbol_info.get('tq_symbol'),
                symbol_info.get('name', symbol_info.get('symbol')),
                symbol_info.get('is_active', True),
                symbol_info.get('is_main_contract', True)
            ))
            conn.commit()
        finally:
            conn.close()
    
    def upsert_symbols_batch(self, symbols: List[Dict[str, Any]]):
        """
        批量插入或更新品种信息
        
        Args:
            symbols: 品种信息列表
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            for symbol_info in symbols:
                cursor.execute("""
                    INSERT INTO symbols (symbol, exchange, variety, tq_symbol, name, is_active, is_main_contract)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        exchange = excluded.exchange,
                        variety = excluded.variety,
                        tq_symbol = excluded.tq_symbol,
                        name = excluded.name,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    symbol_info.get('symbol'),
                    symbol_info.get('exchange'),
                    symbol_info.get('variety'),
                    symbol_info.get('tq_symbol'),
                    symbol_info.get('name', symbol_info.get('symbol')),
                    symbol_info.get('is_active', True),
                    symbol_info.get('is_main_contract', True)
                ))
            conn.commit()
        finally:
            conn.close()
    
    def update_symbol_quote(self, symbol: str, quote: Dict[str, Any]):
        """
        更新品种最新行情
        
        Args:
            symbol: 品种代码
            quote: 行情数据
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE symbols SET
                    last_price = ?,
                    open_interest = ?,
                    volume = ?,
                    last_quote_time = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE symbol = ?
            """, (
                quote.get('last_price'),
                quote.get('open_interest'),
                quote.get('volume'),
                quote.get('timestamp', datetime.now().isoformat()),
                symbol
            ))
            conn.commit()
        finally:
            conn.close()
    
    def get_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取品种信息
        
        Args:
            symbol: 品种代码
        
        Returns:
            品种信息字典
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM symbols WHERE symbol = ?", (symbol,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()
    
    def get_all_symbols(self, exchange: str = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        获取所有品种
        
        Args:
            exchange: 交易所筛选
            active_only: 只返回活跃品种
        
        Returns:
            品种信息列表
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            query = "SELECT * FROM symbols WHERE 1=1"
            params = []
            
            if exchange:
                query += " AND exchange = ?"
                params.append(exchange)
            
            if active_only:
                query += " AND is_active = 1"
            
            query += " ORDER BY exchange, variety"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_active_symbols(self, min_oi: float = 10000) -> List[Dict[str, Any]]:
        """
        获取活跃品种（持仓量≥阈值）
        
        Args:
            min_oi: 最小持仓量
        
        Returns:
            活跃品种列表
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM symbols 
                WHERE is_active = 1 
                AND COALESCE(open_interest, 0) >= ?
                ORDER BY open_interest DESC
            """, (min_oi,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    # ============================================================
    # 同步状态操作
    # ============================================================
    
    def get_sync_status(self, symbol: str, timeframe: str = 'daily') -> Optional[Dict[str, Any]]:
        """
        获取同步状态
        
        Args:
            symbol: 品种代码
            timeframe: 时间周期
        
        Returns:
            同步状态字典
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sync_status 
                WHERE symbol = ? AND timeframe = ?
            """, (symbol, timeframe))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()
    
    def update_sync_status(self, symbol: str, timeframe: str, status: str,
                          earliest_date: str = None, latest_date: str = None,
                          record_count: int = None, error: str = None):
        """
        更新同步状态
        
        Args:
            symbol: 品种代码
            timeframe: 时间周期
            status: 状态
            earliest_date: 最早日期
            latest_date: 最新日期
            record_count: 记录数
            error: 错误信息
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_status (symbol, timeframe, status, earliest_date, latest_date, 
                                        record_count, last_sync_time, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe) DO UPDATE SET
                    status = excluded.status,
                    earliest_date = COALESCE(excluded.earliest_date, earliest_date),
                    latest_date = COALESCE(excluded.latest_date, latest_date),
                    record_count = COALESCE(excluded.record_count, record_count),
                    last_sync_time = CASE WHEN excluded.status = 'success' THEN CURRENT_TIMESTAMP ELSE last_sync_time END,
                    last_error = excluded.last_error,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                symbol, timeframe, status,
                earliest_date, latest_date, record_count,
                datetime.now().isoformat() if status == 'success' else None,
                error
            ))
            conn.commit()
        finally:
            conn.close()
    
    def get_pending_sync_symbols(self, timeframe: str = 'daily') -> List[str]:
        """
        获取待同步的品种列表
        
        Args:
            timeframe: 时间周期
        
        Returns:
            品种代码列表
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.symbol 
                FROM symbols s
                LEFT JOIN sync_status ss ON s.symbol = ss.symbol AND ss.timeframe = ?
                WHERE s.is_active = 1 
                AND (ss.symbol IS NULL OR ss.status != 'success')
                ORDER BY s.exchange, s.variety
            """, (timeframe,))
            rows = cursor.fetchall()
            return [row['symbol'] for row in rows]
        finally:
            conn.close()
    
    # ============================================================
    # 分析结果操作
    # ============================================================
    
    def save_analysis_result(self, result: Dict[str, Any]):
        """
        保存分析结果
        
        Args:
            result: 分析结果字典
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            indicators = result.get('indicators', {})
            cursor.execute("""
                INSERT INTO analysis_results (
                    symbol, analysis_time, direction, trend_phase, signal_strength,
                    er, tsi, r_squared, trend_strength, rsi, adx,
                    brief_json, debate_json, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.get('symbol'),
                result.get('analysis_time', datetime.now().isoformat()),
                indicators.get('direction'),
                indicators.get('trend_phase'),
                self._classify_signal_strength(indicators),
                indicators.get('er'),
                indicators.get('tsi'),
                indicators.get('r_squared'),
                indicators.get('trend_strength'),
                indicators.get('rsi'),
                indicators.get('adx'),
                json.dumps(result.get('brief'), ensure_ascii=False) if result.get('brief') else None,
                json.dumps(result.get('debate'), ensure_ascii=False) if result.get('debate') else None,
                result.get('status', 'success'),
                result.get('error')
            ))
            conn.commit()
        finally:
            conn.close()
    
    def _classify_signal_strength(self, indicators: Dict[str, Any]) -> str:
        """分类信号强度"""
        er = indicators.get('er', 0)
        tsi = abs(indicators.get('tsi', 0))
        trend_strength = indicators.get('trend_strength', 0)
        
        if er > 0.7 and tsi > 30 and trend_strength > 0.7:
            return 'STRONG'
        elif er > 0.6 and tsi > 20:
            return 'MEDIUM'
        else:
            return 'WEAK'
    
    def get_latest_analysis(self, symbol: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最新分析结果
        
        Args:
            symbol: 品种筛选
            limit: 返回数量
        
        Returns:
            分析结果列表
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute("""
                    SELECT * FROM analysis_results 
                    WHERE symbol = ?
                    ORDER BY analysis_time DESC
                    LIMIT ?
                """, (symbol, limit))
            else:
                cursor.execute("""
                    SELECT * FROM analysis_results 
                    ORDER BY analysis_time DESC
                    LIMIT ?
                """, (limit,))
            
            rows = cursor.fetchall()
            results = []
            for row in rows:
                result = dict(row)
                # 解析 JSON 字段
                if result.get('brief_json'):
                    try:
                        result['brief'] = json.loads(result['brief_json'])
                    except:
                        pass
                if result.get('debate_json'):
                    try:
                        result['debate'] = json.loads(result['debate_json'])
                    except:
                        pass
                results.append(result)
            
            return results
        finally:
            conn.close()
    
    # ============================================================
    # 配置操作
    # ============================================================
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键
            default: 默认值
        
        Returns:
            配置值
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT config_value, config_type FROM config WHERE config_key = ?", (key,))
            row = cursor.fetchone()
            if row:
                value = row['config_value']
                config_type = row['config_type']
                
                if config_type == 'json':
                    return json.loads(value)
                elif config_type == 'number':
                    return float(value)
                elif config_type == 'boolean':
                    return value.lower() in ('true', '1', 'yes')
                else:
                    return value
            
            return default
        finally:
            conn.close()
    
    def set_config(self, key: str, value: Any, config_type: str = 'json', description: str = None):
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            config_type: 配置类型
            description: 描述
        """
        if config_type == 'json':
            value_str = json.dumps(value, ensure_ascii=False)
        else:
            value_str = str(value)
        
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO config (config_key, config_value, config_type, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(config_key) DO UPDATE SET
                    config_value = excluded.config_value,
                    config_type = excluded.config_type,
                    description = COALESCE(excluded.description, description),
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value_str, config_type, description))
            conn.commit()
        finally:
            conn.close()
    
    # ============================================================
    # 统计查询
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            统计信息字典
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            
            stats = {}
            
            # 品种统计
            cursor.execute("SELECT COUNT(*) as total FROM symbols")
            stats['total_symbols'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as active FROM symbols WHERE is_active = 1")
            stats['active_symbols'] = cursor.fetchone()['active']
            
            # 同步统计
            cursor.execute("SELECT COUNT(*) as synced FROM sync_status WHERE status = 'success'")
            stats['synced_symbols'] = cursor.fetchone()['synced']
            
            cursor.execute("SELECT COUNT(*) as pending FROM sync_status WHERE status = 'pending'")
            stats['pending_sync'] = cursor.fetchone()['pending']
            
            # 分析统计
            cursor.execute("SELECT COUNT(*) as total FROM analysis_results")
            stats['total_analyses'] = cursor.fetchone()['total']
            
            cursor.execute("""
                SELECT COUNT(*) as today 
                FROM analysis_results 
                WHERE DATE(analysis_time) = DATE('now')
            """)
            stats['today_analyses'] = cursor.fetchone()['today']
            
            return stats
        finally:
            conn.close()
