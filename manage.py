#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "无法导入 Django。请确认以下事项：\n"
            "1. Django 已安装（运行：pip install django）\n"
            "2. 虚拟环境已激活（运行：.venv\\Scripts\\activate）\n"
            "3. 所有依赖已安装（运行：pip install -r requirements.txt）"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()