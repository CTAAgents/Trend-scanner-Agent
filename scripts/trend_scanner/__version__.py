"""
版本管理模块 — 唯一版本号定义

本文件是版本号的唯一定义位置（Single Source of Truth）。
其他文件应通过 `from trend_scanner.__version__ import __version__` 获取版本号。

使用语义化版本号（Semantic Versioning 2.0.0）：
- MAJOR: 不兼容的 API 变更
- MINOR: 向后兼容的功能新增
- PATCH: 向后兼容的问题修复

版本历史：
- v0.1.0: 新架构版（v6.1.0 重置）— FinClaw整合+统一数据路由+知识锚点+分级输出+套利分析
"""

__version__ = "0.1.0"
__version_info__ = tuple(int(x) for x in __version__.split("."))

# 版本元数据
VERSION_METADATA = {
    "major": __version_info__[0],
    "minor": __version_info__[1],
    "patch": __version_info__[2],
    "release": "dev",  # 开发阶段
    "python_requires": ">=3.10",
}

# 版本历史（合并精简版）
VERSION_HISTORY = [
    {
        "version": "0.1.0",
        "date": "2026-06-17",
        "summary": "新架构版 — FinClaw整合 + 统一数据路由 + 知识锚点 + 分级输出 + 套利分析",
        "changes": [
            "统一数据路由层（UnifiedDataRouter，9种数据类型路由，自动Fallback）",
            "知识锚点体系（KnowledgeAnchorManager，13个默认锚点，6个维度）",
            "分级输出机制（TieredOutputFormatter，formal/standard/brief三级）",
            "套利分析模块（ArbitrageAnalyzer，12个预定义价差对，Z-Score信号）",
            "补充分析维度：龙虎榜/保证金/宏观经济/交割数据",
            "数据源扩展：PytdxSource(通达信直连) + AkShareSource(基差/季节性)",
            "数据时效性检查机制（fresh/stale/critical三级）",
            "远程数据自动回写本地DuckDB缓存",
            "孤立模块集成：6个模块接入核心系统",
            "配置驱动路由优先级（config.json data_routing段）",
        ],
    },
    {
        "version": "0.0.0",
        "date": "2026-05-15 ~ 2026-06-16",
        "summary": "前序开发（v1.0~v6.0，版本号已重置）",
        "changes": [
            "推理优先架构（TradingAssistant + LLM推理引擎 + 经验记忆池）",
            "机制门思想（分层机制检测 + 选择性更新 + 策略向量化）",
            "五路径框架（叙事/规则分离、轨迹记录、策略混合、辩论纠偏、反身性）",
            "闭环迭代因子进化引擎（Generate→Eval→Gate→Memory）",
            "截面IC/ICIR评估 + 贝叶斯参数优化 + 多因子组合",
            "Reasoner Agent深度分析 + 持仓健康度评估",
            "五维度筛选评分（Trend/Momentum/Volume/Volatility/Channel）",
            "VGRSI可见图因子 + Walk-Forward验证 + 波动幅度止损锚点",
            "475个测试全部通过",
        ],
    },
]


def get_version() -> str:
    """获取版本号字符串"""
    return __version__


def get_version_info() -> tuple:
    """获取版本号元组"""
    return __version_info__


def get_version_metadata() -> dict:
    """获取版本元数据"""
    return VERSION_METADATA.copy()


def get_version_history() -> list:
    """获取版本历史"""
    return VERSION_HISTORY.copy()


def bump_version(level: str = "patch") -> str:
    """
    升级版本号

    参数:
        level: 升级级别 (major/minor/patch)

    返回:
        新版本号
    """
    major, minor, patch = __version_info__

    if level == "major":
        major += 1
        minor = 0
        patch = 0
    elif level == "minor":
        minor += 1
        patch = 0
    elif level == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid level: {level}. Must be major/minor/patch")

    return f"{major}.{minor}.{patch}"


def format_version(prefix: str = "v") -> str:
    """格式化版本号"""
    return f"{prefix}{__version__}"


def check_compatibility(required_version: str) -> bool:
    """
    检查版本兼容性

    参数:
        required_version: 要求的最低版本

    返回:
        是否兼容
    """
    required = tuple(int(x) for x in required_version.split("."))
    current = __version_info__

    # 比较版本号
    for c, r in zip(current, required):
        if c > r:
            return True
        elif c < r:
            return False

    return True  # 版本相同


if __name__ == "__main__":
    print(f"Version: {format_version()}")
    print(f"Version Info: {get_version_info()}")
    print(f"Metadata: {get_version_metadata()}")
    print(f"\nVersion History:")
    for v in get_version_history():
        print(f"  {v['version']} ({v['date']}):")
        for change in v["changes"]:
            print(f"    - {change}")
