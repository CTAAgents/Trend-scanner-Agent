# 证券数据路由设计

> 版本：v1.0 | 创建日期：2026-06-18
> 状态：设计完成

---

## 一、设计目标

1. 统一管理证券数据获取、存储、更新
2. 技术指标优先使用通达信MCP数据
3. 每天收盘后自动更新所有品种数据
4. 无法获取的数据在下一个交易日开盘前重试

---

## 二、数据源路由

### 2.1 数据源优先级

| 数据类型 | 首选 | 第二 | 第三 | 说明 |
|----------|------|------|------|------|
| K线数据 | 通达信MCP | NeoData | WeStock | tdx_kline |
| **技术指标** | **通达信MCP** | 本地计算 | - | tdx_indicator_select |
| 实时行情 | 通达信MCP | NeoData | - | tdx_quotes |
| 财务数据 | 通达信MCP | NeoData | - | tdx_api_data |
| 股东数据 | 通达信MCP | NeoData | - | tdx_api_data |
| 分红数据 | 通达信MCP | NeoData | - | tdx_api_data |
| 龙虎榜 | 通达信MCP | - | - | tdx_api_data |
| 大宗交易 | 通达信MCP | - | - | tdx_api_data |
| 融资融券 | 通达信MCP | - | - | tdx_api_data |
| 北向资金 | 通达信MCP | - | - | tdx_api_data |
| 行业数据 | 通达信MCP | - | - | tdx_api_data |
| 宏观数据 | 通达信MCP | AKShare | - | wenda_macro_query |
| 研报数据 | 通达信MCP | - | - | wenda_report_query |

### 2.2 通达信MCP技术指标能力

| 指标 | 支持 | 说明 |
|------|------|------|
| MACD | ✅ | DIF、DEA、MACD柱 |
| RSI | ✅ | RSI6、RSI12、RSI14 |
| KDJ | ✅ | K值、D值、J值 |
| EMA | ✅ | 指数移动平均 |
| MA | ✅ | 简单移动平均 |
| BOLL | ✅ | 布林带 |
| ATR | ✅ | 真实波幅 |
| ADX | ✅ | 平均趋向指数 |
| OBV | ✅ | 能量潮 |
| CCI | ✅ | 商品通道指数 |
| WR | ✅ | 威廉指标 |
| DMI | ✅ | 趋向指标 |
| SAR | ✅ | 抛物线指标 |
| BIAS | ✅ | 乖离率 |
| PSY | ✅ | 心理线 |
| TRIX | ✅ | 三重指数平滑平均 |
| DMA | ✅ | 平均线差 |
| EXPMA | ✅ | 指数平均数 |
| ROC | ✅ | 变动速率 |
| MTM | ✅ | 动量指标 |

---

## 三、DuckDB数据库结构

### 3.1 表结构

