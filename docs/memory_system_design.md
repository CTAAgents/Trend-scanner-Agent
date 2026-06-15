# 自优化趋势跟踪 Agent 记忆系统终版设计方案

> 版本：v1.0 | 创建日期：2026-06-15
> 技术栈：SQLite + DuckDB + 可配置 LLM

---

## 一、设计目标

### 1.1 核心目标

构建一个**自优化**的记忆系统，让趋势跟踪 Agent 能够：
- **记住**：存储交易经验、市场模式、策略规则
- **回忆**：快速检索相似场景的历史经验
- **学习**：从成功和失败中提炼规律
- **进化**：自动优化策略参数和规则

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **存储统一** | SQLite 管事务，DuckDB 管分析，分工明确 |
| **检索高效** | 向量检索 + 结构化查询，毫秒级响应 |
| **LLM 可配** | 支持 OpenAI/Anthropic/本地模型，一键切换 |
| **自优化** | 经验→模式→规则→参数，自动进化闭环 |
| **可观测** | 每条记忆可追溯，每次进化可审计 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          自优化记忆系统架构                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │   用户反馈    │
                              └──────┬───────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              Agent 层                                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Scanner    │  │  Reasoner   │  │  Debater    │  │  Evolver    │             │
│  │  脚本       │  │  Agent      │  │  Agent      │  │  Agent      │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
└─────────┼───────────────┼───────────────┼───────────────┼────────────────────────┘
          │               │               │               │
          ▼               ▼               ▼               ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            记忆系统核心层                                         │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                        UnifiedMemoryManager                                │ │
│  │                    （统一记忆管理器 - 唯一入口）                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│          │                    │                    │                             │
│          ▼                    ▼                    ▼                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                       │
│  │  短期记忆    │    │  长期记忆    │    │  工作记忆    │                       │
│  │  (Session)   │    │  (Persistent)│    │  (Working)   │                       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                       │
│         │                   │                   │                               │
└─────────┼───────────────────┼───────────────────┼────────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            存储引擎层                                             │
│                                                                                  │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐            │
│  │         SQLite               │    │          DuckDB              │            │
│  │     (事务型存储)             │    │       (分析型存储)           │            │
│  │                              │    │                              │            │
│  │  • 经验记录                  │    │  • K线时序数据               │            │
│  │  • 交易日志                  │    │  • 技术指标历史              │            │
│  │  • 策略规则                  │    │  • 因子库                    │            │
│  │  • 进化历史                  │    │  • 聚合分析结果              │            │
│  │  • 配置参数                  │    │  • 向量索引                  │            │
│  └──────────────────────────────┘    └──────────────────────────────┘            │
│                                                                                  │
│  ┌──────────────────────────────┐                                               │
│  │       向量存储               │                                               │
│  │    (FAISS / 内存)            │                                               │
│  │                              │                                               │
│  │  • 经验特征向量              │                                               │
│  │  • 文本语义向量              │                                               │
│  └──────────────────────────────┘                                               │
└──────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            LLM 接口层                                            │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                        LLMProviderFactory                                  │ │
│  │                    （可配置 LLM 提供者工厂）                                │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│          │                    │                    │                             │
│          ▼                    ▼                    ▼                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                       │
│  │   OpenAI     │    │  Anthropic   │    │  本地模型    │                       │
│  │   GPT-4      │    │  Claude      │    │  Ollama      │                       │
│  └──────────────┘    └──────────────┘    └──────────────┘                       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、存储引擎设计

### 3.1 双引擎分工

| 引擎 | 职责 | 特点 |
|------|------|------|
| **SQLite** | 事务型数据（经验、规则、配置） | ACID、单文件、易备份 |
| **DuckDB** | 分析型数据（K线、指标、因子） | 列式存储、向量化查询、高性能聚合 |

### 3.2 SQLite 表结构

