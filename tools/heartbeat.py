"""
心跳监控脚本 — 状态变化驱动的市场监控

纯 Python 实现（无 LLM），每 5 分钟检查一次市场状态。
只在检测到状态变化时输出事件，触发 Orchestrator → Reasoner Agent。

状态变化类型：
- 持仓品种价格突破止损/止盈
- 持仓品种趋势反转信号
- 全品种趋势强度突变
- 新品种出现强信号
- 因子健康度退化（新增）

使用方式：
    python tools/heartbeat.py                    # 单次心跳检查（全部品种）
    python tools/heartbeat.py --loop             # 持续循环（每 5 分钟）
    python tools/heartbeat.py --positions-only   # 只监控持仓
    python tools/heartbeat.py --config-only      # 仅扫描配置文件中的品种
    python tools/heartbeat.py --factor-health    # 检查因子健康度
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any


# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

# 导入数据格式工具
from data_formats import (
    create_alert,
    get_signal_filter,
    load_config,
)

from trend_scanner.data_source import DataSourceFactory
from trend_scanner.indicators import IndicatorEngine
from trend_scanner.factor_health_monitor import FactorHealthMonitor, HealthStatus
from trend_scanner.factor_lifecycle import FactorLifecycleManager, LifecycleState


def get_all_main_contracts() -> list[str]:
    """
    获取所有主力合约品种列表

    返回:
        品种列表（配置格式，如 ['SHFE.rb', 'DCE.jm']）
    """
    try:
        # 从 data_source.py 中获取 MAIN_CONTRACT_MAP
        with open(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "trend_scanner", "data_source.py"),
            encoding="utf-8",
        ) as f:
            content = f.read()

        # 提取 MAIN_CONTRACT_MAP
        start = content.find("MAIN_CONTRACT_MAP = {")
        if start == -1:
            return []

        # 找到对应的结束大括号
        brace_count = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == "{":
                brace_count += 1
            elif content[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break

        map_str = content[start:end]

        # 执行并获取所有品种
        exec_globals = {}
        exec(map_str, exec_globals)
        MAIN_CONTRACT_MAP = exec_globals.get("MAIN_CONTRACT_MAP", {})

        symbols = list(MAIN_CONTRACT_MAP.values())

        # 转换为配置格式
        config_symbols = []
        for s in symbols:
            # KQ.m@SHFE.rb -> SHFE.rb
            parts = s.split("@")
            if len(parts) == 2:
                config_symbols.append(parts[1])

        return config_symbols
    except Exception as e:
        print(f"[警告] 获取所有品种列表失败: {e}", file=sys.stderr)
        return []


def get_realtime_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """
    获取实时行情（快速，不下载K线）

    参数:
        symbols: 品种列表（如 ['DCE.jm2609', 'SHFE.ao2609']）

    返回:
        {symbol: {last_price, open_interest, volume, change_percent}}
    """
    import os

    tq_user = os.environ.get("TQ_USER", "")
    tq_password = os.environ.get("TQ_PASSWORD", "")

    if not tq_user or not tq_password:
        return {}

    try:
        from tqsdk import TqApi, TqAuth

        auth = TqAuth(tq_user, tq_password)

        with TqApi(auth=auth) as api:
            quotes = {}
            for sym in symbols:
                try:
                    quotes[sym] = api.get_quote(sym)
                except:
                    pass

            api.wait_update(deadline=time.time() + 10)

            result = {}
            for sym in symbols:
                if sym in quotes:
                    q = quotes[sym]
                    result[sym] = {
                        "last_price": getattr(q, "last_price", 0) or 0,
                        "open_interest": getattr(q, "open_interest", 0) or 0,
                        "volume": getattr(q, "volume", 0) or 0,
                        "change_percent": getattr(q, "change_percent", 0) or 0,
                        "highest": getattr(q, "highest", 0) or 0,
                        "lowest": getattr(q, "lowest", 0) or 0,
                    }
            return result
    except Exception as e:
        print(f"  获取实时行情失败: {e}", file=sys.stderr)
        return {}


# 状态缓存文件
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STATE_FILE = os.path.join(DATA_DIR, "heartbeat_state.json")
POSITIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "positions.json")


def load_state() -> dict[str, Any]:
    """加载上次心跳状态"""
    if not os.path.exists(STATE_FILE):
        return {"last_check": None, "positions": {}, "symbols": {}}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict[str, Any]):
    """保存心跳状态"""
    os.makedirs(DATA_DIR, exist_ok=True)
    state["last_check"] = datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_positions() -> list[dict[str, Any]]:
    """加载持仓数据"""
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    # 兼容两种格式：直接列表 或 {"positions": [...]}
    if isinstance(data, list):
        return data
    return data.get("positions", [])


def normalize_symbol(symbol: str) -> str:
    """将配置格式的品种代码转换为数据源可识别的格式"""
    symbol = symbol.strip()
    if "." in symbol:
        parts = symbol.split(".")
        if len(parts) == 2:
            return parts[1].upper()
    return symbol.upper()


def check_factor_health() -> dict[str, Any]:
    """
    检查因子健康度

    在心跳检查中集成因子健康度监控，自动检测退化并生成维护提案。

    Returns:
        因子健康度检查报告
    """
    try:
        # 初始化因子生命周期管理器和健康监控器
        lifecycle_manager = FactorLifecycleManager()
        health_monitor = FactorHealthMonitor(lifecycle_manager)

        # 检查所有已发布因子的健康度
        reports = health_monitor.check_all_factors()

        # 自动降级不健康的因子
        degraded_factors = []
        for report in reports:
            if report.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL):
                factor = lifecycle_manager.get_factor(report.factor_id)
                if factor:
                    health_monitor.auto_degrade_factor(factor, report)
                    degraded_factors.append({
                        "factor_id": report.factor_id,
                        "factor_name": report.factor_name,
                        "status": report.status.value,
                        "issues": report.issues,
                    })

        # 生成维护提案
        proposals = []
        for report in reports:
            if report.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL):
                factor = lifecycle_manager.get_factor(report.factor_id)
                if factor:
                    proposal = health_monitor.generate_proposal(factor, report)
                    proposals.append(proposal)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_checked": len(reports),
            "healthy": sum(1 for r in reports if r.status == HealthStatus.HEALTHY),
            "warning": sum(1 for r in reports if r.status == HealthStatus.WARNING),
            "degraded": sum(1 for r in reports if r.status == HealthStatus.DEGRADED),
            "critical": sum(1 for r in reports if r.status == HealthStatus.CRITICAL),
            "degraded_factors": degraded_factors,
            "proposals": [
                {
                    "factor_id": p.factor_id,
                    "action": p.action.value,
                    "reason": p.reason,
                }
                for p in proposals
            ],
        }

    except Exception as e:
        return {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


def check_position_alerts(
    positions: list[dict[str, Any]],
    data_source,
    prev_state: dict[str, Any],
    realtime_quotes: dict[str, dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """
    检查持仓品种的风险预警（混合模式：本地K线算指标 + 实时报价算盈亏）

    参数:
        positions: 持仓列表
        data_source: 数据源实例
        prev_state: 上次心跳状态
        realtime_quotes: 实时行情数据

    返回:
        预警列表
    """
    alerts = []
    config = load_config()
    alert_thresholds = config.get("monitor", {}).get("alert_thresholds", {})

    for pos in positions:
        symbol = pos.get("symbol", "")
        direction = pos.get("direction", "")
        entry_price = pos.get("entry_price", 0)
        data_symbol = normalize_symbol(symbol)

        try:
            # 获取当前数据（心跳模式禁用 TqSdk 兜底，避免超时阻塞）
            df = data_source.get_kline(data_symbol, days=120, allow_tqsdk_fallback=False)
            if df is None or len(df) < 60:
                continue

            # 计算指标
            engine = IndicatorEngine(df)
            engine.compute_all()
            composite = engine.get_trend_strength_composite()
            engine.df["trend_strength_composite"] = composite

            latest = engine.df.iloc[-1]
            # 优先使用实时报价，其次用本地K线收盘价
            realtime_price = 0
            if realtime_quotes and symbol in realtime_quotes:
                realtime_price = realtime_quotes[symbol].get("last_price", 0)
            current_price = realtime_price if realtime_price > 0 else float(latest.get("close", 0))
            er = float(latest.get("er", 0))
            tsi = float(latest.get("tsi", 0))
            trend_strength = float(composite.iloc[-1])

            # 计算浮动盈亏
            if entry_price > 0 and current_price > 0:
                if direction == "LONG":
                    pnl_pct = (current_price / entry_price - 1) * 100
                else:
                    pnl_pct = (1 - current_price / entry_price) * 100
            else:
                pnl_pct = 0

            # 获取上次状态
            prev_symbol_state = prev_state.get("positions", {}).get(symbol, {})
            prev_trend_strength = prev_symbol_state.get("trend_strength", trend_strength)

            # 计算趋势强度变化
            strength_change = trend_strength - prev_trend_strength

            # 检查预警条件
            high_threshold = alert_thresholds.get("HIGH", {})
            medium_threshold = alert_thresholds.get("MEDIUM", {})

            # HIGH 级别：趋势强度大幅下降
            if strength_change < -high_threshold.get("trend_strength_drop", 0.35):
                alerts.append(
                    create_alert(
                        symbol=symbol,
                        alert_type="TREND_REVERSAL",
                        severity="HIGH",
                        indicators={
                            "trend_strength": round(trend_strength, 3),
                            "trend_strength_change": round(strength_change, 3),
                            "er": round(er, 3),
                            "tsi": round(tsi, 2),
                            "current_price": current_price,
                        },
                        trigger_reason=f"趋势强度骤降 {strength_change:.3f}",
                    )
                )

            # HIGH 级别：ER 极低
            elif er < high_threshold.get("er_below", 0.3):
                alerts.append(
                    create_alert(
                        symbol=symbol,
                        alert_type="TREND_REVERSAL",
                        severity="HIGH",
                        indicators={
                            "er": round(er, 3),
                            "tsi": round(tsi, 2),
                            "trend_strength": round(trend_strength, 3),
                            "current_price": current_price,
                        },
                        trigger_reason=f"ER={er:.3f} 极低，趋势效率丧失",
                    )
                )

            # MEDIUM 级别：趋势强度中等下降
            elif strength_change < -medium_threshold.get("trend_strength_drop", 0.25):
                alerts.append(
                    create_alert(
                        symbol=symbol,
                        alert_type="TREND_WEAKENING",
                        severity="MEDIUM",
                        indicators={
                            "trend_strength": round(trend_strength, 3),
                            "trend_strength_change": round(strength_change, 3),
                            "current_price": current_price,
                        },
                        trigger_reason=f"趋势强度下降 {strength_change:.3f}",
                    )
                )

            # 更新状态
            if "positions" not in prev_state:
                prev_state["positions"] = {}
            prev_state["positions"][symbol] = {
                "trend_strength": trend_strength,
                "er": er,
                "tsi": tsi,
                "current_price": current_price,
                "last_check": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"  检查 {symbol} 失败: {e}", file=sys.stderr)

    return alerts


def check_symbol_changes(
    symbols: list[str], data_source, signal_filter: dict[str, Any], prev_state: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    检查全品种趋势强度变化

    参数:
        symbols: 品种列表
        data_source: 数据源实例
        signal_filter: 信号筛选条件
        prev_state: 上次心跳状态

    返回:
        新出现的信号列表
    """
    new_signals = []

    for symbol in symbols:
        data_symbol = normalize_symbol(symbol)

        try:
            df = data_source.get_kline(data_symbol, days=120, allow_tqsdk_fallback=False)
            if df is None or len(df) < 60:
                continue

            engine = IndicatorEngine(df)
            engine.compute_all()
            composite = engine.get_trend_strength_composite()
            engine.df["trend_strength_composite"] = composite

            latest = engine.df.iloc[-1]
            er = float(latest.get("er", 0))
            tsi = float(latest.get("tsi", 0))
            trend_strength = float(composite.iloc[-1])

            # 获取上次状态
            prev_symbol_state = prev_state.get("symbols", {}).get(symbol, {})
            prev_er = prev_symbol_state.get("er", er)
            prev_tsi = prev_symbol_state.get("tsi", tsi)

            # 检查是否从"无信号"变为"有信号"
            er_min = signal_filter.get("er_min", 0.6)
            tsi_min = signal_filter.get("tsi_min", 20)
            tsi_max = signal_filter.get("tsi_max", -20)

            # 多头信号
            if prev_er < er_min and er >= er_min and tsi >= tsi_min:
                new_signals.append(
                    {
                        "symbol": symbol,
                        "direction": "LONG",
                        "signal_strength": "MEDIUM",
                        "er": round(er, 3),
                        "tsi": round(tsi, 2),
                        "trend_strength": round(trend_strength, 3),
                        "trigger_reason": f"ER 从 {prev_er:.3f} 突破到 {er:.3f}，TSI={tsi:.1f}",
                        "change_type": "NEW_SIGNAL",
                    }
                )

            # 空头信号
            elif prev_er < er_min and er >= er_min and tsi <= tsi_max:
                new_signals.append(
                    {
                        "symbol": symbol,
                        "direction": "SHORT",
                        "signal_strength": "MEDIUM",
                        "er": round(er, 3),
                        "tsi": round(tsi, 2),
                        "trend_strength": round(trend_strength, 3),
                        "trigger_reason": f"ER 从 {prev_er:.3f} 突破到 {er:.3f}，TSI={tsi:.1f}",
                        "change_type": "NEW_SIGNAL",
                    }
                )

            # 更新状态
            if "symbols" not in prev_state:
                prev_state["symbols"] = {}
            prev_state["symbols"][symbol] = {
                "er": er,
                "tsi": tsi,
                "trend_strength": trend_strength,
                "last_check": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"  检查 {symbol} 失败: {e}", file=sys.stderr)

    return new_signals


