"""
TqSdk 桥接模块

解决 TqSdk 的 sys.exit() 问题：
- 使用 subprocess 在独立子进程中运行 TqSdk
- 通过 JSON 文件交换数据
- 主进程不会被 sys.exit() 终止

使用方式：
    from trend_scanner.tqsdk_bridge import TqSdkBridge
    
    bridge = TqSdkBridge()
    
    # 获取 K 线数据
    df = bridge.get_kline("RB", days=120)
    
    # 获取实时行情
    quote = bridge.get_quote("RB")
"""

import os
import sys
import json
import subprocess
import tempfile
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

import pandas as pd


class TqSdkBridge:
    """TqSdk 桥接器"""
    
    def __init__(self, timeout: int = 60):
        """
        初始化桥接器
        
        Args:
            timeout: 超时时间（秒）
        """
        self.timeout = timeout
        self.worker_script = Path(__file__).parent / 'tqsdk_worker.py'
    
    def get_kline(
        self,
        symbol: str,
        days: int = 120,
        period: str = "daily"
    ) -> Optional[pd.DataFrame]:
        """
        获取 K 线数据
        
        Args:
            symbol: 品种代码（如 "RB", "JM"）
            days: 获取天数
            period: 周期（daily/1h/15m 等）
        
        Returns:
            DataFrame 或 None
        """
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            dir='data'
        ) as f:
            output_file = f.name
        
        try:
            # 构建命令
            cmd = [
                sys.executable,
                str(self.worker_script),
                '--action', 'kline',
                '--symbol', symbol,
                '--days', str(days),
                '--period', period,
                '--output', output_file
            ]
            
            # 执行子进程
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(Path(__file__).parent.parent.parent)
            )
            
            # 读取结果
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data.get('success'):
                    # 转换为 DataFrame
                    records = data['data'].get('data', [])
                    if records:
                        df = pd.DataFrame(records)
                        return df
                
                return None
            else:
                return None
                
        except subprocess.TimeoutExpired:
            print(f"[错误] TqSdk 调用超时: {symbol}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[错误] TqSdk 调用失败: {e}", file=sys.stderr)
            return None
        finally:
            # 清理临时文件
            if os.path.exists(output_file):
                os.remove(output_file)
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情
        
        Args:
            symbol: 品种代码
        
        Returns:
            行情字典或 None
        """
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            dir='data'
        ) as f:
            output_file = f.name
        
        try:
            # 构建命令
            cmd = [
                sys.executable,
                str(self.worker_script),
                '--action', 'quote',
                '--symbol', symbol,
                '--output', output_file
            ]
            
            # 执行子进程
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(Path(__file__).parent.parent.parent)
            )
            
            # 读取结果
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data.get('success'):
                    return data['data']
                
                return None
            else:
                return None
                
        except subprocess.TimeoutExpired:
            print(f"[错误] TqSdk 调用超时: {symbol}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[错误] TqSdk 调用失败: {e}", file=sys.stderr)
            return None
        finally:
            # 清理临时文件
            if os.path.exists(output_file):
                os.remove(output_file)
    
    def get_all_symbols(self, exchanges: list = None) -> List[Dict[str, Any]]:
        """
        获取所有主力合约品种
        
        Args:
            exchanges: 交易所列表
        
        Returns:
            品种列表
        """
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            dir='data'
        ) as f:
            output_file = f.name
        
        try:
            # 构建命令
            cmd = [
                sys.executable,
                str(self.worker_script),
                '--action', 'symbols',
                '--output', output_file
            ]
            
            # 执行子进程
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout * 2,  # 获取所有品种需要更长时间
                cwd=str(Path(__file__).parent.parent.parent)
            )
            
            # 读取结果
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data.get('success'):
                    return data['data'].get('symbols', [])
                
                return []
            else:
                return []
                
        except subprocess.TimeoutExpired:
            print(f"[错误] 获取所有品种超时", file=sys.stderr)
            return []
        except Exception as e:
            print(f"[错误] 获取所有品种失败: {e}", file=sys.stderr)
            return []
        finally:
            # 清理临时文件
            if os.path.exists(output_file):
                os.remove(output_file)
    
    def get_quotes_batch(self, tq_symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量获取行情数据
        
        Args:
            tq_symbols: TqSdk 品种代码列表
        
        Returns:
            行情字典
        """
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            dir='data'
        ) as f:
            output_file = f.name
        
        try:
            # 构建命令
            cmd = [
                sys.executable,
                str(self.worker_script),
                '--action', 'quotes_batch',
                '--symbols', ','.join(tq_symbols),
                '--output', output_file
            ]
            
            # 执行子进程
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout * 3,  # 批量获取需要更长时间
                cwd=str(Path(__file__).parent.parent.parent)
            )
            
            # 读取结果
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data.get('success'):
                    return data['data'].get('quotes', {})
                
                return {}
            else:
                return {}
                
        except subprocess.TimeoutExpired:
            print(f"[错误] 批量获取行情超时", file=sys.stderr)
            return {}
        except Exception as e:
            print(f"[错误] 批量获取行情失败: {e}", file=sys.stderr)
            return {}
        finally:
            # 清理临时文件
            if os.path.exists(output_file):
                os.remove(output_file)
    
    def is_available(self) -> bool:
        """
        检查 TqSdk 是否可用
        
        Returns:
            是否可用
        """
        try:
            # 检查环境变量
            tq_user = os.environ.get('TQ_USER', '')
            tq_password = os.environ.get('TQ_PASSWORD', '')
            
            if not tq_user or not tq_password:
                return False
            
            # 检查 tqsdk 是否可导入
            import tqsdk
            return True
            
        except ImportError:
            return False


class TqSdkDataSource:
    """TqSdk 数据源（使用桥接器）"""
    
    def __init__(self):
        """初始化数据源"""
        self.bridge = TqSdkBridge()
    
    def get_kline(
        self,
        symbol: str,
        days: int = 120,
        period: str = "daily"
    ) -> Optional[pd.DataFrame]:
        """获取 K 线数据"""
        return self.bridge.get_kline(symbol, days, period)
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        return self.bridge.get_quote(symbol)
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.bridge.is_available()
