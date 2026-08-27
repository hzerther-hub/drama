# -*- coding: utf-8 -*-
"""消息里的链接自动取材：图片链接 → 下载识图；网页链接 → 抓正文给模型。

开发/聊天中直接把 URL 粘进输入框发送即可：
- Content-Type 为 image/* → 下载到 media/ 目录，走附件识图管线
  （需当前模型 vision: true，门控与普通图片附件一致）；
- text/html 网页 → 抓取页面，去脚本/样式后提取纯文本，截断拼进
  消息正文（模型直接可读，无需再调 web_search）；
- 其它类型（json/pdf/zip…）→ 下载到 media/ 并附路径说明，交给
  模型用工具处理。

仅标准库；抓取失败不阻断发送，以中文注释形式附在消息里。
多条链接并发抓取（上限 MAX_WORKERS），缩短等待时间。
"""

from __future__ import annotations

import gzip
import hashlib
import html as html_mod
import os
import re
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple

import config

# 一条消息最多自动取材的链接数（防误粘一堆链接卡界面）
MAX_LINKS = 8
# 单个请求超时（秒）
TIMEOUT = 12
# 网页正文最大保留字符数
TEXT_LIMIT = 6000
# 网页标题最大保留字符数（防超长 <title> 刷屏）
TITLE_LIMIT = 120
# 单个响应最大下载字节数（防超大文件撑爆内存；超过视为失败）
MAX_BYTES = 50 * 1024 * 1024
_MAX_MB = MAX_BYTES / 1048576
# 并发抓取链接的最大线程数
MAX_WORKERS = 4
# 报错信息最大展示长度（避免超长 URL / 异常刷屏）
ERR_LIMIT = 160

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 链接末尾可能粘连的字符：英文引号/全角引号/各类收尾标点一律不进 URL，
# 否则粘贴「“https://… ”」或「（https://…）」时会把引号/括号收进链接
_URL_RE = re.compile(
    r"https?://[^\s<>\"'“”‘’「」『』《》【】（）)\]}，。、；！？]+")
# 正则未覆盖的尾随字符（额外兜底剥掉）
_URL_TRAILING = ".,;:!?)）】》"

# Content-Type → 扩展名（图片走识图；其余落盘给工具处理）
_CT_EXT = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
    "image/webp": ".webp", "image/bmp": ".bmp", "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico", "image/tiff": ".tiff",
    "image/avif": ".avif", "image/heif": ".heif", "image/heic": ".heic",
}

# 可安全走 Pillow 标准化的图片扩展
_IMG_EXTS = set(_CT_EXT.values())

# 非图片内容：从 URL 路径里可接受的扩展名（字母/数字，1~5 字符）
_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$")

