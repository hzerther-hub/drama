# -*- coding: utf-8 -*-
"""附件分析：发送前就地预处理文档与压缩包，把内容直接喂给模型。

支持：
- 文本类（txt/md/csv/log/json）：内联原文（超长截断）
- Word（docx）：纯 stdlib 解包 word/document.xml 提取正文
- PDF：优先 pdftotext 命令，其次 pypdf 库（均可选，缺了给模型留提示）
- 压缩包（zip/tar.gz/tgz/tar.bz2/tar.xz/tar/gz）：解压到配置目录，
  返回提取路径 + 文件清单，模型可用 read_file 等工具继续操作
- rar/7z：本机无解压命令时提示模型用 run_shell 处理

全部 graceful degradation：任何一步失败都降级为提示文字，不抛异常。
"""

from __future__ import annotations
import gzip
import hashlib
import os
import re
import shutil
import subprocess
import tarfile
import urllib.parse
import zipfile

import config
import media

# 单个附件内联文本上限（字符），控制上下文预算
MAX_INLINE_CHARS = 20000
# 压缩包清单最多列出的条目数
MAX_LIST_ENTRIES = 50

_TEXT_EXTS = {".txt", ".md", ".csv", ".log", ".json", ".xml", ".htm", ".html"}
_ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz"}
_SHELL_ONLY_EXTS = {".rar", ".7z"}


def analyze(path: str) -> str | None:
    """按类型分析附件，返回内联给模型的文字；不属于支持类型返回 None。"""
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    if ext in _TEXT_EXTS:
        return _inline_text(path, name)
    if ext == ".docx":
        return _docx_text(path, name)
    if ext == ".pdf":
        return _pdf_text(path, name)
    if ext == ".zip" or (ext == ".tar"):
        return _extract_archive(path, name)
    if ext in (".gz", ".tgz", ".bz2", ".xz") or ".tar." in os.path.basename(path).lower():
        return _extract_archive(path, name)
    if ext in _SHELL_ONLY_EXTS:
        tool = "unrar" if ext == ".rar" else "7z"
        return (f"[附件 {name} 是 {ext} 压缩包，本模块不解压；"
                f"模型可用 run_shell 调 {tool}（如未安装可先安装）处理]")
    return None


def _read_text(path: str) -> str:
    """读文本：utf-8 失败退 gb18030（中文环境常见），再失败按替换符读。"""
    raw = open(path, "rb").read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _inline_text(path: str, name: str) -> str:
    """文本类附件直接内联，超长截断并注明。"""
    try:
        text = _read_text(path)
    except OSError as e:
        return f"[附件 {name} 读取失败: {e}]"
    total = len(text)
    note = f"（已截断，全文 {total} 字符）" if total > MAX_INLINE_CHARS else ""
    return f"[附件 {name} 文本内容{note}]\n{text[:MAX_INLINE_CHARS]}"


def _docx_text(path: str, name: str) -> str:
    """docx = zip：解 word/document.xml，拼 <w:t> 文本、</w:p> 断行。"""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 损坏/非 docx → 提示模型自行处理
        return f"[附件 {name} docx 解析失败: {e}；可用 run_shell 尝试其他方式]"
    lines = []
    for para in xml.split("</w:p>"):
        line = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para))
        if line.strip():
            lines.append(line)
    text = "\n".join(lines)
    total = len(text)
    note = f"（已截断，全文 {total} 字符）" if total > MAX_INLINE_CHARS else ""
    return f"[附件 {name} Word 正文{note}]\n{text[:MAX_INLINE_CHARS]}" if text.strip() \
        else f"[附件 {name} 未提取到文本；可能是扫描件或空文档，可用 run_shell 处理]"


def _pdf_text(path: str, name: str) -> str:
    """PDF 提取：pdftotext 命令优先，其次可选 pypdf；都不行给提示。"""
    if shutil.which("pdftotext"):
        try:
            out = subprocess.run(
                ["pdftotext", "-enc", "UTF-8", "-layout", path, "-"],
                capture_output=True, timeout=30)
            if out.returncode == 0 and out.stdout.strip():
                text = out.stdout.decode("utf-8", "replace")
                total = len(text)
                note = f"（已截断，全文 {total} 字符）" if total > MAX_INLINE_CHARS else ""
                return f"[附件 {name} PDF 文本{note}]\n{text[:MAX_INLINE_CHARS]}"
        except Exception:  # noqa: BLE001 命令异常 → 尝试 pypdf
            pass
    try:
        from pypdf import PdfReader  # 可选依赖
        text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
        if text.strip():
            total = len(text)
            note = f"（已截断，全文 {total} 字符）" if total > MAX_INLINE_CHARS else ""
            return f"[附件 {name} PDF 文本{note}]\n{text[:MAX_INLINE_CHARS]}"
    except Exception:  # noqa: BLE001 未安装 pypdf 或解析失败 → 降级提示
        pass
    return (f"[附件 {name} 是 PDF，本机无 pdftotext/pypdf 无法就地提取；"
            f"模型可用 run_shell 安装/调用提取工具后处理]")


def _safe_zip_members(z: zipfile.ZipFile) -> list[str]:
    """过滤 zip 内的绝对路径/.. 穿越 条目，只留安全相对名。"""
    safe = []
    for info in z.infolist():
        if info.is_dir():
            continue
        norm = os.path.normpath(info.filename)
        if norm.startswith("..") or os.path.isabs(norm):
            continue
        safe.append(info.filename)
    return safe


def _extract_dir(path: str) -> str:
    """稳定提取目录：<文件名去扩展名>-<路径哈希8位>/，重复附件复用。"""
    stem = os.path.splitext(os.path.basename(path))[0]
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]
    return os.path.join(config.EXTRACT_DIR, f"{stem}-{digest}")


