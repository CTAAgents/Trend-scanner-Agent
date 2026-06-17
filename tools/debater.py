#!/usr/bin/env python3
"""
Debater Agent 脚本

封装现有的辩论引擎，提供标准化的输入输出接口。

职责：
1. 接收 Reasoner Agent 的初始方案
2. 进行鹰派/鸽派辩论
3. 输出修正后的方案 + 辩论记录

用法：
    # 辩论单个简报
    python tools/debater.py --brief data/latest_brief.json

    # 强制辩论（忽略触发条件）
    python tools/debater.py --brief data/latest_brief.json --force

    # 输出 JSON 格式
    python tools/debater.py --brief data/latest_brief.json --output json
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

from trend_scanner.debate_engine import DebateReasoningEngine
from trend_scanner.reasoning import WorkBuddyAgentProvider
from trend_scanner.models import MarketContext
from trend_scanner.conceptual_feedback import ConceptualFeedbackGenerator
from trend_scanner.belief_propagation import BeliefPropagationManager


class DebaterAgent:
    """
    Debater Agent
    
    通过鹰派/鸽派辩论修正决策偏差。
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化 Debater Agent
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.debater_config = self.config.get('debater', {})
        
        # 初始化辩论引擎
        self.debate_engine = DebateReasoningEngine(
            hawk_llm=WorkBuddyAgentProvider(model="default"),
            dove_llm=WorkBuddyAgentProvider(model="default")
        )
        
        # 触发条件
        self.trigger_confidence = self.debater_config.get('debate_trigger_confidence', 0.7)
        self.trigger_amount = self.debater_config.get('debate_trigger_amount', 100000)
    
    def _should_debate(self, brief: Dict[str, Any], force: bool = False) -> bool:
        """
        检查是否应该触发辩论
        
        Args:
            brief: 交易决策简报
            force: 是否强制辩论
            
        Returns:
            是否应该辩论
        """
        if force:
            return True
        
        # 检查置信度
        routes = brief.get('routes', [])
        recommended = brief.get('recommended_route', '')
        
        for route in routes:
            if route.get('route_id') == recommended:
                confidence = route.get('confidence', 1.0)
                if confidence < self.trigger_confidence:
                    print(f"[Debater] 置信度 {confidence:.2f} < {self.trigger_confidence}，触发辩论", flush=True)
                    return True
        
        # 检查持仓金额（如果有的话）
        # TODO: 从 positions.json 中获取持仓金额
        
        return False
    
    def debate(self, brief: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        """
        执行辩论
        
        Args:
            brief: 交易决策简报
            force: 是否强制辩论
            
        Returns:
            辩论结果（包含修正后的简报）
        """
        symbol = brief.get('symbol', '')
        print(f"[Debater] 检查 {symbol} 是否需要辩论...", flush=True)
        
        # 检查是否需要辩论
        if not self._should_debate(brief, force):
            print(f"[Debater] {symbol} 不需要辩论，跳过", flush=True)
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'debate_triggered': False,
                'original_brief': brief,
                'revised_brief': brief,
                'revision_summary': '未触发辩论'
            }
        
        print(f"[Debater] 对 {symbol} 执行辩论...", flush=True)
        
        try:
            # 构建 MarketContext（简化版，只用于辩论）
            # 注意：辩论引擎需要 MarketContext，但实际辩论主要依赖简报内容
            from trend_scanner.models import IndicatorSnapshot, MarketStructure, MomentumState, VolatilityState, TrendPhase
            
            # 创建简化的 MarketContext
            snapshot = IndicatorSnapshot(
                timestamp=brief.get('timestamp', datetime.now().isoformat()),
                close=0, high=0, low=0, open=0, volume=0
            )
            
            trend_phase = TrendPhase(
                phase=brief.get('trend_phase', {}).get('phase', 'UNKNOWN'),
                confidence=brief.get('trend_phase', {}).get('confidence', 0.5)
            )
            
            context = MarketContext(
                symbol=symbol,
                timestamp=brief.get('timestamp', datetime.now().isoformat()),
                current_price=0,
                snapshot=snapshot,
                trend_phase=trend_phase
            )
            
            # 执行辩论（使用 reason 方法）
            debate_result = self.debate_engine.reason(
                context=context,
                similar_experiences=[],  # 辩论不需要经验
                experience_aggregation={}
            )
            
            # 构建结果
            result = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'debate_triggered': True,
                'original_brief': brief,
                'debate_result': {
                    'hawk_arguments': debate_result.get('hawk_arguments', []),
                    'dove_arguments': debate_result.get('dove_arguments', []),
                    'synthesis': debate_result.get('synthesis', ''),
                    'divergence': debate_result.get('divergence', 0),
                    'condition_levels': debate_result.get('condition_levels', [])
                },
                'revised_brief': debate_result.get('revised_brief', brief),
                'revision_summary': debate_result.get('revision_summary', '')
            }

            # 概念性反馈分析（v6.1 新增）
            try:
                feedback_gen = ConceptualFeedbackGenerator()
                # 从辩论结果生成概念性反馈
                hawk_args = debate_result.get('hawk_arguments', [])
                dove_args = debate_result.get('dove_arguments', [])
                if hawk_args or dove_args:
                    feedback = feedback_gen.generate_feedback(
                        symbol=symbol,
                        hawk_perspective=hawk_args,
                        dove_perspective=dove_args,
                        market_context=context
                    )
                    result['conceptual_feedback'] = feedback
            except Exception as e:
                logger.debug(f"概念性反馈生成失败: {e}")

            # 信念传播分析（v6.1 新增）
            try:
                bp_manager = BeliefPropagationManager()
                # 从辩论结果更新信念
                bp_result = bp_manager.propagate_beliefs(
                    symbol=symbol,
                    debate_result=debate_result,
                    market_context=context
                )
                result['belief_propagation'] = bp_result
            except Exception as e:
                logger.debug(f"信念传播分析失败: {e}")

            return result
            
        except Exception as e:
            print(f"[错误] 辩论失败: {e}", flush=True)
            import traceback
            traceback.print_exc()
            
            # 辩论失败，返回原始简报
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'debate_triggered': False,
                'original_brief': brief,
                'revised_brief': brief,
                'revision_summary': f'辩论失败: {e}',
                'error': str(e)
            }
    
    def debate_from_file(self, brief_file: str, force: bool = False) -> List[Dict[str, Any]]:
        """
        从简报文件辩论多个品种
        
        Args:
            brief_file: 简报文件路径（JSON 格式）
            force: 是否强制辩论
            
        Returns:
            辩论结果列表
        """
        try:
            with open(brief_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 支持单个简报或简报列表
            if isinstance(data, list):
                briefs = data
            else:
                briefs = [data]
            
            results = []
            for brief in briefs:
                result = self.debate(brief, force=force)
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"[错误] 读取简报文件失败: {e}", flush=True)
            return []


