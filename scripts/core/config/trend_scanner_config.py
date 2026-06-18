"""
TrendScanner 统一配置模块

借鉴 ElegantRL 的 Config 设计模式，提供统一的配置管理：
1. 所有配置集中在一个 TrendScannerConfig 对象中
2. 支持 JSON 文件加载和环境变量覆盖
3. 提供配置验证和默认值

版本：v1.0
创建日期：2026-06-17
"""

import json
import os
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DataConfig:
    """数据源配置"""
    
    primary_source: str = "tqsdk"
    fallback_sources: List[str] = field(default_factory=lambda: ["duckdb", "tdx"])
    cache_dir: str = "data/cache"
    db_path: str = "data/market.db"
    meta_db_path: str = "data/meta.db"
    
    # 数据路由优先级
    routing_priorities: Dict[str, List[str]] = field(default_factory=lambda: {
        "kline": ["duckdb", "tqsdk", "pytdx", "csv"],
        "quote": ["duckdb", "tqsdk", "pytdx"],
        "basis": ["akshare", "pytdx"],
        "seasonality": ["akshare", "csv"],
        "inventory": ["akshare"],
        "top_list": ["akshare"],
        "margin": ["akshare"],
        "macro": ["akshare"],
        "delivery": ["akshare"]
    })
    
    # 数据时效阈值（小时）
    staleness_threshold: Dict[str, int] = field(default_factory=lambda: {
        "kline": 4,
        "quote": 0.5,
        "basis": 24,
        "seasonality": 168,
        "inventory": 24,
        "top_list": 24,
        "margin": 168,
        "macro": 168,
        "delivery": 720
    })


@dataclass
class ScannerConfig:
    """Scanner 配置"""
    
    enabled: bool = True
    symbols: List[str] = field(default_factory=lambda: [
        "SHFE.rb", "SHFE.hc", "SHFE.ru", "SHFE.ni", "SHFE.cu",
        "DCE.jm", "DCE.j", "DCE.i", "DCE.p", "DCE.y", "DCE.cs",
        "CZCE.CF", "CZCE.SR", "CZCE.TA", "CZCE.MA",
        "INE.sc", "INE.lu"
    ])
    schedule: List[str] = field(default_factory=lambda: ["08:40", "15:20", "20:40"])
    
    # 信号过滤
    signal_filter: Dict[str, Any] = field(default_factory=lambda: {
        "filter_mode": "or",
        "er_min": 0.6,
        "tsi_min": 20,
        "tsi_max": -20,
        "trend_strength_min": 0.5,
        "r2_min": 0.4
    })
    
    # 多维度筛选
    use_multi_dimension: bool = True
    dimension_weights: Dict[str, float] = field(default_factory=lambda: {
        "trend": 0.30,
        "momentum": 0.25,
        "volume": 0.20,
        "volatility": 0.15,
        "channel": 0.10
    })
    signal_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "long": 0.3,
        "short": -0.3
    })
    
    output_path: str = "data/latest_scan.json"


@dataclass
class ReasonerConfig:
    """Reasoner 配置"""
    
    llm_type: str = "workbuddy"
    llm_model: str = "mimo-v2.5-pro"
    llm_endpoint: str = "https://token-plan-cn.xiaomimimo.com/v1"
    llm_api_key_env: str = "LLM_API_KEY"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    
    output_level: str = "standard"  # formal, standard, brief
    use_knowledge_anchors: bool = True
    debate_trigger_confidence: float = 0.7
    max_tokens_per_day: int = 500000


@dataclass
class EvolverConfig:
    """Evolver 配置"""
    
    enabled: bool = True
    
    # 自动触发条件
    auto_trigger: Dict[str, Any] = field(default_factory=lambda: {
        "consecutive_losses": 3,
        "cumulative_loss_pct": 10,
        "trade_count_interval": 20
    })
    
    # Walk-Forward 验证
    walk_forward_window: int = 30
    walk_forward_test_days: int = 7
    min_trades: int = 10
    min_sharpe: float = 0.5
    max_drawdown: float = 0.20


@dataclass
class DebaterConfig:
    """Debater 配置"""
    
    enabled: bool = True
    trigger_conditions: Dict[str, Any] = field(default_factory=lambda: {
        "confidence_below": 0.7,
        "position_value_above": 50000
    })


