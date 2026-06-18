"""
因子验证模块

验证因子代码的质量和有效性，包括：
1. 语法检查
2. 结构检查
3. 未来数据检查
4. 最佳实践检查
5. 性能指标计算

版本：v1.0
创建日期：2026-06-15
"""

import logging
import re
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    details: dict[str, Any]


class FactorValidator:
    """
    因子验证器

    验证因子代码的质量和有效性
    """

    def __init__(self):
        """初始化因子验证器"""
        logger.info("FactorValidator 初始化完成")

    def validate(self, factor_code: str) -> dict[str, Any]:
        """
        验证因子代码

        Args:
            factor_code: 因子代码

        Returns:
            dict: 验证结果
        """
        errors = []
        warnings = []
        details = {}

        # 1. 语法检查
        syntax_result = self._check_syntax(factor_code)
        if not syntax_result["is_valid"]:
            errors.extend(syntax_result["errors"])
        details["syntax"] = syntax_result

        # 2. 结构检查
        structure_result = self._check_structure(factor_code)
        if not structure_result["is_valid"]:
            errors.extend(structure_result["errors"])
        warnings.extend(structure_result.get("warnings", []))
        details["structure"] = structure_result

        # 3. 未来数据检查
        future_data_result = self._check_future_data(factor_code)
        if not future_data_result["is_valid"]:
            errors.extend(future_data_result["errors"])
        details["future_data"] = future_data_result

        # 4. 最佳实践检查
        best_practices_result = self._check_best_practices(factor_code)
        warnings.extend(best_practices_result.get("warnings", []))
        details["best_practices"] = best_practices_result

        # 5. 安全检查
        security_result = self._check_security(factor_code)
        if not security_result["is_valid"]:
            errors.extend(security_result["errors"])
        warnings.extend(security_result.get("warnings", []))
        details["security"] = security_result

        return {"is_valid": len(errors) == 0, "errors": errors, "warnings": warnings, "details": details}

    def _check_syntax(self, factor_code: str) -> dict[str, Any]:
        """
        检查代码语法

        Args:
            factor_code: 因子代码

        Returns:
            dict: 检查结果
        """
        errors = []

        try:
            compile(factor_code, "<string>", "exec")
        except SyntaxError as e:
            errors.append(f"语法错误: {e}")
        except Exception as e:
            errors.append(f"编译错误: {e}")

        return {"is_valid": len(errors) == 0, "errors": errors}

    def _check_structure(self, factor_code: str) -> dict[str, Any]:
        """
        检查代码结构

        Args:
            factor_code: 因子代码

        Returns:
            dict: 检查结果
        """
        errors = []
        warnings = []

        # 检查是否包含 factor 函数定义
        if "def factor(" not in factor_code:
            errors.append("代码中未找到 factor 函数定义")

        # 检查是否有 return 语句
        if "return " not in factor_code:
            errors.append("代码中未找到 return 语句")

        # 检查是否有 docstring
        if '"""' not in factor_code and "'''" not in factor_code:
            warnings.append("建议添加 docstring 描述因子逻辑")

        # 检查函数参数
        if "def factor(df" not in factor_code:
            warnings.append("建议 factor 函数接收 df 参数")

        # 检查是否有导入语句
        if "import pandas" not in factor_code and "import pd" not in factor_code:
            warnings.append("建议在函数内导入 pandas")

        return {"is_valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def _check_future_data(self, factor_code: str) -> dict[str, Any]:
        """
        检查是否使用未来数据

        Args:
            factor_code: 因子代码

        Returns:
            dict: 检查结果
        """
        errors = []

        # 检查是否使用了 shift(-n) 或其他未来数据模式
        future_data_patterns = [
            (r"shift\(-\d+\)", "使用了 shift(-n)，可能是未来数据"),
            (r"iloc\[\d+:\]", "使用了 iloc[n:]，可能是未来数据"),
            (r"lead\(", "使用了 lead()，可能是未来数据"),
            (r"iloc\[-\d+\]", "使用了 iloc[-n]，可能是未来数据"),
        ]

        for pattern, message in future_data_patterns:
            if re.search(pattern, factor_code):
                errors.append(f"代码可能使用了未来数据: {message}")

        return {"is_valid": len(errors) == 0, "errors": errors}

    def _check_best_practices(self, factor_code: str) -> dict[str, Any]:
        """
        检查最佳实践

        Args:
            factor_code: 因子代码

        Returns:
            dict: 检查结果
        """
        warnings = []

        # 检查是否有 NaN 处理
        if "dropna()" not in factor_code and "fillna(" not in factor_code:
            warnings.append("建议添加 NaN 值处理")

        # 检查是否有异常值处理
        if "clip(" not in factor_code and "winsorize" not in factor_code:
            warnings.append("建议添加异常值处理")

        # 检查是否有归一化
        if "max()" not in factor_code and "min()" not in factor_code and "std()" not in factor_code:
            warnings.append("建议添加归一化处理")

        # 检查是否有类型注解
        if "def factor(df: pd.DataFrame)" not in factor_code:
            warnings.append("建议添加类型注解")

        return {"warnings": warnings}

    def _check_security(self, factor_code: str) -> dict[str, Any]:
        """
        检查安全性

        Args:
            factor_code: 因子代码

        Returns:
            dict: 检查结果
        """
        errors = []
        warnings = []

        # 检查是否使用了危险函数
        dangerous_patterns = [
            (r"eval\(", "使用了 eval()，存在安全风险"),
            (r"exec\(", "使用了 exec()，存在安全风险"),
            (r"__import__", "使用了 __import__，存在安全风险"),
            (r"open\(", "使用了 open()，可能存在文件操作风险"),
            (r"os\.", "使用了 os 模块，可能存在系统操作风险"),
            (r"subprocess", "使用了 subprocess，可能存在命令执行风险"),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, factor_code):
                if "eval(" in pattern or "exec(" in pattern or "__import__" in pattern:
                    errors.append(f"安全问题: {message}")
                else:
                    warnings.append(f"安全警告: {message}")

        return {"is_valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def calculate_performance_metrics(self, factor_func, data: Any) -> dict[str, float]:
        """
        计算因子性能指标

        Args:
            factor_func: 因子函数
            data: 历史数据（pandas DataFrame）

        Returns:
            dict: 性能指标
        """
        try:
            import pandas as pd

            # 计算因子值
            factor_values = factor_func(data)

            # 计算收益率（假设使用下一期收益率）
            returns = data["close"].pct_change().shift(-1)

            # 对齐数据
            aligned_data = pd.DataFrame({"factor": factor_values, "returns": returns}).dropna()

            if len(aligned_data) < 10:
                return {"error": "数据不足"}

            # 计算 IC (Information Coefficient)
            ic = aligned_data["factor"].corr(aligned_data["returns"])

            # 计算 ICIR (Information Coefficient Information Ratio)
            # 滚动计算 IC
            rolling_ic = aligned_data["factor"].rolling(20).corr(aligned_data["returns"])
            icir = rolling_ic.mean() / rolling_ic.std() if rolling_ic.std() > 0 else 0

            # 计算稳定性
            stability = 1 - (rolling_ic.std() / abs(rolling_ic.mean())) if abs(rolling_ic.mean()) > 0 else 0

            # 计算因子自相关性
            autocorrelation = aligned_data["factor"].autocorr()

            # 计算因子覆盖率
            coverage = len(aligned_data) / len(data)

            return {
                "ic": float(ic),
                "icir": float(icir),
                "stability": float(stability),
                "autocorrelation": float(autocorrelation),
                "coverage": float(coverage),
                "sample_count": len(aligned_data),
            }

        except Exception as e:
            logger.error(f"计算因子性能指标失败: {e}")
            return {"error": str(e)}

    def validate_and_score(self, factor_code: str, data: Any = None) -> dict[str, Any]:
        """
        验证并评分因子代码

        Args:
            factor_code: 因子代码
            data: 历史数据（可选）

        Returns:
            dict: 验证和评分结果
        """
        # 基础验证
        validation_result = self.validate(factor_code)

        # 如果数据可用，计算性能指标
        performance_metrics = {}
        if data is not None:
            try:
                # 动态执行因子代码
                exec_globals = {}
                exec(factor_code, exec_globals)
                factor_func = exec_globals.get("factor")

                if factor_func:
                    performance_metrics = self.calculate_performance_metrics(factor_func, data)
            except Exception as e:
                logger.error(f"执行因子代码失败: {e}")
                performance_metrics = {"error": str(e)}

        # 计算综合评分
        score = self._calculate_score(validation_result, performance_metrics)

        return {"validation": validation_result, "performance": performance_metrics, "score": score}

    def _calculate_score(self, validation_result: dict[str, Any], performance_metrics: dict[str, float]) -> float:
        """
        计算综合评分

        Args:
            validation_result: 验证结果
            performance_metrics: 性能指标

        Returns:
            float: 综合评分 (0-100)
        """
        score = 100.0

        # 根据错误扣分
        errors = validation_result.get("errors", [])
        score -= len(errors) * 20

        # 根据警告扣分
        warnings = validation_result.get("warnings", [])
        score -= len(warnings) * 5

        # 根据性能指标调整分数
        if "ic" in performance_metrics:
            ic = abs(performance_metrics["ic"])
            if ic > 0.05:
                score += 10
            elif ic > 0.03:
                score += 5
            elif ic < 0.01:
                score -= 10

        if "icir" in performance_metrics:
            icir = abs(performance_metrics["icir"])
            if icir > 1.0:
                score += 10
            elif icir > 0.5:
                score += 5
            elif icir < 0.2:
                score -= 10

        # 确保分数在 0-100 范围内
        score = max(0, min(100, score))

        return score


class FactorCodeAnalyzer:
    """
    因子代码分析器

    分析因子代码的结构和逻辑
    """

    def __init__(self):
        """初始化因子代码分析器"""
        logger.info("FactorCodeAnalyzer 初始化完成")

    def analyze_structure(self, factor_code: str) -> dict[str, Any]:
        """
        分析因子代码结构

        Args:
            factor_code: 因子代码

        Returns:
            dict: 结构分析结果
        """
        analysis = {
            "has_docstring": self._has_docstring(factor_code),
            "has_type_annotations": self._has_type_annotations(factor_code),
            "has_imports": self._has_imports(factor_code),
            "function_count": self._count_functions(factor_code),
            "line_count": len(factor_code.split("\n")),
            "complexity": self._estimate_complexity(factor_code),
        }

        return analysis

    def _has_docstring(self, code: str) -> bool:
        """检查是否有 docstring"""
        return '"""' in code or "'''" in code

    def _has_type_annotations(self, code: str) -> bool:
        """检查是否有类型注解"""
        return "def factor(df: pd.DataFrame)" in code

    def _has_imports(self, code: str) -> bool:
        """检查是否有导入语句"""
        return "import " in code

    def _count_functions(self, code: str) -> int:
        """统计函数数量"""
        return len(re.findall(r"def \w+", code))

    def _estimate_complexity(self, code: str) -> str:
        """
        估算代码复杂度

        Args:
            code: 代码

        Returns:
            str: 复杂度等级 (low/medium/high)
        """
        lines = code.split("\n")
        line_count = len(lines)

        # 统计控制流语句
        control_flow_count = 0
        for line in lines:
            if any(keyword in line for keyword in ["if ", "for ", "while ", "try:", "except:"]):
                control_flow_count += 1

        if line_count < 20 and control_flow_count < 3:
            return "low"
        elif line_count < 50 and control_flow_count < 10:
            return "medium"
        else:
            return "high"

    def extract_factor_info(self, factor_code: str) -> dict[str, str]:
        """
        提取因子信息

        Args:
            factor_code: 因子代码

        Returns:
            dict: 因子信息
        """
        info = {"name": "", "description": "", "logic": ""}

        # 从 docstring 中提取信息
        docstring_match = re.search(r'"""(.*?)"""', factor_code, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1)

            # 提取因子名称
            name_match = re.search(r"因子名称[：:]\s*(.+)", docstring)
            if name_match:
                info["name"] = name_match.group(1).strip()

            # 提取因子描述
            desc_match = re.search(r"因子描述[：:]\s*(.+)", docstring)
            if desc_match:
                info["description"] = desc_match.group(1).strip()

            # 提取逻辑
            logic_match = re.search(r"逻辑[：:]\s*(.+)", docstring)
            if logic_match:
                info["logic"] = logic_match.group(1).strip()

        return info


# 示例用法
if __name__ == "__main__":
    # 测试因子验证器
    validator = FactorValidator()

    # 测试代码
    test_code = '''
def factor(df: pd.DataFrame) -> pd.Series:
    """
    因子名称：动量突破因子
    因子描述：结合价格动量和成交量放大，捕捉突破信号
    逻辑：5日收益率 * 成交量比率
    
    Args:
        df: 包含 OHLCV 数据的 DataFrame
        
    Returns:
        pd.Series: 因子值，index 与输入 df 相同
    """
    import pandas as pd
    
    # 计算5日收益率
    returns = df['close'].pct_change(5)
    
    # 计算成交量比率
    volume_ratio = df['volume'] / df['volume'].rolling(20).mean()
    
    # 计算因子值
    factor_value = returns * volume_ratio
    
    # 归一化到 [-1, 1] 范围
    factor_value = factor_value / factor_value.abs().max()
    
    return factor_value
'''

    result = validator.validate(test_code)
    print("验证结果:")
    print(f"是否有效: {result['is_valid']}")
    print(f"错误: {result['errors']}")
    print(f"警告: {result['warnings']}")