# HTML 处理正则（预编译，避免每次抓取重复编译）
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_BODY_RE = re.compile(r"<body[^>]*>(.*)</body>", re.S | re.I)
_HEAD_RE = re.compile(r"<head[^>]*>.*</head>", re.S | re.I)
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_BLOCK_RE = re.compile(
    r"</?(p|div|br|li|tr|td|th|h[1-6]|section|article)[^>]*>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
# 压空白：普通空格/制表/换页 + NBSP（&nbsp;）与全角空格
_WS_RE = re.compile(r"[ \t\r\f\v\u00a0\u3000]+")
_NEWLINE_RE = re.compile(r"\n\s*\n+")
# HTML 字节里的 <meta charset=…> 声明
_CHARSET_RE = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?\s*([\w-]+)", re.I)
# Content-Type 字符串里的 charset=…（str 版，供 _decode 使用）
_CT_CHARSET_RE = re.compile(r"charset\s*=\s*[\"']?\s*([\w-]+)", re.I)


def _err(e: BaseException) -> str:
    """异常信息截断并压成单行，避免超长报错刷屏。"""
    s = " ".join(str(e).split())
    return s if len(s) <= ERR_LIMIT else s[:ERR_LIMIT] + "…"


def _mime_type(ct: str) -> str:
    """Content-Type → 纯 MIME（去掉 ;charset=… 等参数）。"""
    return (ct or "").split(";")[0].strip().lower()


def _path_ext(url: str) -> str:
    """URL 路径的扩展名（小写，无则空串）。"""
    return os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()


def find_urls(text: str) -> list[str]:
    """提取消息里的 http(s) 链接（去重、限量）。"""
    seen, urls = set(), []
    for u in _URL_RE.findall(text or ""):
        u = u.rstrip(_URL_TRAILING)
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls[:MAX_LINKS]


def _decompress(data: bytes, encoding: str) -> bytes:
    """按 Content-Encoding 解压；失败退回原始字节（当作未压缩）。"""
    try:
        if encoding == "gzip":
            return gzip.decompress(data)
        if encoding == "deflate":
            try:
                return zlib.decompress(data)
            except zlib.error:
                return zlib.decompress(data, -zlib.MAX_WBITS)  # 无 zlib 头的 raw deflate
    except Exception:  # noqa: BLE001
        pass
    return data


def _fetch(url: str) -> tuple[str, bytes]:
    """GET 一个 URL，返回 (Content-Type 原文, bytes)；失败或超大抛异常。

    返回原文（保留 ;charset= 等参数），供解码阶段提取字符集；
    显式声明 gzip/deflate 并解压（不少站点强制压缩，否则正文是乱码）。
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,"
                   "*/*;q=0.5"),
        "Accept-Encoding": "gzip, deflate",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw_ct = r.headers.get("Content-Type") or ""
        data = r.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("内容过大（>%.0f MB），跳过下载" % _MAX_MB)
        enc = (r.headers.get("Content-Encoding") or "").strip().lower()
        if enc:
            data = _decompress(data, enc)
            if len(data) > MAX_BYTES:
                raise ValueError("解压后内容过大（>%.0f MB），跳过下载" % _MAX_MB)
        return raw_ct, data


def _save_media(ct: str, data: bytes, url: str) -> str:
    """按内容类型落盘到 media/，返回路径。ct 须为纯 MIME（已小写、去参数）。"""
    ext = _CT_EXT.get(ct)
    if ext is None:
        # 非图片：从 URL 猜扩展名（小写化，兼容 .PNG/.JPG 大写写法）；
        # 无/非法扩展名兜底 .bin
        path_ext = _path_ext(url)
        ext = path_ext if _EXT_RE.fullmatch(path_ext) else ".bin"
    name = "link-" + hashlib.sha1(url.encode()).hexdigest()[:12] + ext
    os.makedirs(config.MEDIA_DIR, exist_ok=True)
    path = os.path.join(config.MEDIA_DIR, name)
    with open(path, "wb") as f:
        f.write(data)
    # 图片统一标准化：llama.cpp（stb_image）与 Tk 原生只认 PNG/JPEG，
    # webp/avif/ico 等会 400 或显示失败 → 用 Pillow 转成 PNG/JPEG 落盘
    if ext in _IMG_EXTS:
        normalized = _normalize_image(path)
        if normalized:
            path = normalized
    return path


def _normalize_image(path: str) -> str | None:
    """把图片转成模型/UI 都能读的 PNG（带透明）或 JPEG（照片）。

    成功返回新路径（同目录，改扩展名），失败或无需转换返回 None
    （保留原文件）。已是标准 PNG/JPEG 的无动画图片直接保留，避免
    二次编码造成质量损失。
    """
    try:
        from PIL import Image
    except Exception:                    # noqa: BLE001  Pillow 缺失 → 保留原文件
        return None
    ext = os.path.splitext(path)[1].lower()
    out = path
    same = False
    tmp = path
    try:
        with Image.open(path) as img:
            animated = getattr(img, "is_animated", False)
            if animated:
                img.seek(0)             # 只取第一帧
            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info)
            # 已是标准格式且无需转帧/转透明 → 保留原文件（不整图解码）
            if not animated and (
                (has_alpha and ext == ".png" and img.mode == "RGBA")
                or (not has_alpha and ext in (".jpg", ".jpeg", ".png"))
            ):
                return None
            if has_alpha:
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                fmt, new_ext = "PNG", ".png"
            else:
                img = img.convert("RGB")
                fmt, new_ext = "JPEG", ".jpg"
            out = os.path.splitext(path)[0] + new_ext
            # 目标与源同路径（如 8 位调色板 PNG 转 RGBA）时，原文件句柄仍被
            # with 持有，Windows 上直接覆盖会失败 → 先写临时文件，with 结束
            # 释放句柄后再原子替换。
            same = os.path.abspath(out) == os.path.abspath(path)
            tmp = out + ".tmp" if same else out
            img.save(tmp, format=fmt)
    except Exception:                    # noqa: BLE001
        return None
    if same:
        try:
            os.replace(tmp, out)
        except OSError:
            return None
    else:
        # with 已释放原文件句柄，可安全删除旧格式文件；删不掉也无妨（新文件已生成）
        try:
            os.remove(path)
        except OSError:
            pass
    return out


def _decode(data: bytes, ct: str) -> str:
    """把 HTML 字节按编码解码：BOM → Content-Type charset → meta 声明 → UTF-8 兜底。"""
    # BOM 优先（utf-16 解码会自动剥离 BOM，utf-8 用 utf-8-sig）
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", "replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", "replace")

    charset = ""
    m = _CT_CHARSET_RE.search(ct)
    if m:
        charset = m.group(1)
    if not charset:
        m = _CHARSET_RE.search(data[:4096])
        if m:
            charset = m.group(1).decode("ascii", "ignore")
    if charset:
        try:
            return data.decode(charset, "replace")
        except (LookupError, UnicodeDecodeError):
            pass
    return data.decode("utf-8", "replace")


def _html_to_text(page: str) -> tuple[str, str]:
    """HTML → (标题, 纯文本)：去 script/style、去标签、压空白。"""
    title = ""
    m = _TITLE_RE.search(page)
    if m:
        title = html_mod.unescape(_TAG_RE.sub("", m.group(1))).strip()
    # 只取 <body>；无 body 标签时去掉 <head>（避免 title/meta/style 混入正文）
    mb = _BODY_RE.search(page)
    if mb:
        body = mb.group(1)
    else:
        body = _HEAD_RE.sub(" ", page)
    body = _SCRIPT_STYLE_RE.sub(" ", body)
    # 块级标签换行，再去掉所有标签
    body = _BLOCK_RE.sub("\n", body)
    body = _TAG_RE.sub(" ", body)
    body = html_mod.unescape(body)
    body = _WS_RE.sub(" ", body)
    body = _NEWLINE_RE.sub("\n", body)
    return title, body.strip()


class _Result(NamedTuple):
    """单链接处理结果：正文片段 / 图片路径 / 日志文案。"""
    part: str
    image: str | None
    log: str | None


def _process_one_impl(url: str) -> _Result:
    """抓取并处理单个 URL，返回 (正文片段, 图片路径或 None, 日志文案或 None)。"""
    is_img_url = _path_ext(url) in _IMG_EXTS
    try:
        raw_ct, data = _fetch(url)
    except Exception as e:                        # noqa: BLE001
        if is_img_url:
            # 明确以图片语义报告，避免模型误读成"文字链接打不开"
            return _Result(
                "[图片链接 %s 无法下载（%s）。这是图片地址，但当前防盗链/"
                "鉴权导致拿不到图片数据；若需识图请用「附件」上传本地图片文件，"
                "或改用可公开访问的图片直链。]" % (url, _err(e)), None, None)
        return _Result("[链接 %s 抓取失败：%s]" % (url, _err(e)), None, None)

    ctype = _mime_type(raw_ct)
    if ctype in _CT_EXT:                          # 图片 → 识图附件
        path = _save_media(ctype, data, url)
        return _Result("", path, "🖼 已下载图片：%s" % os.path.basename(path))
    if is_img_url:
        # 扩展名是图片但 Content-Type 不是图片：多为防盗链/反代返回的 HTML
        # 错误页/提示页，落成 .png 会让识图管线拿到坏文件 → 按失败报告。
        if ctype == "text/html":
            return _Result(
                "[图片链接 %s 拿到的不是图片数据（Content-Type: text/html），"
                "通常是防盗链或需要登录的页面；若需识图请用「附件」上传本地"
                "图片文件，或改用可公开访问的图片直链。]" % url, None, None)
        # 其它非 HTML 类型（如被反代/改写为 application/octet-stream）：
        # 仍按图片落盘走识图，交给归一化按内容判断。
        path = _save_media(ctype or "image/png", data, url)
        return _Result("", path,
                       "🖼 已下载图片（按扩展名判定）：%s" % os.path.basename(path))
    if ctype == "text/html":                      # 网页 → 正文
        title, body = _html_to_text(_decode(data, raw_ct))
        if body:
            snippet = ("（前 %d 字）" % TEXT_LIMIT
                       if len(body) > TEXT_LIMIT else "")
            head = "[网页 %s%s正文]\n" % (url, snippet)
            if title:
                title = title[:TITLE_LIMIT] + ("…" if len(title) > TITLE_LIMIT else "")
                head = "[网页 %s%s正文 · %s]\n" % (url, snippet, title)
            return _Result(head + body[:TEXT_LIMIT] + "\n[正文结束]", None,
                           "📄 已抓取网页：%s（%d 字）" % (title or url, len(body)))
        return _Result("[网页 %s 无可提取文本]" % url, None, None)
    # 其它文件 → 落盘给工具
    path = _save_media(ctype, data, url)
    return _Result("[链接 %s 已下载到 %s（%s，%.0f KB），可用工具处理]"
                   % (url, path, ctype or "未知类型", len(data) / 1024),
                   None, None)


def _process_one(url: str) -> _Result:
    """单链接处理的兜底包装：任何意外异常都不冒泡，转成失败注释。"""
    try:
        return _process_one_impl(url)
    except Exception as e:                        # noqa: BLE001
        return _Result("[链接 %s 处理失败：%s]" % (url, _err(e)), None, None)


def process(text: str, log=None) -> tuple[str, list[str]]:
    """处理消息中的链接。返回 ( augment 后的正文, 图片路径列表 )。

    log 为可选回调（打印进度）。抓取失败只加注释行，不抛异常。
    多条链接并发抓取（最多 MAX_WORKERS），结果仍按原文顺序拼接。

    图片 URL：抓取成功 → 下载走识图附件；抓取失败（防盗链/403/需要鉴权等）
    → 以「图片链接」语义附到正文，并明确标注无法下载，避免模型误读为
    普通文字链接或误以为图片打不开。
    """
    urls = find_urls(text)
    if not urls:
        return text, []
    if log:
        for url in urls:
            log("🔗 取材中：%s" % url[:80])

    # 并发抓取（单条则直接串行，避免线程开销）
    if len(urls) > 1:
        with ThreadPoolExecutor(max_workers=min(len(urls), MAX_WORKERS)) as ex:
            results = list(ex.map(_process_one, urls))
    else:
        results = [_process_one(u) for u in urls]

    images, parts = [], [text] if text.strip() else []
    for url, result in zip(urls, results):
        if log and result.log:
            log(result.log)
        if result.image:
            images.append(result.image)
        if result.part:
            parts.append(result.part)
    return "\n\n".join(p for p in parts if p and p.strip()), images
