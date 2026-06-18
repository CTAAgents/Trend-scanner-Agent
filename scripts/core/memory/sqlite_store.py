"""
SQLite 事务型存储

职责：
- 存储经验、规则、交易日志、进化历史、模式库
- 提供 CRUD 操作
- 确保数据一致性

表结构：
- experiences: 经验表
- strategy_rules: 策略规则表
- trade_journal: 交易日志表
- evolution_history: 进化历史表
- pattern_library: 模式库表
- llm_calls: LLM 调用记录表
- system_config: 配置表
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class SQLiteStore:
    """SQLite 事务型存储"""

    def __init__(self, db_path: str):
        """
        初始化 SQLite 存储

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path

        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 连接数据库
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        # 启用 WAL 模式（提高并发性能）
        self.conn.execute("PRAGMA journal_mode=WAL")

    def init_tables(self):
        """初始化表结构"""
        cursor = self.conn.cursor()

        # 0. 符号表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS symbols (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            exchange TEXT,
            product_type TEXT,
            volume_multiple REAL,
            price_tick REAL,
            margin_ratio REAL,
            trading_unit TEXT,
            delivery_month TEXT,
            listed_date TEXT,
            delisted_date TEXT,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # 1. 经验表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiences (
            experience_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            symbol TEXT,
            direction TEXT,
            trend_phase TEXT,
            phase_confidence REAL,
            market_regime TEXT,
            action_taken TEXT,
            action_reasoning TEXT,
            entry_price REAL,
            exit_price REAL,
            pnl_pct REAL,
            holding_days INTEGER,
            max_drawdown_pct REAL,
            risk_adjusted_return REAL,
            feature_vector TEXT,
            context_snapshot TEXT,
            full_data TEXT,
            source TEXT DEFAULT 'manual',
            confidence REAL DEFAULT 0.5,
            importance REAL DEFAULT 0.5,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # 2. 策略规则表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_rules (
            rule_id TEXT PRIMARY KEY,
            rule_name TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            rule_content TEXT NOT NULL,
            applicable_phases TEXT,
            applicable_symbols TEXT,
            trigger_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0,
            avg_pnl REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active',
            confidence REAL DEFAULT 0.5,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            last_triggered_at TEXT
        )
        """)

        # 3. 交易日志表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_journal (
            trade_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            exit_price REAL,
            pnl_pct REAL,
            holding_days INTEGER,
            brief_at_entry TEXT,
            brief_at_exit TEXT,
            user_decision TEXT,
            user_notes TEXT,
            fault_type TEXT,
            fault_severity REAL,
            fault_detail TEXT,
            lessons_learned TEXT,
            patterns_detected TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # 4. 进化历史表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS evolution_history (
            evolution_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            trigger_reason TEXT,
            change_type TEXT,
            target_id TEXT,
            old_value TEXT,
            new_value TEXT,
            expected_improvement REAL,
            actual_improvement REAL,
            validation_status TEXT DEFAULT 'pending',
            audit_score REAL,
            audit_detail TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            validated_at TEXT
        )
        """)

        # 5. 模式库表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pattern_library (
            pattern_id TEXT PRIMARY KEY,
            pattern_name TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            conditions TEXT,
            feature_signature TEXT,
            occurrences INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0,
            avg_pnl REAL DEFAULT 0.0,
            avg_holding_days REAL DEFAULT 0.0,
            associated_rules TEXT,
            status TEXT DEFAULT 'active',
            confidence REAL DEFAULT 0.5,
            created_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT
        )
        """)

        # 6. LLM 调用记录表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_calls (
            call_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            purpose TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            input_summary TEXT,
            output_summary TEXT,
            latency_ms INTEGER,
            success BOOLEAN,
            error_message TEXT,
            cost_usd REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # 7. 配置表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            config_key TEXT PRIMARY KEY,
            config_value TEXT NOT NULL,
            config_type TEXT DEFAULT 'json',
            description TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_experiences_symbol ON experiences(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_experiences_timestamp ON experiences(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_type ON strategy_rules(rule_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_status ON strategy_rules(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_symbol ON trade_journal(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_timestamp ON trade_journal(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evolution_timestamp ON evolution_history(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON pattern_library(pattern_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_llm_calls_timestamp ON llm_calls(timestamp)")

        self.conn.commit()

    # ========== 经验操作 ==========

    def insert_experience(self, experience: dict[str, Any]) -> str:
        """插入一条经验"""
        cursor = self.conn.cursor()

        # 序列化复杂字段
        feature_vector = json.dumps(experience.get("feature_vector", []))
        context_snapshot = json.dumps(experience.get("context_snapshot", {}))
        full_data = json.dumps(experience.get("full_data", {}))

        cursor.execute(
            """
        INSERT OR REPLACE INTO experiences (
            experience_id, timestamp, symbol, direction, trend_phase,
            phase_confidence, market_regime, action_taken, action_reasoning,
            entry_price, exit_price, pnl_pct, holding_days,
            max_drawdown_pct, risk_adjusted_return,
            feature_vector, context_snapshot, full_data,
            source, confidence, importance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                experience.get("experience_id"),
                experience.get("timestamp", datetime.now().isoformat()),
                experience.get("symbol"),
                experience.get("direction"),
                experience.get("trend_phase"),
                experience.get("phase_confidence"),
                experience.get("market_regime"),
                experience.get("action_taken"),
                experience.get("action_reasoning"),
                experience.get("entry_price"),
                experience.get("exit_price"),
                experience.get("pnl_pct"),
                experience.get("holding_days"),
                experience.get("max_drawdown_pct"),
                experience.get("risk_adjusted_return"),
                feature_vector,
                context_snapshot,
                full_data,
                experience.get("source", "manual"),
                experience.get("confidence", 0.5),
                experience.get("importance", 0.5),
            ),
        )

        self.conn.commit()
        return experience.get("experience_id")

    def get_experience(self, experience_id: str) -> dict[str, Any] | None:
        """获取单条经验"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM experiences WHERE experience_id = ?", (experience_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_dict(row)
        return None

    def get_recent_experiences(self, symbol: str = None, limit: int = 10) -> list[dict[str, Any]]:
        """获取最近的经验"""
        cursor = self.conn.cursor()

        if symbol:
            cursor.execute(
                "SELECT * FROM experiences WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?", (symbol, limit)
            )
        else:
            cursor.execute("SELECT * FROM experiences ORDER BY timestamp DESC LIMIT ?", (limit,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def count_experiences(self) -> int:
        """统计经验数量"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM experiences")
        return cursor.fetchone()[0]

    def delete_oldest_experiences(self, count: int):
        """删除最旧的经验"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
        DELETE FROM experiences WHERE experience_id IN (
            SELECT experience_id FROM experiences ORDER BY timestamp ASC LIMIT ?
        )
        """,
            (count,),
        )
        self.conn.commit()

    # ========== 规则操作 ==========

    def insert_rule(self, rule: dict[str, Any]) -> str:
        """插入一条规则"""
        cursor = self.conn.cursor()

        applicable_phases = json.dumps(rule.get("applicable_phases", []))
        applicable_symbols = json.dumps(rule.get("applicable_symbols", []))

        cursor.execute(
            """
        INSERT OR REPLACE INTO strategy_rules (
            rule_id, rule_name, rule_type, rule_content,
            applicable_phases, applicable_symbols,
            trigger_count, success_count, failure_count,
            win_rate, avg_pnl, status, confidence, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                rule.get("rule_id"),
                rule.get("rule_name"),
                rule.get("rule_type"),
                rule.get("rule_content"),
                applicable_phases,
                applicable_symbols,
                rule.get("trigger_count", 0),
                rule.get("success_count", 0),
                rule.get("failure_count", 0),
                rule.get("win_rate", 0.0),
                rule.get("avg_pnl", 0.0),
                rule.get("status", "active"),
                rule.get("confidence", 0.5),
                rule.get("source", "manual"),
            ),
        )

        self.conn.commit()
        return rule.get("rule_id")

    def get_active_rules(self, rule_type: str = None) -> list[dict[str, Any]]:
        """获取活跃规则"""
        cursor = self.conn.cursor()

        if rule_type:
            cursor.execute("SELECT * FROM strategy_rules WHERE status = 'active' AND rule_type = ?", (rule_type,))
        else:
            cursor.execute("SELECT * FROM strategy_rules WHERE status = 'active'")

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def update_rule_performance(self, rule_id: str, success: bool):
        """更新规则性能统计"""
        cursor = self.conn.cursor()

        if success:
            cursor.execute(
                """
            UPDATE strategy_rules SET
                trigger_count = trigger_count + 1,
                success_count = success_count + 1,
                win_rate = CAST(success_count + 1 AS REAL) / (trigger_count + 1),
                last_triggered_at = ?
            WHERE rule_id = ?
            """,
                (datetime.now().isoformat(), rule_id),
            )
        else:
            cursor.execute(
                """
            UPDATE strategy_rules SET
                trigger_count = trigger_count + 1,
                failure_count = failure_count + 1,
                win_rate = CAST(success_count AS REAL) / (trigger_count + 1),
                last_triggered_at = ?
            WHERE rule_id = ?
            """,
                (datetime.now().isoformat(), rule_id),
            )

        self.conn.commit()

    # ========== 交易日志操作 ==========

    def insert_trade(self, trade: dict[str, Any]) -> str:
        """插入一笔交易"""
        cursor = self.conn.cursor()

        brief_at_entry = json.dumps(trade.get("brief_at_entry", {}))
        brief_at_exit = json.dumps(trade.get("brief_at_exit", {}))
        lessons_learned = json.dumps(trade.get("lessons_learned", []))
        patterns_detected = json.dumps(trade.get("patterns_detected", []))

        cursor.execute(
            """
        INSERT OR REPLACE INTO trade_journal (
            trade_id, timestamp, symbol, direction,
            entry_price, exit_price, pnl_pct, holding_days,
            brief_at_entry, brief_at_exit, user_decision, user_notes,
            fault_type, fault_severity, fault_detail,
            lessons_learned, patterns_detected
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                trade.get("trade_id"),
                trade.get("timestamp", datetime.now().isoformat()),
                trade.get("symbol"),
                trade.get("direction"),
                trade.get("entry_price"),
                trade.get("exit_price"),
                trade.get("pnl_pct"),
                trade.get("holding_days"),
                brief_at_entry,
                brief_at_exit,
                trade.get("user_decision"),
                trade.get("user_notes"),
                trade.get("fault_type"),
                trade.get("fault_severity"),
                trade.get("fault_detail"),
                lessons_learned,
                patterns_detected,
            ),
        )

        self.conn.commit()
        return trade.get("trade_id")

    def get_recent_trades(self, symbol: str = None, limit: int = 20) -> list[dict[str, Any]]:
        """获取最近的交易"""
        cursor = self.conn.cursor()

        if symbol:
            cursor.execute(
                "SELECT * FROM trade_journal WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?", (symbol, limit)
            )
        else:
            cursor.execute("SELECT * FROM trade_journal ORDER BY timestamp DESC LIMIT ?", (limit,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    # ========== 进化历史操作 ==========

    def insert_evolution(self, evolution: dict[str, Any]) -> str:
        """插入一次进化记录"""
        cursor = self.conn.cursor()

        cursor.execute(
            """
        INSERT INTO evolution_history (
            evolution_id, timestamp, trigger_reason,
            change_type, target_id, old_value, new_value,
            expected_improvement, actual_improvement,
            validation_status, audit_score, audit_detail
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                evolution.get("evolution_id"),
                evolution.get("timestamp", datetime.now().isoformat()),
                evolution.get("trigger_reason"),
                evolution.get("change_type"),
                evolution.get("target_id"),
                evolution.get("old_value"),
                evolution.get("new_value"),
                evolution.get("expected_improvement"),
                evolution.get("actual_improvement"),
                evolution.get("validation_status", "pending"),
                evolution.get("audit_score"),
                evolution.get("audit_detail"),
            ),
        )

        self.conn.commit()
        return evolution.get("evolution_id")

    def get_last_evolution(self) -> dict[str, Any] | None:
        """获取最近一次进化"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM evolution_history ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()

        if row:
            return self._row_to_dict(row)
        return None

    # ========== 模式库操作 ==========

    def insert_pattern(self, pattern: dict[str, Any]) -> str:
        """插入一个模式"""
        cursor = self.conn.cursor()

        conditions = json.dumps(pattern.get("conditions", {}))
        associated_rules = json.dumps(pattern.get("associated_rules", []))

        cursor.execute(
            """
        INSERT OR REPLACE INTO pattern_library (
            pattern_id, pattern_name, pattern_type,
            conditions, feature_signature,
            occurrences, win_rate, avg_pnl, avg_holding_days,
            associated_rules, status, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                pattern.get("pattern_id"),
                pattern.get("pattern_name"),
                pattern.get("pattern_type"),
                conditions,
                pattern.get("feature_signature"),
                pattern.get("occurrences", 0),
                pattern.get("win_rate", 0.0),
                pattern.get("avg_pnl", 0.0),
                pattern.get("avg_holding_days", 0.0),
                associated_rules,
                pattern.get("status", "active"),
                pattern.get("confidence", 0.5),
            ),
        )

        self.conn.commit()
        return pattern.get("pattern_id")

    def get_active_patterns(self, pattern_type: str = None) -> list[dict[str, Any]]:
        """获取活跃模式"""
        cursor = self.conn.cursor()

        if pattern_type:
            cursor.execute(
                "SELECT * FROM pattern_library WHERE status = 'active' AND pattern_type = ?", (pattern_type,)
            )
        else:
            cursor.execute("SELECT * FROM pattern_library WHERE status = 'active'")

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    # ========== LLM 调用记录操作 ==========

    def insert_llm_call(self, call: dict[str, Any]) -> str:
        """插入一条 LLM 调用记录"""
        cursor = self.conn.cursor()

        cursor.execute(
            """
        INSERT INTO llm_calls (
            call_id, timestamp, provider, model, purpose,
            input_tokens, output_tokens, input_summary, output_summary,
            latency_ms, success, error_message, cost_usd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                call.get("call_id"),
                call.get("timestamp", datetime.now().isoformat()),
                call.get("provider"),
                call.get("model"),
                call.get("purpose"),
                call.get("input_tokens"),
                call.get("output_tokens"),
                call.get("input_summary"),
                call.get("output_summary"),
                call.get("latency_ms"),
                call.get("success", True),
                call.get("error_message"),
                call.get("cost_usd"),
            ),
        )

        self.conn.commit()
        return call.get("call_id")

    # ========== 配置操作 ==========

    def set_config(self, key: str, value: Any, description: str = None):
        """设置配置"""
        cursor = self.conn.cursor()

        value_str = json.dumps(value) if not isinstance(value, str) else value
        config_type = "json" if not isinstance(value, str) else "string"

        cursor.execute(
            """
        INSERT OR REPLACE INTO system_config (config_key, config_value, config_type, description)
        VALUES (?, ?, ?, ?)
        """,
            (key, value_str, config_type, description),
        )

        self.conn.commit()

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT config_value, config_type FROM system_config WHERE config_key = ?", (key,))
        row = cursor.fetchone()

        if row:
            if row[1] == "json":
                return json.loads(row[0])
            return row[0]
        return default

    # ========== 内部方法 ==========

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """将 Row 转换为字典"""
        result = dict(row)

        # 反序列化 JSON 字段
        json_fields = [
            "feature_vector",
            "context_snapshot",
            "full_data",
            "applicable_phases",
            "applicable_symbols",
            "brief_at_entry",
            "brief_at_exit",
            "lessons_learned",
            "patterns_detected",
            "conditions",
            "associated_rules",
        ]

        for field in json_fields:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except:
                    pass

        return result

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
