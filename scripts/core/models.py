"""
数据模型模块（v3.0 — 推理优先架构）

所有数据结构服务于"推理层"，而非"规则层"。
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import ForwardRef


# ──────────────────────────────────────────────
# 前向声明（用于解决循环引用）
# ──────────────────────────────────────────────

# 基本面数据模型的前向声明
FundamentalContextRef = ForwardRef('FundamentalContext')


# ──────────────────────────────────────────────
# 基本面数据模型（v1.0 — 基本面分析模块）
# ──────────────────────────────────────────────


@dataclass
class NewsEvent:
    """新闻事件"""
    event_id: str = ""
    timestamp: str = ""  # 事件时间
    source: str = ""  # 来源（财新、新浪、央广网等）
    title: str = ""  # 标题
    content: str = ""  # 内容摘要
    category: str = ""  # 分类：policy/geopolitical/industry/company
    impact: str = ""  # 影响：positive/negative/neutral
    keywords: list[str] = field(default_factory=list)  # 关键词
    affected_symbols: list[str] = field(default_factory=list)  # 受影响的品种
    confidence: float = 0.5  # 信息置信度
    url: str = ""  # 原文链接
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_prompt_text(self) -> str:
        """转换为推理层可读的文本描述"""
        impact_map = {"positive": "利好", "negative": "利空", "neutral": "中性"}
        return f"[{self.source}] {self.title} ({impact_map.get(self.impact, self.impact)})"


@dataclass
class SupplyDemandData:
    """供需数据"""
    symbol: str = ""  # 品种代码
    timestamp: str = ""  # 数据时间
    source: str = ""  # 数据来源
    
    # 库存数据
    inventory_exchange: float = 0.0  # 交易所库存
    inventory_social: float = 0.0  # 社会库存
    inventory_change_pct: float = 0.0  # 库存变化百分比
    
    # 产量数据
    production: float = 0.0  # 产量
    production_change_pct: float = 0.0  # 产量变化百分比
    capacity_utilization: float = 0.0  # 产能利用率
    
    # 消费数据
    consumption: float = 0.0  # 消费量
    consumption_change_pct: float = 0.0  # 消费变化百分比
    
    # 进出口数据
    import_volume: float = 0.0  # 进口量
    export_volume: float = 0.0  # 出口量
    net_import: float = 0.0  # 净进口
    
    # 供需平衡
    supply_surplus: float = 0.0  # 供需盈余（正=供过于求，负=供不应求）
    balance_status: str = ""  # surplus/balanced/deficit
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_prompt_text(self) -> str:
        """转换为推理层可读的文本描述"""
        status_map = {"surplus": "供过于求", "balanced": "供需平衡", "deficit": "供不应求"}
        lines = []
        if self.inventory_exchange > 0:
            lines.append(f"交易所库存：{self.inventory_exchange:.0f}（{self.inventory_change_pct:+.1f}%）")
        if self.production > 0:
            lines.append(f"产量：{self.production:.0f}（{self.production_change_pct:+.1f}%）")
        if self.consumption > 0:
            lines.append(f"消费量：{self.consumption:.0f}")
        if self.balance_status:
            lines.append(f"供需状态：{status_map.get(self.balance_status, self.balance_status)}")
        return "；".join(lines) if lines else "暂无供需数据"


@dataclass
class GeopoliticalRisk:
    """地缘政治风险"""
    risk_id: str = ""
    timestamp: str = ""  # 事件时间
    region: str = ""  # 地区（中东、俄罗斯、中国等）
    risk_type: str = ""  # 风险类型：war/sanctions/tariffs/dispute/peace_agreement
    risk_level: str = ""  # 风险等级：high/medium/low
    affected_commodities: list[str] = field(default_factory=list)  # 受影响的商品类别
    affected_symbols: list[str] = field(default_factory=list)  # 受影响的品种
    description: str = ""  # 事件描述
    impact_analysis: str = ""  # 影响分析
    confidence: float = 0.5  # 信息置信度
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_prompt_text(self) -> str:
        """转换为推理层可读的文本描述"""
        level_map = {"high": "高风险", "medium": "中风险", "low": "低风险"}
        type_map = {
            "war": "战争/冲突", "sanctions": "制裁", "tariffs": "关税",
            "dispute": "争端", "peace_agreement": "和平协议"
        }
        return f"[{self.region}] {type_map.get(self.risk_type, self.risk_type)} - {level_map.get(self.risk_level, self.risk_level)}：{self.description[:50]}"


@dataclass
class PolicyImpact:
    """政策影响"""
    policy_id: str = ""
    timestamp: str = ""  # 政策时间
    policy_type: str = ""  # 政策类型：monetary/fiscal/industrial/environmental/safety
    policy_name: str = ""  # 政策名称
    issuing_authority: str = ""  # 发布机构
    description: str = ""  # 政策描述
    impact_direction: str = ""  # 影响方向：positive/negative/neutral
    affected_industries: list[str] = field(default_factory=list)  # 受影响行业
    affected_symbols: list[str] = field(default_factory=list)  # 受影响品种
    implementation_date: str = ""  # 实施日期
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_prompt_text(self) -> str:
        """转换为推理层可读的文本描述"""
        type_map = {
            "monetary": "货币政策", "fiscal": "财政政策", "industrial": "产业政策",
            "environmental": "环保政策", "safety": "安全政策"
        }
        return f"[{type_map.get(self.policy_type, self.policy_type)}] {self.policy_name}"


@dataclass
class FundamentalContext:
    """基本面上下文"""
    symbol: str = ""
    timestamp: str = ""
    
    # 新闻事件
    news_events: list[NewsEvent] = field(default_factory=list)
    news_sentiment: str = ""  # 整体情绪：positive/negative/neutral/mixed
    news_count: int = 0  # 新闻数量
    
    # 供需数据
    supply_demand: SupplyDemandData = field(default_factory=SupplyDemandData)
    
    # 地缘政治风险
    geopolitical_risks: list[GeopoliticalRisk] = field(default_factory=list)
    geopolitical_risk_level: str = ""  # 整体风险等级：high/medium/low
    
    # 政策影响
    policy_impacts: list[PolicyImpact] = field(default_factory=list)
    
    # 综合评估
    fundamental_score: float = 0.0  # 基本面综合评分 [-1, 1]
    fundamental_direction: str = ""  # 基本面方向：bullish/bearish/neutral
    key_drivers: list[str] = field(default_factory=list)  # 关键驱动因素
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_prompt_text(self) -> str:
        """转换为推理层可读的文本描述"""
        lines = []
        
        # 新闻摘要
        if self.news_events:
            lines.append(f"近期新闻（{self.news_count}条）：")
            for event in self.news_events[:3]:  # 只显示前3条
                lines.append(f"  - {event.to_prompt_text()}")
            if self.news_count > 3:
                lines.append(f"  ... 还有{self.news_count - 3}条")
        
        # 供需数据
        supply_text = self.supply_demand.to_prompt_text()
        if supply_text != "暂无供需数据":
            lines.append(f"供需数据：{supply_text}")
        
        # 地缘政治风险
        if self.geopolitical_risks:
            lines.append("地缘政治风险：")
            for risk in self.geopolitical_risks[:2]:  # 只显示前2条
                lines.append(f"  - {risk.to_prompt_text()}")
        
        # 政策影响
        if self.policy_impacts:
            lines.append("政策影响：")
            for policy in self.policy_impacts[:2]:  # 只显示前2条
                lines.append(f"  - {policy.to_prompt_text()}")
        
        # 综合评估
        if self.fundamental_direction:
            direction_map = {"bullish": "看多", "bearish": "看空", "neutral": "中性"}
            lines.append(f"基本面评估：{direction_map.get(self.fundamental_direction, self.fundamental_direction)}")
        
        if self.key_drivers:
            lines.append(f"关键驱动：{'、'.join(self.key_drivers[:3])}")
        
        return "\n".join(lines) if lines else "暂无基本面数据"


# ──────────────────────────────────────────────
# 感知层输出：结构化市场上下文
# ──────────────────────────────────────────────


@dataclass
class IndicatorSnapshot:
    """单个时间点的指标快照"""

    timestamp: str
    close: float
    high: float
    low: float
    open: float
    volume: float
    open_interest: float = 0.0

    # 均线
    ema20: float = 0.0
    ema60: float = 0.0
    sma20: float = 0.0
    sma60: float = 0.0

    # 动量
    rsi: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    stoch_k: float = 50.0
    stoch_d: float = 50.0
    cci: float = 0.0

    # 波动率
    atr: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    bb_mid: float = 0.0

    # 趋势
    adx: float = 0.0
    plus_di: float = 0.0
    minus_di: float = 0.0

    # 七维趋势强度（替代 ADX 单一指标）
    trend_strength_er: float = 0.0  # 效率比 [0, 1]
    trend_strength_r2: float = 0.0  # 趋势拟合度 [0, 1]
    trend_strength_hurst: float = 0.5  # Hurst 指数 [0, 1]
    trend_strength_adx_roc: float = 0.0  # ADX 变化率（无界）
    trend_strength_ema_slope: float = 0.0  # EMA 斜率强度（无界）
    trend_strength_tsi: float = 0.0  # TSI 双平滑动量 [-100, 100]
    trend_strength_atr_ratio: float = 1.0  # ATR 比率 [0, +∞)
    trend_strength_composite: float = 0.0  # 复合评分 [0, 1]

    # 通道
    dc_upper: float = 0.0
    dc_lower: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MarketStructure:
    """市场结构分析（感知层输出，非判断）"""

    # 均线排列
    ma_arrangement: str = "NEUTRAL"  # STRONG_BULL / WEAK_BULL / NEUTRAL / WEAK_BEAR / STRONG_BEAR
    ma_slope_20: float = 0.0  # EMA20 斜率（百分比）
    ma_slope_60: float = 0.0  # EMA60 斜率（百分比）
    price_vs_ma: str = "NEUTRAL"  # ABOVE / BELOW / NEAR

    # 高低点结构
    swing_structure: str = "NEUTRAL"  # HIGHER_HIGHS / LOWER_LOWS / MIXED / NEUTRAL
    recent_high: float = 0.0
    recent_low: float = 0.0

    # 成交量
    volume_trend: str = "NEUTRAL"  # INCREASING / DECREASING / NEUTRAL
    volume_ratio: float = 1.0  # 当前成交量 / 20日均量

    # 持仓量
    oi_trend: str = "NEUTRAL"  # INCREASING / DECREASING / NEUTRAL
    oi_change_pct: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MomentumState:
    """动量状态（感知层输出，非判断）"""

    rsi_state: str = "NEUTRAL"  # OVERBOUGHT / STRONG / NEUTRAL / WEAK / OVERSOLD
    rsi_value: float = 50.0

    macd_state: str = "NEUTRAL"  # BULLISH_CROSS / BULLISH / BEARISH_CROSS / BEARISH
    macd_histogram_trend: str = "NEUTRAL"  # EXPANDING / CONTRACTING / NEUTRAL

    stoch_state: str = "NEUTRAL"  # OVERBOUGHT / STRONG / NEUTRAL / WEAK / OVERSOLD
    cci_state: str = "NEUTRAL"  # EXTREME_HIGH / HIGH / NEUTRAL / LOW / EXTREME_LOW

    oscillator_resonance: str = "NEUTRAL"  # BULLISH / BEARISH / MIXED / NEUTRAL
    resonance_count: int = 0  # 同向振荡器数量

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TrendPhase:
    """
    趋势阶段 —— 描述趋势生命周期

    六阶段模型描述趋势生命周期：
    - CONSOLIDATING：横盘整理，无明确趋势
    - EMERGING：趋势萌芽，信号初现
    - DEVELOPING：趋势发展，信号确认
    - MATURE：趋势成熟，动能充沛
    - FATIGUING：趋势衰竭，动能减弱
    - REVERSING：趋势反转，方向改变
    """

    phase: str = "CONSOLIDATING"  # CONSOLIDATING / EMERGING / DEVELOPING / MATURE / FATIGUING / REVERSING
    confidence: float = 0.5  # 阶段判断置信度 (0-1)
    reasoning: str = ""  # 判断依据

    # 阶段特征（感知层输出，用于推理）
    adx_state: str = "NEUTRAL"  # LOW / RISING / HIGH / FALLING
    ma_slope_state: str = "NEUTRAL"  # BOTH_UP / BOTH_DOWN / MIXED / FLAT
    macd_momentum: str = "NEUTRAL"  # EXPANDING / CONTRACTING / CROSSING
    volume_confirmation: bool = False  # 成交量是否确认

    def to_dict(self) -> dict:
        return asdict(self)

    def to_chinese(self) -> str:
        """中文标签"""
        labels = {
            "CONSOLIDATING": "横盘整理",
            "EMERGING": "趋势萌芽",
            "DEVELOPING": "趋势发展",
            "MATURE": "趋势成熟",
            "FATIGUING": "趋势衰竭",
            "REVERSING": "趋势反转",
        }
        return labels.get(self.phase, self.phase)

    def to_emoji(self) -> str:
        """Emoji 标签"""
        emojis = {
            "CONSOLIDATING": "📊",
            "EMERGING": "🆕",
            "DEVELOPING": "🌱",
            "MATURE": "🏆",
            "FATIGUING": "⚠️",
            "REVERSING": "🔄",
        }
        return emojis.get(self.phase, "❓")

    def to_signal_hint(self) -> str:
        """
        根据阶段给出信号倾向提示（非决策，仅提示）
        """
        hints = {
            "CONSOLIDATING": "观望为主，等待突破",
            "EMERGING": "关注确认信号，可小仓试探",
            "DEVELOPING": "顺势加仓，跟踪止损",
            "MATURE": "持仓为主，止盈上移",
            "FATIGUING": "减仓或止盈，警惕反转",
            "REVERSING": "平仓观望，等待新方向",
        }
        return hints.get(self.phase, "观望")


@dataclass
class VolatilityState:
    """波动率状态（感知层输出，非判断）"""

    atr_pct: float = 0.0  # ATR / close * 100
    atr_percentile: float = 50.0  # ATR 在历史中的分位数
    bb_width: float = 0.0  # 布林带宽度
    bb_width_percentile: float = 50.0  # 布林带宽度分位数

    regime: str = "NORMAL"  # LOW / NORMAL / HIGH / EXTREME
    regime_confidence: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MarketContext:
    """
    结构化市场上下文 —— 感知层的最终输出

    这是推理层的输入。它只描述"市场现在是什么样"，
    不做"应该怎么做"的判断。
    """

    symbol: str
    timestamp: str
    timeframe: str = "daily"

    # 当前价格
    current_price: float = 0.0
    price_change_pct: float = 0.0  # 日涨跌幅

    # 各维度状态（感知层输出）
    structure: MarketStructure = field(default_factory=MarketStructure)
    momentum: MomentumState = field(default_factory=MomentumState)
    volatility: VolatilityState = field(default_factory=VolatilityState)

    # 趋势阶段（核心状态）
    trend_phase: TrendPhase = field(default_factory=TrendPhase)

    # 最近N根K线的关键统计
    bars_since_high: int = 0  # 距离最近高点的K线数
    bars_since_low: int = 0  # 距离最近低点的K线数
    consecutive_up_days: int = 0
    consecutive_down_days: int = 0

    # 原始指标快照（最近一根K线）
    snapshot: IndicatorSnapshot = field(default_factory=IndicatorSnapshot)

    # 感知层原始特征向量（用于经验检索）
    feature_vector: list[float] = field(default_factory=list)

    # 基本面上下文（v1.0 新增）
    fundamental: FundamentalContext = field(default_factory=FundamentalContext)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def to_prompt_text(self) -> str:
        """转换为推理层可读的文本描述"""
        phase = self.trend_phase
        lines = [
            f"【{self.symbol} 日线数据】时间：{self.timestamp}",
            f"当前价格：{self.current_price:.2f}，日涨跌：{self.price_change_pct:+.2f}%",
            "",
            "## 趋势阶段（核心状态）",
            f"- 当前阶段：{phase.to_emoji()} {phase.to_chinese()}（{phase.phase}）",
            f"- 判断置信度：{int(phase.confidence * 100)}%",
            f"- 判断依据：{phase.reasoning}",
            f"- ADX状态：{phase.adx_state}",
            f"- 均线斜率状态：{phase.ma_slope_state}",
            f"- MACD动量：{phase.macd_momentum}",
            f"- 成交量确认：{'是' if phase.volume_confirmation else '否'}",
            "",
            "## 市场结构",
            f"- 均线排列：{self.structure.ma_arrangement}",
            f"- EMA20斜率：{self.structure.ma_slope_20:+.2f}%，EMA60斜率：{self.structure.ma_slope_60:+.2f}%",
            f"- 价格位置：{self.structure.price_vs_ma}",
            f"- 高低点结构：{self.structure.swing_structure}",
            f"- 成交量趋势：{self.structure.volume_trend}（比率：{self.structure.volume_ratio:.2f}）",
            f"- 持仓量趋势：{self.structure.oi_trend}（变化：{self.structure.oi_change_pct:+.2f}%）",
            "",
            "## 动量状态",
            f"- RSI({self.momentum.rsi_value:.1f})：{self.momentum.rsi_state}",
            f"- MACD：{self.momentum.macd_state}，柱状线{self.momentum.macd_histogram_trend}",
            f"- 随机指标：{self.momentum.stoch_state}",
            f"- CCI：{self.momentum.cci_state}",
            f"- 振荡器共振：{self.momentum.oscillator_resonance}（{self.momentum.resonance_count}/3同向）",
            "",
            "## 波动率",
            f"- ATR占比：{self.volatility.atr_pct:.2f}%（历史分位：{self.volatility.atr_percentile:.0f}%）",
            f"- 布林带宽度：{self.volatility.bb_width:.4f}（分位：{self.volatility.bb_width_percentile:.0f}%）",
            f"- 波动率状态：{self.volatility.regime}",
            "",
            "## 价格行为",
            f"- 距离高点：{self.bars_since_high}根K线",
            f"- 距离低点：{self.bars_since_low}根K线",
            f"- 连续上涨：{self.consecutive_up_days}天",
            f"- 连续下跌：{self.consecutive_down_days}天",
        ]
        
        # 基本面信息（如果有）
        if self.fundamental and self.fundamental.news_events:
            lines.append("")
            lines.append("## 基本面信息")
            lines.append(self.fundamental.to_prompt_text())
        
        return "\n".join(lines)


# ──────────────────────────────────────────────
# 经验记忆池
# ──────────────────────────────────────────────


@dataclass
class Experience:
    """
    一条交易经验

    不是"规则"，而是"当时发生了什么，我做了什么，结果怎样"。
    用于未来类比推理。
    """

    experience_id: str
    timestamp: str
    symbol: str

    # 当时的市场上下文（快照）
    context_snapshot: dict = field(default_factory=dict)

    # 当时的趋势阶段（核心状态）
    trend_phase: str = "CONSOLIDATING"  # CONSOLIDATING / EMERGING / DEVELOPING / MATURE / FATIGUING / REVERSING
    phase_confidence: float = 0.5  # 阶段判断置信度

    # 采取的动作
    action_taken: str = "NONE"  # LONG / SHORT / HOLD / EXIT
    action_reasoning: str = ""  # 当时的推理过程

    # 约束设置
    stop_loss_used: float = 0.0
    position_size_pct: float = 0.0
    entry_price: float = 0.0

    # 事后结果
    exit_price: float = 0.0
    exit_reason: str = ""
    pnl_pct: float = 0.0
    holding_days: int = 0
    max_drawdown_pct: float = 0.0
    max_profit_pct: float = 0.0

    # 风险调整收益
    risk_adjusted_return: float = 0.0  # pnl / max_drawdown

    # 上下文标签
    market_state_label: str = ""  # 当时的市场状态标签
    trend_phase: str = ""  # 当时的趋势阶段

    # 特征向量（用于相似度检索）
    feature_vector: list[float] = field(default_factory=list)

    # 用户反馈（如果有）
    user_rating: int = 0  # 1-5 用户评价
    user_notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        return d


@dataclass
class ExperienceMatch:
    """经验检索结果"""

    experience: Experience
    similarity: float  # 相似度 (0-1)
    distance: float  # 距离值
    weight: float = 1.0  # 聚合权重

    def to_dict(self) -> dict:
        return {
            "experience_id": self.experience.experience_id,
            "similarity": round(self.similarity, 4),
            "distance": round(self.distance, 4),
            "weight": round(self.weight, 4),
            "action_taken": self.experience.action_taken,
            "pnl_pct": self.experience.pnl_pct,
            "risk_adjusted_return": self.experience.risk_adjusted_return,
        }


# ──────────────────────────────────────────────
# 推理层输出：路线建议
# ──────────────────────────────────────────────


@dataclass
class Constraint:
    """
    动态约束 —— 推理层生成的建议

    不是固定规则，而是"基于当前状态和历史经验，建议这样做"。
    每个约束都附带置信度和推理依据。
    """

    constraint_type: str  # POSITION_SIZE / STOP_LOSS / ENTRY_CONDITION / EXIT_CONDITION
    value: str  # 建议值（文本描述，如"3-5%"或"3540-3560区间"）
    numeric_value: float = 0.0  # 数值（如果可量化）
    confidence: float = 0.5  # 置信度 (0-1)
    reasoning: str = ""  # 推理依据
    historical_basis: str = ""  # 历史依据
    uncertainty_range: str = ""  # 不确定性区间

    def to_dict(self) -> dict:
        return asdict(self)

    def to_text(self) -> str:
        """转换为用户可读文本"""
        conf_pct = int(self.confidence * 100)
        text = f"- {self._type_label()}：{self.value}（置信度{conf_pct}%）"
        if self.reasoning:
            text += f"\n  依据：{self.reasoning}"
        if self.historical_basis:
            text += f"\n  历史：{self.historical_basis}"
        if self.uncertainty_range:
            text += f"\n  区间：{self.uncertainty_range}"
        return text

    def _type_label(self) -> str:
        labels = {
            "POSITION_SIZE": "仓位",
            "STOP_LOSS": "止损",
            "ENTRY_CONDITION": "入场条件",
            "EXIT_CONDITION": "离场条件",
        }
        return labels.get(self.constraint_type, self.constraint_type)


@dataclass
class Route:
    """
    路线建议 —— 推理层的核心输出

    不是"BUY/SELL/HOLD"，而是"如果你选这条路，这是建议的走法"。
    每条路线都有触发条件、代价和置信度。
    """

    route_id: str  # A / B / C
    name: str  # "顺势做多" / "等回调再进" / "观望等待"
    action: str  # 描述性动作（不是 BUY/SELL）
    confidence: float  # 置信度 (0-1)
    reasoning: str  # 推理过程（核心）

    # 约束建议
    constraints: list[Constraint] = field(default_factory=list)

    # 风险提示
    risks: list[str] = field(default_factory=list)

    # 触发条件（什么情况下选这条路）
    trigger_conditions: list[str] = field(default_factory=list)

    # 代价（如果不选这条路会怎样）
    opportunity_cost: str = ""

    # 历史类比
    historical_analog: str = ""  # "类似2024年3月螺纹钢上涨行情，相似度78%"
    historical_outcome: str = ""  # "历史相似情境平均收益+4.2%"

    # 经验支撑
    supporting_experiences: list[ExperienceMatch] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["constraints"] = [c.to_dict() for c in self.constraints]
        d["supporting_experiences"] = [e.to_dict() for e in self.supporting_experiences]
        return d

    def to_text(self) -> str:
        """转换为用户可读文本"""
        conf_pct = int(self.confidence * 100)
        lines = [
            f"### 路线{self.route_id}：{self.name}",
            f"**动作**：{self.action}",
            f"**置信度**：{conf_pct}%",
            f"**推理**：{self.reasoning}",
        ]

        if self.constraints:
            lines.append("**约束建议**：")
            for c in self.constraints:
                lines.append(c.to_text())

        if self.risks:
            lines.append("**风险**：")
            for r in self.risks:
                lines.append(f"- {r}")

        if self.historical_analog:
            lines.append(f"**历史类比**：{self.historical_analog}")
        if self.historical_outcome:
            lines.append(f"**历史结果**：{self.historical_outcome}")

        return "\n".join(lines)


# ──────────────────────────────────────────────
# 交互层输出
# ──────────────────────────────────────────────


@dataclass
class MarketAssessment:
    """
    市场评估 —— 感知层对当前市场的综合判断

    基于趋势阶段、波动率、动量等维度的综合评估。
    """

    trend_phase: str  # 核心：CONSOLIDATING / EMERGING / DEVELOPING / MATURE / FATIGUING / REVERSING
    phase_label: str  # 中文标签
    confidence: float  # 置信度 (0-1)
    summary: str  # 一句话总结
    signal_hint: str  # 信号倾向提示

    def to_dict(self) -> dict:
        return asdict(self)

    def to_text(self) -> str:
        conf_pct = int(self.confidence * 100)
        return f"【{self.phase_label}】{self.summary}（置信度{conf_pct}%）"


@dataclass
class Uncertainty:
    """不确定性量化"""

    cluster_confidence: float = 0.5  # 路段判断置信度
    retrieval_confidence: float = 0.5  # 经验检索置信度
    constraint_confidence: float = 0.5  # 约束建议置信度
    overall_confidence: float = 0.5  # 综合置信度

    def to_dict(self) -> dict:
        return asdict(self)

    def to_text(self) -> str:
        return (
            f"置信度：路段{int(self.cluster_confidence * 100)}% | "
            f"经验{int(self.retrieval_confidence * 100)}% | "
            f"约束{int(self.constraint_confidence * 100)}% | "
            f"综合{int(self.overall_confidence * 100)}%"
        )


@dataclass
class TradingBrief:
    """
    交易决策简报 —— 系统的最终输出

    包含：
    1. 市场评估（趋势阶段 + 综合判断）
    2. 风险提示
    3. 操作方案（2-3条）
    4. 动态约束建议
    5. 不确定性量化
    """

    symbol: str
    timestamp: str

    # 趋势阶段（核心状态）
    trend_phase: TrendPhase = field(default_factory=TrendPhase)

    # 市场评估（综合判断）
    assessment: MarketAssessment = field(default_factory=MarketAssessment)

    # 风险提示
    warnings: list[str] = field(default_factory=list)

    # 操作方案
    routes: list[Route] = field(default_factory=list)

    # 推荐方案
    recommended_route: str = ""  # 推荐的方案ID

    # 不确定性
    uncertainty: Uncertainty = field(default_factory=Uncertainty)

    # 元信息
    reasoning_model: str = ""  # 使用的推理模型
    experience_count: int = 0  # 检索到的经验数量
    generation_time_ms: int = 0  # 生成耗时

    def to_dict(self) -> dict:
        d = asdict(self)
        d["assessment"] = self.assessment.to_dict()
        d["routes"] = [r.to_dict() for r in self.routes]
        d["uncertainty"] = self.uncertainty.to_dict()
        return d

    def to_text(self) -> str:
        """转换为交易决策简报文本"""
        phase = self.trend_phase
        assessment = self.assessment
        lines = [
            f"# {self.symbol} 交易决策简报",
            f"**时间**：{self.timestamp}",
            "",
            "---",
            "",
            "## 市场评估",
            f"{phase.to_emoji()} **趋势阶段：{phase.to_chinese()}**（置信度{int(phase.confidence * 100)}%）",
            f"- 判断依据：{phase.reasoning}",
            f"- ADX状态：{phase.adx_state} | 均线斜率：{phase.ma_slope_state} | MACD动量：{phase.macd_momentum}",
            f"- 信号倾向：{assessment.signal_hint}",
            "",
        ]

        if self.warnings:
            lines.append("## ⚠️ 风险提示")
            for w in self.warnings:
                lines.append(f"- {w}")
            lines.append("")

        lines.append("## 操作方案")
        lines.append("")
        for route in self.routes:
            lines.append(route.to_text())
            lines.append("")

        if self.recommended_route:
            lines.append(f"**推荐方案**：{self.recommended_route}")
            lines.append("")

        lines.append("## 不确定性")
        lines.append(self.uncertainty.to_text())
        lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("以上为系统分析建议，最终决策权在你手中。")
        lines.append(f"_经验库检索到 {self.experience_count} 条相似情境 | 推理模型：{self.reasoning_model}_")

        return "\n".join(lines)


# ──────────────────────────────────────────────
# 用户反馈
# ──────────────────────────────────────────────


@dataclass
class UserFeedback:
    """用户反馈 —— 用于经验学习"""

    feedback_id: str
    timestamp: str
    symbol: str
    brief_id: str  # 对应的简报ID

    # 用户选择
    chosen_route: str  # 选择的路线ID
    actual_action: str  # 实际采取的动作
    entry_price: float = 0.0
    exit_price: float = 0.0
    holding_days: int = 0

    # 结果
    pnl_pct: float = 0.0
    outcome: str = ""  # WIN / LOSS / BREAKEVEN

    # 用户评价
    satisfaction: int = 0  # 1-5
    notes: str = ""

    # 偏离记录（用户是否偏离了建议）
    deviated_from_brief: bool = False
    deviation_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────
# 兼容旧版测试的数据结构
# ──────────────────────────────────────────────


@dataclass
class TrendPhaseInfo:
    """趋势阶段信息（兼容旧版测试）"""

    phase: str = "CONSOLIDATING"
    phase_confidence: float = 0.5
    confidence: float = 0.5
    reliability_score: int = 50
    breakdown: dict = field(default_factory=dict)
    reliability_breakdown: dict = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)
    transition_alerts: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    phase_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TradeSignal:
    """交易信号（兼容旧版测试）"""

    symbol: str = ""
    timestamp: str = ""
    market_state: str = "RANGE_BOUND"
    signal: str = "HOLD"
    strength: str = "NEUTRAL"
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_pct: float = 0.0
    confidence_score: int = 50
    supporting_evidence: list[str] = field(default_factory=list)
    risk_metrics: dict = field(default_factory=dict)
    strategy_votes: dict = field(default_factory=dict)
    trend_phase: str = "CONSOLIDATING"
    phase_confidence: float = 0.5
    reliability_score: int = 50
    reliability_breakdown: dict = field(default_factory=dict)
    transition_alerts: list[str] = field(default_factory=list)
    phase_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


@dataclass
class TradeRecord:
    """交易记录（兼容旧版测试）"""

    trade_id: str = ""
    symbol: str = ""
    direction: str = "LONG"
    entry_time: str = ""
    entry_price: float = 0.0
    entry_signal: str = ""
    market_state_at_entry: str = ""
    adx_at_entry: float = 0.0
    atr_at_entry: float = 0.0
    strategy_votes_at_entry: dict = field(default_factory=dict)
    stop_loss: float = 0.0
    take_profit: float = 0.0
    initial_risk_pct: float = 0.01
    lots: int = 0
    exit_time: str = ""
    exit_price: float = 0.0
    exit_reason: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_bars: int = 0
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    market_context: dict = field(default_factory=dict)
    quality_tags: list[str] = field(default_factory=list)
    trend_phase_at_entry: str = ""
    trend_phase_at_exit: str = ""
    phase_confidence_at_entry: float = 0.5
    reliability_score_at_entry: int = 50
    risk_metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        # 处理datetime类型
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        return d


@dataclass
class ScoringFeedback:
    """
    打分反馈记录

    用于记录打分结果与实际交易结果的关联，支持打分体系优化。
    """

    feedback_id: str
    timestamp: str
    symbol: str

    # 打分结果
    composite_score: float = 0.0
    filtered_composite: float = 0.0
    score_direction: int = 0  # 1/-1/0
    confidence: float = 0.0

    # 维度得分
    dimension_scores: dict[str, float] = field(default_factory=dict)

    # 市场状态
    market_state: str = ""
    trend_phase: str = ""
    volatility_regime: str = ""  # high/normal/low

    # 实际结果（后续填充）
    actual_direction: int = 0  # 1/-1/0
    actual_return: float = 0.0
    holding_days: int = 0
    outcome: str = ""  # WIN/LOSS/BREAKEVEN

    # 相关性指标
    direction_correct: bool = False

    # 元信息
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""
    status: str = "pending"  # pending/completed/cancelled

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    def update_result(self, actual_direction: int, actual_return: float, holding_days: int, outcome: str):
        """更新实际交易结果"""
        self.actual_direction = actual_direction
        self.actual_return = actual_return
        self.holding_days = holding_days
        self.outcome = outcome
        self.direction_correct = self.score_direction == actual_direction
        self.status = "completed"
        self.updated_at = datetime.now().isoformat()


