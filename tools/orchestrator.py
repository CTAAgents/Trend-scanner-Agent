#!/usr/bin/env python3
"""
Orchestrator Agent 脚本

主协调器，接收用户指令，分发任务，汇总结果。

职责：
1. 解析用户自然语言指令
2. 分发任务给专业 Agent 或脚本
3. 汇总结果，生成最终输出

用法：
    # 处理用户指令
    python tools/orchestrator.py --input "帮我扫描一下黑色系"

    # 查看系统状态
    python tools/orchestrator.py --status

    # 执行扫描
    python tools/orchestrator.py --scan
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))


class OrchestratorAgent:
    """
    Orchestrator Agent
    
    主协调器，接收用户指令，分发任务，汇总结果。
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化 Orchestrator Agent
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.orchestrator_config = self.config.get('orchestrator', {})
        
        # 工具路径
        self.tools_dir = project_root / 'tools'
        self.data_dir = project_root / 'data'
        self.config_dir = project_root / 'config'
        
        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _run_script(self, script_name: str, args: List[str] = None) -> Dict[str, Any]:
        """
        运行脚本
        
        Args:
            script_name: 脚本名称
            args: 脚本参数
            
        Returns:
            脚本输出
        """
        script_path = self.tools_dir / script_name
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(project_root)
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': '脚本执行超时',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _parse_intent(self, user_input: str) -> Dict[str, Any]:
        """
        解析用户意图
        
        Args:
            user_input: 用户输入
            
        Returns:
            意图字典
        """
        user_input = user_input.strip().lower()
        
        # 扫描意图
        scan_keywords = ['扫描', '看看', '有什么机会', 'scan']
        if any(keyword in user_input for keyword in scan_keywords):
            # 提取品种范围
            symbol_range = 'all'
            if '黑色' in user_input:
                symbol_range = 'black'
            elif '有色' in user_input:
                symbol_range = 'metal'
            elif '能化' in user_input:
                symbol_range = 'energy'
            
            return {
                'intent': 'scan',
                'symbol_range': symbol_range,
                'raw_input': user_input
            }
        
        # 分析意图
        analyze_keywords = ['分析', '怎么样', '怎么看', 'analyze']
        if any(keyword in user_input for keyword in analyze_keywords):
            # 提取品种代码
            symbol = self._extract_symbol(user_input)
            return {
                'intent': 'analyze',
                'symbol': symbol,
                'raw_input': user_input
            }
        
        # 持仓意图
        position_keywords = ['持仓', '仓位', '我的仓位', 'position']
        if any(keyword in user_input for keyword in position_keywords):
            return {
                'intent': 'position',
                'raw_input': user_input
            }
        
        # 反馈意图
        feedback_keywords = ['平了', '平仓', '赚了', '亏了', '反馈']
        if any(keyword in user_input for keyword in feedback_keywords):
            return {
                'intent': 'feedback',
                'raw_input': user_input
            }
        
        # 配置意图
        config_keywords = ['调到', '改成', '设置', '配置']
        if any(keyword in user_input for keyword in config_keywords):
            return {
                'intent': 'config',
                'raw_input': user_input
            }
        
        # 进化意图
        evolution_keywords = ['进化', '反思', '学习', 'evolve']
        if any(keyword in user_input for keyword in evolution_keywords):
            return {
                'intent': 'evolution',
                'raw_input': user_input
            }
        
        # 默认：未知意图
        return {
            'intent': 'unknown',
            'raw_input': user_input
        }
    
    def _extract_symbol(self, text: str) -> str:
        """
        从文本中提取品种代码
        
        Args:
            text: 文本
            
        Returns:
            品种代码
        """
        # 常见品种名称映射
        symbol_map = {
            '焦煤': 'DCE.jm',
            '焦炭': 'DCE.j',
            '铁矿': 'DCE.i',
            '螺纹': 'SHFE.rb',
            '热卷': 'SHFE.hc',
            '棉花': 'CZCE.CF',
            '白糖': 'CZCE.SR',
            '豆油': 'DCE.y',
            '豆粕': 'DCE.m',
            '棕榈': 'DCE.p',
            '菜油': 'CZCE.OI',
            '沪铜': 'SHFE.cu',
            '沪铝': 'SHFE.al',
            '沪锌': 'SHFE.zn',
            '沪镍': 'SHFE.ni',
            '原油': 'INE.sc',
            '黄金': 'SHFE.au',
            '白银': 'SHFE.ag',
        }
        
        text_lower = text.lower()
        for name, symbol in symbol_map.items():
            if name in text_lower:
                return symbol
        
        # 尝试提取英文代码
        import re
        match = re.search(r'[a-z]{2,3}\d{3,4}', text_lower)
        if match:
            return match.group().upper()
        
        return ''
    
    def process_user_input(self, user_input: str) -> str:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入
            
        Returns:
            响应文本
        """
        print(f"[Orchestrator] 处理用户输入: {user_input}", flush=True)
        
        # 解析意图
        intent = self._parse_intent(user_input)
        print(f"[Orchestrator] 识别意图: {intent['intent']}", flush=True)
        
        # 根据意图分发任务
        if intent['intent'] == 'scan':
            return self._handle_scan(intent)
        elif intent['intent'] == 'analyze':
            return self._handle_analyze(intent)
        elif intent['intent'] == 'position':
            return self._handle_position(intent)
        elif intent['intent'] == 'feedback':
            return self._handle_feedback(intent)
        elif intent['intent'] == 'config':
            return self._handle_config(intent)
        elif intent['intent'] == 'evolution':
            return self._handle_evolution(intent)
        else:
            return self._handle_unknown(intent)
    
    def _handle_scan(self, intent: Dict[str, Any]) -> str:
        """处理扫描意图"""
        print("[Orchestrator] 执行扫描...", flush=True)
        
        # 运行 Scanner 脚本
        result = self._run_script('scan_opportunities.py')
        
        if result['success']:
            return f"📊 扫描完成\n\n{result['stdout']}"
        else:
            return f"❌ 扫描失败\n\n{result['stderr']}"
    
    def _handle_analyze(self, intent: Dict[str, Any]) -> str:
        """处理分析意图"""
        symbol = intent.get('symbol', '')
        if not symbol:
            return "❌ 未识别到品种代码，请指定要分析的品种"
        
        print(f"[Orchestrator] 分析 {symbol}...", flush=True)
        
        # 运行 Reasoner 脚本
        result = self._run_script('reasoner.py', ['--symbol', symbol, '--output', 'text'])
        
        if result['success']:
            return f"📈 {symbol} 分析完成\n\n{result['stdout']}"
        else:
            return f"❌ {symbol} 分析失败\n\n{result['stderr']}"
    
    def _handle_position(self, intent: Dict[str, Any]) -> str:
        """处理持仓意图"""
        print("[Orchestrator] 查看持仓...", flush=True)
        
        # 读取 positions.json
        positions_file = self.config_dir / 'positions.json'
        if not positions_file.exists():
            return "📋 当前无持仓"
        
        try:
            with open(positions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            positions = data.get('positions', [])
            if not positions:
                return "📋 当前无持仓"
            
            # 格式化输出
            lines = ["📋 持仓概览", ""]
            lines.append(f"更新时间: {data.get('updated_at', '未知')}")
            lines.append(f"持仓数量: {len(positions)} 个")
            lines.append("")
            lines.append("品种        方向    入场价    当前价    盈亏    持仓天数")
            lines.append("─" * 60)
            
            for pos in positions:
                symbol = pos.get('symbol', '')
                direction = pos.get('direction', '')
                entry_price = pos.get('entry_price', 0)
                current_price = pos.get('current_price', 0)
                pnl_pct = pos.get('pnl_pct', 0)
                holding_days = pos.get('holding_days', 0)
                
                lines.append(f"{symbol:12} {direction:8} {entry_price:8} {current_price:8} {pnl_pct:+.2f}%  {holding_days}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ 读取持仓失败: {e}"
    
    def _handle_feedback(self, intent: Dict[str, Any]) -> str:
        """处理反馈意图"""
        return "📝 请提供交易反馈详情（品种、方向、入场价、出场价、盈亏等）"
    
    def _handle_config(self, intent: Dict[str, Any]) -> str:
        """处理配置意图"""
        return "⚙️ 请指定要修改的配置项和新值"
    
    def _handle_evolution(self, intent: Dict[str, Any]) -> str:
        """处理进化意图"""
        print("[Orchestrator] 执行进化...", flush=True)
        
        # 运行 Evolver 脚本
        result = self._run_script('evolver.py', ['--periodic'])
        
        if result['success']:
            return f"🧬 进化完成\n\n{result['stdout']}"
        else:
            return f"❌ 进化失败\n\n{result['stderr']}"
    
    def _handle_unknown(self, intent: Dict[str, Any]) -> str:
        """处理未知意图"""
        return f"❓ 未识别的指令: {intent['raw_input']}\n\n可用指令:\n• 扫描 - 扫描市场机会\n• 分析 [品种] - 分析指定品种\n• 持仓 - 查看当前持仓\n• 反馈 - 提交交易反馈\n• 配置 - 修改系统配置\n• 进化 - 执行策略进化"
    
    def get_status(self) -> str:
        """
        获取系统状态
        
        Returns:
            状态文本
        """
        lines = ["📊 系统状态", ""]
        
        # 检查数据源
        lines.append("数据源:")
        lines.append(f"  • TqSdk: {'可用' if self._check_tqsdk() else '不可用'}")
        lines.append(f"  • CSV: {'可用' if self._check_csv() else '不可用'}")
        lines.append("")
        
        # 检查配置
        config_file = self.config_dir / 'config.json'
        lines.append(f"配置文件: {'存在' if config_file.exists() else '不存在'}")
        
        # 检查持仓
        positions_file = self.config_dir / 'positions.json'
        if positions_file.exists():
            with open(positions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            positions = data.get('positions', [])
            lines.append(f"持仓数量: {len(positions)} 个")
        else:
            lines.append("持仓数量: 0 个")
        
        # 检查 Agent
        lines.append("")
        lines.append("Agent 状态:")
        lines.append(f"  • Reasoner: {'就绪' if (self.tools_dir / 'reasoner.py').exists() else '未就绪'}")
        lines.append(f"  • Debater: {'就绪' if (self.tools_dir / 'debater.py').exists() else '未就绪'}")
        lines.append(f"  • Evolver: {'就绪' if (self.tools_dir / 'evolver.py').exists() else '未就绪'}")
        
        return "\n".join(lines)
    
    def _check_tqsdk(self) -> bool:
        """检查 TqSdk 是否可用"""
        try:
            sys.path.insert(0, str(project_root / "scripts"))
            from trend_scanner.data_source import TqSdkSource
            source = TqSdkSource()
            return source.is_available()
        except:
            return False
    
    def _check_csv(self) -> bool:
        """检查 CSV 数据源是否可用"""
        try:
            sys.path.insert(0, str(project_root / "scripts"))
            from trend_scanner.data_source import CsvSource
            source = CsvSource()
            return source.is_available()
        except:
            return False


def main():
    parser = argparse.ArgumentParser(description='Orchestrator Agent 脚本')
    parser.add_argument('--input', type=str, help='用户输入')
    parser.add_argument('--status', action='store_true', help='查看系统状态')
    parser.add_argument('--scan', action='store_true', help='执行扫描')
    parser.add_argument('--output', choices=['json', 'text'], default='text', help='输出格式')
    
    args = parser.parse_args()
    
    # 创建 Orchestrator Agent
    agent = OrchestratorAgent()
    
    # 执行操作
    if args.status:
        result = agent.get_status()
        print(result.encode('utf-8', errors='replace').decode('utf-8'))
    elif args.scan:
        result = agent.process_user_input("扫描")
        print(result.encode('utf-8', errors='replace').decode('utf-8'))
    elif args.input:
        result = agent.process_user_input(args.input)
        print(result.encode('utf-8', errors='replace').decode('utf-8'))
    else:
        print("[错误] 请指定 --input, --status 或 --scan", flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