```sql
-- ============================================================
-- 1. 经验表（核心）
-- ============================================================
CREATE TABLE IF NOT EXISTS experiences (
    experience_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT,                    -- LONG/SHORT/FLAT
    
    -- 上下文快照
    trend_phase TEXT,                  -- CONSOLIDATING/EMERGING/DEVELOPING/MATURE/FATIGUING/REVERSING
    phase_confidence REAL,
    market_regime TEXT,                -- TRENDING/RANGING/VOLATILE
    
    -- 动作与结果
    action_taken TEXT,                 -- 实际执行的动作
    action_reasoning TEXT,             -- 动作推理依据
    entry_price REAL,
    exit_price REAL,
    pnl_pct REAL,
    holding_days INTEGER,
    max_drawdown_pct REAL,
    risk_adjusted_return REAL,
    
    -- 特征向量（JSON 存储）
    feature_vector TEXT,               -- 15维特征向量
    context_snapshot TEXT,             -- 完整上下文快照
    full_data TEXT,                    -- 完整数据（用于深度分析）
    
    -- 元数据
    source TEXT DEFAULT 'manual',      -- manual/auto/cold_start
    confidence REAL DEFAULT 0.5,
    importance REAL DEFAULT 0.5,
    
    -- 时间戳
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_experiences_symbol ON experiences(symbol);
CREATE INDEX idx_experiences_timestamp ON experiences(timestamp);
CREATE INDEX idx_experiences_trend_phase ON experiences(trend_phase);
CREATE INDEX idx_experiences_pnl ON experiences(pnl_pct);

-- ============================================================
-- 2. 策略规则表
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_rules (
    rule_id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL,           -- entry/exit/position/risk
    rule_content TEXT NOT NULL,        -- 规则内容（JSON）
    
    -- 适用条件
    applicable_phases TEXT,            -- 适用的趋势阶段（JSON数组）
    applicable_symbols TEXT,           -- 适用的品种（JSON数组）
    
    -- 性能统计
    trigger_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_pnl REAL DEFAULT 0.0,
    
    -- 状态
    status TEXT DEFAULT 'active',      -- active/deprecated/testing
    confidence REAL DEFAULT 0.5,
    source TEXT DEFAULT 'manual',      -- manual/evolved/promoted
    
    -- 时间戳
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    last_triggered_at TEXT
);

CREATE INDEX idx_rules_type ON strategy_rules(rule_type);
CREATE INDEX idx_rules_status ON strategy_rules(status);

-- ============================================================
-- 3. 交易日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS trade_journal (
    journal_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT,
    
    -- 交易详情
    entry_price REAL,
    exit_price REAL,
    pnl_pct REAL,
    holding_days INTEGER,
    
    -- 决策记录
    brief_at_entry TEXT,               -- 入场时的决策简报（JSON）
    brief_at_exit TEXT,                -- 出场时的决策简报（JSON）
    user_decision TEXT,                -- 用户实际决策
    user_notes TEXT,                   -- 用户备注
    
    -- 归因分析
    fault_type TEXT,                   -- ENTRY_ERROR/INDICATOR_MISUSE/TIMING_ERROR/...
    fault_severity REAL,
    fault_detail TEXT,
    
    -- 学习提炼
    lessons_learned TEXT,              -- 学到的教训（JSON数组）
    patterns_detected TEXT,            -- 检测到的模式（JSON数组）
    
    -- 时间戳
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_journal_symbol ON trade_journal(symbol);
CREATE INDEX idx_journal_timestamp ON trade_journal(timestamp);

-- ============================================================
-- 4. 进化历史表
-- ============================================================
CREATE TABLE IF NOT EXISTS evolution_history (
    evolution_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    trigger_reason TEXT,               -- 触发原因
    
    -- 变更记录
    change_type TEXT,                  -- rule_update/param_adjust/pattern_promote
    target_id TEXT,                    -- 被变更的对象ID
    old_value TEXT,
    new_value TEXT,
    
    -- 效果评估
    expected_improvement REAL,
    actual_improvement REAL,
    validation_status TEXT,            -- pending/validated/rejected
    
    -- 审计
    audit_score REAL,                  -- 过拟合审计分数
    audit_detail TEXT,
    
    -- 时间戳
    created_at TEXT DEFAULT (datetime('now')),
    validated_at TEXT
);

CREATE INDEX idx_evolution_timestamp ON evolution_history(timestamp);

-- ============================================================
-- 5. 模式库表
-- ============================================================
CREATE TABLE IF NOT EXISTS pattern_library (
    pattern_id TEXT PRIMARY KEY,
    pattern_name TEXT NOT NULL,
    pattern_type TEXT NOT NULL,        -- trend/reversal/breakout/event_driven
    
    -- 模式定义
    conditions TEXT NOT NULL,          -- 触发条件（JSON）
    feature_signature TEXT,            -- 特征签名（向量）
    
    -- 统计信息
    occurrences INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_pnl REAL DEFAULT 0.0,
    avg_holding_days REAL DEFAULT 0.0,
    
    -- 关联
    associated_rules TEXT,             -- 关联的规则ID（JSON数组）
    
    -- 状态
    status TEXT DEFAULT 'active',
    confidence REAL DEFAULT 0.5,
    
    -- 时间戳
    created_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT
);

CREATE INDEX idx_patterns_type ON pattern_library(pattern_type);

-- ============================================================
-- 6. LLM 调用记录表
-- ============================================================
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    
    -- 调用详情
    provider TEXT,                     -- openai/anthropic/local
    model TEXT,
    purpose TEXT,                      -- reason/debate/evolve/factor
    
    -- 输入输出
    input_tokens INTEGER,
    output_tokens INTEGER,
    input_summary TEXT,
    output_summary TEXT,
    
    -- 性能
    latency_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    
    -- 成本
    cost_usd REAL,
    
    -- 时间戳
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_llm_calls_timestamp ON llm_calls(timestamp);
CREATE INDEX idx_llm_calls_provider ON llm_calls(provider);

-- ============================================================
-- 7. 配置表
-- ============================================================
CREATE TABLE IF NOT EXISTS system_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    config_type TEXT DEFAULT 'json',   -- json/string/number/boolean
    description TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
```

