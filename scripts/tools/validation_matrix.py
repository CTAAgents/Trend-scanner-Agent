"""
ValidationMatrix — 验证矩阵路由模块 v1.0

定义改动类型 → 最低验证标准的映射，为 Reasoner Agent 提供：
1. 改动类型对应的最低验证要求查询
2. 自动路由到现有验证器（walk_forward / factor_evaluator / overfitting_auditor）
3. 红线检查（Red Flags）

设计原则：
- 不替代现有验证器，只是统一调度层
- Reasoner 在输出建议时引用此模块标注"该建议需要什么级别的验证"

使用方式：
    from validation_matrix import ValidationMatrix
    vm = ValidationMatrix()
    req = vm.get_requirement("new_entry")
    # → ValidationRequirement(minimum="focused_backtest + walk_forward", ...)
"""

from dataclasses import dataclass, field
from typing import Any


# ===================== 数据模型 =====================


@dataclass
class ValidationRequirement:
    """验证要求"""

    minimum: str  # 最低验证标准描述
    checks: list[str] = field(default_factory=list)  # 检查要点
    red_flags: list[str] = field(default_factory=list)  # 红线（一经触发需标记）
    validator: str = ""  # 推荐的验证器
    description: str = ""  # 改动类型说明


# ===================== 验证矩阵 =====================

VALIDATION_MATRIX: dict[str, ValidationRequirement] = {
    "adjust_position": ValidationRequirement(
        minimum="1 次聚焦回测 + 1 个回归测试",
        checks=["仓位限制检查", "敞口检查", "换手率检查", "止损位有效性"],
        red_flags=[
            "PnL 改善伴随换手率同步恶化且未解释",
            "敞口峰值超过历史 2 倍标准差",
        ],
        validator="walk_forward_validator",
        description="调整仓位（加减仓/止损位/止盈位）",
    ),
    "add_indicator": ValidationRequirement(
        minimum="固定 fixture 的单元测试",
        checks=["数值稳定性", "前视偏差检查", "NaN 处理", "极端值处理"],
        red_flags=[
            "存在前视偏差（使用了未来数据）",
            "存在幸存偏差（仅测试活跃品种）",
        ],
        validator="factor_evaluator",
        description="新增技术指标或因子",
    ),
    "modify_threshold": ValidationRequirement(
        minimum="聚焦回测 + 1 个回归测试",
        checks=["交易次数变化", "胜率变化", "换手率变化", "基准偏离度"],
        red_flags=[
            "仅靠单一日历区间证明有效",
            "阈值改动后性能提升在统计上不显著",
        ],
        validator="walk_forward_validator",
        description="修改信号阈值（如 ER min/TSI min/趋势强度 min）",
    ),
    "new_entry": ValidationRequirement(
        minimum="聚焦回测 + Walk-Forward 验证",
        checks=["跨周期稳定性", "样本外表现", "最大回撤控制", "Sharpe 比率"],
        red_flags=[
            "样本外表现显著劣于样本内（OOS Sharpe < IS Sharpe × 0.5）",
            "仅单边市场有效（牛市中做多策略 vs 熊市中无效）",
        ],
        validator="walk_forward_validator",
        description="新入场信号",
    ),
    "exit": ValidationRequirement(
        minimum="1 个回归测试",
        checks=["平仓后 N 日品种走势跟踪", "假退出信号率"],
        red_flags=[
            "平仓后价格继续沿原方向大幅移动（>2×ATR）",
        ],
        validator="walk_forward_validator",
        description="退出/平仓",
    ),
    "strategy_logic": ValidationRequirement(
        minimum="Walk-Forward 验证 + 蒙特卡洛模拟",
        checks=["全维度回归测试", "参数敏感度分析", "市场状态分段测试"],
        red_flags=[
            "策略逻辑在框架适配器和核心逻辑中重复",
            "参数稳定域过窄（10% 微调即失效）",
        ],
        validator="overfitting_auditor",
        description="策略逻辑变更（改变进出场规则/过滤条件）",
    ),
    "risk_parameter": ValidationRequirement(
        minimum="风险集成测试 + 聚焦回测",
        checks=["尾部损失分析", "敞口截断验证", "VaR/CVaR 变化"],
        red_flags=[
            "尾部风险显著增加而 Sharpe 持平",
            "最大回撤扩大超过 30%",
        ],
        validator="walk_forward_validator",
        description="风控参数修改（保证金比例/仓位上限/止损规则）",
    ),
}


