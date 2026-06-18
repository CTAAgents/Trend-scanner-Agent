"""
向量存储模块

职责：
- 存储和检索向量
- 提供相似度搜索
- 支持多种相似度计算方法

支持的相似度计算：
- 余弦相似度
- 欧氏距离
- 组合相似度（余弦 + 欧氏）
"""

import json
import math
from pathlib import Path
from typing import Any


try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class VectorStore:
    """向量存储"""

    def __init__(self, dim: int = 15, use_faiss: bool = False):
        """
        初始化向量存储

        Args:
            dim: 向量维度
            use_faiss: 是否使用 FAISS（需要安装）
        """
        self.dim = dim
        self.use_faiss = use_faiss

        # 内存存储
        self.vectors: dict[str, dict[str, Any]] = {}

        # FAISS 索引（可选）
        self.faiss_index = None
        if use_faiss:
            try:
                import faiss

                self.faiss_index = faiss.IndexFlatIP(dim)  # 内积相似度
            except ImportError:
                print("[警告] FAISS 未安装，使用内存存储")
                self.use_faiss = False

    def add(self, entity_type: str, entity_id: str, vector: list[float], metadata: dict[str, Any] = None):
        """
        添加向量

        Args:
            entity_type: 实体类型（experience/pattern/rule）
            entity_id: 实体ID
            vector: 向量
            metadata: 元数据
        """
        # 确保向量维度正确
        if len(vector) != self.dim:
            # 填充或截断
            if len(vector) < self.dim:
                vector = vector + [0.0] * (self.dim - len(vector))
            else:
                vector = vector[: self.dim]

        key = f"{entity_type}:{entity_id}"

        self.vectors[key] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "vector": vector,
            "metadata": metadata or {},
        }

        # 更新 FAISS 索引
        if self.use_faiss and self.faiss_index is not None:
            import numpy as np

            vec = np.array([vector], dtype=np.float32)
            self.faiss_index.add(vec)

    def search(
        self, query_vector: list[float], top_k: int = 10, entity_type: str = None, min_similarity: float = 0.0
    ) -> list[dict[str, Any]]:
        """
        搜索相似向量

        Args:
            query_vector: 查询向量
            top_k: 返回数量
            entity_type: 过滤实体类型
            min_similarity: 最小相似度

        Returns:
            相似向量列表
        """
        if not self.vectors:
            return []

        # 确保查询向量维度正确
        if len(query_vector) != self.dim:
            if len(query_vector) < self.dim:
                query_vector = query_vector + [0.0] * (self.dim - len(query_vector))
            else:
                query_vector = query_vector[: self.dim]

        # 计算相似度
        results = []
        for key, data in self.vectors.items():
            # 过滤实体类型
            if entity_type and data["entity_type"] != entity_type:
                continue

            # 计算余弦相似度
            similarity = self._cosine_similarity(query_vector, data["vector"])

            if similarity >= min_similarity:
                results.append(
                    {
                        "entity_type": data["entity_type"],
                        "entity_id": data["entity_id"],
                        "similarity": similarity,
                        "metadata": data["metadata"],
                    }
                )

        # 排序
        results.sort(key=lambda x: x["similarity"], reverse=True)

        return results[:top_k]

    def remove(self, entity_type: str, entity_id: str):
        """移除向量"""
        key = f"{entity_type}:{entity_id}"
        if key in self.vectors:
            del self.vectors[key]

    def clear(self):
        """清空所有向量"""
        self.vectors.clear()
        if self.use_faiss and self.faiss_index is not None:
            import faiss

            self.faiss_index = faiss.IndexFlatIP(self.dim)

    def size(self) -> int:
        """返回向量数量"""
        return len(self.vectors)

    # ========== 相似度计算 ==========

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """计算余弦相似度"""
        if not HAS_NUMPY:
            return self._cosine_similarity_python(vec1, vec2)

        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _cosine_similarity_python(self, vec1: list[float], vec2: list[float]) -> float:
        """纯 Python 实现余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _euclidean_distance(self, vec1: list[float], vec2: list[float]) -> float:
        """计算欧氏距离"""
        if not HAS_NUMPY:
            return self._euclidean_distance_python(vec1, vec2)

        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        return np.linalg.norm(vec1 - vec2)

    def _euclidean_distance_python(self, vec1: list[float], vec2: list[float]) -> float:
        """纯 Python 实现欧氏距离"""
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))

    def combined_similarity(
        self, vec1: list[float], vec2: list[float], cosine_weight: float = 0.6, euclidean_weight: float = 0.4
    ) -> float:
        """
        计算组合相似度

        Args:
            vec1: 向量1
            vec2: 向量2
            cosine_weight: 余弦相似度权重
            euclidean_weight: 欧氏距离权重

        Returns:
            组合相似度
        """
        cosine_sim = self._cosine_similarity(vec1, vec2)
        euclidean_dist = self._euclidean_distance(vec1, vec2)

        # 将欧氏距离转换为相似度（0-1）
        euclidean_sim = 1 / (1 + euclidean_dist)

        return cosine_weight * cosine_sim + euclidean_weight * euclidean_sim

    # ========== 持久化 ==========

    def save(self, path: str):
        """保存到文件"""
        data = {"dim": self.dim, "vectors": self.vectors}

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str):
        """从文件加载"""
        if not Path(path).exists():
            return

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.dim = data.get("dim", self.dim)
        self.vectors = data.get("vectors", {})
