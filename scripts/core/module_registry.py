"""
模块注册中心

统一管理所有模块的加载和访问，解决孤立模块问题。

核心功能：
1. 模块注册与发现
2. 模块依赖管理
3. 模块生命周期管理
4. 统一访问接口
"""

import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class ModuleInfo:
    """模块信息"""
    
    def __init__(
        self,
        name: str,
        module_path: str,
        description: str,
        category: str,
        dependencies: Optional[List[str]] = None,
        lazy_load: bool = True,
    ):
        self.name = name
        self.module_path = module_path
        self.description = description
        self.category = category
        self.dependencies = dependencies or []
        self.lazy_load = lazy_load
        self._instance = None
        self._loaded = False
    
    def load(self) -> Any:
        """加载模块"""
        if self._loaded and self._instance is not None:
            return self._instance
        
        try:
            import importlib
            module = importlib.import_module(self.module_path)
            self._instance = module
            self._loaded = True
            logger.debug(f"模块加载成功: {self.name}")
            return module
        except ImportError as e:
            logger.warning(f"模块加载失败: {self.name} - {e}")
            return None
    
    def get_instance(self, *args, **kwargs) -> Any:
        """获取模块实例"""
        if self._instance is not None:
            return self._instance
        
        module = self.load()
        if module is None:
            return None
        
        # 尝试获取主类
        class_name = self.name.split(".")[-1]
        if hasattr(module, class_name):
            self._instance = getattr(module, class_name)(*args, **kwargs)
            return self._instance
        
        return module


