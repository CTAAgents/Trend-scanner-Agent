"""
论文集成测试

测试基于论文思想的新模块：
- ReturnAttributor (KTD-Fin)
- AuditTrail (TradeArena)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from risk.return_attributor import ReturnAttributor, AttributionResult
from risk.audit_trail import (
    AuditTrail,
    AuditRecord,
    AuditTrailBuilder,
    Observation,
    Planning,
    RiskReview,
    Action,
    Reflection,
)


class TestReturnAttributor:
    """收益归因引擎测试"""
    
    def test_init(self):
        """测试初始化"""
        attributor = ReturnAttributor()
        assert len(attributor.factors) == 6
    
    def test_attribute_basic(self):
        """测试基本归因功能"""
        attributor = ReturnAttributor()
        
        # 创建测试数据
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=100)
        portfolio_returns = pd.Series(np.random.randn(100) * 0.01, index=dates)
        market_returns = pd.Series(np.random.randn(100) * 0.01, index=dates)
        
        result = attributor.attribute(portfolio_returns, market_returns)
        
        assert isinstance(result, AttributionResult)
        assert result.total_return != 0
        assert 0 <= result.r_squared <= 1
    
    def test_attribute_with_correlated_returns(self):
        """测试相关收益的归因"""
        attributor = ReturnAttributor()
        
        # 创建与市场高度相关的组合收益
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=100)
        market_returns = pd.Series(np.random.randn(100) * 0.01, index=dates)
        portfolio_returns = market_returns * 0.8 + np.random.randn(100) * 0.002
        
        result = attributor.attribute(portfolio_returns, market_returns)
        
        # 高度相关的组合应有较高的R²
        assert result.r_squared > 0.5
        # 市场Beta和风格暴露应解释大部分收益
        explained = abs(result.market_beta) + abs(result.style_exposure)
        assert explained > 0
    
    def test_attribution_report(self):
        """测试归因报告生成"""
        attributor = ReturnAttributor()
        
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=100)
        portfolio_returns = pd.Series(np.random.randn(100) * 0.01, index=dates)
        market_returns = pd.Series(np.random.randn(100) * 0.01, index=dates)
        
        result = attributor.attribute(portfolio_returns, market_returns)
        report = attributor.create_attribution_report(result)
        
        assert "收益归因分析" in report
        assert "选股Alpha" in report


class TestAuditTrail:
    """审计轨迹系统测试"""
    
    def test_init(self):
        """测试初始化"""
        trail = AuditTrail()
        assert len(trail.records) == 0
    
    def test_record_and_replay(self):
        """测试记录和重放"""
        trail = AuditTrail()
        
        # 创建审计记录
        builder = AuditTrailBuilder("RB2501")
        record = (
            builder
            .set_observation(
                market_data={"close": 3500, "volume": 10000},
                indicators={"rsi": 55, "macd": 0.5},
                context="日线数据"
            )
            .set_planning(
                reasoning="RSI中性，MACD金叉",
                signal="BUY",
                confidence=0.7,
                target_weights={"RB2501": 0.3}
            )
            .set_risk_review(
                risk_checks=[{"check": "position_limit", "passed": True}],
                decision="APPROVED"
            )
            .set_action(
                orders=[{"symbol": "RB2501", "side": "BUY", "qty": 10}],
                mode="SIMULATED"
            )
            .set_reflection(
                outcome="PROFIT",
                pnl=500.0,
                lessons="趋势确认后入场"
            )
            .build()
        )
        
        # 记录
        record_id = trail.record(record)
        assert record_id == record.record_id
        
        # 重放
        replayed = trail.replay(record_id)
        assert replayed is not None
        assert replayed.planning.signal == "BUY"
    
    def test_verify(self):
        """测试验证功能"""
        trail = AuditTrail()
        
        builder = AuditTrailBuilder("RB2501")
        record = (
            builder
            .set_observation({"close": 3500}, {"rsi": 55})
            .set_planning("测试", "HOLD", 0.5)
            .set_risk_review([], "APPROVED")
            .set_action([], "SIMULATED")
            .set_reflection("NEUTRAL")
            .build()
        )
        
        trail.record(record)
        
        # 验证
        assert trail.verify(record)
    
    def test_timeline(self):
        """测试时间线生成"""
        trail = AuditTrail()
        
        builder = AuditTrailBuilder("RB2501")
        record = (
            builder
            .set_observation({"close": 3500}, {"rsi": 55})
            .set_planning("测试", "BUY", 0.7)
            .set_risk_review([], "APPROVED")
            .set_action([{"side": "BUY"}], "SIMULATED")
            .set_reflection("PROFIT", 100.0)
            .build()
        )
        
        trail.record(record)
        timeline = trail.get_timeline(record.record_id)
        
        assert timeline is not None
        assert len(timeline["timeline"]) == 5
        assert timeline["timeline"][0]["phase"] == "observation"
        assert timeline["timeline"][4]["phase"] == "reflection"


class TestAuditTrailBuilder:
    """审计记录构建器测试"""
    
    def test_build_complete_record(self):
        """测试构建完整记录"""
        builder = AuditTrailBuilder("RB2501")
        
        record = (
            builder
            .set_observation({"close": 3500}, {"rsi": 55})
            .set_planning("测试推理", "BUY", 0.7)
            .set_risk_review([{"check": "test"}], "APPROVED")
            .set_action([{"side": "BUY"}], "SIMULATED")
            .set_reflection("PROFIT", 100.0, "学习到经验")
            .build()
        )
        
        assert record.symbol == "RB2501"
        assert record.planning.signal == "BUY"
        assert record.reflection.outcome == "PROFIT"
    
    def test_build_incomplete_record_fails(self):
        """测试构建不完整记录失败"""
        builder = AuditTrailBuilder("RB2501")
        
        with pytest.raises(ValueError):
            builder.build()  # 缺少必要阶段


class TestIntegration:
    """集成测试"""
    
    def test_attribution_with_audit(self):
        """测试收益归因与审计轨迹集成"""
        # 1. 创建收益归因
        attributor = ReturnAttributor()
        
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=100)
        portfolio_returns = pd.Series(np.random.randn(100) * 0.01, index=dates)
        market_returns = pd.Series(np.random.randn(100) * 0.01, index=dates)
        
        result = attributor.attribute(portfolio_returns, market_returns)
        
        # 2. 创建审计记录
        trail = AuditTrail()
        builder = AuditTrailBuilder("RB2501")
        
        record = (
            builder
            .set_observation({"close": 3500}, {"rsi": 55})
            .set_planning(result.to_prompt_text(), "BUY", 0.7)
            .set_risk_review([{"attribution": result.to_dict()}], "APPROVED")
            .set_action([{"side": "BUY"}], "SIMULATED")
            .set_reflection("PROFIT", result.total_return * 10000)
            .build()
        )
        
        trail.record(record)
        
        # 3. 验证
        replayed = trail.replay(record.record_id)
        assert "选股Alpha" in replayed.planning.reasoning


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
