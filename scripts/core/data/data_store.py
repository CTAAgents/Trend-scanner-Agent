"""
数据存储模块

提供数据持久化和配置管理功能：
- DataStore: 数据存储（SQLite 配置 + DuckDB 时序数据）
- ConfigManager: 品种配置管理器

存储策略：
- SQLite: 配置、交易记录、策略参数、进化历史（事务型数据）
- DuckDB: K线数据、技术指标、信号历史（分析型数据，列式存储更快）
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any

import pandas as pd


class DataStore:
    """
    数据存储：SQLite + DuckDB

    SQLite 存储：
    - 品种配置（symbol_config）
    - 交易记录（trades）
    - 策略参数（strategy_params）
    - 进化历史（evolution_history）

    DuckDB 存储：
    - K线数据（klines）
    - 技术指标（indicators）
    - 信号历史（signals）
    """

    def __init__(self, db_path: str = "trend_scanner.db"):
        """
        初始化数据存储

        参数:
            db_path: 数据库文件路径（SQLite）
        """
        self.db_path = db_path
        self.db_dir = os.path.dirname(db_path) or "."
        os.makedirs(self.db_dir, exist_ok=True)

        # SQLite 连接
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        # DuckDB 连接（可选）
        self.duckdb_conn = None
        try:
            import duckdb

            duckdb_path = db_path.replace(".db", ".duckdb")
            self.duckdb_conn = duckdb.connect(duckdb_path)
        except ImportError:
            pass  # DuckDB 不可用时回退到 SQLite

        # 初始化表结构
        self._init_tables()

    def _init_tables(self):
        """初始化数据库表结构"""
        cursor = self.conn.cursor()

        # 品种配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS symbol_config (
                symbol TEXT PRIMARY KEY,
                timeframe TEXT DEFAULT '1d',
                ma_periods TEXT DEFAULT '{"short": 20, "medium": 60, "long": 120}',
                strategy_weights TEXT,
                risk_params TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 交易记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_time TIMESTAMP,
                entry_price REAL,
                exit_time TIMESTAMP,
                exit_price REAL,
                pnl REAL,
                pnl_pct REAL,
                holding_bars INTEGER,
                market_state_at_entry TEXT,
                trend_phase_at_entry TEXT,
                adx_at_entry REAL,
                atr_at_entry REAL,
                composite_score_at_entry REAL,
                exit_reason TEXT,
                quality_tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 策略参数表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_params (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                param_name TEXT NOT NULL,
                param_value TEXT NOT NULL,
                source TEXT DEFAULT 'manual',
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, param_name, version)
            )
        """)

        # 进化历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evolution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                evolution_type TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                performance_before REAL,
                performance_after REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 信号历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                signal TEXT NOT NULL,
                strength TEXT,
                market_state TEXT,
                trend_phase TEXT,
                composite_score REAL,
                filtered_composite REAL,
                score_direction INTEGER,
                vote_direction INTEGER,
                dimension_scores TEXT,
                evidence TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 打分反馈表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scoring_feedback (
                feedback_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                composite_score REAL,
                filtered_composite REAL,
                score_direction INTEGER,
                confidence REAL,
                dimension_scores TEXT,
                market_state TEXT,
                trend_phase TEXT,
                volatility_regime TEXT,
                actual_direction INTEGER,
                actual_return REAL,
                holding_days INTEGER,
                outcome TEXT,
                direction_correct INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        self.conn.commit()

        # DuckDB 表
        if self.duckdb_conn:
            self._init_duckdb_tables()

    def _init_duckdb_tables(self):
        """初始化 DuckDB 表结构"""
        if not self.duckdb_conn:
            return

        # K线数据表
        self.duckdb_conn.execute("""
            CREATE TABLE IF NOT EXISTS klines (
                symbol VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                open_interest DOUBLE,
                PRIMARY KEY (symbol, timestamp)
            )
        """)

        # 技术指标表
        self.duckdb_conn.execute("""
            CREATE TABLE IF NOT EXISTS indicators (
                symbol VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                indicator_name VARCHAR NOT NULL,
                value DOUBLE,
                PRIMARY KEY (symbol, timestamp, indicator_name)
            )
        """)

    def save_klines(self, symbol: str, df: pd.DataFrame):
        """
        保存K线数据

        参数:
            symbol: 品种代码
            df: DataFrame，包含 date/open/high/low/close/volume 列
        """
        if self.duckdb_conn:
            # DuckDB 存储
            df_copy = df.copy()
            df_copy["symbol"] = symbol
            if "date" in df_copy.columns:
                df_copy["timestamp"] = pd.to_datetime(df_copy["date"])
            elif "datetime" in df_copy.columns:
                df_copy["timestamp"] = pd.to_datetime(df_copy["datetime"])

            # 只保留需要的列
            cols = ["symbol", "timestamp", "open", "high", "low", "close", "volume"]
            for col in cols:
                if col not in df_copy.columns:
                    df_copy[col] = None

            # 使用 INSERT OR REPLACE
            for _, row in df_copy[cols].iterrows():
                self.duckdb_conn.execute(
                    """
                    INSERT OR REPLACE INTO klines (symbol, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        row["symbol"],
                        row["timestamp"],
                        row["open"],
                        row["high"],
                        row["low"],
                        row["close"],
                        row["volume"],
                    ],
                )
        else:
            # 回退到 SQLite
            df_copy = df.copy()
            df_copy["symbol"] = symbol
            if "date" in df_copy.columns:
                df_copy["timestamp"] = df_copy["date"]
            elif "datetime" in df_copy.columns:
                df_copy["timestamp"] = df_copy["datetime"]

            cols = ["symbol", "timestamp", "open", "high", "low", "close", "volume"]
            for col in cols:
                if col not in df_copy.columns:
                    df_copy[col] = None

            df_copy[cols].to_sql("klines", self.conn, if_exists="append", index=False)

    def load_klines(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        加载K线数据

        参数:
            symbol: 品种代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        返回:
            DataFrame
        """
        if self.duckdb_conn:
            query = "SELECT * FROM klines WHERE symbol = ?"
            params = [symbol]
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)
            query += " ORDER BY timestamp"
            return self.duckdb_conn.execute(query, params).fetchdf()
        else:
            query = "SELECT * FROM klines WHERE symbol = ?"
            params = [symbol]
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)
            query += " ORDER BY timestamp"
            return pd.read_sql(query, self.conn, params=params)

    def save_signal(self, symbol: str, result: dict):
        """
        保存信号历史

        参数:
            symbol: 品种代码
            result: MultiIndicatorConsensus.consensus() 的结果
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO signal_history
            (symbol, timestamp, signal, strength, market_state, trend_phase,
             composite_score, filtered_composite, score_direction, vote_direction,
             dimension_scores, evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                symbol,
                datetime.now().isoformat(),
                result.get("signal", "HOLD"),
                result.get("strength", "none"),
                result.get("state", "UNKNOWN"),
                result.get("phase", "UNKNOWN"),
                result.get("composite_score", 0),
                result.get("filtered_composite", 0),
                result.get("score_direction", 0),
                result.get("direction", 0),
                json.dumps(result.get("dimension_scores", {}), ensure_ascii=False),
                json.dumps(result.get("evidence", []), ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def save_trade(self, trade: dict):
        """
        保存交易记录

        参数:
            trade: 交易记录字典
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO trades
            (trade_id, symbol, direction, entry_time, entry_price, exit_time, exit_price,
             pnl, pnl_pct, holding_bars, market_state_at_entry, trend_phase_at_entry,
             adx_at_entry, atr_at_entry, composite_score_at_entry, exit_reason, quality_tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                trade.get("trade_id", ""),
                trade.get("symbol", ""),
                trade.get("direction", ""),
                trade.get("entry_time", ""),
                trade.get("entry_price", 0),
                trade.get("exit_time", ""),
                trade.get("exit_price", 0),
                trade.get("pnl", 0),
                trade.get("pnl_pct", 0),
                trade.get("holding_bars", 0),
                trade.get("market_state_at_entry", ""),
                trade.get("trend_phase_at_entry", ""),
                trade.get("adx_at_entry", 0),
                trade.get("atr_at_entry", 0),
                trade.get("composite_score_at_entry", 0),
                trade.get("exit_reason", ""),
                json.dumps(trade.get("quality_tags", []), ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def get_symbol_config(self, symbol: str) -> dict | None:
        """
        获取品种配置

        参数:
            symbol: 品种代码

        返回:
            配置字典或 None
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM symbol_config WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        if row:
            return {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "ma_periods": json.loads(row["ma_periods"]) if row["ma_periods"] else {},
                "strategy_weights": json.loads(row["strategy_weights"]) if row["strategy_weights"] else {},
                "risk_params": json.loads(row["risk_params"]) if row["risk_params"] else {},
            }
        return None

    def save_symbol_config(self, symbol: str, config: dict):
        """
        保存品种配置

        参数:
            symbol: 品种代码
            config: 配置字典
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO symbol_config
            (symbol, timeframe, ma_periods, strategy_weights, risk_params, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                symbol,
                config.get("timeframe", "1d"),
                json.dumps(config.get("ma_periods", {})),
                json.dumps(config.get("strategy_weights", {})),
                json.dumps(config.get("risk_params", {})),
                datetime.now().isoformat(),
            ),
        )
        self.conn.commit()

    def get_trades(self, symbol: str = None, limit: int = 100) -> list[dict]:
        """
        获取交易记录

        参数:
            symbol: 品种代码（可选）
            limit: 返回数量限制

        返回:
            交易记录列表
        """
        cursor = self.conn.cursor()
        if symbol:
            cursor.execute("SELECT * FROM trades WHERE symbol = ? ORDER BY entry_time DESC LIMIT ?", (symbol, limit))
        else:
            cursor.execute("SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_signal_history(self, symbol: str, limit: int = 50) -> list[dict]:
        """
        获取信号历史

        参数:
            symbol: 品种代码
            limit: 返回数量限制

        返回:
            信号历史列表
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM signal_history
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (symbol, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def save_evolution(
        self,
        symbol: str,
        evolution_type: str,
        old_value: Any,
        new_value: Any,
        reason: str,
        performance_before: float = None,
        performance_after: float = None,
    ):
        """
        保存进化历史

        参数:
            symbol: 品种代码
            evolution_type: 进化类型（weight/param/rule）
            old_value: 旧值
            new_value: 新值
            reason: 原因
            performance_before: 进化前性能
            performance_after: 进化后性能
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO evolution_history
            (symbol, evolution_type, old_value, new_value, reason,
             performance_before, performance_after)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                symbol,
                evolution_type,
                json.dumps(old_value) if not isinstance(old_value, str) else old_value,
                json.dumps(new_value) if not isinstance(new_value, str) else new_value,
                reason,
                performance_before,
                performance_after,
            ),
        )
        self.conn.commit()

    # ---- 打分反馈相关方法 ----

    def save_scoring_feedback(self, feedback) -> bool:
        """
        保存打分反馈

        参数:
            feedback: ScoringFeedback 对象或字典

        返回:
            是否保存成功
        """
        try:
            cursor = self.conn.cursor()

            # 支持 ScoringFeedback 对象或字典
            if hasattr(feedback, "to_dict"):
                data = feedback.to_dict()
            else:
                data = feedback

            cursor.execute(
                """
                INSERT OR REPLACE INTO scoring_feedback
                (feedback_id, symbol, timestamp, composite_score, filtered_composite,
                 score_direction, confidence, dimension_scores, market_state,
                 trend_phase, volatility_regime, actual_direction, actual_return,
                 holding_days, outcome, direction_correct, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data.get("feedback_id"),
                    data.get("symbol"),
                    data.get("timestamp"),
                    data.get("composite_score", 0),
                    data.get("filtered_composite", 0),
                    data.get("score_direction", 0),
                    data.get("confidence", 0),
                    json.dumps(data.get("dimension_scores", {})),
                    data.get("market_state", ""),
                    data.get("trend_phase", ""),
                    data.get("volatility_regime", ""),
                    data.get("actual_direction", 0),
                    data.get("actual_return", 0),
                    data.get("holding_days", 0),
                    data.get("outcome", ""),
                    1 if data.get("direction_correct") else 0,
                    data.get("status", "pending"),
                    data.get("created_at", datetime.now().isoformat()),
                    data.get("updated_at"),
                ),
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"保存打分反馈失败: {e}")
            return False

    def get_scoring_feedback(
        self, symbol: str = None, status: str = None, start_date: str = None, end_date: str = None, limit: int = 1000
    ) -> list[dict]:
        """
        获取打分反馈

        参数:
            symbol: 品种代码（可选）
            status: 状态过滤（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 返回数量限制

        返回:
            打分反馈列表
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM scoring_feedback WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if status:
            query += " AND status = ?"
            params.append(status)

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]

        # 解析 JSON 字段
        for row in results:
            if row.get("dimension_scores"):
                try:
                    row["dimension_scores"] = json.loads(row["dimension_scores"])
                except:
                    row["dimension_scores"] = {}

        return results

    def update_scoring_feedback_result(
        self, feedback_id: str, actual_direction: int, actual_return: float, holding_days: int, outcome: str
    ) -> bool:
        """
        更新打分反馈的实际结果

        参数:
            feedback_id: 反馈ID
            actual_direction: 实际方向（1/-1/0）
            actual_return: 实际收益
            holding_days: 持仓天数
            outcome: 结果（WIN/LOSS/BREAKEVEN）

        返回:
            是否更新成功
        """
        try:
            cursor = self.conn.cursor()

            # 获取原始打分方向
            cursor.execute("SELECT score_direction FROM scoring_feedback WHERE feedback_id = ?", (feedback_id,))
            row = cursor.fetchone()
            if not row:
                return False

            score_direction = row[0]
            direction_correct = score_direction == actual_direction

            cursor.execute(
                """
                UPDATE scoring_feedback
                SET actual_direction = ?, actual_return = ?, holding_days = ?,
                    outcome = ?, direction_correct = ?, status = 'completed',
                    updated_at = ?
                WHERE feedback_id = ?
            """,
                (
                    actual_direction,
                    actual_return,
                    holding_days,
                    outcome,
                    1 if direction_correct else 0,
                    datetime.now().isoformat(),
                    feedback_id,
                ),
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"更新打分反馈失败: {e}")
            return False

    def get_scoring_statistics(self, symbol: str = None) -> dict:
        """
        获取打分统计信息

        参数:
            symbol: 品种代码（可选）

        返回:
            统计信息字典
        """
        cursor = self.conn.cursor()

        query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN direction_correct = 1 THEN 1 ELSE 0 END) as correct,
                AVG(CASE WHEN status = 'completed' THEN actual_return ELSE NULL END) as avg_return,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses
            FROM scoring_feedback
            WHERE 1=1
        """
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        cursor.execute(query, params)
        row = cursor.fetchone()

        if not row:
            return {}

        total = row[0] or 0
        completed = row[1] or 0
        correct = row[2] or 0
        avg_return = row[3] or 0
        wins = row[4] or 0
        losses = row[5] or 0

        return {
            "total_feedbacks": total,
            "completed_feedbacks": completed,
            "direction_accuracy": correct / completed if completed > 0 else 0,
            "average_return": avg_return,
            "win_rate": wins / completed if completed > 0 else 0,
            "loss_rate": losses / completed if completed > 0 else 0,
        }

    def close(self):
        """关闭数据库连接"""
        self.conn.close()
        if self.duckdb_conn:
            self.duckdb_conn.close()


class ConfigManager:
    """
    品种配置管理器

    管理不同品种的参数配置，支持：
    - 默认配置
    - 品种特定配置
    - 配置版本管理
    """

    def __init__(self, data_store: DataStore):
        """
        初始化配置管理器

        参数:
            data_store: DataStore 实例
        """
        self.store = data_store

    def get_config(self, symbol: str) -> dict:
        """
        获取品种配置（合并默认配置和品种特定配置）

        参数:
            symbol: 品种代码

        返回:
            合并后的配置字典
        """
        # 默认配置
        default_config = {
            "timeframe": "1d",
            "ma_periods": {"short": 20, "medium": 60, "long": 120},
            "strategy_weights": {},
            "risk_params": {
                "risk_per_trade": 0.01,
                "point_value": 10.0,
                "margin_per_lot": 5000.0,
            },
        }

        # 获取品种特定配置
        symbol_config = self.store.get_symbol_config(symbol)
        if symbol_config:
            # 合并配置
            for key in ["ma_periods", "strategy_weights", "risk_params"]:
                if symbol_config.get(key):
                    default_config[key].update(symbol_config[key])
            if symbol_config.get("timeframe"):
                default_config["timeframe"] = symbol_config["timeframe"]

        return default_config

    def set_config(self, symbol: str, config: dict):
        """
        设置品种配置

        参数:
            symbol: 品种代码
            config: 配置字典
        """
        self.store.save_symbol_config(symbol, config)

    def list_symbols(self) -> list[str]:
        """
        列出所有已配置的品种

        返回:
            品种代码列表
        """
        cursor = self.store.conn.cursor()
        cursor.execute("SELECT symbol FROM symbol_config ORDER BY symbol")
        return [row["symbol"] for row in cursor.fetchall()]

    def delete_config(self, symbol: str):
        """
        删除品种配置

        参数:
            symbol: 品种代码
        """
        cursor = self.store.conn.cursor()
        cursor.execute("DELETE FROM symbol_config WHERE symbol = ?", (symbol,))
        self.store.conn.commit()
