"""
交易决策辅助系统 —— 主协调器

工作流程：
1. 感知层：计算指标，组装结构化上下文
2. 经验层：检索相似历史经验
3. 推理层：调用 LLM 推理，生成操作方案
4. 交互层：生成交易决策简报
5. 进化层：记录反馈，积累经验，持续优化

这不是一个"自动交易系统"，而是一个"决策辅助系统"。
最终决策权始终在交易者手中。
"""

import time

import pandas as pd

from .brief import BriefFormatter, BriefGenerator
from .context import ContextAssembler
from .data_store import DataStore
from .evolution_manager import EvolutionManager
from .experience import ExperienceMemory
from .models import Experience, MarketContext, TradingBrief, UserFeedback
from .reasoning import LLMProvider, ReasoningEngine, WorkBuddyAgentProvider


class TradingAssistant:
    """
    交易决策辅助系统

    不进行自动下单，只提供态势研判、风险提示与操作方案。

    使用方式：
        assistant = TradingAssistant()
        brief = assistant.analyze(df, symbol="RB2501")
        print(brief.to_text())
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        experience_db: str | None = None,
        auto_extract_patterns: bool = True,
        enable_evolution: bool = True,
    ):
        """
        初始化交易辅助系统

        参数:
            llm_provider: LLM 提供者（默认使用 WorkBuddy Agent）
            experience_db: 经验数据库路径
            auto_extract_patterns: 是否自动从历史数据提取模式（冷启动）
            enable_evolution: 是否启用自进化能力
        """
        self.llm_provider = llm_provider or WorkBuddyAgentProvider()
        self.experience_memory = ExperienceMemory(db_path=experience_db)
        self.auto_extract_patterns = auto_extract_patterns
        self.enable_evolution = enable_evolution

        # 组件
        self.brief_generator = BriefGenerator()
        self.reasoning_engine = ReasoningEngine(self.llm_provider)

        # 进化管理器
        if enable_evolution:
            self.evolution_manager = EvolutionManager(
                experience_memory=self.experience_memory,
                db_path=experience_db.replace(".db", "_evolution.db") if experience_db else "evolution.db",
            )
        else:
            self.evolution_manager = None

    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN",
        timeframe: str = "daily",
        top_k_experiences: int = 10,
    ) -> TradingBrief:
        """
        执行分析 —— 主入口

        参数:
            df: 包含 OHLCV 数据的 DataFrame
            symbol: 品种代码
            timeframe: 时间周期
            top_k_experiences: 检索的相似经验数量

        返回:
            TradingBrief 交易决策简报
        """
        start_time = time.time()

        # ──────────────────────────────────────
        # Step 1: 感知层 —— 组装上下文
        # ──────────────────────────────────────
        assembler = ContextAssembler(symbol, timeframe)
        context = assembler.assemble(df)

        # ──────────────────────────────────────
        # Step 2: 经验层 —— 检索相似经验
        # ──────────────────────────────────────
        # 冷启动：如果没有经验，从历史数据提取
        if self.experience_memory.get_experience_count() == 0 and self.auto_extract_patterns:
            self._cold_start(df, symbol)

        # 检索相似经验
        similar_experiences = self.experience_memory.retrieve(context, top_k=top_k_experiences)

        # 聚合经验
        experience_aggregation = self.experience_memory.aggregate_routes(similar_experiences)

        # ──────────────────────────────────────
        # Step 3: 推理层 —— 调用 LLM 推理
        # ──────────────────────────────────────
        reasoning_result = self.reasoning_engine.reason(
            context=context,
            similar_experiences=similar_experiences,
            experience_aggregation=experience_aggregation,
        )

        # ──────────────────────────────────────
        # Step 4: 交互层 —— 生成交易决策简报
        # ──────────────────────────────────────
        brief = self.brief_generator.generate(
            context=context,
            reasoning_result=reasoning_result,
            similar_experiences=similar_experiences,
        )

        # ──────────────────────────────────────
        # Step 5: 进化层 —— 记录分析结果
        # ──────────────────────────────────────
        if self.evolution_manager:
            self.evolution_manager.record_analysis(context, brief)

        return brief

    def analyze_and_format(
        self,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN",
        timeframe: str = "daily",
        format: str = "markdown",
    ) -> str:
        """
        执行分析并返回格式化的文本

        参数:
            df: 包含 OHLCV 数据的 DataFrame
            symbol: 品种代码
            timeframe: 时间周期
            format: 输出格式（markdown / plain / notification）

        返回:
            格式化的交易决策简报文本
        """
        brief = self.analyze(df, symbol, timeframe)

        if format == "markdown":
            return BriefFormatter.to_markdown(brief)
        elif format == "plain":
            return BriefFormatter.to_plain_text(brief)
        elif format == "notification":
            return BriefFormatter.to_notification(brief)
        else:
            return BriefFormatter.to_markdown(brief)

    def record_feedback(self, feedback: UserFeedback, context: MarketContext = None, brief: TradingBrief = None):
        """
        记录用户反馈

        用户选择的方案和实际结果会被记录到经验池，
        用于未来的类比推理和自进化。

        参数:
            feedback: 用户反馈
            context: 当时的市场上下文（可选，用于进化分析）
            brief: 当时的交易决策简报（可选，用于进化分析）
        """
        if self.evolution_manager:
            # 使用进化管理器记录（包含经验积累和进化触发）
            self.evolution_manager.record_feedback(feedback, context, brief)
        else:
            # 简单记录到经验池
            experience = Experience(
                experience_id=f"fb_{feedback.feedback_id}",
                timestamp=feedback.timestamp,
                symbol=feedback.symbol,
                action_taken=feedback.actual_action,
                action_reasoning=f"用户选择方案{feedback.chosen_route}",
                entry_price=feedback.entry_price,
                exit_price=feedback.exit_price,
                pnl_pct=feedback.pnl_pct,
                holding_days=feedback.holding_days,
                user_rating=feedback.satisfaction,
                user_notes=feedback.notes,
            )
            self.experience_memory.add_experience(experience)

    def get_experience_stats(self) -> dict:
        """获取经验池统计"""
        stats = {
            "total_experiences": self.experience_memory.get_experience_count(),
            "phase_distribution": self.experience_memory.get_phase_distribution(),
        }

        # 添加进化统计
        if self.evolution_manager:
            stats["evolution"] = self.evolution_manager.get_evolution_status()
            stats["experience_details"] = self.evolution_manager.get_experience_stats()

        return stats

    def run_evolution(self, reason: str = "手动触发", df: pd.DataFrame = None) -> dict:
        """
        手动触发进化

        参数:
            reason: 触发原因
            df: K线数据（用于轨迹分析）

        返回:
            进化结果
        """
        if not self.evolution_manager:
            return {"error": "进化功能未启用"}

        return self.evolution_manager.run_evolution(reason, df)

    # ──────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────

    def _cold_start(self, df: pd.DataFrame, symbol: str):
        """
        冷启动：从历史数据中提取模式

        当经验池为空时，自动从历史K线中提取相似模式，
        作为推理的初始经验来源。
        """
        count = self.experience_memory.extract_patterns_from_history(df, symbol, window=20, step=5, forward_days=10)


class TradingAssistantFactory:
    """
    交易辅助系统工厂

    简化系统的创建过程。
    """

    @staticmethod
    def create(
        llm_type: str = "workbuddy",
        experience_db: str | None = None,
        **kwargs,
    ) -> TradingAssistant:
        """
        创建交易辅助系统实例

        参数:
            llm_type: LLM 类型（workbuddy / custom）
            experience_db: 经验数据库路径
            **kwargs: 其他参数
        """
        if llm_type == "workbuddy":
            llm_provider = WorkBuddyAgentProvider()
        elif llm_type == "custom":
            from .reasoning import CustomLLMProvider

            llm_provider = CustomLLMProvider(
                api_url=kwargs.get("api_url", ""),
                api_key=kwargs.get("api_key", ""),
                model=kwargs.get("model", "default"),
            )
        else:
            llm_provider = WorkBuddyAgentProvider()

        return TradingAssistant(
            llm_provider=llm_provider,
            experience_db=experience_db,
            auto_extract_patterns=kwargs.get("auto_extract_patterns", True),
        )

    @staticmethod
    def create_with_datastore(
        datastore: DataStore,
        llm_type: str = "workbuddy",
        **kwargs,
    ) -> TradingAssistant:
        """使用 DataStore 创建交易辅助系统"""
        db_path = datastore.db_path.replace(".db", "_experience.db")
        return TradingAssistantFactory.create(
            llm_type=llm_type,
            experience_db=db_path,
            **kwargs,
        )
