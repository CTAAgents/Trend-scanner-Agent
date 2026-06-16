"""
趋势跟踪决策辅助系统

系统提供态势研判、风险提示与操作建议，最终决策权在交易者手中。

模块结构：
- models: 数据模型（MarketContext, Experience, Route, TradingBrief 等）
- indicators: 技术指标计算（感知层）
- context: 上下文组装器（感知层输出）
- experience: 经验记忆池（类比推理基础）
- reasoning: 推理引擎（系统大脑）
- brief: 交易决策简报生成器（交互层）
- assistant: 主协调器（交易辅助系统）
- data_store: 数据持久化
"""

# 版本信息
from .__version__ import (
    __version__,
    __version_info__,
    get_version,
    get_version_info,
    format_version,
)

# 数据模型（v3.0 核心）
from .models import (
    MarketContext,
    IndicatorSnapshot,
    MarketStructure,
    MomentumState,
    VolatilityState,
    TrendPhase,
    Experience,
    ExperienceMatch,
    Route,
    Constraint,
    MarketAssessment,
    Uncertainty,
    TradingBrief,
    UserFeedback,
    ScoringFeedback,
)

# 感知层
from .indicators import IndicatorEngine
from .context import ContextAssembler

# 经验层
from .experience import ExperienceMemory

# 推理层
from .reasoning import (
    ReasoningEngine,
    LLMProvider,
    WorkBuddyAgentProvider,
    CustomLLMProvider,
    ConstraintGenerator,
)

# 交互层
from .brief import BriefGenerator, BriefFormatter

# 辩论引擎（路径④）
from .debate_engine import DebateReasoningEngine, create_debate_engine

# 叙事生成器（路径①）
from .narrative_generator import (
    NarrativeGenerator,
    RuleGenerator,
    generate_narrative,
    generate_rules_from_narrative,
)

# 控制变量隔离
from .control_variable import (
    ControlVariableAnalyzer,
    get_system_layers,
    get_fixed_layers,
    get_llm_layers,
    analyze_llm_contribution,
)

# 向量化记忆
from .memory_vectorizer import (
    MemoryVectorizer,
    MemoryEntry,
    SearchResult,
    create_vectorizer,
    encode_text,
    search_memories,
)

# 主协调器
from .navigator import TradingAssistant, TradingAssistantFactory

# 数据存储
from .data_store import DataStore, ConfigManager

# 市场分析
from .market_analysis import (
    MultiIndicatorConsensus,
    TrendPhaseDetector,
    MarketStateClassifier,
    LLMReasoningLayer,
)

# 策略池
from .strategy import StrategyPool

# 主扫描器
from .scanner import TrendScanner, AdaptiveTrendSystem

# 风险管理
from .risk_management import RiskManager, ExitSignalGenerator

# 进化引擎
from .evolution import (
    SelfMonitor,
    WalkForwardOptimizer,
    StrategyWeightAdjuster,
    OverfittingGuard,
    EnhancedEvolutionEngine,
)

# 进化管理器（连接推理架构与自进化能力）
from .evolution_manager import EvolutionManager, EvolutionManagerFactory

# 轨迹分析
from .trajectory_analysis import (
    TradeTrajectoryAnalyzer,
    TradeFaultAttributor,
    StrategyAdapter,
    TradeTrajectory,
    Fault,
    AdaptationProposal,
    AdaptationStatus,
)

# 交易日志
from .trade_journal import (
    TradeJournal,
    PatternDetector,
    RulePromoter,
    TradeJournalEntry,
    RecurringPattern,
    StrategyRule,
    EntryCategory,
)

# 技能反思
from .skill_reflection import (
    SkillAwareReflector,
    SkillReflection,
    ReflectionEvidence,
    GuidanceReinforcement,
    EvidenceType,
    RevisionAction,
)

# 元技能引擎
from .meta_skill_engine import (
    MetaSkillEngine,
    GeneratedSkill,
    SkillEvolution,
    AuditResult,
    AuditReport,
    SkillGenerationPhase,
)

# 过拟合审计
from .overfitting_audit import (
    OverfittingAuditor,
    AuditCheckType,
    AuditSeverity,
    AuditCheck,
)

# 静默旁路检测
from .silent_bypass_detector import (
    SilentBypassDetector,
    BypassReason,
    ActionRecommendation,
    BypassPattern,
    BypassReport,
    StrategyUsageStats,
)

# 分析工具
from .analytics import KPICalculator, TradeAttributor, StateAccuracyTracker

