# Trend Scanner Agent v5.0

> 推理重于规则的期货趋势跟踪决策辅助系统

**新用户请查看 [用户手册](docs/USER_GUIDE.md) | 开发者请查看 [技术文档](SKILL.md)**

## 一句话概括

闭环迭代因子进化引擎 + 八层管线架构，TqSdk 拉取数据写入本地 DuckDB，纯 Python 做计算，LLM 做推理，每日自动扫描 60+ 非僵尸期货品种，信号输出附带仓位建议和止损价位。

## 核心理念

**以人为本，推理为魂，规则为果。** 所有"规则"均由推理层根据当前市场状态动态生成。

## 快速开始

```bash
git clone https://github.com/CTAAgents/Trend-scanner-Agent.git
cd Trend-scanner-Agent
pip install -r requirements.txt

# 数据同步
python tools/sync_data.py sync --days 120

# 运行扫描
python tools/scan_opportunities.py --output text --save

# 因子评估
python tools/scan_opportunities.py --evaluate-factors

# 因子进化
python tools/scan_opportunities.py --evolve --evolve-rounds 5
```

## v5.0 新特性

- **闭环因子进化**: Generate → Eval → Gate → Memory 自动迭代
- **截面 IC/ICIR 评估**: 多品种截面预测能力量化
- **贝叶斯参数优化**: Optuna TPE 自动搜索最优参数
- **多因子组合**: LightGBM 非线性因子组合
- **种子因子池**: 研报知识注入 + 预置种子因子
- **失败经验库**: 从失败中学习，避免重复错误
- **全品种扫描**: 60+ 非僵尸品种，数据源健康检查

## 系统架构

```
数据层 → 感知层 → 因子进化层 → 推理层 → 执行层 → 进化层 → 记忆层
```

## 许可证

MIT License
