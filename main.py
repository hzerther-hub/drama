#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local AI Studio 入口。"""

from __future__ import annotations
import sys

# 版本基线：Python 3.12+（新语法与依赖均按 3.12 起）。
# 守卫必须放在 import ui 之前：旧解释器下源码里的新语法会先炸 SyntaxError，
# 用户看不到可读的提示。
if sys.version_info < (3, 12):
    sys.stderr.write(
        "Local AI Studio 需要 Python 3.12+，当前 "
        + str(sys.version_info[0]) + "." + str(sys.version_info[1]) + "。\n"
        "Windows 建议：python -m venv .venv 后用 .venv\\Scripts\\python 运行；\n"
        "系统 Python 过旧时可用 Miniconda 建 3.12 环境再建 venv（详见 README）。\n")
    sys.exit(1)

import ui

if __name__ == "__main__":
    ui.launch()
