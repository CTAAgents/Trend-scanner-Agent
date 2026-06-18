#!/usr/bin/env python3
"""
Reasoner Agent 脚本

封装现有的推理引擎，提供标准化的输入输出接口。

职责：
1. 接收 Scanner 脚本或 Monitor 脚本的信号
2. 读取完整的 MarketContext
3. 检索相似经验
4. 调用 LLM 推理
5. 生成交易决策简报

用法：
    # 分析单个品种
    python tools/reasoner.py --symbol DCE.jm2609 --direction LONG

    # 分析信号文件
    python tools/reasoner.py --signal data/latest_scan.json

    # 输出 JSON 格式
    python tools/reasoner.py --symbol DCE.jm2609 --output json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from reasoning.brief import BriefGenerator
from core.context import ContextAssembler
from core.memory.memory_bridge import MemoryBridge
from core.models import MarketContext
from reasoning.reasoning_engine import ReasoningEngine, WorkBuddyAgentProvider
from reasoning.narrative_generator import NarrativeGenerator
from core.data.unified_data_router import get_router


class ReasonerAgent:
    """
    Reasoner Agent

    接收市场信号，生成交易决策简报。
    """

    def __init__(self, config: dict[str, Any] = None):
        """
        初始化 Reasoner Agent

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.reasoner_config = self.config.get("reasoner", {})

        # 初始化组件
        self.llm_provider = WorkBuddyAgentProvider(model=self.reasoner_config.get("llm_type", "default"))
        self.reasoning_engine = ReasoningEngine(llm_provider=self.llm_provider)
        self.brief_generator = BriefGenerator()
        self.experience_memory = ExperienceMemory(db_path=self.config.get("experience_db_path", "evolution.db"))
        # ContextAssembler 需要 symbol 参数，在 analyze 时动态创建
        self.context_assembler = None

        # 数据源
        self.data_source = None

    def _init_data_source(self):
        """初始化数据源（统一路由层：DuckDB > TqSDK > Pytdx > AkShare > CSV）"""
        if self.data_source is None:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "config.json")
            self.data_source = get_router(config_path=config_path, db_dir="data")

        return self.data_source

    def _get_market_context(self, symbol: str, direction: str = None) -> MarketContext | None:
        """
        获取市场上下文

        Args:
            symbol: 品种代码（如 "DCE.jm2609"）
            direction: 方向（LONG/SHORT）

        Returns:
            MarketContext 对象
        """
        try:
            ds = self._init_data_source()
            if ds is None:
                print("[错误] 没有可用的数据源", flush=True)
                return None

            # 从 symbol 中提取品种代码
            parts = symbol.split(".")
            if len(parts) >= 2:
                contract = parts[1]
                variety = "".join([c for c in contract if not c.isdigit()])
            else:
                variety = symbol

            # 获取K线数据（通过统一路由层）
            kline_resp = ds.get_kline(variety, days=120)
            df = kline_resp.data if hasattr(kline_resp, "data") else kline_resp
            if df is None or len(df) < 60:
                print(f"[警告] {symbol} 数据不足(来源: {getattr(kline_resp, 'source', 'unknown')})", flush=True)
                return None

            # 动态创建 ContextAssembler
            context_assembler = ContextAssembler(symbol=symbol)

            # 组装上下文
            context = context_assembler.assemble(df=df)

            return context

        except Exception as e:
            print(f"[错误] 获取 {symbol} 市场上下文失败: {e}", flush=True)
            import traceback

            traceback.print_exc()
            return None

    def _get_similar_experiences(self, context: MarketContext) -> list[dict]:
        """
        检索相似经验

        Args:
            context: 市场上下文

        Returns:
            相似经验列表
        """
        try:
            top_k = self.reasoner_config.get("experience_top_k", 5)
            threshold = self.reasoner_config.get("experience_similarity_threshold", 0.6)

            # 使用retrieve方法（ExperienceMemory的标准接口）
            experiences = self.experience_memory.retrieve(context=context, top_k=top_k, min_similarity=threshold)

            return experiences

        except Exception as e:
            print(f"[警告] 经验检索失败: {e}", flush=True)
            return []

    def analyze(self, signal: dict[str, Any], output_level: str = None) -> dict[str, Any]:
        """
        分析信号，生成交易决策简报

        Args:
            signal: 信号字典，包含 symbol, direction 等信息
            output_level: 输出级别 (formal/standard/brief)，None=标准输出

        Returns:
            交易决策简报（JSON 格式）
        """
        symbol = signal.get("symbol", "")
        direction = signal.get("direction", "")

        print(f"[Reasoner] 分析 {symbol} ({direction})...", flush=True)

        # 1. 获取市场上下文
        context = self._get_market_context(symbol, direction)
        if context is None:
            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "status": "ERROR",
                "error": "无法获取市场上下文",
                "routes": [],
                "recommended_route": "",
                "warnings": ["数据不足，无法分析"],
            }

        # 2. 检索相似经验
        similar_experiences = self._get_similar_experiences(context)
        print(f"[Reasoner] 找到 {len(similar_experiences)} 条相似经验", flush=True)

        # 3. 聚合经验
        experience_aggregation = self.experience_memory.aggregate_routes(similar_experiences)

        # 提取多维度评分结果（如果信号中包含）
        multi_dimension_result = signal.get("multi_dimension")

        # 提取历史交易盈亏（用于蒙特卡洛模拟）
        trade_history = signal.get("trade_history")

        # 提取熔断器状态
        circuit_breaker_status = signal.get("circuit_breaker_status")

        # 4. 执行推理
        try:
            reasoning_result = self.reasoning_engine.reason(
                context=context,
                similar_experiences=similar_experiences,
                experience_aggregation=experience_aggregation,
                multi_dimension_result=multi_dimension_result,
                trade_history=trade_history,
                circuit_breaker_status=circuit_breaker_status,
            )
        except Exception as e:
            print(f"[错误] 推理失败: {e}", flush=True)
            reasoning_result = {
                "routes": [
                    {
                        "route_id": "A",
                        "name": "错误",
                        "action": f"推理失败: {e}",
                        "confidence": 0,
                        "reasoning": str(e),
                        "constraints": [],
                        "risks": ["推理失败，建议仅供参考"],
                    }
                ],
                "recommended_route": "A",
                "warnings": [f"推理失败: {e}"],
            }

        # 5. 生成简报
        try:
            brief = self.brief_generator.generate(
                context=context, reasoning_result=reasoning_result, similar_experiences=similar_experiences
            )
            result = brief.to_dict()
        except Exception as e:
            print(f"[错误] 简报生成失败: {e}", flush=True)
            result = {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "status": "ERROR",
                "error": str(e),
                "routes": reasoning_result.get("routes", []),
                "recommended_route": reasoning_result.get("recommended_route", ""),
                "warnings": reasoning_result.get("warnings", []),
            }

        # 6. 添加元信息
        result["analysis_time"] = datetime.now().isoformat()
        result["signal"] = signal

        # 7. 分级输出格式化（v6.1 新增）
        if output_level:
            try:
                formatter = TieredOutputFormatter()
                # 构建格式化上下文
                fmt_ctx = {
                    "symbol": symbol,
                    "direction": direction,
                    "confidence": reasoning_result.get("confidence", 0),
                    "trend_phase": getattr(context, "trend_phase", type("", (), {"phase": "UNKNOWN"})()).phase
                    if context
                    else "UNKNOWN",
                    "indicators": {},
                    "operation_plans": [],
                    "risks": reasoning_result.get("warnings", []),
                }
                # 提取指标
                if context and hasattr(context, "indicator_snapshot"):
                    snap = context.indicator_snapshot
                    for attr in ["er", "tsi", "r_squared", "hurst", "rsi", "adx"]:
                        if hasattr(snap, attr):
                            fmt_ctx["indicators"][attr] = getattr(snap, attr)
                # 提取操作方案
                for route in reasoning_result.get("routes", []):
                    fmt_ctx["operation_plans"].append(
                        {
                            "action": route.get("action", ""),
                            "reason": route.get("reasoning", ""),
                            "position": next((c.value for c in route.get("constraints", []) if "仓位" in c.name), ""),
                            "stop_loss": next((c.value for c in route.get("constraints", []) if "止损" in c.name), ""),
                        }
                    )
                # 格式化输出
                result["formatted_output"] = formatter.format(fmt_ctx, level=output_level)
                result["output_level"] = output_level
            except Exception as e:
                logger.debug(f"分级输出格式化失败: {e}")

        return result

    def analyze_from_file(self, signal_file: str) -> list[dict[str, Any]]:
        """
        从信号文件分析多个品种

        Args:
            signal_file: 信号文件路径（JSON 格式）

        Returns:
            分析结果列表
        """
        try:
            with open(signal_file, encoding="utf-8") as f:
                data = json.load(f)

            signals = data.get("signals", [])
            if not signals:
                print("[警告] 信号文件中没有信号", flush=True)
                return []

            results = []
            for signal in signals:
                result = self.analyze(signal)
                results.append(result)

            return results

        except Exception as e:
            print(f"[错误] 读取信号文件失败: {e}", flush=True)
            return []


