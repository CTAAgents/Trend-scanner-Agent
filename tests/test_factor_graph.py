"""
因子溯源图单元测试

测试因子溯源知识图的完整功能。
"""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.factor_graph import (
    EdgeType,
    FactorProvenanceGraph,
    GraphEdge,
    GraphNode,
    NodeType,
)


class TestNodeType:
    """测试节点类型"""

    def test_all_types(self):
        """测试所有节点类型"""
        types = list(NodeType)
        assert len(types) == 5

    def test_type_values(self):
        """测试类型值"""
        assert NodeType.PAPER.value == "paper"
        assert NodeType.FACTOR.value == "factor"
        assert NodeType.STRATEGY.value == "strategy"
        assert NodeType.BACKTEST.value == "backtest"
        assert NodeType.MARKET.value == "market"


class TestEdgeType:
    """测试关系类型"""

    def test_all_types(self):
        """测试所有关系类型"""
        types = list(EdgeType)
        assert len(types) == 7

    def test_type_values(self):
        """测试类型值"""
        assert EdgeType.INSPIRED_BY.value == "inspired_by"
        assert EdgeType.EVOLVED_FROM.value == "evolved_from"
        assert EdgeType.COMPOSED_WITH.value == "composed_with"


class TestGraphNode:
    """测试图节点"""

    def test_create_node(self):
        """测试创建节点"""
        node = GraphNode(
            id="paper_001",
            node_type=NodeType.PAPER,
            name="VGRSI论文",
            attributes={"arxiv_id": "2605.01300"},
        )
        assert node.id == "paper_001"
        assert node.node_type == NodeType.PAPER
        assert node.attributes["arxiv_id"] == "2605.01300"

    def test_default_timestamp(self):
        """测试默认时间戳"""
        node = GraphNode(id="test", node_type=NodeType.FACTOR, name="测试")
        assert node.created_at != ""

    def test_to_dict(self):
        """测试转换为字典"""
        node = GraphNode(
            id="test",
            node_type=NodeType.FACTOR,
            name="测试因子",
            attributes={"category": "momentum"},
        )
        data = node.to_dict()
        assert data["id"] == "test"
        assert data["node_type"] == "factor"
        assert data["attributes"]["category"] == "momentum"


class TestGraphEdge:
    """测试图边"""

    def test_create_edge(self):
        """测试创建边"""
        edge = GraphEdge(
            source_id="paper_001",
            target_id="factor_001",
            edge_type=EdgeType.INSPIRED_BY,
            attributes={"confidence": 0.9},
        )
        assert edge.source_id == "paper_001"
        assert edge.target_id == "factor_001"
        assert edge.edge_type == EdgeType.INSPIRED_BY

    def test_to_dict(self):
        """测试转换为字典"""
        edge = GraphEdge(
            source_id="a",
            target_id="b",
            edge_type=EdgeType.DEPENDS_ON,
        )
        data = edge.to_dict()
        assert data["source_id"] == "a"
        assert data["target_id"] == "b"
        assert data["edge_type"] == "depends_on"