@dataclass
class MonitorConfig:
    """Monitor 配置"""
    
    enabled: bool = True
    interval_minutes: int = 30
    data_source: str = "data/positions.json"
    
    alert_thresholds: Dict[str, Dict] = field(default_factory=lambda: {
        "LOW": {"trend_strength_drop": 0.15},
        "MEDIUM": {"trend_strength_drop": 0.25, "tsi_divergence": True},
        "HIGH": {"trend_strength_drop": 0.35, "er_below": 0.3}
    })
    
    output_path: str = "data/latest_monitor.json"


@dataclass
class RLConfig:
    """RL 训练配置"""
    
    enabled: bool = False
    algorithm: str = "ppo"  # ppo, sac
    
    # 网络结构
    net_dims: List[int] = field(default_factory=lambda: [128, 128])
    
    # 训练超参
    gamma: float = 0.99
    lambda_gae: float = 0.95
    learning_rate: float = 2e-4
    batch_size: int = 256
    horizon_len: int = 2048
    repeat_times: int = 10
    
    # PPO 特有
    ratio_clip: float = 0.2
    entropy_weight: float = 0.001
    
    # SAC 特有
    alpha_init: float = 0.2
    tau: float = 0.005
    
    # 评估
    eval_per_step: int = 1000
    eval_times: int = 8


@dataclass
class TokenBudgetConfig:
    """Token 预算配置"""
    
    daily_limit: int = 850000
    warn_at_pct: int = 80
    stop_at_pct: int = 100


