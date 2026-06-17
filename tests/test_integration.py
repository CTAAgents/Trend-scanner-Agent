"""
集成测试

测试因子生命周期、健康监控、治理工作流与现有系统的集成。
"""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.factor_lifecycle import FactorAsset, FactorLifecycleManager, LifecycleState
from trend_scanner.factor_health_monitor import FactorHealthMonitor, HealthStatus
from trend_scanner.factor_graph import FactorProvenanceGraph, NodeType, EdgeType
from trend_scanner.knowledge_ingestion import KnowledgeIngestionPipeline, KnowledgeSource, SourceType
from trend_scanner.factor_governance import FactorGovernanceWorkflow, GovernanceAction, GovernanceStatus


class TestEvolverIntegration:
    """测试 Evolver Agent 集成"""

    def test_lifecycle_manager_init(self):
        """测试生命周期管理器初始化"""
        manager = FactorLifecycleManager()
        assert len(manager.factors) == 0

    def test_health_monitor_init(self):
        """测试健康监控器初始化"""
        manager = FactorLifecycleManager()
        monitor = FactorHealthMonitor(manager)
        assert monitor.lifecycle_manager == manager

    def test_provenance_graph_init(self):
        """测试溯源图初始化"""
        graph = FactorProvenanceGraph()
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0


class TestHeartbeatIntegration:
    """测试心跳监控集成"""

    def test_factor_health_check_function(self):
        """测试因子健康度检查函数"""
        # 导入心跳模块中的函数
        sys.path.insert(0, str(project_root / "tools"))
        from heartbeat import check_factor_health

        # 执行检查
        result = check_factor_health()

        # 验证结果结构
        assert "timestamp" in result
        assert "total_checked" in result
        assert "healthy" in result
        assert "warning" in result
        assert "degraded" in result
        assert "critical" in result


class TestKnowledgeIngestionIntegration:
    """测试知识摄取集成"""

    def test_ingest_and_register(self):
        """测试摄取并注册因子"""
        manager = FactorLifecycleManager()
        pipeline = KnowledgeIngestionPipeline(manager)

        # 摄入论文
        source = KnowledgeSource(
            id="test_paper",
            source_type=SourceType.PAPER,
            title="测试论文",
            content="动量因子研究",
        )
        factors = pipeline.ingest(source)

        # 验证因子已注册
        assert len(manager.factors) >= 1
        assert len(factors) >= 1

    def test_lifecycle_transition(self):
        """测试生命周期转换"""
        manager = FactorLifecycleManager()

        # 创建因子
        factor = FactorAsset(
            id="test_factor",
            name="测试因子",
            code="def factor(df): return df['close'].pct_change(5)",
        )
        manager.register_factor(factor)

        # 推进生命周期
        manager.advance_factor("test_factor", LifecycleState.CANDIDATE, "通过筛选")
        manager.advance_factor("test_factor", LifecycleState.DRAFT, "代码实现")
        manager.advance_factor("test_factor", LifecycleState.VERIFIED, "验证通过")
        manager.advance_factor("test_factor", LifecycleState.RELEASED, "发布")

        assert factor.lifecycle_state == LifecycleState.RELEASED


class TestGovernanceIntegration:
    """测试治理工作流集成"""

    def test_full_governance_cycle(self):
        """测试完整治理周期"""
        manager = FactorLifecycleManager()
        workflow = FactorGovernanceWorkflow(manager)

        # 创建因子
        factor = FactorAsset(
            id="gov_test",
            name="治理测试因子",
            code="def factor(df): return df['close'].pct_change(5)",
            lifecycle_state=LifecycleState.RELEASED,
        )
        manager.register_factor(factor)

        # 提交修改提案
        proposal = workflow.submit_proposal(
            GovernanceAction.MODIFY,
            "gov_test",
            "优化窗口参数",
            changes={"code": "def factor(df): return df['close'].pct_change(10)"},
        )

        # 审核通过
        workflow.review_proposal(proposal.proposal_id, approved=True, reviewer="test_agent")

        # 合并
        workflow.merge_proposal(proposal.proposal_id)

        # 验证
        assert factor.code == "def factor(df): return df['close'].pct_change(10)"
        assert factor.version == 2


class TestProvenanceIntegration:
    """测试溯源图集成"""

    def test_build_and_query(self):
        """测试构建和查询溯源图"""
        graph = FactorProvenanceGraph()

        # 添加节点
        paper = graph.create_node(NodeType.PAPER, "paper_001", "测试论文", {})
        factor = graph.create_node(NodeType.FACTOR, "factor_001", "测试因子", {})
        graph.add_node(paper)
        graph.add_node(factor)

        # 添加关系
        edge = graph.create_edge("paper_001", "factor_001", EdgeType.INSPIRED_BY)
        graph.add_edge(edge)

        # 查询
        neighbors = graph.get_neighbors("factor_001", EdgeType.INSPIRED_BY, "incoming")
        assert len(neighbors) == 1
        assert neighbors[0].id == "paper_001"


class TestEndToEnd:
    """端到端测试"""

    def test_paper_to_factor_to_release(self):
        """测试论文→因子→发布的完整流程"""
        # 1. 初始化系统
        manager = FactorLifecycleManager()
        pipeline = KnowledgeIngestionPipeline(manager)
        health_monitor = FactorHealthMonitor(manager)
        provenance = FactorProvenanceGraph()

        # 2. 摄入论文
        source = KnowledgeSource(
            id="arxiv_test",
            source_type=SourceType.PAPER,
            title="VGRSI论文",
            content="基于可见图的RSI指标",
        )
        factors = pipeline.ingest(source)
        factor = factors[0]

        # 3. 构建溯源图
        paper_node = provenance.create_node(NodeType.PAPER, "arxiv_test", "VGRSI论文", {})
        factor_node = provenance.create_node(NodeType.FACTOR, factor.id, factor.name, {})
        provenance.add_node(paper_node)
        provenance.add_node(factor_node)
        provenance.add_edge(provenance.create_edge("arxiv_test", factor.id, EdgeType.INSPIRED_BY))

        # 4. 推进生命周期
        manager.advance_factor(factor.id, LifecycleState.CANDIDATE, "通过筛选")
        manager.advance_factor(factor.id, LifecycleState.DRAFT, "代码实现")
        manager.advance_factor(factor.id, LifecycleState.VERIFIED, "验证通过")
        manager.advance_factor(factor.id, LifecycleState.RELEASED, "发布")

        # 5. 添加评估指标
        factor.evaluation = {"sharpe": 1.5, "max_drawdown": 0.1, "ic": 0.05, "win_rate": 0.55}

        # 6. 检查健康度
        report = health_monitor.check_factor_health(factor)
        assert report.status in (HealthStatus.HEALTHY, HealthStatus.WARNING)

        # 6. 验证溯源图
        chain = provenance.get_inspiration_chain(factor.id)
        assert len(chain) >= 1

        # 7. 获取统计
        stats = manager.get_statistics()
        assert stats["total_factors"] == 1
        assert stats["active_factors"] == 1
