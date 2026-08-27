#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产品入口模板：设置激活产品后进入共享内核 UI。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
os.environ.setdefault("LOCAL_AI_PRODUCT",
                      os.path.basename(os.path.dirname(os.path.abspath(__file__))))

import ui  # noqa: E402

if __name__ == "__main__":
    ui.launch()
