"""
Agent 健康检查和错误处理模块

功能：
- Agent 健康检查（检测崩溃、超时）
- TqSdk 连接失败自动降级到通达信 MCP
- 脚本执行超时重试机制
- 错误统计和报告

使用方式：
    from health_check import HealthChecker
    
    checker = HealthChecker()
    
    # 检查数据源健康状态
    source_status = checker.check_data_source()
    
    # 执行带重试的脚本
    result = checker.run_with_retry("python tools/scan_opportunities.py", max_retries=2)
    
    # 获取健康报告
    report = checker.get_health_report()
"""

import json
import os
import sys
import time
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# 文件路径
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
HEALTH_FILE = os.path.join(DATA_DIR, 'health_status.json')
ERROR_LOG_FILE = os.path.join(DATA_DIR, 'error_log.json')


class HealthChecker:
    """Agent 健康检查器"""
    
    def __init__(self):
        """初始化"""
        self.health_status = self._load_health_status()
        self.error_log = self._load_error_log()
    
    def _load_health_status(self) -> Dict[str, Any]:
        """加载健康状态"""
        if not os.path.exists(HEALTH_FILE):
            return {
                "last_check": None,
                "data_source": {"status": "UNKNOWN", "last_success": None},
                "agents": {},
                "scripts": {}
            }
        with open(HEALTH_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_health_status(self):
        """保存健康状态"""
        os.makedirs(DATA_DIR, exist_ok=True)
        self.health_status["last_check"] = datetime.now().isoformat()
        with open(HEALTH_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.health_status, f, ensure_ascii=False, indent=2)
    
    def _load_error_log(self) -> List[Dict[str, Any]]:
        """加载错误日志"""
        if not os.path.exists(ERROR_LOG_FILE):
            return []
        with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_error_log(self):
        """保存错误日志（只保留最近 100 条）"""
        os.makedirs(DATA_DIR, exist_ok=True)
        self.error_log = self.error_log[-100:]
        with open(ERROR_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.error_log, f, ensure_ascii=False, indent=2)
    
    def _record_error(self, component: str, error_type: str, message: str, context: Dict[str, Any] = None):
        """记录错误"""
        self.error_log.append({
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "error_type": error_type,
            "message": message,
            "context": context or {}
        })
        self._save_error_log()
    
    def check_data_source(self) -> Dict[str, Any]:
        """
        检查数据源健康状态
        
        检查顺序：
        1. TqSdk 连接
        2. 通达信 MCP（如果 TqSdk 失败）
        
        返回:
            数据源状态字典
        """
        result = {
            "tqsdk": {"status": "UNKNOWN", "latency_ms": None, "error": None},
            "tdx": {"status": "UNKNOWN", "latency_ms": None, "error": None},
            "recommended": "tqsdk"
        }
        
        # 检查 TqSdk
        try:
            start_time = time.time()
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
            from trend_scanner.data_source import DataSourceFactory
            
            ds = DataSourceFactory.create(source="tqsdk", force_new=True)
            if ds.is_available():
                # 尝试获取数据
                df = ds.get_kline("RB", days=10)
                if df is not None and len(df) > 0:
                    latency = (time.time() - start_time) * 1000
                    result["tqsdk"] = {"status": "OK", "latency_ms": round(latency), "error": None}
                    self.health_status["data_source"] = {
                        "status": "OK",
                        "last_success": datetime.now().isoformat(),
                        "type": "tqsdk"
                    }
                else:
                    result["tqsdk"] = {"status": "ERROR", "latency_ms": None, "error": "数据获取失败"}
                    self._record_error("data_source", "DATA_FETCH_FAILED", "TqSdk 数据获取失败")
            else:
                result["tqsdk"] = {"status": "ERROR", "latency_ms": None, "error": "认证失败"}
                self._record_error("data_source", "AUTH_FAILED", "TqSdk 认证失败")
        
        except Exception as e:
            result["tqsdk"] = {"status": "ERROR", "latency_ms": None, "error": str(e)}
            self._record_error("data_source", "CONNECTION_FAILED", f"TqSdk 连接失败: {e}")
        
        # 如果 TqSdk 失败，检查通达信 MCP
        if result["tqsdk"]["status"] != "OK":
            result["recommended"] = "tdx"
            # 通达信 MCP 通过 connector 检查，这里只标记为可用
            result["tdx"] = {"status": "AVAILABLE", "latency_ms": None, "error": None}
        
        self._save_health_status()
        return result
    
    def run_with_retry(self, command: str, max_retries: int = 2, timeout: int = 60) -> Dict[str, Any]:
        """
        执行带重试的脚本
        
        参数:
            command: 要执行的命令
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
        
        返回:
            执行结果字典
        """
        result = {
            "command": command,
            "attempts": 0,
            "success": False,
            "output": None,
            "error": None,
            "total_time_ms": 0
        }
        
        start_time = time.time()
        
        for attempt in range(max_retries + 1):
            result["attempts"] = attempt + 1
            
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                
                if proc.returncode == 0:
                    result["success"] = True
                    result["output"] = proc.stdout
                    result["total_time_ms"] = round((time.time() - start_time) * 1000)
                    return result
                else:
                    result["error"] = proc.stderr
                    if attempt < max_retries:
                        time.sleep(2)  # 等待 2 秒后重试
            
            except subprocess.TimeoutExpired:
                result["error"] = f"超时（{timeout}秒）"
                self._record_error("script", "TIMEOUT", f"脚本超时: {command}", {"timeout": timeout})
                if attempt < max_retries:
                    time.sleep(2)
            
            except Exception as e:
                result["error"] = str(e)
                self._record_error("script", "EXECUTION_FAILED", f"脚本执行失败: {command}", {"error": str(e)})
                if attempt < max_retries:
                    time.sleep(2)
        
        result["total_time_ms"] = round((time.time() - start_time) * 1000)
        return result
    
    def check_script_health(self, script_name: str) -> Dict[str, Any]:
        """
        检查脚本健康状态
        
        参数:
            script_name: 脚本名称（如 scan_opportunities.py）
        
        返回:
            脚本健康状态
        """
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
        
        if not os.path.exists(script_path):
            return {
                "script": script_name,
                "status": "NOT_FOUND",
                "error": f"脚本不存在: {script_path}"
            }
        
        # 检查脚本语法
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", script_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return {
                    "script": script_name,
                    "status": "SYNTAX_ERROR",
                    "error": result.stderr
                }
        
        except Exception as e:
            return {
                "script": script_name,
                "status": "CHECK_FAILED",
                "error": str(e)
            }
        
        return {
            "script": script_name,
            "status": "OK",
            "error": None
        }
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取完整健康报告"""
        # 检查各脚本健康状态
        scripts_to_check = [
            "scan_opportunities.py",
            "heartbeat.py",
            "monitor_positions.py",
            "run_reasoner.py",
            "run_debater.py",
            "run_evolver.py",
            "orchestrator.py"
        ]
        
        script_status = {}
        for script in scripts_to_check:
            script_status[script] = self.check_script_health(script)
        
        # 统计错误
        recent_errors = [e for e in self.error_log 
                        if datetime.fromisoformat(e["timestamp"]) > datetime.now() - timedelta(hours=24)]
        
        error_by_component = {}
        for error in recent_errors:
            comp = error["component"]
            if comp not in error_by_component:
                error_by_component[comp] = 0
            error_by_component[comp] += 1
        
        report = {
            "report_time": datetime.now().isoformat(),
            "data_source": self.health_status.get("data_source", {}),
            "scripts": script_status,
            "recent_errors": {
                "total": len(recent_errors),
                "by_component": error_by_component
            },
            "overall_status": "HEALTHY" if len(recent_errors) < 5 else "DEGRADED"
        }
        
        return report


def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent 健康检查")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # check 命令
    subparsers.add_parser("check", help="检查数据源健康状态")
    
    # report 命令
    subparsers.add_parser("report", help="获取完整健康报告")
    
    # test 命令
    test_parser = subparsers.add_parser("test", help="测试脚本执行")
    test_parser.add_argument("--command", required=True, help="要执行的命令")
    test_parser.add_argument("--retries", type=int, default=2, help="最大重试次数")
    test_parser.add_argument("--timeout", type=int, default=60, help="超时时间（秒）")
    
    args = parser.parse_args()
    
    checker = HealthChecker()
    
    if args.command == "check":
        print("数据源健康检查")
        print("=" * 50)
        result = checker.check_data_source()
        
        tqsdk = result["tqsdk"]
        print(f"\nTqSdk:")
        print(f"  状态: {tqsdk['status']}")
        if tqsdk['latency_ms']:
            print(f"  延迟: {tqsdk['latency_ms']}ms")
        if tqsdk['error']:
            print(f"  错误: {tqsdk['error']}")
        
        tdx = result["tdx"]
        print(f"\n通达信 MCP:")
        print(f"  状态: {tdx['status']}")
        
        print(f"\n推荐数据源: {result['recommended']}")
    
    elif args.command == "report":
        print("Agent 健康报告")
        print("=" * 50)
        report = checker.get_health_report()
        
        print(f"\n数据源状态: {report['data_source'].get('status', 'UNKNOWN')}")
        
        print(f"\n脚本状态:")
        for script, status in report['scripts'].items():
            status_mark = {'OK': '✓', 'NOT_FOUND': '✗', 'SYNTAX_ERROR': '✗'}.get(status['status'], '?')
            print(f"  {status_mark} {script}: {status['status']}")
        
        print(f"\n最近 24 小时错误: {report['recent_errors']['total']} 个")
        for comp, count in report['recent_errors']['by_component'].items():
            print(f"  {comp}: {count} 个")
        
        print(f"\n整体状态: {report['overall_status']}")
    
    elif args.command == "test":
        print(f"测试脚本执行: {args.command}")
        print("=" * 50)
        result = checker.run_with_retry(args.command, max_retries=args.retries, timeout=args.timeout)
        
        print(f"尝试次数: {result['attempts']}")
        print(f"成功: {result['success']}")
        print(f"总耗时: {result['total_time_ms']}ms")
        
        if result['success']:
            print(f"\n输出:\n{result['output'][:500]}...")
        else:
            print(f"\n错误: {result['error']}")


if __name__ == "__main__":
    main()
