# 用户手册

> Trend Scanner Agent v0.1.0 — 期货趋势跟踪决策辅助系统

---

## 这是什么？

一个帮你扫描期货市场趋势信号的工具。它自动计算 60+ 个期货品种的技术指标，发现有趋势的品种，告诉你方向、仓位和止损位。

**它不自动下单。** 最终决策权在你手里。

**独立策略模块**：系统还包含 Carry 策略（期限结构套利），与趋势跟踪策略并行运行。

---

## 安装（3 步）

```bash
# 1. 克隆项目
git clone https://github.com/CTAAgents/QuantNova.git
cd QuantNova

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 TqSdk 账号（期货数据源）
# 设置环境变量 TQ_USER 和 TQ_PASSWORD
# 或在 config/config.json 中配置
```

---

## 日常使用（3 个命令）

### 1. 扫描行情（每天必做）

```bash
python tools/scan_opportunities.py --output text --save
```

输出示例：
```
扫描完成: 60 个品种
发现信号: 1 个
------------------------------------------------------------
  SC                   SHORT    MEDIUM   ER=0.54 TSI=-23.5 R²=0.72
    原因: TSI=-23.5 或 R²=0.72 [mode=or, 满足2/4项]
```

**怎么看**：
- `SC SHORT` = 原油有做空信号
- `MEDIUM` = 信号强度中等
- `ER=0.54` = 效率比率（>0.6 为强趋势）
- `TSI=-23.5` = 趋势强度指标（负值=下跌趋势）
- `无信号` = 当前没有明显的趋势品种

### 2. 评估因子（每周一次）

```bash
python tools/scan_opportunities.py --evaluate-factors
```

输出示例：
```
--- 淘汰 (6 个) ---
  momentum_20d    ICIR=-0.24  t=-1.82  IC>0=44.6%
  rsi_14d         ICIR=-0.30  t=-2.37  IC>0=38.1%
```

**怎么看**：
- `ICIR` = 因子预测力（>1.0 有效，<0.5 无效）
- `IC>0` = 因子方向一致性（>55% 为好）
- `淘汰` = 这个因子在期货市场没用

### 3. 因子进化（研究时用）

```bash
python tools/scan_opportunities.py --evolve --evolve-rounds 5
```

自动尝试不同因子组合，找到有效的留下，没用的淘汰。

---

## 进阶功能

### 参数优化

```bash
# 优化 RSI/动量/波动率等因子的参数
python tools/scan_opportunities.py --optimize-params --opt-trials 50
```

### 策略健康检查

```bash
# 检查策略是否健康（需要有交易历史）
python tools/scan_opportunities.py --health-check

# 检查是否过拟合
python tools/scan_opportunities.py --overfitting-check
```

### 从研报加载因子

```bash
# 把研报中的因子想法导入系统
python tools/scan_opportunities.py --evolve --load-report report.txt
```

### 套利分析（v0.1.0 新增）

```bash
# 扫描套利机会（跨期/跨品种价差）
python tools/scan_opportunities.py --arbitrage
```

**支持的套利组合**：
- 螺纹钢-铁矿石（RB-I）
- 焦炭-焦煤（J-JM）
- 热卷-螺纹钢（HC-RB）
- 铜-铝（CU-AL）
- 原油-燃料油（SC-FU）

### Reasoner 深度分析

```bash
# 使用 LLM 进行深度分析
python tools/scan_opportunities.py --reasoner
```

### VGRSI 因子（可见图技术指标）

基于可见图的技术指标，捕捉价格序列的拓扑结构特征。

```bash
# 添加 VGRSI 因子到种子因子池
python tools/add_vgrsi_factor.py
```

**VGRSI 与传统 RSI 的区别**：
- 传统 RSI：基于价格变化的统计（涨跌幅）
- VGRSI：基于价格点之间的几何可见关系（拓扑结构）

**两种模式**：
- A0（均值聚合）：捕捉趋势持续性
- A1（比率聚合）：捕捉突破脉冲

### Walk-Forward 验证

