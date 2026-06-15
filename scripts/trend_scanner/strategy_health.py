"""
策略健康度评估模块

评估策略的健康状态：
- 夏普比率：风险调整后收益
- 最大回撤：最坏情况的损失
- 胜率趋势：胜率是否在恶化
- 连续亏损：连续亏损次数
- 综合评分：0-100 分

设计原则：
- 策略会失效，关键是要及时发现
- 多维度评估，避免单一指标误导
- 评分要直观，决策要明确

文件：scripts/trend_scanner/strategy_health.py
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class StrategyHealthChecker:
    """
    策略健康度检查器
    
    多维度评估策略健康状态，及时发现策略失效。
    """
    
    def __init__(
        self,
        sharpe_threshold: float = 0.5,
        drawdown_threshold: float = 15.0,
        win_rate_decline_threshold: float = 0.1
    ):
        """
        初始化健康度检查器
        
        Args:
            sharpe_threshold: 夏普比率阈值（低于此值扣分）
            drawdown_threshold: 最大回撤阈值（超过此值扣分）
            win_rate_decline_threshold: 胜率下降阈值（超过此值扣分）
        """
        self.sharpe_threshold = sharpe_threshold
        self.drawdown_threshold = drawdown_threshold
        self.win_rate_decline_threshold = win_rate_decline_threshold
    
    def check(self, trades: List[Dict[str, Any]], lookback: int = 50) -> Dict[str, Any]:
        """
        检查策略健康度
        
        Args:
            trades: 交易记录列表，每条包含 pnl_pct 字段
            lookback: 回看交易数量
            
        Returns:
            健康度评估结果
        """
        if not trades or len(trades) < 5:
            return {
                'health_score': 50,
                'status': '数据不足',
                'details': {},
                'recommendation': '交易数据不足，无法评估'
            }
        
        recent_trades = trades[-lookback:]
        returns = [t.get('pnl_pct', 0) for t in recent_trades]
        
        # 计算各维度指标
        sharpe = self._calculate_sharpe(returns)
        max_drawdown = self._calculate_max_drawdown(returns)
        win_rate_trend = self._calculate_win_rate_trend(returns)
        consecutive_losses = self._count_consecutive_losses(returns)
        profit_factor = self._calculate_profit_factor(returns)
        
        # 计算综合评分
        health_score = 100
        deductions = []
        
        # 夏普比率
        if sharpe < self.sharpe_threshold:
            deduction = min(30, (self.sharpe_threshold - sharpe) * 30)
            health_score -= deduction
            deductions.append(f"夏普比率偏低 ({sharpe:.2f}): -{deduction:.0f}")
        
        # 最大回撤
        if max_drawdown > self.drawdown_threshold:
            deduction = min(30, (max_drawdown - self.drawdown_threshold) * 2)
            health_score -= deduction
            deductions.append(f"最大回撤过大 ({max_drawdown:.1f}%): -{deduction:.0f}")
        
        # 胜率趋势
        if win_rate_trend < -self.win_rate_decline_threshold:
            deduction = min(20, abs(win_rate_trend) * 100)
            health_score -= deduction
            deductions.append(f"胜率下降 ({win_rate_trend:.1%}): -{deduction:.0f}")
        
        # 连续亏损
        if consecutive_losses >= 5:
            deduction = min(20, consecutive_losses * 3)
            health_score -= deduction
            deductions.append(f"连续亏损 {consecutive_losses} 次: -{deduction:.0f}")
        
        # 盈亏比
        if profit_factor < 1.0:
            deduction = min(15, (1.0 - profit_factor) * 15)
            health_score -= deduction
            deductions.append(f"盈亏比不足 ({profit_factor:.2f}): -{deduction:.0f}")
        
        health_score = max(0, min(100, health_score))
        
        return {
            'health_score': round(health_score, 1),
            'status': self._get_status(health_score),
            'details': {
                'sharpe_ratio': round(sharpe, 2),
                'max_drawdown_pct': round(max_drawdown, 1),
                'win_rate_trend': round(win_rate_trend, 3),
                'consecutive_losses': consecutive_losses,
                'profit_factor': round(profit_factor, 2),
                'total_trades': len(recent_trades),
                'win_rate': round(sum(1 for r in returns if r > 0) / len(returns), 2)
            },
            'deductions': deductions,
            'recommendation': self._get_recommendation(health_score)
        }
    
    def _calculate_sharpe(self, returns: List[float]) -> float:
        """计算夏普比率"""
        if not returns:
            return 0.0
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        if std_return == 0:
            return 0.0
        return mean_return / std_return
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """计算最大回撤（百分比）"""
        if not returns:
            return 0.0
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        return float(np.max(drawdown))
    
    def _calculate_win_rate_trend(self, returns: List[float]) -> float:
        """计算胜率趋势（最近 20 笔 vs 之前）"""
        if len(returns) < 40:
            return 0.0
        
        recent = returns[-20:]
        older = returns[:-20]
        
        recent_win_rate = sum(1 for r in recent if r > 0) / len(recent)
        older_win_rate = sum(1 for r in older if r > 0) / len(older)
        
        return recent_win_rate - older_win_rate
    
    def _count_consecutive_losses(self, returns: List[float]) -> int:
        """统计当前连续亏损次数"""
        count = 0
        for r in reversed(returns):
            if r < 0:
                count += 1
            else:
                break
        return count
    
    def _calculate_profit_factor(self, returns: List[float]) -> float:
        """计算盈亏比（总盈利/总亏损）"""
        total_profit = sum(r for r in returns if r > 0)
        total_loss = abs(sum(r for r in returns if r < 0))
        
        if total_loss == 0:
            return float('inf') if total_profit > 0 else 0.0
        
        return total_profit / total_loss
    
    def _get_status(self, score: float) -> str:
        """获取健康状态"""
        if score >= 80:
            return "健康"
        elif score >= 60:
            return "亚健康"
        elif score >= 40:
            return "不健康"
        else:
            return "严重失效"
    
    def _get_recommendation(self, score: float) -> str:
        """获取建议"""
        if score >= 80:
            return "策略健康，继续运行"
        elif score >= 60:
            return "策略亚健康，建议降低仓位至 60%，密切观察"
        elif score >= 40:
            return "策略不健康，建议暂停开新仓，只持有现有仓位"
        else:
            return "策略严重失效，建议清仓并复盘，考虑退休该策略"
    
    def should_retire(self, trades: List[Dict[str, Any]], lookback: int = 100) -> Dict[str, Any]:
        """
        判断策略是否应该退休
        
        条件：
        - 夏普比率连续 6 个月 < 0.5
        - 最大回撤超过 25%
        - 健康评分低于 40
        
        Args:
            trades: 交易记录
            lookback: 回看数量
            
        Returns:
            退休建议
        """
        result = self.check(trades, lookback)
        
        reasons = []
        if result['details']['sharpe_ratio'] < 0.5:
            reasons.append(f"夏普比率过低 ({result['details']['sharpe_ratio']:.2f})")
        if result['details']['max_drawdown_pct'] > 25:
            reasons.append(f"最大回撤过大 ({result['details']['max_drawdown_pct']:.1f}%)")
        if result['health_score'] < 40:
            reasons.append(f"健康评分过低 ({result['health_score']:.1f})")
        
        should_retire = len(reasons) >= 2
        
        return {
            'should_retire': should_retire,
            'reasons': reasons,
            'health_score': result['health_score'],
            'recommendation': '建议退休该策略' if should_retire else '继续观察'
        }
