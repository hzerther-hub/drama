# -*- coding: utf-8 -*-
"""产品 profile 机制：单内核多产品。

core（仓库根目录的扁平模块：agent/llm/tools/ui/gpulocal…）是共享内核；
products/<name>/profile.json 定义一个产品的品牌与功能开关：
  - novelwriter    短剧剧本 + 网文创作（默认产品 = 本仓库主产品）
  - devtool        纯云端开发工具（开发内核的附带产物）
  - devtool_local  本地模型省 token 开发工具
  - quant          量化开发工具（本地模型 + 平台适配器，见 quant/README）
  - devrag         企业多仓库 + 文档 RAG 开发平台（见 devrag/README）

运行本仓库主产品（novelwriter）：
    python main.py                                  # 默认即短剧网文创作
    LOCAL_AI_PRODUCT=novelwriter python3 main.py    # 显式指定
    python3 products/novelwriter/run.py             # 或直接走产品入口

功能开关（features，缺省 true）由 ui.py / agent.py 在功能入口处查询：
    import products
    if products.feature("gpulocal"): ...
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

DEFAULT_PRODUCT = "novelwriter"
ENV_KEY = "LOCAL_AI_PRODUCT"

KNOWN_FEATURES = ("gpulocal", "dispatch", "editor", "voice", "mcp",
                  "attachments", "sessions", "quant", "rag", "zh_only")


@dataclass
class Profile:
    name: str
    title: str
    features: dict = field(default_factory=dict)
    exe_name: str = ""                # PyInstaller 产物名（profile.json 的 exe_name）

    def feature(self, key: str, default: bool = True) -> bool:
        return bool(self.features.get(key, default))


def products_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def list_products() -> list[str]:
    """返回所有合法产品名（含 profile.json 的子目录）。"""
    out = []
    for name in sorted(os.listdir(products_dir())):
        if os.path.isfile(os.path.join(products_dir(), name, "profile.json")):
            out.append(name)
    return out


def load_profile(name: str | None = None) -> Profile:
    """加载产品 profile；未指定时读环境变量，再回退默认产品。"""
    name = (name or os.environ.get(ENV_KEY) or DEFAULT_PRODUCT).strip()
    path = os.path.join(products_dir(), name, "profile.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"未知产品 {name!r}（可用：{', '.join(list_products())}）")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Profile(name=name,
                   title=str(data.get("title", name)),
                   features=dict(data.get("features", {})),
                   exe_name=str(data.get("exe_name", "")))


_ACTIVE: Profile | None = None


def active() -> Profile:
    """当前进程的激活 profile（惰性加载一次）。"""
    global _ACTIVE
    if _ACTIVE is None:
        _ACTIVE = load_profile()
    return _ACTIVE


def feature(key: str, default: bool = True) -> bool:
    return active().feature(key, default)


def _reset_for_test():
    global _ACTIVE
    _ACTIVE = None