def _extract_archive(path: str, name: str) -> str:
    """解压 zip/tar 系压缩包到配置目录，返回清单 + 后续操作提示。"""
    dest = _extract_dir(path)
    try:
        already = os.path.isdir(dest) and any(os.scandir(dest))
        if not already:
            os.makedirs(dest, exist_ok=True)
            if name.lower().endswith(".zip"):
                with zipfile.ZipFile(path) as z:
                    for member in _safe_zip_members(z):
                        z.extract(member, dest)
            else:
                # filter="data"（Python 3.12+）拦截 tar 路径穿越/设备文件
                with tarfile.open(path, "r:*") as t:
                    t.extractall(dest, filter="data")
    except Exception as e:  # noqa: BLE001 解压失败 → 提示模型用 run_shell
        return f"[附件 {name} 解压失败: {e}；模型可用 run_shell 尝试其他方式]"

    entries = []
    total_bytes = 0
    for root, _dirs, files in os.walk(dest):
        for f in files:
            fp = os.path.join(root, f)
            try:
                size = os.path.getsize(fp)
            except OSError:
                size = 0
            total_bytes += size
            entries.append((os.path.relpath(fp, dest), size))
    entries.sort()
    listed = "\n".join(f" - {e} ({size} B)" for e, size in entries[:MAX_LIST_ENTRIES])
    more = f"\n …（其余 {len(entries) - MAX_LIST_ENTRIES} 个略）" \
        if len(entries) > MAX_LIST_ENTRIES else ""
    return (f"[附件 {name} 已解压] → {dest}（{len(entries)} 个文件，"
            f"共 {total_bytes} B）\n清单：\n{listed}{more}\n"
            f"以上均为绝对路径目录下的相对文件，可用 read_file / grep_search / "
            f"glob_search 直接操作 {dest} 下的文件。")


# ---------------- 消息内本地文件引用 → 附件 ----------------

# file:// URI（尾部排除中英文标点，避免吞掉句读）
_FILE_URI_RE = re.compile(r"file://(/[^\s，。；：！？、）」』\]）〉>]+)")
# 裸 Windows 盘符路径（C:\... 或 C:/...，如从微信复制的图片路径）。
# 前置断言保证不是更长单词/URL 的一部分；尾部排除标点与引号。
# （与 URI 一致：以空白结尾，不支持含空格的路径）
_WIN_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_/])"
    r"[A-Za-z]:[\\/][^\s，。；：！？、）」』\]）〉>\"'<>|]+")
# POSIX 绝对路径（/home、/Users、/tmp、/workspace、/mnt、/media…），
# 与盘符路径同规则：仅媒体文件转附件
_POSIX_PATH_RE = re.compile(
    r"(?<![\w./\\])(?:/home|/Users|/tmp|/workspace|/mnt|/media|/opt|/root)"
    r"[^\s\"'<>\u4e00-\u9fff，。；：！？]+")


def extract_file_refs(text: str) -> tuple[list[str], str]:
    """把消息里引用的本地文件提取为附件路径，返回 (路径列表, 剩余文本)。

    三类引用、两种规则：
    - file:// URI：显式引用，文件存在即转附件（任意类型，文档/压缩包
      照常就地分析）；支持 percent-encoding 与 Windows 形式 file:///C:/...
    - 裸盘符路径（C:\\... / C:/...）与 POSIX 绝对路径（/home、/Users…）：
      仅当文件存在且是图片/音频/视频才转（从微信等复制的媒体路径场景）；
      其他路径保留原文，模型可用工具读取

    不存在的路径一律保留原文给模型看；三类引用自动去重。
    """
    paths: list[str] = []

    def _take_uri(m):
        p = urllib.parse.unquote(m.group(1))
        # file:// 的 // 与路径自带的前导 / 可能叠成多个斜杠（file:/// + /tmp 等）：
        # 归一为单个前导斜杠，再按 Windows/POSIX 处理
        p = re.sub(r"^/+", "/", p)
        # Windows 形式 file:///C:/...：去掉盘符前的斜杠再判断
        if re.match(r"^/[A-Za-z]:[\\/]", p):
            p = p[1:]
        if os.path.isfile(p):
            if p not in paths:
                paths.append(p)
            return ""
        return m.group(0)

    def _take_media(m):
        p = m.group(0).rstrip(".,;:!?)]}")
        if os.path.isfile(p) and media.classify(p):
            if p not in paths:
                paths.append(p)
            return ""
        return m.group(0)

    stripped = _FILE_URI_RE.sub(_take_uri, text)
    stripped = _WIN_PATH_RE.sub(_take_media, stripped)
    stripped = _POSIX_PATH_RE.sub(_take_media, stripped)
    return paths, re.sub(r"[ \t]{2,}", " ", stripped).strip()


# ---------------- 代码片段附件（编辑器选中区右键加入） ----------------

# 结构统一用 dict：{"kind":"snippet","path","start_line","end_line","content"}


def format_snippet(att: dict) -> str:
    """把代码片段附件格式化成一段文字（含文件与行号），供发给模型/聊天展示。

    用拼接而非 str.format，避免代码里的花括号触发格式化异常。
    """
    base = os.path.basename(att["path"])
    return ("【代码片段】" + base + "（第 " + str(att["start_line"]) +
            " 行 - 第 " + str(att["end_line"]) + " 行）\n" + att["content"])


def snippet_chip(att: dict) -> str:
    """代码片段附件的附件栏 chip 标签。"""
    base = os.path.basename(att["path"])
    return ("📄 " + base + "（行 " + str(att["start_line"]) + "-" +
            str(att["end_line"]) + "）")


__all__ = ["analyze", "extract_file_refs", "format_snippet", "snippet_chip"]
