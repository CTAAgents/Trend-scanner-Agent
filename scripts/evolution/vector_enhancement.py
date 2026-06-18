"""
向量增强模块

提升经验检索的精度，支持：
1. 扩展特征维度（5维 → 15维）
2. 加权欧氏距离计算
3. 多粒度检索（短期/中期/长期）
4. 机制感知的相似度计算

设计原则：
- 向后兼容：支持旧的5维向量
- 渐进增强：可选启用新特征
- 性能优先：使用向量化计算
"""

from dataclasses import dataclass
from datetime import datetime

import numpy as np


# 特征维度定义
FEATURE_DIMENSIONS = {
    # 趋势特征（5维）
    "trend": [
        "adx_normalized",  # ADX 归一化 (0-1)
        "ema_slope_20",  # EMA20 斜率
        "ema_slope_60",  # EMA60 斜率
        "macd_histogram",  # MACD 柱
        "trend_strength",  # 趋势强度 (0-1)
    ],
    # 波动率特征（3维）
    "volatility": [
        "atr_percentile",  # ATR 分位数 (0-1)
        "bollinger_width",  # 布林带宽度
        "volatility_regime",  # 波动率状态 (0=低, 0.5=中, 1=高)
    ],
    # 动量特征（4维）
    "momentum": [
        "rsi_normalized",  # RSI 归一化 (0-1)
        "rsi_slope",  # RSI 斜率
        "macd_cross_strength",  # MACD 交叉强度
        "momentum_score",  # 动量评分 (-1 到 1)
    ],
    # 市场结构特征（3维）
    "structure": [
        "high_low_ratio",  # 高低点比率
        "channel_position",  # 通道位置 (0-1)
        "support_distance",  # 支撑位距离
    ],
}

# 默认特征权重
DEFAULT_FEATURE_WEIGHTS = {
    "trend": [1.0, 1.2, 1.2, 0.8, 1.0],  # 趋势特征权重较高
    "volatility": [0.6, 0.5, 0.7],  # 波动率特征权重中等
    "momentum": [0.8, 0.7, 0.9, 0.8],  # 动量特征权重中等
    "structure": [0.5, 0.6, 0.4],  # 结构特征权重较低
}


