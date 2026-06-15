"""
Debater 包装脚本 — 对 Reasoner 输出进行 self-debate

读取 Reasoner 输出的交易决策简报，执行鹰派/鸽派辩论，
输出修正后的方案。

使用方式：
    python tools/run_debater.py                          # 处理所有推理结果
    python tools/run_debater.py --symbol DCE.jm2609      # 处理指定品种
    python tools/run_debater.py --input data/latest_reasoning.json  # 指定输入文件
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any

# 导入数据格式工具
from data_formats import load_config


def load_reasoning_results(input_file: str = None) -> List[Dict[str, Any]]:
    """加载 Reasoner 输出"""
    if input_file:
        path = input_file
    else:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                           'data', 'latest_reasoning.json')
    
    if not os.path.exists(path):
        print(f"错误: 未找到推理结果文件 {path}")
        return []
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 支持单个结果或列表
    if isinstance(data, list):
        return data
    return [data]


def generate_hawk_arguments(reasoning: Dict[str, Any]) -> List[str]:
    """
    生成鹰派论点（看空/风险视角）
    
    注意：这是基于规则的论点生成，不依赖 LLM。
    正式运行时由 Debater Agent 的 LLM 推理替代。
    """
    arguments = []
    
    ma = reasoning.get('market_assessment', {})
    uncertainty = reasoning.get('uncertainty', {})
    routes = reasoning.get('routes', [])
    
    # 从不确定性中提取风险因素
    factors = uncertainty.get('factors', [])
    for factor in factors:
        arguments.append(f"风险因素: {factor}")
    
    # 从市场评估中提取潜在问题
    observations = ma.get('key_observations', [])
    for obs in observations:
        if any(kw in obs for kw in ['超买', '超卖', '背离', '风险', '不确定', '下降']):
            arguments.append(f"关注点: {obs}")
    
    # 通用鹰派论点
    if not arguments:
        arguments.append("当前趋势可能已接近尾声，需警惕反转风险")
        arguments.append("入场时机可能偏晚，建议等待回调")
    
    return arguments


def generate_dove_arguments(reasoning: Dict[str, Any]) -> List[str]:
    """
    生成鸽派论点（看多/趋势视角）
    
    注意：这是基于规则的论点生成，不依赖 LLM。
    正式运行时由 Debater Agent 的 LLM 推理替代。
    """
    arguments = []
    
    ma = reasoning.get('market_assessment', {})
    routes = reasoning.get('routes', [])
    
    # 从市场评估中提取支撑因素
    observations = ma.get('key_observations', [])
    for obs in observations:
        if any(kw in obs for kw in ['支撑', '确认', '充足', '有效', '利多']):
            arguments.append(f"支撑因素: {obs}")
    
    # 从趋势阶段判断
    phase = ma.get('trend_phase', '')
    if phase in ['DEVELOPING', 'EMERGING']:
        arguments.append(f"趋势阶段为 {phase}，仍有发展空间")
    
    # 从方案中提取正面理由
    for route in routes:
        reasoning_text = route.get('reasoning', '')
        if reasoning_text:
            arguments.append(f"方案支撑: {reasoning_text}")
    
    # 通用鸽派论点
    if not arguments:
        arguments.append("趋势方向明确，顺势交易是主要策略")
        arguments.append("当前市场结构支持趋势延续")
    
    return arguments


def assess_divergence(hawk_args: List[str], dove_args: List[str], confidence: float) -> str:
    """评估分歧度"""
    if confidence < 0.5:
        return "HIGH"
    elif confidence < 0.7:
        return "MEDIUM"
    else:
        return "LOW"


def revise_confidence(original_confidence: float, divergence_level: str) -> float:
    """根据辩论结果修正置信度"""
    if divergence_level == "HIGH":
        return max(original_confidence - 0.2, 0.1)
    elif divergence_level == "MEDIUM":
        return max(original_confidence - 0.1, 0.1)
    else:
        return original_confidence


def run_debate_for_reasoning(reasoning: Dict[str, Any]) -> Dict[str, Any]:
    """
    对单个推理结果执行辩论
    
    参数:
        reasoning: Reasoner 输出的推理结果
    
    返回:
        辩论结果字典
    """
    symbol = reasoning.get('symbol', 'UNKNOWN')
    direction = reasoning.get('direction', 'UNKNOWN')
    original_confidence = reasoning.get('confidence', 0.5)
    
    print(f"  辩论中: {symbol} ({direction})...", end="", flush=True)
    
    # 生成鹰派论点
    hawk_arguments = generate_hawk_arguments(reasoning)
    
    # 生成鸽派论点
    dove_arguments = generate_dove_arguments(reasoning)
    
    # 评估分歧度
    divergence_level = assess_divergence(hawk_arguments, dove_arguments, original_confidence)
    
    # 修正置信度
    revised_confidence = revise_confidence(original_confidence, divergence_level)
    
    # 识别关键分歧点
    key_disagreement = "趋势持续性和入场时机"
    if hawk_arguments:
        key_disagreement = hawk_arguments[0].split(':')[-1].strip() if ':' in hawk_arguments[0] else hawk_arguments[0]
    
    # 生成修正理由
    revision_reason = ""
    if divergence_level == "HIGH":
        revision_reason = "鹰派论点强势，建议观望或大幅降低仓位"
    elif divergence_level == "MEDIUM":
        revision_reason = "鹰派论点有一定道理，建议优化入场时机或控制仓位"
    else:
        revision_reason = "鹰派论点较弱，维持原方案"
    
    # 构建辩论结果
    debate_result = {
        "symbol": symbol,
        "direction": direction,
        "original_confidence": original_confidence,
        "debate_result": {
            "hawk_arguments": hawk_arguments,
            "dove_arguments": dove_arguments,
            "key_disagreement": key_disagreement,
            "divergence_level": divergence_level,
            "resolution": revision_reason
        },
        "revised_confidence": revised_confidence,
        "revised_routes": reasoning.get('routes', []),
        "revised_constraints": reasoning.get('constraints', []),
        "debate_summary": f"鹰派提出 {len(hawk_arguments)} 个风险论点，鸽派提出 {len(dove_arguments)} 个支撑论点。分歧度: {divergence_level}。{revision_reason}",
        "debate_time": datetime.now().isoformat()
    }
    
    print(f" 完成 (分歧: {divergence_level}, 置信度: {original_confidence:.2f} → {revised_confidence:.2f})")
    
    return debate_result


def run_debate(reasoning_results: List[Dict[str, Any]] = None, 
               symbols: List[str] = None,
               input_file: str = None) -> List[Dict[str, Any]]:
    """
    执行辩论
    
    参数:
        reasoning_results: Reasoner 输出结果列表
        symbols: 品种列表（筛选）
        input_file: 输入文件路径
    
    返回:
        辩论结果列表
    """
    # 加载配置
    config = load_config()
    debater_config = config.get("debater", {})
    trigger_conditions = debater_config.get("trigger_conditions", {})
    confidence_threshold = trigger_conditions.get("confidence_below", 0.7)
    
    # 加载推理结果
    if reasoning_results is None:
        reasoning_results = load_reasoning_results(input_file)
    
    if not reasoning_results:
        print("无推理结果需要辩论")
        return []
    
    # 筛选需要辩论的结果
    to_debate = []
    for r in reasoning_results:
        # 按品种筛选
        if symbols and r.get('symbol') not in symbols:
            continue
        
        # 按置信度筛选
        confidence = r.get('confidence', 0)
        if confidence >= confidence_threshold:
            print(f"  跳过 {r.get('symbol', '')}: 置信度 {confidence:.2f} >= {confidence_threshold}")
            continue
        
        to_debate.append(r)
    
    if not to_debate:
        print("无需要辩论的结果（置信度均达标）")
        return []
    
    print(f"开始辩论 {len(to_debate)} 个结果...")
    
    # 执行辩论
    results = []
    for reasoning in to_debate:
        result = run_debate_for_reasoning(reasoning)
        results.append(result)
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Debater 包装脚本")
    parser.add_argument("--symbol", type=str, help="指定品种代码")
    parser.add_argument("--symbols", type=str, help="多个品种代码（逗号分隔）")
    parser.add_argument("--input", type=str, help="指定输入文件路径")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")
    parser.add_argument("--save", action="store_true", help="保存结果到 data/latest_debate.json")
    parser.add_argument("--force", action="store_true", help="强制辩论（忽略置信度阈值）")
    
    args = parser.parse_args()
    
    # 确定品种列表
    symbols = None
    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    
    # 加载推理结果
    reasoning_results = load_reasoning_results(args.input)
    
    # 如果强制辩论，修改置信度阈值
    if args.force:
        for r in reasoning_results:
            r['confidence'] = 0.0  # 强制触发辩论
    
    # 执行辩论
    results = run_debate(reasoning_results=reasoning_results, symbols=symbols)
    
    # 输出结果
    if args.output == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"\n辩论完成: {len(results)} 个品种")
        print("=" * 60)
        for r in results:
            symbol = r.get('symbol', '')
            orig = r.get('original_confidence', 0)
            revised = r.get('revised_confidence', 0)
            divergence = r.get('debate_result', {}).get('divergence_level', 'N/A')
            
            print(f"\n【{symbol}】")
            print(f"  原始置信度: {orig:.2f} → 修正置信度: {revised:.2f}")
            print(f"  分歧度: {divergence}")
            print(f"  辩论摘要: {r.get('debate_summary', '')}")
            
            # 鹰派论点
            hawk = r.get('debate_result', {}).get('hawk_arguments', [])
            if hawk:
                print(f"  鹰派论点:")
                for arg in hawk:
                    print(f"    - {arg}")
            
            # 鸽派论点
            dove = r.get('debate_result', {}).get('dove_arguments', [])
            if dove:
                print(f"  鸽派论点:")
                for arg in dove:
                    print(f"    - {arg}")
    
    # 保存结果
    if args.save and results:
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                  'data', 'latest_debate.json')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到 data/latest_debate.json")


if __name__ == "__main__":
    main()