def main():
    parser = argparse.ArgumentParser(description='Debater Agent 脚本')
    parser.add_argument('--brief', type=str, required=True, help='简报文件路径')
    parser.add_argument('--force', action='store_true', help='强制辩论（忽略触发条件）')
    parser.add_argument('--output', choices=['json', 'text'], default='text', help='输出格式')
    parser.add_argument('--save', action='store_true', help='保存结果到 data/latest_debate.json')
    
    args = parser.parse_args()
    
    # 创建 Debater Agent
    agent = DebaterAgent()
    
    # 执行辩论
    results = agent.debate_from_file(args.brief, force=args.force)
    
    # 输出结果
    if args.output == 'json':
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*70}")
        print(f"Debater Agent 辩论报告")
        print(f"辩论时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        for result in results:
            symbol = result.get('symbol', '')
            debate_triggered = result.get('debate_triggered', False)
            revision_summary = result.get('revision_summary', '')
            
            print(f"\n【{symbol}】辩论: {'是' if debate_triggered else '否'}")
            
            if debate_triggered:
                debate_result = result.get('debate_result', {})
                hawk_args = debate_result.get('hawk_arguments', [])
                dove_args = debate_result.get('dove_arguments', [])
                divergence = debate_result.get('divergence', 0)
                
                print(f"  分歧度: {divergence:.2f}")
                
                if hawk_args:
                    print(f"  [鹰派观点]:")
                    for arg in hawk_args:
                        print(f"    - {arg}")
                
                if dove_args:
                    print(f"  [鸽派观点]:")
                    for arg in dove_args:
                        print(f"    - {arg}")
            
            if revision_summary:
                print(f"  [修正摘要]: {revision_summary}")
        
        print(f"\n{'='*70}")
    
    # 保存结果
    if args.save and results:
        output_path = project_root / 'data' / 'latest_debate.json'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到 {output_path}")


if __name__ == '__main__':
    main()