@dataclass
class TrendScannerConfig:
    """
    统一配置对象
    
    借鉴 ElegantRL 的 Config 设计模式，将所有配置集中管理。
    使用方式：
        config = TrendScannerConfig.from_json("config/config.json")
        scanner = Scanner(config)
        reasoner = Reasoner(config)
    """
    
    version: str = "1.0.0"
    description: str = "Trend Scanner Agent 统一配置"
    
    # 子配置模块
    data: DataConfig = field(default_factory=DataConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    reasoner: ReasonerConfig = field(default_factory=ReasonerConfig)
    evolver: EvolverConfig = field(default_factory=EvolverConfig)
    debater: DebaterConfig = field(default_factory=DebaterConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    rl: RLConfig = field(default_factory=RLConfig)
    token_budget: TokenBudgetConfig = field(default_factory=TokenBudgetConfig)
    
    # 数据保留策略
    data_retention: Dict[str, int] = field(default_factory=lambda: {
        "scan_history_days": 30,
        "brief_history_days": 90,
        "log_days": 7
    })
    
    @classmethod
    def from_json(cls, path: str) -> 'TrendScannerConfig':
        """
        从 JSON 文件加载配置
        
        Args:
            path: JSON 配置文件路径
            
        Returns:
            TrendScannerConfig 实例
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls._from_dict(data)
    
    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'TrendScannerConfig':
        """从字典创建配置对象"""
        config = cls()
        
        # 更新顶层字段
        config.version = data.get('version', config.version)
        config.description = data.get('description', config.description)
        
        # 更新子配置
        if 'data_routing' in data:
            routing = data['data_routing']
            config.data.routing_priorities = routing.get('priorities', config.data.routing_priorities)
            config.data.staleness_threshold = routing.get('staleness_threshold', config.data.staleness_threshold)
            config.data.db_dir = routing.get('db_dir', 'data')
        
        if 'scanner' in data:
            scanner_data = data['scanner']
            config.scanner.enabled = scanner_data.get('enabled', config.scanner.enabled)
            config.scanner.symbols = scanner_data.get('symbols', config.scanner.symbols)
            config.scanner.schedule = scanner_data.get('schedule', config.scanner.schedule)
            config.scanner.signal_filter = scanner_data.get('signal_filter', config.scanner.signal_filter)
            
            if 'multi_dimension' in scanner_data:
                md = scanner_data['multi_dimension']
                config.scanner.use_multi_dimension = md.get('enabled', config.scanner.use_multi_dimension)
                config.scanner.signal_thresholds = md.get('signal_thresholds', config.scanner.signal_thresholds)
            
            config.scanner.output_path = scanner_data.get('output_path', config.scanner.output_path)
        
        if 'reasoner' in data:
            reasoner_data = data['reasoner']
            config.reasoner.llm_type = reasoner_data.get('llm_type', config.reasoner.llm_type)
            config.reasoner.debate_trigger_confidence = reasoner_data.get('debate_trigger_confidence', config.reasoner.debate_trigger_confidence)
            config.reasoner.max_tokens_per_day = reasoner_data.get('max_tokens_per_day', config.reasoner.max_tokens_per_day)
        
        if 'llm' in data:
            llm_data = data['llm']
            config.reasoner.llm_model = llm_data.get('model', config.reasoner.llm_model)
            config.reasoner.llm_endpoint = llm_data.get('base_url', config.reasoner.llm_endpoint)
            config.reasoner.llm_api_key_env = llm_data.get('api_key_env', config.reasoner.llm_api_key_env)
            config.reasoner.llm_temperature = llm_data.get('temperature', config.reasoner.llm_temperature)
            config.reasoner.llm_max_tokens = llm_data.get('max_tokens', config.reasoner.llm_max_tokens)
        
        if 'debater' in data:
            debater_data = data['debater']
            config.debater.enabled = debater_data.get('enabled', config.debater.enabled)
            config.debater.trigger_conditions = debater_data.get('trigger_conditions', config.debater.trigger_conditions)
        
        if 'evolver' in data:
            evolver_data = data['evolver']
            config.evolver.enabled = evolver_data.get('enabled', config.evolver.enabled)
            config.evolver.auto_trigger = evolver_data.get('auto_trigger', config.evolver.auto_trigger)
        
        if 'monitor' in data:
            monitor_data = data['monitor']
            config.monitor.enabled = monitor_data.get('enabled', config.monitor.enabled)
            config.monitor.interval_minutes = monitor_data.get('interval_minutes', config.monitor.interval_minutes)
            config.monitor.data_source = monitor_data.get('data_source', config.monitor.data_source)
            config.monitor.alert_thresholds = monitor_data.get('alert_thresholds', config.monitor.alert_thresholds)
            config.monitor.output_path = monitor_data.get('output_path', config.monitor.output_path)
        
        if 'token_budget' in data:
            token_data = data['token_budget']
            config.token_budget.daily_limit = token_data.get('daily_limit', config.token_budget.daily_limit)
            config.token_budget.warn_at_pct = token_data.get('warn_at_pct', config.token_budget.warn_at_pct)
            config.token_budget.stop_at_pct = token_data.get('stop_at_pct', config.token_budget.stop_at_pct)
        
        if 'rl' in data:
            rl_data = data['rl']
            config.rl.enabled = rl_data.get('enabled', config.rl.enabled)
            config.rl.algorithm = rl_data.get('algorithm', config.rl.algorithm)
            config.rl.net_dims = rl_data.get('net_dims', config.rl.net_dims)
            config.rl.gamma = rl_data.get('gamma', config.rl.gamma)
            config.rl.lambda_gae = rl_data.get('lambda_gae', config.rl.lambda_gae)
            config.rl.learning_rate = rl_data.get('learning_rate', config.rl.learning_rate)
            config.rl.batch_size = rl_data.get('batch_size', config.rl.batch_size)
            config.rl.horizon_len = rl_data.get('horizon_len', config.rl.horizon_len)
            config.rl.repeat_times = rl_data.get('repeat_times', config.rl.repeat_times)
            config.rl.ratio_clip = rl_data.get('ratio_clip', config.rl.ratio_clip)
            config.rl.entropy_weight = rl_data.get('entropy_weight', config.rl.entropy_weight)
            config.rl.alpha_init = rl_data.get('alpha_init', config.rl.alpha_init)
            config.rl.tau = rl_data.get('tau', config.rl.tau)
            config.rl.eval_per_step = rl_data.get('eval_per_step', config.rl.eval_per_step)
            config.rl.eval_times = rl_data.get('eval_times', config.rl.eval_times)
        
        if 'data_retention' in data:
            config.data_retention = data['data_retention']
        
        # 应用环境变量覆盖
        config._apply_env_overrides()
        
        return config
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # TqSdk 凭证
        if 'TQ_USER' in os.environ:
            self.data.tq_user = os.environ['TQ_USER']
        if 'TQ_PASSWORD' in os.environ:
            self.data.tq_password = os.environ['TQ_PASSWORD']
        
        # LLM API Key
        if self.reasoner.llm_api_key_env in os.environ:
            self.reasoner.llm_api_key = os.environ[self.reasoner.llm_api_key_env]
    
    def to_json(self, path: str):
        """
        保存配置到 JSON 文件
        
        Args:
            path: 输出文件路径
        """
        data = asdict(self)
        
        # 确保目录存在
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"配置已保存到: {path}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """
        验证配置有效性
        
        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors = []
        
        # 验证数据源
        valid_sources = {"tqsdk", "duckdb", "tdx", "pytdx", "akshare", "csv"}
        if self.data.primary_source not in valid_sources:
            errors.append(f"无效的主数据源: {self.data.primary_source}")
        
        # 验证维度权重之和
        weight_sum = sum(self.scanner.dimension_weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            errors.append(f"维度权重之和应为 1.0，当前为 {weight_sum}")
        
        # 验证输出级别
        valid_levels = {"formal", "standard", "brief"}
        if self.reasoner.output_level not in valid_levels:
            errors.append(f"无效的输出级别: {self.reasoner.output_level}")
        
        # 验证 RL 算法
        valid_algorithms = {"ppo", "sac"}
        if self.rl.algorithm not in valid_algorithms:
            errors.append(f"无效的 RL 算法: {self.rl.algorithm}")
        
        # 验证 RL 超参
        if self.rl.gamma < 0 or self.rl.gamma > 1:
            errors.append(f"gamma 应在 [0, 1] 范围内，当前为 {self.rl.gamma}")
        
        if self.rl.learning_rate <= 0:
            errors.append(f"learning_rate 应大于 0，当前为 {self.rl.learning_rate}")
        
        return errors
    
    def get_summary(self) -> str:
        """获取配置摘要"""
        lines = [
            f"TrendScannerConfig v{self.version}",
            f"  数据源: {self.data.primary_source} (备选: {', '.join(self.data.fallback_sources)})",
            f"  扫描品种: {len(self.scanner.symbols)} 个",
            f"  多维度筛选: {'启用' if self.scanner.use_multi_dimension else '禁用'}",
            f"  LLM 模型: {self.reasoner.llm_model}",
            f"  输出级别: {self.reasoner.output_level}",
            f"  Evolver: {'启用' if self.evolver.enabled else '禁用'}",
            f"  RL 训练: {'启用' if self.rl.enabled else '禁用'}",
        ]
        
        if self.rl.enabled:
            lines.append(f"    算法: {self.rl.algorithm}")
            lines.append(f"    网络结构: {self.rl.net_dims}")
        
        return "\n".join(lines)


# 全局配置实例（单例模式）
_global_config: Optional[TrendScannerConfig] = None


def get_config() -> TrendScannerConfig:
    """
    获取全局配置实例
    
    如果尚未初始化，从默认路径加载
    
    Returns:
        TrendScannerConfig 实例
    """
    global _global_config
    
    if _global_config is None:
        # 尝试从默认路径加载
        config_path = os.environ.get(
            'TREND_SCANNER_CONFIG',
            'config/config.json'
        )
        
        if os.path.exists(config_path):
            _global_config = TrendScannerConfig.from_json(config_path)
            logger.info(f"从 {config_path} 加载配置")
        else:
            _global_config = TrendScannerConfig()
            logger.info("使用默认配置")
    
    return _global_config


def set_config(config: TrendScannerConfig):
    """
    设置全局配置实例
    
    Args:
        config: TrendScannerConfig 实例
    """
    global _global_config
    _global_config = config


def reset_config():
    """重置全局配置（用于测试）"""
    global _global_config
    _global_config = None


# 便捷函数
def get_scanner_config() -> ScannerConfig:
    """获取 Scanner 配置"""
    return get_config().scanner


def get_reasoner_config() -> ReasonerConfig:
    """获取 Reasoner 配置"""
    return get_config().reasoner


def get_evolver_config() -> EvolverConfig:
    """获取 Evolver 配置"""
    return get_config().evolver


def get_rl_config() -> RLConfig:
    """获取 RL 配置"""
    return get_config().rl


def get_data_config() -> DataConfig:
    """获取数据配置"""
    return get_config().data
