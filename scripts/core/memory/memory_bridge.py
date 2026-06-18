"""
记忆系统集成桥接器

提供记忆系统与 Scanner/Reasoner/Evolver 的高层集成接口。

职责：
- Scanner 集成：存储扫描结果、指标历史
- Reasoner 集成：检索相似经验、存储推理结果
- Evolver 集成：检索交易历史、存储进化结果

使用方式：
    from trend_scanner.memory_bridge import MemoryBridge

    bridge = MemoryBridge(config)

    # Scanner 集成
    bridge.store_scan_result(scan_result)

    # Reasoner 集成
    experiences = bridge.retrieve_similar_experiences(symbol, market_context)

    # Evolver 集成
    trade_history = bridge.get_trade_history(symbol)
"""

import json
import logging
from datetime import datetime
from typing import Any

from .memory import UnifiedMemoryManager


logger = logging.getLogger(__name__)


class MemoryBridge:
    """
    记忆系统集成桥接器

    提供 Scanner/Reasoner/Evolver 与记忆系统的高层集成接口。
    """

    def __init__(self, config: dict[str, Any] = None):
        """
        初始化记忆桥接器

        Args:
            config: 配置字典，包含：
                - sqlite_path: SQLite 数据库路径（默认 data/memory.db）
                - duckdb_path: DuckDB 数据库路径（默认 data/market.duckdb）
                - llm: LLM 配置
        """
        if config is None:
            config = {}

        # 默认配置
        config.setdefault("sqlite_path", "data/memory.db")
        config.setdefault("duckdb_path", "data/market.duckdb")
        config.setdefault("llm", {"provider": "workbuddy"})

        # 初始化记忆管理器
        self.memory = UnifiedMemoryManager(config)

        logger.info("MemoryBridge 初始化完成")

    # ========== Scanner 集成 ==========

    def store_scan_result(self, scan_result: dict[str, Any]) -> None:
        """
        存储扫描结果

        Args:
            scan_result: 扫描结果字典，包含：
                - scan_time: 扫描时间
                - total_scanned: 扫描品种数
                - signals: 信号列表
                - no_signal_symbols: 无信号品种列表
        """
        scan_time = scan_result.get("scan_time", datetime.now().isoformat())
        signals = scan_result.get("signals", [])

        for signal in signals:
            # 存储为经验
            experience = {
                "experience_id": f"SCAN_{scan_time}_{signal.get('symbol', 'unknown')}",
                "timestamp": scan_time,
                "symbol": signal.get("symbol", ""),
                "trend_phase": signal.get("trend_phase", "UNKNOWN"),
                "direction": signal.get("direction", "NEUTRAL"),
                "signal_strength": signal.get("signal_strength", "WEAK"),
                "er": signal.get("er", 0),
                "tsi": signal.get("tsi", 0),
                "r_squared": signal.get("r_squared", 0),
                "trend_strength": signal.get("trend_strength_composite", 0),
                "trigger_reason": signal.get("trigger_reason", ""),
                "experience_type": "scan_result",
                "feature_vector": self._extract_feature_vector(signal),
            }
            self.memory.store_experience(experience)

        # 存储到短期记忆
        self.memory.short_term["last_scan"] = scan_result

        logger.info(f"存储扫描结果：{len(signals)} 个信号")

    def store_indicators(self, symbol: str, indicators: dict[str, Any], timestamp: str = None) -> None:
        """
        存储技术指标

        Args:
            symbol: 品种代码
            indicators: 指标字典
            timestamp: 时间戳
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        # 存储到 DuckDB
        indicator_records = []
        for name, value in indicators.items():
            if isinstance(value, (int, float)):
                indicator_records.append(
                    {"symbol": symbol, "timestamp": timestamp, "indicator_name": name, "value": float(value)}
                )

        if indicator_records:
            self.memory.duckdb_store.insert_indicators(indicator_records)
            logger.debug(f"存储 {symbol} 的 {len(indicator_records)} 个指标")

    # ========== Reasoner 集成 ==========

    def retrieve_similar_experiences(
        self, symbol: str, market_context: dict[str, Any], top_k: int = 5
    ) -> list[dict[str, Any]]:
        """
        检索相似经验（供 Reasoner 使用）

        Args:
            symbol: 品种代码
            market_context: 市场上下文，包含 feature_vector
            top_k: 返回数量

        Returns:
            相似经验列表
        """
        # 构建查询上下文
        query = {
            "symbol": symbol,
            "feature_vector": market_context.get("feature_vector", []),
            "timestamp": market_context.get("timestamp", datetime.now().isoformat()),
        }

        # 多路召回检索
        experiences = self.memory.retrieve_experiences_multi_path(context=query, top_k=top_k, min_similarity=0.3)

        logger.info(f"检索到 {len(experiences)} 条相似经验（{symbol}）")
        return experiences

    def retrieve_active_rules(self, rule_type: str = None) -> list[dict[str, Any]]:
        """
        获取活跃规则（供 Reasoner 使用）

        Args:
            rule_type: 规则类型（可选）

        Returns:
            活跃规则列表
        """
        return self.memory.get_active_rules(rule_type=rule_type)

    def store_reasoning_result(self, reasoning_result: dict[str, Any]) -> str:
        """
        存储推理结果

        Args:
            reasoning_result: 推理结果字典，包含：
                - symbol: 品种代码
                - direction: 方向
                - confidence: 置信度
                - reasoning: 推理过程
                - market_assessment: 市场评估

        Returns:
            经验 ID
        """
        experience = {
            "timestamp": datetime.now().isoformat(),
            "symbol": reasoning_result.get("symbol", ""),
            "direction": reasoning_result.get("direction", "NEUTRAL"),
            "confidence": reasoning_result.get("confidence", 0),
            "reasoning": reasoning_result.get("reasoning", ""),
            "market_assessment": json.dumps(reasoning_result.get("market_assessment", {}), ensure_ascii=False),
            "experience_type": "reasoning_result",
            "feature_vector": reasoning_result.get("feature_vector", []),
        }

        experience_id = self.memory.store_experience(experience)
        logger.info(f"存储推理结果：{experience_id}")

        return experience_id

    # ========== Evolver 集成 ==========

    def get_trade_history(self, symbol: str = None, n: int = 50) -> list[dict[str, Any]]:
        """
        获取交易历史（供 Evolver 使用）

        Args:
            symbol: 品种代码（可选）
            n: 返回数量

        Returns:
            交易历史列表
        """
        return self.memory.get_recent_trades(symbol=symbol, n=n)

    def get_evolution_history(self) -> list[dict[str, Any]]:
        """
        获取进化历史（供 Evolver 使用）

        Returns:
            进化历史列表
        """
        return self.memory.sqlite_store.get_evolution_history()

    def store_trade(self, trade: dict[str, Any]) -> str:
        """
        存储交易记录

        Args:
            trade: 交易记录字典，包含：
                - symbol: 品种代码
                - direction: 方向
                - entry_price: 入场价
                - exit_price: 出场价
                - pnl: 盈亏
                - pnl_pct: 盈亏百分比

        Returns:
            交易 ID
        """
        trade["timestamp"] = trade.get("timestamp", datetime.now().isoformat())
        trade_id = self.memory.store_trade(trade)

        logger.info(f"存储交易记录：{trade_id}")
        return trade_id

    def store_evolution_result(self, evolution_result: dict[str, Any]) -> str:
        """
        存储进化结果

        Args:
            evolution_result: 进化结果字典，包含：
                - trigger_reason: 触发原因
                - analysis: 分析结果
                - new_rules: 新生成的规则
                - performance_change: 性能变化

        Returns:
            进化 ID
        """
        evolution_result["timestamp"] = evolution_result.get("timestamp", datetime.now().isoformat())
        evolution_id = self.memory.record_evolution(evolution_result)

        # 如果有新规则，存储到规则库
        new_rules = evolution_result.get("new_rules", [])
        for rule in new_rules:
            self.memory.store_rule(rule)

        logger.info(f"存储进化结果：{evolution_id}，{len(new_rules)} 条新规则")
        return evolution_id

    def check_evolution_trigger(self) -> tuple[bool, str]:
        """
        检查是否应该触发进化

        Returns:
            (是否触发, 触发原因)
        """
        from .memory.evolution import EvolutionTrigger

        trigger = EvolutionTrigger(self.memory)
        return trigger.should_evolve()

    # ========== 因子进化集成（v6.0 新增） ==========

    def store_factor_result(self, factor_result: dict[str, Any]) -> str:
        """
        存储因子结果（供 FactorEvolutionEngine 使用）

        Args:
            factor_result: 因子结果字典

        Returns:
            因子ID
        """
        return self.memory.store_factor_result(factor_result)

    def get_factor_history(self, factor_name: str = None) -> list[dict[str, Any]]:
        """
        获取因子历史

        Args:
            factor_name: 因子名称（可选）

        Returns:
            因子历史列表
        """
        return self.memory.get_factor_history(factor_name)

    def store_walk_forward_result(self, wf_result: dict[str, Any]) -> str:
        """
        存储 Walk-Forward 验证结果

        Args:
            wf_result: Walk-Forward 结果字典

        Returns:
            结果ID
        """
        return self.memory.store_walk_forward_result(wf_result)

    def store_visibility_graph_factor(self, factor_info: dict[str, Any]) -> str:
        """
        存储可见图因子信息

        Args:
            factor_info: 因子信息字典

        Returns:
            因子ID
        """
        return self.memory.store_visibility_graph_factor(factor_info)

    def store_volatility_anchor(self, anchor_info: dict[str, Any]) -> str:
        """
        存储波动率锚点信息

        Args:
            anchor_info: 锚点信息字典

        Returns:
            锚点ID
        """
        return self.memory.store_volatility_anchor(anchor_info)

    def get_volatility_anchor(self, symbol: str) -> dict[str, Any] | None:
        """
        获取波动率锚点

        Args:
            symbol: 品种代码

        Returns:
            锚点信息
        """
        return self.memory.get_volatility_anchor(symbol)

    # ========== 工具方法 ==========

    def _extract_feature_vector(self, signal: dict[str, Any]) -> list[float]:
        """
        从信号中提取特征向量

        Args:
            signal: 信号字典

        Returns:
            15 维特征向量
        """
        return [
            signal.get("er", 0),
            signal.get("tsi", 0) / 100,  # 归一化
            signal.get("r_squared", 0),
            signal.get("trend_strength_composite", 0),
            signal.get("hurst", 0.5),
            signal.get("rsi", 50) / 100,  # 归一化
            signal.get("adx", 0) / 100,  # 归一化
            1 if signal.get("direction") == "LONG" else (-1 if signal.get("direction") == "SHORT" else 0),
            {"WEAK": 0, "MEDIUM": 0.5, "STRONG": 1}.get(signal.get("signal_strength", "WEAK"), 0),
            0,  # 预留
            0,  # 预留
            0,  # 预留
            0,  # 预留
            0,  # 预留
            0,  # 预留
        ]

    def get_memory_stats(self) -> dict[str, Any]:
        """
        获取记忆系统统计信息

        Returns:
            统计信息字典
        """
        return {
            "experience_count": self.memory.sqlite_store.get_experience_count(),
            "rule_count": self.memory.sqlite_store.get_rule_count(),
            "trade_count": self.memory.sqlite_store.get_trade_count(),
            "evolution_count": self.memory.sqlite_store.get_evolution_count(),
            "short_term_keys": list(self.memory.short_term.keys()),
        }

    def close(self):
        """关闭记忆系统"""
        self.memory.close()
        logger.info("MemoryBridge 已关闭")
