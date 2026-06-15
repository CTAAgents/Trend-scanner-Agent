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
"""

__version__ = "3.2.2"
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
