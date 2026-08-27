#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""掘金(GoldMiner/MyQuant)官方 Python SDK 接口文档镜像：从 myquant.cn/docs2 抓取。

运行：python products/quant/kb/fetch_myquant.py（勿用 -m，避免与 kb.py 同名遮蔽）

来源：https://www.myquant.cn/docs2/sitemap.xml 中 /docs2/sdk/python/*.html
产物：kb/gm_api.md —— 对齐 kb/qmt_api.md 等，纳入 RAG 检索与微调语料。
清洗复用 fetch_docs.py（未装 bs4 时走 stdlib 正则兜底）。
"""

from __future__ import annotations

import gzip
import importlib.util
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request

KB_DIR = os.path.dirname(os.path.abspath(__file__))
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) quant-kb myquant mirror"}
BASE = "https://www.myquant.cn"

# 复用 fetch_docs.py 的 HTML→Markdown 清洗（按文件路径导入，规避 kb.py 同名遮蔽）
_spec = importlib.util.spec_from_file_location(
    "kb_fetch_docs", os.path.join(KB_DIR, "fetch_docs.py"))
_fd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fd)
html_to_text = _fd.html_to_text


def _fetch(url: str, timeout: int = 60) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE          # 站点证书可能过期，见 fetch_docs docstring
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _sitemap_urls() -> list[str]:
    txt = _fetch(f"{BASE}/docs2/sitemap.xml")
    return re.findall(r"<loc>([^<]+)</loc>", txt)


def _title(url: str) -> str:
    """取 path 最后一节文件名（解码）作标题。"""
    seg = urllib.parse.unquote(url.rstrip("/").rsplit("/", 1)[-1])
    seg = re.sub(r"\.html$", "", seg)
    return seg or "首页"


def main() -> int:
    locs = _sitemap_urls()
    pages = sorted(l for l in locs
                   if "/docs2/sdk/python/" in l and l.endswith(".html"))
    print(f"掘金 Python SDK 页面 {len(pages)} 个")
    parts = ["# 掘金(GoldMiner/MyQuant) Python SDK 接口文档",
             f"> 来源 {BASE}/docs2/ · 自动镜像，仅供本地检索/微调语料\n"]
    ok = 0
    for url in pages:
        title = _title(url)
        print(f"下载 {title} …", flush=True)
        try:
            text = html_to_text(_fetch(url))
        except Exception as e:            # noqa: BLE001
            print(f"  ❌ {type(e).__name__}: {e}")
            continue
        if len(text) < 40:
            print(f"  ⚠️ 内容过短({len(text)} 字符)，跳过")
            continue
        parts.append(f"## {title}\n\n> {url}\n\n{text}")
        ok += 1
    out = os.path.join(KB_DIR, "gm_api.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(parts))
    print(f"成功 {ok}/{len(pages)} → {out}（{os.path.getsize(out)} 字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
