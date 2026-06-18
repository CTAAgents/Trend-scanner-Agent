"""
证券子系统测试

测试 SecuritiesProvider、SecuritiesMarketContext、SecuritiesFactorLibrary、SecuritiesRiskManager
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))


class TestSecuritiesProvider:
    """SecuritiesProvider 测试"""
    
    def test_import(self):
        """测试导入"""
        from securities.provider import SecuritiesProvider
        assert SecuritiesProvider is not None
    
    def test_market_type(self):
        """测试市场类型"""
        from securities.provider import SecuritiesProvider
        
        provider = SecuritiesProvider({})
        assert provider.market_type.value == "securities"
    
    def test_get_symbols(self):
        """测试获取品种列表"""
        from securities.provider import SecuritiesProvider
        
        provider = SecuritiesProvider({})
        symbols = provider.get_symbols()
        
        assert isinstance(symbols, list)
        assert len(symbols) > 0


class TestSecuritiesMarketContext:
    """SecuritiesMarketContext 测试"""
    
    def test_creation(self):
        """测试创建"""
        from securities.market_context import SecuritiesMarketContext
        from core.models import IndicatorSnapshot, TrendPhase, MarketStructure, MomentumState, VolatilityState
        
        context = SecuritiesMarketContext(
            symbol="000001.SZ",
            timestamp="2026-06-18",
            current_price=15.0,
            pe_ratio=10.0,
            pb_ratio=1.2,
            roe=15.0,
            dividend_yield=0.03,
            premium_discount=0.0,
            tracking_error=0.0,
            nav=0.0,
            conversion_premium=0.0,
            pure_bond_value=0.0,
            conversion_price=0.0,
            distribution_yield=0.0,
            nav_premium=0.0,
            indicators=IndicatorSnapshot(
                timestamp="2026-06-18",
                close=15.0,
                high=15.5,
                low=14.5,
                open=14.8,
                volume=5000000.0,
            ),
            trend_phase=TrendPhase(),
            structure=MarketStructure(),
            momentum=MomentumState(),
            volatility=VolatilityState(),
        )
        
        assert context.symbol == "000001.SZ"
        assert context.current_price == 15.0
        assert context.pe_ratio == 10.0


class TestSecuritiesFactorLibrary:
    """SecuritiesFactorLibrary 测试"""
    
    def test_import(self):
        """测试导入"""
        from securities.factor_library import SecuritiesFactorLibrary
        assert SecuritiesFactorLibrary is not None
    
    def test_calculate_valuation_factors(self):
        """测试估值因子计算"""
        from securities.factor_library import SecuritiesFactorLibrary
        
        library = SecuritiesFactorLibrary()
        
        # 创建测试数据
        data = pd.DataFrame({
            "pe": [10, 12, 15],
            "pb": [1.2, 1.3, 1.5],
            "roe": [15, 14, 13],
        })
        
        factors = library.calculate_valuation_factors(data)
        
        assert isinstance(factors, dict)
        assert "pe_percentile" in factors
    
    def test_calculate_momentum_factors(self):
        """测试动量因子计算"""
        from securities.factor_library import SecuritiesFactorLibrary
        
        library = SecuritiesFactorLibrary()
        
        # 创建测试数据
        data = pd.DataFrame({
            "close": [10, 11, 12, 13, 14],
        })
        
        factors = library.calculate_momentum_factors(data)
        
        assert isinstance(factors, dict)
        assert "momentum_5d" in factors


class TestSecuritiesRiskManager:
    """SecuritiesRiskManager 测试"""
    
    def test_import(self):
        """测试导入"""
        from securities.risk_manager import SecuritiesRiskManager
        assert SecuritiesRiskManager is not None
    
    def test_creation(self):
        """测试创建"""
        from securities.risk_manager import SecuritiesRiskManager
        
        config = {
            "t_plus_1": True,
            "limit_up_pct": 0.1,
        }
        
        manager = SecuritiesRiskManager(config)
        assert manager.t_plus_1 is True
        assert manager.limit_up_pct == 0.1
    
    def test_calculate_position_size(self):
        """测试仓位计算"""
        from securities.risk_manager import SecuritiesRiskManager
        
        config = {"t_plus_1": True, "limit_up_pct": 0.1}
        manager = SecuritiesRiskManager(config)
        
        position_size = manager.calculate_position_size(
            signal=0.5,
            capital=100000,
            current_price=15.0,
        )
        
        assert position_size > 0
    
    def test_check_limit(self):
        """测试涨跌停检查"""
        from securities.risk_manager import SecuritiesRiskManager
        
        config = {"t_plus_1": True, "limit_up_pct": 0.1}
        manager = SecuritiesRiskManager(config)
        
        # 未涨停
        assert manager.check_limit(15.0, 14.0) is False
        
        # 涨停
        assert manager.check_limit(15.5, 14.0) is True


class TestSecuritiesStrategy:
    """证券策略测试"""
    
    def test_stock_strategy_import(self):
        """测试股票策略导入"""
        from securities.strategy.stock import StockStrategy
        assert StockStrategy is not None
    
    def test_etf_strategy_import(self):
        """测试ETF策略导入"""
        from securities.strategy.etf import ETFStrategy
        assert ETFStrategy is not None
    
    def test_reits_strategy_import(self):
        """测试REITs策略导入"""
        from securities.strategy.reits import REITsStrategy
        assert REITsStrategy is not None


class TestConvertibleBond:
    """可转债测试"""
    
    def test_strategy_import(self):
        """测试可转债策略导入"""
        from securities.convertible_bond.strategy import ConvertibleBondStrategy
        assert ConvertibleBondStrategy is not None
    
    def test_risk_manager_import(self):
        """测试可转债风控导入"""
        from securities.convertible_bond.risk_manager import ConvertibleBondRiskManager
        assert ConvertibleBondRiskManager is not None


class TestIntegration:
    """集成测试"""
    
    def test_full_workflow(self):
        """测试完整工作流"""
        from securities.provider import SecuritiesProvider
        from securities.risk_manager import SecuritiesRiskManager
        from securities.factor_library import SecuritiesFactorLibrary
        
        # 1. 创建Provider
        provider = SecuritiesProvider({})
        
        # 2. 获取数据
        symbols = provider.get_symbols()
        assert len(symbols) > 0
        
        # 3. 创建因子库
        factor_library = SecuritiesFactorLibrary()
        
        # 4. 创建风控
        risk_manager = SecuritiesRiskManager({"t_plus_1": True, "limit_up_pct": 0.1})
        
        # 5. 计算仓位
        position_size = risk_manager.calculate_position_size(0.5, 100000, 15.0)
        assert position_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