def heartbeat(positions_only: bool = False, all_symbols: bool = False, check_factors: bool = False) -> dict[str, Any]:
    """
    执行一次心跳检查（混合模式）

    参数:
        positions_only: 是否只监控持仓
        all_symbols: 是否扫描全部品种（非僵尸品种）
        check_factors: 是否检查因子健康度

    返回:
        心跳结果
    """
    # 加载配置
    config = load_config()
    signal_filter = get_signal_filter()

    # 加载状态
    prev_state = load_state()

    # 获取数据源（本地K线）
    data_source = DataSourceFactory.create()

    # 加载持仓
    positions = load_positions()

    # 获取持仓品种的实时行情（快速，~10秒）
    realtime_quotes = {}
    if positions:
        position_symbols = [pos.get("symbol", "") for pos in positions if pos.get("symbol")]
        if position_symbols:
            print(f"  获取 {len(position_symbols)} 个持仓品种实时行情...", flush=True)
            realtime_quotes = get_realtime_quotes(position_symbols)

    # 检查持仓预警（使用混合模式）
    alerts = []
    if positions:
        alerts = check_position_alerts(positions, data_source, prev_state, realtime_quotes)

    # 检查全品种变化（如果不是只监控持仓）
    new_signals = []
    symbols_to_scan = []

    if not positions_only:
        if all_symbols:
            # 扫描全部品种：从 data_source.py 的 MAIN_CONTRACT_MAP 提取
            # K线不足60根的品种会被 check_symbol_changes 自动跳过（僵尸品种自然无数据）
            print("  获取全部主力合约品种...", flush=True)
            symbols_to_scan = get_all_main_contracts()
            print(f"  共 {len(symbols_to_scan)} 个品种（K线不足的将自动跳过）", flush=True)
        else:
            # 使用配置文件中的品种
            symbols_to_scan = config.get("scanner", {}).get("symbols", [])

        if symbols_to_scan:
            new_signals = check_symbol_changes(symbols_to_scan, data_source, signal_filter, prev_state)

    # 检查因子健康度（新增）
    factor_health = None
    if check_factors:
        print("  检查因子健康度...", flush=True)
        factor_health = check_factor_health()

    # 保存状态
    save_state(prev_state)

    # 构建结果
    result = {
        "heartbeat_time": datetime.now().isoformat(),
        "positions_checked": len(positions),
        "symbols_checked": len(symbols_to_scan) if not positions_only else 0,
        "alerts": alerts,
        "new_signals": new_signals,
        "has_events": len(alerts) > 0 or len(new_signals) > 0,
        "realtime_quotes": realtime_quotes,
    }

    # 添加因子健康度结果
    if factor_health:
        result["factor_health"] = factor_health
        if factor_health.get("degraded", 0) > 0 or factor_health.get("critical", 0) > 0:
            result["has_events"] = True

    return result


