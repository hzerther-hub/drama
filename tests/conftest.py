# -*- coding: utf-8 -*-
"""pytest 全局准备：隔离用户配置目录 + 项目导入路径。

必须在任何项目模块导入前执行（pytest 会先加载 conftest）：
把 HOME / USERPROFILE / APPDATA 重定向到临时目录，测试就不会读写
真实用户配置（config.py 在 import 时解析一次配置目录）。

同时清除 LOCAL_AI_PRODUCT：开发机上若设置了产品环境变量（如 quant，
zh_only 强制中文），会让语言相关测试误判失败；测试默认跑 devtool_local，
需要指定产品的用例自行 monkeypatch.setenv（见 test_products.py）。
"""

import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="local-ai-studio-test-")
os.environ["HOME"] = _TMP
os.environ["USERPROFILE"] = _TMP                       # Windows expanduser 用它
os.environ["APPDATA"] = os.path.join(_TMP, "AppData", "Roaming")
os.environ.pop("LOCAL_AI_PRODUCT", None)               # 隔离产品选择，防 zh_only 污染

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
