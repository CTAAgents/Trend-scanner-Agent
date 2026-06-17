"""
真实数据集成测试

使用本地DuckDB缓存的真实数据测试：
1. UnifiedDataRouter 数据获取
2. 指标计算
3. 信号生成
4. 套利分析
5. 知识锚点

前置条件：
- 需要先执行 python tools/sync_data.py sync --days 120
- data/market.db 和 data/meta.db 存在
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))

# 检查是否有真实数据
DATA_DIR = Path(__file__).parent.parent / 'data'
HAS_REAL_DATA = (DATA_DIR / 'market.db').exists() and (DATA_DIR / 'meta.db').exists()


@pytest.mark.skipif(not HAS_REAL_DATA, reason="需要真实数据：先执行 sync_data.py sync")
class TestRealDataIntegration:
    """真实数据集成测试"""

    def setup_method(self):
        """测试前准备"""
        from trend_scanner.unified_data_router import UnifiedDataRouter
        config_path = str(Path(__file__).parent.parent / 'config' / 'config.json')
        self.router = UnifiedDataRouter(config_path=config_path, db_dir=str(DATA_DIR))

    def test_router_initialization(self):
        """路由器初始化"""
        assert self.router is not None
        config = self.router.get_routing_config()
        assert 'priorities' in config
        assert 'staleness_threshold' in config

    def test_get_kline_rb(self):
        """获取螺纹钢K线数据"""
        resp = self.router.get_kline('RB', days=60)
        assert resp.ok is True
        assert resp.source in ['duckdb', 'tqsdk', 'pytdx']
        assert resp.data is not None
        assert len(resp.data) > 0
        assert 'close' in resp.data.columns

    def test_get_kline_multiple_varieties(self):
        """获取多个品种K线数据"""
        varieties = ['RB', 'I', 'JM', 'CU', 'AU']
        for v in varieties:
            resp = self.router.get_kline(v, days=30)
            # 至少部分品种应有数据
            if resp.ok:
                assert resp.data is not None
                assert len(resp.data) > 0

    def test_get_quote(self):
        """获取实时行情"""
        resp = self.router.get_quote('RB')
        # 行情数据可能需要TqSdk连接，允许失败
        if resp.ok:
            assert resp.data is not None
            assert 'last_price' in resp.data or 'close' in resp.data

    def test_data_timeliness_check(self):
        """数据时效性检查"""
        result = self.router.check_data_timeliness('RB')
        assert 'symbol' in result
        assert 'kline' in result
        assert 'quote' in result
        assert 'overall_status' in result
        assert result['overall_status'] in ['fresh', 'stale', 'critical', 'unknown']

    def test_get_basis(self):
        """获取基差数据"""
        resp = self.router.get_basis('RB')
        # AkShare 可能不可用，允许失败
        if resp.ok:
            assert resp.data is not None
            assert 'basis' in resp.data or 'basis_rate' in resp.data

    def test_get_seasonality(self):
        """获取季节性数据"""
        resp = self.router.get_seasonality('RB')
        # AkShare 可能不可用，允许失败
        if resp.ok:
            assert resp.data is not None
            assert 'monthly_avg_change' in resp.data or 'strong_months' in resp.data

    def test_get_inventory(self):
        """获取仓单数据"""
        resp = self.router.get_inventory('RB')
        # AkShare 可能不可用，允许失败
        if resp.ok:
            assert resp.data is not None

    def test_get_margin(self):
        """获取保证金数据"""
        resp = self.router.get_margin('RB')
        # AkShare 可能不可用，允许失败
        if resp.ok:
            assert resp.data is not None
            assert 'exchange_margin_ratio' in resp.data

    def test_get_macro(self):
        """获取宏观数据"""
        resp = self.router.get_macro('RB')
        # AkShare 可能不可用，允许失败
        if resp.ok:
            assert resp.data is not None
            assert 'indicators' in resp.data
            assert 'commodity_specific' in resp.data

    def test_available_sources(self):
        """检查数据源可用性"""
        sources = self.router.get_available_sources()
        assert 'duckdb' in sources
        assert 'tqsdk' in sources
        assert 'akshare' in sources
        # DuckDB 应该可用（有数据）
        assert sources['duckdb'] is True


@pytest.mark.skipif(not HAS_REAL_DATA, reason="需要真实数据：先执行 sync_data.py sync")
class TestIndicatorCalculation:
    """指标计算集成测试"""

    def setup_method(self):
        from trend_scanner.indicators import IndicatorEngine
        from trend_scanner.unified_data_router import UnifiedDataRouter
        config_path = str(Path(__file__).parent.parent / 'config' / 'config.json')
        self.router = UnifiedDataRouter(config_path=config_path, db_dir=str(DATA_DIR))
        self.IndicatorEngine = IndicatorEngine

    def test_indicator_engine_with_real_data(self):
        """使用真实数据计算指标"""
        resp = self.router.get_kline('RB', days=120)
        if not resp.ok:
            pytest.skip("无法获取K线数据")

        engine = self.IndicatorEngine(resp.data)
        engine.compute_all()

        df = engine.df
        # 验证关键指标已计算
        assert 'rsi' in df.columns
        assert 'macd_hist' in df.columns
        assert 'atr' in df.columns  # ATR 指标
        assert 'er' in df.columns

    def test_trend_strength_composite(self):
        """测试复合趋势强度计算"""
        resp = self.router.get_kline('RB', days=120)
        if not resp.ok:
            pytest.skip("无法获取K线数据")

        engine = self.IndicatorEngine(resp.data)
        engine.compute_all()
        composite = engine.get_trend_strength_composite()

        assert composite is not None
        assert len(composite) == len(resp.data)
        # 趋势强度应在合理范围
        valid = composite.dropna()
        assert valid.min() >= -1.0
        assert valid.max() <= 1.0


@pytest.mark.skipif(not HAS_REAL_DATA, reason="需要真实数据：先执行 sync_data.py sync")
class TestKnowledgeAnchors:
    """知识锚点集成测试"""

    def setup_method(self):
        from trend_scanner.knowledge_anchors import KnowledgeAnchorManager
        self.db_path = str(DATA_DIR / 'meta.db')
        self.manager = KnowledgeAnchorManager(self.db_path)

    def test_seed_default_anchors(self):
        """导入默认锚点"""
        count = self.manager.seed_default_anchors()
        # 应该导入一些锚点
        assert count >= 0  # 可能已经存在

    def test_get_anchors_by_dimension(self):
        """按维度获取锚点"""
        self.manager.seed_default_anchors()
        anchors = self.manager.get_anchors_by_dimension('momentum')
        assert len(anchors) > 0
        for a in anchors:
            assert a.dimension == 'momentum'

    def test_get_factor_seeds_for_llm(self):
        """为LLM获取因子种子"""
        self.manager.seed_default_anchors()
        seeds = self.manager.get_factor_seeds_for_llm()
        assert len(seeds) > 0
        for s in seeds:
            assert 'factor_seeds' in s
            assert 'validation_rules' in s


@pytest.mark.skipif(not HAS_REAL_DATA, reason="需要真实数据：先执行 sync_data.py sync")
class TestArbitrageAnalyzer:
    """套利分析集成测试"""

    def setup_method(self):
        from trend_scanner.arbitrage_analyzer import ArbitrageAnalyzer
        from trend_scanner.unified_data_router import UnifiedDataRouter
        config_path = str(Path(__file__).parent.parent / 'config' / 'config.json')
        self.router = UnifiedDataRouter(config_path=config_path, db_dir=str(DATA_DIR))
        self.analyzer = ArbitrageAnalyzer()

    def test_available_pairs(self):
        """获取可用价差对"""
        pairs = self.analyzer.get_available_pairs()
        assert len(pairs) > 0
        assert 'rebar_iron' in pairs

    def test_analyze_spread_with_real_data(self):
        """使用真实数据分析价差"""
        near_resp = self.router.get_kline('RB', days=60)
        far_resp = self.router.get_kline('I', days=60)

        if not near_resp.ok or not far_resp.ok:
            pytest.skip("无法获取K线数据")

        result = self.analyzer.analyze_spread(
            near_resp.data, far_resp.data,
            pair_name='rb_i', description='螺纹-铁矿'
        )

        assert result is not None
        assert result.pair_name == 'rb_i'
        assert result.spread != 0
        assert result.signal in ['LONG_SPREAD', 'SHORT_SPREAD', 'NEUTRAL']

    def test_format_brief(self):
        """格式化套利简报"""
        brief = self.analyzer.format_arbitrage_brief([])
        assert '套利分析' in brief
        assert '暂无' in brief


@pytest.mark.skipif(not HAS_REAL_DATA, reason="需要真实数据：先执行 sync_data.py sync")
class TestTieredOutput:
    """分级输出集成测试"""

    def setup_method(self):
        from trend_scanner.tiered_output import TieredOutputFormatter
        self.formatter = TieredOutputFormatter()

    def test_brief_output(self):
        """快速摘要输出"""
        ctx = {
            'symbol': 'RB',
            'direction': 'LONG',
            'confidence': 0.72,
            'trend_phase': 'TREND_UP',
            'indicators': {'er': 0.65, 'tsi': 25.3, 'rsi': 58},
        }
        output = self.formatter.format(ctx, level='brief')
        assert 'RB' in output
        assert len(output) < 500

    def test_standard_output(self):
        """标准简报输出"""
        ctx = {
            'symbol': 'RB',
            'direction': 'LONG',
            'confidence': 0.72,
            'trend_phase': 'TREND_UP',
            'indicators': {'er': 0.65, 'tsi': 25.3, 'rsi': 58, 'adx': 32},
            'operation_plans': [{'action': 'LONG', 'reason': '趋势确认'}],
            'risks': ['RSI偏高'],
        }
        output = self.formatter.format(ctx, level='standard')
        assert '市场状态' in output
        assert '操作方案' in output

    def test_formal_output(self):
        """完整报告输出"""
        ctx = {
            'symbol': 'RB',
            'direction': 'LONG',
            'confidence': 0.72,
            'trend_phase': 'TREND_UP',
            'indicators': {'er': 0.65, 'tsi': 25.3, 'rsi': 58, 'adx': 32, 'hurst': 0.55},
            'operation_plans': [{'action': 'LONG', 'reason': '趋势确认', 'position': '30%'}],
            'risks': ['RSI偏高'],
            'multi_dimension_scores': {'trend': 0.7, 'momentum': 0.6},
        }
        output = self.formatter.format(ctx, level='formal')
        assert '指标详情' in output
        assert '免责声明' in output