滚动前向优化验证，防止参数过拟合。

```bash
# 在因子进化中启用 Walk-Forward 验证
python tools/scan_opportunities.py --evolve --walk-forward
```

**验证标准**：
- 最小交易次数：5 次
- 最小夏普比率：0.5
- 最大回撤：20%
- IS/OOS 一致性：OOS Sharpe >= IS Sharpe * 50%

### 数据同步

```bash
# 同步所有品种数据到本地（首次使用必须执行）
python tools/sync_data.py sync --days 120

# 查看数据状态
python tools/sync_data.py stats
```

---

## 看懂输出

### 扫描结果字段

| 字段 | 含义 | 好的值 |
|------|------|--------|
| ER | 效率比率（趋势的"纯度"） | >0.6 |
| TSI | 趋势强度指标 | 绝对值 >20 |
| R² | 线性拟合度（趋势的"稳定性"） | >0.4 |
| ADX | 平均趋向指数 | >25 = 有趋势 |
| RSI | 相对强弱指标 | <30 超卖，>70 超买 |
| Hurst | 赫斯特指数 | >0.5 = 趋势，<0.5 = 均值回归 |

### 信号强度

| 强度 | 含义 | 建议 |
|------|------|------|
| STRONG | 4/4 指标达标 | 可重点关注 |
| MEDIUM | 2-3/4 指标达标 | 观察确认 |
| WEAK | 1/4 指标达标 | 不建议操作 |

### 门控决策（因子评估）

| 决策 | 含义 | ICIR 阈值 |
|------|------|----------|
| 晋升 | 因子有效，纳入因子池 | >= 1.0 |
| 观察 | 数据不足或效果不确定 | 0.5 ~ 1.0 |
| 淘汰 | 因子无效 | < 0.5 |

---

## 配置文件

### config/config.json

```json
{
  "scanner": {
    "symbols": ["RB", "I", "J", "JM", "CU", "NI", "SC"],
    "filter_mode": "or",
    "er_min": 0.6,
    "tsi_min": 20,
    "r2_min": 0.4
  }
}
```

- `symbols`：要扫描的品种列表（不设置则扫描全部非僵尸品种）
- `filter_mode`：`or` = 任一条件触发，`and` = 全部条件满足
- `er_min`：效率比率最低阈值

---

## 常见问题

### Q: 扫描结果全是"无信号"？

A: 正常。期货市场大部分时间没有强趋势。无信号时不要强行交易。

### Q: TqSdk 连接超时？

A: 检查：
1. 环境变量 `TQ_USER` 和 `TQ_PASSWORD` 是否设置
2. 是否在交易时间（盘前/收盘后数据可能延迟）
3. 网络是否通畅

### Q: 本地数据为空？

A: 首次使用需要同步数据：
```bash
python tools/sync_data.py sync --days 120
```

### Q: 因子评估全是"淘汰"？

A: 正常。简单因子在期货市场预测力很弱。这正是需要因子进化引擎的原因。

### Q: 怎么添加自己的因子？

A: 编辑 `data/seed_factors.json`，添加因子代码：
```json
{
  "name": "my_factor",
  "code": "def factor(df):\n    return df['close'].pct_change(10).fillna(0)",
  "logic": "10日动量",
  "economic_rationale": "趋势跟踪",
  "source": "manual"
}
```

---

## 文件说明

| 文件/目录 | 用途 |
|-----------|------|
| `tools/scan_opportunities.py` | 主入口（扫描/评估/进化） |
| `tools/sync_data.py` | 数据同步 |
| `tools/heartbeat.py` | 心跳监控 |
| `config/config.json` | 配置文件 |
| `data/latest_scan.json` | 最新扫描结果 |
| `data/market.db` | K线数据库（DuckDB） |
| `data/meta.db` | 元数据库（SQLite） |
| `README.md` | 完整技术文档 |
| `docs/` | 设计文档和方案 |

---

## 完整技术文档

如需了解系统架构、模块清单、工作流细节，请查看 [README.md](../README.md)。