### 3.3 DuckDB 表结构

```sql
-- ============================================================
-- 1. K线数据表（列式存储，高性能聚合）
-- ============================================================
CREATE TABLE IF NOT EXISTS klines (
    symbol VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    timeframe VARCHAR NOT NULL,        -- daily/1h/15m/5m
    
    -- OHLCV
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    open_interest DOUBLE,
    
    -- 元数据
    source VARCHAR DEFAULT 'tqsdk',
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX idx_klines_symbol_time ON klines(symbol, timestamp);

-- ============================================================
-- 2. 技术指标历史表
-- ============================================================
CREATE TABLE IF NOT EXISTS indicators (
    symbol VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    indicator_name VARCHAR NOT NULL,   -- rsi/macd/adx/er/tsi/...
    value DOUBLE,
    
    -- 元数据
    parameters VARCHAR,                -- 指数参数（JSON）
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX idx_indicators_symbol_name ON indicators(symbol, indicator_name);

-- ============================================================
-- 3. 因子库表
-- ============================================================
CREATE TABLE IF NOT EXISTS factor_library (
    factor_id VARCHAR PRIMARY KEY,
    factor_name VARCHAR NOT NULL,
    factor_type VARCHAR NOT NULL,      -- technical/fundamental/sentiment/custom
    
    -- 因子定义
    expression VARCHAR NOT NULL,       -- 因子表达式
    parameters VARCHAR,                -- 参数（JSON）
    
    -- 性能统计
    ic_mean DOUBLE,                    -- 信息系数均值
    ic_std DOUBLE,                     -- 信息系数标准差
    ir DOUBLE,                         -- 信息比率
    turnover DOUBLE,                   -- 换手率
    
    -- 状态
    status VARCHAR DEFAULT 'active',
    confidence DOUBLE DEFAULT 0.5,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT current_timestamp,
    last_evaluated_at TIMESTAMP
);

-- ============================================================
-- 4. 向量索引表（用于相似度检索）
-- ============================================================
CREATE TABLE IF NOT EXISTS vector_index (
    vector_id VARCHAR PRIMARY KEY,
    entity_type VARCHAR NOT NULL,      -- experience/pattern/rule
    entity_id VARCHAR NOT NULL,
    
    -- 向量数据
    vector DOUBLE[] NOT NULL,
    dimension INTEGER NOT NULL,
    
    -- 元数据
    metadata VARCHAR,                  -- 额外元数据（JSON）
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX idx_vector_entity ON vector_index(entity_type, entity_id);
```

---

## 四、记忆层次设计

### 4.1 三层记忆架构

| 层次 | 类型 | 生命周期 | 存储位置 | 用途 |
|------|------|----------|----------|------|
| **短期记忆** | Session | 会话级 | 内存 | 当前分析上下文、临时计算结果 |
| **工作记忆** | Working | 日级 | SQLite | 今日信号、预警、决策简报 |
| **长期记忆** | Persistent | 永久 | SQLite + DuckDB | 经验、规则、模式、历史数据 |

### 4.2 记忆流转

```
市场数据 → 短期记忆 → 工作记忆 → 长期记忆
                │           │           │
                ▼           ▼           ▼
           实时计算    当日汇总    持久化存储
                │           │           │
                └───────────┴───────────┘
                            │
                            ▼
                    经验检索 → 推理决策
```

