"""
Token 预算控制模块

实现每日 850K token 预算和三级降级策略：
- 80%：停止 Debater Agent（跳过辩论）
- 90%：只保留 Scanner 脚本（无推理）
- 100%：停止所有 Agent，等待次日重置

使用方式：
    from token_budget import TokenBudget
    
    budget = TokenBudget()
    budget.record_usage("reasoner", 5000)
    
    if budget.can_use("debater"):
        # 执行辩论
        budget.record_usage("debater", 3000)
    else:
        # 跳过辩论
        pass
"""

import json
import os
from datetime import datetime, date
from typing import Optional, Dict, Any

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'config.json')
USAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'token_usage.json')


class TokenBudget:
    """Token 预算控制器"""
    
    def __init__(self):
        """初始化"""
        self.config = self._load_config()
        self.usage = self._load_usage()
        self._check_daily_reset()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        if not os.path.exists(CONFIG_FILE):
            return {}
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_usage(self) -> Dict[str, Any]:
        """加载使用记录"""
        if not os.path.exists(USAGE_FILE):
            return {"date": None, "total": 0, "by_component": {}}
        with open(USAGE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_usage(self):
        """保存使用记录"""
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        with open(USAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.usage, f, ensure_ascii=False, indent=2)
    
    def _check_daily_reset(self):
        """检查是否需要每日重置"""
        today = date.today().isoformat()
        if self.usage.get("date") != today:
            self.usage = {
                "date": today,
                "total": 0,
                "by_component": {}
            }
            self._save_usage()
    
    def get_daily_limit(self) -> int:
        """获取每日 token 预算"""
        return self.config.get("token_budget", {}).get("daily_limit", 850000)
    
    def get_usage(self) -> int:
        """获取当前使用量"""
        return self.usage.get("total", 0)
    
    def get_usage_pct(self) -> float:
        """获取使用百分比"""
        limit = self.get_daily_limit()
        if limit == 0:
            return 0
        return self.get_usage() / limit * 100
    
    def record_usage(self, component: str, tokens: int):
        """
        记录 token 使用
        
        参数:
            component: 组件名称（reasoner/debater/evolver/orchestrator）
            tokens: 使用的 token 数量
        """
        self._check_daily_reset()
        
        self.usage["total"] = self.usage.get("total", 0) + tokens
        
        if "by_component" not in self.usage:
            self.usage["by_component"] = {}
        
        if component not in self.usage["by_component"]:
            self.usage["by_component"][component] = 0
        
        self.usage["by_component"][component] += tokens
        
        self._save_usage()
    
    def can_use(self, component: str) -> bool:
        """
        检查是否可以使用指定组件
        
        根据降级策略决定：
        - 80%：停止 debater
        - 90%：只保留 scanner
        - 100%：停止所有
        """
        usage_pct = self.get_usage_pct()
        warn_pct = self.config.get("token_budget", {}).get("warn_at_pct", 80)
        stop_pct = self.config.get("token_budget", {}).get("stop_at_pct", 100)
        
        # 100%：停止所有
        if usage_pct >= stop_pct:
            return False
        
        # 90%：只保留 scanner
        if usage_pct >= 90:
            return component == "scanner"
        
        # 80%：停止 debater
        if usage_pct >= warn_pct:
            return component != "debater"
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """获取预算状态"""
        usage_pct = self.get_usage_pct()
        warn_pct = self.config.get("token_budget", {}).get("warn_at_pct", 80)
        stop_pct = self.config.get("token_budget", {}).get("stop_at_pct", 100)
        
        # 确定当前级别
        if usage_pct >= stop_pct:
            level = "STOP"
            description = "已停止所有 Agent"
        elif usage_pct >= 90:
            level = "CRITICAL"
            description = "只保留 Scanner 脚本"
        elif usage_pct >= warn_pct:
            level = "WARNING"
            description = "已停止 Debater Agent"
        else:
            level = "NORMAL"
            description = "正常运行"
        
        return {
            "date": self.usage.get("date"),
            "daily_limit": self.get_daily_limit(),
            "total_usage": self.get_usage(),
            "usage_pct": round(usage_pct, 1),
            "level": level,
            "description": description,
            "by_component": self.usage.get("by_component", {}),
            "thresholds": {
                "warn": f"{warn_pct}% ({int(self.get_daily_limit() * warn_pct / 100):,} token)",
                "stop": f"{stop_pct}% ({int(self.get_daily_limit() * stop_pct / 100):,} token)"
            }
        }


def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Token 预算控制")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # status 命令
    subparsers.add_parser("status", help="查看预算状态")
    
    # record 命令
    record_parser = subparsers.add_parser("record", help="记录 token 使用")
    record_parser.add_argument("--component", required=True, help="组件名称")
    record_parser.add_argument("--tokens", required=True, type=int, help="token 数量")
    
    # check 命令
    check_parser = subparsers.add_parser("check", help="检查是否可以使用组件")
    check_parser.add_argument("--component", required=True, help="组件名称")
    
    args = parser.parse_args()
    
    budget = TokenBudget()
    
    if args.command == "status":
        status = budget.get_status()
        print(f"Token 预算状态")
        print("=" * 50)
        print(f"日期: {status['date']}")
        print(f"每日预算: {status['daily_limit']:,} token")
        print(f"已使用: {status['total_usage']:,} token ({status['usage_pct']}%)")
        print(f"状态级别: {status['level']}")
        print(f"说明: {status['description']}")
        print(f"\n各组件使用:")
        for comp, tokens in status['by_component'].items():
            print(f"  {comp}: {tokens:,} token")
        print(f"\n阈值:")
        print(f"  警告: {status['thresholds']['warn']}")
        print(f"  停止: {status['thresholds']['stop']}")
    
    elif args.command == "record":
        budget.record_usage(args.component, args.tokens)
        print(f"已记录: {args.component} 使用 {args.tokens:,} token")
        print(f"当前总使用: {budget.get_usage():,} token ({budget.get_usage_pct():.1f}%)")
    
    elif args.command == "check":
        can = budget.can_use(args.component)
        print(f"{args.component}: {'可以使用' if can else '已达到预算限制'}")
        print(f"当前使用: {budget.get_usage():,} token ({budget.get_usage_pct():.1f}%)")


if __name__ == "__main__":
    main()
