#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""官方 API 文档镜像：下载 PTrade / 聚宽(JoinQuant) / QMT 接口文档，清洗后存入 kb/。

运行：python products/quant/kb/fetch_docs.py（注意不能用 -m：kb.py 与 kb/ 包同名会遮蔽）

来源（用户提供）：
  PTrade      https://p.mei.biz/             （index 就是全文）
  聚宽 JQ     https://jk.mei.biz/            （index 就是全文，JSON 动态内容已实测抓到）
  QMT         https://qmt.mei.biz/QMT_Python_API_Doc.html

⚠️ 相关站点证书可能已过期（2026-08 实测），下载统一关闭证书校验并打印警告；
   产物是静态文档文本，内容风险低，但请知悉。
产物：kb/ptrade_api.md / kb/joinquant_api.md / kb/qmt_api.md（自动纳入 RAG 检索与微调语料）。

清洗：优先用 bs4（若已安装）；未安装时退回 stdlib 正则兜底，避免强依赖。
"""

from __future__ import annotations

import html
import os
import re
import ssl
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

SOURCES = {
    "ptrade_api.md": [
        ("https://p.mei.biz/", "PTrade API 文档"),
    ],
    "joinquant_api.md": [
        ("https://jk.mei.biz/", "聚宽 JoinQuant API 文档"),
    ],
    "qmt_api.md": [
        ("https://qmt.mei.biz/QMT_Python_API_Doc.html", "QMT Python API 文档"),
    ],
}

KB_DIR = os.path.dirname(os.path.abspath(__file__))
_UA = {"User-Agent": "Mozilla/5.0 (quant-kb doc mirror)"}


def _fetch(url: str) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE          # 站点证书可能过期，见模块 docstring
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        raw = r.read()
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ---- 文本清洗：bs4 优先，stdlib 正则兜底 ----
def _strip_tags(s: str) -> str:
    """去掉注释与标签（只匹配 tag 形态，避免误删 a < b 这类比较符）。"""
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"<[A-Za-z/][^>]*>", " ", s)
    return s


def _code_text(s: str) -> str:
    """pre 块内取代码：保留比较符等 `<`，仅剥离行内格式标签。"""
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)</(div|p|li|pre)>", "\n", s)
    s = re.sub(r"<[A-Za-z/][^>]*>", "", s)
    return html.unescape(s).strip()


def _html_to_text_fallback(html_text: str) -> str:
    """stdlib 兜底：正则取文本，产出粗 markdown，供 RAG 检索。"""
    text = html_text
    text = re.sub(r"(?is)<(script|style|nav|footer|header|svg|aside)[^>]*>.*?</\1>",
                  " ", text)
    # 标题 → markdown 井号
    text = re.sub(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>",
                  lambda m: "\n\n" + "#" * int(m.group(1)) + " "
                  + _strip_tags(m.group(2)).strip() + "\n\n", text)
    # 代码块 → 围栏代码
    text = re.sub(r"(?is)<pre[^>]*>(.*?)</pre>",
                  lambda m: "\n\n```\n" + _code_text(m.group(1)) + "\n```\n\n",
                  text)
    # 块级标签 → 换行，避免整页挤成一行
    text = re.sub(r"(?i)</(p|div|li|tr|td|th|ul|ol|table|h[1-6]|pre|blockquote)>",
                  "\n", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = _strip_tags(text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def html_to_text(html_text: str) -> str:
    """HTML → 粗 markdown：去脚本样式，标题/表格/代码保留结构线索。

    bs4 可用时用它（更准）；否则走 stdlib 正则兜底，避免强依赖。
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return _html_to_text_fallback(html_text)

    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    for h in soup.find_all(re.compile("^h[1-6]$")):
        level = int(h.name[1])
        h.insert_before("\n" + "#" * level + " ")
        h.unwrap()
    for pre in soup.find_all("pre"):
        pre.insert_before("\n```\n")
        pre.insert_after("\n```\n")
    text = soup.get_text("\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def main() -> int:
    print("⚠️  p.mei.biz / jk.mei.biz / qmt.mei.biz 证书可能已过期，本次下载关闭证书校验")
    for out_name, pages in SOURCES.items():
        parts = []
        for url, title in pages:
            print(f"下载 {url} …", flush=True)
            try:
                text = html_to_text(_fetch(url))
            except Exception as e:            # noqa: BLE001
                print(f"  ❌ {type(e).__name__}: {e}")
                continue
            print(f"  ✅ {len(text)} 字符")
            parts.append(f"# {title}\n\n> 镜像自 {url}\n\n{text}")
        if not parts:
            print(f"❌ {out_name} 全部页面下载失败，跳过")
            continue
        out = os.path.join(KB_DIR, out_name)
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n\n---\n\n".join(parts))
        print(f"写入 {out}（{os.path.getsize(out)} 字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