```sql
-- 1. K线数据表
CREATE TABLE securities_kline (
    symbol VARCHAR NOT NULL,        -- 证券代码 (600519, 000001)
    date DATE NOT NULL,             -- 交易日期
    open DOUBLE,                    -- 开盘价
    high DOUBLE,                    -- 最高价
    low DOUBLE,                     -- 最低价
    close DOUBLE,                   -- 收盘价
    volume BIGINT,                  -- 成交量
    amount DOUBLE,                  -- 成交额
    turnover_rate DOUBLE,           -- 换手率
    data_source VARCHAR,            -- 数据来源 (tdx_mcp)
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 2. 技术指标表（通达信MCP优先）
CREATE TABLE securities_indicators (
    symbol VARCHAR NOT NULL,        -- 证券代码
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
    ma120 DOUBLE,                   -- 120日均线
    ma250 DOUBLE,                   -- 250日均线（年线）
    
    -- 动量指标
    rsi6 DOUBLE,                    -- 6日RSI
    rsi12 DOUBLE,                   -- 12日RSI
    rsi14 DOUBLE,                   -- 14日RSI
    macd_dif DOUBLE,                -- MACD DIF
    macd_dea DOUBLE,                -- MACD DEA
    macd_hist DOUBLE,               -- MACD柱状图
    kdj_k DOUBLE,                   -- KDJ-K值
    kdj_d DOUBLE,                   -- KDJ-D值
    kdj_j DOUBLE,                   -- KDJ-J值
    cci DOUBLE,                     -- CCI
    wr6 DOUBLE,                     -- 6日威廉指标
    wr10 DOUBLE,                    -- 10日威廉指标
    
    -- 波动率指标
    atr14 DOUBLE,                   -- 14日ATR
    boll_upper DOUBLE,              -- 布林带上轨
    boll_middle DOUBLE,             -- 布林带中轨
    boll_lower DOUBLE,              -- 布林带下轨
    std20 DOUBLE,                   -- 20日标准差
    bias6 DOUBLE,                   -- 6日乖离率
    bias12 DOUBLE,                  -- 12日乖离率
    bias24 DOUBLE,                  -- 24日乖离率
    
    -- 成交量指标
    obv DOUBLE,                     -- OBV能量潮
    vwap DOUBLE,                    -- 成交量加权均价
    
    -- 趋势强度
    adx14 DOUBLE,                   -- 14日ADX
    plus_di DOUBLE,                 -- +DI
    minus_di DOUBLE,                -- -DI
    dmi DOUBLE,                     -- DMI
    sar DOUBLE,                     -- SAR抛物线
    trix DOUBLE,                    -- TRIX
    dma DOUBLE,                     -- DMA
    expma DOUBLE,                   -- EXPMA
    roc DOUBLE,                     -- ROC
    mtm DOUBLE,                     -- MTM
    psy DOUBLE,                     -- PSY心理线
    
    -- 自研指标
    trend_strength DOUBLE,          -- 趋势强度
    momentum_score DOUBLE,          -- 动量评分
    volatility_regime DOUBLE,       -- 波动率状态
    
    data_source VARCHAR,            -- 数据来源 (tdx_mcp/local)
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 3. 财务数据表
CREATE TABLE securities_financial (
    symbol VARCHAR NOT NULL,        -- 证券代码
    report_date DATE NOT NULL,      -- 报告期
    report_type VARCHAR,            -- 报告类型 (年报/半年报/季报)
    
    -- 利润表
    revenue DOUBLE,                 -- 营业收入
    net_profit DOUBLE,              -- 净利润
    operating_profit DOUBLE,        -- 营业利润
    gross_profit_margin DOUBLE,     -- 毛利率
    net_profit_margin DOUBLE,       -- 净利率
    
    -- 资产负债表
    total_assets DOUBLE,            -- 总资产
    total_liabilities DOUBLE,       -- 总负债
    total_equity DOUBLE,            -- 股东权益
    debt_ratio DOUBLE,              -- 资产负债率
    current_ratio DOUBLE,           -- 流动比率
    quick_ratio DOUBLE,             -- 速动比率
    
    -- 现金流量表
    operating_cashflow DOUBLE,      -- 经营活动现金流
    investing_cashflow DOUBLE,      -- 投资活动现金流
    financing_cashflow DOUBLE,      -- 筹资活动现金流
    free_cashflow DOUBLE,           -- 自由现金流
    
    -- 盈利指标
    roe DOUBLE,                     -- 净资产收益率
    roa DOUBLE,                     -- 总资产收益率
    eps DOUBLE,                     -- 每股收益
    bps DOUBLE,                     -- 每股净资产
    
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, report_date)
);

-- 4. 估值数据表
CREATE TABLE securities_valuation (
    symbol VARCHAR NOT NULL,        -- 证券代码
    date DATE NOT NULL,             -- 日期
    
    pe_ratio DOUBLE,                -- 市盈率
    pe_ratio_ttm DOUBLE,            -- 滚动市盈率
    pb_ratio DOUBLE,                -- 市净率
    ps_ratio DOUBLE,                -- 市销率
    pcf_ratio DOUBLE,               -- 市现率
    dividend_yield DOUBLE,          -- 股息率
    
    -- 估值分位数
    pe_percentile DOUBLE,           -- PE历史分位
    pb_percentile DOUBLE,           -- PB历史分位
    
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 5. 股东数据表
CREATE TABLE securities_shareholder (
    symbol VARCHAR NOT NULL,        -- 证券代码
    report_date DATE NOT NULL,      -- 报告期
    
    -- 股东人数
    shareholder_count BIGINT,       -- 股东人数
    shareholder_count_change BIGINT, -- 股东人数变化
    shareholder_count_change_pct DOUBLE, -- 变化比例
    
    -- 十大股东
    top10_holders TEXT,              -- 十大股东JSON
    
    -- 机构持股
    institutional_holding_pct DOUBLE, -- 机构持股比例
    institutional_count INT,        -- 机构数量
    
    -- 控股股东
    controlling_shareholder VARCHAR, -- 控股股东
    actual_controller VARCHAR,      -- 实际控制人
    
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, report_date)
);

-- 6. 分红数据表
CREATE TABLE securities_dividend (
    symbol VARCHAR NOT NULL,        -- 证券代码
    dividend_date DATE NOT NULL,    -- 分红日期
    ex_date DATE,                   -- 除权除息日
    
    -- 分红方案
    dividend_per_share DOUBLE,      -- 每股派息
    bonus_shares DOUBLE,            -- 每股送股
    transfer_shares DOUBLE,         -- 每股转增
    
    -- 历史分红
    dividend_yield DOUBLE,          -- 股息率
    payout_ratio DOUBLE,            -- 派息率
    consecutive_years INT,          -- 连续分红年数
    
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, dividend_date)
);

-- 7. 龙虎榜数据表
CREATE TABLE securities_dragon_tiger (
    symbol VARCHAR NOT NULL,        -- 证券代码
    date DATE NOT NULL,             -- 日期
    
    -- 龙虎榜信息
    reason VARCHAR,                 -- 上榜原因
    net_buy_amount DOUBLE,          -- 净买入金额
    buy_amount DOUBLE,              -- 买入总额
    sell_amount DOUBLE,             -- 卖出总额
    
    -- 机构席位
    institutional_buy DOUBLE,       -- 机构买入
    institutional_sell DOUBLE,      -- 机构卖出
    
    -- 营业部席位
    seat_data TEXT,                 -- 席位数据JSON
    
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 8. 大宗交易数据表
CREATE TABLE securities_block_trade (
    symbol VARCHAR NOT NULL,        -- 证券代码
    date DATE NOT NULL,             -- 日期
    
    trade_price DOUBLE,             -- 成交价格
    trade_volume BIGINT,            -- 成交数量
    trade_amount DOUBLE,            -- 成交金额
    premium_rate DOUBLE,            -- 溢折价率
    
    -- 买卖方
    buyer_name VARCHAR,             -- 买方营业部
    seller_name VARCHAR,            -- 卖方营业部
    
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 9. 融资融券数据表
CREATE TABLE securities_margin_trading (
    symbol VARCHAR NOT NULL,        -- 证券代码
    date DATE NOT NULL,             -- 日期
    
    -- 融资
    margin_buy_balance DOUBLE,      -- 融资余额
    margin_buy_amount DOUBLE,       -- 融资买入额
    margin_buy_repay DOUBLE,        -- 融资偿还额
    
    -- 融券
    short_sell_balance DOUBLE,      -- 融券余额
    short_sell_volume BIGINT,       -- 融券余量
    short_sell_amount DOUBLE,       -- 融券卖出额
    short_sell_repay DOUBLE,        -- 融券偿还额
    
    -- 合计
    total_balance DOUBLE,           -- 融资融券余额
    
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 10. 北向资金数据表
CREATE TABLE securities_northbound (
    symbol VARCHAR NOT NULL,        -- 证券代码
    date DATE NOT NULL,             -- 日期
    
    -- 持股信息
    share_holding BIGINT,           -- 持股数量
    market_value DOUBLE,            -- 持股市值
    holding_pct DOUBLE,             -- 持股比例
    
    -- 变动信息
    share_change BIGINT,            -- 持股变化
    market_value_change DOUBLE,     -- 市值变化
    
    -- 净买入
    net_buy_amount DOUBLE,          -- 净买入金额
    
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 11. 行业数据表
CREATE TABLE securities_industry (
    symbol VARCHAR NOT NULL,        -- 证券代码
    
    industry_code VARCHAR,          -- 行业代码
    industry_name VARCHAR,          -- 行业名称
    industry_rank INT,              -- 行业排名
    
    -- 行业估值
    industry_pe DOUBLE,             -- 行业平均PE
    industry_pb DOUBLE,             -- 行业平均PB
    
    -- 行业排名
    pe_rank INT,                    -- PE排名
    pb_rank INT,                    -- PB排名
    roe_rank INT,                   -- ROE排名
    
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (symbol)
);

-- 12. 数据更新日志表
    data_source VARCHAR,
    update_time TIMESTAMP,
    PRIMARY KEY (title, publish_date)
);

-- 14. 数据更新日志表（与期货共用）
-- 见 futures_data_routing_design.md

-- 15. 交易日历表（与期货共用）
-- 见 futures_data_routing_design.md
```

