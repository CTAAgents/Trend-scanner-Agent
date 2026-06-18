"""
变长机制分割器

基于变化点检测算法，将市场数据分割成变长的机制段。

核心思想：
- 第1层：数据驱动的变长分割（在哪里切）
- 第2层：规则驱动的语义标注（叫什么名字）

设计原则：
- 两层独立优化
- 向后兼容
- 可配置参数
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


try:
    import ruptures as rpt

    HAS_RUPTURES = True
except ImportError:
    HAS_RUPTURES = False


@dataclass
class RegimeSegment:
    """
    机制段

    表示一个时间区间内的市场机制。
    """

    start_idx: int  # 起始索引
    end_idx: int  # 结束索引
    start_time: str = ""  # 起始时间
    end_time: str = ""  # 结束时间
    length: int = 0  # 长度（天数）

    # 语义标注（第2层填充）
    phase: str = ""  # 阶段标签
    confidence: float = 0.0  # 置信度

    # 统计特征
    avg_price: float = 0.0
    avg_volume: float = 0.0
    avg_atr: float = 0.0
    price_change: float = 0.0
    volatility: float = 0.0

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "length": self.length,
            "phase": self.phase,
            "confidence": self.confidence,
            "avg_price": self.avg_price,
            "avg_volume": self.avg_volume,
            "avg_atr": self.avg_atr,
            "price_change": self.price_change,
            "volatility": self.volatility,
        }


class RegimeSegmenter:
    """
    变长机制分割器

    使用变化点检测算法将市场数据分割成变长的机制段。

    支持的算法：
    - PELT (Pruned Exact Linear Time)
    - BinSeg (Binary Segmentation)
    - Window (Sliding Window)
    """

    def __init__(
        self,
        algorithm: str = "pelt",
        model: str = "rbf",
        min_size: int = 10,
        penalty: float | None = None,
        n_breakpoints: int | None = None,
    ):
        """
        初始化分割器

        Args:
            algorithm: 算法类型 ('pelt', 'binseg', 'window')
            model: 成本函数模型 ('l1', 'l2', 'rbf', 'linear', 'normal')
            min_size: 最小段长度
            penalty: 惩罚系数（越小，检测到的变化点越多）
            n_breakpoints: 指定变化点数量（如果指定，忽略 penalty）
        """
        if not HAS_RUPTURES:
            raise ImportError("ruptures 库未安装，请运行: pip install ruptures")

        self.algorithm = algorithm
        self.model = model
        self.min_size = min_size
        self.penalty = penalty
        self.n_breakpoints = n_breakpoints

    def segment(
        self, df: pd.DataFrame, features: list[str] = None, return_segments: bool = True
    ) -> list[RegimeSegment]:
        """
        分割市场数据

        Args:
            df: DataFrame，包含市场数据
            features: 用于分割的特征列名
            return_segments: 是否返回 RegimeSegment 列表

        Returns:
            机制段列表
        """
        if features is None:
            features = self._detect_features(df)

        # 准备特征矩阵
        feature_matrix = self._prepare_features(df, features)

        # 检测变化点
        change_points = self._detect_change_points(feature_matrix)

        # 创建机制段
        segments = self._create_segments(df, change_points)

        return segments

    def _detect_features(self, df: pd.DataFrame) -> list[str]:
        """自动检测可用的特征列"""
        available = []

        # 价格特征
        for col in ["close", "high", "low", "open"]:
            if col in df.columns:
                available.append(col)

        # 成交量特征
        if "volume" in df.columns:
            available.append("volume")

        # 波动率特征
        if "atr" in df.columns:
            available.append("atr")

        # 如果没有足够的特征，使用 close
        if not available:
            if "close" in df.columns:
                available = ["close"]
            else:
                raise ValueError("DataFrame 中没有可用的特征列")

        return available

    def _prepare_features(self, df: pd.DataFrame, features: list[str]) -> np.ndarray:
        """准备特征矩阵"""
        # 提取特征
        matrix = df[features].values

        # 处理缺失值
        matrix = np.nan_to_num(matrix, nan=0.0)

        # 标准化（可选）
        # matrix = (matrix - matrix.mean(axis=0)) / (matrix.std(axis=0) + 1e-8)

        return matrix

    def _detect_change_points(self, feature_matrix: np.ndarray) -> list[int]:
        """检测变化点"""
        # 创建算法对象
        algo = self._create_algorithm(feature_matrix)

        # 检测变化点
        if self.n_breakpoints is not None:
            # 指定变化点数量
            # Pelt 不支持 n_bkps，使用 BinSeg
            if self.algorithm == "pelt":
                algo = rpt.Binseg(model=self.model, min_size=self.min_size).fit(feature_matrix)
            change_points = algo.predict(n_bkps=self.n_breakpoints)
        elif self.penalty is not None:
            # 使用惩罚系数
            change_points = algo.predict(pen=self.penalty)
        else:
            # 自动选择惩罚系数
            change_points = self._auto_penalty(algo, feature_matrix)

        # 移除最后一个点（通常是数据长度）
        if change_points and change_points[-1] == len(feature_matrix):
            change_points = change_points[:-1]

        return change_points

    def _create_algorithm(self, feature_matrix: np.ndarray):
        """创建变化点检测算法"""
        if self.algorithm == "pelt":
            return rpt.Pelt(model=self.model, min_size=self.min_size).fit(feature_matrix)
        elif self.algorithm == "binseg":
            return rpt.Binseg(model=self.model, min_size=self.min_size).fit(feature_matrix)
        elif self.algorithm == "window":
            return rpt.Window(model=self.model, min_size=self.min_size).fit(feature_matrix)
        else:
            raise ValueError(f"不支持的算法: {self.algorithm}")

    def _auto_penalty(self, algo, feature_matrix: np.ndarray) -> list[int]:
        """自动选择惩罚系数"""
        # 使用 BIC (Bayesian Information Criterion) 的近似
        n = len(feature_matrix)
        d = feature_matrix.shape[1] if len(feature_matrix.shape) > 1 else 1

        # 惩罚系数 = d * log(n)
        penalty = d * np.log(n)

        return algo.predict(pen=penalty)

    def _create_segments(self, df: pd.DataFrame, change_points: list[int]) -> list[RegimeSegment]:
        """创建机制段"""
        segments = []
        start = 0

        # 添加数据结束点
        all_points = change_points + [len(df)]

        for cp in all_points:
            # 提取段数据
            segment_data = df.iloc[start:cp]

            if len(segment_data) > 0:
                # 创建机制段
                segment = RegimeSegment(
                    start_idx=start,
                    end_idx=cp,
                    length=cp - start,
                )

                # 设置时间
                if hasattr(df.index[start], "isoformat"):
                    segment.start_time = str(df.index[start])
                elif "date" in df.columns:
                    segment.start_time = str(df["date"].iloc[start])

                if hasattr(df.index[min(cp - 1, len(df) - 1)], "isoformat"):
                    segment.end_time = str(df.index[min(cp - 1, len(df) - 1)])
                elif "date" in df.columns:
                    segment.end_time = str(df["date"].iloc[min(cp - 1, len(df) - 1)])

                # 计算统计特征
                self._compute_segment_stats(segment, segment_data)

                segments.append(segment)

            start = cp

        return segments

    def _compute_segment_stats(self, segment: RegimeSegment, data: pd.DataFrame):
        """计算段的统计特征"""
        # 价格统计
        if "close" in data.columns:
            segment.avg_price = data["close"].mean()
            if len(data) > 1:
                segment.price_change = (data["close"].iloc[-1] - data["close"].iloc[0]) / data["close"].iloc[0] * 100

        # 成交量统计
        if "volume" in data.columns:
            segment.avg_volume = data["volume"].mean()

        # ATR 统计
        if "atr" in data.columns:
            segment.avg_atr = data["atr"].mean()

        # 波动率统计
        if "close" in data.columns and len(data) > 1:
            returns = data["close"].pct_change().dropna()
            segment.volatility = returns.std() * np.sqrt(252)  # 年化波动率


class PhaseLabeler:
    """
    语义标注器

    对机制段进行语义标注，使用规则判断趋势阶段。
    """

    def __init__(self):
        """初始化标注器"""
        pass

    def label(self, segment: RegimeSegment, data: pd.DataFrame) -> RegimeSegment:
        """
        对机制段进行语义标注

        Args:
            segment: 机制段
            data: 段内的市场数据

        Returns:
            更新后的机制段
        """
        # 计算指标
        indicators = self._compute_indicators(data)

        # 判断阶段
        phase, confidence = self._determine_phase(indicators)

        # 更新段
        segment.phase = phase
        segment.confidence = confidence

        return segment

    def _compute_indicators(self, data: pd.DataFrame) -> dict:
        """计算技术指标"""
        indicators = {}

        if "close" not in data.columns or len(data) < 5:
            return indicators

        close = data["close"]

        # 均线
        indicators["ema20"] = close.ewm(span=20, adjust=False).mean().iloc[-1]
        indicators["ema60"] = (
            close.ewm(span=60, adjust=False).mean().iloc[-1]
            if len(data) >= 60
            else indicators.get("ema20", close.iloc[-1])
        )

        # 均线斜率
        if len(data) >= 20:
            ema20_series = close.ewm(span=20, adjust=False).mean()
            indicators["ema20_slope"] = (ema20_series.iloc[-1] - ema20_series.iloc[-5]) / ema20_series.iloc[-5] * 100
        else:
            indicators["ema20_slope"] = 0

        if len(data) >= 60:
            ema60_series = close.ewm(span=60, adjust=False).mean()
            indicators["ema60_slope"] = (ema60_series.iloc[-1] - ema60_series.iloc[-5]) / ema60_series.iloc[-5] * 100
        else:
            indicators["ema60_slope"] = 0

        # 价格位置
        indicators["price_vs_ema20"] = (close.iloc[-1] - indicators["ema20"]) / indicators["ema20"] * 100
        indicators["price_vs_ema60"] = (close.iloc[-1] - indicators["ema60"]) / indicators["ema60"] * 100

        # 高低点
        indicators["high"] = data["high"].max() if "high" in data.columns else close.max()
        indicators["low"] = data["low"].min() if "low" in data.columns else close.min()
        indicators["price_range"] = (indicators["high"] - indicators["low"]) / indicators["low"] * 100

        # 波动率
        if len(data) > 1:
            returns = close.pct_change().dropna()
            indicators["volatility"] = returns.std() * np.sqrt(252)
        else:
            indicators["volatility"] = 0

        return indicators

    def _determine_phase(self, indicators: dict) -> tuple[str, float]:
        """
        判断趋势阶段

        基于动量驱动框架：
        - 动量方向 → 趋势方向
        - 动量强度 → 趋势阶段
        """
        if not indicators:
            return "CONSOLIDATING", 0.5

        # 获取指标
        ema20_slope = indicators.get("ema20_slope", 0)
        ema60_slope = indicators.get("ema60_slope", 0)
        price_vs_ema20 = indicators.get("price_vs_ema20", 0)
        price_vs_ema60 = indicators.get("price_vs_ema60", 0)
        volatility = indicators.get("volatility", 0)

        # 判断趋势方向
        bullish_signals = 0
        bearish_signals = 0

        # 均线斜率
        if ema20_slope > 0.5:
            bullish_signals += 1
        elif ema20_slope < -0.5:
            bearish_signals += 1

        if ema60_slope > 0.5:
            bullish_signals += 1
        elif ema60_slope < -0.5:
            bearish_signals += 1

        # 价格位置
        if price_vs_ema20 > 1:
            bullish_signals += 1
        elif price_vs_ema20 < -1:
            bearish_signals += 1

        if price_vs_ema60 > 2:
            bullish_signals += 1
        elif price_vs_ema60 < -2:
            bearish_signals += 1

        # 判断阶段
        if bullish_signals >= 3:
            # 强多头
            if ema20_slope > 2 and ema60_slope > 1:
                return "DEVELOPING", 0.8
            elif ema20_slope > 1:
                return "EMERGING", 0.7
            else:
                return "MATURE", 0.6
        elif bearish_signals >= 3:
            # 强空头
            if ema20_slope < -2 and ema60_slope < -1:
                return "DEVELOPING", 0.8
            elif ema20_slope < -1:
                return "EMERGING", 0.7
            else:
                return "MATURE", 0.6
        else:
            # 震荡
            if volatility > 0.3:
                return "FATIGUING", 0.6
            else:
                return "CONSOLIDATING", 0.7


class HierarchicalRegimeDetector:
    """
    分层机制检测器

    整合第1层（变长分割）和第2层（语义标注）。
    """

    def __init__(self, segmenter: RegimeSegmenter | None = None, labeler: PhaseLabeler | None = None):
        """
        初始化分层检测器

        Args:
            segmenter: 变长分割器
            labeler: 语义标注器
        """
        self.segmenter = segmenter or RegimeSegmenter()
        self.labeler = labeler or PhaseLabeler()

    def detect(self, df: pd.DataFrame, features: list[str] = None) -> list[RegimeSegment]:
        """
        执行分层机制检测

        Args:
            df: DataFrame，包含市场数据
            features: 用于分割的特征列名

        Returns:
            机制段列表（带语义标注）
        """
        # 第1层：变长分割
        segments = self.segmenter.segment(df, features)

        # 第2层：语义标注
        for segment in segments:
            # 提取段数据
            segment_data = df.iloc[segment.start_idx : segment.end_idx]

            # 标注
            self.labeler.label(segment, segment_data)

        return segments

    def detect_current_phase(self, df: pd.DataFrame) -> tuple[str, float]:
        """
        检测当前市场阶段

        Args:
            df: DataFrame，包含市场数据

        Returns:
            (阶段, 置信度)
        """
        # 执行分层检测
        segments = self.detect(df)

        if not segments:
            return "CONSOLIDATING", 0.5

        # 返回最后一个段的阶段
        last_segment = segments[-1]
        return last_segment.phase, last_segment.confidence

    def get_segment_summary(self, segments: list[RegimeSegment]) -> dict:
        """
        获取机制段摘要

        Args:
            segments: 机制段列表

        Returns:
            摘要信息
        """
        if not segments:
            return {}

        # 统计各阶段数量
        phase_counts = {}
        for seg in segments:
            phase = seg.phase or "UNKNOWN"
            phase_counts[phase] = phase_counts.get(phase, 0) + 1

        # 计算平均段长度
        avg_length = np.mean([seg.length for seg in segments])

        # 当前阶段
        current_phase = segments[-1].phase if segments[-1].phase else "UNKNOWN"
        current_confidence = segments[-1].confidence

        return {
            "total_segments": len(segments),
            "phase_distribution": phase_counts,
            "avg_segment_length": round(float(avg_length), 1),
            "current_phase": current_phase,
            "current_confidence": round(current_confidence, 2),
            "segments": [seg.to_dict() for seg in segments],
        }


# 便捷函数
def create_segmenter(algorithm: str = "pelt", min_size: int = 10) -> RegimeSegmenter:
    """创建分割器实例"""
    return RegimeSegmenter(algorithm=algorithm, min_size=min_size)


def create_hierarchical_detector(algorithm: str = "pelt", min_size: int = 10) -> HierarchicalRegimeDetector:
    """创建分层检测器实例"""
    segmenter = RegimeSegmenter(algorithm=algorithm, min_size=min_size)
    labeler = PhaseLabeler()
    return HierarchicalRegimeDetector(segmenter=segmenter, labeler=labeler)


def detect_regime_changes(
    df: pd.DataFrame, features: list[str] = None, algorithm: str = "pelt", min_size: int = 10
) -> list[RegimeSegment]:
    """快速检测机制变化"""
    detector = create_hierarchical_detector(algorithm, min_size)
    return detector.detect(df, features)
