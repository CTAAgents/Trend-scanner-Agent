# 期货数据路由设计

> 版本：v1.0 | 创建日期：2026-06-18
> 状态：设计完成

---

## 一、设计目标

1. 统一管理期货数据获取、存储、更新
2. 支持多数据源自动切换
3. 每天收盘后自动更新所有品种数据
4. 无法获取的数据在下一个交易日开盘前重试

---

## 二、数据源路由

### 2.1 数据源优先级

| 数据类型 | 首选 | 第二 | 第三 | 说明 |
|----------|------|------|------|------|
| K线/实时行情 | TqSdk | 通达信MCP | - | TqSdk通过target="1"获取 |
| 库存/仓单 | AKShare | - | - | 交易所官方数据 |
| 基差 | AKShare | TqSdk（计算） | - | 现货-期货价差 |
| 期限结构 | AKShare | TqSdk（计算） | - | 展期收益率 |
| 持仓排名 | AKShare | TqSdk（仅OI） | - | 会员持仓排名 |
| 宏观数据 | 通达信MCP | AKShare | - | GDP/CPI/PPI |
| 研报数据 | 通达信MCP | - | - | 券商研报 |

### 2.2 数据源适配器

```python
class FuturesDataProvider:
    """期货数据路由"""
    
    # K线数据
    def get_kline(self, symbol, timeframe, count):
        # 优先TqSdk，失败则通达信MCP
        pass
    
    # 库存数据
    def get_inventory(self, symbol):
        # AKShare
        pass
    
    # 仓单数据
    def get_warehouse_receipt(self, symbol, date):
        # AKShare
        pass
    
    # 基差数据
    def get_basis(self, symbol, date):
        # AKShare
        pass
    
    # 期限结构
    def get_term_structure(self, symbol, date):
        # AKShare
        pass
    
    # 持仓排名
    def get_position_rank(self, symbol, date):
        # AKShare
        pass
    
    # 宏观数据
    def get_macro_data(self, query):
        # 通达信MCP
        pass
    
    # 研报数据
    def get_report(self, query):
        # 通达信MCP
        pass
```

---

## 三、DuckDB数据库结构

### 3.1 表结构