### 3.2 索引设计

```sql
-- K线数据索引
CREATE INDEX idx_sec_kline_symbol ON securities_kline(symbol);
CREATE INDEX idx_sec_kline_date ON securities_kline(date);
CREATE INDEX idx_sec_kline_symbol_date ON securities_kline(symbol, date);

-- 技术指标索引
CREATE INDEX idx_sec_indicator_symbol ON securities_indicators(symbol);
CREATE INDEX idx_sec_indicator_date ON securities_indicators(date);

-- 财务数据索引
CREATE INDEX idx_sec_financial_symbol ON securities_financial(symbol);
CREATE INDEX idx_sec_financial_date ON securities_financial(report_date);

-- 估值数据索引
CREATE INDEX idx_sec_valuation_symbol ON securities_valuation(symbol);
CREATE INDEX idx_sec_valuation_date ON securities_valuation(date);

-- 北向资金索引
CREATE INDEX idx_sec_northbound_symbol ON securities_northbound(symbol);
CREATE INDEX idx_sec_northbound_date ON securities_northbound(date);
```

---

## 四、定时更新机制

### 4.1 更新时间表

| 更新时间 | 数据类型 | 说明 |
|----------|----------|------|
| **15:30** | K线数据 | 日线收盘数据 |
| **15:30** | 技术指标 | 通达信MCP获取 |
| **15:30** | 实时行情 | 收盘行情 |
| **15:30** | 龙虎榜 | 当日数据 |
| **15:30** | 大宗交易 | 当日数据 |
| **15:30** | 融资融券 | 当日数据 |
| **15:30** | 北向资金 | 当日数据 |
| **18:00** | 财务数据 | 季报/年报更新 |
| **18:00** | 股东数据 | 季报/年报更新 |
| **18:00** | 分红数据 | 分红季节更新 |
| **20:30** | 宏观数据 | 更新最新宏观指标 |
| **20:30** | 研报数据 | 获取最新研报 |
| **次日08:30** | 失败重试 | 重试前一日失败的数据 |