### 4.3 统一记忆管理器

```python
class UnifiedMemoryManager:
    """
    统一记忆管理器 - 记忆系统的唯一入口
    
    职责：
    1. 管理三层记忆（短期/工作/长期）
    2. 提供统一的读写接口
    3. 协调 SQLite 和 DuckDB
    4. 管理向量索引
    """
    
    def __init__(self, config: Dict[str, Any]):
        # SQLite 连接（事务型）
        self.sqlite_conn = sqlite3.connect(config['sqlite_path'])
        
        # DuckDB 连接（分析型）
        self.duckdb_conn = duckdb.connect(config['duckdb_path'])
        
        # 向量存储
        self.vector_store = VectorStore(config.get('vector_dim', 15))
        
        # LLM 提供者
        self.llm_provider = LLMProviderFactory.create(config['llm'])
        
        # 短期记忆（内存）
        self.short_term = {}
        
        # 工作记忆（今日）
        self.working_memory = WorkingMemory(self.sqlite_conn)
    
    # ========== 经验管理 ==========
    
    def store_experience(self, experience: Experience) -> str:
        """存储一条经验"""
        # 1. 存入 SQLite
        self._save_to_sqlite('experiences', experience)
        
        # 2. 更新向量索引
        self.vector_store.add(
            entity_type='experience',
            entity_id=experience.experience_id,
            vector=experience.feature_vector
        )
        
        # 3. 存入 DuckDB（用于分析）
        self._save_to_duckdb('klines', experience.context_snapshot)
        
        return experience.experience_id
    
    def retrieve_experiences(
        self, 
        context: MarketContext, 
        top_k: int = 5,
        time_decay: bool = True
    ) -> List[ExperienceMatch]:
        """检索相似经验"""
        # 1. 向量检索（粗筛）
        vector_matches = self.vector_store.search(
            query_vector=context.feature_vector,
            top_k=top_k * 3  # 多取一些，后续精筛
        )
        
        # 2. 结构化过滤（精筛）
        filtered = self._filter_by_context(vector_matches, context)
        
        # 3. 时间衰减加权
        if time_decay:
            filtered = self._apply_time_decay(filtered)
        
        # 4. 排序返回
        return sorted(filtered, key=lambda x: x.similarity, reverse=True)[:top_k]
    
    # ========== 规则管理 ==========
    
    def store_rule(self, rule: StrategyRule) -> str:
        """存储一条策略规则"""
        return self._save_to_sqlite('strategy_rules', rule)
    
    def get_active_rules(
        self, 
        rule_type: str = None,
        trend_phase: str = None
    ) -> List[StrategyRule]:
        """获取活跃规则"""
        query = "SELECT * FROM strategy_rules WHERE status = 'active'"
        params = []
        
        if rule_type:
            query += " AND rule_type = ?"
            params.append(rule_type)
        
        if trend_phase:
            query += " AND applicable_phases LIKE ?"
            params.append(f'%{trend_phase}%')
        
        return self._query_sqlite(query, params)
    
    # ========== 模式管理 ==========
    
    def store_pattern(self, pattern: Pattern) -> str:
        """存储一个模式"""
        return self._save_to_sqlite('pattern_library', pattern)
    
    def detect_patterns(self, df: pd.DataFrame) -> List[Pattern]:
        """从数据中检测模式"""
        # 使用 DuckDB 进行高性能分析
        return self._analyze_with_duckdb(df)
    
    # ========== 分析查询 ==========
    
    def analyze_performance(
        self, 
        symbol: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """分析交易性能（使用 DuckDB）"""
        query = """
        SELECT 
            symbol,
            COUNT(*) as trade_count,
            AVG(pnl_pct) as avg_pnl,
            SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate,
            AVG(holding_days) as avg_holding,
            MAX(pnl_pct) as best_trade,
            MIN(pnl_pct) as worst_trade,
            STDDEV(pnl_pct) as pnl_std
        FROM trade_journal
        WHERE 1=1
        """
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " GROUP BY symbol"
        
        return self._query_duckdb(query, params)
    
    def get_factor_performance(self) -> pd.DataFrame:
        """获取因子性能（使用 DuckDB）"""
        query = """
        SELECT 
            factor_name,
            factor_type,
            ic_mean,
            ic_std,
            ir,
            turnover,
            status
        FROM factor_library
        WHERE status = 'active'
        ORDER BY ir DESC
        """
        return self.duckdb_conn.execute(query).fetchdf()
```

---