```sql
-- 1. K线数据表
CREATE TABLE futures_kline (
    symbol VARCHAR NOT NULL,        -- 品种代码 (RB, I, J...)
    date DATE NOT NULL,             -- 交易日期
    open DOUBLE,                    -- 开盘价
    high DOUBLE,                    -- 最高价
    low DOUBLE,                     -- 最低价
    close DOUBLE,                   -- 收盘价
    volume BIGINT,                  -- 成交量
    open_interest BIGINT,           -- 持仓量
    close_oi BIGINT,                -- 收盘持仓量
    data_source VARCHAR,            -- 数据来源 (tqsdk/tdx)
    update_time TIMESTAMP,          -- 更新时间
    PRIMARY KEY (symbol, date)
);

-- 2. 库存数据表
CREATE TABLE futures_inventory (
    symbol VARCHAR NOT NULL,        -- 品种代码
    date DATE NOT NULL,             -- 交易日期
    inventory BIGINT,               -- 库存量
    change_amount BIGINT,           -- 增减量
    data_source VARCHAR,            -- 数据来源 (akshare)
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 3. 仓单数据表
CREATE TABLE futures_warehouse_receipt (
    symbol VARCHAR NOT NULL,        -- 品种代码
    date DATE NOT NULL,             -- 交易日期
    exchange VARCHAR,               -- 交易所 (SHFE/DCE/CZCE/GFEX)
    warehouse VARCHAR,              -- 仓库名称
    receipt_amount BIGINT,          -- 仓单数量
    change_amount BIGINT,           -- 增减量
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date, warehouse)
);

-- 4. 技术指标表（TqSdk + 本地实现）
CREATE TABLE futures_indicators (
    symbol VARCHAR NOT NULL,        -- 品种代码
    date DATE NOT NULL,             -- 交易日期
    
    -- 趋势指标
    ema5 DOUBLE,                    -- 5日EMA
    ema10 DOUBLE,                   -- 10日EMA
    ema20 DOUBLE,                   -- 20日EMA
    ema60 DOUBLE,                   -- 60日EMA
    ma5 DOUBLE,                     -- 5日均线
    ma10 DOUBLE,                    -- 10日均线
    ma20 DOUBLE,                    -- 20日均线
    ma60 DOUBLE,                    -- 60日均线
    
    -- 动量指标
    rsi14 DOUBLE,                   -- 14日RSI
    rsi6 DOUBLE,                    -- 6日RSI
    macd DOUBLE,                    -- MACD
    macd_signal DOUBLE,             -- MACD信号线
    macd_hist DOUBLE,               -- MACD柱状图
    kdj_k DOUBLE,                   -- KDJ-K值
    kdj_d DOUBLE,                   -- KDJ-D值
    kdj_j DOUBLE,                   -- KDJ-J值
    
    -- 波动率指标
    atr14 DOUBLE,                   -- 14日ATR
    boll_upper DOUBLE,              -- 布林带上轨
    boll_middle DOUBLE,             -- 布林带中轨
    boll_lower DOUBLE,              -- 布林带下轨
    std20 DOUBLE,                   -- 20日标准差
    
    -- 成交量指标
    obv DOUBLE,                     -- OBV能量潮
    vwap DOUBLE,                    -- 成交量加权均价
    
    -- 趋势强度
    adx14 DOUBLE,                   -- 14日ADX
    plus_di DOUBLE,                 -- +DI
    minus_di DOUBLE,                -- -DI
    
    -- 自研指标
    trend_strength DOUBLE,          -- 7维趋势强度
    momentum_score DOUBLE,          -- 动量评分
    volatility_regime DOUBLE,       -- 波动率状态
    
    data_source VARCHAR,            -- 数据来源 (tqsdk/local)
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 5. 基差数据表
CREATE TABLE futures_basis (
    symbol VARCHAR NOT NULL,        -- 品种代码
    date DATE NOT NULL,             -- 交易日期
    spot_price DOUBLE,              -- 现货价格
    futures_price DOUBLE,           -- 期货价格
    basis DOUBLE,                   -- 基差 (现货-期货)
    basis_rate DOUBLE,              -- 基差率
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 6. 期限结构表
CREATE TABLE futures_term_structure (
    symbol VARCHAR NOT NULL,        -- 品种代码
    date DATE NOT NULL,             -- 交易日期
    near_month VARCHAR,             -- 近月合约
    near_price DOUBLE,              -- 近月价格
    far_month VARCHAR,              -- 远月合约
    far_price DOUBLE,               -- 远月价格
    roll_yield DOUBLE,              -- 展期收益率
    structure_type VARCHAR,         -- Contango/Backwardation
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 7. 持仓排名表
CREATE TABLE futures_position_rank (
    symbol VARCHAR NOT NULL,        -- 品种代码
    date DATE NOT NULL,             -- 交易日期
    rank_type VARCHAR,              -- 排名类型 (long/short)
    rank_number INT,                -- 排名序号
    member_name VARCHAR,            -- 会员名称
    position_volume BIGINT,         -- 持仓量
    change_volume BIGINT,           -- 增减量
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date, rank_type, rank_number)
);

-- 8. 宏观数据表
CREATE TABLE macro_data (
    subject VARCHAR NOT NULL,       -- 主体 (中国/美国)
    indicator VARCHAR NOT NULL,     -- 指标 (GDP/CPI/PPI)
    date DATE NOT NULL,             -- 数据日期
    value DOUBLE,                   -- 数值
    unit VARCHAR,                   -- 单位
    data_source VARCHAR,            -- 数据来源 (tdx_mcp)
    update_time TIMESTAMP,
    PRIMARY KEY (subject, indicator, date)
);

-- 9. 研报数据表
CREATE TABLE research_report (
    symbol VARCHAR,                 -- 品种代码 (可为空)
    title VARCHAR,                  -- 研报标题
    author VARCHAR,                 -- 研报机构/作者
    rating VARCHAR,                 -- 评级
    target_price DOUBLE,            -- 目标价
    summary TEXT,                   -- 摘要
    publish_date DATE,              -- 发布日期
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (title, publish_date)
);

-- 10. 数据更新日志表
CREATE TABLE data_update_log (
    update_id SERIAL PRIMARY KEY,
    table_name VARCHAR NOT NULL,    -- 表名
    symbol VARCHAR,                 -- 品种代码
    update_type VARCHAR,            -- 更新类型 (full/incremental)
    status VARCHAR,                 -- 状态 (success/failed/pending)
    records_count INT,              -- 记录数
    error_message TEXT,             -- 错误信息
    start_time TIMESTAMP,           -- 开始时间
    end_time TIMESTAMP,             -- 结束时间
    data_source VARCHAR             -- 数据来源
);

-- 11. 交易日历表
CREATE TABLE trading_calendar (
    date DATE PRIMARY KEY,          -- 日期
    is_trading_day BOOLEAN,         -- 是否交易日
    exchange VARCHAR,               -- 交易所
    update_time TIMESTAMP
);
```

