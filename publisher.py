# -*- coding: utf-8 -*-
"""发布与导出：封面生成 + 多格式导出 + 多渠道发布（纯 stdlib）。

渠道矩阵：
- txt        番茄/起点等国内平台：官方作家后台「导入 TXT」直接可用
- md         完整 Markdown 书稿
- epub       Apple Books / Google Play 图书 / 各阅读器
- html       Webnovel / Royal Road / ScribbleHub 后台粘贴即用
- wattpad    海外直发（实验性）：Wattpad v3 API，需 LAS_PUBLISH_WATTPAD_TOKEN
- webhook    海外自动化中转：章节 JSON POST 到 LAS_PUBLISH_WEBHOOK_URL
             （对接 n8n / Zapier / 自建发布脚本，覆盖无公开 API 的平台）
封面：LAS_IMAGE_* 图像服务生成（见 imggen.py）

环境变量：
- LAS_PUBLISH_WATTPAD_TOKEN  Wattpad OAuth2 用户 Token
- LAS_PUBLISH_WEBHOOK_URL    接收 {title, chapters:[{idx,title,text}]} 的 URL
"""

from __future__ import annotations

import json
import os
import urllib.request
import zipfile

import imggen


class PublishError(Exception):
    pass


# ---------------- 配置 ----------------

def wattpad_token() -> str:
    return os.environ.get("LAS_PUBLISH_WATTPAD_TOKEN", "").strip()


def webhook_url() -> str:
    return os.environ.get("LAS_PUBLISH_WEBHOOK_URL", "").strip()


# ---------------- 封面 ----------------

def cover(state: dict, out_path: str = "") -> str:
    """生成书封：标题 + 题材 + 简介融合成图像提示词，走图像服务。"""
    prompt = (f"小说封面设计，竖版 {imggen.default_size()}。"
              f"书名「{state['idea'][:20]}」。"
              f"题材氛围：{state.get('genre', state['idea'][:20])}。"
              f"{state.get('framing', '')[:160]} "
              "风格：高对比度、电影感构图、书名文字清晰可读、无水印。")
    out = out_path or _book_sibling(state, "-封面.png")
    return imggen.generate(prompt, out)


# ---------------- 导出 ----------------

def export_txt(state: dict, path: str = "") -> str:
    """纯文本（番茄/起点作家后台导入格式：章节标题行 + 空行正文）。"""
    out = path or _book_sibling(state, ".txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(_book_title(state) + "\n\n")
        if state.get("framing"):
            f.write("简介：" + _first_line(state["framing"]) + "\n\n")
        for c in state.get("chapters", []):
            f.write(c["title"] + "\n\n" + c["text"] + "\n\n")
    return out


def export_md(state: dict, path: str = "") -> str:
    """完整 Markdown 书稿：规划 + 全部章节合并成单文件（便于分发）。"""
    out = path or _book_sibling(state, "-完整.md")
    parts = []
    plan = state.get("file")
    if plan and os.path.exists(plan):
        with open(plan, encoding="utf-8") as f:
            parts.append(f.read().rstrip())
    for c in state.get("chapters", []):
        parts.append(f"\n\n## {c['title']}\n\n{c['text']}")
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(parts) + "\n")
    return out


def export_html(state: dict, path: str = "") -> str:
    """单文件网页：海外平台后台可直接粘贴各章节。"""
    out = path or _book_sibling(state, ".html")
    body = [f"<h1>{_esc(_book_title(state))}</h1>"]
    for c in state.get("chapters", []):
        body.append(f"<h2>{_esc(c['title'])}</h2>")
        for para in c["text"].splitlines():
            if para.strip():
                body.append(f"<p>{_esc(para.strip())}</p>")
    html = ("<!doctype html><meta charset='utf-8'>"
            "<title>" + _esc(_book_title(state)) + "</title>"
            "<body>" + "\n".join(body) + "</body>")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


