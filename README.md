# Trend Scanner Agent

> 推理重于规则的期货趋势跟踪决策辅助系统 v4.0

**完整文档请查看 [SKILL.md](SKILL.md)**

## 一句话概括

五层管线（Scanner → Reasoner → Debater → Monitor → Evolver），纯 Python 脚本做计算，LLM Agent 做推理，每日自动扫描 17 个期货品种，只在有信号时触发推理，输出决策简报供人参考。

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