# 打分分析
from .scoring_analytics import ScoringAnalytics

# 权重优化
from .weight_optimizer import WeightOptimizer

# 阈值优化
from .threshold_optimizer import ThresholdOptimizer

# 元学习
from .meta_learner import (
    MetaLearningEngine,
    BayesianScoringOptimizer,
    OptimizationResult,
    ParameterSpace,
)

# 向量增强
from .vector_enhancement import (
    FeatureVector,
    VectorEnhancer,
    MultiGranularityRetriever,
)

# 机制门
from .regime_gate import (
    RegimeGate,
    RegimeAwareRetriever,
    RegimeMatchResult,
)

# 分层机制检测
from .regime_segmenter import (
    RegimeSegment,
    RegimeSegmenter,
    PhaseLabeler,
    HierarchicalRegimeDetector,
)

# 选择性更新
from .selective_update import (
    DecayConfig,
    SelectiveUpdater,
    KnowledgeDistiller,
    ExperiencePoolManager,
)

# 数据源适配器
from .data_source import (
    DataSource,
    TqSdkSource,
    CsvSource,
    DataSourceFactory,
    get_kline,
    get_quote,
    get_active_symbols,
)

# v5.0 因子进化子系统
from .factor_evaluator import (
    FactorEvaluator,
    FactorEvaluationResult,
    BUILTIN_FACTORS,
)
from .factor_executor import FactorExecutor
from .factor_gate import FactorGate, GateDecision
from .factor_evolution_engine import FactorEvolutionEngine, EvolutionResult
from .factor_param_optimizer import FactorParamOptimizer, OptimizationResult
from .seed_factor_pool import SeedFactorPool
from .multi_factor_model import MultiFactorModel, ModelResult
from .factor_experience_db import FactorExperienceDB

# 因子生成与验证
from .factor_generator import (
    FactorGenerator,
    FactorValidator,
    FactorKnowledgeManager,
    FactorResult,
)
from .factor_validator import FactorValidator as FactorCodeValidator
from .llm_factor_client import LLMClient

# 研报解析
from .report_parser import ReportParser

# 信念传播与概念性反馈（FinCon 架构）
from .belief_propagation import BeliefPropagationManager
from .conceptual_feedback import ConceptualFeedbackGenerator

# RL 接口设计（GIFT 架构）
from .rl_interface_designer import RLInterfaceDesigner

# 执行引擎
from .execution import ExecutionEngine, PositionState, RiskGuard, TradeFilter

# 仓位管理
from .position_sizer import PositionSizer

# 止损管理
from .stop_loss import StopLossCalculator

# 组合管理
from .portfolio import PortfolioManager

# 回测框架
from .backtest import WalkForwardBacktester, MonteCarloValidator

# 过拟合检测
from .overfitting_detector import OverfittingDetector

# 策略健康度
from .strategy_health import StrategyHealthChecker

# 宏观状态检测
from .macro_state import MacroStateDetector

# 记忆桥接器
from .memory_bridge import MemoryBridge

# 交易记录（兼容旧版测试）
from .models import TradeRecord, TradeSignal, TrendPhaseInfo