class ValidationMatrix:
    """
    验证矩阵路由层。

    为 Reasoner Agent 提供改动类型 → 验证标准的查询接口。
    """

    def __init__(self):
        self._matrix = VALIDATION_MATRIX

    def get_requirement(self, change_type: str) -> ValidationRequirement | None:
        """
        获取改动类型对应的验证要求。

        Args:
            change_type: 改动类型（见 VALIDATION_MATRIX keys）

        Returns:
            ValidationRequirement 或 None（未知类型）
        """
        return self._matrix.get(change_type)

    def validate_route(self, change_type: str, validator_results: dict[str, Any]) -> dict[str, Any]:
        """
        根据改动类型路由到适当的验证器并检查红线。

        Args:
            change_type: 改动类型
            validator_results: {
                "walk_forward": {...},
                "factor_evaluation": {...},
                "overfitting_audit": {...}
            }

        Returns:
            {
                "passed": bool,
                "warnings": [...],
                "red_flags_triggered": [...],
                "recommended_action": str
            }
        """
        req = self.get_requirement(change_type)
        if req is None:
            return {
                "passed": False,
                "warnings": [f"未知改动类型: {change_type}"],
                "red_flags_triggered": [],
                "recommended_action": "请定义该改动类型的验证标准",
            }

        # 获取对应验证器结果
        vr = validator_results.get(req.validator, {})
        red_flags_triggered = self._check_red_flags(req.red_flags, vr)

        passed = len(red_flags_triggered) == 0

        return {
            "passed": passed,
            "warnings": vr.get("warnings", []),
            "red_flags_triggered": red_flags_triggered,
            "recommended_action": "通过验证，可以执行"
            if passed
            else f"红线触发: {', '.join(red_flags_triggered)}，建议暂停并复审",
        }

    def get_minimum_standard(self, change_type: str) -> str:
        """获取改动类型的最低验证标准描述"""
        req = self.get_requirement(change_type)
        return req.minimum if req else "未定义"

    def list_all_types(self) -> list[str]:
        """列出所有已知改动类型"""
        return list(self._matrix.keys())

    def to_reasoner_context(self, change_type: str) -> str:
        """
        生成 Reasoner 可用的验证要求上下文文本。

        用于"Step 4: Decide The Proof Up Front"阶段，
        注入到 LLM 推理提示词中。
        """
        req = self.get_requirement(change_type)
        if req is None:
            return f"改动类型 '{change_type}' 无预定义验证标准，请根据团队规范执行。"

        lines = [
            f"改动类型: {change_type} ({req.description})",
            f"最低验证标准: {req.minimum}",
            f"推荐验证器: {req.validator}",
            f"检查要点: {', '.join(req.checks)}",
        ]

        if req.red_flags:
            lines.append(f"红线: {', '.join(req.red_flags)}")

        return "\n".join(lines)

    # ===================== 内部方法 =====================

    @staticmethod
    def _check_red_flags(red_flags: list[str], validator_result: dict[str, Any]) -> list[str]:
        """
        检查验证器结果是否触发红线。

        当前为基于规则的简单检查。未来可扩展为基于 LLM 的语义匹配。
        """
        triggered = []

        # 基于 validator_result 中的 known_issues 字段
        issues = validator_result.get("known_issues", [])

        for flag in red_flags:
            for issue in issues:
                if flag.lower() in issue.lower():
                    triggered.append(flag)
                    break

        return triggered


# ===================== 便捷函数 =====================

_VALIDATION_MATRIX_INSTANCE = None


def get_validation_matrix() -> ValidationMatrix:
    """获取 ValidationMatrix 单例"""
    global _VALIDATION_MATRIX_INSTANCE
    if _VALIDATION_MATRIX_INSTANCE is None:
        _VALIDATION_MATRIX_INSTANCE = ValidationMatrix()
    return _VALIDATION_MATRIX_INSTANCE


def get_requirement(change_type: str) -> ValidationRequirement | None:
    """便捷函数：获取验证要求"""
    return get_validation_matrix().get_requirement(change_type)


def to_reasoner_context(change_type: str) -> str:
    """便捷函数：生成 Reasoner 上下文"""
    return get_validation_matrix().to_reasoner_context(change_type)
