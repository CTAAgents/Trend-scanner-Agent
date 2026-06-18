"""
模块注册中心测试

测试 ModuleRegistry 的核心功能
"""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from core.module_registry import ModuleRegistry, ModuleInfo, get_module, list_modules


class TestModuleRegistry:
    """模块注册中心测试"""
    
    def test_singleton(self):
        """测试单例模式"""
        registry1 = ModuleRegistry()
        registry2 = ModuleRegistry()
        
        assert registry1 is registry2
    
    def test_register_module(self):
        """测试模块注册"""
        registry = ModuleRegistry()
        
        # 检查模块是否已注册
        assert "CrowdingDetector" in registry.list_all()
        assert "ReturnAttributor" in registry.list_all()
        assert "TriadDebateEngine" in registry.list_all()
    
    def test_get_module_info(self):
        """测试获取模块信息"""
        registry = ModuleRegistry()
        
        info = registry.get("CrowdingDetector")
        assert info is not None
        assert info.name == "CrowdingDetector"
        assert info.category == "risk"
    
    def test_get_by_category(self):
        """测试按类别获取模块"""
        registry = ModuleRegistry()
        
        risk_modules = registry.get_by_category("risk")
        assert len(risk_modules) >= 4
        
        reasoning_modules = registry.get_by_category("reasoning")
        assert len(reasoning_modules) >= 4
    
    def test_list_categories(self):
        """测试列出所有类别"""
        registry = ModuleRegistry()
        
        categories = registry.list_categories()
        assert "risk" in categories
        assert "data" in categories
        assert "reasoning" in categories
    
    def test_get_status(self):
        """测试获取模块状态"""
        registry = ModuleRegistry()
        
        status = registry.get_status()
        assert "total_modules" in status
        assert "categories" in status
        assert status["total_modules"] >= 20
    
    def test_get_module_function(self):
        """测试便捷函数"""
        # 测试 get_module 函数
        module = get_module("CrowdingDetector")
        assert module is not None
    
    def test_list_modules_function(self):
        """测试便捷函数"""
        # 测试 list_modules 函数
        modules = list_modules()
        assert "CrowdingDetector" in modules
        assert "TriadDebateEngine" in modules


class TestModuleInfo:
    """模块信息测试"""
    
    def test_init(self):
        """测试初始化"""
        info = ModuleInfo(
            name="TestModule",
            module_path="scripts.risk.crowding_detector",
            description="测试模块",
            category="test",
        )
        
        assert info.name == "TestModule"
        assert info.category == "test"
        assert not info._loaded
    
    def test_load(self):
        """测试模块加载"""
        info = ModuleInfo(
            name="CrowdingDetector",
            module_path="scripts.risk.crowding_detector",
            description="拥挤度检测",
            category="risk",
        )
        
        module = info.load()
        assert module is not None
        assert info._loaded


class TestIntegration:
    """集成测试"""
    
    def test_all_modules_registered(self):
        """测试所有模块都已注册"""
        registry = ModuleRegistry()
        
        # 检查关键模块
        key_modules = [
            "CrowdingDetector",
            "DeploymentRiskEstimator",
            "ReturnAttributor",
            "AuditTrail",
            "DataConflictResolver",
            "AnomalyWeighter",
            "HallucinationDetector",
            "AdaptivePromptRouter",
            "TriadDebateEngine",
            "EvidenceEvaluator",
            "FactorEvolutionEngine",
            "CircuitBreaker",
            "StrategyHealth",
        ]
        
        for module_name in key_modules:
            assert module_name in registry.list_all(), f"模块 {module_name} 未注册"
    
    def test_module_categories(self):
        """测试模块分类"""
        registry = ModuleRegistry()
        
        # 检查各类别模块数量
        risk_modules = registry.get_by_category("risk")
        assert len(risk_modules) >= 4
        
        data_modules = registry.get_by_category("data")
        assert len(data_modules) >= 2
        
        reasoning_modules = registry.get_by_category("reasoning")
        assert len(reasoning_modules) >= 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
