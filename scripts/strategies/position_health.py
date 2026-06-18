"""
持仓健康度评估模块

评估单个持仓品种的健康状态：
- 技术面评估（趋势强度、动量、波动率）
- 资金面评估（盈亏、回撤、持仓时间）
- 市场面评估（宏观状态、相关性）
- LLM推理评估（Reasoner Agent）

设计原则：
- 推理重于规则：使用LLM进行综合评估
- 多维度评估：技术面+资金面+市场面
- 动态权重：根据市场状态调整权重
- 可回测验证：所有指标可量化

文件：scripts/trend_scanner/position_health.py
"""

import json
import logging
import os
from datetime import datetime
from typing import Any

import pandas as pd


logger = logging.getLogger(__name__)


class PositionHealthChecker:
    """
    持仓健康度检查器

    多维度评估持仓健康状态，提供操作建议。
    """

    # 权重配置
    WEIGHTS = {
        "technical": 0.40,  # 技术面
        "capital": 0.30,  # 资金面
        "market": 0.20,  # 市场面
        "reasoning": 0.10,  # LLM推理
    }

    def __init__(self, config: dict[str, Any] = None):
        """
        初始化持仓健康度检查器

        Args:
            config: 配置字典
        """
        self.config = config or {}

        # 延迟初始化组件
        self._duckdb = None
        self._sqlite = None
        self._reasoner = None
        self._macro_detector = None

    @property
    def duckdb(self):
        """延迟初始化DuckDB"""
        if self._duckdb is None:
            from .storage.duckdb_store import DuckDBStore

            db_path = self.config.get("duckdb_path", "data/market.db")
            self._duckdb = DuckDBStore(db_path=db_path)
        return self._duckdb

    @property
    def sqlite(self):
        """延迟初始化SQLite"""
        if self._sqlite is None:
            from .storage.sqlite_store import SQLiteStore

            db_path = self.config.get("sqlite_path", "data/meta.db")
            self._sqlite = SQLiteStore(db_path=db_path)
        return self._sqlite

    @property
    def reasoner(self):
        """延迟初始化Reasoner"""
        if self._reasoner is None:
            import sys

            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
            from reasoner import ReasonerAgent

            self._reasoner = ReasonerAgent()
        return self._reasoner

    @property
    def macro_detector(self):
        """延迟初始化宏观状态检测器"""
        if self._macro_detector is None:
            from .macro_state import MacroStateDetector

            self._macro_detector = MacroStateDetector()
        return self._macro_detector

    def check(self, position: dict[str, Any], kline_days: int = 120) -> dict[str, Any]:
        """
        检查单个持仓的健康度

        Args:
            position: 持仓信息，包含：
                - symbol: 品种代码（如 'JM'）
                - direction: 方向（'LONG' 或 'SHORT'）
                - entry_price: 入场价格（可选）
                - entry_date: 入场日期（可选）
                - position_size: 仓位比例（可选）
            kline_days: K线天数

        Returns:
            健康度评估结果
        """
        symbol = position.get("symbol", "")
        direction = position.get("direction", "LONG")

        try:
            # 1. 获取K线数据
            df = self._get_kline_data(symbol, kline_days)
            if df is None or df.empty:
                return self._error_result(symbol, direction, "无法获取K线数据")

            # 2. 计算技术指标
            df = self._compute_indicators(df)

            # 3. 技术面评估
            technical_result = self._evaluate_technical(df, direction)

            # 4. 资金面评估
            capital_result = self._evaluate_capital(df, position)

            # 5. 市场面评估
            market_result = self._evaluate_market(symbol, direction)

            # 6. LLM推理评估
            reasoning_result = self._evaluate_reasoning(
                symbol, direction, df, technical_result, capital_result, market_result
            )

            # 7. 计算综合评分
            health_score = self._calculate_health_score(
                technical_result, capital_result, market_result, reasoning_result
            )

            # 8. 确定健康等级
            health_grade = self._get_health_grade(health_score)

            # 9. 生成操作建议
            recommendation = self._generate_recommendation(health_score, health_grade, technical_result, capital_result)

            # 10. 识别风险因素
            risk_factors = self._identify_risk_factors(technical_result, capital_result, market_result)

            return {
                "symbol": symbol,
                "direction": direction,
                "health_score": round(health_score, 1),
                "health_grade": health_grade,
                "details": {
                    "technical": technical_result,
                    "capital": capital_result,
                    "market": market_result,
                    "reasoning": reasoning_result,
                },
                "recommendation": recommendation,
                "risk_factors": risk_factors,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"检查持仓 {symbol} 健康度失败: {e}")
            return self._error_result(symbol, direction, str(e))

    def check_batch(self, positions: list[dict[str, Any]], kline_days: int = 120) -> list[dict[str, Any]]:
        """
        批量检查持仓健康度

        Args:
            positions: 持仓列表
            kline_days: K线天数

        Returns:
            健康度评估结果列表
        """
        results = []
        for pos in positions:
            result = self.check(pos, kline_days)
            results.append(result)
        return results

    def _get_kline_data(self, symbol: str, days: int) -> pd.DataFrame | None:
        """获取K线数据"""
        try:
            df = self.duckdb.get_klines(symbol, days)
            return df
        except Exception as e:
            logger.error(f"获取 {symbol} K线数据失败: {e}")
            return None

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        try:
            from .indicators import IndicatorEngine

            engine = IndicatorEngine(df)
            df = engine.compute_all()

            # 计算复合趋势强度
            composite = engine.get_trend_strength_composite()
            df["trend_strength_composite"] = composite

            return df
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return df

    def _evaluate_technical(self, df: pd.DataFrame, direction: str) -> dict[str, Any]:
        """技术面评估"""
        if df.empty:
            return {"score": 50, "error": "无数据"}

        latest = df.iloc[-1]
        score = 100
        issues = []

        # 趋势强度
        trend_strength = latest.get("trend_strength_composite", 0)
        er = latest.get("er", 0)
        r_squared = latest.get("r_squared", 0)
        adx = latest.get("adx", 0)

        # 动量状态
        rsi = latest.get("rsi", 50)
        tsi = latest.get("tsi", 0)
        macd_hist = latest.get("macd_hist", 0)

        # 波动率
        atr = latest.get("atr", 0)
        current_price = latest.get("close", 1)
        volatility_pct = (atr / current_price * 100) if current_price > 0 else 0

        # 趋势强度评估
        if direction == "LONG":
            if tsi < 0:
                score -= 15
                issues.append(f"TSI为负({tsi:.1f})，下跌动量")
            if rsi > 70:
                score -= 15
                issues.append(f"RSI超买({rsi:.1f})")
            elif rsi > 65:
                score -= 5
                issues.append(f"RSI偏高({rsi:.1f})")
        else:  # SHORT
            if tsi > 0:
                score -= 15
                issues.append(f"TSI为正({tsi:.1f})，上涨动量")
            if rsi < 30:
                score -= 15
                issues.append(f"RSI超卖({rsi:.1f})")
            elif rsi < 35:
                score -= 5
                issues.append(f"RSI偏低({rsi:.1f})")

        # 趋势强度评估
        if trend_strength < 0.3:
            score -= 15
            issues.append(f"趋势强度弱({trend_strength:.3f})")
        elif trend_strength < 0.4:
            score -= 5
            issues.append(f"趋势强度中等({trend_strength:.3f})")

        # R²评估
        if r_squared < 0.4:
            score -= 10
            issues.append(f"趋势不清晰(R²={r_squared:.2f})")

        # 波动率评估
        if volatility_pct > 3:
            score -= 10
            issues.append(f"波动率高({volatility_pct:.1f}%)")

        score = max(0, min(100, score))

        return {
            "score": score,
            "trend_strength": round(trend_strength, 3),
            "er": round(er, 3),
            "r_squared": round(r_squared, 3),
            "adx": round(adx, 1),
            "rsi": round(rsi, 1),
            "tsi": round(tsi, 1),
            "macd_hist": round(macd_hist, 2),
            "volatility_pct": round(volatility_pct, 2),
            "issues": issues,
        }

    def _evaluate_capital(self, df: pd.DataFrame, position: dict[str, Any]) -> dict[str, Any]:
        """资金面评估"""
        if df.empty:
            return {"score": 50, "error": "无数据"}

        score = 100
        issues = []

        # 获取当前价格
        current_price = df.iloc[-1]["close"]

        # 获取入场价格（如果有）
        entry_price = position.get("entry_price")
        if entry_price is None:
            # 使用60日均价作为参考
            entry_price = df["close"].tail(60).mean()

        # 计算盈亏
        direction = position.get("direction", "LONG")
        if direction == "LONG":
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100

        # 计算回撤（从60日高点）
        highest_60d = df["high"].tail(60).max()
        if direction == "LONG":
            drawdown_pct = (current_price - highest_60d) / highest_60d * 100
        else:
            lowest_60d = df["low"].tail(60).min()
            drawdown_pct = (lowest_60d - current_price) / current_price * 100

        # 持仓时间
        entry_date = position.get("entry_date")
        if entry_date:
            if isinstance(entry_date, str):
                entry_date = datetime.fromisoformat(entry_date)
            holding_days = (datetime.now() - entry_date).days
        else:
            holding_days = 0

        # 仓位比例
        position_size = position.get("position_size", 0)

        # 盈亏评估
        if pnl_pct < -10:
            score -= 25
            issues.append(f"大幅亏损({pnl_pct:.1f}%)")
        elif pnl_pct < -5:
            score -= 15
            issues.append(f"中等亏损({pnl_pct:.1f}%)")
        elif pnl_pct < 0:
            score -= 5
            issues.append(f"小幅亏损({pnl_pct:.1f}%)")

        # 回撤评估
        if drawdown_pct < -15:
            score -= 20
            issues.append(f"大幅回撤({drawdown_pct:.1f}%)")
        elif drawdown_pct < -10:
            score -= 10
            issues.append(f"中等回撤({drawdown_pct:.1f}%)")

        # 仓位评估
        if position_size > 0.5:
            score -= 10
            issues.append(f"仓位过重({position_size:.0%})")

        score = max(0, min(100, score))

        return {
            "score": score,
            "current_price": round(current_price, 2),
            "entry_price": round(entry_price, 2),
            "pnl_pct": round(pnl_pct, 2),
            "drawdown_pct": round(drawdown_pct, 2),
            "holding_days": holding_days,
            "position_size": position_size,
            "highest_60d": round(highest_60d, 2),
            "issues": issues,
        }

    def _evaluate_market(self, symbol: str, direction: str) -> dict[str, Any]:
        """市场面评估"""
        score = 100
        issues = []

        try:
            # 获取宏观状态
            macro_state = self.macro_detector.detect()
            cycle = macro_state.get("cycle", {}).get("state", "unknown")
            strategy_weights = macro_state.get("strategy_weights", {})

            # 根据宏观状态评估
            if cycle == "recession":
                if direction == "LONG":
                    score -= 10
                    issues.append("衰退期，多头承压")
            elif cycle == "expansion":
                if direction == "SHORT":
                    score -= 10
                    issues.append("扩张期，空头承压")

            # 趋势策略权重
            trend_weight = strategy_weights.get("trend_following", 0.5)
            if trend_weight < 0.4:
                score -= 5
                issues.append("趋势策略权重低")

            return {
                "score": score,
                "macro_state": cycle,
                "strategy_weights": strategy_weights,
                "issues": issues,
            }

        except Exception as e:
            logger.warning(f"获取市场状态失败: {e}")
            return {
                "score": 70,
                "macro_state": "unknown",
                "error": str(e),
                "issues": ["无法获取市场状态"],
            }

    def _evaluate_reasoning(
        self, symbol: str, direction: str, df: pd.DataFrame, technical: dict, capital: dict, market: dict
    ) -> dict[str, Any]:
        """LLM推理评估"""
        try:
            # 构造信号数据
            latest = df.iloc[-1] if not df.empty else {}

            signal_data = {
                "symbol": symbol,
                "direction": direction,
                "trend_phase": "UNKNOWN",
                "trend_strength_composite": technical.get("trend_strength", 0),
                "tsi": technical.get("tsi", 0),
                "er": technical.get("er", 0),
                "r_squared": technical.get("r_squared", 0),
                "key_signals": technical.get("issues", []),
                "risk_factors": capital.get("issues", []) + market.get("issues", []),
                "scan_id": f"health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            }

            # 调用Reasoner
            brief = self.reasoner.analyze(signal_data)

            # 提取关键信息
            recommended_route = brief.get("recommended_route", "")
            routes = brief.get("routes", [])
            confidence = 0
            summary = ""

            for route in routes:
                if route.get("route_id") == recommended_route:
                    confidence = route.get("confidence", 0)
                    summary = route.get("reasoning", "")
                    break

            return {
                "score": int(confidence * 100),
                "confidence": confidence,
                "summary": summary[:200],
                "routes_count": len(routes),
                "warnings": brief.get("warnings", []),
            }

        except Exception as e:
            logger.warning(f"Reasoner评估失败: {e}")
            return {
                "score": 60,
                "confidence": 0.6,
                "summary": f"Reasoner评估失败: {str(e)[:100]}",
                "error": str(e),
            }

    def _calculate_health_score(self, technical: dict, capital: dict, market: dict, reasoning: dict) -> float:
        """计算综合健康度评分"""
        scores = {
            "technical": technical.get("score", 50),
            "capital": capital.get("score", 50),
            "market": market.get("score", 50),
            "reasoning": reasoning.get("score", 50),
        }

        # 加权计算
        total_score = 0
        for dim, weight in self.WEIGHTS.items():
            total_score += scores[dim] * weight

        return total_score

    def _get_health_grade(self, score: float) -> str:
        """确定健康等级"""
        if score >= 85:
            return "健康"
        elif score >= 70:
            return "良好"
        elif score >= 55:
            return "一般"
        elif score >= 40:
            return "警告"
        else:
            return "危险"

    def _generate_recommendation(self, score: float, grade: str, technical: dict, capital: dict) -> str:
        """生成操作建议"""
        rsi = technical.get("rsi", 50)
        direction = "LONG" if rsi > 50 else "SHORT"  # 简化判断
        pnl_pct = capital.get("pnl_pct", 0)

        if grade == "健康":
            return "持仓健康，可继续持有"
        elif grade == "良好":
            return "持仓良好，关注风险"
        elif grade == "一般":
            if pnl_pct < 0:
                return "持仓一般，亏损中，考虑减仓"
            else:
                return "持仓一般，设置止损"
        elif grade == "警告":
            return "持仓警告，建议减仓50%"
        else:
            return "持仓危险，建议止损离场"

    def _identify_risk_factors(self, technical: dict, capital: dict, market: dict) -> list[str]:
        """识别风险因素"""
        risk_factors = []

        # 技术面风险
        if technical.get("rsi", 50) > 70:
            risk_factors.append("RSI超买")
        elif technical.get("rsi", 50) < 30:
            risk_factors.append("RSI超卖")

        if technical.get("volatility_pct", 0) > 3:
            risk_factors.append("波动率偏高")

        # 资金面风险
        if capital.get("pnl_pct", 0) < -10:
            risk_factors.append("大幅亏损")

        if capital.get("drawdown_pct", 0) < -15:
            risk_factors.append("大幅回撤")

        # 市场面风险
        for issue in market.get("issues", []):
            risk_factors.append(issue)

        return risk_factors

    def _error_result(self, symbol: str, direction: str, error: str) -> dict[str, Any]:
        """返回错误结果"""
        return {
            "symbol": symbol,
            "direction": direction,
            "health_score": 50,
            "health_grade": "未知",
            "details": {},
            "recommendation": f"评估失败: {error}",
            "risk_factors": ["数据不足"],
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }


def load_positions_from_file(filepath: str = "config/positions.json") -> list[dict[str, Any]]:
    """从文件加载持仓信息"""
    try:
        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"加载持仓文件失败: {e}")
        return []


def save_positions_to_file(positions: list[dict[str, Any]], filepath: str = "config/positions.json"):
    """保存持仓信息到文件"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存持仓文件失败: {e}")
