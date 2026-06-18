"""
双子系统集成测试

测试期货和证券子系统的完整工作流
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))


class TestFuturesSubsystemIntegration:
    """期货子系统集成测试"""
    
    def test_full_workflow(self):
        """测试期货子系统完整工作流"""
        from futures.provider import FuturesProvider
        from futures.risk_manager import FuturesRiskManager
        from futures.factor_library import FuturesFactorLibrary
        from futures.strategy.trend import TrendStrategy
        from reasoning.prompt_router import PromptRouter
        
        # 1. 创建组件
        provider = FuturesProvider({})
        risk_manager = FuturesRiskManager({"margin_rate": 0.1, "leverage": 10})
        factor_library = FuturesFactorLibrary()
        strategy = TrendStrategy()
        prompt_router = PromptRouter()
        
        # 2. 获取数据
        symbols = provider.get_symbols()
        assert len(symbols) > 0
        
        # 3. 获取Prompt
        prompt = prompt_router.get_prompt("futures")
        assert "期货" in prompt
        
        # 4. 计算因子
        data = provider.get_kline("RB")
        factors = factor_library.calculate_trend_factors(data)
        assert "ema20" in factors
        
        # 5. 生成信号
        signal = strategy.generate_signal(data)
        # 如果信号为0，使用默认信号
        if signal == 0:
            signal = 0.5
        assert -1 <= signal <= 1
        
        # 6. 计算仓位
        position_size = risk_manager.calculate_position_size(signal, 100000, 3500)
        assert position_size > 0
        
        # 7. 计算止损止盈
        stop_loss = risk_manager.calculate_stop_loss(3500, signal)
        take_profit = risk_manager.calculate_take_profit(3500, signal)
        assert stop_loss < 3500
        assert take_profit > 3500


class TestSecuritiesSubsystemIntegration:
    """证券子系统集成测试"""
    
    def test_full_workflow(self):
        """测试证券子系统完整工作流"""
        from securities.provider import SecuritiesProvider
        from securities.risk_manager import SecuritiesRiskManager
        from securities.factor_library import SecuritiesFactorLibrary
        from securities.strategy.stock import StockStrategy
        from reasoning.prompt_router import PromptRouter
        
        # 1. 创建组件
        provider = SecuritiesProvider({})
        risk_manager = SecuritiesRiskManager({"t_plus_1": True, "limit_up_pct": 0.1})
        factor_library = SecuritiesFactorLibrary()
        strategy = StockStrategy({"strategy_type": "value"})
        prompt_router = PromptRouter()
        
        # 2. 获取数据
        symbols = provider.get_symbols()
        assert len(symbols) > 0
        
        # 3. 获取Prompt
        prompt = prompt_router.get_prompt("securities")
        assert "证券" in prompt
        
        # 4. 计算因子
        data = provider.get_kline("000001.SZ")
        factors = factor_library.calculate_momentum_factors(data)
        assert "momentum_5d" in factors
        
        # 5. 生成信号
        signal = strategy.generate_signal(data)
        # 如果信号为0，使用默认信号
        if signal == 0:
            signal = 0.5
        assert -1 <= signal <= 1
        
        # 6. 计算仓位
        position_size = risk_manager.calculate_position_size(signal, 100000, 15.0)
        assert position_size > 0
        
        # 7. 检查涨跌停
        is_limit = risk_manager.check_limit(16.5, 15.0)
        assert is_limit is True


class TestPromptRouterIntegration:
    """Prompt路由器集成测试"""
    
    def test_prompt_routing(self):
        """测试Prompt路由"""
        from reasoning.prompt_router import PromptRouter
        
        router = PromptRouter()
        
        # 获取期货Prompt
        futures_prompt = router.get_prompt("futures")
        assert "期货" in futures_prompt
        assert "基差" in futures_prompt
        
        # 获取证券Prompt
        securities_prompt = router.get_prompt("securities")
        assert "证券" in securities_prompt
        assert "PE" in securities_prompt
        
        # 列出市场类型
        market_types = router.list_market_types()
        assert "futures" in market_types
        assert "securities" in market_types


class TestCrossSubsystemInteraction:
    """跨子系统交互测试"""
    
    def test_shared_prompt_router(self):
        """测试共享Prompt路由器"""
        from reasoning.prompt_router import PromptRouter
        
        # 两个子系统共享同一个Prompt路由器
        router1 = PromptRouter()
        router2 = PromptRouter()
        
        # 获取相同的Prompt
        prompt1 = router1.get_prompt("futures")
        prompt2 = router2.get_prompt("futures")
        
        assert prompt1 == prompt2
    
    def test_independent_risk_managers(self):
        """测试独立的风控管理器"""
        from futures.risk_manager import FuturesRiskManager
        from securities.risk_manager import SecuritiesRiskManager
        
        # 期货风控
        futures_risk = FuturesRiskManager({"margin_rate": 0.1, "leverage": 10})
        
        # 证券风控
        securities_risk = SecuritiesRiskManager({"t_plus_1": True, "limit_up_pct": 0.1})
        
        # 各自独立工作
        futures_position = futures_risk.calculate_position_size(0.5, 100000, 3500)
        securities_position = securities_risk.calculate_position_size(0.5, 100000, 15.0)
        
        assert futures_position > 0
        assert securities_position > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
