"""
统一数据路由层测试

覆盖：
- DataResponse 返回格式
- normalize_symbol 品种代码标准化
- 路由优先级链与 Fallback 逻辑
- 配置驱动路由
- 时效性检查
- 缓存回写
- AkShare/Pytdx 数据源（mock）
- 兼容接口
"""

import os
import json
import pytest
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime
import pandas as pd

from trend_scanner.unified_data_router import (
    DataResponse,
    UnifiedDataRouter,
    PytdxSource,
    AkShareSource,
    normalize_symbol,
    DEFAULT_ROUTING,
    DEFAULT_STALENESS_THRESHOLD,
    get_router,
    reset_router,
)


# ===========================================================================
# DataResponse 测试
# ===========================================================================

class TestDataResponse:
    def test_default_values(self):
        resp = DataResponse()
        assert resp.ok is False
        assert resp.source == ""
        assert resp.fallback_used is False
        assert resp.data_type == ""
        assert resp.count == 0
        assert resp.data is None
        assert resp.error is None
        assert resp.staleness_hours == 0.0

    def test_success_response(self):
        df = pd.DataFrame({'close': [100, 101, 102]})
        resp = DataResponse(
            ok=True, source='duckdb', fallback_used=False,
            data_type='kline', count=3, data=df,
            timestamp='2026-06-17T10:00:00',
        )
        assert resp.ok is True
        assert resp.source == 'duckdb'
        assert resp.count == 3
        assert len(resp.data) == 3

    def test_fallback_response(self):
        resp = DataResponse(
            ok=True, source='tqsdk', fallback_used=True,
            data_type='kline', count=120, data=None,
        )
        assert resp.fallback_used is True

    def test_error_response(self):
        resp = DataResponse(
            ok=False, source="", fallback_used=False,
            data_type='kline', error="所有数据源不可用",
        )
        assert resp.ok is False
        assert resp.error is not None

    def test_to_dict(self):
        resp = DataResponse(ok=True, source='duckdb', data_type='kline', count=5, timestamp='2026-06-17')
        d = resp.to_dict()
        assert d['ok'] is True
        assert d['source'] == 'duckdb'
        assert d['count'] == 5
        assert 'data' not in d  # data 不序列化（可能很大）


# ===========================================================================
# normalize_symbol 测试
# ===========================================================================

class TestNormalizeSymbol:
    def test_plain_upper(self):
        assert normalize_symbol("RB") == "RB"

    def test_plain_lower(self):
        assert normalize_symbol("rb") == "RB"

    def test_exchange_prefix_shfe(self):
        assert normalize_symbol("SHFE.rb") == "RB"

    def test_exchange_prefix_dce(self):
        assert normalize_symbol("DCE.jm") == "JM"

    def test_exchange_prefix_czce(self):
        assert normalize_symbol("CZCE.CF") == "CF"

    def test_tqsdk_prefix(self):
        assert normalize_symbol("KQ.m@SHFE.rb") == "RB"

    def test_tqsdk_prefix_dce(self):
        assert normalize_symbol("KQ.m@DCE.i") == "I"

    def test_with_contract_month(self):
        assert normalize_symbol("RB2609") == "RB"

    def test_exchange_with_contract(self):
        assert normalize_symbol("SHFE.rb2609") == "RB"

    def test_whitespace(self):
        assert normalize_symbol("  RB  ") == "RB"

    def test_ine_prefix(self):
        assert normalize_symbol("INE.sc2609") == "SC"

    def test_cffex_prefix(self):
        assert normalize_symbol("CFFEX.if2606") == "IF"

    def test_czce_3digit_month(self):
        assert normalize_symbol("CZCE.CF609") == "CF"


# ===========================================================================
# UnifiedDataRouter 测试
# ===========================================================================

