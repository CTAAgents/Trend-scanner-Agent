"""
因子执行引擎模块

将因子代码（字符串）安全执行为截面因子值矩阵。
核心原则：
1. 确定性执行：相同输入 → 相同输出，无随机性
2. 沙箱隔离：因子代码在受限环境中执行，禁止危险操作
3. 批量计算：一次性对所有品种计算因子值

版本：v1.0
创建日期：2026-06-16
"""

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)

# 禁止在因子代码中使用的模块/函数
BLOCKED_MODULES = [
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "http",
    "requests",
    "urllib",
    "pathlib",
    "open",
    "exec",
    "eval",
    "__import__",
    "compile",
    "globals",
    "locals",
    "vars",
]

# 允许因子代码使用的模块
ALLOWED_MODULES = {
    "pd": pd,
    "np": np,
    "pandas": pd,
    "numpy": np,
}


class FactorExecutionError(Exception):
    """因子执行异常"""

    pass


class FactorExecutor:
    """
    因子执行引擎

    将因子代码字符串安全执行为截面因子值矩阵。

    使用方式：
        executor = FactorExecutor()
        factor_values = executor.execute(factor_code, kline_data)
        # 返回 DataFrame, index=date, columns=symbol
    """

    def __init__(self, safety_check: bool = True):
        """
        初始化执行引擎

        Args:
            safety_check: 是否启用安全检查（禁止危险操作）
        """
        self.safety_check = safety_check

    def execute(self, factor_code: str, kline_data: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
        """
        执行因子代码，计算所有品种的截面因子值

        Args:
            factor_code: 因子代码（必须定义 factor(df) 函数）
            kline_data: {symbol: DataFrame(date, open, high, low, close, volume)}

        Returns:
            DataFrame, index=date, columns=symbol, values=因子值
            失败返回 None
        """
        # 1. 安全检查
        if self.safety_check:
            issues = self._safety_check(factor_code)
            if issues:
                logger.warning(f"因子代码安全检查未通过: {issues}")
                return None

        # 2. 编译因子函数
        factor_fn = self._compile_factor(factor_code)
        if factor_fn is None:
            return None

        # 3. 对所有品种执行因子
        return self._execute_cross_section(factor_fn, kline_data)

    def execute_function(
        self, factor_fn: Callable[[pd.DataFrame], pd.Series], kline_data: dict[str, pd.DataFrame]
    ) -> pd.DataFrame | None:
        """
        直接执行因子函数（不需要编译）

        Args:
            factor_fn: 因子函数
            kline_data: {symbol: DataFrame}

        Returns:
            DataFrame, index=date, columns=symbol
        """
        return self._execute_cross_section(factor_fn, kline_data)

    def _safety_check(self, code: str) -> list[str]:
        """
        安全检查：禁止危险操作

        Args:
            code: 因子代码

        Returns:
            问题列表（空 = 通过）
        """
        import re

        issues = []

        # 检查是否使用了禁止的模块/函数（使用单词边界匹配，避免误报如 fillna 中的 os）
        for blocked in BLOCKED_MODULES:
            pattern = r"\b" + re.escape(blocked) + r"\b"
            if re.search(pattern, code):
                issues.append(f"使用了禁止的操作: {blocked}")

        # 检查是否有未来数据使用
        future_patterns = [r"shift\(-", r"iloc\[1:\]", r"lead\("]
        for pattern in future_patterns:
            if re.search(pattern, code):
                issues.append(f"可能使用了未来数据: {pattern}")

        return issues

    def _compile_factor(self, factor_code: str) -> Callable | None:
        """
        编译因子代码为可执行函数

        Args:
            factor_code: 因子代码

        Returns:
            编译后的因子函数，失败返回 None
        """
        try:
            # 构建执行环境
            exec_globals = {**ALLOWED_MODULES}
            exec_locals = {}

            # 执行代码
            exec(factor_code, exec_globals, exec_locals)

            # 查找 factor 函数
            factor_fn = exec_locals.get("factor") or exec_globals.get("factor")

            if factor_fn is None:
                logger.error("因子代码中未找到 'factor' 函数")
                return None

            if not callable(factor_fn):
                logger.error("'factor' 不是可调用对象")
                return None

            return factor_fn

        except SyntaxError as e:
            logger.error(f"因子代码语法错误: {e}")
            return None
        except Exception as e:
            logger.error(f"编译因子代码失败: {e}")
            return None

    def _execute_cross_section(self, factor_fn: Callable, kline_data: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
        """
        对所有品种执行因子，生成截面因子值矩阵

        Args:
            factor_fn: 因子函数
            kline_data: {symbol: DataFrame}

        Returns:
            DataFrame, index=date, columns=symbol
        """
        factor_dict = {}

        for symbol, df in kline_data.items():
            try:
                # 使用原始数据的索引（不归一化，保持与 evaluator 一致）
                if "date" in df.columns:
                    df = df.set_index("date")
                df = df.copy()

                # 执行因子
                values = factor_fn(df)

                if values is not None and len(values) > 0:
                    if isinstance(values, pd.Series):
                        factor_dict[symbol] = values
                    else:
                        factor_dict[symbol] = pd.Series(values, index=df.index)

            except Exception as e:
                logger.debug(f"因子在 {symbol} 上执行失败: {e}")
                continue

        if not factor_dict:
            logger.warning("因子在所有品种上执行失败")
            return None

        factor_df = pd.DataFrame(factor_dict)

        # 处理无穷大值
        factor_df = factor_df.replace([np.inf, -np.inf], np.nan)

        logger.debug(f"因子执行完成: {factor_df.shape[1]} 品种, {factor_df.shape[0]} 天")
        return factor_df

    def validate_and_execute(self, factor_code: str, kline_data: dict[str, pd.DataFrame]) -> dict[str, Any]:
        """
        验证并执行因子，返回详细结果

        Args:
            factor_code: 因子代码
            kline_data: {symbol: DataFrame}

        Returns:
            {
                'success': bool,
                'factor_values': DataFrame or None,
                'errors': List[str],
                'warnings': List[str],
                'symbol_count': int,
                'day_count': int,
            }
        """
        result = {
            "success": False,
            "factor_values": None,
            "errors": [],
            "warnings": [],
            "symbol_count": 0,
            "day_count": 0,
        }

        # 安全检查
        if self.safety_check:
            issues = self._safety_check(factor_code)
            if issues:
                result["errors"] = issues
                return result

        # 编译
        factor_fn = self._compile_factor(factor_code)
        if factor_fn is None:
            result["errors"].append("因子代码编译失败")
            return result

        # 执行
        factor_values = self._execute_cross_section(factor_fn, kline_data)
        if factor_values is None:
            result["errors"].append("因子执行失败（所有品种均返回空值）")
            return result

        result["success"] = True
        result["factor_values"] = factor_values
        result["symbol_count"] = factor_values.shape[1]
        result["day_count"] = factor_values.shape[0]

        # 检查数据质量
        null_pct = factor_values.isnull().mean().mean()
        if null_pct > 0.5:
            result["warnings"].append(f"因子值空值比例过高: {null_pct:.1%}")

        return result
