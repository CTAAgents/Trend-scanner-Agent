#!/usr/bin/env python3
"""
文件监控自动 Git 推送脚本

使用 watchdog 监控文件变化，自动执行 git add + commit + push。
设置防抖机制避免频繁提交。

用法：
    python tools/auto_git_push.py [--debounce 5] [--branch main]
"""

import os
import sys
import time
import argparse
import subprocess
import threading
from pathlib import Path
from datetime import datetime

# 设置标准输出编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print("错误：需要安装 watchdog 库")
    print("请运行：pip install watchdog")
    sys.exit(1)


class GitAutoPushHandler(FileSystemEventHandler):
    """文件变化处理器，自动执行 git 操作"""
    
    def __init__(self, repo_path: str, debounce_seconds: int = 5, branch: str = "main"):
        """
        初始化处理器
        
        Args:
            repo_path: Git 仓库根目录
            debounce_seconds: 防抖时间（秒）
            branch: 推送的分支名
        """
        self.repo_path = Path(repo_path).resolve()
        self.debounce_seconds = debounce_seconds
        self.branch = branch
        self._pending_changes = False
        self._timer = None
        self._lock = threading.Lock()
        self._git_lock = threading.Lock()
        
        # 忽略的目录模式
        self.ignore_patterns = {
            '.git',
            '__pycache__',
            '.pyc',
            '.pyo',
            '.egg-info',
            'dist',
            'build',
            'venv',
            '.vscode',
            '.idea',
            '.DS_Store',
            'Thumbs.db',
            'data',  # 运行时数据目录
            '.workbuddy',  # WorkBuddy 内部目录
        }
    
    def _should_ignore(self, path: str) -> bool:
        """检查路径是否应该被忽略"""
        path_parts = Path(path).parts
        for part in path_parts:
            if part in self.ignore_patterns:
                return True
            if part.endswith('.pyc') or part.endswith('.pyo'):
                return True
        return False
    
    def on_any_event(self, event: FileSystemEvent):
        """处理任何文件系统事件"""
        if event.is_directory:
            return
        
        src_path = event.src_path
        if self._should_ignore(src_path):
            return
        
        # 转换为相对路径
        try:
            rel_path = Path(src_path).relative_to(self.repo_path)
        except ValueError:
            return
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 检测到变化: {rel_path}")
        
        with self._lock:
            self._pending_changes = True
            # 重置定时器
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._do_git_push)
            self._timer.daemon = True
            self._timer.start()
    
    def _do_git_push(self):
        """执行 git add + commit + push"""
        with self._git_lock:
            if not self._pending_changes:
                return
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始执行 git 操作...")
            
            try:
                # 检查是否有实际变化
                result = subprocess.run(
                    ['git', 'status', '--porcelain'],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if not result.stdout.strip():
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 没有实际变化，跳过提交")
                    self._pending_changes = False
                    return
                
                # git add
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 执行 git add...")
                result = subprocess.run(
                    ['git', 'add', '-A'],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    print(f"git add 失败: {result.stderr}")
                    return
                
                # 生成提交信息
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                commit_msg = f"auto: 文件变化自动提交 ({timestamp})"
                
                # git commit
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 执行 git commit...")
                result = subprocess.run(
                    ['git', 'commit', '-m', commit_msg],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    if 'nothing to commit' in result.stdout:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 没有需要提交的内容")
                    else:
                        print(f"git commit 失败: {result.stderr}")
                    return
                
                # git push
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 执行 git push...")
                result = subprocess.run(
                    ['git', 'push', 'origin', self.branch],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    print(f"git push 失败: {result.stderr}")
                    # 尝试强制推送（仅在非 main 分支时）
                    if self.branch != 'main':
                        print(f"尝试强制推送...")
                        result = subprocess.run(
                            ['git', 'push', '--force-with-lease', 'origin', self.branch],
                            cwd=self.repo_path,
                            capture_output=True,
                            text=True,
                            timeout=60
                        )
                        if result.returncode != 0:
                            print(f"强制推送也失败: {result.stderr}")
                            return
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [成功] 自动推送成功")
                
            except subprocess.TimeoutExpired:
                print("git 操作超时")
            except Exception as e:
                print(f"git 操作异常: {e}")
            finally:
                self._pending_changes = False


def main():
    try:
        parser = argparse.ArgumentParser(description='文件监控自动 Git 推送')
        parser.add_argument('--debounce', type=int, default=5, help='防抖时间（秒），默认 5 秒')
        parser.add_argument('--branch', type=str, default='main', help='推送的分支名，默认 main')
        parser.add_argument('--path', type=str, default=None, help='监控的目录路径，默认当前目录')
        
        args = parser.parse_args()
        
        print(f"[DEBUG] Args: debounce={args.debounce}, branch={args.branch}, path={args.path}")
    except Exception as e:
        print(f"[错误] 参数解析失败: {e}")
        sys.exit(1)
    
    # 确定监控路径
    if args.path:
        repo_path = Path(args.path).resolve()
    else:
        repo_path = Path(__file__).parent.parent.resolve()
    
    # 验证是否为 git 仓库
    git_dir = repo_path / '.git'
    if not git_dir.exists():
        print(f"错误：{repo_path} 不是 git 仓库")
        sys.exit(1)
    
    print(f"[启动] 文件监控自动 Git 推送")
    print(f"   监控目录: {repo_path}")
    print(f"   推送分支: {args.branch}")
    print(f"   防抖时间: {args.debounce} 秒")
    print(f"   按 Ctrl+C 停止")
    print()
    
    # 创建事件处理器和观察者
    handler = GitAutoPushHandler(
        repo_path=str(repo_path),
        debounce_seconds=args.debounce,
        branch=args.branch
    )
    observer = Observer()
    observer.schedule(handler, str(repo_path), recursive=True)
    
    # 启动监控
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[停止] 停止文件监控...")
        observer.stop()
    
    observer.join()
    print("[完成] 文件监控已停止")


if __name__ == '__main__':
    print("[调试] 进入 main 函数")
    main()