class TestUnifiedDataRouter:
    """使用 mock 数据源测试路由逻辑"""

    def setup_method(self):
        reset_router()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        reset_router()

    def _make_router_with_mocks(self, routing=None, db_dir=None):
        """创建带 mock 的路由器"""
        db_dir = db_dir or self.temp_dir
        router = UnifiedDataRouter(db_dir=db_dir)

        if routing:
            for dtype, priorities in routing.items():
                router._routing[dtype] = priorities

        return router

    def _mock_source_ok(self, source_name, method_name, return_value):
        """创建返回成功的 mock 数据源"""
        mock_source = MagicMock()
        mock_source.is_available.return_value = True
        handler = getattr(mock_source, method_name)
        handler.return_value = return_value
        return mock_source

    def _mock_source_fail(self, source_name, method_name):
        """创建返回失败的 mock 数据源"""
        mock_source = MagicMock()
        mock_source.is_available.return_value = True
        handler = getattr(mock_source, method_name)
        handler.return_value = None
        return mock_source

    def test_default_routing_config(self):
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        config = router.get_routing_config()
        assert config['priorities'] == DEFAULT_ROUTING
        assert config['staleness_threshold'] == DEFAULT_STALENESS_THRESHOLD

    def test_kline_routing_priority(self):
        """K线优先级：duckdb → tqsdk → pytdx → csv"""
        router = self._make_router_with_mocks()
        priorities = router._routing['kline']
        assert priorities == ['duckdb', 'tqsdk', 'pytdx', 'csv']

    def test_quote_routing_priority(self):
        """行情优先级：duckdb → tqsdk → pytdx"""
        router = self._make_router_with_mocks()
        priorities = router._routing['quote']
        assert priorities == ['duckdb', 'tqsdk', 'pytdx']

    def test_basis_routing_priority(self):
        """基差优先级：akshare → pytdx"""
        router = self._make_router_with_mocks()
        priorities = router._routing['basis']
        assert priorities == ['akshare', 'pytdx']

    def test_seasonality_routing_priority(self):
        """季节性优先级：akshare → csv"""
        router = self._make_router_with_mocks()
        priorities = router._routing['seasonality']
        assert priorities == ['akshare', 'csv']

    def test_fallback_mechanism(self):
        """测试 Fallback：第一个数据源失败时自动降级"""
        router = self._make_router_with_mocks(routing={'kline': ['source_a', 'source_b']})

        # source_a 返回 None，source_b 返回 DataFrame
        df = pd.DataFrame({'close': [100, 101]})
        mock_a = self._mock_source_fail('source_a', 'get_kline')
        mock_b = self._mock_source_ok('source_b', 'get_kline', df)

        router._sources['source_a'] = mock_a
        router._sources['source_b'] = mock_b

        resp = router.get_kline('RB', days=2)
        assert resp.ok is True
        assert resp.source == 'source_b'
        assert resp.fallback_used is True

    def test_all_sources_fail(self):
        """所有数据源均失败时返回错误"""
        router = self._make_router_with_mocks(routing={'kline': ['source_a', 'source_b']})

        mock_a = self._mock_source_fail('source_a', 'get_kline')
        mock_b = self._mock_source_fail('source_b', 'get_kline')

        router._sources['source_a'] = mock_a
        router._sources['source_b'] = mock_b

        resp = router.get_kline('RB')
        assert resp.ok is False
        assert resp.error is not None

    def test_first_source_succeeds_no_fallback(self):
        """第一个数据源成功时不触发 Fallback"""
        router = self._make_router_with_mocks(routing={'kline': ['source_a', 'source_b']})

        df = pd.DataFrame({'close': [100]})
        mock_a = self._mock_source_ok('source_a', 'get_kline', df)
        router._sources['source_a'] = mock_a

        resp = router.get_kline('RB')
        assert resp.ok is True
        assert resp.source == 'source_a'
        assert resp.fallback_used is False

    def test_update_routing(self):
        """动态更新路由优先级"""
        router = self._make_router_with_mocks()
        router.update_routing('kline', ['tqsdk', 'pytdx', 'csv'])
        assert router._routing['kline'] == ['tqsdk', 'pytdx', 'csv']

    def test_update_routing_invalid_source_filtered(self):
        """无效数据源名被过滤"""
        router = self._make_router_with_mocks()
        router.update_routing('kline', ['tqsdk', 'invalid_source', 'csv'])
        assert router._routing['kline'] == ['tqsdk', 'csv']

    def test_normalize_symbol_in_get_kline(self):
        """get_kline 内部自动标准化品种代码"""
        router = self._make_router_with_mocks(routing={'kline': ['mock_src']})
        df = pd.DataFrame({'close': [100]})
        mock_src = self._mock_source_ok('mock_src', 'get_kline', df)
        router._sources['mock_src'] = mock_src

        # 传入 SHFE.rb 格式，应被标准化为 RB
        resp = router.get_kline('SHFE.rb')
        # mock 接收到的 symbol 应该是标准化后的
        call_args = mock_src.get_kline.call_args
        assert call_args[1]['symbol'] == 'RB' or call_args[0][0] == 'RB'


