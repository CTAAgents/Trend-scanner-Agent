"""
经验记忆池 —— 类比推理的基础

核心理念：不是"规则"，而是"当时发生了什么，我做了什么，结果怎样"。
通过检索相似历史情境，为推理层提供类比依据。

三种经验来源（按优先级）：
1. B. 历史价格模式匹配 —— 从历史K线中自动提取相似模式
2. A. 规则退化 —— 用简单规则生成初始经验（冷启动）
3. C. LLM世界知识 —— 交叉验证（在推理层实现）
"""

import json
import os
import uuid
from datetime import datetime

import numpy as np
import pandas as pd

from .models import Experience, ExperienceMatch, MarketContext


class ExperienceMemory:
    """
    经验记忆池

    存储和检索交易经验，支持：
    - 添加经验（来自实际交易或历史模式提取）
    - 相似度检索（基于特征向量，支持组合相似度）
    - 多粒度检索（短期/中期/长期）
    - 加权聚合（按相似度和风险调整收益加权）
    - 持久化（SQLite）
    """

    def __init__(self, db_path: str | None = None, max_experiences: int = 10000, use_enhanced_vector: bool = True):
        """
        初始化经验记忆池

        Args:
            db_path: 数据库路径
            max_experiences: 最大经验数量
            use_enhanced_vector: 是否使用增强向量（15维）
        """
        self.db_path = db_path
        self.max_experiences = max_experiences
        self.experiences: list[Experience] = []
        self.use_enhanced_vector = use_enhanced_vector

        # 内存中的特征矩阵（用于快速检索）
        self._feature_matrix: np.ndarray | None = None
        self._feature_ids: list[str] = []

        # 向量增强器（可选）
        self._enhancer = None
        if use_enhanced_vector:
            try:
                from .vector_enhancement import VectorEnhancer

                self._enhancer = VectorEnhancer()
            except ImportError:
                pass

        # 加载已有经验
        if db_path and os.path.exists(db_path):
            self._load_from_db()

    # ──────────────────────────────────────────
    # 公共接口
    # ──────────────────────────────────────────

    def add_experience(self, experience: Experience) -> str:
        """添加一条经验"""
        if not experience.experience_id:
            experience.experience_id = str(uuid.uuid4())[:8]

        self.experiences.append(experience)
        self._invalidate_cache()

        # 持久化
        if self.db_path:
            self._save_to_db(experience)

        # 容量管理
        if len(self.experiences) > self.max_experiences:
            self._evict_old()

        return experience.experience_id

    def retrieve(
        self,
        context: MarketContext,
        top_k: int = 10,
        min_similarity: float = 0.3,
        time_decay: bool = True,
    ) -> list[ExperienceMatch]:
        """
        检索最相似的历史经验

        参数:
            context: 当前市场上下文
            top_k: 返回数量
            min_similarity: 最小相似度阈值
            time_decay: 是否启用时间衰减

        返回:
            按相似度排序的匹配列表
        """
        if not self.experiences:
            return []

        # 构建特征矩阵
        self._build_feature_matrix()

        # 计算当前特征向量
        query_vector = np.array(context.feature_vector)
        if len(query_vector) == 0:
            return []

        # 计算相似度
        similarities = self._compute_similarities(query_vector)

        # 时间衰减
        if time_decay:
            decay_weights = self._compute_time_decay()
            similarities = similarities * decay_weights

        # 排序取 top_k
        indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in indices:
            sim = similarities[idx]
            if sim >= min_similarity:
                exp = self.experiences[idx]
                match = ExperienceMatch(
                    experience=exp,
                    similarity=float(sim),
                    distance=float(1 - sim),
                    weight=float(sim),  # 权重 = 相似度
                )
                results.append(match)

        return results

    def aggregate_routes(
        self,
        matches: list[ExperienceMatch],
    ) -> dict:
        """
        聚合相似经验的动作推荐

        返回:
            {
                'LONG': {'count': 5, 'avg_return': 2.3, 'win_rate': 0.6, 'avg_weight': 0.7},
                'SHORT': {'count': 3, 'avg_return': -1.1, 'win_rate': 0.33, 'avg_weight': 0.5},
                ...
            }
        """
        if not matches:
            return {}

        groups = {}
        for match in matches:
            action = match.experience.action_taken
            if action not in groups:
                groups[action] = {
                    "count": 0,
                    "returns": [],
                    "weights": [],
                    "max_drawdowns": [],
                    "holding_days": [],
                }
            groups[action]["count"] += 1
            groups[action]["returns"].append(match.experience.pnl_pct)
            groups[action]["weights"].append(match.weight)
            groups[action]["max_drawdowns"].append(match.experience.max_drawdown_pct)
            groups[action]["holding_days"].append(match.experience.holding_days)

        # 聚合统计
        result = {}
        for action, data in groups.items():
            returns = np.array(data["returns"])
            weights = np.array(data["weights"])

            # 加权平均收益
            if weights.sum() > 0:
                avg_return = np.average(returns, weights=weights)
            else:
                avg_return = returns.mean()

            # 胜率
            win_rate = (returns > 0).sum() / len(returns)

            # 风险调整收益
            avg_dd = np.mean(data["max_drawdowns"])
            risk_adj = avg_return / max(avg_dd, 0.1) if avg_dd > 0 else avg_return

            result[action] = {
                "count": data["count"],
                "avg_return": round(float(avg_return), 2),
                "win_rate": round(float(win_rate), 2),
                "avg_weight": round(float(weights.mean()), 2),
                "avg_max_drawdown": round(float(avg_dd), 2),
                "risk_adjusted_return": round(float(risk_adj), 2),
                "avg_holding_days": int(np.mean(data["holding_days"])),
            }

        return result

    def get_experience_count(self) -> int:
        """获取经验总数"""
        return len(self.experiences)

    def retrieve_by_granularity(
        self,
        context: MarketContext,
        granularity: str = "all",
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[ExperienceMatch]:
        """
        按时间粒度检索经验

        Args:
            context: 当前市场上下文
            granularity: 粒度 ('short'=7天, 'medium'=30天, 'long'=90天, 'all'=全部)
            top_k: 返回数量
            min_similarity: 最小相似度阈值

        Returns:
            按相似度排序的匹配列表
        """
        if not self.experiences:
            return []

        # 计算当前特征向量
        query_vector = np.array(context.feature_vector)
        if len(query_vector) == 0:
            return []

        # 按时间过滤
        now = datetime.now()
        filtered_indices = []

        for i, exp in enumerate(self.experiences):
            try:
                exp_time = datetime.fromisoformat(exp.timestamp.replace("Z", "+00:00").split("+")[0])
                days_ago = (now - exp_time).days

                if (
                    (granularity == "short" and days_ago <= 7)
                    or (granularity == "medium" and days_ago <= 30)
                    or (granularity == "long" and days_ago <= 90)
                    or granularity == "all"
                ):
                    filtered_indices.append(i)
            except (ValueError, AttributeError):
                if granularity == "all":
                    filtered_indices.append(i)

        if not filtered_indices:
            return []

        # 构建过滤后的特征矩阵
        self._build_feature_matrix()
        if self._feature_matrix is None:
            return []

        filtered_matrix = self._feature_matrix[filtered_indices]

        # 计算相似度
        similarities = []
        query_list = query_vector.tolist()

        for idx in filtered_indices:
            exp_vector = self._feature_matrix[idx].tolist()
            if self._enhancer and self.use_enhanced_vector:
                sim = self._enhancer.combined_similarity(query_list, exp_vector)
            else:
                # 传统余弦相似度
                v1 = np.array(exp_vector)
                dot = np.dot(query_vector, v1)
                norm1 = np.linalg.norm(query_vector)
                norm2 = np.linalg.norm(v1)
                sim = dot / (norm1 * norm2 + 1e-10) if norm1 > 0 and norm2 > 0 else 0
            similarities.append(sim)

        similarities = np.array(similarities)

        # 排序取 top_k
        sorted_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for pos in sorted_indices:
            sim = similarities[pos]
            if sim >= min_similarity:
                exp_idx = filtered_indices[pos]
                exp = self.experiences[exp_idx]
                match = ExperienceMatch(
                    experience=exp,
                    similarity=float(sim),
                    distance=float(1 - sim),
                    weight=float(sim),
                )
                results.append(match)

        return results

    def retrieve_multi_granularity(
        self,
        context: MarketContext,
        top_k: int = 10,
    ) -> dict[str, list[ExperienceMatch]]:
        """
        多粒度检索

        Args:
            context: 当前市场上下文
            top_k: 每个粒度的返回数量

        Returns:
            {
                'short': [...],
                'medium': [...],
                'long': [...],
                'all': [...],
            }
        """
        return {
            "short": self.retrieve_by_granularity(context, "short", top_k),
            "medium": self.retrieve_by_granularity(context, "medium", top_k),
            "long": self.retrieve_by_granularity(context, "long", top_k),
            "all": self.retrieve_by_granularity(context, "all", top_k),
        }

    def get_phase_distribution(self) -> dict:
        """获取趋势阶段分布"""
        dist = {}
        for exp in self.experiences:
            phase = exp.trend_phase
            dist[phase] = dist.get(phase, 0) + 1
        return dist

    # ──────────────────────────────────────────
    # 冷启动：从历史K线提取模式
    # ──────────────────────────────────────────

    def extract_patterns_from_history(
        self,
        df: pd.DataFrame,
        symbol: str,
        window: int = 20,
        step: int = 5,
        forward_days: int = 10,
    ) -> int:
        """
        从历史K线中提取模式作为初始经验

        方法：滑动窗口扫描，每个窗口提取特征，
        看未来 forward_days 的涨跌作为"结果"。

        这是冷启动阶段的主要经验来源。
        """
        from .context import ContextAssembler

        if len(df) < window + forward_days:
            return 0

        assembler = ContextAssembler(symbol)
        count = 0

        for i in range(window, len(df) - forward_days, step):
            # 取窗口内的数据
            window_df = df.iloc[i - window : i + 1].copy()

            try:
                context = assembler.assemble(window_df)
            except Exception:
                continue

            # 计算未来收益
            future_close = df["close"].iloc[i + forward_days]
            current_close = df["close"].iloc[i]
            if current_close > 0:
                pnl_pct = (future_close - current_close) / current_close * 100
            else:
                continue

            # 确定动作
            if pnl_pct > 1.0:
                action = "LONG"
            elif pnl_pct < -1.0:
                action = "SHORT"
            else:
                action = "HOLD"

            # 确定趋势阶段
            trend_phase = context.trend_phase.phase

            # 计算最大回撤
            future_prices = df["close"].iloc[i : i + forward_days + 1]
            max_dd = self._calc_max_drawdown(future_prices, direction="long" if action == "LONG" else "short")

            # 创建经验
            exp = Experience(
                experience_id=f"hist_{symbol}_{i}",
                timestamp=str(df.index[i] if hasattr(df.index[i], "isoformat") else df.iloc[i].get("date", i)),
                symbol=symbol,
                context_snapshot=context.to_dict(),
                trend_phase=trend_phase,
                phase_confidence=context.trend_phase.confidence,
                action_taken=action,
                action_reasoning=f"历史模式自动提取（窗口{window}，前瞻{forward_days}天）",
                entry_price=current_close,
                exit_price=future_close,
                pnl_pct=pnl_pct,
                holding_days=forward_days,
                max_drawdown_pct=max_dd,
                max_profit_pct=max(0, (future_prices.max() - current_close) / current_close * 100),
                risk_adjusted_return=pnl_pct / max(max_dd, 0.1),
                feature_vector=context.feature_vector,
            )

            self.add_experience(exp)
            count += 1

        return count

    # ──────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────

    def _build_feature_matrix(self):
        """构建特征矩阵（缓存）"""
        if self._feature_matrix is not None:
            return

        vectors = []
        ids = []
        for exp in self.experiences:
            if exp.feature_vector:
                vectors.append(exp.feature_vector)
                ids.append(exp.experience_id)

        if vectors:
            # 统一长度
            max_len = max(len(v) for v in vectors)
            padded = []
            for v in vectors:
                if len(v) < max_len:
                    v = v + [0.0] * (max_len - len(v))
                padded.append(v)

            self._feature_matrix = np.array(padded)
            self._feature_ids = ids

    def _compute_similarities(self, query_vector: np.ndarray) -> np.ndarray:
        """
        计算相似度

        如果启用增强向量，使用组合相似度（余弦 + 欧氏）
        否则使用传统的余弦相似度
        """
        if self._feature_matrix is None or len(self._feature_matrix) == 0:
            return np.array([])

        # 使用增强向量计算
        if self._enhancer is not None and self.use_enhanced_vector:
            return self._compute_enhanced_similarities(query_vector)

        # 传统余弦相似度
        return self._compute_cosine_similarities(query_vector)

    def _compute_cosine_similarities(self, query_vector: np.ndarray) -> np.ndarray:
        """计算余弦相似度（传统方法）"""
        # 统一长度
        max_len = max(len(query_vector), self._feature_matrix.shape[1])
        if len(query_vector) < max_len:
            query_vector = np.concatenate([query_vector, np.zeros(max_len - len(query_vector))])

        # 余弦相似度
        dot = self._feature_matrix @ query_vector
        norm_matrix = np.linalg.norm(self._feature_matrix, axis=1)
        norm_query = np.linalg.norm(query_vector)

        if norm_query == 0:
            return np.zeros(len(self._feature_matrix))

        similarities = dot / (norm_matrix * norm_query + 1e-10)
        return np.clip(similarities, -1, 1)

    def _compute_enhanced_similarities(self, query_vector: np.ndarray) -> np.ndarray:
        """计算增强相似度（组合余弦 + 欧氏）"""
        similarities = []
        query_list = query_vector.tolist()

        for i in range(len(self._feature_matrix)):
            exp_vector = self._feature_matrix[i].tolist()
            sim = self._enhancer.combined_similarity(query_list, exp_vector)
            similarities.append(sim)

        return np.array(similarities)

    def _compute_time_decay(self) -> np.ndarray:
        """计算时间衰减权重（越新的经验权重越高）"""
        now = datetime.now()
        weights = []

        for exp in self.experiences:
            try:
                exp_time = datetime.fromisoformat(exp.timestamp.replace("Z", "+00:00").split("+")[0])
                days_ago = (now - exp_time).days
                # 半衰期 90 天
                decay = 0.5 ** (days_ago / 90)
                weights.append(decay)
            except (ValueError, AttributeError):
                weights.append(0.5)  # 默认中等权重

        return np.array(weights)

    def _calc_max_drawdown(self, prices: pd.Series, direction: str = "long") -> float:
        """计算最大回撤"""
        if len(prices) < 2:
            return 0.0

        if direction == "long":
            peak = prices.iloc[0]
            max_dd = 0.0
            for p in prices:
                if p > peak:
                    peak = p
                dd = (peak - p) / peak * 100
                if dd > max_dd:
                    max_dd = dd
            return max_dd
        else:
            trough = prices.iloc[0]
            max_dd = 0.0
            for p in prices:
                if p < trough:
                    trough = p
                dd = (p - trough) / trough * 100
                if dd > max_dd:
                    max_dd = dd
            return max_dd

    def _invalidate_cache(self):
        """使特征矩阵缓存失效"""
        self._feature_matrix = None
        self._feature_ids = []

    def _evict_old(self):
        """淘汰最旧的经验"""
        if len(self.experiences) > self.max_experiences:
            self.experiences = self.experiences[-self.max_experiences :]
            self._invalidate_cache()

    # ──────────────────────────────────────────
    # 持久化
    # ──────────────────────────────────────────

    def _save_to_db(self, experience: Experience):
        """保存经验到数据库"""
        if not self.db_path:
            return

        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiences (
                    experience_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    trend_phase TEXT,
                    action_taken TEXT,
                    action_reasoning TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    pnl_pct REAL,
                    holding_days INTEGER,
                    max_drawdown_pct REAL,
                    risk_adjusted_return REAL,
                    feature_vector TEXT,
                    context_snapshot TEXT,
                    full_data TEXT
                )
            """)
            conn.execute(
                """INSERT OR REPLACE INTO experiences
                (experience_id, timestamp, symbol, trend_phase, action_taken,
                 action_reasoning, entry_price, exit_price, pnl_pct,
                 holding_days, max_drawdown_pct, risk_adjusted_return,
                 feature_vector, context_snapshot, full_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    experience.experience_id,
                    experience.timestamp,
                    experience.symbol,
                    experience.trend_phase,
                    experience.action_taken,
                    experience.action_reasoning,
                    experience.entry_price,
                    experience.exit_price,
                    experience.pnl_pct,
                    experience.holding_days,
                    experience.max_drawdown_pct,
                    experience.risk_adjusted_return,
                    json.dumps(experience.feature_vector),
                    json.dumps(experience.context_snapshot),
                    json.dumps(experience.to_dict()),
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # 静默失败，不影响主流程

    def _load_from_db(self):
        """从数据库加载经验"""
        if not self.db_path:
            return

        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT full_data FROM experiences ORDER BY timestamp DESC LIMIT ?", (self.max_experiences,)
            )
            for row in cursor:
                try:
                    data = json.loads(row[0])
                    exp = Experience(**{k: v for k, v in data.items() if k in Experience.__dataclass_fields__})
                    self.experiences.append(exp)
                except Exception:
                    continue
            conn.close()
        except Exception:
            pass  # 表不存在或其他错误，静默处理
