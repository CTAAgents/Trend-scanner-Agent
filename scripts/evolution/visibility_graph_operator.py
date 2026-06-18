"""
可见图算子管理器模块

提供可见图类因子的算子定义、描述和示例，用于扩展因子生成器的搜索空间。

核心功能：
1. 算子注册和管理
2. 算子描述生成（用于 LLM prompt）
3. 示例因子代码生成
4. 算子执行

版本：v1.0
创建日期：2026-06-17
"""

import logging

import numpy as np


logger = logging.getLogger(__name__)


class VisibilityGraphOperator:
    """
    可见图算子管理器

    管理可见图类因子的算子，提供：
    - 算子注册和执行
    - 算子描述生成（用于 LLM prompt）
    - 示例因子代码生成
    """

    def __init__(self):
        """初始化算子管理器"""
        self.operators = {
            "backward_visibility": {
                "func": self._backward_visibility,
                "description": "计算价格点之间的向后可见性关系",
                "params": {"window": "回看窗口大小，默认100"},
                "returns": "可见性向量（1=可见，0=不可见）",
                "use_case": "捕捉价格序列的局部结构特征",
            },
            "horizontal_visibility": {
                "func": self._horizontal_visibility,
                "description": "计算水平可见性关系（更严格的可见性条件）",
                "params": {"window": "回看窗口大小，默认100"},
                "returns": "水平可见性向量（1=可见，0=不可见）",
                "use_case": "捕捉价格序列的转折点",
            },
            "visibility_matrix": {
                "func": self._visibility_matrix,
                "description": "计算完整的可见性矩阵",
                "params": {"window": "回看窗口大小，默认100"},
                "returns": "可见性矩阵（邻接矩阵）",
                "use_case": "网络分析、度分布计算",
            },
            "visibility_aggregate_mean": {
                "func": self._aggregate_mean,
                "description": "基于可见性关系的均值聚合",
                "params": {"window": "回看窗口大小，默认100"},
                "returns": "聚合后的因子值",
                "use_case": "趋势持续性指标",
            },
            "visibility_aggregate_ratio": {
                "func": self._aggregate_ratio,
                "description": "基于可见性关系的比率聚合",
                "params": {"window": "回看窗口大小，默认100"},
                "returns": "聚合后的因子值",
                "use_case": "突破脉冲指标",
            },
        }

        logger.info(f"VisibilityGraphOperator 初始化完成，注册 {len(self.operators)} 个算子")

    def get_operator_descriptions(self) -> str:
        """
        获取所有算子的描述，用于 LLM prompt

        Returns:
            str: 算子描述文本
        """
        descriptions = []

        for name, info in self.operators.items():
            desc = f"### {name}\n"
            desc += f"- **功能**: {info['description']}\n"
            desc += f"- **参数**: {', '.join(f'{k}={v}' for k, v in info['params'].items())}\n"
            desc += f"- **返回**: {info['returns']}\n"
            desc += f"- **适用**: {info['use_case']}\n"
            descriptions.append(desc)

        return "\n".join(descriptions)

    def get_example_factors(self) -> list[str]:
        """
        获取示例因子代码，用于 LLM prompt

        Returns:
            List[str]: 示例因子代码列表
        """
        examples = []

        # 示例 1：可见性动量因子
        example1 = '''
# 示例 1：可见性动量因子
def factor(df, window=50):
    """可见性动量：基于可见性关系的动量指标"""
    from scripts.trend_scanner.visibility_graph import VisibilityGraph
    
    prices = df['close'].values
    n = len(prices)
    result = np.full(n, np.nan)
    
    for i in range(window, n):
        window_prices = prices[i-window:i+1]
        visibility = VisibilityGraph.compute_visibility_matrix(window_prices, window)
        
        # 计算可见性动量
        positive_count = 0
        negative_count = 0
        for j, visible_points in visibility.items():
            for k in visible_points:
                if window_prices[k] > window_prices[j]:
                    positive_count += 1
                elif window_prices[k] < window_prices[j]:
                    negative_count += 1
        
        if positive_count + negative_count > 0:
            result[i] = positive_count / (positive_count + negative_count) * 100
    
    return pd.Series(result, index=df.index)
'''
        examples.append(example1)

        # 示例 2：可见性波动率因子
        example2 = '''
# 示例 2：可见性波动率因子
def factor(df, window=50):
    """可见性波动率：基于可见性关系的波动率指标"""
    from scripts.trend_scanner.visibility_graph import VisibilityGraph
    
    prices = df['close'].values
    n = len(prices)
    result = np.full(n, np.nan)
    
    for i in range(window, n):
        window_prices = prices[i-window:i+1]
        visibility = VisibilityGraph.compute_visibility_matrix(window_prices, window)
        
        # 计算可见性波动率
        visible_returns = []
        for j, visible_points in visibility.items():
            for k in visible_points:
                ret = (window_prices[k] - window_prices[j]) / window_prices[j]
                visible_returns.append(abs(ret))
        
        if visible_returns:
            result[i] = np.std(visible_returns)
    
    return pd.Series(result, index=df.index)
'''
        examples.append(example2)

        # 示例 3：可见性趋势强度因子
        example3 = '''
# 示例 3：可见性趋势强度因子
def factor(df, window=50):
    """可见性趋势强度：基于可见性关系的趋势强度指标"""
    from scripts.trend_scanner.visibility_graph import VisibilityGraph
    
    prices = df['close'].values
    n = len(prices)
    result = np.full(n, np.nan)
    
    for i in range(window, n):
        window_prices = prices[i-window:i+1]
        visibility = VisibilityGraph.compute_visibility_matrix(window_prices, window)
        
        # 计算可见性趋势强度
        total_connections = 0
        upward_connections = 0
        
        for j, visible_points in visibility.items():
            for k in visible_points:
                total_connections += 1
                if window_prices[k] > window_prices[j]:
                    upward_connections += 1
        
        if total_connections > 0:
            # 趋势强度 = 上涨连接占比 * 100
            result[i] = upward_connections / total_connections * 100
    
    return pd.Series(result, index=df.index)
'''
        examples.append(example3)

        return examples

    def _backward_visibility(self, prices: np.ndarray, window: int = 100) -> np.ndarray:
        """
        向后可见性关系算子

        计算每个价格点与前一个价格点的可见性关系。

        Args:
            prices: 价格序列
            window: 回看窗口大小

        Returns:
            np.ndarray: 可见性向量（1=可见，0=不可见）
        """
        from .visibility_graph import VisibilityGraph

        n = len(prices)
        result = np.zeros(n)

        for i in range(1, n):
            # 检查前一个点是否从当前点可见
            if VisibilityGraph.backward_visibility(prices, i - 1, i):
                result[i] = 1

        return result

    def _horizontal_visibility(self, prices: np.ndarray, window: int = 100) -> np.ndarray:
        """
        水平可见性关系算子

        计算水平可见性关系（更严格的可见性条件）。

        Args:
            prices: 价格序列
            window: 回看窗口大小

        Returns:
            np.ndarray: 水平可见性向量（1=可见，0=不可见）
        """

        n = len(prices)
        result = np.zeros(n)

        for i in range(1, n):
            # 水平可见性：价格必须相等
            if prices[i] == prices[i - 1]:
                result[i] = 1

        return result

    def _visibility_matrix(self, prices: np.ndarray, window: int = 100) -> np.ndarray:
        """
        可见性矩阵算子

        计算完整的可见性矩阵。

        Args:
            prices: 价格序列
            window: 回看窗口大小

        Returns:
            np.ndarray: 可见性矩阵的度（连接数）
        """
        from .visibility_graph import VisibilityGraph

        n = len(prices)
        result = np.zeros(n)

        for i in range(window, n):
            window_start = max(0, i - window)
            window_prices = prices[window_start : i + 1]

            # 计算可见性矩阵
            visibility = VisibilityGraph.compute_visibility_matrix(window_prices, window)

            # 计算度（连接数）
            total_connections = 0
            for j, visible_points in visibility.items():
                total_connections += len(visible_points)

            result[i] = total_connections

        return result

    def _aggregate_mean(self, prices: np.ndarray, window: int = 100) -> np.ndarray:
        """
        均值聚合算子

        基于可见性关系的均值聚合。

        Args:
            prices: 价格序列
            window: 回看窗口大小

        Returns:
            np.ndarray: 聚合后的因子值
        """
        from .visibility_graph import VisibilityGraph

        n = len(prices)
        result = np.full(n, np.nan)

        for i in range(window, n):
            window_start = max(0, i - window)
            window_prices = prices[window_start : i + 1]

            # 计算可见性矩阵
            visibility = VisibilityGraph.compute_visibility_matrix(window_prices, window)

            # 计算均值聚合
            values = []
            for j, visible_points in visibility.items():
                for k in visible_points:
                    values.append(window_prices[k] - window_prices[j])

            if values:
                result[i] = np.mean(values)

        return result

    def _aggregate_ratio(self, prices: np.ndarray, window: int = 100) -> np.ndarray:
        """
        比率聚合算子

        基于可见性关系的比率聚合。

        Args:
            prices: 价格序列
            window: 回看窗口大小

        Returns:
            np.ndarray: 聚合后的因子值
        """
        from .visibility_graph import VisibilityGraph

        n = len(prices)
        result = np.full(n, np.nan)

        for i in range(window, n):
            window_start = max(0, i - window)
            window_prices = prices[window_start : i + 1]

            # 计算可见性矩阵
            visibility = VisibilityGraph.compute_visibility_matrix(window_prices, window)

            # 计算比率聚合
            positive_count = 0
            negative_count = 0

            for j, visible_points in visibility.items():
                for k in visible_points:
                    if window_prices[k] > window_prices[j]:
                        positive_count += 1
                    elif window_prices[k] < window_prices[j]:
                        negative_count += 1

            if positive_count + negative_count > 0:
                result[i] = positive_count / (positive_count + negative_count) * 100

        return result

    def execute_operator(self, operator_name: str, prices: np.ndarray, **params) -> np.ndarray:
        """
        执行指定的算子

        Args:
            operator_name: 算子名称
            prices: 价格序列
            **params: 算子参数

        Returns:
            np.ndarray: 算子结果
        """
        if operator_name not in self.operators:
            raise ValueError(f"未知算子: {operator_name}")

        operator_func = self.operators[operator_name]["func"]
        return operator_func(prices, **params)


def get_visibility_operator_descriptions() -> str:
    """
    便捷函数：获取可见图算子描述

    Returns:
        str: 算子描述文本
    """
    operator = VisibilityGraphOperator()
    return operator.get_operator_descriptions()


def get_visibility_example_factors() -> list[str]:
    """
    便捷函数：获取可见图示例因子

    Returns:
        List[str]: 示例因子代码列表
    """
    operator = VisibilityGraphOperator()
    return operator.get_example_factors()
