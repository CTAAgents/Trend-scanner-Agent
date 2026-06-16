# Trend Scanner Agent

> 推理重于规则的期货趋势跟踪决策辅助系统 v4.0

**完整文档请查看 [SKILL.md](SKILL.md)**

## 一句话概括

八层管线（数据采集 → Scanner → Reasoner → Debater → 仓位管理 → 动态止损 → Monitor → Evolver），TqSdk 拉取数据写入本地 DuckDB，纯 Python 脚本做计算，LLM Agent 做推理，每日自动扫描所有非僵尸期货品种，信号输出附带仓位建议和止损价位，Evolver 阶段执行策略健康度评估和过拟合检测。

## 快速开始

```bash
git clone https://github.com/CTAAgents/Trend-scanner-Agent.git
cd Trend-scanner-Agent
pip install -r requirements.txt

# 运行扫描
python tools/scan_opportunities.py --output text --save

# 完整流程
python tools/orchestrator.py full
```

## 核心理念

**以人为本，推理为魂，规则为果。** 所有"规则"均由推理层根据当前市场状态动态生成。

## 许可证

MIT License
