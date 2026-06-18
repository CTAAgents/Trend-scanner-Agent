"""
向量化记忆模块

支持文本语义检索，将记忆转换为向量表示：
1. 文本嵌入：使用 sentence-transformers 将文本转换为向量
2. 向量存储：使用 FAISS 存储和检索向量
3. 语义检索：基于语义相似度检索相关记忆

设计原则：
- 向后兼容：可选启用，不影响现有功能
- 渐进增强：支持多种嵌入模型
- 性能优先：使用 FAISS 加速检索
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np


logger = logging.getLogger(__name__)


# ===========================================================================
# 数据结构定义
# ===========================================================================


@dataclass
class MemoryEntry:
    """记忆条目"""

    memory_id: str
    text: str  # 原始文本
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    category: str = ""  # 记忆类别（experience/lesson/pattern）
    importance: float = 1.0  # 重要性权重 (0-1)
    vector: list[float] | None = None  # 嵌入向量


@dataclass
class SearchResult:
    """搜索结果"""

    memory: MemoryEntry
    score: float  # 相似度分数 (0-1)
    rank: int  # 排名


class MemoryVectorizer:
    """
    记忆向量化器

    将文本记忆转换为向量表示，支持语义检索。

    使用方式：
        vectorizer = MemoryVectorizer()
        vector = vectorizer.encode("市场处于趋势发展阶段")
        results = vectorizer.search("趋势跟踪策略", top_k=5)
    """

    def __init__(self, model_name: str = None, use_gpu: bool = False):
        """
        初始化向量化器

        Args:
            model_name: 嵌入模型名称
                - 默认: 'paraphrase-multilingual-MiniLM-L12-v2' (多语言，384维)
                - 中文优化: 'shibing624/text2vec-base-chinese' (768维)
                - 高性能: 'BAAI/bge-base-zh-v1.5' (768维)
            use_gpu: 是否使用GPU
        """
        self.model_name = model_name or "paraphrase-multilingual-MiniLM-L12-v2"
        self.use_gpu = use_gpu
        self.model = None
        self.dimension = None

        # FAISS 索引
        self.index = None
        self.memories: list[MemoryEntry] = []

        # 延迟加载模型
        self._model_loaded = False

    def _load_model(self):
        """延迟加载嵌入模型"""
        if self._model_loaded:
            return

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device="cuda" if self.use_gpu else "cpu")
            self.dimension = self.model.get_sentence_embedding_dimension()
            self._model_loaded = True
            logger.info(f"Model loaded. Dimension: {self.dimension}")

        except ImportError:
            logger.warning("sentence-transformers not installed. Using fallback encoding.")
            self._model_loaded = True
            self.dimension = 384  # 默认维度

        except Exception as e:
            logger.warning(f"Failed to load model: {e}. Using fallback encoding.")
            self._model_loaded = True
            self.dimension = 384

    def encode(self, text: str) -> list[float]:
        """
        将文本编码为向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        self._load_model()

        if self.model is not None:
            try:
                vector = self.model.encode(text, convert_to_numpy=True)
                return vector.tolist()
            except Exception as e:
                logger.warning(f"Encoding failed: {e}. Using fallback.")

        # 回退方案：简单的哈希向量
        return self._fallback_encode(text)

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """
        批量编码文本

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        self._load_model()

        if self.model is not None:
            try:
                vectors = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
                return [v.tolist() for v in vectors]
            except Exception as e:
                logger.warning(f"Batch encoding failed: {e}. Using fallback.")

        # 回退方案
        return [self._fallback_encode(text) for text in texts]

    def _fallback_encode(self, text: str) -> list[float]:
        """
        回退编码方案（当模型不可用时）

        使用简单的哈希生成伪向量，用于测试和降级。
        """
        import hashlib

        # 确保维度已设置
        if self.dimension is None:
            self.dimension = 384

        # 生成哈希
        hash_obj = hashlib.md5(text.encode("utf-8"))
        hash_bytes = hash_obj.digest()

        # 转换为向量
        vector = []
        for byte in hash_bytes:
            vector.append(byte / 255.0)  # 归一化到 0-1

        # 扩展到目标维度
        while len(vector) < self.dimension:
            vector.extend(vector[: self.dimension - len(vector)])

        return vector[: self.dimension]

    def build_index(self, memories: list[MemoryEntry]):
        """
        构建向量索引

        Args:
            memories: 记忆条目列表
        """
        self._load_model()

        if not memories:
            logger.warning("No memories to index.")
            return

        # 编码所有记忆
        texts = [m.text for m in memories]
        vectors = self.encode_batch(texts)

        # 保存向量到记忆条目
        for memory, vector in zip(memories, vectors):
            memory.vector = vector

        # 构建 FAISS 索引
        self.memories = memories
        self._build_faiss_index(vectors)

        logger.info(f"Built index with {len(memories)} memories.")

    def _build_faiss_index(self, vectors: list[list[float]]):
        """构建 FAISS 索引"""
        try:
            import faiss

            # 转换为 numpy 数组
            vectors_np = np.array(vectors, dtype=np.float32)

            # 创建索引（使用内积相似度）
            self.index = faiss.IndexFlatIP(self.dimension)

            # 归一化向量（用于余弦相似度）
            faiss.normalize_L2(vectors_np)

            # 添加向量到索引
            self.index.add(vectors_np)

            logger.info(f"FAISS index built with {self.index.ntotal} vectors.")

        except ImportError:
            logger.warning("faiss-cpu not installed. Using brute-force search.")
            self.index = None

        except Exception as e:
            logger.warning(f"Failed to build FAISS index: {e}. Using brute-force search.")
            self.index = None

    def search(self, query: str, top_k: int = 10, min_score: float = 0.0) -> list[SearchResult]:
        """
        语义搜索

        Args:
            query: 查询文本
            top_k: 返回数量
            min_score: 最小相似度分数

        Returns:
            搜索结果列表
        """
        if not self.memories:
            logger.warning("No memories indexed. Call build_index() first.")
            return []

        # 编码查询
        query_vector = self.encode(query)

        # 搜索
        if self.index is not None:
            results = self._search_faiss(query_vector, top_k, min_score)
        else:
            results = self._search_brute_force(query_vector, top_k, min_score)

        return results

    def _search_faiss(self, query_vector: list[float], top_k: int, min_score: float) -> list[SearchResult]:
        """使用 FAISS 搜索"""
        import faiss

        # 转换为 numpy 数组
        query_np = np.array([query_vector], dtype=np.float32)
        faiss.normalize_L2(query_np)

        # 搜索
        scores, indices = self.index.search(query_np, top_k)

        # 构建结果
        results = []
        for rank, (idx, score) in enumerate(zip(indices[0], scores[0])):
            if idx >= 0 and score >= min_score:
                results.append(
                    SearchResult(
                        memory=self.memories[idx],
                        score=float(score),
                        rank=rank + 1,
                    )
                )

        return results

    def _search_brute_force(self, query_vector: list[float], top_k: int, min_score: float) -> list[SearchResult]:
        """暴力搜索（回退方案）"""
        query_np = np.array(query_vector)

        # 计算所有相似度
        scores = []
        for i, memory in enumerate(self.memories):
            if memory.vector is not None:
                mem_np = np.array(memory.vector)
                # 余弦相似度
                dot = np.dot(query_np, mem_np)
                norm = np.linalg.norm(query_np) * np.linalg.norm(mem_np)
                score = dot / norm if norm > 0 else 0
                scores.append((i, score))

        # 排序
        scores.sort(key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for rank, (idx, score) in enumerate(scores[:top_k]):
            if score >= min_score:
                results.append(
                    SearchResult(
                        memory=self.memories[idx],
                        score=float(score),
                        rank=rank + 1,
                    )
                )

        return results

    def add_memory(self, memory: MemoryEntry):
        """
        添加单个记忆到索引

        Args:
            memory: 记忆条目
        """
        # 编码
        vector = self.encode(memory.text)
        memory.vector = vector

        # 添加到列表
        self.memories.append(memory)

        # 更新 FAISS 索引
        if self.index is not None:
            try:
                import faiss

                vector_np = np.array([vector], dtype=np.float32)
                faiss.normalize_L2(vector_np)
                self.index.add(vector_np)
            except Exception as e:
                logger.warning(f"Failed to add to FAISS index: {e}")

    def save(self, path: str):
        """
        保存索引到文件

        Args:
            path: 保存路径
        """
        import pickle

        data = {
            "memories": self.memories,
            "dimension": self.dimension,
            "model_name": self.model_name,
        }

        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump(data, f)

        logger.info(f"Saved {len(self.memories)} memories to {path}")

    def load(self, path: str):
        """
        从文件加载索引

        Args:
            path: 文件路径
        """
        import pickle

        with open(path, "rb") as f:
            data = pickle.load(f)

        self.memories = data["memories"]
        self.dimension = data["dimension"]
        self.model_name = data.get("model_name", self.model_name)

        # 重建 FAISS 索引
        vectors = [m.vector for m in self.memories if m.vector is not None]
        if vectors:
            self._build_faiss_index(vectors)

        logger.info(f"Loaded {len(self.memories)} memories from {path}")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_memories": len(self.memories),
            "dimension": self.dimension,
            "model_name": self.model_name,
            "index_type": "FAISS" if self.index is not None else "brute-force",
            "model_loaded": self._model_loaded,
        }


# ===========================================================================
# 便捷函数
# ===========================================================================


def create_vectorizer(model_name: str = None) -> MemoryVectorizer:
    """创建向量化器"""
    return MemoryVectorizer(model_name)


def encode_text(text: str, model_name: str = None) -> list[float]:
    """编码单个文本"""
    vectorizer = MemoryVectorizer(model_name)
    return vectorizer.encode(text)


def search_memories(
    query: str, memories: list[MemoryEntry], top_k: int = 10, model_name: str = None
) -> list[SearchResult]:
    """搜索记忆"""
    vectorizer = MemoryVectorizer(model_name)
    vectorizer.build_index(memories)
    return vectorizer.search(query, top_k)