class TestFactorProvenanceGraph:
    """测试因子溯源图"""

    def setup_method(self):
        self.graph = FactorProvenanceGraph()

    def test_add_node(self):
        """测试添加节点"""
        node = GraphNode(id="n1", node_type=NodeType.FACTOR, name="测试")
        self.graph.add_node(node)
        assert self.graph.get_node("n1") is not None

    def test_add_edge(self):
        """测试添加边"""
        n1 = GraphNode(id="n1", node_type=NodeType.PAPER, name="论文")
        n2 = GraphNode(id="n2", node_type=NodeType.FACTOR, name="因子")
        self.graph.add_node(n1)
        self.graph.add_node(n2)

        edge = GraphEdge(
            source_id="n1",
            target_id="n2",
            edge_type=EdgeType.INSPIRED_BY,
        )
        self.graph.add_edge(edge)
        assert len(self.graph.edges) == 1

    def test_add_edge_invalid_node(self):
        """测试添加边时节点不存在"""
        n1 = GraphNode(id="n1", node_type=NodeType.PAPER, name="论文")
        self.graph.add_node(n1)

        with pytest.raises(ValueError, match="目标节点不存在"):
            edge = GraphEdge(
                source_id="n1",
                target_id="nonexistent",
                edge_type=EdgeType.INSPIRED_BY,
            )
            self.graph.add_edge(edge)

    def test_get_neighbors_outgoing(self):
        """测试获取出边邻居"""
        n1 = GraphNode(id="n1", node_type=NodeType.PAPER, name="论文")
        n2 = GraphNode(id="n2", node_type=NodeType.FACTOR, name="因子")
        n3 = GraphNode(id="n3", node_type=NodeType.FACTOR, name="因子2")
        self.graph.add_node(n1)
        self.graph.add_node(n2)
        self.graph.add_node(n3)

        self.graph.add_edge(GraphEdge("n1", "n2", EdgeType.INSPIRED_BY))
        self.graph.add_edge(GraphEdge("n1", "n3", EdgeType.INSPIRED_BY))

        neighbors = self.graph.get_neighbors("n1", direction="outgoing")
        assert len(neighbors) == 2

    def test_get_neighbors_incoming(self):
        """测试获取入边邻居"""
        n1 = GraphNode(id="n1", node_type=NodeType.FACTOR, name="因子1")
        n2 = GraphNode(id="n2", node_type=NodeType.FACTOR, name="因子2")
        n3 = GraphNode(id="n3", node_type=NodeType.PAPER, name="论文")
        self.graph.add_node(n1)
        self.graph.add_node(n2)
        self.graph.add_node(n3)

        self.graph.add_edge(GraphEdge("n3", "n1", EdgeType.INSPIRED_BY))
        self.graph.add_edge(GraphEdge("n3", "n2", EdgeType.INSPIRED_BY))

        neighbors = self.graph.get_neighbors("n3", direction="outgoing")
        assert len(neighbors) == 2

    def test_get_neighbors_filtered(self):
        """测试过滤边类型"""
        n1 = GraphNode(id="n1", node_type=NodeType.FACTOR, name="因子1")
        n2 = GraphNode(id="n2", node_type=NodeType.FACTOR, name="因子2")
        n3 = GraphNode(id="n3", node_type=NodeType.PAPER, name="论文")
        self.graph.add_node(n1)
        self.graph.add_node(n2)
        self.graph.add_node(n3)

        self.graph.add_edge(GraphEdge("n3", "n1", EdgeType.INSPIRED_BY))
        self.graph.add_edge(GraphEdge("n2", "n1", EdgeType.EVOLVED_FROM))

        # 只查 inspired_by
        neighbors = self.graph.get_neighbors(
            "n1", edge_type=EdgeType.INSPIRED_BY, direction="incoming"
        )
        assert len(neighbors) == 1
        assert neighbors[0].id == "n3"

    def test_inspiration_chain(self):
        """测试灵感链条追踪"""
        # 论文 → 因子1 → 因子2
        paper = GraphNode(id="paper", node_type=NodeType.PAPER, name="VGRSI论文")
        f1 = GraphNode(id="f1", node_type=NodeType.FACTOR, name="VGRSI_A0")
        f2 = GraphNode(id="f2", node_type=NodeType.FACTOR, name="VGRSI_Multi")

        self.graph.add_node(paper)
        self.graph.add_node(f1)
        self.graph.add_node(f2)

        self.graph.add_edge(GraphEdge("paper", "f1", EdgeType.INSPIRED_BY))
        self.graph.add_edge(GraphEdge("f1", "f2", EdgeType.EVOLVED_FROM))

        chain = self.graph.get_inspiration_chain("f2")
        assert len(chain) >= 1
        # f2 的灵感来源是 f1
        assert any(c["factor_id"] == "f2" for c in chain)

    def test_degradation_causes(self):
        """测试退化原因追踪"""
        f1 = GraphNode(id="f1", node_type=NodeType.FACTOR, name="因子")
        m1 = GraphNode(
            id="m1",
            node_type=NodeType.MARKET,
            name="衰退期",
            attributes={"recession": True},
        )

        self.graph.add_node(f1)
        self.graph.add_node(m1)

        self.graph.add_edge(
            GraphEdge(
                "f1",
                "m1",
                EdgeType.DEGRADED_IN,
                attributes={"sharpe_drop": 0.5},
            )
        )

        causes = self.graph.get_degradation_causes("f1")
        assert len(causes) == 1
        assert causes[0]["market_state"]["name"] == "衰退期"

    def test_composition_tree(self):
        """测试组合树"""
        composite = GraphNode(id="c1", node_type=NodeType.FACTOR, name="组合因子")
        a1 = GraphNode(id="a1", node_type=NodeType.FACTOR, name="原子因子1")
        a2 = GraphNode(id="a2", node_type=NodeType.FACTOR, name="原子因子2")

        self.graph.add_node(composite)
        self.graph.add_node(a1)
        self.graph.add_node(a2)

        # COMPOSED_WITH 边方向：组件(source) → 组合因子(target)
        self.graph.add_edge(GraphEdge("a1", "c1", EdgeType.COMPOSED_WITH))
        self.graph.add_edge(GraphEdge("a2", "c1", EdgeType.COMPOSED_WITH))

        tree = self.graph.get_composition_tree("c1")
        assert tree["factor"]["name"] == "组合因子"
        assert len(tree["components"]) == 2

    def test_validation_history(self):
        """测试验证历史"""
        f1 = GraphNode(id="f1", node_type=NodeType.FACTOR, name="因子")
        bt1 = GraphNode(
            id="bt1",
            node_type=NodeType.BACKTEST,
            name="回测1",
            attributes={"sharpe": 1.2},
        )
        bt2 = GraphNode(
            id="bt2",
            node_type=NodeType.BACKTEST,
            name="回测2",
            attributes={"sharpe": 0.8},
        )

        self.graph.add_node(f1)
        self.graph.add_node(bt1)
        self.graph.add_node(bt2)

        self.graph.add_edge(
            GraphEdge("f1", "bt1", EdgeType.VALIDATED_BY, attributes={"date": "2026-01"})
        )
        self.graph.add_edge(
            GraphEdge("f1", "bt2", EdgeType.VALIDATED_BY, attributes={"date": "2026-06"})
        )

        history = self.graph.get_validation_history("f1")
        assert len(history) == 2

    def test_export_for_visualization(self):
        """测试导出可视化格式"""
        n1 = GraphNode(id="n1", node_type=NodeType.FACTOR, name="因子")
        n2 = GraphNode(id="n2", node_type=NodeType.PAPER, name="论文")
        self.graph.add_node(n1)
        self.graph.add_node(n2)
        self.graph.add_edge(GraphEdge("n2", "n1", EdgeType.INSPIRED_BY))

        export = self.graph.export_for_visualization()
        assert len(export["nodes"]) == 2
        assert len(export["edges"]) == 1
        assert export["edges"][0]["type"] == "inspired_by"

    def test_to_dict_and_from_dict(self):
        """测试序列化和反序列化"""
        n1 = GraphNode(id="n1", node_type=NodeType.FACTOR, name="因子")
        n2 = GraphNode(id="n2", node_type=NodeType.PAPER, name="论文")
        self.graph.add_node(n1)
        self.graph.add_node(n2)
        self.graph.add_edge(GraphEdge("n2", "n1", EdgeType.INSPIRED_BY))

        data = self.graph.to_dict()
        restored = FactorProvenanceGraph.from_dict(data)

        assert len(restored.nodes) == 2
        assert len(restored.edges) == 1
        assert restored.get_node("n1").name == "因子"

    def test_get_statistics(self):
        """测试获取统计信息"""
        n1 = GraphNode(id="n1", node_type=NodeType.FACTOR, name="f1")
        n2 = GraphNode(id="n2", node_type=NodeType.PAPER, name="p1")
        self.graph.add_node(n1)
        self.graph.add_node(n2)
        self.graph.add_edge(GraphEdge("n2", "n1", EdgeType.INSPIRED_BY))

        stats = self.graph.get_statistics()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
        assert stats["node_types"]["factor"] == 1
        assert stats["node_types"]["paper"] == 1


