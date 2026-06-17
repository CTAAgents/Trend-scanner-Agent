"""
知识摄取流水线单元测试

测试从各种知识源提取因子候选的功能。
"""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.factor_lifecycle import FactorAsset, FactorLifecycleManager, LifecycleState
from trend_scanner.knowledge_ingestion import (
    ExtractedPattern,
    KnowledgeIngestionPipeline,
    KnowledgeSource,
    SourceType,
)


class TestSourceType:
    """测试知识源类型"""

    def test_all_types(self):
        """测试所有类型"""
        types = list(SourceType)
        assert len(types) == 5

    def test_type_values(self):
        """测试类型值"""
        assert SourceType.PAPER.value == "paper"
        assert SourceType.TRAJECTORY.value == "trajectory"
        assert SourceType.DOCUMENT.value == "document"
        assert SourceType.SCRIPT.value == "script"
        assert SourceType.PAST_SKILL.value == "past_skill"


class TestKnowledgeSource:
    """测试知识源"""

    def test_create_source(self):
        """测试创建知识源"""
        source = KnowledgeSource(
            id="paper_001",
            source_type=SourceType.PAPER,
            title="测试论文",
            content="这是一个测试",
        )
        assert source.id == "paper_001"
        assert source.source_type == SourceType.PAPER
        assert source.title == "测试论文"

    def test_default_timestamp(self):
        """测试默认时间戳"""
        source = KnowledgeSource(
            id="test",
            source_type=SourceType.DOCUMENT,
            title="测试",
            content="",
        )
        assert source.created_at != ""


class TestKnowledgeIngestionPipeline:
    """测试知识摄取流水线"""

    def setup_method(self):
        self.manager = FactorLifecycleManager()
        self.pipeline = KnowledgeIngestionPipeline(self.manager)

    def test_ingest_paper_momentum(self):
        """测试摄入动量论文"""
        source = KnowledgeSource(
            id="paper_001",
            source_type=SourceType.PAPER,
            title="动量因子研究",
            content="本文研究了动量因子在期货市场的应用，提出了基于价格动量的交易策略。",
        )
        factors = self.pipeline.ingest(source)
        assert len(factors) >= 1
        assert factors[0].lifecycle_state == LifecycleState.RAW
        assert factors[0].source_type == "paper"

    def test_ingest_paper_volume(self):
        """测试摄入成交量论文"""
        source = KnowledgeSource(
            id="paper_002",
            source_type=SourceType.PAPER,
            title="成交量分析",
            content="本文分析了成交量与价格的关系，提出了基于成交量突破的信号。",
        )
        factors = self.pipeline.ingest(source)
        assert len(factors) >= 1

    def test_ingest_paper_generic(self):
        """测试摄入通用论文"""
        source = KnowledgeSource(
            id="paper_003",
            source_type=SourceType.PAPER,
            title="市场微观结构",
            content="本文研究了市场微观结构对价格形成的影响。",
        )
        factors = self.pipeline.ingest(source)
        assert len(factors) >= 1
        # 通用论文应生成unknown类型
        assert factors[0].category == "unknown"

    def test_ingest_trajectory(self):
        """测试摄入交易轨迹"""
        source = KnowledgeSource(
            id="traj_001",
            source_type=SourceType.TRAJECTORY,
            title="回测记录",
            content="EMA金叉入场，RSI超卖确认，持仓3天后离场。",
        )
        factors = self.pipeline.ingest(source)
        assert len(factors) >= 1
        assert factors[0].source_type == "trajectory"

    def test_ingest_document_with_indicators(self):
        """测试摄入包含指标的文档"""
        source = KnowledgeSource(
            id="doc_001",
            source_type=SourceType.DOCUMENT,
            title="技术指标手册",
            content="RSI指标用于判断超买超卖状态。MACD用于判断趋势方向。ATR用于衡量波动率。",
        )
        factors = self.pipeline.ingest(source)
        assert len(factors) >= 1

    def test_ingest_script(self):
        """测试摄入脚本"""
        code = """
def factor(df):
    \"\"\"动量因子\"\"\"
    return df['close'].pct_change(5)
"""
        source = KnowledgeSource(
            id="script_001",
            source_type=SourceType.SCRIPT,
            title="动量因子脚本",
            content=code,
        )
        factors = self.pipeline.ingest(source)
        assert len(factors) == 1
        assert "def factor" in factors[0].code

    def test_ingest_past_skill(self):
        """测试摄入历史因子"""
        source = KnowledgeSource(
            id="skill_001",
            source_type=SourceType.PAST_SKILL,
            title="旧版动量因子",
            content="def factor(df): return df['close'].pct_change(5)",
            metadata={"original_id": "old_factor_001", "logic": "5日收益率"},
        )
        factors = self.pipeline.ingest(source)
        assert len(factors) == 1
        assert factors[0].category == "migration"

    def test_batch_ingest(self):
        """测试批量摄入"""
        sources = [
            KnowledgeSource(
                id=f"paper_{i}",
                source_type=SourceType.PAPER,
                title=f"论文{i}",
                content="动量因子研究" if i % 2 == 0 else "成交量分析",
            )
            for i in range(5)
        ]
        stats = self.pipeline.batch_ingest(sources)
        assert stats["total_sources"] == 5
        assert stats["total_factors"] >= 5

    def test_factor_registered_in_manager(self):
        """测试因子注册到管理器"""
        source = KnowledgeSource(
            id="paper_reg",
            source_type=SourceType.PAPER,
            title="测试注册",
            content="动量因子研究",
        )
        self.pipeline.ingest(source)
        assert len(self.pipeline.lifecycle_manager.factors) >= 1

    def test_get_statistics(self):
        """测试获取统计"""
        source = KnowledgeSource(
            id="paper_stat",
            source_type=SourceType.PAPER,
            title="统计测试",
            content="动量因子研究",
        )
        self.pipeline.ingest(source)
        stats = self.pipeline.get_statistics()
        assert stats["pattern_counter"] >= 1


class TestFullIngestionFlow:
    """测试完整摄取流程"""

    def test_paper_to_factor_lifecycle(self):
        """测试论文→因子→生命周期的完整流程"""
        manager = FactorLifecycleManager()
        pipeline = KnowledgeIngestionPipeline(manager)

        # 摄入论文
        source = KnowledgeSource(
            id="arxiv_2605_01300",
            source_type=SourceType.PAPER,
            title="Visibility Graphs Can Make Money in Financial Markets",
            content="本文提出了基于可见图的RSI指标（VGRSI），利用价格点之间的几何可见关系替代传统RSI的简单价格变化。",
        )
        factors = pipeline.ingest(source)
        assert len(factors) >= 1

        factor = factors[0]

        # 验证初始状态
        assert factor.lifecycle_state == LifecycleState.RAW
        assert factor.source_type == "paper"
        assert factor.source_ref == "arxiv_2605_01300"

        # 推进生命周期
        factor.transition(LifecycleState.CANDIDATE, "通过语法检查")
        factor.transition(LifecycleState.DRAFT, "代码实现完成")
        factor.transition(LifecycleState.VERIFIED, "Walk-Forward验证通过")
        factor.transition(LifecycleState.RELEASED, "进入实盘观察")

        assert factor.lifecycle_state == LifecycleState.RELEASED
        assert len(factor.lifecycle_history) == 4

        # 检查管理器统计
        stats = manager.get_statistics()
        assert stats["total_factors"] == 1
        assert stats["active_factors"] == 1
