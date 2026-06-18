"""
期货数据路由

统一管理期货数据获取、存储、更新
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import pandas as pd

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class FuturesDataRouter:
    """
    期货数据路由
    
    统一管理期货数据获取、存储、更新
    """
    
    def __init__(self, db_path: str = "data/futures.db"):
        """
        初始化数据路由
        
        Args:
            db_path: DuckDB数据库路径
        """
        self.db_path = db_path
        self.db = duckdb.connect(db_path)
        self._init_tables()
        
        # 数据源适配器
        self._tqsdk_provider = None
        self._tdx_provider = None
        self._akshare_provider = None
    
    def _init_tables(self):
        """初始化数据库表"""
        # K线数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS futures_kline (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                open_interest BIGINT,
                close_oi BIGINT,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 库存数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS futures_inventory (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                inventory BIGINT,
                change_amount BIGINT,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 仓单数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS futures_warehouse_receipt (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                exchange VARCHAR,
                warehouse VARCHAR,
                receipt_amount BIGINT,
                change_amount BIGINT,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date, warehouse)
            )
        """)
        
        # 技术指标表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS futures_indicators (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                -- 趋势指标
                ema5 DOUBLE,
                ema10 DOUBLE,
                ema20 DOUBLE,
                ema60 DOUBLE,
                ma5 DOUBLE,
                ma10 DOUBLE,
                ma20 DOUBLE,
                ma60 DOUBLE,
                -- 动量指标
                rsi14 DOUBLE,
                rsi6 DOUBLE,
                macd DOUBLE,
                macd_signal DOUBLE,
                macd_hist DOUBLE,
                kdj_k DOUBLE,
                kdj_d DOUBLE,
                kdj_j DOUBLE,
                -- 波动率指标
                atr14 DOUBLE,
                boll_upper DOUBLE,
                boll_middle DOUBLE,
                boll_lower DOUBLE,
                std20 DOUBLE,
                -- 成交量指标
                obv DOUBLE,
                vwap DOUBLE,
                -- 趋势强度
                adx14 DOUBLE,
                plus_di DOUBLE,
                minus_di DOUBLE,
                -- 自研指标
                trend_strength DOUBLE,
                momentum_score DOUBLE,
                volatility_regime DOUBLE,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 基差数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS futures_basis (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                spot_price DOUBLE,
                futures_price DOUBLE,
                basis DOUBLE,
                basis_rate DOUBLE,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 期限结构表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS futures_term_structure (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                near_month VARCHAR,
                near_price DOUBLE,
                far_month VARCHAR,
                far_price DOUBLE,
                roll_yield DOUBLE,
                structure_type VARCHAR,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 持仓排名表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS futures_position_rank (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                rank_type VARCHAR,
                rank_number INT,
                member_name VARCHAR,
                position_volume BIGINT,
                change_volume BIGINT,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date, rank_type, rank_number)
            )
        """)
        
        # 宏观数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS macro_data (
                subject VARCHAR NOT NULL,
                indicator VARCHAR NOT NULL,
                date DATE NOT NULL,
                value DOUBLE,
                unit VARCHAR,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (subject, indicator, date)
            )
        """)
        
        # 研报数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS research_report (
                symbol VARCHAR,
                title VARCHAR,
                author VARCHAR,
                rating VARCHAR,
                target_price DOUBLE,
                summary TEXT,
                publish_date DATE,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (title, publish_date)
            )
        """)
        
        # 数据更新日志表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS data_update_log (
                update_id SERIAL PRIMARY KEY,
                table_name VARCHAR NOT NULL,
                symbol VARCHAR,
                update_type VARCHAR,
                status VARCHAR,
                records_count INT,
                error_message TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                data_source VARCHAR
            )
        """)
        
        # 交易日历表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS trading_calendar (
                date DATE PRIMARY KEY,
                is_trading_day BOOLEAN,
                exchange VARCHAR,
                update_time TIMESTAMP
            )
        """)
    
    def get_kline(self, symbol: str, timeframe: str = "daily", count: int = 100) -> pd.DataFrame:
        """
        获取K线数据
        
        Args:
            symbol: 品种代码
            timeframe: 时间周期
            count: 数据条数
            
        Returns:
            DataFrame: K线数据
        """
        # 优先从数据库读取
        df = self.db.execute(f"""
            SELECT * FROM futures_kline 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT {count}
        """).fetchdf()
        
        if len(df) >= count:
            return df.sort_values('date')
        
        # 数据不足，从TqSdk获取
        try:
            from scripts.futures.provider import FuturesProvider
            provider = FuturesProvider({})
            df = provider.get_kline(symbol, timeframe, count)
            provider.close()
            
            # 写入数据库
            self._save_kline(symbol, df)
            
            return df
        except Exception as e:
            logger.error(f"获取{symbol}K线数据失败: {e}")
            return df.sort_values('date') if len(df) > 0 else pd.DataFrame()
    
    def _save_kline(self, symbol: str, df: pd.DataFrame):
        """保存K线数据到数据库"""
        for index, row in df.iterrows():
            try:
                self.db.execute(f"""
                    INSERT OR REPLACE INTO futures_kline 
                    (symbol, date, open, high, low, close, volume, open_interest, data_source, update_time)
                    VALUES ('{symbol}', '{index.date()}', {row['open']}, {row['high']}, 
                            {row['low']}, {row['close']}, {row['volume']}, 
                            {row.get('open_interest', 0)}, 'tqsdk', CURRENT_TIMESTAMP)
                """)
            except Exception as e:
                logger.error(f"保存{symbol}K线数据失败: {e}")
    
    def get_indicators(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """
        获取技术指标数据
        
        Args:
            symbol: 品种代码
            days: 获取天数
            
        Returns:
            DataFrame: 技术指标数据
        """
        return self.db.execute(f"""
            SELECT * FROM futures_indicators 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT {days}
        """).fetchdf()
    
    def save_indicators(self, symbol: str, df: pd.DataFrame, source: str = "local"):
        """
        保存技术指标数据
        
        Args:
            symbol: 品种代码
            df: 技术指标DataFrame
            source: 数据来源 (tqsdk/local)
        """
        for index, row in df.iterrows():
            try:
                # 构建INSERT语句
                columns = ['symbol', 'date', 'data_source', 'update_time']
                values = [f"'{symbol}'", f"'{index.date()}'", f"'{source}'", "CURRENT_TIMESTAMP"]
                
                # 添加指标值
                indicator_cols = [
                    'ema5', 'ema10', 'ema20', 'ema60',
                    'ma5', 'ma10', 'ma20', 'ma60',
                    'rsi14', 'rsi6',
                    'macd', 'macd_signal', 'macd_hist',
                    'kdj_k', 'kdj_d', 'kdj_j',
                    'atr14', 'boll_upper', 'boll_middle', 'boll_lower', 'std20',
                    'obv', 'vwap',
                    'adx14', 'plus_di', 'minus_di',
                    'trend_strength', 'momentum_score', 'volatility_regime'
                ]
                
                for col in indicator_cols:
                    if col in row.index:
                        columns.append(col)
                        val = row[col]
                        if pd.isna(val):
                            values.append("NULL")
                        else:
                            values.append(str(val))
                
                sql = f"""
                    INSERT OR REPLACE INTO futures_indicators 
                    ({', '.join(columns)})
                    VALUES ({', '.join(values)})
                """
                self.db.execute(sql)
            except Exception as e:
                logger.error(f"保存{symbol}技术指标失败: {e}")
    
    def calculate_and_save_indicators(self, symbol: str, kline_df: pd.DataFrame):
        """
        计算并保存技术指标
        
        Args:
            symbol: 品种代码
            kline_df: K线数据
        """
        import numpy as np
        
        if kline_df.empty or len(kline_df) < 20:
            return
        
        # 计算技术指标
        df = kline_df.copy()
        
        # EMA
        df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
        df['ema10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema60'] = df['close'].ewm(span=60, adjust=False).mean()
        
        # MA
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi14'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr14'] = true_range.rolling(14).mean()
        
        # Bollinger Bands
        df['boll_middle'] = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        df['boll_upper'] = df['boll_middle'] + 2 * std
        df['boll_lower'] = df['boll_middle'] - 2 * std
        df['std20'] = std
        
        # 保存指标
        self.save_indicators(symbol, df, source="local")
    
    def get_inventory(self, symbol: str) -> pd.DataFrame:
        """获取库存数据"""
        return self.db.execute(f"""
            SELECT * FROM futures_inventory 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT 30
        """).fetchdf()
    
    def get_basis(self, symbol: str) -> pd.DataFrame:
        """获取基差数据"""
        return self.db.execute(f"""
            SELECT * FROM futures_basis 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT 30
        """).fetchdf()
    
    def get_term_structure(self, symbol: str) -> pd.DataFrame:
        """获取期限结构数据"""
        return self.db.execute(f"""
            SELECT * FROM futures_term_structure 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT 30
        """).fetchdf()
    
    def get_position_rank(self, symbol: str) -> pd.DataFrame:
        """获取持仓排名数据"""
        return self.db.execute(f"""
            SELECT * FROM futures_position_rank 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC, rank_type, rank_number
            LIMIT 100
        """).fetchdf()
    
    def get_update_log(self, days: int = 7) -> pd.DataFrame:
        """获取更新日志"""
        return self.db.execute(f"""
            SELECT * FROM data_update_log 
            WHERE start_time >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY start_time DESC
        """).fetchdf()
    
    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()
