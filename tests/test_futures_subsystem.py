"""
期货子系统测试

测试 FuturesProvider、FuturesMarketContext、FuturesFactorLibrary、FuturesRiskManager
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))


class TestFuturesProvider:
    """FuturesProvider 测试"""
    
    def test_import(self):
        """测试导入"""
        from futures.provider import FuturesProvider
        assert FuturesProvider is not None
    
    def test_market_type(self):
        """测试市场类型"""
        from futures.provider import FuturesProvider
        
        provider = FuturesProvider({})
        assert provider.market_type.value == "futures"
    
    def test_get_symbols(self):
        """测试获取品种列表"""
        from futures.provider import FuturesProvider
        
        provider = FuturesProvider({})
        symbols = provider.get_symbols()
        
        assert isinstance(symbols, list)
        assert len(symbols) > 0
        assert "RB" in symbols


class TestFuturesMarketContext:
    """FuturesMarketContext 测试"""
    
    def test_creation(self):
        """测试创建"""
        from futures.market_context import FuturesMarketContext
        from core.models import IndicatorSnapshot, TrendPhase, MarketStructure, MomentumState, VolatilityState
        
        context = FuturesMarketContext(
            symbol="RB2609",
            timestamp="2026-06-18",
            current_price=3500.0,
            open_interest=100000.0,
            basis=50.0,
            basis_rate=0.014,
            term_structure={"near": 3500, "far": 3550},
            inventory=1000000.0,
            warehouse_receipt=500000.0,
            indicators=IndicatorSnapshot(
                timestamp="2026-06-18",
                close=3500.0,
                high=3520.0,
                low=3480.0,
                open=3490.0,
                volume=50000.0,
            ),
            trend_phase=TrendPhase(),
            structure=MarketStructure(),
            momentum=MomentumState(),
            volatility=VolatilityState(),
        )
        
        assert context.symbol == "RB2609"
        assert context.current_price == 3500.0
        assert context.open_interest == 100000.0


class TestFuturesFactorLibrary:
    """FuturesFactorLibrary 测试"""
    
    def test_import(self):
        """测试导入"""
        from futures.factor_library import FuturesFactorLibrary
        assert FuturesFactorLibrary is not None
    
    def test_calculate_basis_factors(self):
        """测试基差因子计算"""
        from futures.factor_library import FuturesFactorLibrary
        
        library = FuturesFactorLibrary()
        
        # 创建测试数据
        data = pd.DataFrame({
            "close": [3500, 3510, 3520],
            "spot": [3550, 3560, 3570],
        })
        
        factors = library.calculate_basis_factors(data)
        
        assert isinstance(factors, dict)
        assert "basis" in factors
        assert "basis_rate" in factors
    
    def test_calculate_oi_factors(self):
        """测试持仓量因子计算"""
        from futures.factor_library import FuturesFactorLibrary
        
        library = FuturesFactorLibrary()
        
        # 创建测试数据
        data = pd.DataFrame({
            "close": [3500, 3510, 3520],
            "open_interest": [100000, 105000, 110000],
        })
        
        factors = library.calculate_oi_factors(data)
        
        assert isinstance(factors, dict)
        assert "oi_change" in factors


class TestFuturesRiskManager:
    """FuturesRiskManager 测试"""
    
    def test_import(self):
        """测试导入"""
        from futures.risk_manager import FuturesRiskManager
        assert FuturesRiskManager is not None
    
    def test_creation(self):
        """测试创建"""
        from futures.risk_manager import FuturesRiskManager
        
        config = {
            "margin_rate": 0.1,
            "leverage": 10,
        }
        
        manager = FuturesRiskManager(config)
        assert manager.margin_rate == 0.1
        assert manager.leverage == 10
    
    def test_calculate_position_size(self):
        """测试仓位计算"""
        from futures.risk_manager import FuturesRiskManager
        
        config = {"margin_rate": 0.1, "leverage": 10}
        manager = FuturesRiskManager(config)
        
        position_size = manager.calculate_position_size(
            signal=0.5,
            capital=100000,
            current_price=3500,
        )
        
        assert position_size > 0
    
    def test_calculate_stop_loss(self):
        """测试止损计算"""
        from futures.risk_manager import FuturesRiskManager
        
        config = {"margin_rate": 0.1, "leverage": 10}
        manager = FuturesRiskManager(config)
        
        stop_loss = manager.calculate_stop_loss(
            entry_price=3500,
            signal=1.0,
        )
        
        assert stop_loss < 3500  # 多头止损应在入场价下方
    
    def test_calculate_take_profit(self):
        """测试止盈计算"""
        from futures.risk_manager import FuturesRiskManager
        
        config = {"margin_rate": 0.1, "leverage": 10}
        manager = FuturesRiskManager(config)
        
        take_profit = manager.calculate_take_profit(
            entry_price=3500,
            signal=1.0,
        )
        
        assert take_profit > 3500  # 多头止盈应在入场价上方


class TestFuturesStrategy:
    """期货策略测试"""
    
    def test_trend_strategy_import(self):
        """测试趋势策略导入"""
        from futures.strategy.trend import TrendStrategy
        assert TrendStrategy is not None
    
    def test_carry_strategy_import(self):
        """测试Carry策略导入"""
        from futures.strategy.carry import CarryStrategy
        assert CarryStrategy is not None
    
    def test_arbitrage_strategy_import(self):
        """测试套利策略导入"""
        from futures.strategy.arbitrage import ArbitrageStrategy
        assert ArbitrageStrategy is not None


class TestIntegration:
    """集成测试"""
    
    def test_full_workflow(self):
        """测试完整工作流"""
        from futures.provider import FuturesProvider
        from futures.risk_manager import FuturesRiskManager
        from futures.factor_library import FuturesFactorLibrary
        
        # 1. 创建Provider
        provider = FuturesProvider({})
        
        # 2. 获取数据
        symbols = provider.get_symbols()
        assert len(symbols) > 0
        
        # 3. 创建因子库
        factor_library = FuturesFactorLibrary()
        
        # 4. 创建风控
        risk_manager = FuturesRiskManager({"margin_rate": 0.1, "leverage": 10})
        
        # 5. 计算仓位
        position_size = risk_manager.calculate_position_size(0.5, 100000, 3500)
        assert position_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
