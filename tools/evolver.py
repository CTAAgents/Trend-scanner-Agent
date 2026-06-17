#!/usr/bin/env python3
"""
Evolver Agent 脚本

封装现有的进化管理器，提供标准化的输入输出接口。

职责：
1. 记录交易反馈
2. 轨迹分析与故障归因
3. 模式检测与规则优化
4. 过拟合审计
5. 因子生命周期管理（S0-S7）
6. 因子健康度监控

用法：
    # 处理单个交易反馈
    python tools/evolver.py --feedback data/trade_feedback.json

    # 查看进化历史
    python tools/evolver.py --history

    # 执行定期进化
    python tools/evolver.py --periodic

    # 检查因子健康度
    python tools/evolver.py --health-check

    # 查看因子生命周期统计
    python tools/evolver.py --lifecycle-stats
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.evolution_manager import EvolutionManager
from trend_scanner.factor_lifecycle import FactorAsset, FactorLifecycleManager, LifecycleState
from trend_scanner.factor_health_monitor import FactorHealthMonitor, HealthStatus
from trend_scanner.factor_graph import FactorProvenanceGraph
from trend_scanner.models import UserFeedback
from trend_scanner.rl_interface_designer import RLInterfaceDesigner


class EvolverAgent:
    """
    Evolver Agent

    从交易结果中学习，优化策略。
    集成因子生命周期管理、健康度监控和溯源图。
    """

    def __init__(self, config: dict[str, Any] = None):
        """
        初始化 Evolver Agent

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.evolver_config = self.config.get("evolver", {})

        # 初始化进化管理器
        db_path = self.config.get("experience_db_path", "evolution.db")
        self.evolution_manager = EvolutionManager(db_path=db_path)

        # 初始化因子生命周期管理器
        self.lifecycle_manager = FactorLifecycleManager()
        self.health_monitor = FactorHealthMonitor(self.lifecycle_manager)
        self.provenance_graph = FactorProvenanceGraph()

        # 触发条件
        self.auto_trigger = self.evolver_config.get(
            "auto_trigger", {"consecutive_losses": 3, "cumulative_loss_pct": 10, "trade_count_interval": 20}
        )

    def _check_trigger_conditions(self) -> dict[str, Any]:
        """
        检查触发条件

        Returns:
            触发条件状态
        """
        # EvolutionManager 没有 get_statistics 方法，使用默认值
        # TODO: 实现统计功能
        return {"consecutive_losses": 0, "cumulative_loss_pct": 0, "trade_count": 0, "should_trigger": False}

    def evolve(self, feedback: dict[str, Any]) -> dict[str, Any]:
        """
        执行进化

        Args:
            feedback: 交易反馈数据

        Returns:
            进化报告
        """
        symbol = feedback.get("symbol", "")
        print(f"[Evolver] 处理 {symbol} 的交易反馈...", flush=True)

        try:
            # 构建 UserFeedback 对象
            user_feedback = UserFeedback(
                symbol=symbol,
                direction=feedback.get("direction", ""),
                entry_price=feedback.get("entry_price", 0),
                exit_price=feedback.get("exit_price", 0),
                entry_time=feedback.get("entry_time", ""),
                exit_time=feedback.get("exit_time", ""),
                pnl_pct=feedback.get("pnl_pct", 0),
                pnl_amount=feedback.get("pnl_amount", 0),
                holding_days=feedback.get("holding_days", 0),
                exit_reason=feedback.get("exit_reason", ""),
                user_decision=feedback.get("user_decision", ""),
                user_notes=feedback.get("user_notes", ""),
            )

            # 记录反馈（使用 EvolutionManager 的 record_feedback 方法）
            experience = self.evolution_manager.record_feedback(
                feedback=user_feedback,
                context=feedback.get("market_context_at_entry"),
                brief=feedback.get("brief_at_entry"),
            )

            # 构建结果
            result = {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "evolution_report": {
                    "experience_id": experience.experience_id if experience else "",
                    "symbol": symbol,
                    "pnl_pct": feedback.get("pnl_pct", 0),
                    "holding_days": feedback.get("holding_days", 0),
                    "exit_reason": feedback.get("exit_reason", ""),
                    "status": "recorded",
                },
                "experience_saved": True,
                "experience_id": experience.experience_id if experience else "",
            }

            # RL 接口诊断（v6.1 新增）
            try:
                rl_designer = RLInterfaceDesigner()
                # 基于交易结果诊断是否需要 RL 接口重设计
                rl_diagnosis = rl_designer.diagnose_interface(
                    symbol=symbol,
                    pnl_pct=feedback.get("pnl_pct", 0),
                    holding_days=feedback.get("holding_days", 0),
                    exit_reason=feedback.get("exit_reason", ""),
                    market_context=feedback.get("market_context_at_entry"),
                )
                result["rl_diagnosis"] = rl_diagnosis
            except Exception as e:
                logger.debug(f"RL 接口诊断失败: {e}")

            print(f"[Evolver] {symbol} 反馈记录完成", flush=True)
            return result

        except Exception as e:
            print(f"[错误] 进化失败: {e}", flush=True)
            import traceback

            traceback.print_exc()

            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "evolution_report": {"error": str(e)},
                "experience_saved": False,
                "error": str(e),
            }

    def evolve_periodic(self) -> dict[str, Any]:
        """
        执行定期进化

        Returns:
            进化报告
        """
        print("[Evolver] 执行定期进化...", flush=True)

        try:
            # 检查触发条件
            trigger_status = self._check_trigger_conditions()

            if not trigger_status["should_trigger"]:
                print("[Evolver] 未达到触发条件，跳过", flush=True)
                return {
                    "timestamp": datetime.now().isoformat(),
                    "trigger_status": trigger_status,
                    "evolution_executed": False,
                    "reason": "未达到触发条件",
                }

            # 执行定期进化
            evolution_result = self.evolution_manager.periodic_evolution()

            result = {
                "timestamp": datetime.now().isoformat(),
                "trigger_status": trigger_status,
                "evolution_executed": True,
                "evolution_report": evolution_result,
            }

            print("[Evolver] 定期进化完成", flush=True)
            return result

        except Exception as e:
            print(f"[错误] 定期进化失败: {e}", flush=True)
            return {"timestamp": datetime.now().isoformat(), "evolution_executed": False, "error": str(e)}

    def get_history(self) -> dict[str, Any]:
        """
        获取进化历史

        Returns:
            进化历史
        """
        try:
            # EvolutionManager 没有 get_evolution_history 方法
            # 返回基本状态信息
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "EvolutionManager 已初始化",
                "evolution_history_count": len(self.evolution_manager.evolution_history)
                if hasattr(self.evolution_manager, "evolution_history")
                else 0,
                "last_evolution_time": self.evolution_manager.last_evolution_time
                if hasattr(self.evolution_manager, "last_evolution_time")
                else None,
                "evolution_count": self.evolution_manager.evolution_count
                if hasattr(self.evolution_manager, "evolution_count")
                else 0,
            }

        except Exception as e:
            print(f"[错误] 获取进化历史失败: {e}", flush=True)
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}

    def check_factor_health(self) -> dict[str, Any]:
        """
        检查所有因子健康度

        Returns:
            健康度检查报告
        """
        print("[Evolver] 检查因子健康度...", flush=True)

        try:
            reports = self.health_monitor.check_all_factors()

            # 自动降级不健康的因子
            degraded_count = 0
            for report in reports:
                if report.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL):
                    factor = self.lifecycle_manager.get_factor(report.factor_id)
                    if factor:
                        self.health_monitor.auto_degrade_factor(factor, report)
                        degraded_count += 1

            # 生成维护提案
            proposals = self.health_monitor.generate_maintenance_proposals()

            result = {
                "timestamp": datetime.now().isoformat(),
                "total_checked": len(reports),
                "healthy": sum(1 for r in reports if r.status == HealthStatus.HEALTHY),
                "warning": sum(1 for r in reports if r.status == HealthStatus.WARNING),
                "degraded": sum(1 for r in reports if r.status == HealthStatus.DEGRADED),
                "critical": sum(1 for r in reports if r.status == HealthStatus.CRITICAL),
                "auto_degraded": degraded_count,
                "proposals_generated": len(proposals),
                "reports": [
                    {
                        "factor_id": r.factor_id,
                        "factor_name": r.factor_name,
                        "status": r.status.value,
                        "issues": r.issues,
                    }
                    for r in reports
                ],
            }

            print(f"[Evolver] 健康度检查完成: {result['healthy']}健康, {result['warning']}警告, {result['degraded']}退化", flush=True)
            return result

        except Exception as e:
            print(f"[错误] 健康度检查失败: {e}", flush=True)
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}

    def get_lifecycle_stats(self) -> dict[str, Any]:
        """
        获取因子生命周期统计

        Returns:
            生命周期统计
        """
        try:
            stats = self.lifecycle_manager.get_statistics()
            graph_stats = self.provenance_graph.get_statistics()

            return {
                "timestamp": datetime.now().isoformat(),
                "lifecycle": stats,
                "provenance_graph": graph_stats,
            }

        except Exception as e:
            print(f"[错误] 获取生命周期统计失败: {e}", flush=True)
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Evolver Agent 脚本")
    parser.add_argument("--feedback", type=str, help="交易反馈文件路径")
    parser.add_argument("--history", action="store_true", help="查看进化历史")
    parser.add_argument("--periodic", action="store_true", help="执行定期进化")
    parser.add_argument("--health-check", action="store_true", help="检查因子健康度")
    parser.add_argument("--lifecycle-stats", action="store_true", help="查看因子生命周期统计")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")
    parser.add_argument("--save", action="store_true", help="保存结果到 data/latest_evolution.json")

    args = parser.parse_args()

    # 创建 Evolver Agent
    agent = EvolverAgent()

    # 执行进化
    result = None

    if args.feedback:
        # 处理交易反馈
        try:
            with open(args.feedback, encoding="utf-8") as f:
                feedback = json.load(f)
            result = agent.evolve(feedback)
        except Exception as e:
            print(f"[错误] 读取反馈文件失败: {e}", flush=True)
            sys.exit(1)
    elif args.history:
        # 查看进化历史
        result = agent.get_history()
    elif args.periodic:
        # 执行定期进化
        result = agent.evolve_periodic()
    elif args.health_check:
        # 检查因子健康度
        result = agent.check_factor_health()
    elif args.lifecycle_stats:
        # 查看因子生命周期统计
        result = agent.get_lifecycle_stats()
    else:
        print("[错误] 请指定 --feedback, --history, --periodic, --health-check 或 --lifecycle-stats", flush=True)
        sys.exit(1)

    # 输出结果
    if result:
        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n{'=' * 70}")
            print("Evolver Agent 进化报告")
            print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'=' * 70}")

            symbol = result.get("symbol", "")
            if symbol:
                print(f"\n品种: {symbol}")

            evolution_report = result.get("evolution_report", {})
            if evolution_report:
                # 轨迹分析
                trajectory = evolution_report.get("trajectory_analysis", {})
                if trajectory:
                    print("\n[轨迹分析]")
                    print(f"  入场质量: {trajectory.get('entry_quality', 'UNKNOWN')}")
                    print(f"  出场质量: {trajectory.get('exit_quality', 'UNKNOWN')}")
                    print(f"  持有效率: {trajectory.get('holding_efficiency', 0):.2f}")

                # 故障归因
                fault = evolution_report.get("fault_attribution", {})
                if fault:
                    print("\n[故障归因]")
                    print(f"  主要故障: {fault.get('primary_fault', 'NONE')}")
                    print(f"  故障严重度: {fault.get('fault_severity', 0):.2f}")

                # 反思
                reflection = evolution_report.get("reflection", {})
                if reflection:
                    print("\n[反思]")
                    what_went_well = reflection.get("what_went_well", [])
                    if what_went_well:
                        print("  做得好的:")
                        for item in what_went_well:
                            print(f"    - {item}")

                    what_to_improve = reflection.get("what_to_improve", [])
                    if what_to_improve:
                        print("  需改进的:")
                        for item in what_to_improve:
                            print(f"    - {item}")

            print(f"\n{'=' * 70}")

        # 保存结果
        if args.save and result:
            output_path = project_root / "data" / "latest_evolution.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存到 {output_path}")


if __name__ == "__main__":
    main()