## 五、可配置 LLM 设计

### 5.1 LLM 提供者架构

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class LLMProvider(ABC):
    """LLM 提供者抽象基类"""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        pass
    
    @abstractmethod
    def chat(self, messages: list, **kwargs) -> str:
        """对话模式"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """提供者名称"""
        pass
    
    @property
    @abstractmethod
    def model(self) -> str:
        """模型名称"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI 提供者"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        import openai
        self.client = openai.OpenAI(api_key=api_key)
        self._model = model
    
    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get('temperature', 0.3),
            max_tokens=kwargs.get('max_tokens', 2000)
        )
        return response.choices[0].message.content
    
    def chat(self, messages: list, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=kwargs.get('temperature', 0.3),
            max_tokens=kwargs.get('max_tokens', 2000)
        )
        return response.choices[0].message.content
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def model(self) -> str:
        return self._model


class AnthropicProvider(LLMProvider):
    """Anthropic 提供者"""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self._model = model
    
    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.messages.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=kwargs.get('max_tokens', 2000)
        )
        return response.content[0].text
    
    def chat(self, messages: list, **kwargs) -> str:
        response = self.client.messages.create(
            model=self._model,
            messages=messages,
            max_tokens=kwargs.get('max_tokens', 2000)
        )
        return response.content[0].text
    
    @property
    def name(self) -> str:
        return "anthropic"
    
    @property
    def model(self) -> str:
        return self._model