@dataclass
class FeatureVector:
    """
    扩展特征向量

    支持15维特征，按类别组织：
    - 趋势特征（5维）
    - 波动率特征（3维）
    - 动量特征（4维）
    - 市场结构特征（3维）
    """

    # 趋势特征
    adx_normalized: float = 0.5
    ema_slope_20: float = 0.0
    ema_slope_60: float = 0.0
    macd_histogram: float = 0.0
    trend_strength: float = 0.5

    # 波动率特征
    atr_percentile: float = 0.5
    bollinger_width: float = 0.0
    volatility_regime: float = 0.5

    # 动量特征
    rsi_normalized: float = 0.5
    rsi_slope: float = 0.0
    macd_cross_strength: float = 0.0
    momentum_score: float = 0.0

    # 市场结构特征
    high_low_ratio: float = 0.5
    channel_position: float = 0.5
    support_distance: float = 0.5

    def to_list(self) -> list[float]:
        """转换为列表"""
        return [
            # 趋势特征
            self.adx_normalized,
            self.ema_slope_20,
            self.ema_slope_60,
            self.macd_histogram,
            self.trend_strength,
            # 波动率特征
            self.atr_percentile,
            self.bollinger_width,
            self.volatility_regime,
            # 动量特征
            self.rsi_normalized,
            self.rsi_slope,
            self.macd_cross_strength,
            self.momentum_score,
            # 市场结构特征
            self.high_low_ratio,
            self.channel_position,
            self.support_distance,
        ]

    def to_dict(self) -> dict[str, float]:
        """转换为字典"""
        return {
            "adx_normalized": self.adx_normalized,
            "ema_slope_20": self.ema_slope_20,
            "ema_slope_60": self.ema_slope_60,
            "macd_histogram": self.macd_histogram,
            "trend_strength": self.trend_strength,
            "atr_percentile": self.atr_percentile,
            "bollinger_width": self.bollinger_width,
            "volatility_regime": self.volatility_regime,
            "rsi_normalized": self.rsi_normalized,
            "rsi_slope": self.rsi_slope,
            "macd_cross_strength": self.macd_cross_strength,
            "momentum_score": self.momentum_score,
            "high_low_ratio": self.high_low_ratio,
            "channel_position": self.channel_position,
            "support_distance": self.support_distance,
        }

    @classmethod
    def from_list(cls, vec: list[float]) -> "FeatureVector":
        """从列表创建"""
        # 支持旧的5维向量
        if len(vec) == 5:
            return cls(
                adx_normalized=vec[0],
                ema_slope_20=vec[1],
                ema_slope_60=vec[2],
                macd_histogram=vec[3],
                trend_strength=vec[4],
            )

        # 支持完整的15维向量
        if len(vec) >= 15:
            return cls(
                adx_normalized=vec[0],
                ema_slope_20=vec[1],
                ema_slope_60=vec[2],
                macd_histogram=vec[3],
                trend_strength=vec[4],
                atr_percentile=vec[5],
                bollinger_width=vec[6],
                volatility_regime=vec[7],
                rsi_normalized=vec[8],
                rsi_slope=vec[9],
                macd_cross_strength=vec[10],
                momentum_score=vec[11],
                high_low_ratio=vec[12],
                channel_position=vec[13],
                support_distance=vec[14],
            )

        # 其他长度，用默认值填充
        result = cls()
        for i, val in enumerate(vec[:15]):
            setattr(result, list(cls.__dataclass_fields__.keys())[i], val)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "FeatureVector":
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class VectorEnhancer:
    """
    向量增强器

    提供：
    1. 特征提取（从 MarketContext 提取15维特征）
    2. 距离计算（加权欧氏距离、余弦相似度）
    3. 多粒度检索（短期/中期/长期经验）
    """

    def __init__(self, weights: dict[str, list[float]] | None = None):
        """
        初始化向量增强器

        Args:
            weights: 特征权重，格式为 {'trend': [w1, w2, ...], ...}
        """
        self.weights = weights or DEFAULT_FEATURE_WEIGHTS
        self._flat_weights = self._flatten_weights()

    def _flatten_weights(self) -> np.ndarray:
        """将嵌套权重展平为一维数组"""
        flat = []
        for category in ["trend", "volatility", "momentum", "structure"]:
            flat.extend(self.weights.get(category, []))
        return np.array(flat)

    def extract_features(self, context) -> FeatureVector:
        """
        从 MarketContext 提取扩展特征向量

        Args:
            context: MarketContext 对象

        Returns:
            FeatureVector 对象
        """
        # 从 context.snapshot 获取指标
        snapshot = context.snapshot if hasattr(context, "snapshot") else {}
        indicators = context.indicators if hasattr(context, "indicators") else {}

        # 提取趋势特征
        adx = getattr(snapshot, "adx", 20) if hasattr(snapshot, "adx") else 20
        ema20 = getattr(snapshot, "ema20", 0) if hasattr(snapshot, "ema20") else 0
        ema60 = getattr(snapshot, "ema60", 0) if hasattr(snapshot, "ema60") else 0
        macd_hist = getattr(snapshot, "macd_histogram", 0) if hasattr(snapshot, "macd_histogram") else 0

        # 计算归一化值
        adx_normalized = min(adx / 50, 1.0)  # ADX 50 为上限
        ema_slope_20 = ema20 / 1000 if ema20 != 0 else 0  # 归一化斜率
        ema_slope_60 = ema60 / 1000 if ema60 != 0 else 0
        macd_histogram = macd_hist / 100 if macd_hist != 0 else 0

        # 趋势强度（基于 ADX 和均线排列）
        trend_strength = adx_normalized * 0.7 + abs(ema_slope_20 - ema_slope_60) * 0.3

        # 提取波动率特征
        atr = getattr(snapshot, "atr", 0) if hasattr(snapshot, "atr") else 0
        close = context.current_price if hasattr(context, "current_price") else 1000

        atr_percentile = min(atr / close * 100, 1.0)  # ATR 占价格的百分比
        bollinger_width = getattr(snapshot, "bollinger_width", 0) if hasattr(snapshot, "bollinger_width") else 0
        volatility_regime = 0.5  # 默认中等波动

        # 提取动量特征
        rsi = getattr(snapshot, "rsi", 50) if hasattr(snapshot, "rsi") else 50
        rsi_normalized = rsi / 100
        rsi_slope = 0  # 需要历史数据计算
        macd_cross_strength = abs(macd_histogram)
        momentum_score = macd_histogram  # 正值看多，负值看空

        # 提取市场结构特征
        high_low_ratio = 0.5  # 默认中性
        channel_position = 0.5  # 默认中性
        support_distance = 0.5  # 默认中性

        return FeatureVector(
            adx_normalized=adx_normalized,
            ema_slope_20=ema_slope_20,
            ema_slope_60=ema_slope_60,
            macd_histogram=macd_histogram,
            trend_strength=trend_strength,
            atr_percentile=atr_percentile,
            bollinger_width=bollinger_width,
            volatility_regime=volatility_regime,
            rsi_normalized=rsi_normalized,
            rsi_slope=rsi_slope,
            macd_cross_strength=macd_cross_strength,
            momentum_score=momentum_score,
            high_low_ratio=high_low_ratio,
            channel_position=channel_position,
            support_distance=support_distance,
        )

    def weighted_euclidean_distance(self, vec1: list[float], vec2: list[float]) -> float:
        """
        计算加权欧氏距离

        Args:
            vec1: 特征向量1
            vec2: 特征向量2

        Returns:
            加权欧氏距离（越小越相似）
        """
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        # 统一长度
        max_len = max(len(v1), len(v2))
        if len(v1) < max_len:
            v1 = np.concatenate([v1, np.zeros(max_len - len(v1))])
        if len(v2) < max_len:
            v2 = np.concatenate([v2, np.zeros(max_len - len(v2))])

        # 截断权重到匹配长度
        weights = (
            self._flat_weights[:max_len]
            if len(self._flat_weights) >= max_len
            else np.concatenate([self._flat_weights, np.ones(max_len - len(self._flat_weights))])
        )

        # 加权欧氏距离
        diff = v1 - v2
        weighted_diff = diff * weights
        distance = np.sqrt(np.sum(weighted_diff**2))

        return float(distance)

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        计算余弦相似度

        Args:
            vec1: 特征向量1
            vec2: 特征向量2

        Returns:
            余弦相似度（-1 到 1，越大越相似）
        """
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        # 统一长度
        max_len = max(len(v1), len(v2))
        if len(v1) < max_len:
            v1 = np.concatenate([v1, np.zeros(max_len - len(v1))])
        if len(v2) < max_len:
            v2 = np.concatenate([v2, np.zeros(max_len - len(v2))])

        # 余弦相似度
        dot = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot / (norm1 * norm2))

    def combined_similarity(
        self, vec1: list[float], vec2: list[float], cosine_weight: float = 0.6, euclidean_weight: float = 0.4
    ) -> float:
        """
        计算组合相似度（余弦 + 欧氏）

        Args:
            vec1: 特征向量1
            vec2: 特征向量2
            cosine_weight: 余弦相似度权重
            euclidean_weight: 欧氏距离权重

        Returns:
            组合相似度（0-1，越大越相似）
        """
        # 余弦相似度（归一化到 0-1）
        cos_sim = self.cosine_similarity(vec1, vec2)
        cos_sim_normalized = (cos_sim + 1) / 2  # 从 [-1,1] 映射到 [0,1]

        # 加权欧氏距离（归一化到 0-1）
        euclidean_dist = self.weighted_euclidean_distance(vec1, vec2)
        # 使用指数衰减将距离转换为相似度
        euclidean_sim = np.exp(-euclidean_dist / 5)  # 衰减系数可调

        # 组合相似度
        combined = cosine_weight * cos_sim_normalized + euclidean_weight * euclidean_sim

        return float(np.clip(combined, 0, 1))

    def compute_similarity_matrix(self, vectors: list[list[float]]) -> np.ndarray:
        """
        计算相似度矩阵

        Args:
            vectors: 特征向量列表

        Returns:
            相似度矩阵 (n x n)
        """
        n = len(vectors)
        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i, n):
                sim = self.combined_similarity(vectors[i], vectors[j])
                matrix[i, j] = sim
                matrix[j, i] = sim

        return matrix


class MultiGranularityRetriever:
    """
    多粒度检索器

    支持按时间粒度检索经验：
    - 短期（7天内）
    - 中期（30天内）
    - 长期（90天内）
    - 全部
    """

    def __init__(self, enhancer: VectorEnhancer | None = None):
        self.enhancer = enhancer or VectorEnhancer()

    def retrieve_by_granularity(
        self, experiences: list, query_vector: list[float], granularity: str = "all", top_k: int = 10
    ) -> list[tuple[int, float]]:
        """
        按粒度检索经验

        Args:
            experiences: 经验列表
            query_vector: 查询向量
            granularity: 粒度 ('short', 'medium', 'long', 'all')
            top_k: 返回数量

        Returns:
            [(index, similarity), ...] 按相似度排序
        """
        # 按时间过滤
        now = datetime.now()
        filtered = []

        for i, exp in enumerate(experiences):
            try:
                exp_time = datetime.fromisoformat(exp.timestamp.replace("Z", "+00:00").split("+")[0])
                days_ago = (now - exp_time).days

                if (
                    (granularity == "short" and days_ago <= 7)
                    or (granularity == "medium" and days_ago <= 30)
                    or (granularity == "long" and days_ago <= 90)
                    or granularity == "all"
                ):
                    filtered.append((i, exp))
            except:
                # 时间解析失败，包含在全部中
                if granularity == "all":
                    filtered.append((i, exp))

        # 计算相似度
        results = []
        for idx, exp in filtered:
            exp_vector = exp.feature_vector if hasattr(exp, "feature_vector") else []
            if exp_vector:
                sim = self.enhancer.combined_similarity(query_vector, exp_vector)
                results.append((idx, sim))

        # 排序
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]

    def retrieve_multi_granularity(
        self, experiences: list, query_vector: list[float], top_k: int = 10
    ) -> dict[str, list[tuple[int, float]]]:
        """
        多粒度检索

        Returns:
            {
                'short': [(idx, sim), ...],
                'medium': [(idx, sim), ...],
                'long': [(idx, sim), ...],
                'all': [(idx, sim), ...],
            }
        """
        return {
            "short": self.retrieve_by_granularity(experiences, query_vector, "short", top_k),
            "medium": self.retrieve_by_granularity(experiences, query_vector, "medium", top_k),
            "long": self.retrieve_by_granularity(experiences, query_vector, "long", top_k),
            "all": self.retrieve_by_granularity(experiences, query_vector, "all", top_k),
        }


# 便捷函数
def create_enhancer(weights: dict[str, list[float]] | None = None) -> VectorEnhancer:
    """创建向量增强器"""
    return VectorEnhancer(weights)


def compute_feature_vector(context) -> list[float]:
    """从 MarketContext 计算特征向量"""
    enhancer = VectorEnhancer()
    features = enhancer.extract_features(context)
    return features.to_list()


def compute_similarity(vec1: list[float], vec2: list[float]) -> float:
    """计算两个向量的相似度"""
    enhancer = VectorEnhancer()
    return enhancer.combined_similarity(vec1, vec2)
