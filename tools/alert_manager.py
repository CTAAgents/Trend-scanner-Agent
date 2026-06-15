#!/usr/bin/env python3
"""
告警管理器

功能：
1. 监控系统状态
2. 检测异常情况
3. 发送告警通知
4. 记录告警历史

告警级别：
- INFO: 信息通知
- WARNING: 警告
- ERROR: 错误
- CRITICAL: 严重错误

使用方式：
    python tools/alert_manager.py --check
    python tools/alert_manager.py --history
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


class AlertLevel:
    """告警级别"""
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


class AlertManager:
    """告警管理器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化告警管理器
        
        Args:
            db_path: 告警数据库路径
        """
        self.db_path = db_path or str(Path(__file__).parent.parent / 'data' / 'alerts.db')
        self._init_db()
    
    def _init_db(self):
        """初始化告警数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            details TEXT,
            status TEXT DEFAULT 'active',
            resolved_at TEXT,
            resolved_by TEXT
        )
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_level ON alerts(level)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)
        """)
        
        conn.commit()
        conn.close()
    
    def create_alert(
        self,
        level: str,
        category: str,
        title: str,
        message: str = None,
        details: Dict = None
    ) -> str:
        """
        创建告警
        
        Args:
            level: 告警级别
            category: 告警类别
            title: 告警标题
            message: 告警消息
            details: 详细信息
        
        Returns:
            告警 ID
        """
        alert_id = f"ALERT_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{level}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO alerts (alert_id, timestamp, level, category, title, message, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            alert_id,
            datetime.now().isoformat(),
            level,
            category,
            title,
            message,
            json.dumps(details or {}, ensure_ascii=False)
        ))
        
        conn.commit()
        conn.close()
        
        return alert_id
    
    def get_active_alerts(self, level: str = None) -> List[Dict[str, Any]]:
        """
        获取活跃告警
        
        Args:
            level: 过滤告警级别
        
        Returns:
            告警列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if level:
            cursor.execute("""
            SELECT * FROM alerts 
            WHERE status = 'active' AND level = ?
            ORDER BY timestamp DESC
            """, (level,))
        else:
            cursor.execute("""
            SELECT * FROM alerts 
            WHERE status = 'active'
            ORDER BY timestamp DESC
            """)
        
        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # 解析 details JSON
        for alert in alerts:
            if alert.get('details'):
                try:
                    alert['details'] = json.loads(alert['details'])
                except:
                    pass
        
        return alerts
    
    def get_alert_history(self, days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取告警历史
        
        Args:
            days: 查询天数
            limit: 返回数量限制
        
        Returns:
            告警列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
        SELECT * FROM alerts 
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT ?
        """, (cutoff, limit))
        
        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # 解析 details JSON
        for alert in alerts:
            if alert.get('details'):
                try:
                    alert['details'] = json.loads(alert['details'])
                except:
                    pass
        
        return alerts
    
    def resolve_alert(self, alert_id: str, resolved_by: str = 'system'):
        """
        解决告警
        
        Args:
            alert_id: 告警 ID
            resolved_by: 解决者
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        UPDATE alerts 
        SET status = 'resolved', resolved_at = ?, resolved_by = ?
        WHERE alert_id = ?
        """, (datetime.now().isoformat(), resolved_by, alert_id))
        
        conn.commit()
        conn.close()
    
    def check_and_alert(self):
        """检查系统状态并生成告警"""
        # 导入健康检查器
        from health_check import HealthChecker
        
        checker = HealthChecker()
        results = checker.check_all()
        
        # 检查各项状态
        for check_name, check_result in results.get('checks', {}).items():
            status = check_result.get('status', 'OK')
            
            if status == 'ERROR':
                self.create_alert(
                    level=AlertLevel.ERROR,
                    category=check_name,
                    title=f'{check_name} 检查失败',
                    message=f'{check_name} 状态异常: ERROR',
                    details=check_result
                )
            elif status == 'WARNING':
                self.create_alert(
                    level=AlertLevel.WARNING,
                    category=check_name,
                    title=f'{check_name} 警告',
                    message=f'{check_name} 状态异常: WARNING',
                    details=check_result
                )
        
        # 检查磁盘空间
        disk_check = results.get('checks', {}).get('disk', {})
        if disk_check.get('details', {}).get('percent', 0) > 90:
            self.create_alert(
                level=AlertLevel.WARNING,
                category='disk',
                title='磁盘空间不足',
                message=f"磁盘使用率: {disk_check['details']['percent']}%",
                details=disk_check
            )
        
        # 检查内存使用
        memory_check = results.get('checks', {}).get('memory', {})
        if memory_check.get('details', {}).get('percent', 0) > 80:
            self.create_alert(
                level=AlertLevel.WARNING,
                category='memory',
                title='内存使用率过高',
                message=f"内存使用率: {memory_check['details']['percent']}%",
                details=memory_check
            )
        
        return results


def print_alerts(alerts: List[Dict[str, Any]]):
    """打印告警列表"""
    level_colors = {
        'INFO': '\033[94m',      # 蓝色
        'WARNING': '\033[93m',   # 黄色
        'ERROR': '\033[91m',     # 红色
        'CRITICAL': '\033[95m',  # 紫色
    }
    reset_color = '\033[0m'
    
    if not alerts:
        print("没有告警")
        return
    
    print("\n" + "=" * 80)
    print(f"{'时间':<20} {'级别':<10} {'类别':<15} {'标题':<30}")
    print("=" * 80)
    
    for alert in alerts:
        timestamp = alert.get('timestamp', '')[:19]
        level = alert.get('level', '')
        category = alert.get('category', '')
        title = alert.get('title', '')
        
        color = level_colors.get(level, '')
        print(f"{timestamp:<20} {color}{level:<10}{reset_color} {category:<15} {title:<30}")
    
    print("=" * 80)
    print(f"共 {len(alerts)} 条告警")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='告警管理器')
    parser.add_argument('--check', action='store_true', help='检查系统状态并生成告警')
    parser.add_argument('--active', action='store_true', help='显示活跃告警')
    parser.add_argument('--history', action='store_true', help='显示告警历史')
    parser.add_argument('--days', type=int, default=7, help='历史天数')
    parser.add_argument('--resolve', type=str, help='解决指定告警')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')
    
    args = parser.parse_args()
    
    manager = AlertManager()
    
    if args.check:
        print("检查系统状态...")
        results = manager.check_and_alert()
        print("检查完成")
        
        # 显示新生成的告警
        active_alerts = manager.get_active_alerts()
        if active_alerts:
            print(f"\n发现 {len(active_alerts)} 条活跃告警:")
            print_alerts(active_alerts)
        else:
            print("\n没有活跃告警")
    
    elif args.active:
        alerts = manager.get_active_alerts()
        if args.json:
            print(json.dumps(alerts, ensure_ascii=False, indent=2))
        else:
            print_alerts(alerts)
    
    elif args.history:
        alerts = manager.get_alert_history(days=args.days)
        if args.json:
            print(json.dumps(alerts, ensure_ascii=False, indent=2))
        else:
            print_alerts(alerts)
    
    elif args.resolve:
        manager.resolve_alert(args.resolve)
        print(f"告警 {args.resolve} 已解决")
    
    else:
        # 默认显示活跃告警
        alerts = manager.get_active_alerts()
        if args.json:
            print(json.dumps(alerts, ensure_ascii=False, indent=2))
        else:
            print_alerts(alerts)


if __name__ == '__main__':
    main()
