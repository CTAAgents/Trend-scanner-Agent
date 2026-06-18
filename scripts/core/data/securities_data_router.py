"""
证券数据路由

统一管理证券数据获取、存储、更新
技术指标优先使用通达信MCP数据
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


class SecuritiesDataRouter:
    """
    证券数据路由
    
    统一管理证券数据获取、存储、更新
    技术指标优先使用通达信MCP数据
    """
    
    def __init__(self, db_path: str = "data/securities.db"):
        """
        初始化数据路由
        
        Args:
            db_path: DuckDB数据库路径
        """
        self.db_path = db_path
        self.db = duckdb.connect(db_path)
        self._init_tables()
    
    def _init_tables(self):
        """初始化数据库表"""
        # K线数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_kline (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                amount DOUBLE,
                turnover_rate DOUBLE,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 技术指标表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_indicators (
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
                ma120 DOUBLE,
                ma250 DOUBLE,
                -- 动量指标
                rsi6 DOUBLE,
                rsi12 DOUBLE,
                rsi14 DOUBLE,
                macd_dif DOUBLE,
                macd_dea DOUBLE,
                macd_hist DOUBLE,
                kdj_k DOUBLE,
                kdj_d DOUBLE,
                kdj_j DOUBLE,
                cci DOUBLE,
                wr6 DOUBLE,
                wr10 DOUBLE,
                -- 波动率指标
                atr14 DOUBLE,
                boll_upper DOUBLE,
                boll_middle DOUBLE,
                boll_lower DOUBLE,
                std20 DOUBLE,
                bias6 DOUBLE,
                bias12 DOUBLE,
                bias24 DOUBLE,
                -- 成交量指标
                obv DOUBLE,
                vwap DOUBLE,
                -- 趋势强度
                adx14 DOUBLE,
                plus_di DOUBLE,
                minus_di DOUBLE,
                dmi DOUBLE,
                sar DOUBLE,
                trix DOUBLE,
                dma DOUBLE,
                expma DOUBLE,
                roc DOUBLE,
                mtm DOUBLE,
                psy DOUBLE,
                -- 自研指标
                trend_strength DOUBLE,
                momentum_score DOUBLE,
                volatility_regime DOUBLE,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 财务数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_financial (
                symbol VARCHAR NOT NULL,
                report_date DATE NOT NULL,
                report_type VARCHAR,
                revenue DOUBLE,
                net_profit DOUBLE,
                operating_profit DOUBLE,
                gross_profit_margin DOUBLE,
                net_profit_margin DOUBLE,
                total_assets DOUBLE,
                total_liabilities DOUBLE,
                total_equity DOUBLE,
                debt_ratio DOUBLE,
                current_ratio DOUBLE,
                quick_ratio DOUBLE,
                operating_cashflow DOUBLE,
                investing_cashflow DOUBLE,
                financing_cashflow DOUBLE,
                free_cashflow DOUBLE,
                roe DOUBLE,
                roa DOUBLE,
                eps DOUBLE,
                bps DOUBLE,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, report_date)
            )
        """)
        
        # 估值数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_valuation (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                pe_ratio DOUBLE,
                pe_ratio_ttm DOUBLE,
                pb_ratio DOUBLE,
                ps_ratio DOUBLE,
                pcf_ratio DOUBLE,
                dividend_yield DOUBLE,
                pe_percentile DOUBLE,
                pb_percentile DOUBLE,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 股东数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_shareholder (
                symbol VARCHAR NOT NULL,
                report_date DATE NOT NULL,
                shareholder_count BIGINT,
                shareholder_count_change BIGINT,
                shareholder_count_change_pct DOUBLE,
                top10_holders TEXT,
                institutional_holding_pct DOUBLE,
                institutional_count INT,
                controlling_shareholder VARCHAR,
                actual_controller VARCHAR,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, report_date)
            )
        """)
        
        # 分红数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_dividend (
                symbol VARCHAR NOT NULL,
                dividend_date DATE NOT NULL,
                ex_date DATE,
                dividend_per_share DOUBLE,
                bonus_shares DOUBLE,
                transfer_shares DOUBLE,
                dividend_yield DOUBLE,
                payout_ratio DOUBLE,
                consecutive_years INT,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, dividend_date)
            )
        """)
        
        # 龙虎榜数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_dragon_tiger (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                reason VARCHAR,
                net_buy_amount DOUBLE,
                buy_amount DOUBLE,
                sell_amount DOUBLE,
                institutional_buy DOUBLE,
                institutional_sell DOUBLE,
                seat_data TEXT,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 大宗交易数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_block_trade (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                trade_price DOUBLE,
                trade_volume BIGINT,
                trade_amount DOUBLE,
                premium_rate DOUBLE,
                buyer_name VARCHAR,
                seller_name VARCHAR,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 融资融券数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_margin_trading (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                margin_buy_balance DOUBLE,
                margin_buy_amount DOUBLE,
                margin_buy_repay DOUBLE,
                short_sell_balance DOUBLE,
                short_sell_volume BIGINT,
                short_sell_amount DOUBLE,
                short_sell_repay DOUBLE,
                total_balance DOUBLE,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 北向资金数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_northbound (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                share_holding BIGINT,
                market_value DOUBLE,
                holding_pct DOUBLE,
                share_change BIGINT,
                market_value_change DOUBLE,
                net_buy_amount DOUBLE,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        # 行业数据表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS securities_industry (
                symbol VARCHAR NOT NULL,
                industry_code VARCHAR,
                industry_name VARCHAR,
                industry_rank INT,
                industry_pe DOUBLE,
                industry_pb DOUBLE,
                pe_rank INT,
                pb_rank INT,
                roe_rank INT,
                data_source VARCHAR,
                update_time TIMESTAMP,
                PRIMARY KEY (symbol)
            )
        """)
    
    def get_kline(self, symbol: str, count: int = 100) -> pd.DataFrame:
        """获取K线数据"""
        return self.db.execute(f"""
            SELECT * FROM securities_kline 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT {count}
        """).fetchdf()
    
    def get_indicators(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """获取技术指标数据"""
        return self.db.execute(f"""
            SELECT * FROM securities_indicators 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT {days}
        """).fetchdf()
    
    def get_financial(self, symbol: str, periods: int = 4) -> pd.DataFrame:
        """获取财务数据"""
        return self.db.execute(f"""
            SELECT * FROM securities_financial 
            WHERE symbol = '{symbol}' 
            ORDER BY report_date DESC 
            LIMIT {periods}
        """).fetchdf()
    
    def get_valuation(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """获取估值数据"""
        return self.db.execute(f"""
            SELECT * FROM securities_valuation 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT {days}
        """).fetchdf()
    
    def get_northbound(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """获取北向资金数据"""
        return self.db.execute(f"""
            SELECT * FROM securities_northbound 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT {days}
        """).fetchdf()
    
    def get_margin_trading(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """获取融资融券数据"""
        return self.db.execute(f"""
            SELECT * FROM securities_margin_trading 
            WHERE symbol = '{symbol}' 
            ORDER BY date DESC 
            LIMIT {days}
        """).fetchdf()
    
    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()
