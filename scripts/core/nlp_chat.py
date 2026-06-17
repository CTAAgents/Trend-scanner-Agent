#!/usr/bin/env python3
"""
自然语言交互 CLI

允许用户通过自然语言与系统交互：
- 查询信号
- 执行操作
- 查看状态
- 获取帮助

用法：
    python scripts/core/nlp_chat.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from core.nlp import NLPEngine
from core.nlp.intent_recognizer import IntentType


def show_thinking(step: str, detail: str = ""):
    """显示思考过程"""
    print(f"  [{step}] {detail}")


def main():
    """主函数"""
    print("=" * 60)
    print("Trend Scanner Agent - 自然语言交互")
    print("=" * 60)
    print("输入自然语言指令，系统会自动识别并执行。")
    print("输入 'help' 查看帮助，输入 'quit' 退出。")
    print("=" * 60)
    print()

    engine = NLPEngine()

    while True:
        try:
            # 获取用户输入
            user_input = input("您: ").strip()

            # 检查退出命令
            if user_input.lower() in ["quit", "exit", "q", "退出"]:
                print("再见！")
                break

            # 检查空输入
            if not user_input:
                continue

            print()  # 空行

            # 1. 显示正在思考
            show_thinking("思考", "正在理解您的意图...")

            # 2. 识别意图
            intent = engine.intent_recognizer.recognize(user_input)
            show_thinking("识别", f"意图类型: {intent.intent_type.value}, 动作: {intent.action}")

            if intent.parameters:
                show_thinking("参数", f"提取到的参数: {intent.parameters}")

            # 3. 解析命令
            command = engine.command_parser.parse(intent)
            if command:
                show_thinking("解析", f"执行命令: {command.command}")
                show_thinking("命令", f"参数: {' '.join(command.args)}")
            else:
                show_thinking("解析", "未找到匹配的命令，将使用默认处理")

            print()  # 空行

            # 4. 处理自然语言
            show_thinking("执行", "正在执行...")
            response = engine.process(user_input)

            # 5. 显示响应
            print()
            print(f"系统: {response}")
            print()

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"错误: {e}")
            print()


if __name__ == "__main__":
    main()
