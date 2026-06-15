"""
统一记忆管理器 - 记忆系统的唯一入口

职责：
1. 管理三层记忆（短期/工作/长期）
2. 提供统一的读写接口
3. 协调 SQLite 和 DuckDB
4. 管理向量索引
5. 调用 LLM 进行推理

使用方式：
    from trend_scanner.memory import UnifiedMemoryManager
    
    config = {
        "sqlite_path": "data/memory.db",
        "duckdb_path": "data/analytics.duckdb",
        "llm": {"provider": "workbuddy"}
    }
    memory = UnifiedMemoryManager(config)
    
    # 存储经验
    memory.store_experience(experience)
    
    # 检索相似经验
    matches = memory.retrieve_experiences(context, top_k=5)
"""

import os
import json
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from .sqlite_store import SQLiteStore
from .duckdb_store import DuckDBStore
from .vector_store import VectorStore
from .llm_factory import LLMProviderFactory, LLMProvider
from .retriever import MultiPathRetriever, SimilarityCalculator


class UnifiedMemoryManager:
    """
    统一记忆管理器 - 记忆系统的唯一入口
    
    三层记忆架构：
    - 短期记忆（Session）：会话级，内存存储
    - 工作记忆（Working）：日级，SQLite 存储
    - 长期记忆（Persistent）：永久，SQLite + DuckDB 存储
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化记忆管理器
        
        Args:
            config: 配置字典，包含：
                - sqlite_path: SQLite 数据库路径
                - duckdb_path: DuckDB 数据库路径
                - vector_dim: 向量维度（默认 15）
                - max_experiences: 最大经验数量（默认 10000）
                - time_decay_half_life_days: 时间衰减半衰期（默认 90）
                - llm: LLM 配置
        """
        self.config = config
        
        # 确保数据目录存在
        sqlite_path = config.get('sqlite_path', 'data/memory.db')
        duckdb_path = config.get('duckdb_path', 'data/analytics.duckdb')
        
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        Path(duckdb_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化存储引擎
        self.sqlite_store = SQLiteStore(sqlite_path)
        self.duckdb_store = DuckDBStore(duckdb_path)
        
        # 初始化向量存储
        vector_dim = config.get('vector_dim', 15)
        self.vector_store = VectorStore(dim=vector_dim)
        
        # 初始化 LLM 提供者
        llm_config = config.get('llm', {'provider': 'workbuddy'})
        self.llm_provider = LLMProviderFactory.create(llm_config)
        
        # 短期记忆（内存）
        self.short_term: Dict[str, Any] = {}
        
        # 配置参数
        self.max_experiences = config.get('max_experiences', 10000)
        self.time_decay_half_life = config.get('time_decay_half_life_days', 90)
        
        # 初始化表结构
        self._init_tables()
    
    def _init_tables(self):
        """初始化数据库表结构"""
        self.sqlite_store.init_tables()
        self.duckdb_store.init_tables()
    
    # ========== 经验管理 ==========
    
    def store_experience(self, experience: Dict[str, Any]) -> str:
        """
        存储一条经验
        
        Args:
            experience: 经验数据字典，包含：
                - experience_id: 经验ID
                - timestamp: 时间戳
                - symbol: 品种代码
                - trend_phase: 趋势阶段
                - action_taken: 执行的动作
                - pnl_pct: 盈亏百分比
                - feature_vector: 特征向量
                - ...
        
        Returns:
            经验ID
        """
        experience_id = experience.get('experience_id', self._generate_id('EXP'))
        experience['experience_id'] = experience_id
        
        # 1. 存入 SQLite
        self.sqlite_store.insert_experience(experience)
        
        # 2. 更新向量索引
        feature_vector = experience.get('feature_vector', [])
        if feature_vector:
            self.vector_store.add(
                entity_type='experience',
                entity_id=experience_id,
                vector=feature_vector,
                metadata={'symbol': experience.get('symbol'), 'timestamp': experience.get('timestamp')}
            )
        
        # 3. 检查容量限制
        self._enforce_capacity_limit()
        
        return experience_id
    
    def retrieve_experiences(
        self,
        context: Dict[str, Any],
        top_k: int = 5,
        min_similarity: float = 0.5,
        time_decay: bool = True
    ) -> List[Dict[str, Any]]:
        """
        检索相似经验
        
        Args:
            context: 市场上下文，包含 feature_vector
            top_k: 返回数量
            min_similarity: 最小相似度
            time_decay: 是否应用时间衰减
        
        Returns:
            相似经验列表
        """
        feature_vector = context.get('feature_vector', [])
        if not feature_vector:
            return []
        
        # 1. 向量检索（粗筛）
        vector_matches = self.vector_store.search(
            query_vector=feature_vector,
            top_k=top_k * 3
        )
        
        # 2. 从 SQLite 获取完整经验数据
        results = []
        for match in vector_matches:
            if match['similarity'] < min_similarity:
                continue
            
            experience = self.sqlite_store.get_experience(match['entity_id'])
            if experience:
                experience['similarity'] = match['similarity']
                
                # 3. 应用时间衰减
                if time_decay:
                    decay = self._compute_time_decay(experience.get('timestamp', ''))
                    experience['adjusted_similarity'] = match['similarity'] * decay
                else:
                    experience['adjusted_similarity'] = match['similarity']
                
                results.append(experience)
        
        # 4. 排序返回
        results.sort(key=lambda x: x.get('adjusted_similarity', 0), reverse=True)
        return results[:top_k]
    
    def get_experience(self, experience_id: str) -> Optional[Dict[str, Any]]:
        """获取单条经验"""
        return self.sqlite_store.get_experience(experience_id)
    
    def get_recent_experiences(self, symbol: str = None, n: int = 10) -> List[Dict[str, Any]]:
        """获取最近的经验"""
        return self.sqlite_store.get_recent_experiences(symbol=symbol, limit=n)
    
    # ========== 规则管理 ==========
    
    def store_rule(self, rule: Dict[str, Any]) -> str:
        """存储一条策略规则"""
        rule_id = rule.get('rule_id', self._generate_id('R'))
        rule['rule_id'] = rule_id
        self.sqlite_store.insert_rule(rule)
        return rule_id
    
    def get_active_rules(self, rule_type: str = None) -> List[Dict[str, Any]]:
        """获取活跃规则"""
        return self.sqlite_store.get_active_rules(rule_type=rule_type)
    
    def update_rule_performance(self, rule_id: str, success: bool):
        """更新规则性能统计"""
        self.sqlite_store.update_rule_performance(rule_id, success)
    
    # ========== 交易日志 ==========
    
    def store_trade(self, trade: Dict[str, Any]) -> str:
        """存储一笔交易记录"""
        trade_id = trade.get('trade_id', self._generate_id('T'))
        trade['trade_id'] = trade_id
        self.sqlite_store.insert_trade(trade)
        
        # 同时存入 DuckDB 用于分析
        self.duckdb_store.insert_trade(trade)
        
        return trade_id
    
    def get_recent_trades(self, symbol: str = None, n: int = 20) -> List[Dict[str, Any]]:
        """获取最近的交易"""
        return self.sqlite_store.get_recent_trades(symbol=symbol, limit=n)
    
    # ========== 进化历史 ==========
    
    def record_evolution(self, evolution: Dict[str, Any]) -> str:
        """记录一次进化"""
        evolution_id = evolution.get('evolution_id', self._generate_id('EVO'))
        evolution['evolution_id'] = evolution_id
        self.sqlite_store.insert_evolution(evolution)
        return evolution_id
    
    def get_last_evolution(self) -> Optional[Dict[str, Any]]:
        """获取最近一次进化"""
        return self.sqlite_store.get_last_evolution()
    
    # ========== 模式库 ==========
    
    def store_pattern(self, pattern: Dict[str, Any]) -> str:
        """存储一个模式"""
        pattern_id = pattern.get('pattern_id', self._generate_id('P'))
        pattern['pattern_id'] = pattern_id
        self.sqlite_store.insert_pattern(pattern)
        return pattern_id
    
    def get_active_patterns(self, pattern_type: str = None) -> List[Dict[str, Any]]:
        """获取活跃模式"""
        return self.sqlite_store.get_active_patterns(pattern_type=pattern_type)
    
    # ========== 分析查询（DuckDB） ==========
    
    def analyze_performance(self, symbol: str = None, days: int = 30) -> Dict[str, Any]:
        """分析交易性能"""
        return self.duckdb_store.analyze_performance(symbol=symbol, days=days)
    
    def get_factor_performance(self) -> List[Dict[str, Any]]:
        """获取因子性能"""
        return self.duckdb_store.get_factor_performance()
    
    # ========== LLM 调用 ==========
    
    def llm_generate(self, prompt: str, **kwargs) -> str:
        """调用 LLM 生成文本"""
        result = self.llm_provider.generate(prompt, **kwargs)
        
        # 记录 LLM 调用
        self._log_llm_call('generate', prompt, result)
        
        return result
    
    def llm_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """调用 LLM 对话"""
        result = self.llm_provider.chat(messages, **kwargs)
        
        # 记录 LLM 调用
        self._log_llm_call('chat', str(messages), result)
        
        return result
    
    # ========== 短期记忆 ==========
    
    def set_short_term(self, key: str, value: Any):
        """设置短期记忆"""
        self.short_term[key] = value
    
    def get_short_term(self, key: str, default: Any = None) -> Any:
        """获取短期记忆"""
        return self.short_term.get(key, default)
    
    def clear_short_term(self):
        """清除短期记忆"""
        self.short_term.clear()
    
    # ========== 内部方法 ==========
    
    def _generate_id(self, prefix: str) -> str:
        """生成唯一ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        import uuid
        unique = uuid.uuid4().hex[:8]
        return f"{prefix}_{timestamp}_{unique}"
    
    def _compute_time_decay(self, timestamp_str: str) -> float:
        """计算时间衰减因子"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            days_ago = (datetime.now() - timestamp).days
            import math
            decay = math.pow(0.5, days_ago / self.time_decay_half_life)
            return decay
        except:
            return 1.0
    
    def _enforce_capacity_limit(self):
        """强制执行容量限制"""
        count = self.sqlite_store.count_experiences()
        if count > self.max_experiences:
            # 删除最旧的经验
            excess = count - self.max_experiences
            self.sqlite_store.delete_oldest_experiences(excess)
    
    def _log_llm_call(self, purpose: str, input_text: str, output_text: str):
        """记录 LLM 调用"""
        call = {
            'call_id': self._generate_id('LLM'),
            'timestamp': datetime.now().isoformat(),
            'provider': self.llm_provider.name,
            'model': self.llm_provider.model,
            'purpose': purpose,
            'input_summary': input_text[:200] if input_text else '',
            'output_summary': output_text[:200] if output_text else '',
            'success': True
        }
        self.sqlite_store.insert_llm_call(call)
    
    # ========== 生命周期 ==========
    
    def close(self):
        """关闭所有连接"""
        self.sqlite_store.close()
        self.duckdb_store.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