### 3.2 索引设计

```sql
-- K线数据索引
CREATE INDEX idx_kline_symbol ON futures_kline(symbol);
CREATE INDEX idx_kline_date ON futures_kline(date);
CREATE INDEX idx_kline_symbol_date ON futures_kline(symbol, date);

-- 库存数据索引
CREATE INDEX idx_inventory_symbol ON futures_inventory(symbol);
CREATE INDEX idx_inventory_date ON futures_inventory(date);

-- 基差数据索引
CREATE INDEX idx_basis_symbol ON futures_basis(symbol);
CREATE INDEX idx_basis_date ON futures_basis(date);

-- 数据更新日志索引
CREATE INDEX idx_log_table ON data_update_log(table_name);
CREATE INDEX idx_log_status ON data_update_log(status);
CREATE INDEX idx_log_time ON data_update_log(start_time);
```

---

## 四、定时更新机制

### 4.1 更新时间表

| 更新时间 | 数据类型 | 说明 |
|----------|----------|------|
| **15:30** | K线数据 | 日线收盘数据 |
| **15:30** | 库存/仓单 | 当日数据 |
| **15:30** | 基差/期限结构 | 当日数据 |
| **15:30** | 持仓排名 | 当日数据 |
| **20:30** | 宏观数据 | 更新最新宏观指标 |
| **20:30** | 研报数据 | 获取最新研报 |
| **次日08:30** | 失败重试 | 重试前一日失败的数据 |

### 4.2 更新流程

```
15:30 收盘后触发
    ↓
获取交易日历 → 判断是否交易日
    ↓
批量更新K线数据（所有品种）
    ↓
批量更新库存/仓单数据
    ↓
批量更新基差/期限结构数据
    ↓
批量更新持仓排名数据
    ↓
记录更新日志
    ↓
20:30 更新宏观/研报数据
    ↓
次日08:30 重试失败数据
```

### 4.3 失败重试机制

```python
class DataUpdateScheduler:
    """数据更新调度器"""
    
    def __init__(self, db_path):
        self.db = duckdb.connect(db_path)
    
    def schedule_daily_update(self):
        """每日更新调度"""
        # 15:30 收盘后更新
        self.update_kline_data()
        self.update_inventory_data()
        self.update_basis_data()
        self.update_term_structure_data()
        self.update_position_rank_data()
        
        # 20:30 宏观/研报
        self.update_macro_data()
        self.update_report_data()
        
        # 次日09:00 重试
        self.retry_failed_updates()
    
    def retry_failed_updates(self):
        """重试失败的更新"""
        failed = self.db.execute("""
            SELECT * FROM data_update_log 
            WHERE status = 'failed' 
            AND update_time < CURRENT_DATE
        """).fetchall()
        
        for record in failed:
            self.retry_update(record)
```

---

## 五、数据质量控制

### 5.1 数据校验规则

| 规则 | 说明 |
|------|------|
| 价格非负 | open/high/low/close > 0 |
| 成交量非负 | volume >= 0 |
| 日期有效 | 在交易日历范围内 |
| 数据完整 | 必填字段不为空 |
| 时效性 | 数据更新时间在24小时内 |

### 5.2 数据质量检查

```sql
-- 检查数据完整性
SELECT 
    symbol,
    COUNT(*) as total_days,
    MAX(date) as latest_date,
    DATEDIFF('day', MAX(date), CURRENT_DATE) as days_gap
FROM futures_kline
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY symbol
HAVING days_gap > 1;
```

---

*本文档由 WorkBuddy 于 2026-06-18 创建*
