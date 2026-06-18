#!/usr/bin/env python3
"""
系统健康检查脚本

检查项目：
1. 进程状态
2. 数据库状态
3. 数据源状态
4. 磁盘空间
5. 内存使用
6. 最近错误

使用方式：
    python tools/health_check.py
    python tools/health_check.py --json  # JSON 格式输出
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil


# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class HealthChecker:
    """系统健康检查器"""

    def __init__(self, project_root: str = None):
        """
        初始化健康检查器

        Args:
            project_root: 项目根目录
        """
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.results = {}

    def check_all(self) -> dict[str, Any]:
        """
        执行所有检查

        Returns:
            检查结果字典
        """
        self.results = {"timestamp": datetime.now().isoformat(), "checks": {}}

        # 执行各项检查
        self.results["checks"]["process"] = self.check_process()
        self.results["checks"]["database"] = self.check_database()
        self.results["checks"]["data_source"] = self.check_data_source()
        self.results["checks"]["disk"] = self.check_disk()
        self.results["checks"]["memory"] = self.check_memory()
        self.results["checks"]["logs"] = self.check_logs()
        self.results["checks"]["config"] = self.check_config()

        # 计算总体状态
        self.results["status"] = self._calculate_overall_status()

        return self.results

    def check_process(self) -> dict[str, Any]:
        """检查进程状态"""
        result = {"status": "OK", "details": {}}

        # 检查 Orchestrator
        orchestrator_pid_file = self.project_root / "data" / "orchestrator.pid"
        if orchestrator_pid_file.exists():
            try:
                pid = int(orchestrator_pid_file.read_text().strip())
                process = psutil.Process(pid)
                result["details"]["orchestrator"] = {
                    "status": "running",
                    "pid": pid,
                    "cpu_percent": process.cpu_percent(),
                    "memory_mb": process.memory_info().rss / 1024 / 1024,
                }
            except (ValueError, psutil.NoSuchProcess):
                result["details"]["orchestrator"] = {"status": "stopped"}
                result["status"] = "WARNING"
        else:
            result["details"]["orchestrator"] = {"status": "not_started"}

        # 检查自动 Git 推送
        git_pid_file = self.project_root / "data" / "auto_git_push.pid"
        if git_pid_file.exists():
            try:
                pid = int(git_pid_file.read_text().strip())
                process = psutil.Process(pid)
                result["details"]["auto_git_push"] = {"status": "running", "pid": pid}
            except (ValueError, psutil.NoSuchProcess):
                result["details"]["auto_git_push"] = {"status": "stopped"}
        else:
            result["details"]["auto_git_push"] = {"status": "not_started"}

        return result

    def check_database(self) -> dict[str, Any]:
        """检查数据库状态"""
        result = {"status": "OK", "details": {}}

        # 检查 SQLite
        sqlite_path = self.project_root / "data" / "memory.db"
        if sqlite_path.exists():
            try:
                size_mb = sqlite_path.stat().st_size / 1024 / 1024

                # 检查数据库完整性
                conn = sqlite3.connect(str(sqlite_path))
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                integrity = cursor.fetchone()[0]
                conn.close()

                result["details"]["sqlite"] = {"status": "OK", "size_mb": round(size_mb, 2), "integrity": integrity}

                if integrity != "ok":
                    result["status"] = "WARNING"

            except Exception as e:
                result["details"]["sqlite"] = {"status": "ERROR", "error": str(e)}
                result["status"] = "ERROR"
        else:
            result["details"]["sqlite"] = {"status": "not_found"}

        # 检查 DuckDB
        duckdb_path = self.project_root / "data" / "analytics.duckdb"
        if duckdb_path.exists():
            try:
                size_mb = duckdb_path.stat().st_size / 1024 / 1024
                result["details"]["duckdb"] = {"status": "OK", "size_mb": round(size_mb, 2)}
            except Exception as e:
                result["details"]["duckdb"] = {"status": "ERROR", "error": str(e)}
        else:
            result["details"]["duckdb"] = {"status": "not_found"}

        return result

    def check_data_source(self) -> dict[str, Any]:
        """检查数据源状态"""
        result = {"status": "OK", "details": {}}

        # 检查 TqSdk 环境变量
        tq_user = os.environ.get("TQ_USER", "")
        tq_password = os.environ.get("TQ_PASSWORD", "")

        if tq_user and tq_password:
            result["details"]["tqsdk_env"] = {"status": "configured"}
        else:
            result["details"]["tqsdk_env"] = {"status": "not_configured"}
            result["status"] = "WARNING"

        # 检查 CSV 数据源
        csv_dir = self.project_root / "data" / "klines"
        if csv_dir.exists():
            csv_files = list(csv_dir.glob("*.csv"))
            result["details"]["csv_source"] = {"status": "OK", "file_count": len(csv_files)}
        else:
            result["details"]["csv_source"] = {"status": "not_found"}

        return result

    def check_disk(self) -> dict[str, Any]:
        """检查磁盘空间"""
        result = {"status": "OK", "details": {}}

        try:
            usage = psutil.disk_usage(str(self.project_root))

            result["details"] = {
                "total_gb": round(usage.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(usage.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(usage.free / 1024 / 1024 / 1024, 2),
                "percent": usage.percent,
            }

            # 磁盘空间不足警告
            if usage.percent > 90:
                result["status"] = "WARNING"
            elif usage.percent > 95:
                result["status"] = "ERROR"

        except Exception as e:
            result["status"] = "ERROR"
            result["error"] = str(e)

        return result

    def check_memory(self) -> dict[str, Any]:
        """检查内存使用"""
        result = {"status": "OK", "details": {}}

        try:
            memory = psutil.virtual_memory()

            result["details"] = {
                "total_gb": round(memory.total / 1024 / 1024 / 1024, 2),
                "available_gb": round(memory.available / 1024 / 1024 / 1024, 2),
                "used_gb": round(memory.used / 1024 / 1024 / 1024, 2),
                "percent": memory.percent,
            }

            # 内存不足警告
            if memory.percent > 80:
                result["status"] = "WARNING"
            elif memory.percent > 90:
                result["status"] = "ERROR"

        except Exception as e:
            result["status"] = "ERROR"
            result["error"] = str(e)

        return result

    def check_logs(self) -> dict[str, Any]:
        """检查日志文件"""
        result = {"status": "OK", "details": {}}

        logs_dir = self.project_root / "logs"
        if logs_dir.exists():
            log_files = list(logs_dir.glob("*.log"))

            recent_errors = []
            for log_file in log_files:
                try:
                    # 检查最近 24 小时的错误
                    cutoff = datetime.now() - timedelta(hours=24)

                    with open(log_file, encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if "ERROR" in line or "FAILED" in line:
                                recent_errors.append({"file": log_file.name, "message": line.strip()[:200]})
                except:
                    pass

            result["details"] = {
                "log_count": len(log_files),
                "recent_errors": recent_errors[:10],  # 最多显示 10 条
            }

            if recent_errors:
                result["status"] = "WARNING"
        else:
            result["details"] = {"status": "logs_dir_not_found"}

        return result

    def check_config(self) -> dict[str, Any]:
        """检查配置文件"""
        result = {"status": "OK", "details": {}}

        config_file = self.project_root / "config" / "config.json"
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)

                result["details"] = {"status": "OK", "sections": list(config.keys())}
            except json.JSONDecodeError as e:
                result["details"] = {"status": "ERROR", "error": f"JSON 解析错误: {e}"}
                result["status"] = "ERROR"
        else:
            result["details"] = {"status": "not_found"}
            result["status"] = "WARNING"

        # 检查持仓文件
        positions_file = self.project_root / "config" / "positions.json"
        if positions_file.exists():
            try:
                with open(positions_file, encoding="utf-8") as f:
                    positions = json.load(f)

                result["details"]["positions"] = {"status": "OK", "count": len(positions.get("positions", []))}
            except:
                result["details"]["positions"] = {"status": "ERROR"}
        else:
            result["details"]["positions"] = {"status": "not_found"}

        return result

    def _calculate_overall_status(self) -> str:
        """计算总体状态"""
        statuses = []
        for check_name, check_result in self.results["checks"].items():
            statuses.append(check_result.get("status", "UNKNOWN"))

        if "ERROR" in statuses:
            return "ERROR"
        elif "WARNING" in statuses:
            return "WARNING"
        else:
            return "OK"


def print_report(results: dict[str, Any]):
    """打印检查报告"""
    status_colors = {
        "OK": "\033[92m",  # 绿色
        "WARNING": "\033[93m",  # 黄色
        "ERROR": "\033[91m",  # 红色
    }
    reset_color = "\033[0m"

    print("\n" + "=" * 60)
    print("QuantNova 健康检查报告")
    print("=" * 60)
    print(f"时间: {results['timestamp']}")

    # 总体状态
    overall_status = results["status"]
    color = status_colors.get(overall_status, "")
    print(f"总体状态: {color}{overall_status}{reset_color}")

    print("\n" + "-" * 60)

    # 各项检查结果
    for check_name, check_result in results["checks"].items():
        status = check_result.get("status", "UNKNOWN")
        color = status_colors.get(status, "")

        print(f"\n[{check_name.upper()}]")
        print(f"  状态: {color}{status}{reset_color}")

        # 打印详细信息
        details = check_result.get("details", {})
        for key, value in details.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for k, v in value.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {key}: {value}")

    print("\n" + "=" * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="系统健康检查")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--project-root", type=str, help="项目根目录")

    args = parser.parse_args()

    # 执行检查
    checker = HealthChecker(args.project_root)
    results = checker.check_all()

    # 输出结果
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_report(results)

    # 返回状态码
    if results["status"] == "ERROR":
        sys.exit(1)
    elif results["status"] == "WARNING":
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
