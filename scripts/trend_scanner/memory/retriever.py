"""
多路召回检索器

职责：
- 多路召回：向量 + 结构化 + 时间 + 品种
- 相似度计算：组合多种相似度
- 结果排序：综合评分排序

支持的检索路径：
1. 向量相似度检索（粗筛）
2. 结构化条件检索（精筛）
3. 时间相似度（衰减）
4. 品种相似度（匹配）
"""

import math
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class SimilarityCalculator:
    """相似度计算器"""
    
    def __init__(self, weights: Dict[str, float] = None):
        """
        初始化相似度计算器
        
        Args:
            weights: 权重配置，默认：
                - vector_cosine: 0.4（向量余弦相似度）
                - vector_euclidean: 0.2（向量欧氏距离）
                - structural: 0.2（结构化相似度）
                - temporal: 0.1（时间相似度）
                - symbol: 0.1（品种相似度）
        """
        self.weights = weights or {
            'vector_cosine': 0.4,
            'vector_euclidean': 0.2,
            'structural': 0.2,
            'temporal': 0.1,
            'symbol': 0.1
        }
    
    def calculate(
        self,
        query: Dict[str, Any],
        candidate: Dict[str, Any]
    ) -> float:
        """
        计算综合相似度
        
        Args:
            query: 查询上下文
            candidate: 候选经验
        
        Returns:
            综合相似度分数（0-1）
        """
        scores = {}
        
        # 1. 向量余弦相似度
        query_vec = query.get('feature_vector', [])
        cand_vec = candidate.get('feature_vector', [])
        if query_vec and cand_vec:
            scores['vector_cosine'] = self._cosine_similarity(query_vec, cand_vec)
        else:
            scores['vector_cosine'] = 0.0
        
        # 2. 向量欧氏距离（转换为相似度）
        if query_vec and cand_vec:
            euclidean_dist = self._euclidean_distance(query_vec, cand_vec)
            scores['vector_euclidean'] = 1 / (1 + euclidean_dist)
        else:
            scores['vector_euclidean'] = 0.0
        
        # 3. 结构化相似度
        scores['structural'] = self._structural_similarity(query, candidate)
        
        # 4. 时间相似度（指数衰减）
        query_time = query.get('timestamp', '')
        cand_time = candidate.get('timestamp', '')
        scores['temporal'] = self._temporal_similarity(query_time, cand_time)
        
        # 5. 品种相似度
        query_symbol = query.get('symbol', '')
        cand_symbol = candidate.get('symbol', '')
        scores['symbol'] = 1.0 if query_symbol == cand_symbol else 0.3
        
        # 加权求和
        total = sum(
            scores[key] * self.weights.get(key, 0)
            for key in scores
        )
        
        return min(1.0, max(0.0, total))
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if len(vec1) != len(vec2):
            # 填充较短的向量
            max_len = max(len(vec1), len(vec2))
            vec1 = vec1 + [0.0] * (max_len - len(vec1))
            vec2 = vec2 + [0.0] * (max_len - len(vec2))
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _euclidean_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """计算欧氏距离"""
        if len(vec1) != len(vec2):
            max_len = max(len(vec1), len(vec2))
            vec1 = vec1 + [0.0] * (max_len - len(vec1))
            vec2 = vec2 + [0.0] * (max_len - len(vec2))
        
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))
    
    def _structural_similarity(
        self,
        query: Dict[str, Any],
        candidate: Dict[str, Any]
    ) -> float:
        """计算结构化相似度"""
        score = 0.0
        count = 0
        
        # 趋势阶段匹配
        query_phase = query.get('trend_phase', '')
        cand_phase = candidate.get('trend_phase', '')
        if query_phase and cand_phase:
            score += 1.0 if query_phase == cand_phase else 0.3
            count += 1
        
        # 方向匹配
        query_dir = query.get('direction', '')
        cand_dir = candidate.get('direction', '')
        if query_dir and cand_dir:
            score += 1.0 if query_dir == cand_dir else 0.0
            count += 1
        
        # 市场机制匹配
        query_regime = query.get('market_regime', '')
        cand_regime = candidate.get('market_regime', '')
        if query_regime and cand_regime:
            score += 1.0 if query_regime == cand_regime else 0.2
            count += 1
        
        return score / count if count > 0 else 0.5
    
    def _temporal_similarity(self, time1: str, time2: str) -> float:
        """计算时间相似度（指数衰减）"""
        if not time1 or not time2:
            return 0.5
        
        try:
            t1 = datetime.fromisoformat(time1.replace('Z', '+00:00'))
            t2 = datetime.fromisoformat(time2.replace('Z', '+00:00'))
            
            days_diff = abs((t1 - t2).days)
            
            # 半衰期 90 天
            half_life = 90
            decay = math.pow(0.5, days_diff / half_life)
            
            return decay
        except:
            return 0.5