def main():
    parser = argparse.ArgumentParser(description="心跳监控脚本")
    parser.add_argument("--loop", action="store_true", help="持续循环（每 5 分钟）")
    parser.add_argument("--interval", type=int, default=300, help="心跳间隔（秒，默认 300）")
    parser.add_argument("--positions-only", action="store_true", help="只监控持仓")
    parser.add_argument("--config-only", action="store_true", help="仅扫描配置文件中的品种（默认扫描全部86个主力合约）")
    parser.add_argument("--factor-health", action="store_true", help="检查因子健康度")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")
    parser.add_argument("--save", action="store_true", help="保存结果到 data/latest_heartbeat.json")

    args = parser.parse_args()

    if args.loop:
        print(f"心跳监控启动（间隔 {args.interval} 秒）...")
        print("按 Ctrl+C 停止")
        print("-" * 60)

        while True:
            try:
                result = heartbeat(
                    positions_only=args.positions_only,
                    all_symbols=not args.config_only,
                    check_factors=args.factor_health,
                )

                if result["has_events"]:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 检测到事件:")

                    for alert in result["alerts"]:
                        print(f"  ⚠️ [{alert['severity']}] {alert['symbol']}: {alert['trigger_reason']}")

                    for signal in result["new_signals"]:
                        print(f"  📊 [{signal['direction']}] {signal['symbol']}: {signal['trigger_reason']}")

                    # 因子健康度事件
                    factor_health = result.get("factor_health", {})
                    if factor_health.get("degraded", 0) > 0:
                        for f in factor_health.get("degraded_factors", []):
                            print(f"  🔴 [FACTOR_DEGRADED] {f['factor_name']}: {'; '.join(f['issues'][:2])}")

                    # 保存事件
                    if args.save:
                        output_path = os.path.join(DATA_DIR, "latest_heartbeat.json")
                        with open(output_path, "w", encoding="utf-8") as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 无事件", end="\r")

                time.sleep(args.interval)

            except KeyboardInterrupt:
                print("\n心跳监控停止")
                break
            except Exception as e:
                print(f"\n心跳异常: {e}", file=sys.stderr)
                time.sleep(args.interval)

    else:
        # 单次心跳
        result = heartbeat(
            positions_only=args.positions_only,
            all_symbols=not args.config_only,
            check_factors=args.factor_health,
        )

        if args.output == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"心跳检查完成: {datetime.now().strftime('%H:%M:%S')}")
            print(f"  持仓品种: {result['positions_checked']} 个")
            print(f"  扫描品种: {result['symbols_checked']} 个")

            # 显示因子健康度
            factor_health = result.get("factor_health")
            if factor_health:
                print(f"  因子健康: {factor_health.get('healthy', 0)} 个")
                print(f"  因子警告: {factor_health.get('warning', 0)} 个")
                print(f"  因子退化: {factor_health.get('degraded', 0)} 个")
            print(f"  预警: {len(result['alerts'])} 个")
            print(f"  新信号: {len(result['new_signals'])} 个")

            if result["alerts"]:
                print("\n预警:")
                for alert in result["alerts"]:
                    print(f"  [{alert['severity']}] {alert['symbol']}: {alert['trigger_reason']}")

            if result["new_signals"]:
                print("\n新信号:")
                for signal in result["new_signals"]:
                    print(f"  [{signal['direction']}] {signal['symbol']}: {signal['trigger_reason']}")

        if args.save:
            output_path = os.path.join(DATA_DIR, "latest_heartbeat.json")
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print("\n结果已保存到 data/latest_heartbeat.json")


if __name__ == "__main__":
    main()