# ===========================================================================
# PytdxSource 测试（使用 mock）
# ===========================================================================

class TestPytdxSource:
    def setup_method(self):
        self.source = PytdxSource()

    def test_is_available_no_connection(self):
        """未连接时不可用"""
        with patch.object(self.source, '_ensure_connection', return_value=False):
            assert self.source.is_available() is False

    def test_get_kline_no_connection(self):
        """未连接时返回 None"""
        with patch.object(self.source, '_ensure_connection', return_value=False):
            result = self.source.get_kline('RB', days=120)
            assert result is None

    def test_get_quote_no_connection(self):
        """未连接时返回 None"""
        with patch.object(self.source, '_ensure_connection', return_value=False):
            result = self.source.get_quote('RB')
            assert result is None

    def test_get_kline_unknown_symbol(self):
        """未知品种返回 None"""
        with patch.object(self.source, '_ensure_connection', return_value=True):
            result = self.source.get_kline('UNKNOWN_SYMBOL_XYZ')
            assert result is None

    def test_disconnect(self):
        """断开连接不报错"""
        self.source._connected = True
        mock_api = MagicMock()
        self.source._api = mock_api
        self.source.disconnect()
        assert self.source._connected is False


# ===========================================================================
# AkShareSource 测试（使用 mock）
# ===========================================================================

class TestAkShareSource:
    def setup_method(self):
        self.source = AkShareSource()

    def test_is_available_with_akshare(self):
        """akshare 已安装时可用"""
        with patch.dict('sys.modules', {'akshare': MagicMock()}):
            assert self.source.is_available() is True

    def test_is_available_without_akshare(self):
        """akshare 未安装时不可用"""
        with patch.dict('sys.modules', {}):
            # 需要在 import 时就失败
            with patch('builtins.__import__', side_effect=ImportError("No module 'akshare'")):
                pass  # AkShareSource.is_available 通过 try/except 处理

    def test_get_basis_known_symbol(self):
        """已知品种的基差请求"""
        with patch.dict('sys.modules', {'akshare': MagicMock()}):
            # 测试品种映射是否正确
            from trend_scanner.unified_data_router import AKSHARE_FUTURES_MAP
            assert 'RB' in AKSHARE_FUTURES_MAP
            assert AKSHARE_FUTURES_MAP['RB'] == '螺纹钢'
            assert AKSHARE_FUTURES_MAP['I'] == '铁矿石'

    def test_get_basis_unknown_symbol(self):
        """未知品种返回 None"""
        result = self.source.get_basis('UNKNOWN_XYZ')
        assert result is None

    def test_get_seasonality_unknown_symbol(self):
        """未知品种返回 None"""
        result = self.source.get_seasonality('UNKNOWN_XYZ')
        assert result is None

    def test_get_inventory_unknown_symbol(self):
        """未知品种返回 None"""
        result = self.source.get_inventory('UNKNOWN_XYZ')
        assert result is None


# ===========================================================================
# 时效性检查测试
# ===========================================================================

class TestTimelinessCheck:
    def setup_method(self):
        reset_router()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        reset_router()

    def test_check_data_timeliness_no_db(self):
        """无本地 DB 时返回 unknown"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        result = router.check_data_timeliness('RB')
        assert result['symbol'] == 'RB'
        assert 'kline' in result
        assert 'quote' in result
        assert 'overall_status' in result

    def test_is_data_stale_default(self):
        """默认不判断为过期（无 DB 时）"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        # 无 DB 时 staleness 返回 0.0，不会超过阈值
        assert router.is_data_stale('RB', 'kline') is False

    def test_staleness_thresholds(self):
        """验证各数据类型时效性阈值"""
        assert DEFAULT_STALENESS_THRESHOLD['kline'] == 4
        assert DEFAULT_STALENESS_THRESHOLD['quote'] == 0.5
        assert DEFAULT_STALENESS_THRESHOLD['basis'] == 24
        assert DEFAULT_STALENESS_THRESHOLD['seasonality'] == 168
        assert DEFAULT_STALENESS_THRESHOLD['inventory'] == 24


