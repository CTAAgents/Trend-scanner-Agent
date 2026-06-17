"""
因子溯源知识图

参考 SkillWiki 的 Provenance Knowledge Graph，构建因子生态系统的关系网络。

节点类型：
- Paper      — 论文（如 arXiv:2605.01300）
- Factor     — 因子（如 VGRSI_A0）
- Strategy   — 策略（如 EMA20+MA60多时间框架）
- Backtest   — 回测记录
- Market     — 市场状态标签（如 衰退期/扩张期）

关系类型：
- inspired_by    — 因子 ← 论文
- evolved_from   — 新因子 ← 旧因子（变异来源）
- composed_with  — 组合因子 ← 多个原子因子
- validated_by   — 因子 ← 回测记录
- degraded_in    — 因子 ← 市场状态
- replaces       — 新因子 ← 旧因子（替代关系）
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class NodeType(str, Enum):
    """节点类型"""

    PAPER = "paper"
    FACTOR = "factor"
    STRATEGY = "strategy"
    BACKTEST = "backtest"
    MARKET = "market"


class EdgeType(str, Enum):
    """关系类型"""

    INSPIRED_BY = "inspired_by"
    EVOLVED_FROM = "evolved_from"
    COMPOSED_WITH = "composed_with"
    VALIDATED_BY = "validated_by"
    DEGRADED_IN = "degraded_in"
    REPLACES = "replaces"
    DEPENDS_ON = "depends_on"


@dataclass
class GraphNode:
    """图节点"""

    id: str
    node_type: NodeType
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "name": self.name,
            "attributes": self.attributes,
            "created_at": self.created_at,
        }


@dataclass
class GraphEdge:
    """图边（关系）"""

    source_id: str
    target_id: str
    edge_type: EdgeType
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "attributes": self.attributes,
            "created_at": self.created_at,
        }


class FactorProvenanceGraph:
    """
    因子溯源知识图

    使用邻接表实现，支持高效的邻居查询和路径追踪。
    """

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self._adjacency: dict[str, list[GraphEdge]] = {}  # 邻接表

    def create_node(self, node_type: NodeType, node_id: str, name: str, attributes: dict[str, Any] = None) -> GraphNode:
        """
        创建节点

        Args:
            node_type: 节点类型
            node_id: 节点ID
            name: 节点名称
            attributes: 节点属性

        Returns:
            创建的节点
        """
        return GraphNode(
            id=node_id,
            node_type=node_type,
            name=name,
            attributes=attributes or {},
        )

    def create_edge(self, source_id: str, target_id: str, edge_type: EdgeType, attributes: dict[str, Any] = None) -> GraphEdge:
        """
        创建边

        Args:
            source_id: 源节点ID
            target_id: 目标节点ID
            edge_type: 边类型
            attributes: 边属性

        Returns:
            创建的边
        """
        return GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            attributes=attributes or {},
        )

    def add_node(self, node: GraphNode) -> None:
        """添加节点"""
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []

    def add_edge(self, edge: GraphEdge) -> None:
        """添加边"""
        # 验证节点存在
        if edge.source_id not in self.nodes:
            raise ValueError(f"源节点不存在: {edge.source_id}")
        if edge.target_id not in self.nodes:
            raise ValueError(f"目标节点不存在: {edge.target_id}")

        self.edges.append(edge)
        self._adjacency[edge.source_id].append(edge)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """获取节点"""
        return self.nodes.get(node_id)

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[EdgeType] = None,
        direction: str = "outgoing",
    ) -> list[GraphNode]:
        """
        获取邻居节点

        Args:
            node_id: 节点ID
            edge_type: 过滤边类型
            direction: outgoing（出边）/ incoming（入边）/ both（双向）

        Returns:
            邻居节点列表
        """
        neighbors = []

        for edge in self.edges:
            if edge_type and edge.edge_type != edge_type:
                continue

            if direction in ("outgoing", "both") and edge.source_id == node_id:
                neighbor = self.nodes.get(edge.target_id)
                if neighbor:
                    neighbors.append(neighbor)

            if direction in ("incoming", "both") and edge.target_id == node_id:
                neighbor = self.nodes.get(edge.source_id)
                if neighbor:
                    neighbors.append(neighbor)

        return neighbors

    def get_inspiration_chain(self, factor_id: str, max_depth: int = 5) -> list[dict[str, Any]]:
        """
        获取因子的灵感链条

        追溯因子的灵感来源（论文 → 因子 → 新因子），同时追踪组合关系。

        Args:
            factor_id: 因子ID
            max_depth: 最大追溯深度

        Returns:
            灵感链条
        """
        chain = []
        visited = set()

        def _trace(current_id: str, depth: int):
            if depth > max_depth or current_id in visited:
                return
            visited.add(current_id)

            # 查找所有入边关系（inspired_by, evolved_from, composed_with）
            for edge in self.edges:
                if edge.target_id == current_id and edge.edge_type in (
                    EdgeType.INSPIRED_BY,
                    EdgeType.EVOLVED_FROM,
                    EdgeType.COMPOSED_WITH,
                ):
                    source_node = self.nodes.get(edge.source_id)
                    if source_node:
                        chain.append(
                            {
                                "factor_id": current_id,
                                "source": source_node.to_dict(),
                                "edge_type": edge.edge_type.value,
                                "depth": depth,
                            }
                        )
                        _trace(edge.source_id, depth + 1)

        _trace(factor_id, 0)
        return chain

    def get_degradation_causes(self, factor_id: str) -> list[dict[str, Any]]:
        """
        获取因子退化原因

        查找因子在哪些市场状态下退化。

        Args:
            factor_id: 因子ID

        Returns:
            退化原因列表
        """
        causes = []

        for edge in self.edges:
            if edge.edge_type == EdgeType.DEGRADED_IN and edge.source_id == factor_id:
                market_node = self.nodes.get(edge.target_id)
                if market_node:
                    causes.append(
                        {
                            "market_state": market_node.to_dict(),
                            "attributes": edge.attributes,
                        }
                    )

        return causes

    def get_composition_tree(self, factor_id: str, max_depth: int = 5) -> dict[str, Any]:
        """
        获取因子的组合树

        追溯组合因子的组成部分。
        注意：COMPOSED_WITH 边的方向是 组件 → 组合因子，
        所以查找入边（source_id 是组件，target_id 是组合因子）。

        Args:
            factor_id: 因子ID
            max_depth: 最大追溯深度

        Returns:
            组合树结构
        """
        node = self.nodes.get(factor_id)
        if node is None:
            return {}

        tree = {"factor": node.to_dict(), "components": []}

        # 查找入边：source_id 是组件，target_id 是当前因子
        for edge in self.edges:
            if edge.edge_type == EdgeType.COMPOSED_WITH and edge.target_id == factor_id:
                component = self.nodes.get(edge.source_id)
                if component:
                    if max_depth > 0:
                        sub_tree = self.get_composition_tree(edge.source_id, max_depth - 1)
                        tree["components"].append(sub_tree)
                    else:
                        tree["components"].append(component.to_dict())

        return tree

    def get_validation_history(self, factor_id: str) -> list[dict[str, Any]]:
        """
        获取因子的验证历史

        Args:
            factor_id: 因子ID

        Returns:
            验证记录列表
        """
        history = []

        for edge in self.edges:
            if edge.edge_type == EdgeType.VALIDATED_BY and edge.source_id == factor_id:
                backtest_node = self.nodes.get(edge.target_id)
                if backtest_node:
                    history.append(
                        {
                            "backtest": backtest_node.to_dict(),
                            "attributes": edge.attributes,
                        }
                    )

        return history

    def export_for_visualization(self) -> dict[str, Any]:
        """
        导出为可视化格式

        Returns:
            包含 nodes 和 edges 的字典
        """
        return {
            "nodes": [
                {
                    "id": node.id,
                    "label": node.name,
                    "type": node.node_type.value,
                    "attributes": node.attributes,
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type.value,
                    "attributes": edge.attributes,
                }
                for edge in self.edges
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FactorProvenanceGraph":
        """从字典创建图"""
        graph = cls()

        for node_data in data.get("nodes", []):
            node = GraphNode(
                id=node_data["id"],
                node_type=NodeType(node_data["node_type"]),
                name=node_data["name"],
                attributes=node_data.get("attributes", {}),
                created_at=node_data.get("created_at", ""),
            )
            graph.add_node(node)

        for edge_data in data.get("edges", []):
            edge = GraphEdge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                edge_type=EdgeType(edge_data["edge_type"]),
                attributes=edge_data.get("attributes", {}),
                created_at=edge_data.get("created_at", ""),
            )
            graph.add_edge(edge)

        return graph

    def get_statistics(self) -> dict[str, Any]:
        """获取图统计信息"""
        node_type_counts = {}
        for node in self.nodes.values():
            t = node.node_type.value
            node_type_counts[t] = node_type_counts.get(t, 0) + 1

        edge_type_counts = {}
        for edge in self.edges:
            t = edge.edge_type.value
            edge_type_counts[t] = edge_type_counts.get(t, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": node_type_counts,
            "edge_types": edge_type_counts,
        }
