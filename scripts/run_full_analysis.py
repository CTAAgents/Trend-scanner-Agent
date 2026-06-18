#!/usr/bin/env python3
"""
运行QuantNova完整系统流程分析
包括趋势识别、市场上下文、Reasoner深度分析
"""

import duckdb
import os
import pandas as pd
import numpy as np
import sys
import json
from datetime import datetime

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'scripts'))

# 导入系统模块
from reasoning.market_analysis import TrendPhaseDetector
from reasoning.reasoner import ReasonerAgent
from core.models import MarketContext

def main():
    # 连接数据库
    db_path = os.path.join(project_root, 'data', 'market.db')
    if not os.path.exists(db_path):
        print(f'数据库文件不存在: {db_path}')
        return
    
    conn = duckdb.connect(db_path, read_only=True)
    
    # 选择有足够数据的品种进行分析
    result = conn.execute('''
        SELECT 
            symbol,
            COUNT(DISTINCT DATE(timestamp)) as date_count
        FROM klines
        GROUP BY symbol
        HAVING COUNT(DISTINCT DATE(timestamp)) >= 20
        ORDER BY symbol
        LIMIT 10
    ''').fetchall()
    
    symbols = [row[0] for row in result]
    print(f'找到{len(symbols)}个有足够数据的品种')
    
    # 尝试创建ReasonerAgent
    try:
        reasoner = ReasonerAgent()
        print('成功创建ReasonerAgent')
    except Exception as e:
        print(f'创建ReasonerAgent失败: {e}')
        reasoner = None
    
    # 分析每个品种
    print('\n基于QuantNova完整系统流程的分析（包括趋势识别和Reasoner深度分析）:')
    print('=' * 120)
    
    for symbol in symbols[:5]:  # 只分析前5个品种
        try:
            print(f'\n分析 {symbol}:')
            print('-' * 80)
            
            # 获取数据
            result = conn.execute('''
                SELECT 
                    close,
                    high,
                    low,
                    volume,
                    timestamp
                FROM klines
                WHERE symbol = ?
                ORDER BY timestamp ASC
            ''', [symbol]).fetchall()
            
            if result and len(result) >= 20:
                df = pd.DataFrame(result, columns=['close', 'high', 'low', 'volume', 'timestamp'])
                
                # 计算技术指标
                df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
                df['ema60'] = df['close'].ewm(span=60, adjust=False).mean() if len(df) >= 60 else df['ema20']
                
                exp1 = df['close'].ewm(span=12, adjust=False).mean()
                exp2 = df['close'].ewm(span=26, adjust=False).mean()
                df['macd'] = exp1 - exp2
                df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
                df['macd_hist'] = df['macd'] - df['macd_signal']
                
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['rsi'] = 100 - (100 / (1 + rs))
                
                # 1. 趋势阶段识别
                phase, confidence, reliability, breakdown, alerts, evidence = TrendPhaseDetector.detect(df, 'neutral')
                print(f'1. 趋势阶段: {phase} (置信度: {confidence:.2f}, 可靠性: {reliability})')
                
                # 2. 创建市场上下文
                context = MarketContext(
                    symbol=symbol,
                    timestamp=datetime.now().isoformat(),
                    timeframe='daily',
                    current_price=df['close'].iloc[-1],
                    price_change_pct=((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]) * 100 if len(df) >= 2 else 0
                )
                
                print(f'2. 市场上下文创建成功')
                
                # 3. 运行Reasoner深度分析（如果有）
                if reasoner:
                    try:
                        # 准备信号数据
                        signal_data = {
                            'symbol': symbol,
                            'current_price': df['close'].iloc[-1],
                            'trend_phase': phase,
                            'phase_confidence': confidence,
                            'reliability': reliability,
                            'indicators': {
                                'ema20': df['ema20'].iloc[-1],
                                'ema60': df['ema60'].iloc[-1],
                                'macd_hist': df['macd_hist'].iloc[-1],
                                'rsi': df['rsi'].iloc[-1]
                            }
                        }
                        
                        # 运行Reasoner分析
                        brief = reasoner.analyze(signal_data)
                        
                        print(f'3. Reasoner深度分析结果:')
                        print(f'   - 置信度: {brief.get("confidence", 0):.2f}')
                        print(f'   - 推荐操作: {brief.get("recommended_action", "N/A")}')
                        print(f'   - 风险评估: {brief.get("risk_assessment", "N/A")}')
                        
                        # 4. 综合建议
                        print(f'4. 综合建议:')
                        action = brief.get('recommended_action', 'HOLD')
                        confidence = brief.get('confidence', 0)
                        
                        if action == 'BUY':
                            advice = '做多'
                        elif action == 'SELL':
                            advice = '做空'
                        else:
                            advice = '观望'
                        
                        print(f'   - 操作建议: {advice} (置信度: {confidence:.2f})')
                        print(f'   - 趋势阶段: {phase}')
                        print(f'   - 系统可靠性: {reliability}/100')
                        
                    except Exception as e:
                        print(f'   Reasoner分析失败: {e}')
                else:
                    print('3. Reasoner不可用，跳过深度分析')
                    
                    # 基于趋势阶段给出建议
                    print(f'4. 基于趋势阶段的建议:')
                    if phase in ['EMERGING', 'DEVELOPING']:
                        if df['ema20'].iloc[-1] > df['ema60'].iloc[-1]:
                            advice = '关注做多'
                        else:
                            advice = '关注做空'
                    elif phase in ['FATIGUING', 'REVERSING']:
                        advice = '观望/反转'
                    else:
                        advice = '区间交易'
                    
                    print(f'   - 趋势阶段建议: {advice}')
                    print(f'   - 系统可靠性: {reliability}/100')
                
            else:
                print(f'   数据不足: {len(result)}天')
                
        except Exception as e:
            print(f'   分析失败: {e}')
    
    # 打印系统流程说明
    print('\n' + '=' * 120)
    print('QuantNova完整系统流程:')
    print('=' * 120)
    print('1. 数据收集: 获取品种历史数据')
    print('2. 指标计算: 计算EMA、MACD、RSI、ADX、STOCH、CCI等技术指标')
    print('3. 趋势识别: 使用TrendPhaseDetector识别趋势阶段')
    print('4. 市场上下文: 创建MarketContext对象')
    print('5. Reasoner深度分析: 使用LLM进行深度分析（需要WorkBuddyAgentProvider）')
    print('6. 综合建议: 结合趋势阶段和Reasoner分析结果给出建议')
    print()
    print('风险控制:')
    print('- 所有交易必须设置2%止损')
    print('- 单品种仓位不超过5%（7,500元）')
    print('- 总仓位不超过15%（22,500元）')
    print('- 总风险不超过总资金1%（1,500元）')
    print()
    print('重要提醒:')
    print('- 所有建议需人工确认后执行')
    print('- 严格遵循系统逻辑，不能主观解读')
    print('- 数据不足时，明确告知用户')
    
    conn.close()

if __name__ == '__main__':
    main()