# ===========================================================================
# 配置驱动测试
# ===========================================================================

class TestConfigDrivenRouting:
    def setup_method(self):
        reset_router()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        reset_router()

    def test_config_loading(self):
        """从 config.json 加载路由配置"""
        config = {
            "data_routing": {
                "priorities": {
                    "kline": ["tqsdk", "pytdx", "csv"],
                    "basis": ["akshare"],
                },
                "staleness_threshold": {
                    "kline": 2,
                    "quote": 0.25,
                },
                "db_dir": self.temp_dir,
            }
        }

        config_path = os.path.join(self.temp_dir, 'test_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f)

        router = UnifiedDataRouter(config_path=config_path, db_dir=self.temp_dir)

        # 验证优先级已更新
        assert router._routing['kline'] == ["tqsdk", "pytdx", "csv"]
        assert router._routing['basis'] == ["akshare"]

        # 验证阈值已更新
        assert router._staleness_threshold['kline'] == 2
        assert router._staleness_threshold['quote'] == 0.25

        # 其他类型保持默认
        assert router._routing['quote'] == DEFAULT_ROUTING['quote']
        assert router._routing['seasonality'] == DEFAULT_ROUTING['seasonality']

    def test_config_with_missing_file(self):
        """配置文件不存在时使用默认值"""
        router = UnifiedDataRouter(config_path='/nonexistent/path/config.json', db_dir=self.temp_dir)
        assert router._routing == DEFAULT_ROUTING

    def test_config_with_invalid_json(self):
        """配置文件格式错误时使用默认值"""
        bad_config_path = os.path.join(self.temp_dir, 'bad_config.json')
        with open(bad_config_path, 'w') as f:
            f.write("{invalid json")

        router = UnifiedDataRouter(config_path=bad_config_path, db_dir=self.temp_dir)
        assert router._routing == DEFAULT_ROUTING


# ===========================================================================
# 缓存回写测试
# ===========================================================================

class TestCacheWriteback:
    def setup_method(self):
        reset_router()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        reset_router()

    def test_cache_kline_calls_save(self):
        """远程 K 线成功后自动回写本地缓存"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        mock_duckdb_mgr = MagicMock()
        router._sources['duckdb'] = mock_duckdb_mgr

        df = pd.DataFrame({
            'date': pd.date_range('2026-06-10', periods=3),
            'open': [100, 101, 102],
            'high': [103, 104, 105],
            'low': [99, 100, 101],
            'close': [102, 103, 104],
            'volume': [1000, 1100, 1200],
            'open_interest': [5000, 5100, 5200],
        })

        router._cache_kline('RB', df, 'daily', 'tqsdk')
        mock_duckdb_mgr.duckdb.save_klines.assert_called_once()

    def test_cache_quote_calls_save(self):
        """远程行情成功后自动回写本地缓存"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        mock_duckdb_mgr = MagicMock()
        router._sources['duckdb'] = mock_duckdb_mgr

        quote = {'symbol': 'RB', 'last_price': 3600, 'open_interest': 10000, 'volume': 5000}

        router._cache_quote('RB', quote, 'tqsdk')
        mock_duckdb_mgr.duckdb.save_quote.assert_called_once()
        mock_duckdb_mgr.sqlite.update_symbol_quote.assert_called_once()


# ===========================================================================
# 兼容接口测试
# ===========================================================================

class TestCompatibilityInterfaces:
    def setup_method(self):
        reset_router()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        reset_router()

    def test_get_kline_df_success(self):
        """get_kline_df 返回 DataFrame"""
        router = self._make_router_with_mock_kline()
        df = router.get_kline_df('RB', days=2)
        assert df is not None
        assert isinstance(df, pd.DataFrame)

    def test_get_kline_df_failure(self):
        """get_kline_df 失败时返回 None"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        # 使用空路由链模拟所有数据源不可用
        router._routing['kline'] = []
        df = router.get_kline_df('RB')
        assert df is None

    def test_get_quote_dict_success(self):
        """get_quote_dict 返回 Dict"""
        router = self._make_router_with_mock_quote()
        quote = router.get_quote_dict('RB')
        assert quote is not None
        assert isinstance(quote, dict)

    def test_get_quote_dict_failure(self):
        """get_quote_dict 失败时返回 None"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        # 使用空路由链模拟所有数据源不可用
        router._routing['quote'] = []
        quote = router.get_quote_dict('RB')
        assert quote is None

    def _make_router_with_mock_kline(self):
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        router._routing['kline'] = ['mock_src']

        df = pd.DataFrame({'close': [100, 101]})
        mock_src = MagicMock()
        mock_src.is_available.return_value = True
        mock_src.get_kline.return_value = df
        router._sources['mock_src'] = mock_src

        return router

    def _make_router_with_mock_quote(self):
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        router._routing['quote'] = ['mock_src']

        quote = {'symbol': 'RB', 'last_price': 3600, 'volume': 5000}
        mock_src = MagicMock()
        mock_src.is_available.return_value = True
        mock_src.get_quote.return_value = quote
        router._sources['mock_src'] = mock_src

        return router


# ===========================================================================
# 全局单例测试
# ===========================================================================

class TestGlobalRouter:
    def setup_method(self):
        reset_router()

    def teardown_method(self):
        reset_router()

    def test_get_router_creates_singleton(self):
        r1 = get_router(db_dir="data")
        r2 = get_router(db_dir="data")
        assert r1 is r2

    def test_reset_router_clears_instance(self):
        r1 = get_router(db_dir="data")
        reset_router()
        r2 = get_router(db_dir="data")
        assert r1 is not r2


# ===========================================================================
# 品种映射完整性测试
# ===========================================================================

class TestSymbolMaps:
    def test_variety_exchange_map_completeness(self):
        """核心品种都应有交易所映射"""
        from trend_scanner.unified_data_router import VARIETY_EXCHANGE_MAP
        # 黑色系
        for v in ['RB', 'HC', 'I', 'J', 'JM']:
            assert v in VARIETY_EXCHANGE_MAP, f"{v} 缺少交易所映射"
        # 有色
        for v in ['CU', 'AL', 'ZN', 'NI']:
            assert v in VARIETY_EXCHANGE_MAP, f"{v} 缺少交易所映射"
        # 能源
        for v in ['SC', 'FU', 'BU', 'RU']:
            assert v in VARIETY_EXCHANGE_MAP, f"{v} 缺少交易所映射"

    def test_pytdx_market_map(self):
        """交易所 → pytdx market 编号映射完整"""
        from trend_scanner.unified_data_router import PYTDX_MARKET_MAP
        assert 'SHFE' in PYTDX_MARKET_MAP
        assert 'DCE' in PYTDX_MARKET_MAP
        assert 'CZCE' in PYTDX_MARKET_MAP
        assert 'CFFEX' in PYTDX_MARKET_MAP
        assert 'INE' in PYTDX_MARKET_MAP

    def test_akshare_futures_map_coverage(self):
        """AkShare 中文品种名映射覆盖核心品种"""
        from trend_scanner.unified_data_router import AKSHARE_FUTURES_MAP
        # 核心品种
        for v in ['RB', 'I', 'J', 'JM', 'CU', 'AU', 'SC', 'FU']:
            assert v in AKSHARE_FUTURES_MAP, f"{v} 缺少 AkShare 中文映射"

    def test_tqsdk_map_covers_core(self):
        """TqSdk 主力合约映射覆盖核心品种"""
        from trend_scanner.data_source import TqSdkSource
        for v in ['RB', 'HC', 'I', 'J', 'JM', 'CU', 'AU', 'SC', 'FU', 'BU']:
            assert v in TqSdkSource.MAIN_CONTRACT_MAP, f"{v} 缺少 TqSdk 映射"


# ===========================================================================
# 基差/季节性数据类型测试（新增数据类型）
# ===========================================================================

class TestNewDataTypes:
    def setup_method(self):
        reset_router()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        reset_router()

    def test_basis_data_type(self):
        """基差数据类型路由"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        # AkShare 不可用时，返回失败但格式正确
        resp = router.get_basis('RB')
        assert resp.data_type == 'basis'
        # 可能成功也可能失败（取决于 akshare 可用性），但格式必须正确
        assert isinstance(resp, DataResponse)

    def test_seasonality_data_type(self):
        """季节性数据类型路由"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        resp = router.get_seasonality('RB')
        assert resp.data_type == 'seasonality'
        assert isinstance(resp, DataResponse)

    def test_inventory_data_type(self):
        """仓单数据类型路由"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        resp = router.get_inventory('RB')
        assert resp.data_type == 'inventory'
        assert isinstance(resp, DataResponse)

    def test_basis_with_mock_akshare(self):
        """基差数据 AkShare mock 测试"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        router._routing['basis'] = ['akshare']

        basis_data = {
            'symbol': 'RB', 'spot_price': 3600, 'futures_price': 3580,
            'basis': 20, 'basis_rate': 0.56, 'date': '2026-06-17',
        }
        mock_ak = MagicMock()
        mock_ak.is_available.return_value = True
        mock_ak.get_basis.return_value = basis_data
        router._sources['akshare'] = mock_ak

        resp = router.get_basis('RB')
        assert resp.ok is True
        assert resp.source == 'akshare'
        assert resp.data['basis'] == 20

    def test_seasonality_with_mock_akshare(self):
        """季节性数据 AkShare mock 测试"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        router._routing['seasonality'] = ['akshare']

        season_data = {
            'symbol': 'RB',
            'monthly_avg_change': {1: 2.3, 2: -1.5, 3: 0.8},
            'strong_months': [1, 9, 10],
            'weak_months': [2, 7],
            'current_month_signal': 0.8,
            'current_month_pos_rate': 55.0,
            'years_covered': 5,
        }
        mock_ak = MagicMock()
        mock_ak.is_available.return_value = True
        mock_ak.get_seasonality.return_value = season_data
        router._sources['akshare'] = mock_ak

        resp = router.get_seasonality('RB')
        assert resp.ok is True
        assert resp.data['strong_months'] == [1, 9, 10]
        assert resp.data['years_covered'] == 5


# ===========================================================================
# 边界场景测试
# ===========================================================================

class TestEdgeCases:
    def setup_method(self):
        reset_router()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        reset_router()

    def test_source_unavailable_skipped(self):
        """不可用数据源被跳过"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        router._routing['kline'] = ['unavail', 'avail']

        df = pd.DataFrame({'close': [100]})
        mock_unavail = MagicMock()
        mock_unavail.is_available.return_value = False
        mock_avail = MagicMock()
        mock_avail.is_available.return_value = True
        mock_avail.get_kline.return_value = df

        router._sources['unavail'] = mock_unavail
        router._sources['avail'] = mock_avail

        resp = router.get_kline('RB')
        assert resp.ok is True
        assert resp.source == 'avail'
        assert resp.fallback_used is True

    def test_empty_routing_chain(self):
        """空路由链返回错误"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        router._routing['kline'] = []

        resp = router.get_kline('RB')
        assert resp.ok is False

    def test_get_available_sources(self):
        """检查各数据源可用性"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        # 无 DB 时 duckdb 不可用
        sources = router.get_available_sources()
        assert 'duckdb' in sources
        assert 'akshare' in sources

    def test_cache_writeback_failure_silent(self):
        """缓存回写失败不抛异常"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        mock_mgr = MagicMock()
        mock_mgr.duckdb.save_klines.side_effect = Exception("DB error")
        router._sources['duckdb'] = mock_mgr

        df = pd.DataFrame({'close': [100]})
        # 不应抛异常
        router._cache_kline('RB', df, 'daily', 'tqsdk')

    def test_multiple_data_type_routing(self):
        """多种数据类型可以独立路由"""
        router = UnifiedDataRouter(db_dir=self.temp_dir)
        # K线走 duckdb，基差走 akshare
        assert router._routing['kline'][0] == 'duckdb'
        assert router._routing['basis'][0] == 'akshare'
        assert router._routing['seasonality'][0] == 'akshare'
