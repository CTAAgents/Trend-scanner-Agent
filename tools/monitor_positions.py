#!/usr/bin/env python3
"""
持仓监控脚本（Phase 5）

纯 Python 脚本，无 LLM 调用。监控持仓品种的风险状态，输出预警信息。

职责：
- 读取 positions.json 获取当前持仓
- 监控持仓品种的价格和指标变化
- 检测止损/止盈触发条件
- 检测趋势反转信号（TSI 背离、ER 下降等）
- 输出 JSON 格式的预警列表

用法：
    python tools/monitor_positions.py [--config config.json] [--positions positions.json]
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from trend_scanner.data_source import DataSourceFactory
from trend_scanner.indicators import IndicatorEngine
from trend_scanner.models import IndicatorSnapshot


class PositionMonitor:
    """持仓监控器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化监控器
        
        Args:
            config: 配置字典，包含 monitor 相关配置
        """
        self.config = config
        self.monitor_config = config.get('monitor', {})
        
        # 预警阈值
        self.alert_thresholds = self.monitor_config.get('alert_thresholds', {
            'LOW': {'trend_strength_drop': 0.15},
            'MEDIUM': {'trend_strength_drop': 0.25, 'tsi_divergence': True},
            'HIGH': {'trend_strength_drop': 0.35, 'er_below': 0.3}
        })
        
        # 数据源
        self.data_source = None
    
    def _init_data_source(self):
        """初始化数据源"""
        if self.data_source is None:
            self.data_source = DataSourceFactory.create()
        return self.data_source
    
    def load_positions(self, positions_file: str) -> List[Dict[str, Any]]:
        """
        加载持仓数据
        
        Args:
            positions_file: positions.json 文件路径
            
        Returns:
            持仓列表
        """
        try:
            with open(positions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('positions', [])
        except FileNotFoundError:
            print(f"[警告] 持仓文件不存在: {positions_file}")
            return []
        except json.JSONDecodeError as e:
            print(f"[错误] 持仓文件格式错误: {e}")
            return []
    
    def get_position_indicators(self, symbol: str, days: int = 60) -> Optional[Dict[str, Any]]:
        """
        获取持仓品种的指标数据
        
        Args:
            symbol: 品种代码（如 "DCE.jm2609"）
            days: 获取天数
            
        Returns:
            指标字典，包含最新指标和历史指标
        """
        try:
            ds = self._init_data_source()
            if ds is None:
                print(f"[错误] 数据源初始化失败")
                return None
            
            # 获取K线数据
            # 从 symbol 中提取品种代码（如 "DCE.jm2609" -> "jm"）
            parts = symbol.split('.')
            if len(parts) >= 2:
                # 提取品种代码（去掉合约月份）
                contract = parts[1]
                # 去掉数字部分，只保留品种代码
                variety = ''.join([c for c in contract if not c.isdigit()])
            else:
                variety = symbol
            
            df = ds.get_kline(variety, days=days)
            if df is None or len(df) < 20:
                print(f"[警告] {symbol} 数据不足")
                return None
            
            # 计算指标
            engine = IndicatorEngine(df)
            engine.add_ema(20)
            engine.add_ema(60)
            engine.add_atr(14)
            engine.add_adx(14)
            engine.add_rsi(14)
            engine.add_macd()
            engine.add_tsi()
            engine.add_efficiency_ratio()
            engine.add_r_squared(20)
            
            # 获取最新指标
            latest = engine.df.iloc[-1]
            prev = engine.df.iloc[-2] if len(engine.df) > 1 else latest
            
            # 构建指标字典
            indicators = {
                'symbol': symbol,
                'timestamp': str(latest.get('date', datetime.now().isoformat())),
                'close': float(latest.get('close', 0)),
                'high': float(latest.get('high', 0)),
                'low': float(latest.get('low', 0)),
                'open': float(latest.get('open', 0)),
                'volume': float(latest.get('volume', 0)),
                'open_interest': float(latest.get('open_interest', 0)),
                
                # 均线
                'ema20': float(latest.get('ema20', 0)),
                'ema60': float(latest.get('ema60', 0)),
                
                # 动量指标
                'rsi': float(latest.get('rsi', 50)),
                'macd': float(latest.get('macd', 0)),
                'macd_signal': float(latest.get('macd_signal', 0)),
                'macd_hist': float(latest.get('macd_hist', 0)),
                'tsi': float(latest.get('tsi', 0)),
                
                # 波动率
                'atr': float(latest.get('atr', 0)),
                
                # 趋势强度
                'er': float(latest.get('er', 0)),
                'r_squared': float(latest.get('r_squared', 0)),
                'adx': float(latest.get('adx', 0)),
                'plus_di': float(latest.get('plus_di', 0)),
                'minus_di': float(latest.get('minus_di', 0)),
                
                # 历史指标（用于检测背离）
                'tsi_prev_high': float(engine.df['tsi'].rolling(20).max().iloc[-1]) if 'tsi' in engine.df.columns else 0,
                'tsi_prev_low': float(engine.df['tsi'].rolling(20).min().iloc[-1]) if 'tsi' in engine.df.columns else 0,
                'er_prev': float(prev.get('er', 0)),
                'adx_prev': float(prev.get('adx', 0)),
            }
            
            return indicators
            
        except Exception as e:
            print(f"[错误] 获取 {symbol} 指标失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def detect_alerts(self, position: Dict[str, Any], indicators: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        检测持仓风险预警
        
        Args:
            position: 持仓信息
            indicators: 指标数据
            
        Returns:
            预警列表
        """
        alerts = []
        
        symbol = position.get('symbol', '')
        direction = position.get('direction', '').upper()
        entry_price = position.get('entry_price', 0)
        current_price = indicators.get('close', 0)
        
        # 计算盈亏
        if entry_price > 0 and current_price > 0:
            if direction == 'LONG':
                pnl_pct = (current_price - entry_price) / entry_price * 100
            elif direction == 'SHORT':
                pnl_pct = (entry_price - current_price) / entry_price * 100
            else:
                pnl_pct = 0
        else:
            pnl_pct = 0
        
        # 获取关键指标
        tsi = indicators.get('tsi', 0)
        er = indicators.get('er', 0)
        r_squared = indicators.get('r_squared', 0)
        adx = indicators.get('adx', 0)
        atr = indicators.get('atr', 0)
        ema20 = indicators.get('ema20', 0)
        ema60 = indicators.get('ema60', 0)
        
        # 历史指标
        tsi_prev_high = indicators.get('tsi_prev_high', 0)
        er_prev = indicators.get('er_prev', 0)
        
        # ============================================================
        # 高风险预警（HIGH）
        # ============================================================
        
        # 1. 趋势反转信号：TSI 顶背离/底背离
        if direction == 'LONG' and tsi < -20 and tsi_prev_high > 20:
            alerts.append({
                'type': 'TREND_REVERSAL',
                'severity': 'HIGH',
                'indicators': {
                    'tsi': tsi,
                    'tsi_prev_high': tsi_prev_high,
                    'er': er
                },
                'trigger_reason': f'TSI 顶背离：当前 TSI={tsi:.1f}，前期高点={tsi_prev_high:.1f}',
                'pnl_pct': pnl_pct
            })
        elif direction == 'SHORT' and tsi > 20 and indicators.get('tsi_prev_low', 0) < -20:
            alerts.append({
                'type': 'TREND_REVERSAL',
                'severity': 'HIGH',
                'indicators': {
                    'tsi': tsi,
                    'tsi_prev_low': indicators.get('tsi_prev_low', 0),
                    'er': er
                },
                'trigger_reason': f'TSI 底背离：当前 TSI={tsi:.1f}，前期低点={indicators.get("tsi_prev_low", 0):.1f}',
                'pnl_pct': pnl_pct
            })
        
        # 2. 效率比骤降
        if er < 0.3 and er_prev > 0.5:
            alerts.append({
                'type': 'ER_DROP',
                'severity': 'HIGH',
                'indicators': {
                    'er': er,
                    'er_prev': er_prev,
                    'tsi': tsi
                },
                'trigger_reason': f'效率比骤降：当前 ER={er:.2f}，前期 ER={er_prev:.2f}',
                'pnl_pct': pnl_pct
            })
        
        # 3. 趋势强度大幅下降
        trend_strength_composite = indicators.get('trend_strength_composite', 0)
        if trend_strength_composite < 0.3:
            alerts.append({
                'type': 'TREND_WEAK',
                'severity': 'HIGH',
                'indicators': {
                    'trend_strength_composite': trend_strength_composite,
                    'er': er,
                    'adx': adx
                },
                'trigger_reason': f'趋势强度不足：复合评分={trend_strength_composite:.2f}',
                'pnl_pct': pnl_pct
            })
        
        # ============================================================
        # 中风险预警（MEDIUM）
        # ============================================================
        
        # 4. 盈利回撤
        if pnl_pct > 5 and pnl_pct < 2:
            alerts.append({
                'type': 'PROFIT_REVERSAL',
                'severity': 'MEDIUM',
                'indicators': {
                    'pnl_pct': pnl_pct,
                    'tsi': tsi,
                    'er': er
                },
                'trigger_reason': f'盈利回撤：盈利从高点回撤至 {pnl_pct:.1f}%',
                'pnl_pct': pnl_pct
            })
        
        # 5. RSI 超买/超卖
        rsi = indicators.get('rsi', 50)
        if direction == 'LONG' and rsi > 70:
            alerts.append({
                'type': 'RSI_OVERBOUGHT',
                'severity': 'MEDIUM',
                'indicators': {
                    'rsi': rsi,
                    'tsi': tsi,
                    'adx': adx
                },
                'trigger_reason': f'RSI 超买：RSI={rsi:.1f}',
                'pnl_pct': pnl_pct
            })
        elif direction == 'SHORT' and rsi < 30:
            alerts.append({
                'type': 'RSI_OVERSOLD',
                'severity': 'MEDIUM',
                'indicators': {
                    'rsi': rsi,
                    'tsi': tsi,
                    'adx': adx
                },
                'trigger_reason': f'RSI 超卖：RSI={rsi:.1f}',
                'pnl_pct': pnl_pct
            })
        
        # 6. 均线死叉/金叉
        if direction == 'LONG' and ema20 < ema60:
            alerts.append({
                'type': 'MA_CROSS',
                'severity': 'MEDIUM',
                'indicators': {
                    'ema20': ema20,
                    'ema60': ema60,
                    'adx': adx
                },
                'trigger_reason': f'均线死叉：EMA20={ema20:.0f} < EMA60={ema60:.0f}',
                'pnl_pct': pnl_pct
            })
        elif direction == 'SHORT' and ema20 > ema60:
            alerts.append({
                'type': 'MA_CROSS',
                'severity': 'MEDIUM',
                'indicators': {
                    'ema20': ema20,
                    'ema60': ema60,
                    'adx': adx
                },
                'trigger_reason': f'均线金叉：EMA20={ema20:.0f} > EMA60={ema60:.0f}',
                'pnl_pct': pnl_pct
            })
        
        # ============================================================
        # 低风险预警（LOW）
        # ============================================================
        
        # 7. 波动率扩大
        atr_ratio = indicators.get('atr_ratio', 1.0)
        if atr_ratio > 1.5:
            alerts.append({
                'type': 'VOLATILITY_HIGH',
                'severity': 'LOW',
                'indicators': {
                    'atr': atr,
                    'atr_ratio': atr_ratio
                },
                'trigger_reason': f'波动率扩大：ATR 比率={atr_ratio:.2f}',
                'pnl_pct': pnl_pct
            })
        
        # 8. ADX 趋势减弱
        if adx < 20 and direction in ['LONG', 'SHORT']:
            alerts.append({
                'type': 'ADX_WEAK',
                'severity': 'LOW',
                'indicators': {
                    'adx': adx,
                    'plus_di': indicators.get('plus_di', 0),
                    'minus_di': indicators.get('minus_di', 0)
                },
                'trigger_reason': f'ADX 趋势减弱：ADX={adx:.1f}',
                'pnl_pct': pnl_pct
            })
        
        return alerts
    
    def monitor(self, positions_file: str, output_file: str = None) -> Dict[str, Any]:
        """
        执行监控
        
        Args:
            positions_file: positions.json 文件路径
            output_file: 输出文件路径（可选）
            
        Returns:
            监控结果字典
        """
        # 加载持仓
        positions = self.load_positions(positions_file)
        
        if not positions:
            return {
                'monitor_time': datetime.now().isoformat(),
                'positions_monitored': 0,
                'alerts': [],
                'no_alert_positions': [],
                'message': '没有持仓需要监控'
            }
        
        # 初始化数据源
        self._init_data_source()
        
        # 监控每个持仓
        all_alerts = []
        no_alert_positions = []
        
        for position in positions:
            symbol = position.get('symbol', '')
            print(f"[监控] {symbol}...")
            
            # 获取指标
            indicators = self.get_position_indicators(symbol)
            if indicators is None:
                print(f"[警告] {symbol} 指标获取失败，跳过")
                continue
            
            # 检测预警
            alerts = self.detect_alerts(position, indicators)
            
            if alerts:
                for alert in alerts:
                    alert['symbol'] = symbol
                    alert['direction'] = position.get('direction', '')
                    alert['entry_price'] = position.get('entry_price', 0)
                    alert['current_price'] = indicators.get('close', 0)
                    all_alerts.append(alert)
            else:
                no_alert_positions.append(symbol)
        
        # 构建结果
        result = {
            'monitor_time': datetime.now().isoformat(),
            'positions_monitored': len(positions),
            'alerts': all_alerts,
            'no_alert_positions': no_alert_positions
        }
        
        # 输出到文件
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[完成] 监控结果已写入: {output_file}")
        
        return result


