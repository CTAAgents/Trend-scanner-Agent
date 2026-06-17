from setuptools import setup, find_packages
import re
from pathlib import Path

# 从 __version__.py 读取版本号（Single Source of Truth）
def get_version():
    version_file = Path(__file__).parent / "scripts" / "trend_scanner" / "__version__.py"
    content = version_file.read_text(encoding='utf-8')
    match = re.search(r'__version__ = "([^"]+)"', content)
    if match:
        return match.group(1)
    raise RuntimeError("无法从 __version__.py 读取版本号")

setup(
    name="trend-scanner-agent",
    version=get_version(),
    description="推理重于规则的期货趋势跟踪决策辅助系统（FinClaw整合+统一数据路由+知识锚点+分级输出+套利分析）",
    author="CTAAgents",
    python_requires=">=3.12",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "scikit-learn>=1.2.0",
        "tqsdk>=3.9.0",
        "ta-lib>=0.4.28",
        "matplotlib>=3.7.0",
        "requests>=2.28.0",
        "optuna>=4.0.0",
        "lightgbm>=4.0.0",
        "duckdb>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "trend-scanner=tools.scan_opportunities:main",
            "trend-heartbeat=tools.heartbeat:main",
            "trend-monitor=tools.monitor_positions:main",
            "trend-reasoner=tools.run_reasoner:main",
            "trend-debater=tools.run_debater:main",
            "trend-evolver=tools.run_evolver:main",
            "trend-orchestrator=tools.orchestrator:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
)