class MultiPathRetriever:
    """多路召回检索器"""
    
    def __init__(self, memory_manager):
        """
        初始化多路召回检索器
        
        Args:
            memory_manager: UnifiedMemoryManager 实例
        """
        self.memory = memory_manager
        self.similarity_calc = SimilarityCalculator()
    
    def retrieve(
        self,
        context: Dict[str, Any],
        top_k: int = 5,
        min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        多路召回相似经验
        
        Args:
            context: 市场上下文
            top_k: 返回数量
            min_similarity: 最小相似度
        
        Returns:
            相似经验列表
        """
        results = []
        
        # 路径1：向量相似度检索
        vector_matches = self._vector_search(context, top_k * 2)
        results.extend(vector_matches)
        
        # 路径2：结构化条件检索
        condition_matches = self._condition_search(context, top_k)
        results.extend(condition_matches)
        
        # 路径3：时间范围检索
        time_matches = self._time_search(context, top_k)
        results.extend(time_matches)
        
        # 去重
        unique_results = self._deduplicate(results)
        
        # 计算综合相似度
        for result in unique_results:
            result['combined_similarity'] = self.similarity_calc.calculate(context, result)
        
        # 过滤和排序
        filtered = [r for r in unique_results if r.get('combined_similarity', 0) >= min_similarity]
        filtered.sort(key=lambda x: x.get('combined_similarity', 0), reverse=True)
        
        return filtered[:top_k]
    
    def _vector_search(
        self,
        context: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """向量相似度检索"""
        feature_vector = context.get('feature_vector', [])
        if not feature_vector:
            return []
        
        # 使用向量存储检索
        matches = self.memory.vector_store.search(
            query_vector=feature_vector,
            top_k=top_k
        )
        
        # 获取完整经验数据
        results = []
        for match in matches:
            experience = self.memory.sqlite_store.get_experience(match['entity_id'])
            if experience:
                experience['vector_similarity'] = match['similarity']
                results.append(experience)
        
        return results
    
    def _condition_search(
        self,
        context: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """结构化条件检索"""
        symbol = context.get('symbol', '')
        trend_phase = context.get('trend_phase', '')
        
        # 按品种检索
        if symbol:
            experiences = self.memory.sqlite_store.get_recent_experiences(
                symbol=symbol,
                limit=top_k
            )
        else:
            experiences = self.memory.sqlite_store.get_recent_experiences(limit=top_k)
        
        # 过滤趋势阶段
        if trend_phase:
            experiences = [
                e for e in experiences
                if e.get('trend_phase') == trend_phase
            ]
        
        return experiences
    
    def _time_search(
        self,
        context: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """时间范围检索"""
        # 获取最近的经验
        experiences = self.memory.sqlite_store.get_recent_experiences(limit=top_k * 2)
        
        # 按时间相似度排序
        query_time = context.get('timestamp', '')
        if query_time:
            for exp in experiences:
                exp_time = exp.get('timestamp', '')
                exp['time_similarity'] = self.similarity_calc._temporal_similarity(query_time, exp_time)
            
            experiences.sort(key=lambda x: x.get('time_similarity', 0), reverse=True)
        
        return experiences[:top_k]
    
    def _deduplicate(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重"""
        seen = set()
        unique = []
        
        for result in results:
            exp_id = result.get('experience_id', '')
            if exp_id and exp_id not in seen:
                seen.add(exp_id)
                unique.append(result)
        
        return unique