class TestFullProvenance:
    """测试完整溯源场景"""

    def test_paper_to_factor_chain(self):
        """测试论文→因子→新因子的完整链条"""
        graph = FactorProvenanceGraph()

        # 添加论文
        paper1 = GraphNode(
            id="arxiv_2605_01300",
            node_type=NodeType.PAPER,
            name="Visibility Graphs Can Make Money",
            attributes={"arxiv_id": "2605.01300", "year": 2026},
        )
        paper2 = GraphNode(
            id="arxiv_2604_26747",
            node_type=NodeType.PAPER,
            name="AlphaCrafter",
            attributes={"arxiv_id": "2604.26747", "year": 2026},
        )
        graph.add_node(paper1)
        graph.add_node(paper2)

        # 添加因子
        vgrsi_a0 = GraphNode(
            id="VGRSI_A0",
            node_type=NodeType.FACTOR,
            name="VGRSI均值聚合",
            attributes={"category": "momentum"},
        )
        vgrsi_a1 = GraphNode(
            id="VGRSI_A1",
            node_type=NodeType.FACTOR,
            name="VGRSI比率聚合",
            attributes={"category": "momentum"},
        )
        vgrsi_multi = GraphNode(
            id="VGRSI_Multi",
            node_type=NodeType.FACTOR,
            name="多周期VGRSI一致性",
            attributes={"category": "momentum", "composite": True},
        )
        graph.add_node(vgrsi_a0)
        graph.add_node(vgrsi_a1)
        graph.add_node(vgrsi_multi)

        # 添加策略
        strategy = GraphNode(
            id="trend_strategy_001",
            node_type=NodeType.STRATEGY,
            name="EMA20+MA60多时间框架",
            attributes={"timeframes": ["M1", "M5", "M30"]},
        )
        graph.add_node(strategy)

        # 添加关系
        graph.add_edge(GraphEdge("arxiv_2605_01300", "VGRSI_A0", EdgeType.INSPIRED_BY))
        graph.add_edge(GraphEdge("arxiv_2605_01300", "VGRSI_A1", EdgeType.INSPIRED_BY))
        graph.add_edge(GraphEdge("VGRSI_A0", "VGRSI_Multi", EdgeType.COMPOSED_WITH))
        graph.add_edge(GraphEdge("VGRSI_A1", "VGRSI_Multi", EdgeType.COMPOSED_WITH))
        graph.add_edge(GraphEdge("VGRSI_Multi", "trend_strategy_001", EdgeType.DEPENDS_ON))

        # 验证
        stats = graph.get_statistics()
        assert stats["total_nodes"] == 6
        assert stats["total_edges"] == 5

        # 追溯 VGRSI_Multi 的灵感来源
        chain = graph.get_inspiration_chain("VGRSI_Multi")
        assert len(chain) >= 1

        # 获取组合树
        tree = graph.get_composition_tree("VGRSI_Multi")
        assert len(tree["components"]) == 2

        # 导出可视化
        export = graph.export_for_visualization()
        assert len(export["nodes"]) == 6
        assert len(export["edges"]) == 5