class ModuleRegistry:
    """
    模块注册中心
    
    统一管理所有模块的加载和访问
    """
    
    _instance = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._modules: Dict[str, ModuleInfo] = {}
        self._categories: Dict[str, List[str]] = {}
        self._initialized = True
        
        # 注册所有模块
        self._register_all_modules()
    
    def _register_all_modules(self):
        """注册所有模块"""
        # 风险模块
        self.register(
            ModuleInfo(
                name="CrowdingDetector",
                module_path="scripts.risk.crowding_detector",
                description="拥挤度检测",
                category="risk",
            )
        )
        self.register(
            ModuleInfo(
                name="DeploymentRiskEstimator",
                module_path="scripts.risk.deployment_risk",
                description="部署风险评估",
                category="risk",
            )
        )
        self.register(
            ModuleInfo(
                name="ReturnAttributor",
                module_path="scripts.risk.return_attributor",
                description="收益归因",
                category="risk",
            )
        )
        self.register(
            ModuleInfo(
                name="AuditTrail",
                module_path="scripts.risk.audit_trail",
                description="审计轨迹",
                category="risk",
            )
        )
        
        # 数据模块
        self.register(
            ModuleInfo(
                name="DataConflictResolver",
                module_path="scripts.data.conflict_resolver",
                description="数据冲突裁决",
                category="data",
            )
        )
        self.register(
            ModuleInfo(
                name="AnomalyWeighter",
                module_path="scripts.data.anomaly_weighter",
                description="异常值分层加权",
                category="data",
            )
        )
        
        # 推理模块
        self.register(
            ModuleInfo(
                name="HallucinationDetector",
                module_path="scripts.reasoning.hallucination_detector",
                description="幻觉检测",
                category="reasoning",
            )
        )
        self.register(
            ModuleInfo(
                name="AdaptivePromptRouter",
                module_path="scripts.reasoning.adaptive_prompt_router",
                description="自适应Prompt路由",
                category="reasoning",
            )
        )
        self.register(
            ModuleInfo(
                name="TriadDebateEngine",
                module_path="scripts.reasoning.triad_debate_engine",
                description="三方辩论引擎",
                category="reasoning",
            )
        )
        self.register(
            ModuleInfo(
                name="EvidenceEvaluator",
                module_path="scripts.reasoning.evidence_evaluator",
                description="论据可靠性评估",
                category="reasoning",
            )
        )
        
        # 进化模块
        self.register(
            ModuleInfo(
                name="FactorEvolutionEngine",
                module_path="scripts.evolution.factor_evolution_engine",
                description="因子进化引擎",
                category="evolution",
            )
        )
        self.register(
            ModuleInfo(
                name="FactorGenerator",
                module_path="scripts.evolution.factor_generator",
                description="因子生成器",
                category="evolution",
            )
        )
        self.register(
            ModuleInfo(
                name="FactorEvaluator",
                module_path="scripts.evolution.factor_evaluator",
                description="因子评估器",
                category="evolution",
            )
        )
        
        # 进化工具模块
        self.register(
            ModuleInfo(
                name="CircuitBreaker",
                module_path="scripts.evolution_tools.circuit_breaker",
                description="熔断器",
                category="evolution_tools",
            )
        )
        self.register(
            ModuleInfo(
                name="StrategyHealth",
                module_path="scripts.evolution_tools.strategy_health",
                description="策略健康检查",
                category="evolution_tools",
            )
        )
        self.register(
            ModuleInfo(
                name="OverfittingDetector",
                module_path="scripts.evolution_tools.overfitting_detector",
                description="过拟合检测",
                category="evolution_tools",
            )
        )
        
        # 策略模块
        self.register(
            ModuleInfo(
                name="TrendScanner",
                module_path="scripts.strategies.trend_following.scanner",
                description="趋势扫描器",
                category="strategies",
            )
        )
        self.register(
            ModuleInfo(
                name="CarryAnalyzer",
                module_path="scripts.strategies.carry.carry_analyzer",
                description="Carry策略分析",
                category="strategies",
            )
        )
        self.register(
            ModuleInfo(
                name="StrategyPortfolio",
                module_path="scripts.strategies.strategy_portfolio",
                description="策略组合",
                category="strategies",
            )
        )
        
        # 指标模块
        self.register(
            ModuleInfo(
                name="IndicatorEngine",
                module_path="scripts.indicators.indicator_engine",
                description="指标引擎",
                category="indicators",
            )
        )
        self.register(
            ModuleInfo(
                name="MultiDimensionScreener",
                module_path="scripts.indicators.multi_dimension_screener",
                description="多维度筛选",
                category="indicators",
            )
        )
        
        # 基本面模块
        self.register(
            ModuleInfo(
                name="NewsCrawler",
                module_path="scripts.fundamental.news_crawler",
                description="新闻抓取",
                category="fundamental",
            )
        )
        self.register(
            ModuleInfo(
                name="SupplyDemandProvider",
                module_path="scripts.fundamental.supply_demand",
                description="供需数据",
                category="fundamental",
            )
        )
        self.register(
            ModuleInfo(
                name="GeopoliticalTracker",
                module_path="scripts.fundamental.geopolitical",
                description="地缘政治追踪",
                category="fundamental",
            )
        )
        
        # RL模块
        self.register(
            ModuleInfo(
                name="AgentPPO",
                module_path="scripts.rl.agent_ppo",
                description="PPO强化学习",
                category="rl",
            )
        )
        self.register(
            ModuleInfo(
                name="RLInterfaceDesigner",
                module_path="scripts.rl.rl_interface_designer",
                description="RL接口设计",
                category="rl",
            )
        )
    
    def register(self, module_info: ModuleInfo):
        """注册模块"""
        self._modules[module_info.name] = module_info
        
        # 按类别分组
        if module_info.category not in self._categories:
            self._categories[module_info.category] = []
        self._categories[module_info.category].append(module_info.name)
    
    def get(self, name: str) -> Optional[ModuleInfo]:
        """获取模块信息"""
        return self._modules.get(name)
    
    def get_module(self, name: str, *args, **kwargs) -> Any:
        """获取模块实例"""
        module_info = self.get(name)
        if module_info is None:
            logger.warning(f"模块未注册: {name}")
            return None
        
        return module_info.get_instance(*args, **kwargs)
    
    def get_by_category(self, category: str) -> List[ModuleInfo]:
        """按类别获取模块"""
        names = self._categories.get(category, [])
        return [self._modules[name] for name in names if name in self._modules]
    
    def list_all(self) -> Dict[str, str]:
        """列出所有模块"""
        return {name: info.description for name, info in self._modules.items()}
    
    def list_categories(self) -> List[str]:
        """列出所有类别"""
        return list(self._categories.keys())
    
    def load_all(self):
        """加载所有模块"""
        for name, info in self._modules.items():
            if not info.lazy_load:
                info.load()
    
    def get_status(self) -> Dict[str, Any]:
        """获取模块状态"""
        status = {
            "total_modules": len(self._modules),
            "categories": len(self._categories),
            "loaded_modules": sum(1 for info in self._modules.values() if info._loaded),
            "by_category": {},
        }
        
        for category, names in self._categories.items():
            status["by_category"][category] = {
                "total": len(names),
                "loaded": sum(1 for name in names if self._modules[name]._loaded),
            }
        
        return status


# 全局模块注册中心
registry = ModuleRegistry()


def get_module(name: str, *args, **kwargs) -> Any:
    """获取模块实例的便捷函数"""
    return registry.get_module(name, *args, **kwargs)


def list_modules() -> Dict[str, str]:
    """列出所有模块的便捷函数"""
    return registry.list_all()