def main():
    parser = argparse.ArgumentParser(description='持仓监控脚本')
    parser.add_argument('--config', type=str, default='config/config.json',
                        help='配置文件路径')
    parser.add_argument('--positions', type=str, default='config/positions.json',
                        help='持仓文件路径')
    parser.add_argument('--output', type=str, default='data/latest_monitor.json',
                        help='输出文件路径')
    parser.add_argument('--debug', action='store_true',
                        help='启用调试模式')
    
    args = parser.parse_args()
    
    if args.debug:
        print(f"[调试] 配置文件: {args.config}")
        print(f"[调试] 持仓文件: {args.positions}")
        print(f"[调试] 输出文件: {args.output}")
    
    # 转换为绝对路径
    project_root = Path(__file__).parent.parent
    config_file = project_root / args.config
    positions_file = project_root / args.positions
    output_file = project_root / args.output
    
    # 加载配置
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"[警告] 配置文件不存在: {config_file}，使用默认配置")
        config = {}
    
    # 创建监控器
    monitor = PositionMonitor(config)
    
    # 执行监控
    result = monitor.monitor(str(positions_file), str(output_file))
    
    # 打印摘要
    print(f"\n{'='*60}")
    print(f"[监控完成] {result['monitor_time']}")
    print(f"  监控持仓: {result['positions_monitored']} 个")
    print(f"  预警数量: {len(result['alerts'])} 个")
    print(f"  正常持仓: {len(result['no_alert_positions'])} 个")
    
    if result['alerts']:
        print(f"\n[预警详情]")
        for alert in result['alerts']:
            severity = alert.get('severity', 'UNKNOWN')
            symbol = alert.get('symbol', '')
            reason = alert.get('trigger_reason', '')
            print(f"  [{severity}] {symbol}: {reason}")
    
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