def main():
    parser = argparse.ArgumentParser(description="Reasoner Agent 脚本")
    parser.add_argument("--symbol", type=str, help="品种代码（如 DCE.jm2609）")
    parser.add_argument("--direction", type=str, choices=["LONG", "SHORT"], help="方向")
    parser.add_argument("--signal", type=str, help="信号文件路径")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")
    parser.add_argument("--save", action="store_true", help="保存结果到 data/latest_brief.json")

    args = parser.parse_args()

    # 创建 Reasoner Agent
    agent = ReasonerAgent()

    # 执行分析
    results = []

    if args.symbol:
        # 分析单个品种
        signal = {
            "symbol": args.symbol,
            "direction": args.direction or "LONG",
            "trend_phase": "UNKNOWN",
            "trend_strength_composite": 0,
            "tsi": 0,
            "er": 0,
            "r_squared": 0,
            "key_signals": [],
            "risk_factors": [],
        }
        result = agent.analyze(signal)
        results.append(result)
    elif args.signal:
        # 分析信号文件
        results = agent.analyze_from_file(args.signal)
    else:
        print("[错误] 请指定 --symbol 或 --signal", flush=True)
        sys.exit(1)

    # 输出结果
    if args.output == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'=' * 70}")
        print("Reasoner Agent 分析报告")
        print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 70}")

        for result in results:
            symbol = result.get("symbol", "")
            status = result.get("status", "OK")
            routes = result.get("routes", [])
            recommended = result.get("recommended_route", "")
            warnings = result.get("warnings", [])

            print(f"\n【{symbol}】状态: {status}")

            if routes:
                print(f"  推荐方案: {recommended}")
                for route in routes:
                    route_id = route.get("route_id", "")
                    name = route.get("name", "")
                    confidence = route.get("confidence", 0)
                    action = route.get("action", "")
                    print(f"  [{route_id}] {name} (置信度: {confidence:.2f})")
                    print(f"      操作: {action}")

            if warnings:
                print("  [警告]:")
                for warning in warnings:
                    print(f"    - {warning}")

        print(f"\n{'=' * 70}")

    # 保存结果
    if args.save and results:
        output_path = project_root / "data" / "latest_brief.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到 {output_path}")


if __name__ == "__main__":
    main()