class LocalLLMProvider(LLMProvider):
    """本地 LLM 提供者（Ollama）"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        import requests
        self.base_url = base_url
        self._model = model
    
    def generate(self, prompt: str, **kwargs) -> str:
        import requests
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False
            }
        )
        return response.json()['response']
    
    def chat(self, messages: list, **kwargs) -> str:
        import requests
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "stream": False
            }
        )
        return response.json()['message']['content']
    
    @property
    def name(self) -> str:
        return "local"
    
    @property
    def model(self) -> str:
        return self._model


class WorkBuddyProvider(LLMProvider):
    """WorkBuddy Agent 提供者（默认）"""
    
    def __init__(self, model: str = "default"):
        self._model = model
    
    def generate(self, prompt: str, **kwargs) -> str:
        # 在 WorkBuddy 环境中，这个调用会被 Agent 系统处理
        # 这里提供一个 fallback 实现
        return self._fallback(prompt)
    
    def chat(self, messages: list, **kwargs) -> str:
        # 合并消息为单个 prompt
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        return self.generate(prompt, **kwargs)
    
    def _fallback(self, prompt: str) -> str:
        """降级响应"""
        return json.dumps({
            "routes": [{
                "route_id": "A",
                "name": "观望等待",
                "action": "暂不操作，等待更明确的信号",
                "confidence": 0.5,
                "reasoning": "LLM 不可用，使用规则退化建议"
            }],
            "warnings": ["当前使用规则退化模式"]
        }, ensure_ascii=False)
    
    @property
    def name(self) -> str:
        return "workbuddy"
    
    @property
    def model(self) -> str:
        return self._model


class LLMProviderFactory:
    """LLM 提供者工厂"""
    
    @staticmethod
    def create(config: Dict[str, Any]) -> LLMProvider:
        """
        创建 LLM 提供者
        
        配置示例：
        {
            "provider": "openai",  # openai/anthropic/local/workbuddy
            "api_key": "sk-xxx",   # OpenAI/Anthropic 需要
            "model": "gpt-4",      # 模型名称
            "base_url": "http://localhost:11434"  # 本地模型需要
        }
        """
        provider = config.get('provider', 'workbuddy')
        
        if provider == 'openai':
            return OpenAIProvider(
                api_key=config['api_key'],
                model=config.get('model', 'gpt-4')
            )
        elif provider == 'anthropic':
            return AnthropicProvider(
                api_key=config['api_key'],
                model=config.get('model', 'claude-3-sonnet-20240229')
            )
        elif provider == 'local':
            return LocalLLMProvider(
                base_url=config.get('base_url', 'http://localhost:11434'),
                model=config.get('model', 'llama2')
            )
        elif provider == 'workbuddy':
            return WorkBuddyProvider(
                model=config.get('model', 'default')
            )
        else:
            raise ValueError(f"不支持的 LLM 提供者: {provider}")
```

### 5.2 配置文件格式

```json
{
  "memory_system": {
    "sqlite_path": "data/memory.db",
    "duckdb_path": "data/analytics.duckdb",
    "vector_dim": 15,
    "max_experiences": 10000,
    "time_decay_half_life_days": 90
  },
  "llm": {
    "provider": "openai",
    "api_key": "${OPENAI_API_KEY}",
    "model": "gpt-4",
    "temperature": 0.3,
    "max_tokens": 2000,
    "daily_budget": 850000,
    "fallback": {
      "provider": "workbuddy",
      "model": "default"
    }
  }
}
```

---

## 六、自优化闭环

### 6.1 进化流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        自优化闭环                                │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │   交易执行    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   结果记录    │ ← trade_journal
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   轨迹分析    │ ← TradeTrajectoryAnalyzer
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   故障归因    │ ← TradeFaultAttributor
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   模式检测    │ ← PatternDetector (DuckDB 分析)
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   LLM 反思    │ ← LLMProvider.generate()
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   规则优化    │ ← strategy_rules 更新
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   过拟合审计  │ ← OverfittingAuditor
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   规则晋升    │ ← pattern_library → strategy_rules
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   经验存储    │ ← experiences
    └──────┬───────┘
           │
           └──────────→ 回到交易执行（闭环）
```

### 6.2 进化触发条件

```python
class EvolutionTrigger:
    """进化触发器"""
    
    def __init__(self, memory: UnifiedMemoryManager):
        self.memory = memory
    
    def should_evolve(self) -> tuple[bool, str]:
        """检查是否应该触发进化"""
        
        # 条件1：连续亏损 >= 3 次
        recent_trades = self.memory.get_recent_trades(n=10)
        consecutive_losses = 0
        for trade in reversed(recent_trades):
            if trade.pnl_pct < 0:
                consecutive_losses += 1
            else:
                break
        
        if consecutive_losses >= 3:
            return True, f"连续亏损{consecutive_losses}次"
        
        # 条件2：累计亏损 >= 10%
        cumulative_pnl = sum(t.pnl_pct for t in recent_trades)
        if cumulative_pnl <= -10:
            return True, f"累计亏损{cumulative_pnl:.1f}%"
        
        # 条件3：距上次进化 >= 20 笔交易
        last_evolution = self.memory.get_last_evolution()
        trades_since = self.memory.get_trade_count_since(last_evolution)
        if trades_since >= 20:
            return True, f"距上次进化{trades_since}笔交易"
        
        # 条件4：检测到新模式
        new_patterns = self.memory.detect_new_patterns()
        if len(new_patterns) > 0:
            return True, f"检测到{len(new_patterns)}个新模式"
        
        return False, "未达到触发条件"
```

### 6.3 规则晋升流程

```python
class RulePromoter:
    """规则晋升器"""
    
    def __init__(self, memory: UnifiedMemoryManager):
        self.memory = memory
    
    def promote_pattern_to_rule(self, pattern: Pattern) -> Optional[StrategyRule]:
        """将模式晋升为规则"""
        
        # 检查晋升条件
        if pattern.occurrences < 5:
            return None  # 样本不足
        
        if pattern.win_rate < 0.6:
            return None  # 胜率不足
        
        if pattern.confidence < 0.7:
            return None  # 置信度不足
        
        # 创建规则
        rule = StrategyRule(
            rule_id=f"R_{pattern.pattern_id}",
            rule_name=f"从模式 {pattern.pattern_name} 晋升",
            rule_type=self._infer_rule_type(pattern),
            rule_content=self._generate_rule_content(pattern),
            applicable_phases=pattern.applicable_phases,
            confidence=pattern.confidence,
            source='promoted'
        )
        
        # 存储规则
        self.memory.store_rule(rule)
        
        # 记录晋升历史
        self.memory.record_evolution(
            change_type='pattern_promote',
            target_id=pattern.pattern_id,
            new_value=rule.rule_id,
            expected_improvement=pattern.avg_pnl
        )
        
        return rule
```

---

## 七、检索策略设计

### 7.1 多路召回

```python
class MultiPathRetriever:
    """多路召回检索器"""
    
    def __init__(self, memory: UnifiedMemoryManager):
        self.memory = memory
    
    def retrieve(
        self, 
        context: MarketContext, 
        top_k: int = 5
    ) -> List[ExperienceMatch]:
        """多路召回相似经验"""
        
        results = []
        
        # 路径1：向量相似度检索
        vector_matches = self.memory.vector_store.search(
            query_vector=context.feature_vector,
            top_k=top_k * 2
        )
        results.extend(vector_matches)
        
        # 路径2：结构化条件检索
        condition_matches = self.memory.query_experiences(
            symbol=context.symbol,
            trend_phase=context.trend_phase.phase,
            limit=top_k
        )
        results.extend(condition_matches)
        
        # 路径3：文本语义检索（如果可用）
        if self.memory.text_search_enabled:
            text_matches = self.memory.text_search(
                query=self._build_text_query(context),
                top_k=top_k
            )
            results.extend(text_matches)
        
        # 路径4：多粒度检索
        granularity_matches = self.memory.retrieve_by_granularity(
            context=context,
            granularity='medium'  # 30天
        )
        results.extend(granularity_matches)
        
        # 去重 + 排序
        unique_results = self._deduplicate(results)
        sorted_results = sorted(
            unique_results, 
            key=lambda x: x.similarity, 
            reverse=True
        )
        
        return sorted_results[:top_k]
```

### 7.2 相似度计算

```python
class SimilarityCalculator:
    """相似度计算器"""
    
    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or {
            'vector_cosine': 0.4,      # 向量余弦相似度
            'vector_euclidean': 0.2,   # 向量欧氏距离
            'structural': 0.2,         # 结构化相似度
            'temporal': 0.1,           # 时间相似度
            'symbol': 0.1              # 品种相似度
        }
    
    def calculate(
        self, 
        query: MarketContext, 
        candidate: Experience
    ) -> float:
        """计算综合相似度"""
        
        scores = {}
        
        # 1. 向量余弦相似度
        scores['vector_cosine'] = self._cosine_similarity(
            query.feature_vector, 
            candidate.feature_vector
        )
        
        # 2. 向量欧氏距离（转换为相似度）
        scores['vector_euclidean'] = 1 / (1 + self._euclidean_distance(
            query.feature_vector, 
            candidate.feature_vector
        ))
        
        # 3. 结构化相似度
        scores['structural'] = self._structural_similarity(query, candidate)
        
        # 4. 时间相似度（指数衰减）
        scores['temporal'] = self._temporal_similarity(
            query.timestamp, 
            candidate.timestamp
        )
        
        # 5. 品种相似度
        scores['symbol'] = 1.0 if query.symbol == candidate.symbol else 0.3
        
        # 加权求和
        total = sum(
            scores[key] * self.weights[key] 
            for key in self.weights
        )
        
        return total
```

---

## 八、配置管理

### 8.1 配置文件结构

```json
{
  "memory_system": {
    "sqlite_path": "data/memory.db",
    "duckdb_path": "data/analytics.duckdb",
    "vector_dim": 15,
    "max_experiences": 10000,
    "time_decay_half_life_days": 90,
    "enable_text_search": true,
    "text_search_model": "paraphrase-multilingual-MiniLM-L12-v2"
  },
  "llm": {
    "provider": "openai",
    "api_key": "${OPENAI_API_KEY}",
    "model": "gpt-4",
    "temperature": 0.3,
    "max_tokens": 2000,
    "daily_budget": 850000,
    "timeout_seconds": 30,
    "retry_count": 3,
    "fallback": {
      "provider": "workbuddy",
      "model": "default"
    }
  },
  "evolution": {
    "auto_trigger": {
      "consecutive_losses": 3,
      "cumulative_loss_pct": 10,
      "trade_count_interval": 20
    },
    "overfitting_threshold": 0.7,
    "min_samples_for_rule": 5,
    "rule_promotion_threshold": 0.6
  },
  "retrieval": {
    "top_k": 5,
    "min_similarity": 0.5,
    "enable_multi_path": true,
    "granularity": "medium"
  }
}
```

### 8.2 环境变量支持

```python
import os

def load_config(config_path: str = "config/memory_config.json") -> Dict[str, Any]:
    """加载配置（支持环境变量替换）"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 替换环境变量
    def replace_env(obj):
        if isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            env_var = obj[2:-1]
            return os.environ.get(env_var, obj)
        elif isinstance(obj, dict):
            return {k: replace_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_env(item) for item in obj]
        return obj
    
    return replace_env(config)
