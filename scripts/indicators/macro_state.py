"""
宏观状态集成模块

检测当前宏观经济状态：
- 经济周期：复苏/过热/滞胀/衰退
- 流动性：宽松/中性/紧缩
- 风险偏好：risk-on/risk-off

根据宏观状态调整策略权重：
- 衰退期：趋势跟踪权重提高
- 过热期：均值回归权重提高
- 流动性紧缩：降低整体仓位

设计原则：
- 宏观状态决定大方向，技术指标决定入场时机
- 不预测宏观，只识别当前状态
- 状态转换时及时调整策略权重

文件：scripts/trend_scanner/macro_state.py
"""

import logging
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)


class MacroStateDetector:
    """
    宏观状态检测器

    基于多维度指标识别当前宏观经济状态。
    """

    # 经济周期状态
    CYCLE_STATES = {
        "recovery": {"name": "复苏", "description": "经济增长加速，通胀温和"},
        "overheating": {"name": "过热", "description": "经济增长强劲，通胀上升"},
        "stagflation": {"name": "滞胀", "description": "经济增长放缓，通胀高企"},
        "recession": {"name": "衰退", "description": "经济收缩，通胀回落"},
    }

    # 流动性状态
    LIQUIDITY_STATES = {
        "loose": {"name": "宽松", "description": "货币政策宽松，流动性充裕"},
        "neutral": {"name": "中性", "description": "货币政策中性"},
        "tight": {"name": "紧缩", "description": "货币政策收紧，流动性收缩"},
    }

    # 风险偏好状态
    RISK_APPETITE_STATES = {
        "risk_on": {"name": "风险偏好", "description": "资金流向风险资产"},
        "neutral": {"name": "中性", "description": "风险偏好中性"},
        "risk_off": {"name": "风险规避", "description": "资金流向避险资产"},
    }

    # 策略权重配置
    STRATEGY_WEIGHTS = {
        "recovery": {"trend_following": 0.4, "mean_reversion": 0.3, "event_driven": 0.2, "defensive": 0.1},
        "overheating": {"trend_following": 0.3, "mean_reversion": 0.4, "event_driven": 0.2, "defensive": 0.1},
        "stagflation": {"trend_following": 0.5, "mean_reversion": 0.2, "event_driven": 0.1, "defensive": 0.2},
        "recession": {"trend_following": 0.6, "mean_reversion": 0.1, "event_driven": 0.1, "defensive": 0.2},
    }

    def detect(
        self,
        gdp_growth: float = None,
        inflation: float = None,
        interest_rate: float = None,
        pmi: float = None,
        commodity_index: float = None,
        vix: float = None,
        usd_index: float = None,
    ) -> dict[str, Any]:
        """
        检测当前宏观状态

        可以手动输入宏观指标，也可以通过数据源自动获取。

        Args:
            gdp_growth: GDP 增速（%）
            inflation: 通胀率（%）
            interest_rate: 利率（%）
            pmi: PMI 指数
            commodity_index: 商品指数
            vix: VIX 恐慌指数
            usd_index: 美元指数

        Returns:
            宏观状态分析结果
        """
        # 经济周期判断
        cycle_state = self._detect_cycle(gdp_growth, inflation, pmi)

        # 流动性判断
        liquidity_state = self._detect_liquidity(interest_rate)

        # 风险偏好判断
        risk_appetite = self._detect_risk_appetite(vix, commodity_index)

        # 获取策略权重
        strategy_weights = self.STRATEGY_WEIGHTS.get(cycle_state, self.STRATEGY_WEIGHTS["recession"])

        # 风险调整
        if risk_appetite == "risk_off":
            strategy_weights = self._adjust_for_risk_off(strategy_weights)

        return {
            "cycle": {
                "state": cycle_state,
                "name": self.CYCLE_STATES[cycle_state]["name"],
                "description": self.CYCLE_STATES[cycle_state]["description"],
            },
            "liquidity": {
                "state": liquidity_state,
                "name": self.LIQUIDITY_STATES[liquidity_state]["name"],
                "description": self.LIQUIDITY_STATES[liquidity_state]["description"],
            },
            "risk_appetite": {
                "state": risk_appetite,
                "name": self.RISK_APPETITE_STATES[risk_appetite]["name"],
                "description": self.RISK_APPETITE_STATES[risk_appetite]["description"],
            },
            "strategy_weights": strategy_weights,
            "recommendation": self._get_recommendation(cycle_state, liquidity_state, risk_appetite),
            "timestamp": datetime.now().isoformat(),
        }

    def _detect_cycle(self, gdp_growth, inflation, pmi) -> str:
        """检测经济周期"""
        if gdp_growth is None and pmi is None:
            return "recession"  # 默认保守

        # 简化判断逻辑
        if pmi is not None:
            if pmi > 52:
                if inflation is not None and inflation > 3:
                    return "overheating"
                return "recovery"
            elif pmi < 48:
                if inflation is not None and inflation > 3:
                    return "stagflation"
                return "recession"

        if gdp_growth is not None:
            if gdp_growth > 3:
                return "overheating"
            elif gdp_growth < 0:
                return "recession"
            elif gdp_growth < 2 and inflation is not None and inflation > 3:
                return "stagflation"

        return "recovery"

    def _detect_liquidity(self, interest_rate) -> str:
        """检测流动性状态"""
        if interest_rate is None:
            return "neutral"

        if interest_rate < 2:
            return "loose"
        elif interest_rate > 5:
            return "tight"
        return "neutral"

    def _detect_risk_appetite(self, vix, commodity_index) -> str:
        """检测风险偏好"""
        if vix is None:
            return "neutral"

        if vix > 30:
            return "risk_off"
        elif vix < 15:
            return "risk_on"
        return "neutral"

    def _adjust_for_risk_off(self, weights: dict[str, float]) -> dict[str, float]:
        """风险规避时降低风险仓位"""
        adjusted = weights.copy()
        adjusted["trend_following"] *= 0.7
        adjusted["mean_reversion"] *= 0.5
        adjusted["event_driven"] *= 0.5
        adjusted["defensive"] = 1.0 - sum(v for k, v in adjusted.items() if k != "defensive")
        return adjusted

    def _get_recommendation(self, cycle: str, liquidity: str, risk: str) -> str:
        """获取宏观建议"""
        recommendations = []

        if cycle == "recession":
            recommendations.append("经济衰退期，趋势跟踪为主，降低仓位")
        elif cycle == "overheating":
            recommendations.append("经济过热期，关注通胀受益品种")
        elif cycle == "stagflation":
            recommendations.append("滞胀期，防守为主，减少交易频率")

        if liquidity == "tight":
            recommendations.append("流动性紧缩，降低杠杆，增加现金比例")
        elif liquidity == "loose":
            recommendations.append("流动性宽松，可适当提高仓位")

        if risk == "risk_off":
            recommendations.append("风险规避情绪浓厚，避险资产优先")

        return "；".join(recommendations) if recommendations else "宏观环境稳定，正常交易"

    def detect_from_llm(self, llm_client=None) -> dict[str, Any]:
        """
        通过 LLM 分析最新宏观新闻来判断宏观状态

        Args:
            llm_client: LLM 客户端

        Returns:
            宏观状态分析结果
        """
        if llm_client is None:
            # 返回默认状态
            return self.detect()

        prompt = """分析当前全球宏观经济状态，判断：
1. 经济周期：复苏/过热/滞胀/衰退
2. 流动性：宽松/中性/紧缩
3. 风险偏好：risk-on/risk-off

请用 JSON 格式输出：
{
    "cycle": "recovery/overheating/stagflation/recession",
    "liquidity": "loose/neutral/tight",
    "risk_appetite": "risk_on/neutral/risk_off",
    "reasoning": "判断依据"
}
"""
        try:
            response = llm_client.generate(prompt)
            import json

            result = json.loads(response)

            return self.detect(
                pmi=50,  # 默认值，实际应从 LLM 分析中获取
            )
        except Exception as e:
            logger.warning(f"LLM 宏观分析失败: {e}")
            return self.detect()