def export_epub(state: dict, path: str = "") -> str:
    """EPUB3（stdlib zipfile 构建，Apple Books/Google Play/阅读器通用）。"""
    out = path or _book_sibling(state, ".epub")
    title = _book_title(state)
    chapters = state.get("chapters", [])
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   "<?xml version='1.0'?><container version='1.0' "
                   "xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>"
                   "<rootfiles><rootfile full-path='OEBPS/content.opf' "
                   "media-type='application/oebps-package+xml'/></rootfiles>"
                   "</container>")
        manifest = "".join(
            f"<item id='c{i}' href='c{i}.xhtml' "
            "media-type='application/xhtml+xml'/>"
            for i in range(1, len(chapters) + 1))
        spine = "".join(f"<itemref idref='c{i}'/>"
                        for i in range(1, len(chapters) + 1))
        z.writestr("OEBPS/content.opf",
                   "<?xml version='1.0' encoding='utf-8'?>"
                   "<package xmlns='http://www.idpf.org/2007/opf' version='3.0' "
                   "unique-identifier='bid'><metadata "
                   "xmlns:dc='http://purl.org/dc/elements/1.1/'>"
                   f"<dc:title>{_esc(title)}</dc:title>"
                   "<dc:language>zh</dc:language>"
                   "<dc:identifier id='bid'>urn:uuid:"
                   + state.get("pid", "novel") + "</dc:identifier>"
                   "</metadata><manifest>" + manifest + "</manifest>"
                   "<spine>" + spine + "</spine></package>")
        for c in chapters:
            paras = "".join(f"<p>{_esc(p.strip())}</p>"
                            for p in c["text"].splitlines() if p.strip())
            z.writestr(f"OEBPS/c{c['idx']}.xhtml",
                       "<?xml version='1.0' encoding='utf-8'?>"
                       "<html xmlns='http://www.w3.org/1999/xhtml'><head><title>"
                       + _esc(c["title"]) + "</title></head><body><h2>"
                       + _esc(c["title"]) + "</h2>" + paras + "</body></html>")
    return out


# ---------------- 渠道发布 ----------------

def publish_wattpad(state: dict, ch_start: int, ch_end: int) -> str:
    """Wattpad 直发（实验性）：创建/复用作品并逐章添加。需配置 Token。"""
    if not wattpad_token():
        raise PublishError("未配置 Wattpad Token（LAS_PUBLISH_WATTPAD_TOKEN）")
    chapters = [c for c in state.get("chapters", [])
                if ch_start <= c["idx"] <= ch_end]
    if not chapters:
        raise PublishError("所选范围没有已完成章节")
    story = _req("POST", "https://www.wattpad.com/api/v3/stories",
                 {"title": _book_title(state)[:100],
                  "description": _first_line(state.get("framing", ""))[:400]})
    sid = story.get("id")
    for c in chapters:
        _req("POST", f"https://www.wattpad.com/api/v3/stories/{sid}/parts",
             {"title": c["title"][:100], "text": c["text"]})
    return f"https://www.wattpad.com/story/{sid}（{len(chapters)} 章）"


def publish_webhook(state: dict, ch_start: int, ch_end: int) -> str:
    """Webhook 中转：把章节 JSON 推给自动化脚本（n8n/Zapier/自建）。"""
    if not webhook_url():
        raise PublishError("未配置 Webhook（LAS_PUBLISH_WEBHOOK_URL）")
    chapters = [c for c in state.get("chapters", [])
                if ch_start <= c["idx"] <= ch_end]
    if not chapters:
        raise PublishError("所选范围没有已完成章节")
    body = {"title": _book_title(state),
            "chapters": [{"idx": c["idx"], "title": c["title"],
                          "text": c["text"]} for c in chapters]}
    _req("POST", webhook_url(), body)
    return f"已推送 {len(chapters)} 章 → {webhook_url()}"


def _req(method: str, url: str, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 method=method)
    req.add_header("Content-Type", "application/json")
    token = wattpad_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except Exception as e:             # noqa: BLE001
        raise PublishError(f"发布请求失败：{e}") from e


# ---------------- 小工具 ----------------

def _book_sibling(state: dict, suffix: str) -> str:
    """导出物放在本书目录下，用书名命名（书稿已改为目录布局）。"""
    d = state.get("dir")
    if not d:
        f = state.get("file") or "novel.md"
        d = os.path.dirname(f) or "."
    base = _book_title(state) or state.get("pid") or "novel"
    return os.path.join(d, _safe_filename(base) + suffix)


def _safe_filename(name: str) -> str:
    """清洗为合法文件名（去 Windows 非法字符）。"""
    import re
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", (name or "").strip())
    return name.strip(" .")[:40] or "novel"


def _book_title(state: dict) -> str:
    """书名：优先取大纲首行里的《书名》，否则用灵感句前 40 字。"""
    import re
    first = ""
    if state.get("outline"):
        first = state["outline"].splitlines()[0].strip()
    m = re.search(r"《(.+?)》", first)
    if m:
        return m.group(1)[:40]
    return (first or state.get("idea", ""))[:40]


def _first_line(text: str) -> str:
    return (text or "").splitlines()[0].strip()[:120] if text else ""


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