```

---

## 九、使用示例

### 9.1 初始化记忆系统

```python
from trend_scanner.memory_system import UnifiedMemoryManager

# 加载配置
config = load_config("config/memory_config.json")

# 初始化记忆系统
memory = UnifiedMemoryManager(config)
```

### 9.2 存储经验

```python
from trend_scanner.models import Experience

# 创建经验
experience = Experience(
    experience_id="EXP_20260615_001",
    timestamp="2026-06-15T10:30:00",
    symbol="DCE.jm2609",
    trend_phase="DEVELOPING",
    action_taken="LONG",
    entry_price=1350,
    exit_price=1385,
    pnl_pct=2.59,
    holding_days=3,
    feature_vector=[0.65, 25.3, 0.72, 0.68, 0.72, ...]
)

# 存储
exp_id = memory.store_experience(experience)
print(f"经验已存储: {exp_id}")
```

### 9.3 检索相似经验

```python
from trend_scanner.models import MarketContext

# 当前市场上下文
context = MarketContext(
    symbol="DCE.jm2609",
    trend_phase="DEVELOPING",
    feature_vector=[0.62, 22.1, 0.68, 0.65, 0.70, ...]
)

# 检索相似经验
matches = memory.retrieve_experiences(context, top_k=5)

for match in matches:
    print(f"经验: {match.experience.experience_id}")
    print(f"相似度: {match.similarity:.3f}")
    print(f"盈亏: {match.experience.pnl_pct:.2f}%")
