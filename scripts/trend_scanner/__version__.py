"""
版本管理模块

使用语义化版本号（Semantic Versioning）：
- MAJOR.MINOR.PATCH
- MAJOR: 不兼容的 API 变更
- MINOR: 向后兼容的功能性新增
- PATCH: 向后兼容的问题修复

版本历史：
- v1.0.0: 初始版本
- v2.0.0: 自适应系统
- v3.0.0: 推理优先架构
- v3.1.0: 机制门思想引入
- v3.2.0: 五路径框架实现
- v3.2.1: 控制变量隔离
- v3.2.2: 分歧度和条件层级记录
- v5.0.0: 闭环迭代因子进化引擎
- v6.0.0: Reasoner Agent 深度分析 + 持仓健康度评估
- v6.1.0: FinClaw整合Phase 1-5 + 统一数据路由 + 知识锚点 + 分级输出 + 套利分析
"""

__version__ = "6.1.0"
__version_info__ = tuple(int(x) for x in __version__.split("."))

# 版本元数据
VERSION_METADATA = {
    "major": __version_info__[0],
    "minor": __version_info__[1],
    "patch": __version_info__[2],
    "release": "stable",
    "python_requires": ">=3.10",
}

# 版本历史
VERSION_HISTORY = [
    {
        "version": "6.1.0",
        "date": "2026-06-17",
        "changes": [
            "FinClaw整合Phase 1-5全部完成",
            "统一数据路由层（UnifiedDataRouter，9种数据类型路由）",
            "知识锚点体系（KnowledgeAnchorManager，13个默认锚点，6个维度）",
            "分级输出机制（TieredOutputFormatter，formal/standard/brief三级）",
            "套利分析模块（ArbitrageAnalyzer，12个预定义价差对）",
            "补充缺失分析维度：龙虎榜/保证金/宏观/交割",
            "PytdxSource通达信直连 + AkShareSource辅助数据源",
            "数据时效性检查机制",
            "远程数据自动回写本地DuckDB缓存",
            "孤立模块集成：知识锚点→推理引擎，分级输出→Reasoner，套利→Scanner，信念传播→Debater，RL接口→Evolver",
            "配置驱动路由优先级（config.json data_routing段）",
            "475个测试全部通过",
        ],
    },
    {
        "version": "6.0.0",
        "date": "2026-06-16",
        "changes": [
            "Reasoner Agent 深度分析（LLM推理→决策简报，输出置信度评估）",
            "持仓健康度评估（PositionHealthChecker，多维度评估持仓状态）",
            "技术面评估（趋势强度、动量、波动率）",
            "资金面评估（盈亏、回撤、持仓时间）",
            "市场面评估（宏观状态、相关性）",
            "LLM推理评估（Reasoner Agent深度分析）",
            "持仓配置文件（config/positions.json）",
            "DuckDB K线查询优化（获取最近N条记录而非最近N天）",
            "LLM提供者集成（WorkBuddy内置LLM，OpenAI兼容接口）",
            "集成到scan_opportunities.py（--position-health参数）",
        ],
    },
    {
        "version": "5.0.0",
        "date": "2026-06-16",
        "changes": [
            "闭环迭代因子进化引擎（Generate→Eval→Gate→Memory）",
            "截面 IC/ICIR 因子评估体系（FactorEvaluator）",
            "因子代码安全执行引擎（FactorExecutor）",
            "三元门控决策器（FactorGate）",
            "贝叶斯参数优化器（FactorParamOptimizer，基于 Optuna）",
            "种子因子池（SeedFactorPool，含研报知识注入）",
            "多因子组合模型（MultiFactorModel，基于 LightGBM）",
            "失败经验库（FactorExperienceDB，轨迹感知优化）",
            "TqSdk 数据源优化（deadline 机制，批量行情分批处理）",
            "数据源健康检查（DataSourceFactory.check_health）",
            "全品种扫描扩展（60 个非僵尸品种）",
            "全部 73 个模块集成到核心系统",
            "58 个单元测试全部通过",
        ],
    },
    {
        "version": "3.2.2",
        "date": "2026-06-14",
        "changes": [
            "新增分歧度和条件层级记录",
            "提升测试覆盖率至80%",
            "新增1054个测试用例",
        ],
    },
    {
        "version": "3.2.1",
        "date": "2026-06-14",
        "changes": [
            "新增控制变量隔离模块",
            "显式标记固定层和LLM影响层",
            "量化LLM边际贡献",
        ],
    },
    {
        "version": "3.2.0",
        "date": "2026-06-14",
        "changes": [
            "五路径框架全部完成",
            "路径①: 叙事/规则分离",
            "路径②: 修正轨迹记录",
            "路径③: 策略混合报告",
            "路径④: 辩论纠偏器",
            "路径⑤: 反身性框架注入",
            "核心理念更新为'LLM为眼，规则为手'",
        ],
    },
    {
        "version": "3.1.0",
        "date": "2026-06-14",
        "changes": [
            "引入机制门思想",
            "分层机制检测",
            "选择性更新机制",
            "策略向量化增强",
        ],
    },
    {
        "version": "3.0.0",
        "date": "2026-06-14",
        "changes": [
            "推理优先架构重写",
            "TradingAssistant 主协调器",
            "LLM推理引擎",
            "经验记忆池",
            "24个Python模块",
        ],
    },
    {
        "version": "2.0.0",
        "date": "2026-06-01",
        "changes": [
            "自适应系统",
            "AdaptiveTrendSystem",
            "波动率权重切换",
            "维度胜率自适应",
        ],
    },
    {
        "version": "1.0.0",
        "date": "2026-05-15",
        "changes": [
            "初始版本",
            "基础趋势跟踪",
            "技术指标计算",
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