__version__ = "3.0.0"
__all__ = [
    # 版本信息
    "__version__", "__version_info__",
    "get_version", "get_version_info", "format_version",
    # 数据模型（v3.0 核心）
    "MarketContext", "IndicatorSnapshot", "MarketStructure",
    "MomentumState", "VolatilityState", "TrendPhase",
    "Experience", "ExperienceMatch",
    "Route", "Constraint", "MarketAssessment", "Uncertainty",
    "TradingBrief", "UserFeedback", "ScoringFeedback",
    # 兼容旧版测试
    "TradeRecord", "TradeSignal", "TrendPhaseInfo",
    # 感知层
    "IndicatorEngine", "ContextAssembler",
    # 经验层
    "ExperienceMemory",
    # 推理层
    "ReasoningEngine", "LLMProvider", "WorkBuddyAgentProvider",
    "CustomLLMProvider", "ConstraintGenerator",
    # 交互层
    "BriefGenerator", "BriefFormatter",
    # 辩论引擎
    "DebateReasoningEngine", "create_debate_engine",
    # 叙事生成器
    "NarrativeGenerator", "RuleGenerator",
    "generate_narrative", "generate_rules_from_narrative",
    # 控制变量隔离
    "ControlVariableAnalyzer",
    "get_system_layers", "get_fixed_layers", "get_llm_layers",
    "analyze_llm_contribution",
    # 向量化记忆
    "MemoryVectorizer", "MemoryEntry", "SearchResult",
    "create_vectorizer", "encode_text", "search_memories",
    # 主协调器
    "TradingAssistant", "TradingAssistantFactory",
    # 数据存储
    "DataStore", "ConfigManager",
    # 市场分析
    "MultiIndicatorConsensus", "TrendPhaseDetector", "MarketStateClassifier",
    "LLMReasoningLayer",
    # 策略池
    "StrategyPool",
    # 主扫描器
    "TrendScanner", "AdaptiveTrendSystem",
    # 风险管理
    "RiskManager", "ExitSignalGenerator",
    # 进化引擎
    "SelfMonitor", "WalkForwardOptimizer", "StrategyWeightAdjuster",
    "OverfittingGuard", "EnhancedEvolutionEngine",
    # 进化管理器
    "EvolutionManager", "EvolutionManagerFactory",
    # 轨迹分析
    "TradeTrajectoryAnalyzer", "TradeFaultAttributor", "StrategyAdapter",
    "TradeTrajectory", "Fault", "AdaptationProposal", "AdaptationStatus",
    # 交易日志
    "TradeJournal", "PatternDetector", "RulePromoter",
    "TradeJournalEntry", "RecurringPattern", "StrategyRule", "EntryCategory",
    # 技能反思
    "SkillAwareReflector", "SkillReflection", "ReflectionEvidence",
    "GuidanceReinforcement", "EvidenceType", "RevisionAction",
    # 元技能引擎
    "MetaSkillEngine", "GeneratedSkill", "SkillEvolution",
    "AuditResult", "AuditReport", "SkillGenerationPhase",
    # 过拟合审计
    "OverfittingAuditor", "AuditCheckType", "AuditSeverity", "AuditCheck",
    # 静默旁路检测
    "SilentBypassDetector", "BypassReason", "ActionRecommendation",
    "BypassPattern", "BypassReport", "StrategyUsageStats",
    # 分析工具
    "KPICalculator", "TradeAttributor", "StateAccuracyTracker",
    # 打分分析
    "ScoringAnalytics",
    # 权重优化
    "WeightOptimizer",
    # 阈值优化
    "ThresholdOptimizer",
    # 元学习
    "MetaLearningEngine", "BayesianScoringOptimizer",
    "OptimizationResult", "ParameterSpace",
    # 向量增强
    "FeatureVector", "VectorEnhancer", "MultiGranularityRetriever",
    # 机制门
    "RegimeGate", "RegimeAwareRetriever", "RegimeMatchResult",
    # 分层机制检测
    "RegimeSegment", "RegimeSegmenter", "PhaseLabeler", "HierarchicalRegimeDetector",
    # 选择性更新
    "DecayConfig", "SelectiveUpdater", "KnowledgeDistiller", "ExperiencePoolManager",
    # 数据源适配器
    "DataSource", "TqSdkSource", "CsvSource", "DataSourceFactory",
    "get_kline", "get_quote", "get_active_symbols",
    # v5.0 因子进化子系统
    "FactorEvaluator", "FactorEvaluationResult", "BUILTIN_FACTORS",
    "FactorExecutor",
    "FactorGate", "GateDecision",
    "FactorEvolutionEngine", "EvolutionResult",
    "FactorParamOptimizer", "OptimizationResult",
    "SeedFactorPool",
    "MultiFactorModel", "ModelResult",
    "FactorExperienceDB",
    # 因子生成与验证
    "FactorGenerator", "FactorValidator", "FactorKnowledgeManager", "FactorResult",
    "FactorCodeValidator",
    "LLMClient",
    # 研报解析
    "ReportParser",
    # 信念传播与概念性反馈
    "BeliefPropagationManager",
    "ConceptualFeedbackManager",
    # RL 接口设计
    "RLInterfaceDesigner",
    # 执行引擎
    "ExecutionEngine", "PositionState", "RiskGuard", "TradeFilter",
    # 仓位管理
    "PositionSizer",
    # 止损管理
    "StopLossCalculator",
    # 组合管理
    "PortfolioManager",
    # 回测框架
    "WalkForwardBacktester", "MonteCarloValidator",
    # 过拟合检测
    "OverfittingDetector",
    # 策略健康度
    "StrategyHealthChecker",
    # 宏观状态检测
    "MacroStateDetector",
    # 记忆桥接器
    "MemoryBridge",
]