```

### 9.4 切换 LLM

```python
# 切换到 Anthropic
config['llm'] = {
    "provider": "anthropic",
    "api_key": os.environ['ANTHROPIC_API_KEY'],
    "model": "claude-3-sonnet-20240229"
}
memory.llm_provider = LLMProviderFactory.create(config['llm'])

# 切换到本地模型
config['llm'] = {
    "provider": "local",
    "base_url": "http://localhost:11434",
    "model": "llama2"
}
memory.llm_provider = LLMProviderFactory.create(config['llm'])
```

### 9.5 触发进化

```python
from trend_scanner.evolution_system import EvolutionTrigger

# 检查是否需要进化
trigger = EvolutionTrigger(memory)
should_evolve, reason = trigger.should_evolve()

if should_evolve:
    print(f"触发进化: {reason}")
    # 执行进化...
```

---

## 十、实施路线

### 10.1 阶段规划

| 阶段 | 时间 | 任务 | 交付物 |
|------|------|------|--------|
| **Phase 1** | 1周 | 统一记忆管理器核心 | `UnifiedMemoryManager` |
| **Phase 2** | 1周 | SQLite + DuckDB 存储层 | 表结构 + CRUD |
| **Phase 3** | 1周 | 可配置 LLM 接口 | `LLMProviderFactory` |
| **Phase 4** | 1周 | 向量检索增强 | 多路召回 + 相似度计算 |
| **Phase 5** | 1周 | 自优化闭环 | 进化触发 + 规则晋升 |
| **Phase 6** | 1周 | 集成测试 + 文档 | 测试用例 + 使用文档 |

### 10.2 优先级

| 优先级 | 任务 | 理由 |
|--------|------|------|
| **P0** | SQLite 表结构 | 基础存储 |
| **P0** | LLM 可配置 | 核心需求 |
| **P1** | DuckDB 分析 | 性能优化 |
| **P1** | 向量检索 | 检索质量 |
| **P2** | 自优化闭环 | 高级功能 |
| **P2** | 多路召回 | 检索增强 |

---

## 十一、与现有系统的集成

### 11.1 替换关系

| 现有模块 | 替换为 | 说明 |
|----------|--------|------|
| `experience.py` | `UnifiedMemoryManager` | 统一入口 |
| `data_store.py` | 合并到记忆系统 | 双引擎统一管理 |
| `memory_vectorizer.py` | 集成到向量存储 | 统一向量管理 |
| `llm_factor_client.py` | `LLMProviderFactory` | 统一 LLM 接口 |

### 11.2 兼容性

- 保留现有 Agent 的调用接口
- 逐步迁移，不破坏现有功能
- 提供适配器层，兼容旧代码

---

## 十二、总结

### 核心优势

1. **存储统一**：SQLite + DuckDB 分工明确，各司其职
2. **LLM 灵活**：支持 4 种 LLM 提供者，一键切换
3. **检索高效**：多路召回 + 向量检索，毫秒级响应
4. **自优化**：完整的进化闭环，自动优化策略
5. **可观测**：每条记忆可追溯，每次进化可审计

### 技术亮点

1. **三层记忆架构**：短期/工作/长期，分工明确
2. **双存储引擎**：事务型 + 分析型，性能最优
3. **多路召回**：向量 + 结构化 + 语义，召回率高
4. **规则晋升**：模式→规则自动晋升，持续进化
5. **过拟合审计**：防止过度优化，保持稳健