---

## 五、技术指标获取流程

```python
class SecuritiesIndicatorRouter:
    """证券技术指标数据路由"""
    
    def get_indicators(self, symbol: str, date: str) -> dict:
        """
        获取技术指标（通达信MCP优先）
        
        优先级：
        1. 通达信MCP（实时计算）
        2. 数据库缓存
        3. 本地计算
        """
        # 1. 从通达信MCP获取
        try:
            indicators = self._get_from_tdx_mcp(symbol)
            if indicators:
                self._save_to_db(symbol, date, indicators, source="tdx_mcp")
                return indicators
        except Exception as e:
            logger.warning(f"通达信MCP获取{symbol}技术指标失败: {e}")
        
        # 2. 从数据库缓存获取
        cached = self._get_from_db(symbol, date)
        if cached:
            return cached
        
        # 3. 本地计算
        return self._calculate_locally(symbol)
    
    def _get_from_tdx_mcp(self, symbol: str) -> dict:
        """从通达信MCP获取技术指标"""
        # 调用 tdx_indicator_select
        # 解析返回的指标数据
        pass
    
    def _calculate_locally(self, symbol: str) -> dict:
        """本地计算技术指标"""
        # 获取K线数据
        # 使用numpy/pandas计算指标
        pass
```

---

*本文档由 WorkBuddy 于 2026-06-18 创建*
