# -*- coding: utf-8 -*-
"""Tkinter 界面：流式聊天 + 工具调用展示 + 权限审批 + 目录切换 + 语音。

另含：📎 附件（图片识图/音视频）、聊天区内嵌媒体控件
（图片/GIF 动画/音频播放/视频缩略图）、MCP 服务器管理。
使用系统默认颜色（浅色），只保留布局和功能。
"""

from __future__ import annotations
import html
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk

import agent as agent_mod
import attach
import config
import media
import mcp
import theme
import tools

try:
    import products                   # 产品 profile / 功能开关（缺失时全开）
except Exception:                     # noqa: BLE001
    products = None


def _feature(key: str, default: bool = True) -> bool:
    """产品功能开关查询；products 缺失时默认全开（兼容独立运行）。"""
    if products is None:
        return default
    try:
        return products.feature(key, default)
    except Exception:                 # noqa: BLE001
        return default


def _app_title() -> str:
    """主窗口标题：跟随激活产品 profile 的 title；缺失时回退 i18n 默认。"""
    if products is not None:
        try:
            t = products.active().title
            if t:
                return t
        except Exception:             # noqa: BLE001
            pass
    return _t("app.title")


try:
    import weblinks                  # 消息内链接自动取材（图片识图/网页正文）
except Exception:                     # noqa: BLE001
    weblinks = None

from i18n import t as _t, set_lang as _set_lang, load_lang as _load_lang, get_lang as _get_lang

# 权限模式 → 显示名 key（按当前语言动态取）
MODE_LABEL_KEYS = {
    agent_mod.MODE_READONLY: "mode.readonly",
    agent_mod.MODE_ASK: "mode.ask",
    agent_mod.MODE_ALWAYS: "mode.always",
}


def _ctx_label_key():
    """上下文模式 → 显示名 key：独立提问 / 续上下文。"""
    return "ctx.standalone" if config.get_standalone() else "ctx.keep"


def _ctx_btn_icon():
    """上下文模式 → 按钮图标：续上下文 🔗 / 独立提问 ✂️。"""
    return "🔗" if not config.get_standalone() else "✂️"


# 权限模式 → 图标（按钮前缀）
MODE_ICON = {
    agent_mod.MODE_READONLY: "🔒",
    agent_mod.MODE_ASK: "🛡",
    agent_mod.MODE_ALWAYS: "⚡",
}


def _mode_btn_label(mode):
    """权限按钮文案：图标 + 模式名（跟随当前语言）。"""
    return f"{MODE_ICON.get(mode,'🛡')} {_mode_label(mode)}"

# 推理等级可选值（第一个空值 = 留空，不发送、用模型默认）
# 覆盖 OpenAI/Kimi/GLM（low/medium/high）与 DeepSeek（low/medium/high/xhigh/max/none）
REASONING_CHOICES = ("", "none", "low", "medium", "high", "xhigh", "max")

# 各等级图标（空值=默认/关）
REASONING_ICON = {
    "": "⚪",
    "none": "🚫",
    "low": "🐢",
    "medium": "🧠",
    "high": "⚡",
    "xhigh": "🔥",
    "max": "🚀",
}


def _reasoning_label(val: str):
    """等级显示文案：图标 +（翻译后的）默认名或等级值。"""
    if val:
        return f"{REASONING_ICON.get(val, '🧠')} {val}"
    return f"{REASONING_ICON.get('', '🌫')} {_t('model.reasoning.default')}"



def _mode_label(mode):
    return _t(MODE_LABEL_KEYS.get(mode, "mode.ask"))
def _stat_text(u: dict, cached_pct: float = 0, fast_hits=None, saved=None) -> str:
    """按当前语言构建底部统计栏文案。"""
    reasoning = (("  " + _t("stat.think") + ": " + str(u.get("reasoning_tokens")))
                 if u.get("reasoning_tokens") else "")
    extra = ("  " + _t("stat.fast") + ": %d  (%s)" % (fast_hits, _t("stat.save_tk", n=saved))
             if fast_hits else "")
    return ("%s: %d  (↑%s %d ↓%s %d)%s"
            "  %s: %d (%.0f%%)"
            "  %s: %d%s") % (
        _t("stat.tokens"), int(u["total_tokens"]),
        _t("stat.in"), int(u["prompt_tokens"]),
        _t("stat.out"), int(u["completion_tokens"]),
        reasoning,
        _t("stat.cache"), int(u["cached_tokens"]), cached_pct,
        _t("stat.req"), int(u["requests"]),
        extra)


# 各平台候选字体（等宽 / 中文无衬线），按优先级排列
_MONO_CANDIDATES = [
    "JetBrains Mono", "Cascadia Code", "Consolas", "Menlo", "Monaco",
    "DejaVu Sans Mono", "Courier New", "monospace",
]
_UI_CANDIDATES = [
    "Noto Sans CJK SC", "Microsoft YaHei UI", "Microsoft YaHei",
    "PingFang SC", "Hiragino Sans GB", "WenQuanYi Micro Hei",
    "Segoe UI", "Helvetica", "sans-serif",
]
# 初始值（_setup_fonts() 会按平台重选）
FONT_MONO = "JetBrains Mono"       # 等宽：代码、工具结果、输入框
FONT_UI = "Noto Sans CJK SC"       # 正文：中英文混排，现代无衬线
# 彩色 emoji：按平台选择系统已装的彩色 emoji 字体。
# 顶栏带 emoji 的 Label/Button 显式用这个，否则会回退到 FONT_UI 把 emoji 渲成黑字形。
_FONT_EMOJI_CANDIDATES = (
    "Segoe UI Emoji",       # Windows（自带，彩色）
    "Apple Color Emoji",    # macOS（自带，彩色）
    "Noto Color Emoji",     # Linux（多数发行版不自带，需手动装）
    "Twitter Color Emoji",  # Linux 备用
)
FONT_EMOJI = _FONT_EMOJI_CANDIDATES[0]   # 默认值，_setup_fonts() 在探测后再校正

# ================= 源码高亮（多语言） =================
# 按文件扩展名映射到语言
_EDITOR_LANG_EXT = {
    ".py": "python", ".pyw": "python", ".php": "php", ".phtml": "php",
    ".java": "java", ".cs": "csharp", ".cpp": "cpp", ".cc": "cpp",
    ".cxx": "cpp", ".c": "c", ".h": "cpp", ".hpp": "cpp",
    ".rs": "rust", ".dart": "dart", ".js": "js", ".mjs": "js",
    ".ts": "ts", ".jsx": "js", ".tsx": "ts", ".vue": "vue",
    ".html": "html", ".htm": "html", ".xml": "html",
    ".go": "go", ".rb": "ruby", ".swift": "swift", ".kt": "kotlin",
    ".vb": "vb", ".vbs": "vb", ".vbnet": "vb", ".bas": "basic",
    ".erl": "erlang", ".hrl": "erlang", ".escript": "erlang",
    ".kts": "kotlin", ".sql": "sql", ".sh": "sh", ".bash": "sh",
    ".css": "css", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".md": "md",
}

# 语言 -> 关键词集合
_EDITOR_KW = {
    "python": {"def","class","if","elif","else","for","while","return","import","from",
               "as","try","except","finally","with","lambda","yield","pass","break",
               "continue","raise","global","nonlocal","assert","del","in","is","and",
               "or","not","None","True","False","async","await","match","case","self"},
    "php": {"echo","print","if","else","elseif","for","foreach","while","do","switch",
            "case","break","continue","return","function","class","interface","extends",
            "implements","new","try","catch","finally","throw","use","namespace",
            "public","private","protected","static","const","global","require","include",
            "isset","empty","array","as","and","or","xor","instanceof","true","false"},
    "java": {"public","private","protected","class","interface","extends","implements",
             "new","try","catch","finally","throw","if","else","for","while","do","switch",
             "case","break","continue","return","static","final","void","int","long",
             "double","float","boolean","char","byte","short","abstract","enum","import",
             "package","this","super","null","true","false","synchronized"},
    "csharp": {"public","private","protected","class","interface","namespace","using","new",
               "try","catch","finally","throw","if","else","for","foreach","while","do",
               "switch","case","break","continue","return","static","void","int","long",
               "double","float","bool","char","string","var","sealed","abstract","override",
               "partial","async","await","null","true","false","enum"},
    "cpp": {"public","private","protected","class","struct","namespace","using","new",
            "delete","if","else","for","while","do","switch","case","break","continue",
            "return","void","int","long","double","float","bool","char","const","static",
            "inline","virtual","override","template","typename","auto","nullptr","true",
            "false","this"},
    "c": {"if","else","for","while","do","switch","case","break","continue","return",
          "void","int","long","double","float","char","const","static","struct","union",
          "enum","typedef","sizeof"},
    "rust": {"fn","let","mut","if","else","for","while","loop","match","return","struct",
             "enum","impl","trait","mod","use","pub","crate","self","super","as","async",
             "await","move","ref","where","dyn","true","false"},
    "dart": {"class","extends","implements","with","new","super","this","if","else","for",
             "while","do","switch","case","break","continue","return","void","int","double",
             "bool","String","var","final","const","static","get","set","async","await",
             "null","true","false","import","library"},
    "js": {"function","var","let","const","if","else","for","while","do","switch","case",
           "break","continue","return","class","extends","new","try","catch","finally",
           "throw","async","await","typeof","instanceof","null","undefined","true","false",
           "this","import","export","from","default"},
    "ts": {"function","var","let","const","if","else","for","while","do","switch","case",
           "break","continue","return","class","extends","implements","interface","new",
           "try","catch","finally","throw","async","await","typeof","instanceof","null",
           "undefined","true","false","this","import","export","from","default","type",
           "enum","readonly"},
    "vue": {"template","script","style","export","default","from","import","new","const",
            "let","function","return","props","data","computed","methods","watch","mounted",
            "created","if","else","for","v-if","v-for","v-bind","v-on","true","false"},
    "html": {"html","head","body","div","span","p","a","ul","ol","li","table","tr","td",
             "th","thead","tbody","form","input","button","select","option","img","script",
             "style","link","meta","title","section","header","footer","nav","main","h1",
             "h2","h3","h4","h5","h6","class","id","href","src","style","type","name"},
    "go": {"package","import","func","var","const","type","struct","interface","if","else",
           "for","range","return","go","defer","chan","map","nil","true","false"},
    "ruby": {"def","end","if","else","elsif","unless","while","until","for","each","do",
             "class","module","require","include","puts","return","true","false","nil"},
    "swift": {"func","var","let","if","else","for","while","switch","case","break",
              "continue","return","class","struct","enum","protocol","extension","import",
              "guard","defer","self","true","false","nil"},
    "kotlin": {"fun","val","var","if","else","for","while","do","when","in","is","class",
               "object","interface","data","sealed","override","open","private","public",
               "protected","internal","return","null","true","false"},
    "sql": {"select","from","where","insert","update","delete","create","table","join",
            "inner","left","right","on","group","by","order","having","limit","and","or",
            "not","null","primary","key","values","into"},
    "sh": {"if","then","else","elif","fi","for","while","do","done","case","esac",
           "function","echo","exit","return","local","export"},
    "css": {"color","background","display","position","margin","padding","border","width",
            "height","font","align","flex","grid","hover","@media","@import"},
    "json": {"true","false","null"},
    "yaml": {"true","false","null"},
    "toml": {"true","false"},
    "md": set(),
    "vb": {"Dim","If","Then","Else","ElseIf","For","Each","While","Do","Loop","Sub",
           "Function","End","Return","Public","Private","Class","Module","New","Try",
           "Catch","Finally","Throw","And","Or","Not","True","False","Nothing","ByVal",
           "ByRef","As","Select","Case","Exit","Continue","Structure","Overrides",
           "Implements","Inherits","Interface","Enum","Const","Static","Shared",
           "Boolean","Integer","Long","Double","String","Object","Decimal","Single",
           "With","Property","Get","Set"},
    "basic": {"IF","THEN","ELSE","ELSEIF","FOR","NEXT","TO","STEP","WHILE","WEND","DO",
              "LOOP","GOTO","GOSUB","RETURN","SUB","END","FUNCTION","PRINT","INPUT",
              "DIM","LET","AND","OR","NOT","TRUE","FALSE","REM","SELECT","CASE","AS"},
    "erlang": {"module","export","import","record","define","include","include_lib","fun",
               "case","of","when","end","if","receive","after","try","catch","throw",
               "begin","andalso","orelse","not","and","or","xor","div","rem","true",
               "false","maybe","let","ok","error","fail","bnot","bor","band","bxor",
               "bsl","bsr","query","call","spawn","send","self","pid","ref","atom",
               "integer","float","tuple","list","binary","var"},
}

# 语言 -> (行注释, 块注释对)
_EDITOR_CMT = {
    "python": ("#", None), "sh": ("#", None), "ruby": ("#", None),
    "php": ("//", ("/*", "*/")), "java": ("//", ("/*", "*/")),
    "csharp": ("//", ("/*", "*/")), "cpp": ("//", ("/*", "*/")), "c": ("//", ("/*", "*/")),
    "rust": ("//", None), "dart": ("//", None), "js": ("//", ("/*", "*/")),
    "ts": ("//", ("/*", "*/")), "vue": ("//", ("<!--", "-->")),
    "html": (None, ("<!--", "-->")), "css": (None, ("/*", "*/")),
    "go": ("//", None), "swift": ("//", None), "kotlin": ("//", ("/*", "*/")),
    "sql": ("--", None),
    "vb": ("'", None), "basic": ("'", None),
    "erlang": ("%", None),
}


def _fetch_openai_models(base_url: str, api_key: str,
                         api_type: str = "openai_compatible") -> list:
    """端点获取模型列表（GET /models），失败抛异常。

    base_url 可能带或不带 /v1 后缀，自动尝试两种拼法；
    api_type="anthropic" 时改用 x-api-key + anthropic-version 鉴权
    （Anthropic /v1/models 与 OpenAI 响应同为 {"data":[{"id":...}]}）；
    返回按字母排序的模型 ID 列表（去重）。
    """
    import json
    import urllib.request

    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError(_t("fetch.e.empty"))
    candidates = [base + "/models"]
    if not base.endswith("/v1"):
        candidates.insert(1, base + "/v1/models")
    # anthropic 型端点用 x-api-key + anthropic-version 鉴权（无 Bearer）
    is_anthropic = (api_type == "anthropic")
    last_exc = None
    for url in candidates:
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")})
        if is_anthropic:
            if api_key:
                req.add_header("x-api-key", api_key)
            req.add_header("anthropic-version", "2023-06-01")
        elif api_key:
            req.add_header("Authorization", "Bearer " + api_key)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.load(r)
            ids = {m.get("id") for m in data.get("data", []) if m.get("id")}
            if ids:
                return sorted(ids)
            last_exc = ValueError(_t("fetch.e.nodata"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                last_exc = ValueError(_t("fetch.e.auth", c=e.code))
            elif e.code == 404:
                last_exc = ValueError(_t("fetch.e.404"))
            elif e.code >= 500:
                last_exc = ValueError(_t("fetch.e.server", c=e.code))
            else:
                last_exc = ValueError(_t("fetch.e.http", c=e.code, u=url))
        except Exception as e:                      # noqa: BLE001
            last_exc = e
    raise last_exc


# 文件类型 → Noto 彩色图标（assets/icons/<hex>.png，见 _emoji_icon）
_TREE_ICON_MAP = {
    "py": "1f40d", "md": "1f4dd", "markdown": "1f4dd",
    "txt": "1f4c4", "log": "1f4c4",
    "json": "2699", "yaml": "2699", "yml": "2699", "toml": "2699",
    "ini": "2699", "cfg": "2699", "conf": "2699",
    "ipynb": "1f4d3",
    "html": "1f310", "htm": "1f310", "css": "1f310", "js": "1f310",
    "mjs": "1f310", "ts": "1f310", "tsx": "1f310", "jsx": "1f310",
    "png": "1f5bc", "jpg": "1f5bc", "jpeg": "1f5bc", "gif": "1f5bc",
    "bmp": "1f5bc", "webp": "1f5bc", "svg": "1f5bc", "ico": "1f5bc",
    "csv": "1f4ca", "xlsx": "1f4ca", "xls": "1f4ca",
    "zip": "1f4e6", "tar": "1f4e6", "gz": "1f4e6", "tgz": "1f4e6",
    "7z": "1f4e6", "rar": "1f4e6",
    "pdf": "1f4d5", "doc": "1f4d8", "docx": "1f4d8",
    "mp3": "1f3b5", "wav": "1f3b5", "flac": "1f3b5", "m4a": "1f3b5",
    "mp4": "1f3ac", "mov": "1f3ac", "avi": "1f3ac", "mkv": "1f3ac",
    "bat": "1f527", "sh": "1f527", "ps1": "1f527",
}


def _emoji_icon(key: str):
    """hex 码点 → 彩色 PNG PhotoImage（缺素材/非 Windows 返回 None）。"""
    try:
        return _icon_image(chr(int(key, 16)))
    except Exception:                # noqa: BLE001
        return None


def _tv_select(lb, i) -> int:
    """Treeview 候选框：选中第 i 行（夹紧范围）并滚动可见，返回实际 i。"""
    kids = lb.get_children("")
    if not kids:
        return 0
    i = max(0, min(i, len(kids) - 1))
    lb.selection_set(kids[i])
    lb.see(kids[i])
    return i


def _tv_index(lb) -> int:
    """Treeview 候选框：当前选中行索引（无选中返回 0）。"""
    sel = lb.selection()
    return lb.index(sel[0]) if sel else 0


def _fmt_size(n) -> str:
    """字节数 → 人类可读：980 B / 12.3 KB / 4.5 MB。"""
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return ("%d %s" % (n, unit)) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024
    return "%.1f TB" % n


def _dir_size(path: str, max_entries: int = 20000) -> int:
    """目录聚合大小（递归，含隐藏文件）。条目数超过 max_entries 提前止步，
    防止 node_modules/.git 之类超大目录拖慢文件树刷新。"""
    total = 0
    count = 0
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    count += 1
                    if count > max_entries:
                        return total
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def _project_fonts_dir() -> str:
    """项目自带字体目录。兼容源码运行和 PyInstaller 打包。"""
    if hasattr(sys, "_MEIPASS"):   # PyInstaller 解包目录
        bundled = os.path.join(sys._MEIPASS, "fonts")
        if os.path.isdir(bundled):
            return bundled
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def _load_bundled_fonts() -> bool:
    """把项目 fonts/ 里的字体注册到当前进程/用户环境（免安装生效）。

    - Windows：AddFontResourceExW（FR_PRIVATE，仅本进程）
    - macOS：CoreText CTFontManagerRegisterFontsForURL（进程域）
    - Linux：复制到 ~/.local/share/fonts + fc-cache
    返回是否成功处理了字体文件。
    """
    fonts_dir = _project_fonts_dir()
    if not os.path.isdir(fonts_dir):
        return False
    font_files = [os.path.join(fonts_dir, f) for f in sorted(os.listdir(fonts_dir))
                  if f.lower().endswith((".ttf", ".ttc", ".otf"))]
    if not font_files:
        return False

    system = sys.platform
    try:
        if system == "win32":
            import ctypes
            gdi32 = ctypes.windll.gdi32
            for p in font_files:
                gdi32.AddFontResourceExW(p, 0x10, 0)   # 0x10 = FR_PRIVATE
            return True
        if system == "darwin":
            import ctypes
            import ctypes.util
            ct_path = ctypes.util.find_library("CoreText")
            if not ct_path:
                return False
            ct = ctypes.CDLL(ct_path)
            from Foundation import NSURL  # type: ignore
            for p in font_files:
                url = NSURL.fileURLWithPath_(p)
                ct.CTFontManagerRegisterFontsForURL(url, 1, None)  # 1=进程域
            return True
        # Linux / BSD：安装到用户字体目录并刷新缓存
        import shutil
        user_fonts = os.path.join(os.path.expanduser("~"),
                                  ".local", "share", "fonts", "local-ai-studio")
        os.makedirs(user_fonts, exist_ok=True)
        for p in font_files:
            dst = os.path.join(user_fonts, os.path.basename(p))
            if not os.path.exists(dst):
                shutil.copy(p, dst)
        subprocess.run(["fc-cache", "-f", user_fonts],
                       capture_output=True, timeout=30)
        return True
    except Exception:  # noqa: BLE001
        return False


def _flat_button(parent, text, command, width=12, font=(FONT_UI, 10)):
    """扁平按钮（令牌底色 + 悬停浅主题色反馈，无边框浮雕）。"""
    btn = tk.Button(parent, text=text, command=command, width=width,
                    font=font, relief="flat", cursor="hand2", padx=8, pady=4,
                    bg=theme.BG, fg=theme.TEXT, bd=0, highlightthickness=0,
                    activebackground=theme.ACCENT_FAINT,
                    activeforeground=theme.TEXT)

    def _hover(on):
        if str(btn.cget("state")) == "normal":
            btn.config(bg=theme.ACCENT_FAINT if on else theme.BG)
    btn.bind("<Enter>", lambda _e: _hover(True))
    btn.bind("<Leave>", lambda _e: _hover(False))
    return btn


# ---------------- emoji 图标按钮：Windows 走 PNG 图片 ----------------
# Tk 9.0 的 Windows 字体引擎渲染不了彩色字形（要 9.1+），字体方案在 Win 上
# 只能出黑色图标；这里改用 Noto Emoji 的 PNG（Apache-2.0，assets/icons/），
# 非平台 fallback：其它系统 emoji 字体本来就是彩色，继续走字体。
_ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets", "icons")
_ICON_PHOTOS: dict = {}          # 文件名 key → PhotoImage（持引用防 GC）


def _icon_image(emoji):
    """emoji → 彩色 PNG PhotoImage；非 Windows / 无 root / 缺素材返回 None。"""
    if sys.platform != "win32":
        return None
    key = "_".join(f"{ord(c):x}" for c in emoji.replace("\ufe0f", ""))
    path = os.path.join(_ICON_DIR, key + ".png")
    if not os.path.isfile(path):
        return None
    img = _ICON_PHOTOS.get(key)
    if img is None:
        try:
            img = tk.PhotoImage(file=path)
            while img.width() > 18:          # 128px 源图缩到 ~16px 贴按钮
                img = img.subsample(2)
            _ICON_PHOTOS[key] = img
        except Exception:                    # noqa: BLE001  PNG 损坏则回退字体
            return None
    return img


def _image_button(parent, img, command):
    """PNG 图标按钮：与 _flat_button 同款扁平/悬停风格。"""
    btn = tk.Button(parent, image=img, command=command, relief="flat",
                    cursor="hand2", bg=theme.BG, bd=0, highlightthickness=0,
                    activebackground=theme.ACCENT_FAINT)

    def _hover(on):
        if str(btn.cget("state")) == "normal":
            btn.config(bg=theme.ACCENT_FAINT if on else theme.BG)
    btn.bind("<Enter>", lambda _e: _hover(True))
    btn.bind("<Leave>", lambda _e: _hover(False))
    btn._icon_ref = img              # PhotoImage 挂在控件上防 GC
    return btn


def _flat_emoji_button(parent, emoji, command, width=2, font_size=None):
    """纯 emoji 按钮：Windows 优先 PNG 图片，其它平台/缺素材回退字体字形。"""
    img = _icon_image(emoji)
    if img is not None:
        return _image_button(parent, img, command)
    return _flat_button(parent, text=emoji, command=command, width=width,
                        font=(FONT_EMOJI, font_size or theme.FS_ICON))


def _set_btn_icon(btn, emoji):
    """运行时切换 emoji 按钮的图标（图片/字体两态都要能切）。"""
    img = _icon_image(emoji)
    if img is not None:
        btn.config(image=img, text="")
        btn._icon_ref = img
    else:
        btn.config(text=emoji)


def _enable_text_copy(text, block_tags=()):
    """让 disabled 的 Text/ScrolledText 可选中、可复制（含鼠标拖选）。

    Tk 的 disabled Text 忽略鼠标输入、无法拖选文本——这是"部分内容
    复制不了"的根源。做法：点击时临时切到 normal（可拖选、可 Ctrl+C），
    失去焦点时恢复 disabled 防误编辑，并拦截普通编辑键（仅放行
    Ctrl+A/C）。block_tags 非空时右键菜单额外提供「复制本条消息」：
    把光标/右键所在的那条消息（如 user/assistant 块）整体复制。
    """
    def _copy():
        try:
            sel = text.get("sel.first", "sel.last")
        except tk.TclError:
            return               # 无选区
        if sel:
            text.clipboard_clear()
            text.clipboard_append(sel)

    def _copy_all():
        text.clipboard_clear()
        text.clipboard_append(text.get("1.0", "end-1c"))

    def _copy_block():
        """复制鼠标所在的那条消息块（按 block_tags 的标签范围）。"""
        cur = getattr(menu, "cur", None)
        if not cur:
            return
        for tag in block_tags:
            try:
                r = text.tag_prevrange(tag, cur + "+1c")
            except tk.TclError:
                continue
            if r and text.compare(r[0], "<=", cur) \
                    and text.compare(cur, "<", r[1]):
                text.clipboard_clear()
                text.clipboard_append(text.get(r[0], r[1]))
                return

    menu = tk.Menu(text, tearoff=0)
    menu.add_command(label=_t("menu.copy"), command=_copy)
    if block_tags:
        menu.add_command(label=_t("menu.copy_block"), command=_copy_block)
    menu.add_command(label=_t("menu.select_all"), command=_copy_all)

    def _activate(_e=None):
        # 点击：切到 normal 允许鼠标拖选，并抢焦点（Ctrl+C 派发到本控件）
        if str(text.cget("state")) == "disabled":
            text.config(state="normal")
        text.focus_set()

    def _deactivate(_e=None):
        # 失去焦点：恢复 disabled，防止把只读内容改掉
        if str(text.cget("state")) == "normal":
            text.config(state="disabled")

    def _block_edit(e):
        # normal 期间只放行 Ctrl+A/C（复制/全选），其余键一律拦截
        if e.state & 0x4 and e.keysym in ("c", "C", "a", "A"):
            return None
        return "break"

    def _on_right(_e):
        _activate(_e)           # 右键也切 normal，保证菜单复制可用
        try:
            menu.cur = text.index("current")   # 记录右键位置（菜单弹出后 current 会漂移）
        except tk.TclError:
            menu.cur = None
        # 若点选在已有选区内则保留选区，否则把光标定位到点击处
        try:
            sel_first, sel_last = text.index("sel.first"), text.index("sel.last")
            cur = text.index("current")
            if not (text.compare(sel_first, "<=", cur)
                    and text.compare(cur, "<=", sel_last)):
                text.mark_set("insert", cur)
        except tk.TclError:
            pass
        menu.tk_popup(_e.x_root, _e.y_root)

    text.bind("<Button-1>", _activate)
    text.bind("<Button-3>", _on_right)
    text.bind("<FocusOut>", _deactivate)
    text.bind("<Key>", _block_edit)
    text.bind("<Control-c>", lambda e: _copy() or "break")
    text.bind("<Control-C>", lambda e: _copy() or "break")
    text.bind("<Control-a>", lambda e: text.tag_add("sel", "1.0", "end-1c")
              or "break")
    text.bind("<Control-A>", lambda e: text.tag_add("sel", "1.0", "end-1c")
              or "break")
    if sys.platform == "darwin":        # macOS 用户习惯 Cmd+C / Cmd+A
        text.bind("<Command-c>", lambda e: _copy() or "break")
        text.bind("<Command-a>", lambda e: text.tag_add("sel", "1.0", "end-1c")
                  or "break")


# 消息里的本地文件引用（file:// URI / 裸盘符路径）自动转附件：
# 提取逻辑在 attach.extract_file_refs（可脱离 tkinter 单测）。


# ================= 工具返回美化 =================
# 把工具/搜索/网页抓取的原始返回格式化成结构化片段：
# segment = {"text": str, "tag": 外观标签, "url": 可点击链接, "popup": (标题, 全文)}

_DISPLAY_MAX = 6000     # 正文直接展示的字符上限（超出折叠为「查看全文」；提高以完整显示 DSH 式工具结果）
_SNIPPET_MAX = 200      # 单条搜索摘要展示长度
_ITEM_RE = re.compile(r"^\s*(\d+)[.、]\s*(.+)$")


def _open_url(url: str):
    """用系统默认浏览器打开链接。"""
    import webbrowser
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


def _show_text_window(parent, title: str, text: str):
    """完整内容查看窗口：可复制、可另存。"""
    from tkinter import messagebox
    win = tk.Toplevel(parent.winfo_toplevel())
    win.title(title)
    win.geometry("720x540")
    _make_modal(win, parent.winfo_toplevel())   # 弹窗统一模态
    win.configure(bg=theme.PANEL)
    box = scrolledtext.ScrolledText(win, wrap="word", font=(FONT_MONO, 10),
                                    relief="flat", padx=14, pady=12,
                                    background=theme.PANEL,
                                    foreground=theme.TEXT,
                                    highlightthickness=0)
    box.insert("1.0", text)
    box.config(state="disabled")
    _enable_text_copy(box)
    box.pack(fill="both", expand=True, padx=12, pady=(12, 0))

    def _save():
        p = filedialog.asksaveasfilename(parent=win, title=_t("dlg.save_as_title"))
        if not p:
            return
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo(_t("msg.saved"), _t("msg.saved_to", p=p), parent=win)
        except OSError as e:
            messagebox.showerror(_t("msg.save_fail"), str(e), parent=win)

    bar = tk.Frame(win)
    bar.pack(pady=10)
    tk.Button(bar, text=_t("btn.copy_all"), width=10, command=lambda: (
        win.clipboard_clear(), win.clipboard_append(text))).pack(
            side="left", padx=6)
    tk.Button(bar, text=_t("btn.save_as"), width=10, command=_save).pack(
        side="left", padx=6)
    tk.Button(bar, text=_t("btn.close"), width=10, command=win.destroy).pack(
        side="left", padx=6)
    win.bind("<Escape>", lambda e: win.destroy())


def _clean_text(s: str) -> str:
    """去掉 HTML 标签/样式/脚本/实体，压缩空白。"""
    s = re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"[ \t\u3000]+", " ", s).strip()


def _make_modal(win, parent):
    """把 win 调成依附 parent 的可靠模态窗口。

    Tk 的 grab_set() 在 Toplevel 尚未映射（未真正显示）时调用，在 Windows 上会
    静默失效，导致窗口看似能操作主界面。这里等窗口可见后再 grab，确保模态生效。
    """
    win.transient(parent)
    try:
        win.wait_visibility()
        win.grab_set()
        win.focus_set()
    except tk.TclError:
        # 窗口已销毁或父窗口不存在：放弃模态，避免阻塞
        pass


def _try_json(s: str):
    """尝试解析 JSON；兼容 MCP 返回的「字符串二次编码」（'"[{...}]"'）。"""
    try:
        v = json.loads(s)
    except (ValueError, TypeError):
        return None
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except (ValueError, TypeError):
            return None
    return v if isinstance(v, (dict, list)) else None


def _is_search_items(data) -> bool:
    """判断 JSON 是否为搜索结果列表：每项含 title + link/url/content。"""
    return (isinstance(data, list) and data
            and all(isinstance(x, dict) for x in data)
            and all(("title" in x or "content" in x)
                    and ("link" in x or "url" in x) for x in data))


def _fmt_search_items(items) -> list:
    """搜索结果列表 → 编号条目：标题/链接可点、摘要灰色。"""
    segs = [{"text": _t("render.search_done", n=len(items)),
             "tag": "toolhead"}]
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "").strip() or _t("misc.no_title")
        link = str(it.get("link") or it.get("url") or "").strip()
        snip = _clean_text(str(it.get("content") or it.get("snippet") or ""))
        snip = snip[:_SNIPPET_MAX] + ("…" if len(snip) > _SNIPPET_MAX else "")
        segs.append({"text": f" {i}. ", "tag": "toolitem"})
        if link:
            segs.append({"text": f"{title}\n", "tag": "toolitem", "url": link})
            segs.append({"text": f"     {link}\n", "tag": "toollink",
                         "url": link})
        else:
            segs.append({"text": f"{title}\n", "tag": "toolitem"})
        if snip:
            segs.append({"text": f"     {snip}\n", "tag": "toolnote"})
    segs.append({"text": "\n", "tag": "toolnote"})
    return segs


def _fmt_webpage(d: dict, raw: str) -> list:
    """网页抓取返回（title/description/url/content）→ 页面信息卡。"""
    title = str(d.get("title") or "").strip() or _t("misc.webpage")
    desc = _clean_text(str(d.get("description") or ""))[:_SNIPPET_MAX]
    url = str(d.get("url") or "").strip()
    content = _clean_text(str(d.get("content") or ""))
    segs = [{"text": f"📄 {title}\n", "tag": "toolhead"}]
    if url:
        segs.append({"text": f"🔗 {url}\n", "tag": "toollink", "url": url})
    if desc:
        segs.append({"text": f"📝 {desc}\n", "tag": "toolnote"})
    if content:
        shown = content[:600]
        segs.append({"text": f"\n{shown}", "tag": "toolitem"})
        if len(content) > 600:
            segs.append({"text": " …\n", "tag": "toolnote"})
            segs.append({"text": _t("view.full") + "\n", "tag": "toollink",
                         "popup": (_t("popup.page", title=title), raw)})
        else:
            segs.append({"text": "\n", "tag": "toolitem"})
    segs.append({"text": "\n", "tag": "toolnote"})
    return segs


def _fmt_plain(name: str, result: str) -> list:
    """纯文本返回：URL 行可点；形如搜索列表的按条目排版；超长折叠。"""
    lines = result.splitlines()
    n_urls = sum(1 for ln in lines
                 if ln.strip().startswith(("http://", "https://")))
    is_list = n_urls >= 2
    segs = []
    in_item = False
    for ln in lines:
        s = ln.strip()
        if s.startswith(("http://", "https://")) and " " not in s:
            segs.append({"text": f"     {s}\n", "tag": "toollink", "url": s})
            in_item = True
            continue
        m = _ITEM_RE.match(ln)
        if m and is_list:
            segs.append({"text": f"  {m.group(1)}. {m.group(2)}\n",
                         "tag": "toolitem"})
            in_item = True
            continue
        if s:
            tag = "toolnote" if (is_list and in_item) else "toolresult"
            body = f"     {s}" if (is_list and in_item) else ln
            segs.append({"text": body + "\n", "tag": tag})
        else:
            segs.append({"text": "\n", "tag": "toolresult"})
            in_item = False
    if len(result) > _DISPLAY_MAX:
        segs.append({"text": "\n" + _t("view.full") + "\n", "tag": "toollink",
                     "popup": (_t("popup.tool", name=name), result)})
    else:
        segs.append({"text": "\n", "tag": "toolresult"})
    return segs


def _format_tool_result(name: str, result: str) -> list:
    """工具返回 → 美化片段；识别不出的按纯文本展示（超长折叠可看全文）。"""
    data = _try_json(result)
    if _is_search_items(data):
        return _fmt_search_items(data)
    if isinstance(data, dict) and "url" in data \
            and ("content" in data or "title" in data):
        return _fmt_webpage(data, result)
    if data is not None:
        pretty = json.dumps(data, ensure_ascii=False, indent=2)
        segs = [{"text": _t("render.json"), "tag": "toolnote"}]
        if len(pretty) <= _DISPLAY_MAX:
            segs.append({"text": pretty + "\n\n", "tag": "toolresult"})
        else:
            segs.append({"text": pretty[:_DISPLAY_MAX] + "\n…\n",
                         "tag": "toolresult"})
            segs.append({"text": _t("view.full") + "\n", "tag": "toollink",
                         "popup": (_t("popup.tool", name=name), pretty)})
        return segs
    return _fmt_plain(name, result)


def _fmt_tool_args(args: dict) -> list:
    """工具入参 → 美化片段：每参一行「· 键: 值」，超长值截断。"""
    if not isinstance(args, dict) or not args:
        return []
    segs = []
    for k, v in args.items():
        try:
            text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        except Exception:  # noqa: BLE001  不可序列化的值退回 str
            text = str(v)
        text = text.replace("\n", " ")
        if len(text) > 90:
            text = text[:90] + "…"
        segs.append({"text": f"  · {k}: {text}\n", "tag": "toolnote"})
    return segs


class App:
    def __init__(self, root):
        # 读界面语言（默认英文）并在构建 UI 前生效
        _load_lang()
        self.root = root
        root.title(_app_title())
        _set_app_icon(root)
        root.geometry("1000x720")
        root.minsize(760, 560)
        # 启动即最大化（兼容 Windows/多平台，失败则保留默认尺寸）
        try:
            root.state("zoomed")
        except Exception:                # noqa: BLE001
            try:
                root.attributes("-zoomed", True)
            except Exception:            # noqa: BLE001
                pass

        # 加载模型列表 + 默认模型
        self.models, default_key = config.load_models()
        self.model_map = {m.key: m for m in self.models}
        self.current_model = self.model_map.get(default_key) or (
            self.models[0] if self.models else None)

        # 端点模型动态探测：打开模型菜单前自动拉各端点 /models 补全下拉
        self._endpoint_sync_at = 0.0           # 上次探测时间戳
        self._endpoint_syncing = False         # 探测进行中标记
        self._endpoint_lock = threading.Lock()

        # 当前权限模式
        self.mode = agent_mod.MODE_ASK

        # 转轮动画状态
        self._spinner_after = None
        self._spinner_idx = 0
        self._spinner_base = ""

        # token 统计（跨对话累计，点统计栏清零）
        self.usage_total = {
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "cached_tokens": 0, "reasoning_tokens": 0, "requests": 0,
        }
        # 缓存命中（LLM 回复 + 工具结果）
        self.cache_hits = 0
        self.cache_saved_tokens = 0

        # 当前会话：None = 未开始（首条消息时创建）
        self.session_id = None
        self.session_title = _t("sess.new")
        self.messages = None

        # 附件（待发送文件路径）与媒体控件引用（防 Tkinter GC）
        self._pending_attachments = []
        self._md_block = None   # 当前助手文本块起始位置（Markdown 重排用）
        self._md_buf: list[str] = []

        self._msg_queue: list[str] = []        # 排队消息（Ctrl+Enter 发送全部）
        self._media_refs = []
        # 可点链接/弹窗标签的递增序号
        self._link_seq = 0
        self._route_override = "auto"   # 路由覆盖：auto/cloud（侧栏按钮切换）
        # 界面字号（持久化）：聊天区 / 代码编辑器分别可调
        self._font_chat = config.get_font_size_chat()
        self._font_editor = config.get_font_size_editor()

        self._build_ui()
        self._append_style()
        self._update_workspace_label()
        # 关闭窗口时停掉 MCP 子进程
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        # 后台连接 MCP 服务器（有配置才连，不阻塞界面）
        self._start_mcp()
        # 派发守护：定时核验条件（本地大脑运行 + 云端可达），不满足自动关掉
        self._dispatch_cloud_fails = 0   # 云端连续探测失败次数（≥2 才关，防抖动）
        threading.Thread(target=self._dispatch_check_loop, daemon=True).start()
        # 启动即预热一次端点模型探测（后台），让下拉尽快带上全部可用模型
        self._maybe_sync_endpoints()
        # 启动时探测工作区开发语言，预热对应 LSP 服务器（多语言智能提示）
        self._lsp_warmed = set()
        threading.Thread(target=self._lsp_warm_loop, daemon=True).start()

    # ================= 构建界面 =================
    def _icon_button(self, parent, icon, hint, command, font_size=None, image=True):
        """纯图标工具按钮：完整含义悬停经状态栏显示（hint 可传 lambda 实时取）。
        Windows 优先 PNG 图片（Tk 9.0 渲染不了彩色 emoji 字形），否则回退字体；
        image=False 强制字体模式（按钮后续要显示文字的场景，如会话标题）。"""
        if image:
            btn = _flat_emoji_button(parent, icon, command,
                                     font_size=font_size or theme.FS_ICON)
        else:
            btn = _flat_button(parent, text=icon, command=command, width=2,
                               font=(FONT_EMOJI, font_size or theme.FS_ICON))
        btn.bind("<Enter>",
                 lambda _e: self._set_status(hint() if callable(hint) else hint))
        btn.bind("<Leave>", lambda _e: self._set_status(""))
        return btn

    def _build_ui(self):
        # ---- 顶部菜单（整行全宽，位于下方三栏之上）----
        ctrl = tk.Frame(self.root)
        ctrl.pack(fill="x", padx=16, pady=(10, 4))

        _mb_img = _icon_image("🤖")
        if _mb_img is not None:
            # Windows PNG：机器人图 + 模型名图文混排（Tk 9.0 渲染不了彩色 emoji 字形）
            self.model_btn = _image_button(ctrl, _mb_img,
                                           command=self._show_model_menu)
            self.model_btn.config(text=self._model_btn_text(), compound="left",
                                  font=(FONT_MONO, theme.FS_TOOLBAR), fg=theme.TEXT)
        else:
            self.model_btn = _flat_button(
                ctrl, text=self._model_btn_label(),
                command=self._show_model_menu, width=self._model_btn_width(), font=(FONT_MONO, theme.FS_TOOLBAR))
        # 模型名首字母与下方输入框文字精确左对齐：
        # 按钮内距=输入框内距(12)，文字左锚定（短模型名也顶格不居中）
        self.model_btn.config(padx=12, bd=0, highlightthickness=0, anchor="w")
        self.model_btn.pack(side="left", padx=(0, 10))

        # 思考按钮：只选等级（模型默认/关闭），点击弹等级列表
        self.think_btn = self._icon_button(
            ctrl, "🧠", lambda: "🧠 " + self._think_btn_text(),
            self._show_think_menu)
        self.think_btn.pack(side="left", padx=(0, 10))
        self._update_thinking_btn()

        # 设置按钮：管理模型 / MCP / 缓存 / 派发 / 代码索引 / 语言——从模型菜单独立出来
        _set_img = _icon_image("⚙")
        if _set_img is not None:
            self.settings_btn = _image_button(ctrl, _set_img,
                                              command=self._show_settings_menu)
        else:
            self.settings_btn = _flat_button(
                ctrl, text="⚙",
                command=self._show_settings_menu,
                width=3,
                font=(FONT_UI, theme.FS_TOOLBAR))
            self.settings_btn.config(padx=10, bd=0, highlightthickness=0)
        self.settings_btn.pack(side="left", padx=(0, 6))

        self.sess_btn = self._icon_button(
            ctrl, "💬", lambda: _t("top.sessions"), self._show_session_menu,
            image=False)
        self.sess_btn.pack(side="left", padx=(0, 10))


        # 上下文开关：续上下文（默认）/ 独立提问（每条消息不带历史）
        self.ctx_btn = self._icon_button(
            ctrl, _ctx_btn_icon(), lambda: _t(_ctx_label_key()),
            self._toggle_ctx)
        self.ctx_btn.pack(side="left", padx=(0, 10))

        # 模型派发快捷开关：左键切换开/关；右键打开派发设置面板
        # ● = 大脑运行中（派发生效） / ○ = 大脑未运行（视为未生效）
        # 产品开关：dispatch=false（纯云端/创作版）不建此按钮
        self.dispatch_btn = None
        if _feature("dispatch"):
            self.dispatch_btn = _flat_button(
                ctrl, text="⚡",
                command=self._toggle_dispatch, width=2, font=(FONT_EMOJI, theme.FS_ICON))
            self.dispatch_btn.pack(side="left", padx=(0, 10))
            self.dispatch_btn.bind("<Button-3>",
                                   lambda e: self._manage_dispatch())
            self.dispatch_btn.bind(
                "<Enter>", lambda e: self._set_status(_t("dispatch.topbar.hint")))
            self.dispatch_btn.bind(
                "<Leave>", lambda e: self._set_status(""))
            self._update_dispatch_btn()

        # 量化产品：策略互转面板入口（其它产品不建此按钮）
        if _feature("quant", False):
            _flat_emoji_button(ctrl, "📈",
                               command=self._open_quant_panel).pack(side="left", padx=(0, 10))

        # 公司知识库（企业代码 RAG）：知识库管理面板入口（rag 功能开关）
        if _feature("rag", False):
            _flat_emoji_button(ctrl, "📚",
                               command=self._open_kb_panel).pack(side="left", padx=(0, 10))

        self.dir_label = tk.Label(ctrl, text="📁 " + _t("top.dir"), font=(FONT_MONO, 10))
        self.dir_label.pack(side="left")
        self.ws_var = tk.StringVar(value="")
        self.ws_label = tk.Label(ctrl, textvariable=self.ws_var,
                                 font=(FONT_MONO, 10), cursor="hand2")
        self.ws_label.pack(side="left", padx=4)
        self.ws_label.bind("<Button-1>", lambda e: self._change_workspace())
        self.ws_label.bind("<Enter>", lambda e: self.ws_label.config(font=(FONT_MONO, 10, "underline")))
        self.ws_label.bind("<Leave>", lambda e: self.ws_label.config(font=(FONT_MONO, 10)))
        # Git 分支徽标（⧉ master / ⧉ dev）——在当前工作区目录后
        self.branch_var = tk.StringVar(value="")
        self.branch_label = tk.Label(ctrl, textvariable=self.branch_var,
                                     font=(FONT_MONO, 10), fg="#2563eb")
        self.branch_label.pack(side="left", padx=(0, 8))

        # 帮助按钮（最右上角，图标点击打开帮助窗口）
        _flat_emoji_button(ctrl, "❓", command=self._show_help,
                           width=3).pack(side="right", padx=(0, 12))

        # 中英语言切换按钮（点一下切换界面语言）——「仅中文」产品不显示
        self.lang_btn = None
        if not _feature("zh_only", False):
            self.lang_btn = _flat_button(
                ctrl, text="中/EN", command=self._toggle_lang,
                width=5, font=(FONT_MONO, theme.FS_TOOLBAR))
            self.lang_btn.pack(side="right", padx=(0, 6))

        # 字号调节（Aa）：聊天 / 编辑器分别 −/＋，实时生效并持久化
        _flat_button(ctrl, text="Aa", command=self._show_font_popup,
                     width=3, font=(FONT_MONO, theme.FS_TOOLBAR)).pack(side="right", padx=(0, 6))

        # 状态文字（"就绪"等，置于帮助按钮左侧）
        self.status_label = tk.Label(ctrl, text=_t("top.ready"), font=(FONT_MONO, 10))
        self.status_label.pack(side="right", padx=(0, 8))

        # ---- 下方三栏（可拖动，栏间隔 2px）：左会话 | 中主区 | 右文件 ----
        self.paned = tk.PanedWindow(self.root, orient="horizontal",
                                    sashwidth=2, sashrelief="flat", bd=0,
                                    background=theme.BORDER)
        self.paned.pack(fill="both", expand=True)
        self._build_sidebar()                 # 左：会话树（工作区分组）
        self.center = tk.Frame(self.paned)    # 中：主区（聊天+统计+输入）
        self.paned.add(self.center, minsize=300, stretch="always")
        self._file_views: dict = {}           # 编辑器视图注册表（无 editor 产品为空）
        if _feature("editor"):
            self._build_file_panel()          # 右：文件树(树|编辑区)

        # ---- 聊天区 ----
        # 任务步骤(todo)清单：从模型输出的步骤识别，实时显示并可在界面勾选
        self.todo_frame = tk.Frame(self.center)
        # 任务步骤(todo)清单：从模型输出的步骤识别，实时显示并可在界面勾选
        self.todo_items: list[dict] = []   # {"label": str, "done": bool}
        self._todo_tool_current: str | None = None   # 底部临时「正在执行」行
        self._has_plan = False              # 是否已收到 task_plan 计划
        self.chat = scrolledtext.ScrolledText(
            self.center, state="disabled", wrap="word",
            font=(FONT_MONO, self._font_chat), padx=16, pady=12,
            relief="flat", borderwidth=0,
            background=theme.PANEL, fg=theme.TEXT)
        self.chat.pack(fill="both", expand=True, padx=16, pady=(0, 4))
        self._setup_chat_copy()
        # Esc：运行中 = 停止任务（审批/帮助弹窗自有 Esc 绑定，grab 期间不冲突）
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<Control-Shift-f>", lambda e: self._trigger_screenshot())
        self.root.bind("<Control-Shift-F>", lambda e: self._trigger_screenshot())
        self.root.bind("<Control-F2>", lambda e: self._trigger_screenshot())

        # token 统计栏
        stat = tk.Frame(self.center)
        self.stat_frame = stat
        stat.pack(fill="x", padx=16, pady=(0, 6))
        self.stat_var = tk.StringVar(value=_stat_text(
    {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
     "cached_tokens": 0, "requests": 0}))
        stat_label = tk.Label(stat, textvariable=self.stat_var,
                              font=(FONT_MONO, theme.FS_STAT), fg="#64748b", anchor="w")
        stat_label.pack(side="left")
        # 点击统计栏 = 清零
        stat_label.bind("<Button-1>", lambda e: self._reset_usage())
        stat_label.bind("<Enter>", lambda e: stat_label.config(fg="#0f172a", cursor="hand2"))
        stat_label.bind("<Leave>", lambda e: stat_label.config(fg="#64748b"))

        # 动态状态徽标：空闲/进行中（转轮）/完成（✓），与统计栏同行居右
        self.status_badge = tk.Label(stat, text=_t("status.idle"),
                                     font=(FONT_MONO, theme.FS_STAT), fg="#94a3b8",
                                     anchor="e")
        self.status_badge.pack(side="right")
        # 附件按钮：放在「空闲」徽标前面（同 pack side=right，后 pack 者在其左）
        # 字号用 FS_STAT（与同行统计/徽标一致，不用 FS_TOOLBAR——大两号很扎眼）
        self.attach_btn = _flat_button(stat, text=_t("top.attach"),
                                       command=self._pick_attachments,
                                       font=(FONT_MONO, theme.FS_STAT))
        self.attach_btn.pack(side="right", padx=(0, 8))
        self._badge_after = None
        self._badge_idx = 0

        # ---- 附件预览条（有待发附件时显示）----
        self.attach_bar = tk.Frame(self.center)
        # 不立即 pack：_render_attachments 里按需显示/隐藏

        # ---- 输入区 ----
        bottom = tk.Frame(self.center)
        bottom.pack(fill="x", padx=16, pady=(0, 14))

        # 排队消息栏（Ctrl+Enter 排队发送全部；每条可✎编辑/✕删除）
        self.queue_bar = tk.Frame(bottom)
        self.queue_bar.pack(fill="x", pady=(0, 2))

        # DSH 式底部控制条：＋文件 | 访问级别 | 模型 | 🔄刷新
        ctrlbar = tk.Frame(bottom)
        ctrlbar.pack(fill="x", pady=(0, 4))
        self.cmd_plus = _flat_button(ctrlbar, text="＋",
                                     command=lambda: self._show_command_menu(anchor=self.cmd_plus),
                                     font=(FONT_MONO, theme.FS_ICON))
        self.cmd_plus.config(width=1, padx=8)
        self.cmd_plus.pack(side="left")
        self._icon_button(ctrlbar, "⏱", _t("q.queue"),
                          self._queue_current).pack(side="left", padx=(4, 0))
        self.bottom_mode_btn = self._icon_button(
            ctrlbar, MODE_ICON.get(self.mode, "🛡"),
            lambda: _mode_btn_label(self.mode),
            lambda: self._show_mode_menu(anchor=self.bottom_mode_btn))
        self.bottom_mode_btn.pack(side="left", padx=(4, 0))
        self.bottom_model_btn = self._icon_button(
            ctrlbar, "🤖", lambda: self._model_btn_label(),
            lambda: self._show_model_menu(anchor=self.bottom_model_btn))
        self.bottom_model_btn.pack(side="left", padx=(4, 0))
        self.bottom_think_btn = self._icon_button(
            ctrlbar, "🧠", lambda: "🧠 " + self._think_btn_text(),
            lambda: self._show_think_menu(anchor=self.bottom_think_btn))
        self.bottom_think_btn.pack(side="left", padx=(4, 0))
        self.bottom_route_btn = self._icon_button(
            ctrlbar, "🔀", lambda: self._route_mode_text(),
            self._cycle_route_override)
        self.bottom_route_btn.pack(side="right", padx=(4, 0))
        _flat_emoji_button(ctrlbar, "\U0001F4F8",
                           command=self._trigger_screenshot).pack(side="right", padx=(4, 0))
        _flat_emoji_button(ctrlbar, "🔄",
                           command=self._refresh_all).pack(side="right", padx=(4, 0))

        self.input = tk.Text(bottom, height=3, width=8,
                             font=(FONT_MONO, self._font_chat + 1), wrap="word",
                             relief="flat", padx=12, pady=10, highlightthickness=0)
        self.input.pack(side="left", fill="both", expand=True)
        # 回车发送；Shift+回车换行；Ctrl+回车排队（聊天软件标准行为）
        # 弹窗（@ 文件、/ 命令）打开时，回车优先确认候选——全部在
        # _on_input_keypress（KeyPress 阶段）统一处理，见下方绑定与处理器
        self.input.bind("<Control-Return>", lambda e: self._send_queued())
        self.input.bind("<Control-space>", lambda e: self._queue_current())
        self.input.bind("<Command-Return>", lambda e: self._send_queued())
        self._setup_placeholder()
        # 弹窗导航/确认 + 无弹窗时的回车发送，都在 KeyPress 阶段拦截，
        # 否则回车先被 Text 插入换行、方向键先移动光标
        self.input.bind("<KeyPress>", self._on_input_keypress)
        self.input.bind("<KeyRelease>", self._input_on_keyrelease)

        btn_col = tk.Frame(bottom)
        btn_col.pack(side="right", fill="y", padx=(10, 0))

        # 🎤 语音输入（单按钮）：按下即录音——长按松手停止（按住说话），
        # 轻点一下切换为自动停顿检测（静音 1.5s 自动结束）
        # 三个按钮 fill=both + expand：在按钮列里纵向均分，与 3 行输入框对齐
        self.voice_btn = _flat_button(btn_col, text=_t("btn.voice"),
                                      width=3, command=None, font=(FONT_MONO, theme.FS_TOOLBAR))
        self.voice_btn.pack(fill="both", expand=True)
        self.voice_btn.bind("<ButtonPress-1>", self._voice_press)
        self.voice_btn.bind("<ButtonRelease-1>", self._voice_release)
        self._bind_hint(self.voice_btn, "top.voice")

        self.send_btn = _flat_button(btn_col, text=_t("btn.send"),
                                     width=3, command=self._on_send_or_stop,
                                     font=(FONT_MONO, theme.FS_TOOLBAR))
        self.send_btn.pack(fill="both", expand=True, pady=(4, 0))
        self._bind_hint(self.send_btn, "top.send")
        self._stop_requested = False
        self._running = False

        _clear_btn = _flat_button(btn_col, text=_t("btn.clear"), width=3,
                                  command=self.clear, font=(FONT_MONO, theme.FS_TOOLBAR))
        _clear_btn.pack(fill="both", expand=True, pady=(4, 0))
        self._bind_hint(_clear_btn, "top.clear")

    # ---- 左侧工作区/会话列表 ----
    _TOOL_LABEL = {"read_file": "\U0001F4D6 读文件", "write_file": "\u270F\uFE0F 写文件",
                   "run_shell": "\U0001F50D 执行", "grep_search": "\U0001F50E 搜索",
                   "glob_search": "\U0001F525 找文件", "index_search": "\U0001F5C2 索引搜索",
                   "web_search": "\U0001F310 联网", "call_model": "\U0001F916 委派",
                   "lsp_diagnostics": "\U0001F52C 诊断"}

    def _todo_tool_label(self, name: str, args: dict) -> str:
        base = self._TOOL_LABEL.get(name, "\U0001F527 " + (name or "工具"))
        import os as _os
        path = (args or {}).get("path")
        if name == "run_shell":
            cmd = (args or {}).get("command", "").split("\n")[0]
            if cmd:
                return base + " " + cmd[:26]
        if path:
            return base + " " + _os.path.basename(str(path))[:26]
        return base

    _SPIN = "◐◓◑◒"

    def _todo_start(self, name: str, args: dict):
        if name == "write_file":
            pth = (args or {}).get("path")
            if pth and getattr(self, "_file_tabs", {}).get(pth):
                self._editor_status_animate(pth)
        label = self._todo_tool_label(name, args)
        # 工具调用不再作为步骤追加（读了个啥就列一行，无意义）——
        # 步骤只来自 task_plan 计划；工具只更新底部一行临时「正在执行」
        self._todo_tool_current = label
        for it in self.todo_items:
            if not it.get("done"):
                it["state"] = "working"
                it["spin"] = 0
                break
        self._render_todo()
        self._todo_animate()

    def _todo_done(self, name: str):
        if name == "write_file":
            pth = getattr(self, "_pending_write_path", None)
            if pth and getattr(self, "_file_tabs", {}).get(pth):
                self._editor_status_stop(pth)
                self._editor_status(pth, "\u2705")
        self._todo_tool_current = None
        if not getattr(self, "_has_plan", False):
            # 非计划模式（处理中占位/文本扫描项）：保持原来的完成推进
            for it in self.todo_items:
                if it.get("state") == "working":
                    it["state"] = "done"
                    it["done"] = True
                    break
        # 计划模式下步骤完成与否由模型经 task_plan 更新
        self._render_todo()

    def _todo_from_plan(self, steps):
        """task_plan 下发的计划 → 任务步骤清单（'[x] ' 前缀视为已完成）。"""
        items = []
        for s in steps or []:
            s = str(s).strip()
            if not s:
                continue
            low = s.lower()
            done = False
            if low.startswith("[x] "):
                done = True
                s = s[4:].strip()
            elif low.startswith("[ ] "):
                s = s[4:].strip()
            items.append({"label": s, "done": done,
                          "state": "done" if done else "pending"})
        self.todo_items = items
        self._render_todo()

    def _todo_animate(self):
        """进行中的 todo 项：旋转 spinner（修改文件的"效果动画"）。"""
        idx = next((i for i, it in enumerate(self.todo_items)
                    if it.get("state") == "working"), None)
        if idx is None:
            if getattr(self, "_todo_after", None):
                try: self.root.after_cancel(self._todo_after)
                except Exception: pass
                self._todo_after = None
            return
        it = self.todo_items[idx]
        it["spin"] = (it.get("spin", 0) + 1) % len(self._SPIN)
        if idx < len(getattr(self, "todo_rows", [])):
            try:
                self.todo_rows[idx].config(text=self._SPIN[it["spin"]] + " " + it["label"])
            except Exception:            # noqa: BLE001
                pass
        self._todo_after = self.root.after(150, self._todo_animate)

    def _scan_todo(self, text: str):
        """从文本里识别步骤行：① 数字开头 '1) / 1. / 步骤1'；② '- [ ] / - [x]'。"""
        import re as _re
        items = []
        for line in text.split("\n"):
            s = line.strip()
            m = _re.match(r"^(\d+)[\.\)]\s+(.+)$", s) or \
                _re.match(r"^(?:步骤|step)\s*\d+\s*[:：]\s*(.+)$", s, _re.I) or \
                _re.match(r"^[-*]\s*\[([ xX])\]\s+(.+)$", s)
            if m:
                if len(m.groups()) >= 2:
                    done = m.group(1).lower() == "x"   # '- [ ]'=未完成, '- [x]'=完成
                    label = m.group(2)
                else:
                    done = False
                    label = m.group(1)
                items.append({"label": label.strip(), "done": bool(done)})
        return items

    def _render_todo(self):
        for w in self.todo_frame.winfo_children():
            w.destroy()
        self.todo_frame.config(bg=theme.PANEL)
        # 无条目，或全部完成 → 不再显示（完成后自动消失）
        if not self.todo_items:
            self.todo_frame.pack_forget()
            return
        try:
            self.todo_frame.pack(fill="x", padx=16, pady=(0, 2), after=self.chat)
        except Exception as e:            # noqa: BLE001
            self.todo_frame.pack(fill="x", padx=16, pady=(0, 2))
        # 头部一行：📋 任务步骤 (n)  [▾/▴]
        hdr = tk.Frame(self.todo_frame, bg=theme.PANEL)
        hdr.pack(fill="x")
        tk.Label(hdr, text="\U0001F4CB " + _t("todo.title"),
                 font=(FONT_UI, 10, "bold"), fg="#334155").pack(side="left", padx=(0, 6))
        tk.Label(hdr, text="({})".format(len(self.todo_items)),
                 font=(FONT_UI, 9), fg="#94a3b8").pack(side="left", padx=(0, 4))
        if not hasattr(self, "_todo_collapsed"):
            self._todo_collapsed = False
        arrow = "\u25be" if not self._todo_collapsed else "\u25b4"
        _flat_button(hdr, text=arrow, width=2, command=self._toggle_todo_collapse,
                     font=(FONT_MONO, theme.FS_TOOLBAR)).pack(side="right", padx=(4, 0))
        if self._todo_collapsed:
            return
        # 条目：从上到下（DSH 式）；最多显示 6 条，超出用滚动条/滚轮下拉
        body = tk.Frame(self.todo_frame, bg=theme.PANEL)
        body.pack(fill="x")
        canvas = tk.Canvas(body, bg=theme.PANEL, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(body, orient="vertical", command=canvas.yview,
                          width=10)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=theme.PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _toggle(idx, var):
            var.set(not var.get())
            self.todo_items[idx]["done"] = var.get()
            self.todo_rows[idx].config(
                text=("\u2611 " if var.get() else "\u2610 ") + self.todo_items[idx]["label"])
        self.todo_rows = []

        def _wheel(e):
            canvas.yview_scroll(-1 * (e.delta // 120 or 1), "units")
        canvas.bind("<MouseWheel>", _wheel)
        inner.bind("<MouseWheel>", _wheel)

        for i, it in enumerate(self.todo_items):
            st = it.get("state", "done" if it["done"] else "pending")
            if it["done"]:
                prefix = "\u2705 "
                color = "green"
            elif st == "working":
                prefix = self._SPIN[it.get("spin", 0)] + " "
                color = "#2563eb"
            else:
                prefix = "\u2610 "
                color = "#475569"
            var = tk.BooleanVar(value=it["done"])
            lb = tk.Label(inner, text=prefix + it["label"],
                          font=(FONT_UI, 9), fg=color, bg=theme.PANEL,
                          cursor="hand2", anchor="w", justify="left")
            lb.pack(side="top", fill="x", anchor="w", padx=(2, 0))
            lb.bind("<Button-1>", lambda e, i=i, v=var: _toggle(i, v))
            lb.bind("<MouseWheel>", _wheel)
            self.todo_rows.append(lb)

        # 可视高度 = min(内容高, 6 行)；内容不足 6 行时按内容收缩
        _TODO_MAX_ROWS = 6

        def _fit():
            inner.update_idletasks()
            row_h = max(22, (self.todo_rows[0].winfo_reqheight() + 4)
                        if self.todo_rows else 26)
            canvas.configure(height=min(inner.winfo_reqheight(),
                                        row_h * _TODO_MAX_ROWS))
        inner.after(10, _fit)
        # 底部一行灰显当前正在执行的工具（临时行，不进清单）
        cur = getattr(self, "_todo_tool_current", None)
        if cur:
            tk.Label(self.todo_frame, text="  \u2699 " + cur + "…",
                     font=(FONT_UI, 9), fg="#94a3b8", bg=theme.PANEL,
                     anchor="w",
                     justify="left").pack(side="top", fill="x", anchor="w")
        # 确保有一条"进行中"（第一个未完成），展示旋转动画
        if not any(it.get("state") == "working" for it in self.todo_items):
            for it in self.todo_items:
                if not it["done"]:
                    it["state"] = "working"
                    it["spin"] = 0
                    break
        self._todo_animate()

    def _toggle_todo_collapse(self):
        self._todo_collapsed = not getattr(self, "_todo_collapsed", False)
        self._render_todo()

    def _clear_todo(self):
        self.todo_items = []
        self._has_plan = False
        self._todo_tool_current = None
        self._render_todo()

    def _update_todo(self):
        # 抓模型的计划步骤（1)…2)…），先建立清单（DSH 式：先有、再推进）
        # 计划模式下步骤以 task_plan 下发为准，不再从正文文本扫描
        if getattr(self, "_has_plan", False):
            return
        import re as _re
        if getattr(self, "_todo_collapsed", False):
            return
        try:
            buf = "".join(getattr(self, "_md_buf", []) or [])
            plan = self._scan_todo(buf)
            if not plan:
                return
            old = self.todo_items
            new = []
            for p in plan:
                old_it = next((it for it in old if it["label"] == p["label"]), None)
                done = old_it["done"] if old_it else p["done"]
                state = old_it.get("state") if old_it else ("done" if p["done"] else "pending")
                new.append({"label": p["label"], "done": done, "state": state})
            self.todo_items = new
            self._render_todo()
        except Exception:            # noqa: BLE001
            pass

    def _build_sidebar(self):
        import tkinter.ttk as ttk
        self._sidebar_loading = True
        # 左侧（对话/会话）框宽度 = 屏宽 15%，且最大不超过 280px
        screen_w = self.root.winfo_screenwidth()
        side_w = max(120, min(int(round(screen_w * 0.15)), 280))
        self.sidebar_frame = tk.Frame(self.paned, width=side_w)
        self.paned.add(self.sidebar_frame, minsize=120, stretch="never")
        self.sidebar_frame.pack_propagate(False)

        # 顶部标题 + 新建会话按钮 + 更多（搜索/全部/删除）
        head = tk.Frame(self.sidebar_frame)
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text="🗂 " + _t("sess.workspace"), font=(FONT_UI, 10, "bold")).pack(side="left")
        # 路由模式按钮：自动/本地/云端 循环（local 保存自动路由，仅覆盖当前轮）
        self._route_btn = _flat_emoji_button(
            head, "🔀", command=self._cycle_route_override)
        self._route_btn.pack(side="right", padx=(6, 0))
        self._bind_hint(self._route_btn, "route.auto")
        self._sidebar_more = _flat_button(
            head, text="⋯", command=lambda: self._show_session_menu(anchor=self._sidebar_more),
            font=(FONT_MONO, 9))
        self._sidebar_more.pack(side="right", padx=(4, 0))
        _flat_button(head, text=_t("top.new_session"), command=self._new_session,
                     font=(FONT_MONO, 9)).pack(side="right", padx=(6, 0))

        self.sidebar = ttk.Treeview(self.sidebar_frame, show="tree", selectmode="browse",
                                    height=20, takefocus=1)
        # 树横向填满侧栏（fill=both+expand），否则树右侧会留一条空白竖条
        self.sidebar.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(self.sidebar_frame, orient="vertical", command=self.sidebar.yview)
        self.sidebar.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.sidebar.tag_configure("current", font=(FONT_UI, 10, "bold"),
                                   foreground=theme.ACCENT)
        self.sidebar.tag_configure("group", font=(FONT_UI, 9, "bold"),
                                   foreground=theme.MUTED)
        self.sidebar.tag_configure("stripe", background=theme.STRIPE)
        self.sidebar.bind("<<TreeviewSelect>>", self._on_sidebar_select)
        # 会话项：DEL 键删除；右键菜单（重命名 / 删除）
        self.sidebar.bind("<Delete>", self._sidebar_delete_selected)
        self.sidebar.bind("<Button-3>", self._sidebar_menu)
        self._refresh_sidebar()

    def _fmt_since(self, ts: float) -> str:
        """相对时间：刚刚 / N分钟 / N小时 / N天（跟随界面语言）。"""
        try:
            d = time.time() - float(ts)
        except (TypeError, ValueError):
            return ""
        if d < 60:
            return _t("time.now")
        if d < 3600:
            return _t("time.min", n=int(d // 60))
        if d < 86400:
            return _t("time.hr", n=int(d // 3600))
        return _t("time.day", n=int(d // 86400))

    def _refresh_sidebar(self):
        """按工作区分组刷新左侧会话树。

        行结构：工作区分组行 values=(ws,)；会话行 text=标题、
        values=(id, workspace, 完整标题)——DEL 删除、右键重命名/删除依赖 values。
        """
        if not hasattr(self, "sidebar"):
            return
        import os as _os
        import sessions as sess_mod
        self._sidebar_loading = True
        try:
            self.sidebar.delete(*self.sidebar.get_children())
            all_sessions = sess_mod.list_sessions(limit=1000)
            groups: dict[str, list] = {}
            for s in all_sessions:
                ws = s.get("workspace", "") or ""
                groups.setdefault(ws, []).append(s)
            # 有名字的工作区在前，未分组最后
            def _key(ws):
                return (0, ws) if ws else (1, "")
            for ws in sorted(groups, key=_key):
                if ws:
                    label = _os.path.basename(ws.rstrip("/\\")) or ws
                    parent = self.sidebar.insert(
                        "", "end", text=f"📁 {label}", open=True,
                        values=(ws,), tags=("group",))
                else:
                    parent = self.sidebar.insert(
                        "", "end", text=f"🗂 {_t('sess.ungrouped')}", open=True, values=("",))
                for i, s in enumerate(groups[ws]):
                    # 列表只显示标题（不显示时间）；完整标题存 values 供右键重命名用
                    title = (s.get("title") or _t("misc.no_title"))[:22]
                    tags = ("current",) if s.get("id") == getattr(self, "session_id", None) else ()
                    if i % 2:              # 隔行斑马纹（i 为组内序号）
                        tags = tags + ("stripe",)
                    self.sidebar.insert(parent, "end",
                                        text=title,
                                        values=(s["id"], s.get("workspace", "") or "",
                                                s.get("title") or ""),
                                        tags=tags)
        finally:
            self._sidebar_loading = False

    def _on_sidebar_select(self, _e=None):
        """点击左侧：工作区分组 = 切换展开/折叠（显示它下面的会话）；会话项 = 载入。"""
        if getattr(self, "_sidebar_loading", False):
            return
        sel = self.sidebar.selection()
        if not sel:
            return
        iid = sel[0]
        if self.sidebar.get_children(iid):     # 工作区分组 → 展开/收起（显示它下面的会话）
            if self.sidebar.item(iid, "open"):
                self.sidebar.item(iid, open=False)
            else:
                self.sidebar.item(iid, open=True)
            return
        vals = self.sidebar.item(iid, "values")
        if vals and vals[0]:
            self._load_session(vals[0])

    # ---- 编辑器面板宽度：点开编辑时窄面板自动扩到约半屏 ----
    def _editor_record_startup(self, _e=None):
        """只记第一次：编辑区初始渲染宽度 = 「启动时大小」的比较基准。"""
        if not getattr(self, "_editor_startup_w", 0):
            self._editor_startup_w = self.file_frame.winfo_width()

    def _editor_auto_expand(self):
        """点开编辑器：面板仍 ≤ 启动宽度（用户没主动拉大过）→ 扩到约半屏。

        共享内核行为，所有带编辑器的产品线一致；目标宽 = 屏宽一半，
        同时给左侧会话栏+聊天区至少留 560px。用户拉大过就不再动。
        """
        def _w():
            startup = getattr(self, "_editor_startup_w", 0)
            cur = self.file_frame.winfo_width()
            if not startup or not cur or cur > startup + 4:
                return                    # 用户已手动拉大 → 尊重现状
            screen_w = self.root.winfo_screenwidth()
            win_w = max(self.root.winfo_width(), self.paned.winfo_width())
            target = max(360, min(screen_w // 2, win_w - 560))
            if target <= cur:
                return
            try:
                self.paned.sash_place(1, self.paned.winfo_width() - target, 0)
            except Exception:             # noqa: BLE001  sash 未就绪则跳过
                pass
        self.root.after(60, _w)           # 等本次布局稳定再动分栏

    # ---- 侧栏会话项：DEL 删除 / 右键重命名·删除 ----
    def _sidebar_session_info(self, iid=None):
        """侧栏行对应的会话 (sid, 完整标题)；工作区分组行/无选中返回 None。"""
        iid = iid or (self.sidebar.selection() or [None])[0]
        if not iid or self.sidebar.get_children(iid):
            return None                       # 分组行或无选中
        vals = self.sidebar.item(iid, "values")
        if len(vals) < 3 or not vals[0]:
            return None
        return vals[0], vals[2]

    def _sidebar_delete_selected(self, _e=None):
        """删除侧栏选中会话（DEL 键 / 右键菜单）；删的是当前会话则新开一个。"""
        from tkinter import messagebox
        import sessions as sess_mod
        info = self._sidebar_session_info()
        if not info:
            return "break"
        sid, title = info
        if messagebox.askyesno(_t("sess.del_title"),
                               _t("sess.del_confirm", t=title)):
            sess_mod.delete(sid)
            if sid == getattr(self, "session_id", None):
                self._new_session()
            else:
                self._refresh_sidebar()
            self._set_status(_t("sess.deleted"))
        return "break"

    def _sidebar_rename_selected(self, _e=None):
        """重命名侧栏选中会话（右键菜单）：只改标题，不动更新时间。"""
        from tkinter import simpledialog
        import sessions as sess_mod
        info = self._sidebar_session_info()
        if not info:
            return "break"
        sid, title = info
        new = simpledialog.askstring(_t("sess.rename_title"),
                                     _t("sess.rename_prompt"),
                                     initialvalue=title, parent=self.root)
        if not new or new.strip() in ("", title):
            return "break"
        new = new.strip()
        if sess_mod.rename(sid, new):
            if sid == getattr(self, "session_id", None):
                self.session_title = new      # 后续保存沿用新标题
            self._refresh_sidebar()
            self._set_status(_t("sess.renamed", t=new))
        return "break"

    def _sidebar_menu(self, e):
        """右键菜单：会话项 = 重命名/删除；工作区分组 = 删除该目录全部会话。"""
        iid = self.sidebar.identify_row(e.y)
        if not iid:
            return
        menu = tk.Menu(self.root, tearoff=0, font=(FONT_UI, 10))
        if self.sidebar.get_children(iid):
            # 顶层工作区分组：删除该工作区（目录）下的全部会话，
            # 会话清空后分组节点随之消失
            vals = self.sidebar.item(iid, "values")
            ws = vals[0] if vals else ""
            sids = [self.sidebar.item(k, "values")[0]
                    for k in self.sidebar.get_children(iid)
                    if self.sidebar.item(k, "values")]
            if not sids:
                return
            menu.add_command(
                label=_t("sess.del_group", n=len(sids)),
                command=lambda: self._delete_sessions(sids, ws))
        else:
            self.sidebar.selection_set(iid)
            if not self._sidebar_session_info(iid):
                return
            menu.add_command(label=_t("sess.rename"),
                             command=self._sidebar_rename_selected)
            menu.add_command(label=_t("sess.del_btn"),
                             command=self._sidebar_delete_selected)
        menu.tk_popup(e.x_root, e.y_root)

    def _delete_sessions(self, sids, ws=""):
        """批量删除会话（工作区分组的「删除顶层」）；含当前会话则新开一个。"""
        from tkinter import messagebox
        import sessions as sess_mod
        label = ws or _t("sess.ungrouped")
        if not messagebox.askyesno(
                _t("sess.del_title"),
                _t("sess.del_group_confirm", ws=label, n=len(sids))):
            return
        for sid in sids:
            sess_mod.delete(sid)
        if any(sid == getattr(self, "session_id", None) for sid in sids):
            self._new_session()
        else:
            self._refresh_sidebar()
        self._set_status(_t("sess.deleted"))

    # ---- 右侧文件树（当前工作区文件，双击填入输入框）----
    def _build_file_panel(self):
        import tkinter.ttk as ttk
        self.file_frame = tk.Frame(self.paned)
        self.paned.add(self.file_frame, minsize=240, stretch="never")

        # 自定义标签栏（Cursor 式）：蓝色文件名 + ✕，紧凑，默认只读防误改
        self.file_tabbar = tk.Frame(self.file_frame)
        self.file_tabbar.pack(fill="x", pady=(0, 2))
        self.file_content = tk.Frame(self.file_frame)
        self.file_content.pack(fill="both", expand=True)
        self._file_views: dict = {}      # view_id -> content frame
        self._file_tabs: dict = {}       # path -> (tab_frame, name_lbl, cls_lbl, view_id)
        self._file_tab_by_view: dict = {}  # view_id -> path (None for files view)
        self._file_active_view = None

        # 文件树视图（默认激活）
        tree_view = tk.Frame(self.file_content)
        self._file_views["__files__"] = tree_view
        self._file_tab_by_view["__files__"] = None

        # 搜索框 + 刷新按钮
        srow = tk.Frame(tree_view)
        srow.pack(fill="x", padx=6, pady=(6, 4))
        self.file_search = tk.Entry(srow, font=(FONT_MONO, 10))
        self.file_search.pack(side="left", fill="x", expand=True)
        self.file_search.insert(0, _t("file.search"))
        self.file_search.bind("<FocusIn>", lambda e: (self.file_search.delete(0, "end"),
                                                     self.file_search.config(fg="black"))
                              if self.file_search.get() == _t("file.search") else None)
        self.file_search.bind("<FocusOut>", lambda e: (self.file_search.insert(0, _t("file.search")),
                                                       self.file_search.config(fg="gray"))
                              if not self.file_search.get() else None)
        self.file_search.bind("<KeyRelease>", lambda e: self._apply_file_filter(self.file_search.get()))
        _flat_emoji_button(srow, "🔄", command=self._refresh_file_panel,
                           font_size=theme.FS_TOOLBAR).pack(side="left", padx=(6, 0))

        # 文件树
        self.file_tree = ttk.Treeview(tree_view, show="tree", selectmode="browse")
        self.file_tree.pack(side="left", fill="both", expand=True, padx=(6, 0))
        sb = ttk.Scrollbar(tree_view, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.file_tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_select)
        self.file_tree.bind("<Button-1>", self._on_file_click)
        self.file_tree.bind("<Button-3>", self._on_file_right)
        self._bind_file_tree_drag()   # 文件树条目可拖拽加入对话

        # 记录启动宽度基准（点开编辑自动扩到半屏的比较用，见 _editor_auto_expand）
        self._editor_startup_w = 0
        self.file_frame.bind("<Configure>", self._editor_record_startup, add="+")
        self._file_add_tab("__files__", _t("panel.files"), closable=False)
        self._file_select_view("__files__")
        self._refresh_file_panel()

    # ---- 文件标签栏（Cursor 式）----
    _TAB_ON = "#2563eb"
    _TAB_OFF = "#e2e8f0"
    _TAB_FG_ON = "#ffffff"
    _TAB_FG_OFF = "#334155"

    # 编辑器标签的修改状态图标：进行中 ◐ 动画 → 完成 ✓
    def _editor_status(self, path, icon=None):
        name_lbl = self._file_tabs.get(path, (None, None, None))[1] if path in self._file_tabs else None
        if name_lbl is None:
            return
        base = os.path.basename(str(path))
        name_lbl.config(text=(icon + "  " if icon else "") + base)

    def _editor_status_animate(self, path):
        """进行中：tab 前缀旋转 ◐◓◑◒；完成时 _editor_status_stop 置False即停。"""
        spin = "◐◓◑◒"
        if not hasattr(self, "_editor_anim"):
            self._editor_anim = {}
        self._editor_anim[path] = True
        def _tick(i=0):
            if not self._editor_anim.get(path) or self._file_tabs.get(path) is None:
                return
            self._editor_status(path, spin[(i) % len(spin)])
            self.root.after(150, lambda: _tick(i + 1))
        _tick(0)

    def _editor_status_stop(self, path):
        """写文件完成：停止该 tab 的旋转动画。"""
        if hasattr(self, "_editor_anim"):
            self._editor_anim[path] = False

    def _file_add_tab(self, view_id, label, closable=True):
        """新增/更新一个顶部标签按钮；view_id='__files__' 例外（文件树）。"""
        yes_txt = str(label)
        tab = tk.Frame(self.file_tabbar, bg=self._TAB_ON, bd=0,
                       highlightbackground="#cbd5e1", highlightthickness=1)
        name_lbl = tk.Label(tab, text=yes_txt, bg=self._TAB_ON, fg=self._TAB_FG_ON,
                            font=(FONT_UI, 9), padx=6, pady=3, cursor="hand2")
        name_lbl.pack(side="left")
        cls_lbl = None
        if closable:
            cls_lbl = tk.Label(tab, text=" ✕", bg=self._TAB_ON, fg=self._TAB_FG_ON,
                               font=(FONT_UI, 9), cursor="hand2")
            cls_lbl.pack(side="left")
            cls_lbl.bind("<Button-1>", lambda e, v=view_id: self._file_close_view(v))
        name_lbl.bind("<Button-1>", lambda e, v=view_id: self._file_select_view(v))
        tab.pack(side="left", padx=(0, 3))
        self._file_tabs[view_id] = (tab, name_lbl, cls_lbl)
        if closable and view_id != "__files__":
            self._bind_tab_drag(name_lbl, view_id)   # 标签可拖拽加入对话
        return tab

    @staticmethod
    def _point_over_widget(widget, gx, gy):
        """全局坐标 (gx, gy) 是否落在 widget 矩形内（用根坐标判断放下位置）。"""
        if not widget:
            return False
        try:
            x, y = widget.winfo_rootx(), widget.winfo_rooty()
            w, h = widget.winfo_width(), widget.winfo_height()
            return x <= gx <= x + w and y <= gy <= y + h
        except Exception:            # noqa: BLE001
            return False

    def _bind_tab_drag(self, name_lbl, view_id):
        """让文件标签可拖拽：按住拖到聊天输入区/消息区放下 = 加入对话。

        效果等同在文件树选中文件后「添加到对话」：追加到待发送附件栏。
        无位移的普通点击仍走原点击逻辑（切换视图），不触发拖拽。
        """
        import os as _os
        path = self._file_tab_by_view.get(view_id)
        if not path:
            return
        drag = {"sx": 0, "sy": 0, "moved": False, "ghost": None}

        def _press(e):
            drag["sx"], drag["sy"] = e.x_root, e.y_root
            drag["moved"] = False

        def _motion(e):
            # 未超过阈值视为点击，不弹拖影
            if abs(e.x_root - drag["sx"]) < 6 and abs(e.y_root - drag["sy"]) < 6:
                return
            drag["moved"] = True
            if drag["ghost"] is None:
                g = tk.Toplevel(self.root)
                g.overrideredirect(True)
                try:
                    g.attributes("-topmost", True)
                except Exception:    # noqa: BLE001
                    pass
                tk.Label(g, text="📄 " + _os.path.basename(path),
                         bg=self._TAB_ON, fg=self._TAB_FG_ON,
                         font=(FONT_UI, 9), padx=8, pady=4).pack()
                drag["ghost"] = g
            try:
                drag["ghost"].geometry(f"+{e.x_root + 10}+{e.y_root + 10}")
            except Exception:        # noqa: BLE001
                pass

        def _release(e):
            ghost = drag["ghost"]
            drag["ghost"] = None
            if ghost is not None:
                try:
                    ghost.destroy()
                except Exception:    # noqa: BLE001
                    pass
            if not drag["moved"]:
                return
            if self._point_over_widget(self.input, e.x_root, e.y_root) or \
               self._point_over_widget(self.chat, e.x_root, e.y_root):
                self._add_selected_to_chat(path)

        name_lbl.bind("<Button-1>", _press, add="+")
        name_lbl.bind("<B1-Motion>", _motion)
        name_lbl.bind("<ButtonRelease-1>", _release)

    def _bind_file_tree_drag(self):
        """文件树条目可拖拽：按住拖到聊天输入区/消息区放下 = 加入对话。

        - 文件：追加到待发送附件栏（等同右键「添加到对话」）
        - 目录：以 @引用 形式插入输入框（作为模型上下文，不转附件）
        无位移的普通点击仍走 _on_file_click（选中/展开/双击打开），不触发拖拽。
        """
        drag = {"sx": 0, "sy": 0, "moved": False, "ghost": None,
                "path": None, "isdir": False}

        def _item_file_path(y):
            """返回鼠标 y 坐标对应条目的 (路径, 是否目录)；空白返回 (None, False)。"""
            try:
                iid = self.file_tree.identify_row(y)
            except Exception:            # noqa: BLE001
                iid = ""
            if not iid:
                iid = self.file_tree.focus()
            if not iid:
                return None, False
            vals = self.file_tree.item(iid, "values")
            if not vals or len(vals) < 2 or not str(vals[0]).strip():
                return None, False
            return vals[0], str(vals[1]).strip().lower() == "true"

        def _press(e):
            drag["sx"], drag["sy"] = e.x_root, e.y_root
            drag["moved"] = False
            drag["path"], drag["isdir"] = _item_file_path(e.y)

        def _motion(e):
            # 未超过阈值视为点击，不弹拖影
            if abs(e.x_root - drag["sx"]) < 6 and abs(e.y_root - drag["sy"]) < 6:
                return
            if not drag["path"]:
                return
            drag["moved"] = True
            if drag["ghost"] is None:
                g = tk.Toplevel(self.root)
                g.overrideredirect(True)
                try:
                    g.attributes("-topmost", True)
                except Exception:    # noqa: BLE001
                    pass
                icon = "📁" if drag["isdir"] else "📄"
                tk.Label(g, text=icon + " " + os.path.basename(drag["path"].rstrip("/\\")),
                         bg=self._TAB_ON, fg=self._TAB_FG_ON,
                         font=(FONT_UI, 9), padx=8, pady=4).pack()
                drag["ghost"] = g
            try:
                drag["ghost"].geometry(f"+{e.x_root + 10}+{e.y_root + 10}")
            except Exception:        # noqa: BLE001
                pass

        def _release(e):
            ghost = drag["ghost"]
            drag["ghost"] = None
            if ghost is not None:
                try:
                    ghost.destroy()
                except Exception:    # noqa: BLE001
                    pass
            if not drag["moved"] or not drag["path"]:
                return
            if self._point_over_widget(self.input, e.x_root, e.y_root) or                self._point_over_widget(self.chat, e.x_root, e.y_root):
                if drag["isdir"]:
                    self._insert_at_ref(drag["path"])
                else:
                    self._add_selected_to_chat(drag["path"])
            drag["path"] = None

        self.file_tree.bind("<Button-1>", _press, add="+")
        self.file_tree.bind("<B1-Motion>", _motion)
        self.file_tree.bind("<ButtonRelease-1>", _release)

    def _file_restyle(self):
        for view_id, (tab, name_lbl, cls_lbl) in self._file_tabs.items():
            active = (view_id == self._file_active_view)
            bg = self._TAB_ON if active else self._TAB_OFF
            fg = self._TAB_FG_ON if active else self._TAB_FG_OFF
            try:
                tab.config(bg=bg)
                name_lbl.config(bg=bg, fg=fg)
                if cls_lbl:
                    cls_lbl.config(bg=bg, fg=fg)
            except Exception:        # noqa: BLE001
                pass

    def _file_select_view(self, view_id):
        self._file_active_view = view_id
        for v, frame in self._file_views.items():
            if v == view_id:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        self._file_restyle()
        if view_id != "__files__":
            self._editor_auto_expand()   # 点开编辑 → 窄面板自动扩到约半屏

    def _file_close_view(self, view_id):
        if view_id == "__files__":
            return
        frame = self._file_views.pop(view_id, None)
        tab = self._file_tabs.pop(view_id, None)
        # 关闭该文件的 LSP 客户端（若曾启动）
        lspc = getattr(frame, "_lsp_ref", None) if frame else None
        if lspc is not None:
            try: lspc.close()
            except Exception: pass
        if frame:
            frame.destroy()
        if tab:
            tab[0].destroy()
        # 停用已关闭文件的引用
        for path in [pp for pp, vv in self._file_tab_by_view.items() if vv == view_id]:
            self._file_tab_by_view.pop(path, None)
        if self._file_active_view == view_id:
            self._file_select_view("__files__")

    def _close_all_file_views(self):
        """关闭全部已打开的文件标签（保留文件树视图）。

        工作区切换 / 会话载入切目录时调用，防止旧目录的代码标签残留
        （例如切换到新目录后，之前打开的 730.py 标签仍在）。
        """
        if not getattr(self, "_file_views", None):
            return
        for view_id in list(self._file_views.keys()):
            if view_id == "__files__":
                continue
            self._file_close_view(view_id)
        if getattr(self, "_file_active_view", None) != "__files__":
            self._file_select_view("__files__")

    def _on_file_right(self, event):
        """右键文件树：文件=添加到对话/打开/改名/删除；目录=在资源管理器中打开/添加到对话/改名/删除。"""
        try:
            self.file_tree.identify_row(event.y)
        except Exception:            # noqa: BLE001
            pass
        iid = self.file_tree.focus()
        if not iid:
            try:
                iid = self.file_tree.identify_row(event.y)
            except Exception:        # noqa: BLE001
                iid = ""
        vals = self.file_tree.item(iid, "values") if iid else ("", False)
        path = str(vals[0]) if vals and vals[0] else ""
        is_dir = str(vals[1]).strip().lower() == "true" if len(vals) >= 2 else False
        menu = tk.Menu(self.root, tearoff=0, font=(FONT_UI, 10))
        if not path:
            menu.tk_popup(event.x_root, event.y_root)
            return
        if is_dir:
            menu.add_command(label=_t("file.open_dir"),
                             command=lambda p=path: self._open_in_explorer(p))
            menu.add_command(label=_t("file.add_chat"),
                             command=lambda p=path: self._add_selected_to_chat(p))
            menu.add_command(label=_t("file.rename"),
                             command=lambda p=path: self._rename_tree_item(p, True))
            menu.add_separator()
            menu.add_command(label=_t("file.delete"),
                             command=lambda p=path: self._delete_tree_item(p, True))
        else:
            menu.add_command(label=_t("file.add_chat"),
                             command=lambda p=path: self._add_selected_to_chat(p))
            menu.add_command(label=_t("file.open"),
                             command=lambda p=path: self._open_file_editor(p))
            menu.add_command(label=_t("file.rename"),
                             command=lambda p=path: self._rename_tree_item(p, False))
            menu.add_separator()
            menu.add_command(label=_t("file.delete"),
                             command=lambda p=path: self._delete_file(p))
        menu.tk_popup(event.x_root, event.y_root)

    def _open_in_explorer(self, path):
        """在系统文件管理器中打开目录（Windows 资源管理器 / macOS Finder / xdg-open）。"""
        try:
            if sys.platform == "win32":
                os.startfile(path)                    # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:            # noqa: BLE001
            self._set_status(str(e))

    def _rename_tree_item(self, path, is_dir):
        """重命名文件/目录（带确认；打开中的文件改名后关闭旧标签）。"""
        import os as _os
        from tkinter import messagebox, simpledialog
        old = _os.path.basename(path)
        new = simpledialog.askstring(_t("file.rename"),
                                     _t("file.rename_to", old=old),
                                     initialvalue=old, parent=self.root)
        if not new:
            return
        new = new.strip()
        if not new or new == old:
            return
        target = _os.path.join(_os.path.dirname(path), new)
        if _os.path.exists(target):
            messagebox.showerror(_t("file.rename"), _t("file.exists"),
                                 parent=self.root)
            return
        try:
            _os.rename(path, target)
        except OSError as e:
            messagebox.showerror(_t("file.rename"), str(e), parent=self.root)
            return
        if not is_dir and path in getattr(self, "_file_tabs", {}):
            view_id = self._file_tabs[path][2]
            self._file_close_view(view_id)
        self._refresh_file_panel()
        self._set_status(_t("file.renamed", old=old, new=new))

    def _delete_tree_item(self, path, is_dir):
        import shutil
        if is_dir:
            from tkinter import messagebox
            if not messagebox.askyesno(_t("file.delete"), path, parent=self.root):
                return
            try:
                shutil.rmtree(path)
            except OSError as e:
                from tkinter import messagebox as _mb
                _mb.showerror(_t("file.delete"), str(e), parent=self.root)
                return
            self._refresh_file_panel()
            self._set_status(_t("mm.deleted", name=os.path.basename(path.rstrip("/\\"))))
        else:
            self._delete_file(path)

    def _delete_file(self, path):
        """删除文件（带确认）。"""
        import os as _os
        from tkinter import messagebox
        if not path or not _os.path.isfile(path):
            return
        if not messagebox.askyesno(_t("file.delete"),
                                   f"{_t('file.delete')}?\n{_os.path.basename(path)}",
                                   parent=self.root):
            return
        try:
            _os.remove(path)
            self._set_status(_t("file.deleted", p=path))
            self._refresh_file_panel()
        except OSError as e:
            messagebox.showerror(_t("msg.save_fail"), str(e), parent=self.root)

    def _on_file_select(self, _e=None):
        """选中文件（用于右键定位）；无底部标签板了，占位保留。"""
        return

    def _add_selected_to_chat(self, path=None):
        """把选中的文件加入待发送附件栏；目录则以 @引用 形式插入输入框。"""
        if not path:
            iid = self.file_tree.focus()
            if not iid:
                return
            vals = self.file_tree.item(iid, "values")
            if not vals or len(vals) < 2:
                return
            path = vals[0]
            if str(vals[1]).strip().lower() == 'true':
                self._insert_at_ref(path)
                return
        if not path:
            return
        if os.path.isdir(path):
            self._insert_at_ref(path)
            return
        if path in self._pending_attachments:
            return
        self._pending_attachments.append(path)
        self._render_attachments()
        kinds = "、".join(
            (media.classify(p) if isinstance(p, str) else attach.snippet_chip(p))
            or _t("msg.file") for p in self._pending_attachments)
        self._set_status(_t("msg.attached", n=len(self._pending_attachments), kinds=kinds))

    def _insert_at_ref(self, path):
        """把目录（或文件）以 @引用 插入输入框光标处，作为模型上下文。"""
        try:
            ws = tools.get_workspace() or os.getcwd()
            rel = os.path.relpath(path, ws).replace("\\", "/")
        except Exception:            # noqa: BLE001
            rel = path
        self.input.insert("insert", f"@{rel}/ " if os.path.isdir(path)
                          else f"@{rel} ")
        self.input.focus_set()
        self._set_status(_t("file.dir_added", rel=rel))

    def _add_code_to_chat(self, path, start_line, end_line, content):
        """把编辑器选中区作为「代码片段」加入待发送附件栏。

        附件携带 文件路径 + 起止行号 + 代码内容，发送时 AI 直接内联该片段，
        便于针对性分析（而非整文件）。
        """
        att = {"kind": "snippet", "path": path,
               "start_line": start_line, "end_line": end_line,
               "content": content}
        sig = (path, start_line, end_line)
        for p in self._pending_attachments:
            if isinstance(p, dict) and p.get("kind") == "snippet" and \
                    (p.get("path"), p.get("start_line"), p.get("end_line")) == sig:
                self._file_select_view(path)       # 重复添加：切回该文件视图提示
                return
        self._pending_attachments.append(att)
        self._render_attachments()
        self._set_status(_t("msg.attached", n=len(self._pending_attachments),
                            kinds=attach.snippet_chip(att)))

    def _code_context_menu(self, event, path, text_widget):
        """编辑器右键菜单：选中代码可加入聊天（附件带文件路径 + 行号范围）。"""
        has_sel = bool(text_widget.tag_ranges("sel"))
        menu = tk.Menu(self.root, tearoff=0, font=(FONT_UI, 10))
        menu.add_command(
            label=_t("file.add_code_chat"),
            state=("normal" if has_sel else "disabled"),
            command=(lambda: self._code_sel_to_chat(path, text_widget))
            if has_sel else (lambda: None))
        menu.tk_popup(event.x_root, event.y_root)

    def _code_sel_to_chat(self, path, text_widget):
        """把编辑器选中区加入聊天：附件携带文件 + 行号范围 + 代码内容。"""
        sel = text_widget.tag_ranges("sel")
        if not sel:
            return
        first, last = sel[0], sel[1]
        try:
            start_line = int(str(first).split(".")[0])
            content = text_widget.get(first, last)
        except Exception:            # noqa: BLE001
            return
        lines = content.split("\n")
        if lines and lines[-1] == "":
            lines.pop()              # 选中到整行末尾多出的换行不计入
        end_line = start_line + max(len(lines) - 1, 0)
        if not lines:
            return
        self._add_code_to_chat(path, start_line, end_line, "\n".join(lines))

    def _apply_file_filter(self, query: str):
        """按文件名过滤右侧文件树：命中的文件 + 其父目录显示，其余隐藏。"""
        q = (query or "").strip().lower()
        if q == _t("file.search").lower() or not q:
            self._refresh_file_panel()
            return
        import os as _os
        self._file_filter = q
        root = tools.get_workspace()
        self.file_tree.delete(*self.file_tree.get_children())
        if not root or not _os.path.isdir(root):
            return

        def _match(path):
            try:
                for name in _os.listdir(path):
                    if q in name.lower():
                        return True
                    fp = _os.path.join(path, name)
                    if _os.path.isdir(fp) and _match(fp):
                        return True
            except OSError:
                pass
            return False

        def _walk(parent, path):
            try:
                names = sorted(_os.listdir(path))
            except OSError:
                return
            for name in names:
                full = _os.path.join(path, name)
                try:
                    isdir = _os.path.isdir(full)
                except OSError:
                    isdir = False
                if q in name.lower():
                    txt = f"📁 {name}" if isdir else f"📄 {name}"
                    node = self.file_tree.insert(parent, "end", text=txt, values=(full, isdir))
                    if isdir:
                        self.file_tree.insert(node, "end", text="", values=("", False))
                elif isdir and _match(full):
                    node = self.file_tree.insert(parent, "end", text=f"📁 {name}",
                                                 values=(full, True))
                    _walk(node, full)

        _root_name = _os.path.basename(root.rstrip("/\\")) or root
        rid = self.file_tree.insert("", "end", text=f"📁 {_root_name}",
                                    open=True, values=(root, True))
        _walk(rid, root)

    def _refresh_file_panel(self):
        """刷新右侧文件树：根节点=工作区文件夹，展开显示目录内全部文件（含隐藏项）。

        重建前记录已展开目录的绝对路径，重建后恢复展开状态——
        避免 Agent 删除/新增文件后刷新把用户展开的目录全部折叠回去。
        """
        import os as _os

        open_paths: set = set()

        def _collect(iid):
            for c in self.file_tree.get_children(iid):
                v = self.file_tree.item(c, "values")
                if not v or len(v) < 2 or not str(v[0]).strip():
                    continue
                if str(v[1]) in ("True", "1"):
                    if self.file_tree.item(c, "open"):
                        open_paths.add(str(v[0]))
                    _collect(c)

        _collect("")

        self.file_tree.delete(*self.file_tree.get_children())
        root = tools.get_workspace()
        if not root or not _os.path.isdir(root):
            return
        name = _os.path.basename(root.rstrip("/\\")) or root
        rid = self.file_tree.insert("", "end", text=f"📁 {name}", open=True,
                                    values=(root, True))
        self._populate_file_dir(rid, root)

        def _reopen(iid):
            for c in self.file_tree.get_children(iid):
                v = self.file_tree.item(c, "values")
                if not v or len(v) < 2 or not str(v[0]).strip():
                    continue
                if str(v[1]) in ("True", "1") and str(v[0]) in open_paths:
                    self.file_tree.item(c, open=True)
                    # 该节点初始只带占位空行：先删占位再填充，避免占位与真实子项叠加
                    self._ensure_dir_loaded(c, str(v[0]))
                    _reopen(c)

        _reopen(rid)

        _reopen(rid)

    def _schedule_fs_refresh(self):
        """写/删文件操作后刷新文件树（2 秒去抖，连续工具调用不反复重建）。"""
        import time as _t
        now = _t.monotonic()
        if now - getattr(self, "_fs_refresh_last", 0.0) < 2:
            return
        self._fs_refresh_last = now
        self.root.after(0, self._refresh_file_panel)

    def _populate_file_dir(self, iid, path):
        try:
            entries = sorted(os.scandir(path),
                             key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        for e in entries:
            try:
                isdir = e.is_dir()
            except OSError:
                continue
            if isdir:
                # 目录显示递归聚合大小；文件显示自身大小
                size_txt = f"  ({_fmt_size(_dir_size(e.path))})"
                icon_key, fallback = "1f4c1", "📁"
            else:
                try:
                    sz = e.stat().st_size
                except OSError:
                    sz = 0
                size_txt = f"  ({_fmt_size(sz)})"
                ext = e.name.rsplit(".", 1)[-1].lower() if "." in e.name else ""
                icon_key, fallback = _TREE_ICON_MAP.get(ext, "1f4c4"), "📄"
            img = _emoji_icon(icon_key)
            txt = f"{e.name}{size_txt}" if img is not None else f"{fallback} {e.name}{size_txt}"
            kw = {"text": txt, "values": (e.path, isdir)}
            if img is not None:
                kw["image"] = img
            child = self.file_tree.insert(iid, "end", **kw)
            if isdir:
                self.file_tree.insert(child, "end", text="", values=("", False))  # 占位出展开箭头

    def _ensure_dir_loaded(self, iid, path):
        """目录懒加载：若节点仍只有占位空行，删占位并填充其子项。

        占位行的 values 为 ("", False)（路径为空），用「首个孩子路径为空」判定占位；
        直接取 not values 会因 ("", False) 非空元组恒为真而永远不触发。
        """
        kids = self.file_tree.get_children(iid)
        if len(kids) == 1:
            kv = self.file_tree.item(kids[0], "values")
            if not kv or not str(kv[0]).strip():
                self.file_tree.delete(kids[0])
                self._populate_file_dir(iid, path)

    def _on_tree_open(self, _e=None):
        """展开目录时懒加载其子项（点击展开箭头触发）。"""
        def _walk(parent):
            for iid in self.file_tree.get_children(parent):
                vals = self.file_tree.item(iid, "values")
                if len(vals) >= 2 and str(vals[1]).strip().lower() == 'true' \
                        and self.file_tree.item(iid, "open"):
                    self._ensure_dir_loaded(iid, vals[0])
                _walk(iid)
        _walk("")

    def _toggle_dir(self, iid):
        """展开/折叠目录节点；展开时懒加载其子项。"""
        opening = not self.file_tree.item(iid, "open")
        self.file_tree.item(iid, open=opening)
        if opening:
            vals = self.file_tree.item(iid, "values")
            if vals and len(vals) >= 2:
                self._ensure_dir_loaded(iid, vals[0])

    def _on_file_click(self, event):
        """单击目录 → 展开/折叠并加载子项；单击文件 → 选中；同一条目 <0.5s 连点两次 → 双击打开源码。

        目录返回 "break" 以便阻止 ttk 默认绑定再对点三角做一次切换，避免二次翻转。
        """
        import time as _time
        now = _time.time()
        try:
            iid = self.file_tree.identify_row(event.y)
        except Exception:            # noqa: BLE001
            iid = ""
        if not iid:
            iid = self.file_tree.focus()
        if not iid:
            return
        vals = self.file_tree.item(iid, "values")
        is_dir = bool(vals) and len(vals) >= 2 and str(vals[1]).strip().lower() == 'true'
        if is_dir:
            self.file_tree.selection_set(iid)
            self.file_tree.focus(iid)
            self._toggle_dir(iid)
            return "break"
        prev = getattr(self, "_file_last_click", (None, None))
        self._file_last_click = (now, iid)
        if prev[1] == iid and (now - prev[0]) < 0.5:
            self._file_last_click = (None, None)
            self._open_file_iid(iid)

    def _open_file_iid(self, iid):
        """按条目打开：文件→源码标签页；目录→展开/折叠。"""
        vals = self.file_tree.item(iid, "values")
        if not vals or len(vals) < 2:
            return
        if str(vals[1]).strip().lower() == 'true':                  # 目录
            opening = not self.file_tree.item(iid, "open")
            self.file_tree.item(iid, open=opening)
            if opening:
                # 编程式展开不触发 <<TreeviewOpen>>，需手动懒加载子项
                self._ensure_dir_loaded(iid, vals[0])
            return
        path = vals[0]
        if path:
            self._open_file_editor(path)

    def _reload_editor_tab(self, path):
        """模型 write_file 改了这个文件，若已打开则重载为新内容。"""
        txt = getattr(self, "_editor_txt_map", {}).get(path)
        if txt is None:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            # 修改动画：重载前绿色闪烁提示"已更新"，500ms 后恢复
            try:
                txt.config(bg="#dcfce7")
            except Exception:            # noqa: BLE001
                pass
            txt.config(state="normal")
            txt.delete("1.0", "end")
            txt.insert("1.0", content)
            txt.config(state="normal")
            self._editor_hl_apply(txt)
            import os as _os
            self._set_status("\u2705 " + _t("todo.updated", p=_os.path.basename(path)))
            self.root.after(500, lambda: txt.config(bg="white"))
            try:
                if hasattr(self, "_maybe_lsp_query"):
                    self._maybe_lsp_query(txt)
            except Exception:            # noqa: BLE001
                pass
        except Exception:                # noqa: BLE001
            pass

    def _open_file_editor(self, path):
        """把文件源码打开为一个蓝色标签（文件名+✕）；默认预览只读，防误改；可切换编辑。"""
        import os as _os
        from tkinter import messagebox

        # 已打开 → 切到它的视图
        if path in self._file_tab_by_view:
            self._file_select_view(self._file_tab_by_view[path])
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:               # noqa: BLE001
            messagebox.showerror(_t("ui.error", e=e), path, parent=self.file_content)
            return

        view_id = path
        frame = tk.Frame(self.file_content)
        self._file_views[view_id] = frame
        self._file_tab_by_view[view_id] = path

        state = {"edit": False, "dirty": False}
        bar = tk.Frame(frame)
        bar.pack(fill="x", padx=6, pady=5)

        # 直接进入编辑态；去掉 预览/编辑 切换；Ctrl+S 保存
        def _apply_state():
            try:
                txt.config(state="normal", bg="white")
            except Exception:        # noqa: BLE001
                pass

        def _save(_e=None):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(txt.get("1.0", "end-1c"))
                state["dirty"] = False
                self._set_status(_t("msg.saved_to", p=path))
            except Exception as e:           # noqa: BLE001
                messagebox.showerror(_t("msg.save_fail"), str(e), parent=frame)

        _save_btn = _flat_button(bar, text=_t("btn.save_icon"), command=_save,
                                 width=2, font=(FONT_MONO, 10))
        _save_btn.pack(side="left")
        self._bind_hint(_save_btn, "btn.save")
        _close_btn = _flat_button(bar, text=_t("btn.close_icon"),
                                  command=lambda: self._file_close_view(view_id),
                                  width=2, font=(FONT_MONO, 10))
        _close_btn.config(fg="#dc2626")
        _close_btn.pack(side="left", padx=(4, 0))
        # 诊断标签：LSP 实时错误/警告计数（无 LSP 时隐藏）
        diag_lbl = tk.Label(bar, text="", font=(FONT_UI, 9), fg="#dc2626")
        diag_lbl.pack(side="left", padx=(10, 0))
        frame._lsp_diag_lbl = diag_lbl
        self._bind_hint(_close_btn, "btn.close")

        if not hasattr(self, "_editor_txt_map"):
            self._editor_txt_map = {}
        txt = scrolledtext.ScrolledText(frame, wrap="none",
                                        font=(FONT_MONO, self._font_editor))
        self._editor_txt_map[path] = txt
        txt.insert("1.0", content)
        txt.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        _apply_state()
        txt.bind("<Key>", lambda e: state.__setitem__("dirty", True))
        txt.bind("<Control-s>", _save)
        # 语法高亮 + 智能补全（按文件扩展名选语言）+ LSP 客户端（懒启动，慢则回退）
        txt._lang = self._editor_lang_for(path)
        txt._lsp = None
        frame._lsp_ref = None
        try:
            import lsp as _lsp_mod
            if _lsp_mod.available_for(txt._lang):
                txt._lsp = _lsp_mod.LSPClient.for_file(path)
                frame._lsp_ref = txt._lsp
        except Exception:            # noqa: BLE001
            txt._lsp = None
        self._editor_hl_config(txt)
        self._editor_hl_apply(txt)

        def _on_key_rel(e):
            self._editor_on_key(e, txt)
            # 输入停顿 1.2s 后拉一次 LSP 诊断（更新底栏 ✗/⚠ 计数）
            if getattr(txt, "_lsp", None):
                if getattr(txt, "_diag_after", None):
                    try:
                        txt.after_cancel(txt._diag_after)
                    except Exception:        # noqa: BLE001
                        pass
                txt._diag_after = txt.after(
                    1200, lambda: self._lsp_diag_query(txt, frame))
        txt.bind("<KeyRelease>", _on_key_rel)
        txt.bind("<Escape>", lambda e: self._editor_hide_complete())
        # 右键：选中代码区 → 加入聊天（附件带文件路径 + 行号范围，供 AI 分析）
        txt.bind("<Button-3>",
                 lambda e, p=path, w=txt: self._code_context_menu(e, p, w))

        # 加蓝色标签（文件名 + ✕）
        self._file_add_tab(view_id, _os.path.basename(path), closable=True)
        self._file_select_view(view_id)

    def _close_file_tab(self, path):
        """关闭某个文件的源码标签。"""
        view_id = self._file_tab_by_view.get(path)
        if view_id:
            self._file_close_view(view_id)

    _CHAT_HL_DARK = {"kw": "#93c5fd", "str": "#fca5a5", "cmt": "#86efac",
                     "num": "#fcd34d", "fn": "#f9a8d4"}
    _CHAT_HL_LIGHT = {"kw": "#0000ff", "str": "#a31515", "cmt": "#008000",
                      "num": "#098658", "fn": "#795e26"}

    def _insert_highlighted_code(self, raw, lang, dark, base_tag=None, code_font=None):
        """把代码插入聊天并按语言高亮；dark 决定配色（深底浅色、浅底深色）。"""
        import re
        try:
            prev_state = self.chat.cget("state")
            self.chat.config(state="normal")
            start = self.chat.index("end")
            body = raw.rstrip("\n")
            tags = (base_tag,) if base_tag else ()
            self.chat.insert("end", body, tags) if tags else self.chat.insert("end", body)
            if code_font:
                self.chat.tag_add(code_font, start, self.chat.index("end"))
            colors = self._CHAT_HL_DARK if dark else self._CHAT_HL_LIGHT
            for tag, color in colors.items():
                self.chat.tag_configure(tag, foreground=color)
            kw = _EDITOR_KW.get(lang, _EDITOR_KW["python"])
            linec, _blockc = _EDITOR_CMT.get(lang, ("#", None))
            for ln, line in enumerate(body.split("\n"), 1):
                if not line:
                    continue
                l0 = "%s.%d.0" % (start.split(".")[0], ln)      # 第 ln 行绝对索引
                # 行注释
                if linec and linec in line:
                    i = line.rindex(linec)
                    self.chat.tag_add("cmt", "%s+%dc" % (l0, i), "%s lineend" % l0)
                    line = line[:i]
                # 字符串（双/单引号）
                for mm in re.finditer(r'"(?:\\.|[^"\\])*"', line):
                    self.chat.tag_add("str", "%s+%dc" % (l0, mm.start()), "%s+%dc" % (l0, mm.end()))
                for mm in re.finditer(r"'(?:\\.|[^'\\])*'", line):
                    self.chat.tag_add("str", "%s+%dc" % (l0, mm.start()), "%s+%dc" % (l0, mm.end()))
                # def/class 声明 + 函数调用 + 数字 + 关键词
                for mm in re.finditer(r"\b(def|class|struct|interface|enum|fn|function)\s+([A-Za-z_]\w*)", line):
                    self.chat.tag_add("fn", "%s+%dc" % (l0, mm.start(2)), "%s+%dc" % (l0, mm.end(2)))
                for mm in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", line):
                    self.chat.tag_add("fn", "%s+%dc" % (l0, mm.start(1)), "%s+%dc" % (l0, mm.end(1)))
                for mm in re.finditer(r"\b(\d+)\b", line):
                    self.chat.tag_add("num", "%s+%dc" % (l0, mm.start(1)), "%s+%dc" % (l0, mm.end(1)))
                for mm in re.finditer(r"\b([A-Za-z_]\w*)\b", line):
                    if mm.group(1) in kw:
                        self.chat.tag_add("kw", "%s+%dc" % (l0, mm.start(1)), "%s+%dc" % (l0, mm.end(1)))
            self.chat.insert("end", "\n")
            self.chat.see("end")
            self.chat.config(state=prev_state)
        except Exception:            # noqa: BLE001
            try:
                self.chat.insert("end", raw + "\n")
            except Exception:        # noqa: BLE001
                pass

    def _editor_hl_config(self, txt):
        # 浅色底下的高亮配色
        txt.tag_configure("kw", foreground="#0000ff")
        txt.tag_configure("str", foreground="#a31515")
        txt.tag_configure("cmt", foreground="#008000")
        txt.tag_configure("num", foreground="#098658")
        txt.tag_configure("fn", foreground="#795e26")
        txt.tag_configure("def", foreground="#267f99",
                          font=(FONT_MONO, getattr(self, "_font_editor", 10), "bold"))
        txt.tag_configure("bas", foreground="#0070c1")

    def _editor_lang_for(self, path):
        """按文件扩展名推断语言；未知回退 python。"""
        import os
        return _EDITOR_LANG_EXT.get(os.path.splitext(path)[1].lower(), "python")

    def _editor_hl_apply(self, txt):
        import re
        for t in ("kw", "str", "cmt", "num", "fn", "def", "bas"):
            txt.tag_remove(t, "1.0", "end")
        lang = getattr(txt, "_lang", "python")
        kw = _EDITOR_KW.get(lang, _EDITOR_KW["python"])
        linec, blockc = _EDITOR_CMT.get(lang, ("#", None))
        bo, bc = blockc if blockc else (None, None)
        content = txt.get("1.0", "end-1c")
        in_block = False
        for ln, line in enumerate(content.split("\n"), 1):
            # 块注释中 → 整行是注释
            if in_block:
                if bc and bc in line:
                    i = line.index(bc)
                    try: txt.tag_add("cmt", f"{ln}.0", f"{ln}.{i + len(bc)}")
                    except Exception: pass
                    line = line[i + len(bc):]
                    in_block = False
                else:
                    try: txt.tag_add("cmt", f"{ln}.0", f"{ln}.end")
                    except Exception: pass
                    continue
            # 行注释（//、#、--）
            if linec and linec in line:
                i = line.index(linec)
                try: txt.tag_add("cmt", f"{ln}.{i}", f"{ln}.end")
                except Exception: pass
                line = line[:i]
            # 字符串
            for m in re.finditer(r"(\"\"\".*?\"\"\"|'''[^']*?'{3}|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")", line):
                try: txt.tag_add("str", f"{ln}.{m.start(1)}", f"{ln}.{m.end(1)}")
                except Exception: pass
            # def/class 等声明名 + 函数调用 + 数字 + 关键词
            for m in re.finditer(r"\b(def|class|struct|interface|enum|namespace|function|fn)\s+([A-Za-z_][A-Za-z0-9_]*)\b", line):
                try: txt.tag_add("def", f"{ln}.{m.start(2)}", f"{ln}.{m.end(2)}")
                except Exception: pass
            for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", line):
                try: txt.tag_add("fn", f"{ln}.{m.start(1)}", f"{ln}.{m.end(1)}")
                except Exception: pass
            for m in re.finditer(r"\b(\d+)\b", line):
                try: txt.tag_add("num", f"{ln}.{m.start(1)}", f"{ln}.{m.end(1)}")
                except Exception: pass
            for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", line):
                w = m.group(1)
                if w in kw:
                    try: txt.tag_add("kw", f"{ln}.{m.start(1)}", f"{ln}.{m.end(1)}")
                    except Exception: pass
            # 块注释开始（/* */ 或 <!-- -->）
            if bo and not in_block and bo in line:
                si = line.index(bo)
                if bc and bc in line[si + len(bo):]:
                    ei = line.index(bc, si + len(bo))
                    try: txt.tag_add("cmt", f"{ln}.{si}", f"{ln}.{ei + len(bc)}")
                    except Exception: pass
                else:
                    try: txt.tag_add("cmt", f"{ln}.{si}", f"{ln}.end")
                    except Exception: pass
                    in_block = True

    # ---- 智能补全 ----
    def _editor_words(self, txt):
        import re
        lang = getattr(txt, "_lang", "python")
        words = set(_EDITOR_KW.get(lang, _EDITOR_KW["python"]))
        content = txt.get("1.0", "end-1c")
        for m in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]{1,}\b", content):
            words.add(m.group(0))
        return words

    def _editor_hide_complete(self):
        if getattr(self, "_complete_pop", None) and self._complete_pop.winfo_exists():
            try: self._complete_pop.destroy()
            except Exception: pass
        self._complete_pop = None

    def _editor_semantic(self, txt):
        """按语言分发语义补全：Python 用 ast，其它用正则符号抽取（近似）。"""
        lang = getattr(txt, "_lang", "python")
        if lang == "python":
            return self._python_ast_symbols(txt)
        return self._regex_symbols(txt, lang)

    def _regex_symbols(self, txt, lang):
        """非 Python 语言：正则抽取 类/函数/导入名（近似语义），供 obj. 成员联想与签名提示。"""
        import re
        content = txt.get("1.0", "end-1c")
        classes: set = set(); functions: set = set(); names: set = set()
        cls_members: dict = {}; func_sigs: dict = {}
        # 类型声明（class/interface/struct/enum/namespace/module/type）
        for m in re.finditer(
                r"\b(?:class|interface|struct|enum|namespace|module|type)\s+([A-Za-z_]\w*)", content):
            name = m.group(1); classes.add(name); names.add(name)
        # 函数/方法名 + 签名
        for m in re.finditer(
                r"(?:^|[;{\n])\s*(?:public|private|protected|static|async|final|abstract|"
                r"function|def|fn|fun|func)?\s*(?:[A-Za-z_][\w<>,\s]*\s+)?([A-Za-z_]\w*)\s*\(([^)]*)\)",
                content):
            fn = m.group(1); functions.add(fn); names.add(fn)
            func_sigs[fn] = fn + "(" + m.group(2).strip() + ")"
        # 导入/use/require/from
        for m in re.finditer(r"\b(?:import|use|require|from)\s+([A-Za-z_]\w*)", content):
            names.add(m.group(1))
        # 尽量把类体成员放进类（无法精确配对大括号，用启发：类名后到下一个类/函数定义之间的 name( 收集）
        return cls_members, func_sigs, classes, functions, names

    def _python_ast_symbols(self, txt):
        """用 ast 解析当前文件，提取 类/成员/函数签名/顶层名/导入名（语义级补全）。"""
        import ast
        content = txt.get("1.0", "end-1c")
        cls_members: dict = {}
        func_sigs: dict = {}
        classes: set = set()
        functions: set = set()
        names: set = set()
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return cls_members, func_sigs, classes, functions, names
        def _sig(node):
            args = []
            for a in list(getattr(node.args, "posonlyargs", [])) + list(getattr(node.args, "args", [])):
                args.append(a.arg)
            if getattr(node.args, "vararg", None):
                args.append("*" + node.args.vararg.arg)
            for a in getattr(node.args, "kwonlyargs", []):
                args.append(a.arg)
            if getattr(node.args, "kwarg", None):
                args.append("**" + node.args.kwarg.arg)
            return node.name + "(" + ", ".join(args) + ")"
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.add(node.name); names.add(node.name)
                mem = cls_members.setdefault(node.name, set())
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        mem.add(item.name); func_sigs[item.name] = _sig(item)
                    elif isinstance(item, ast.Assign):
                        for t in item.targets:
                            if isinstance(t, ast.Name):
                                mem.add(t.id)
                    elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        mem.add(item.target.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.add(node.name); names.add(node.name)
                func_sigs[node.name] = _sig(node)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    names.add(a.asname or a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    names.add(a.asname or a.name)
        return cls_members, func_sigs, classes, functions, names

    def _show_complete_popup(self, txt, cands, dotted=False):
        self._complete_cands = cands
        self._complete_idx = 0
        self._complete_dotted = dotted
        try:
            pop = tk.Toplevel(self.root)
            pop.overrideredirect(True)
            lb = tk.Listbox(pop, font=(FONT_MONO, 10), height=min(len(cands), 8),
                            borderwidth=0, highlightthickness=0)
            for c in cands:
                lb.insert("end", c)
            lb.select_set(0)
            lb.pack()
            bbox = txt.bbox("insert")
            x = txt.winfo_rootx() + (bbox[0] if bbox else 0)
            y = txt.winfo_rooty() + (bbox[1] + bbox[3] if bbox else 0) + 18
            pop.geometry(f"+{x}+{y}")
            self._complete_pop = pop
            self._complete_lb = lb
        except Exception:            # noqa: BLE001
            pass

    def _lsp_diag_query(self, txt, frame):
        """后台拉取当前编辑器内容的 LSP 诊断，底栏显示 ✗/⚠ 计数。"""
        lspc = getattr(txt, "_lsp", None)
        if not lspc:
            return
        try:
            content = txt.get("1.0", "end-1c")
        except Exception:            # noqa: BLE001  编辑器已关
            return
        lbl = getattr(frame, "_lsp_diag_lbl", None)

        def _worker():
            try:
                diags = lspc.diag(content)
            except Exception:        # noqa: BLE001
                diags = None
            if diags is None:
                return

            def _apply():
                try:
                    if lbl is not None and lbl.winfo_exists():
                        errs = sum(1 for d in diags if d["mark"] == "✗")
                        warns = sum(1 for d in diags if d["mark"] == "⚠")
                        parts = []
                        if errs:
                            parts.append(f"✗ {errs}")
                        if warns:
                            parts.append(f"⚠ {warns}")
                        lbl.config(text=" ".join(parts) or "✓",
                                   fg="#dc2626" if errs else
                                   ("#d97706" if warns else "#16a34a"))
                        # 详情放状态栏（第一条）
                        if diags:
                            d0 = diags[0]
                            self._set_status(_t("lsp.first_diag", line=d0["line"],
                                                msg=d0["msg"]))
                except Exception:    # noqa: BLE001
                    pass
            self.root.after(0, _apply)
        threading.Thread(target=_worker, daemon=True).start()

    def _maybe_lsp_query(self, txt):
        """有 LSP 客户端时，后台查询补全；慢则保留 AST/正则回退。"""
        lspc = getattr(txt, "_lsp", None)
        if not lspc or getattr(self, "_lsp_query_busy", False):
            return
        try:
            idx = txt.index("insert")
            before = txt.get("1.0", idx)
            content = txt.get("1.0", "end-1c")
            line = before.count("\n")
            char = len(before) - (before.rfind("\n") + 1)
        except Exception:            # noqa: BLE001
            return
        seq = getattr(self, "_lsp_query_seq", 0) + 1
        self._lsp_query_seq = seq
        self._lsp_query_busy = True
        threading.Thread(target=self._lsp_query,
                         args=(txt, lspc, content, line, char, seq), daemon=True).start()

    def _lsp_query(self, txt, lspc, content, line, char, seq):
        try:
            lspc.start()
            lspc.did_change(content)
            items = lspc.complete(content, line, char)
        except Exception:            # noqa: BLE001
            items = []
        self.root.after(0, lambda: self._lsp_apply(txt, seq, items))

    def _lsp_apply(self, txt, seq, items):
        self._lsp_query_busy = False
        if seq != getattr(self, "_lsp_query_seq", 0):
            return                       # 已过期（用户又敲了键）
        if not items:
            return                       # 保留 AST/正则回退
        cands = [it["label"] for it in items if it.get("label")][:12]
        if not cands:
            return
        if getattr(self, "_complete_pop", None) and self._complete_pop.winfo_exists():
            self._complete_cands = cands
            self._complete_idx = 0
            self._complete_lb.delete(0, "end")
            for c in cands:
                self._complete_lb.insert("end", c)
            self._complete_lb.select_set(0)
        else:
            self._show_complete_popup(txt, cands,
                                      dotted=getattr(self, "_complete_dotted", False))

    def _editor_on_key(self, event, txt):
        self._editor_hl_apply(txt)
        k = event.keysym
        # 补全弹窗在 → 处理导航/确认
        if getattr(self, "_complete_pop", None) and self._complete_pop.winfo_exists():
            if k == "Down":
                self._complete_idx = min(len(self._complete_cands) - 1, self._complete_idx + 1)
            elif k == "Up":
                self._complete_idx = max(0, self._complete_idx - 1)
            elif k in ("Return", "Tab"):
                self._editor_insert_complete(txt, self._complete_cands[self._complete_idx])
                return "break"
            elif k == "Escape":
                self._editor_hide_complete()
                return "break"
            else:
                self._editor_hide_complete()
            if k in ("Up", "Down") and getattr(self, "_complete_pop", None):
                self._complete_lb.selection_clear(0, "end")
                self._complete_lb.select_set(self._complete_idx)
                return None
            return None
        if k in ("Left", "Right", "Up", "Down", "Return", "Tab", "Escape"):
            return
        import re
        if k == "BackSpace":
            self._editor_hide_complete()
            return
        idx = txt.index("insert")
        line_start = txt.index(f"{idx} linestart")
        prefix = txt.get(line_start, idx)
        m = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", prefix)
        self._editor_hide_complete()
        if not m:
            return
        word = m.group(0)
        # 语义：obj. 成员补全
        if getattr(txt, "_lang", "") in ("html", "vue") and prefix.rstrip().endswith("<"):
            tags = ["div","span","p","a","ul","li","table","tr","td","form","input",
                    "button","section","header","footer","nav","main","h1","h2","h3",
                    "script","style","img","select","option","textarea","label","h4","h5","h6"]
            self._show_complete_popup(txt, tags, dotted=False)
            return
        dm = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\.[A-Za-z_]*$", prefix)
        if dm and k not in ("space",):
            obj = dm.group(1); part = dm.group(0).split(".")[-1]
            cls_members, func_sigs, classes, functions, names = self._editor_semantic(txt)
            pool = cls_members.get(obj, names)
            cands = sorted(x for x in pool if x.startswith(part) and x != part)[:12]
            if cands:
                self._show_complete_popup(txt, cands, dotted=True)
            self._maybe_lsp_query(txt)
            return
        # 语义：func( 签名提示
        sm = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*\($", prefix)
        if sm:
            cls_members, func_sigs, classes, functions, names = self._editor_semantic(txt)
            sig = func_sigs.get(sm.group(1))
            if sig:
                self._set_status("📖 " + sig)
            return
        cands = sorted(w for w in self._editor_words(txt) if w.startswith(word) and w != word)[:12]
        if cands:
            self._show_complete_popup(txt, cands)
            self._maybe_lsp_query(txt)

    def _editor_insert_complete(self, txt, cand):
        try:
            idx = txt.index("insert")
            line_start = txt.index(f"{idx} linestart")
            prefix = txt.get(line_start, idx)
            if getattr(self, "_complete_dotted", False):
                dot = prefix.rfind(".")
                start = f"{line_start}+{dot + 1}c" if dot >= 0 else f"{line_start}+{len(prefix)}c"
            else:
                m = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", prefix)
                word = m.group(0) if m else ""
                start = f"{line_start}+{max(0, len(prefix) - len(word))}c"
            txt.delete(start, idx)
            txt.insert(start, cand)
        except Exception:            # noqa: BLE001
            pass
        self._editor_hide_complete()
        self._editor_hl_apply(txt)

    # ---- 输入框 placeholder ----
    PLACEHOLDER = _t("input.placeholder")

    def _setup_placeholder(self):
        """占位提示改为悬浮灰字层：不再往输入框里插入真实文本。

        旧实现把占位符当正文插入（灰色），和用户输入混在同一缓冲里——
        IME/粘贴/弹窗插入等路径没清干净时，就会出现『输入看不到』『选择后
        残留占位符』。现在：内容为空 → 悬浮显示提示；有任何内容 → 自动隐藏。
        """
        self._placeholder_active = False      # 兼容旧引用：恒为 False
        self._ph_label = tk.Label(
            self.input, text=self.PLACEHOLDER, justify="left", anchor="nw",
            font=(FONT_MONO, self._font_chat + 1), fg="#9aa4b2", bg=theme.PANEL)
        self._ph_label.bind("<Button-1>", self._ph_click)
        # 内容任何增删（含程序化 delete/insert）都会触发 <<Modified>>
        self.input.bind("<<Modified>>", self._on_modified)
        self._ph_update()

    def _on_modified(self, _event):
        # <<Modified>> 是粘性标志：处理后必须复位，否则只触发一次
        try:
            self.input.edit_modified(False)
        except Exception:            # noqa: BLE001
            pass
        self.root.after(0, self._ph_update)

    def _ph_update(self):
        """空输入 → 显示悬浮占位符；有内容 → 隐藏。"""
        has = bool(self.input.get("1.0", "end").strip())
        if has:
            try:
                self._ph_label.place_forget()
            except Exception:        # noqa: BLE001
                pass
        else:
            self._ph_label.config(font=(FONT_MONO, self._font_chat + 1))
            self._ph_label.place(x=12, y=8, anchor="nw")

    def _ph_click(self, _event):
        """点击占位符 → 把焦点还给输入框（占位符在下次内容更新时自动消失）。"""
        self.input.focus_set()
        return "break"

    # ================= 模型管理 =================
    def _refresh_models(self):
        """重新加载模型列表；当前模型被删则切换到第一个可用模型。

        无论 key 是否变化都把 current_model 重绑到新加载的对象——
        改 provider/model（端点、密钥、显示名、上下文等）后立即生效，
        下一次请求就用新配置，无需重启。
        """
        self.models, default_key = config.load_models()
        self.model_map = {m.key: m for m in self.models}
        if self.current_model is not None \
                and self.current_model.key in self.model_map:
            self.current_model = self.model_map[self.current_model.key]
        else:
            self.current_model = self.model_map.get(default_key) or (
                self.models[0] if self.models else None)
        if self.current_model:
            if str(self.model_btn.cget("image")):      # PNG 模式：前缀由图片承担
                self.model_btn.config(text=self._model_btn_text())
            else:
                self.model_btn.config(text=self._model_btn_label(),
                                      width=self._model_btn_width())
            self._update_thinking_btn()
            if hasattr(self, "bottom_model_btn"):
                self.bottom_model_btn.config(text=self._model_btn_label(),
                                             width=self._model_btn_width())
        else:
            self.model_btn.config(text=_t("top.select_model"))

    def _model_btn_label(self):
        """模型按钮文案：🤖 + 模型名（等级由思考按钮展示，两者联动）。"""
        if not self.current_model:
            return "🤖 " + _t("top.select_model")
        return f"🤖 {self.current_model.display_name}"

    def _model_btn_text(self):
        """PNG 模式下按钮的纯文字部分（机器人前缀已由图片承担）。"""
        if not self.current_model:
            return _t("top.select_model")
        return self.current_model.display_name

    def _model_btn_width(self) -> int:
        """模型名长度自适应（字符数，留出余量）。"""
        label = self._model_btn_label()
        return max(14, len(label) + 2)

    def _select_model(self, key):
        self.current_model = self.model_map.get(key)
        if self.current_model:
            if str(self.model_btn.cget("image")):      # PNG 模式：前缀由图片承担
                self.model_btn.config(text=self._model_btn_text())
            else:
                self.model_btn.config(text=self._model_btn_label(), width=self._model_btn_width())
            self._update_thinking_btn()
            self._set_status(_t("st.model", m=self.current_model.display_name))
            if hasattr(self, "bottom_model_btn"):
                self.bottom_model_btn.config(text=self._model_btn_label(),
                                             width=self._model_btn_width())

    def _think_btn_text(self):
        """思考按钮文案：模型默认 / 当前等级。"""
        cur = (getattr(self.current_model, "reasoning_effort", "") or "").strip()
        return cur or _t("model.reasoning.default")

    def _update_thinking_btn(self):
        """思考按钮：图标随等级切换（🌫🚫🐢🧠⚡🔥🚀）；Windows 走 PNG。
        未设等级时显示「模型默认」图标。同步顶部与底部两颗思考按钮。"""
        cur = (getattr(self.current_model, "reasoning_effort", "") or "").strip()
        self._think_hint = self._think_btn_text()   # 图标化：等级悬停可见
        icon = REASONING_ICON.get(cur, "🧠")
        for name in ("think_btn", "bottom_think_btn"):
            b = getattr(self, name, None)
            if b:
                _set_btn_icon(b, icon)

    def _reasoning_choices(self) -> tuple:
        """当前模型支持的推理等级（空 = 标准集）。"""
        return tuple(getattr(self.current_model, "reasoning_choices", ())) \
            or REASONING_CHOICES

    def _show_think_menu(self, anchor=None):
        """思考按钮弹菜单：只列该模型支持的等级；选「模型默认」= 关闭。"""
        m = self.current_model
        if not m:
            return
        cur = (getattr(m, "reasoning_effort", "") or "").strip()
        menu = tk.Menu(self.root, tearoff=0, font=(FONT_UI, 10))
        for val in self._reasoning_choices():
            label = _reasoning_label(val)
            mark = "  ✓" if val == cur else ""
            menu.add_command(label=label + mark,
                             command=lambda v=val: self._apply_reasoning(v))
        tgt = anchor or self.think_btn
        x = tgt.winfo_rootx()
        y = tgt.winfo_rooty() + tgt.winfo_height()
        menu.tk_popup(x, y)

    def _apply_reasoning(self, val: str):
        """把等级写入当前模型并联动按钮/状态。val 空串 = 关（清掉等级）。"""
        m = self.current_model
        if not m:
            return
        mc = config.update_model(m.key, reasoning_effort=val)
        if mc is None:
            return
        for i, mm in enumerate(self.models):
            if mm.key == m.key:
                self.models[i] = mc
                break
        self.model_map = {mm.key: mm for mm in self.models}
        if self.current_model and self.current_model.key == mc.key:
            self.current_model = mc
        self.model_btn.config(text=self._model_btn_label())
        self._update_thinking_btn()
        self._set_status(_t("think.set", v=val or _t("think.off")))

    def _set_reasoning(self, val: str):
        """下拉直接改当前模型的推理等级并持久化（空串 = 模型默认）。

        设过等级自动打上 "reasoning" 能力标记（菜单继续显示 🧠）。
        """
        self._apply_reasoning(val)

    # ================= 派发守护：定时核验条件，不满足自动关掉 =================
    DISPATCH_CHECK_S = 4        # 本地大脑核验周期（秒）
    DISPATCH_CLOUD_S = 600      # 云端目标/网络探测周期（秒）

    def _dispatch_check_loop(self):
        """后台守护：派发开启时定时核验生效条件。

        - 本地大脑：未配置 / 未运行 / 不健康 → 立即自动关掉（状态确定）；
          纯云端产品线（gpulocal 关闭）无本地大脑，不做此项核验；
        - 云端目标（含网络可达性 / 密钥有效性）：连续 2 次探测失败 → 自动关掉
          （60s 一次，防瞬时网络抖动误关）。
        只关不启：重新满足条件后需手动再开（绝不自动拉起本地模型）。
        """
        last_cloud = 0.0
        while True:
            try:
                if config.get_model_dispatch():
                    if not self._dispatch_brain_healthy():
                        name = config.get_dispatch_model().split("/")[-1]
                        self.root.after(0, lambda: self._dispatch_auto_off(
                            _t("dispatch.auto_off.brain", name=name)))
                    else:
                        now = time.time()
                        if now - last_cloud >= self.DISPATCH_CLOUD_S:
                            last_cloud = now
                            ok, bad = self._dispatch_cloud_ok()
                            if ok:
                                self._dispatch_cloud_fails = 0
                            else:
                                self._dispatch_cloud_fails += 1
                                if self._dispatch_cloud_fails >= 2:
                                    self.root.after(
                                        0, lambda b=bad: self._dispatch_auto_off(
                                            _t("dispatch.auto_off.cloud",
                                               models=b)))
            except Exception:                       # noqa: BLE001
                pass
            threading.Event().wait(self.DISPATCH_CHECK_S)

    def _dispatch_cloud_ok(self):
        """探测云端目标所在端点（顺带验证网络与密钥）。返回 (是否全通, 失败串)。"""
        seen, mcs, bad = set(), [], []
        for k in ("dispatch_flash", "dispatch_pro", "dispatch_vision"):
            mc = config.find_model(config.get_dispatch_config()[k])
            if mc and mc.base_url and mc.base_url not in seen:
                seen.add(mc.base_url)
                mcs.append(mc)
        for mc in mcs:
            try:
                _fetch_openai_models(mc.base_url, mc.api_key)
            except Exception:                      # noqa: BLE001 网络不通也算失败
                bad.append(mc.display_name)
        return (not bad), "、".join(bad)

    def _dispatch_auto_off(self, reason: str):
        """自动关掉派发：写配置 + 刷顶栏按钮 + 状态栏与对话层提示原因。"""
        if not config.get_model_dispatch():
            return
        config.set_model_dispatch(False)
        self._dispatch_cloud_fails = 0
        self._update_dispatch_btn()
        self._set_status(reason)
        self._append(reason + "\n", "dispatch")

    # ================= LSP 多语言智能提示（启动预热） =================
    def _lsp_warm_loop(self):
        """启动后台：探测工作区开发语言，预热对应 LSP 服务器（前 2 种）。

        只预热（拉起进程过一遍 initialize，让 OS/运行时缓存热起来），
        编辑器打开文件时仍各自懒启动客户端；探测不到或服务器缺失则跳过。
        """
        try:
            import lsp as lsp_mod
            ws = tools.get_workspace()
            langs = lsp_mod.probe_workspace(ws)
            warmed = []
            for lang in langs[:2]:           # 前两大语言，避免拉起太多进程
                if lsp_mod.warm(lang, ws):
                    warmed.append(lang)
            self._lsp_warmed = set(warmed)
            if warmed:
                names = {"python": "Python", "js": "JS/JSX", "ts": "TS/TSX",
                         "go": "Go", "rust": "Rust", "c": "C", "cpp": "C/C++",
                         "java": "Java", "cs": "C#", "ruby": "Ruby",
                         "kotlin": "Kotlin", "swift": "Swift", "php": "PHP",
                         "dart": "Dart", "sh": "Shell", "yaml": "YAML",
                         "vue": "Vue", "html": "HTML", "css": "CSS",
                         "json": "JSON", "erlang": "Erlang"}
                text = "、".join(names.get(l, l) for l in warmed)
                self.root.after(0, lambda: self._set_status(
                    _t("lsp.warmed", langs=text)))
        except Exception:                    # noqa: BLE001  预热失败无碍
            pass

    def _lsp_warm_again(self):
        """切换工作区后重新预热（老的失效，重新探测）。"""
        threading.Thread(target=self._lsp_warm_loop, daemon=True).start()

    def _bind_hint(self, btn, key):
        """悬停按钮时在状态栏显示全称。"""
        btn.bind("<Enter>", lambda e: self._set_status(_t(key)))
        btn.bind("<Leave>", lambda e: self._set_status(_t("top.ready")))

    def _toggle_lang(self):

        """一键切换中/英文界面。"""
        self._switch_lang("zh" if _get_lang() != "zh" else "en")

    def _switch_lang(self, lang):
        """切换界面语言并刷新可见文案。"""
        _set_lang(lang)
        # 刷新当前语言相关标签
        self.root.title(_app_title())
        self.model_btn.config(text=self._model_btn_label())
        self._update_thinking_btn()
        self.sess_btn.config(text="💬")
        if hasattr(self, 'mode_btn') and self.mode_btn:
            self.mode_btn.config(text=MODE_ICON.get(self.mode, "🛡"))
        _set_btn_icon(self.ctx_btn, _ctx_btn_icon())
        self.dir_label.config(text="📁 " + _t("top.dir"))
        self.status_label.config(text=_t("top.ready"))
        self.attach_btn.config(text=_t("top.attach"))
        if hasattr(self, "bottom_model_btn"):
            self.bottom_model_btn.config(text="🤖")
            _set_btn_icon(self.bottom_mode_btn, MODE_ICON.get(self.mode, "🛡"))
        self.voice_btn.config(text=_t("btn.voice"))
        self.send_btn.config(text=_t("btn.send"))
        self.status_badge.config(text=_t("status.idle"))
        # 重设 placeholder：悬浮层文本随语言刷新（内容为空才显示）
        self._ph_label.config(text=_t("input.placeholder"))
        self._ph_update()
        if self.lang_btn:
            self.lang_btn.config(text="中/EN")
        self._update_workspace_label()
        self._set_status(_t("top.ready"))
        # 联动：已打开的本地模型面板跟随主窗体语言
        gpm = getattr(self, "_gpm", None)
        panel = getattr(self, "_gp_panel", None)
        if gpm and panel and hasattr(gpm, "set_lang") and hasattr(panel, "_relabel"):
            try:
                gpm.set_lang(lang)
                panel._relabel()
            except Exception:                # noqa: BLE001  面板已关闭
                pass

    # ================= 端点模型动态探测 =================
    ENDPOINT_SYNC_INTERVAL = 60.0          # 两次探测最小间隔（秒）

    def _maybe_sync_endpoints(self):
        """按节流触发一次端点探测；结果回来后刷新下拉里的模型。

        打开模型菜单时自动拉取各已配置端点的 /models，把支持的模型补进
        下拉（未配置过的自动加入，免手动逐个添加）。
        """
        if self._endpoint_syncing:
            return
        if time.time() - self._endpoint_sync_at < self.ENDPOINT_SYNC_INTERVAL:
            return
        self._endpoint_syncing = True
        threading.Thread(target=self._sync_endpoints_worker, daemon=True).start()

    def _sync_endpoints_worker(self):
        """遍历已配置 provider，探测 /models 并补全缺失模型。"""
        try:
            self._endpoint_sync_at = time.time()
            seen_url = set()
            new_total = 0
            for m in self.models:
                url = m.base_url
                if url in seen_url or not url:
                    continue
                seen_url.add(url)
                pid = m.key.split("/", 1)[0]     # provider id = key 前缀
                try:
                    ids = _fetch_openai_models(url, m.api_key)
                except Exception:                # noqa: BLE001  端点不可用 → 跳过
                    continue
                if ids:
                    new_total += config.augment_provider_models(pid, ids)
            if new_total:
                def _apply():
                    self._refresh_models()
                    self._set_status(_t("probe.found", n=new_total))
                self.root.after(0, _apply)
        finally:
            self._endpoint_syncing = False

    def _provider_name(self, pid: str) -> str:
        """从 models.json 取 provider 的当前显示名（不命中时返回空串）。

        用 live lookup：用户在「设置 → 模型管理」里重命名后，
        下一次打开模型下拉就能看到新名字，无需重启 app。
        """
        try:
            return config.get_provider_name(pid)
        except Exception:                # noqa: BLE001
            return ""

    def _show_model_menu(self, anchor=None):
        """下拉：当前模型 + 按 provider 分组的云端模型 + 本地 GPU + 推理等级。

        管理类（MCP / 缓存 / 派发 / 代码索引 / 语言 / 模型增删）已挪到独立的
        ⚙ 设置菜单，避免 200+ 模型条目和设置项挤在一个下拉里。
        """
        # 打开前触发端点模型探测（60s 节流，后台拉取，完成后自动刷新下拉）
        self._maybe_sync_endpoints()
        if self._endpoint_syncing:
            self._set_status(_t("probe.working"))
        menu = tk.Menu(self.root, tearoff=0, font=(FONT_UI, 10))

        # ---- 当前模型（始终置顶，方便看清当前在用哪个）----
        if self.current_model:
            menu.add_command(
                label=_t("model.current", name=self.current_model.display_name),
                state="disabled")
            menu.add_separator()

        # ---- 按 provider 分组的模型 ----
        # key 形如 "provider_id/model_id"；group 时取前缀。
        from collections import OrderedDict
        cloud_groups: "OrderedDict[str, list]" = OrderedDict()
        for m in self.models:
            pid = m.key.split("/", 1)[0]
            cloud_groups.setdefault(pid, []).append(m)

        cur_pid = (self.current_model.key.split("/", 1)[0]
                   if self.current_model else "")

        for pid, items in cloud_groups.items():
            # 取 provider 显示名（live lookup：用户重命名后立即生效）
            pname = self._provider_name(pid) or items[0].provider_name or pid
            sub = tk.Menu(menu, tearoff=0, font=(FONT_UI, 10))
            self._populate_model_submenu(sub, items)
            mark = " ✓" if pid == cur_pid else ""
            menu.add_cascade(
                label=_t("model.menu.cloud", name=pname, n=len(items)) + mark,
                menu=sub)

        if not cloud_groups:
            menu.add_command(label=_t("model.menu.empty"), state="disabled")

        # ---- 推理等级：直接改当前模型并持久化（对应请求里的 reasoning_effort）----
        # 留在模型菜单——它作用于当前模型，不属于通用设置。
        if self.current_model:
            menu.add_separator()
            cur_effort = (getattr(self.current_model, "reasoning_effort", "") or "").strip()
            eff = tk.Menu(menu, tearoff=0, font=(FONT_UI, 10))
            for val in self._reasoning_choices():
                label = _reasoning_label(val)
                mark = "  ✓" if val == cur_effort else ""
                eff.add_command(label=label + mark,
                                command=lambda v=val: self._set_reasoning(v))
            menu.add_cascade(
                label=_t("model.reasoning")
                + (f" ({cur_effort})" if cur_effort
                   else f" ({_t('model.reasoning.default')})"),
                menu=eff)

        tgt = anchor or self.model_btn
        x = tgt.winfo_rootx()
        y = tgt.winfo_rooty() + tgt.winfo_height()
        menu.tk_popup(x, y)

    def _populate_model_submenu(self, sub, items):
        """把一组模型塞进子菜单；按字母排序、当前模型置顶。"""
        items = sorted(items, key=lambda m: m.display_name)
        # 当前模型提到最前面，避免翻页
        if self.current_model:
            for i, m in enumerate(items):
                if m.key == self.current_model.key:
                    if i:
                        items.insert(0, items.pop(i))
                    break
        for m in items:
            mark = " ✓" if (self.current_model and m.key == self.current_model.key) else ""
            caps = ""
            if m.vision:
                caps += " 👁"
            if getattr(m, "reasoning", False):
                caps += " 🧠"
            label = f"{m.display_name}{caps}{mark}"
            sub.add_command(label=label,
                            command=lambda k=m.key: self._select_model(k))

    def _show_settings_menu(self, anchor=None):
        """独立的设置菜单：模型管理 / MCP / 缓存 / 派发 / 代码索引 / 语言。"""
        menu = tk.Menu(self.root, tearoff=0, font=(FONT_UI, 10))
        menu.add_command(label=_t("model.manage"),
                         command=self._manage_models)
        menu.add_command(label=_t("model.mcp"),
                         command=self._manage_mcp)
        menu.add_command(label=_t("model.cache"),
                         command=self._manage_cache)
        if _feature("dispatch"):
            menu.add_command(label=_t("model.dispatch"),
                             command=self._manage_dispatch)
        menu.add_command(label=_t("model.index"),
                         command=self._rebuild_codeindex)
        if not _feature("zh_only", False):
            menu.add_separator()
            lang = tk.Menu(menu, tearoff=0, font=(FONT_UI, 10))
            cur = _get_lang()
            lang.add_command(label=_t("lang.en") + ("  ✓" if cur != "zh" else ""),
                             command=lambda: self._switch_lang("en"))
            lang.add_command(label=_t("lang.zh") + ("  ✓" if cur == "zh" else ""),
                             command=lambda: self._switch_lang("zh"))
            menu.add_cascade(label=_t("lang.menu"), menu=lang)
        tgt = anchor or self.settings_btn
        x = tgt.winfo_rootx()
        y = tgt.winfo_rooty() + tgt.winfo_height()
        menu.tk_popup(x, y)

    def _rebuild_codeindex(self):
        """后台重建当前工作目录的代码索引（模型工具 index_search 使用）。"""
        import codeindex
        ws = tools.get_workspace()
        self._set_status(_t("msg.indexing"))

        def worker():
            try:
                st = codeindex.build(ws, force=True)
                self._set_status(_t("msg.index_done",
                                      files=st['files_indexed'],
                                      chunks=codeindex.stats(ws)['chunks'],
                                      sec=st['seconds']))
            except Exception as e:  # noqa: BLE001
                self._set_status(_t("msg.index_fail", err=e))

        threading.Thread(target=worker, daemon=True).start()

    def _manage_cache(self):
        """缓存管理窗口（实现在 ui_panel_cache.py）。"""
        import ui_panel_cache
        ui_panel_cache.show(self)

    def _manage_dispatch(self):
        """模型派发设置窗口（实现在 ui_panel_dispatch.py）。"""
        import ui_panel_dispatch
        ui_panel_dispatch.show(self)

    def _open_quant_panel(self):
        """策略互转面板（实现在 ui_panel_quant.py；仅量化产品有此入口）。"""
        import ui_panel_quant
        ui_panel_quant.show(self)

    def _open_kb_panel(self):
        """公司知识库管理面板（实现在 ui_panel_kb.py；rag 功能开关）。"""
        import ui_panel_kb
        ui_panel_kb.show(self)

    # ---- 顶栏派发快捷开关 ----
    def _dispatch_brain_healthy(self) -> bool:
        """大脑健康核验：本地 GPU 腿已移除，派发只剩云端腿，视为恒健康。

        云端目标/网络可达性由 _dispatch_check_loop 的云端探测单独把关。
        """
        return True

    def _update_dispatch_btn(self):
        """按 开关+大脑状态 刷新顶栏按钮文字（● 生效 / ○ 未生效 / 关）。"""
        if getattr(self, "dispatch_btn", None) is None:
            return                      # 产品开关关闭时无此按钮
        if not config.get_model_dispatch():
            self.dispatch_btn.config(text="⚡", fg="#94a3b8")
        elif self._dispatch_brain_healthy():
            self.dispatch_btn.config(text="●", fg="#16a34a")
        else:
            self.dispatch_btn.config(text="○", fg="#d97706")

    def _toggle_dispatch(self):
        """左键：切换模型派发总开关（不自动启动本地模型）。"""
        on = not config.get_model_dispatch()
        config.set_model_dispatch(on)
        self._update_dispatch_btn()
        name = config.get_dispatch_model().split("/")[-1]
        if not on:
            self._set_status(_t("dispatch.topbar.now_off"))
        elif self._dispatch_brain_healthy():
            self._set_status(_t("dispatch.topbar.now_on_active", name=name))
        else:
            self._set_status(_t("dispatch.topbar.now_on_inactive", name=name))

    def _manage_models(self):
        """模型管理窗口（实现在 ui_panel_models.py）。"""
        import ui_panel_models
        ui_panel_models.show_manager(self)

    def _model_add_dialog(self, parent, on_done):
        """添加模型对话框（实现在 ui_panel_models.py）。"""
        import ui_panel_models
        ui_panel_models._add_dialog(self, parent, on_done)

    def _model_edit_dialog(self, parent, m, on_done):
        """编辑模型对话框（实现在 ui_panel_models.py）。"""
        import ui_panel_models
        ui_panel_models._edit_dialog(self, parent, m, on_done)

    def _show_mode_menu(self, anchor=None):
        menu = tk.Menu(self.root, tearoff=0, font=(FONT_UI, 10))
        for m in (agent_mod.MODE_READONLY, agent_mod.MODE_ASK, agent_mod.MODE_ALWAYS):
            mark = "  ✓" if m == self.mode else ""
            menu.add_command(label=f"{MODE_ICON.get(m,'🛡')} {_mode_label(m)}{mark}",
                             command=lambda mm=m: self._select_mode(mm))
        tgt = anchor or getattr(self, 'mode_btn', None)
        x = tgt.winfo_rootx()
        y = tgt.winfo_rooty() + tgt.winfo_height()
        menu.tk_popup(x, y)

    def _select_mode(self, mode):
        self.mode = mode
        if hasattr(self, 'mode_btn') and self.mode_btn:
            self.mode_btn.config(text=MODE_ICON.get(mode, "🛡"))
        self._set_status(_t("st.perm", m=_mode_label(mode)))
        if hasattr(self, "bottom_mode_btn"):
            _set_btn_icon(self.bottom_mode_btn, MODE_ICON.get(mode, "🛡"))

    def _toggle_ctx(self):
        """切换 续上下文 ⇄ 独立提问，并持久化到 models.json。"""
        on = not config.get_standalone()
        config.set_standalone(on)
        self.ctx_btn.config(text=_t(_ctx_label_key()))
        self._set_status(_t("ctx.standalone_hint" if on else "ctx.keep_hint"))

    # ================= 样式 =================
    def _append_style(self):
        # 字号基准：b = 聊天基础字号（用户可调，持久化），其余标签相对缩放
        b = getattr(self, "_font_chat", 10)
        s1, s2 = max(8, b - 1), max(8, b - 2)   # 小一号 / 小两号
        # 用户/助手只靠背景色区分：不加粗、无额外行距
        self.chat.tag_config("user", font=(FONT_UI, b),
                             background=theme.ACCENT_SOFT,  # 浅主题色：用户消息
                             spacing1=4, spacing3=2,
                             lmargin1=8, lmargin2=8)
        # 用户消息左侧主题色强调条（▍ 字符单独打标）
        self.chat.tag_config("userbar", font=(FONT_MONO, b + 1),
                             foreground=theme.ACCENT, background=theme.ACCENT_SOFT)
        self.chat.tag_config("assistant", font=(FONT_UI, b),
                             background=theme.BOT_BUBBLE,   # 浅灰：助手回复
                             spacing1=0, spacing3=2,
                             lmargin1=8, lmargin2=8)
        self.chat.tag_config("tool", font=(FONT_UI, b), spacing1=8)
        self.chat.tag_config("toolresult", font=(FONT_MONO, s2))
        self.chat.tag_config("dispatch", font=(FONT_UI, b),
                             foreground=theme.DISPATCH, spacing1=8)
        # 工具返回美化：标题条目 / 灰色摘要 / 蓝色可点链接
        self.chat.tag_config("toolhead", font=(FONT_UI, b, "bold"),
                             spacing1=6, lmargin1=8, lmargin2=8)
        self.chat.tag_config("toolitem", font=(FONT_UI, b),
                             lmargin1=16, lmargin2=16, wrap="word")
        self.chat.tag_config("toolnote", font=(FONT_UI, s1), foreground=theme.MUTED,
                             lmargin1=16, lmargin2=16, wrap="word")
        self.chat.tag_config("toollink", font=(FONT_MONO, s1), foreground=theme.ACCENT,
                             underline=True, lmargin1=16, lmargin2=16)
        self.chat.tag_config("meta", font=(FONT_UI, s1))
        self.chat.tag_config("denied", font=(FONT_UI, b, "bold"))
        self.chat.tag_config("spinner", font=(FONT_MONO, b + 1), foreground=theme.MUTED)

        # Markdown 格式化标签
        self.chat.tag_config("mdh1", font=(FONT_UI, b + 4, "bold"), spacing1=6,
                             spacing3=4, lmargin1=8)
        self.chat.tag_config("mdh2", font=(FONT_UI, b + 2, "bold"), spacing1=6,
                             spacing3=2, lmargin1=8)
        self.chat.tag_config("mdh3", font=(FONT_UI, b + 1, "bold"), spacing1=4,
                             lmargin1=8)
        self.chat.tag_config("mdbold", font=(FONT_UI, b, "bold"))
        self.chat.tag_config("mditalic", font=(FONT_UI, b, "italic"))
        self.chat.tag_config("mdcode", font=(FONT_MONO, s1), background=theme.BORDER,
                             foreground=theme.TEXT)
        self.chat.tag_config("mdcodeblock", font=(FONT_MONO, s2),
                             background=theme.CODE_BLOCK_BG,
                             foreground=theme.CODE_BLOCK_FG,
                             lmargin1=10, lmargin2=10, spacing1=4, spacing3=4)
        self.chat.tag_config("mdlist", font=(FONT_UI, b), lmargin1=14,
                             lmargin2=14)
        self.chat.tag_config("mdquote", font=(FONT_UI, s1, "italic"),
                             foreground=theme.MUTED, lmargin1=10, lmargin2=10)

    def _append(self, text, tag=None):
        def _w():
            self.chat.config(state="normal")
            # 转轮还在转时，新内容插到转轮行之前（转轮始终在最后）
            rng = self._spinner_range() if self._spinner_after is not None else None
            pos = rng[0] if rng else "end"
            if tag:
                self.chat.insert(pos, text, tag)
            else:
                self.chat.insert(pos, text)
            self.chat.see("end")
            self.chat.config(state="disabled")
        self.root.after(0, _w)

    def _append_segments(self, segs):
        """按片段插入富文本：链接可点击、「查看全文」弹窗显示完整内容。"""
        def _w():
            self.chat.config(state="normal")
            # 转轮还在转时，新内容插到转轮行之前（转轮始终在最后）
            rng = self._spinner_range() if self._spinner_after is not None else None
            pos = rng[0] if rng else "end"
            for seg in segs:
                chunk = seg.get("text", "")
                tags = []
                if seg.get("tag"):
                    tags.append(seg["tag"])
                url, popup = seg.get("url"), seg.get("popup")
                if url or popup:
                    # 每个链接独立标签：绑定各自的 URL / 弹窗内容
                    self._link_seq += 1
                    utag = f"link{self._link_seq}"
                    self.chat.tag_config(utag, foreground="#2563eb",
                                         underline=True)
                    if url:
                        self.chat.tag_bind(
                            utag, "<Button-1>", lambda e, u=url: _open_url(u))
                    else:
                        def _pop(_e, p=popup):
                            _show_text_window(self.chat, p[0], p[1])
                        self.chat.tag_bind(utag, "<Button-1>", _pop)
                    self.chat.tag_bind(utag, "<Enter>",
                                       lambda e: self.chat.config(cursor="hand2"))
                    self.chat.tag_bind(utag, "<Leave>",
                                       lambda e: self.chat.config(cursor=""))
                    tags.append(utag)
                start = self.chat.index(pos)
                if tags:
                    self.chat.insert(start, chunk, tags)
                else:
                    self.chat.insert(start, chunk)
                pos = self.chat.index(f"{start}+{len(chunk)}c")
            self.chat.see("end")
            self.chat.config(state="disabled")
        self.root.after(0, _w)

    def _render_tool_result(self, name, result):
        """工具返回美化渲染：结构化卡片 / 链接可点 / 超长折叠可看全文。

        代码类工具（read_file/grep/…）结果直接按浅色方案语法高亮显示（DSH 式）。
        """
        if name in ("read_file", "grep_search", "glob_search", "index_search") \
                and result and len(result) > 40:
            lines = result.split("\n")
            PREVIEW = 15
            if len(lines) > PREVIEW + 2:
                # 长/重复 → 只显示前几行 + 查看全文，避免刷屏
                self._insert_highlighted_code("\n".join(lines[:PREVIEW]),
                                              "python", dark=False, base_tag="toolresult",
                                              code_font="toolresult")
                n = len([l for l in lines if l.strip()])
                self._append_segments([
                    {"text": _t("tool.preview_more", n=n), "tag": "toolnote"},
                    {"text": _t("view.full") + "\n", "tag": "toollink",
                     "popup": (_t("popup.tool", name=name), result)}])
                return
            self._insert_highlighted_code(result, "python", dark=False,
                                          base_tag="toolresult", code_font="toolresult")
            return
        try:
            segs = _format_tool_result(name, result)
        except Exception:  # noqa: BLE001  格式化失败退回纯文本展示
            shown = result if len(result) <= _DISPLAY_MAX \
                else result[:_DISPLAY_MAX] + "\n…"
            segs = [{"text": shown + "\n", "tag": "toolresult"},
                    {"text": _t("view.full") + "\n", "tag": "toollink",
                     "popup": (_t("popup.tool", name=name), result)}]
        self._append_segments(segs)

    def _set_status(self, text, color=None):
        self.root.after(0, lambda: self.status_label.config(text=text))

    # ================= 右侧动态状态徽标 =================
    BADGE_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def badge_busy(self, label: str = _t("ui.busy")):
        """进入忙碌态：转轮动画 + 绿色。"""
        def _start():
            self._badge_label = label
            self._badge_tick()
        self.root.after(0, _start)

    def _badge_tick(self):
        if self._badge_after is not None:
            self.root.after_cancel(self._badge_after)
            self._badge_after = None
        frame = self.BADGE_FRAMES[self._badge_idx % len(self.BADGE_FRAMES)]
        self._badge_idx += 1
        self.status_badge.config(text=f"{frame} {self._badge_label}",
                                 fg="#2563eb")
        self._badge_after = self.root.after(120, self._badge_tick)

    def badge_done(self, ok: bool = True):
        """完成：停止动画，显示 ✓（2 秒后回空闲）。"""
        def _stop():
            if self._badge_after is not None:
                self.root.after_cancel(self._badge_after)
                self._badge_after = None
            self.status_badge.config(
                text=(_t("ui.ok") if ok else _t("ui.err")),
                fg=("#16a34a" if ok else "#dc2626"))
            if self._badge_after is not None:
                self.root.after_cancel(self._badge_after)
            self._badge_idle_after = self.root.after(
                2000, lambda: (self.status_badge.config(text=_t("status.idle"), fg="#94a3b8"),
                               setattr(self, "_badge_idle_after", None)))
        self.root.after(0, _stop)

    # ================= token 统计 =================
    def _update_usage(self, total: dict):
        """Agent 报告 usage 时累计并刷新统计栏。"""
        for k, v in total.items():
            if isinstance(v, int):
                self.usage_total[k] = self.usage_total.get(k, 0) + 0
        # Agent 传来的 total 是「该次对话累计」，直接取大者避免重复加
        for k in ("prompt_tokens", "completion_tokens", "total_tokens",
                  "cached_tokens", "reasoning_tokens", "requests"):
            v = total.get(k)
            if isinstance(v, int) and v > self.usage_total.get(k, 0):
                self.usage_total[k] = v
        self._render_usage()

    def _render_usage(self):
        u = self.usage_total
        cached_pct = (u["cached_tokens"] / u["prompt_tokens"] * 100
                      if u["prompt_tokens"] else 0)
        # 文案统一由 _stat_text 按当前语言生成（此处不再重复拼接）
        text = _stat_text(u, cached_pct, fast_hits=self.cache_hits,
                          saved=self.cache_saved_tokens)
        self.root.after(0, lambda: self.stat_var.set(text))

    def _reset_usage(self):
        """点击统计栏清零。"""
        self.usage_total = {k: 0 for k in self.usage_total}
        self.cache_hits = 0
        self.cache_saved_tokens = 0
        self._render_usage()
        self._set_status(_t("ui.usage_reset"))

    # ================= 转动等待动画 =================
    SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"   # 盲文转轮
    SPINNER_INTERVAL = 120                      # 毫秒/帧

    def _spinner_range(self):
        """转轮文本（tag=spinner）的范围 (start, end)；无则 None。"""
        ranges = self.chat.tag_ranges("spinner")
        if not ranges:
            return None
        return str(ranges[0]), str(ranges[-1])

    def _spinner_delete(self):
        """删除当前转轮文本。"""
        rng = self._spinner_range()
        if rng:
            self.chat.delete(rng[0], rng[1])

    def _spinner_start(self, base_text=None):
        base_text = base_text or _t("ui.processing")
        """启动聊天区转轮动画：任务进行中显示一行转动的等待符号。"""
        def _start():
            if self._spinner_after is not None:
                # 已在转：只更新提示文字
                self._spinner_base = base_text
                return
            self._spinner_idx = 0
            self._spinner_base = base_text
            self._spinner_tick()
        self.root.after(0, _start)

    def _spinner_tick(self):
        frame = self.SPINNER_FRAMES[self._spinner_idx % len(self.SPINNER_FRAMES)]
        self._spinner_idx += 1
        self.chat.config(state="normal")
        self._spinner_delete()
        self.chat.insert("end", f"{frame} {self._spinner_base}\n", "spinner")
        self.chat.see("end")
        self.chat.config(state="disabled")
        self._spinner_after = self.root.after(self.SPINNER_INTERVAL, self._spinner_tick)

    def _spinner_stop(self):
        """停止转轮并删掉等待行（回复完成时调用）。"""
        def _stop():
            if self._spinner_after is not None:
                self.root.after_cancel(self._spinner_after)
                self._spinner_after = None
            self.chat.config(state="normal")
            self._spinner_delete()
            self.chat.config(state="disabled")
        self.root.after(0, _stop)

    # ================= 工作目录 =================
    def _change_workspace(self):
        path = filedialog.askdirectory(title=_t("pick.dir"),
                                       initialdir=tools.get_workspace())
        if path:
            tools.set_workspace(path)
            config.save_last_workspace(path)   # 记住，下次启动恢复
            self._close_all_file_views()       # 切目录：旧目录打开的文件标签一并关掉
            self._update_workspace_label()
            branch = tools.git_branch(path)
            self._set_status(_t("st.dir", p=path) if not branch
                             else _t("st.dir_branch", p=path, b=branch))
            # 工作区变了 → 重新探测并预热对应语言的 LSP
            self._lsp_warm_again()

    def _update_workspace_label(self):
        path = tools.get_workspace()
        branch = tools.git_branch(path)
        self.ws_var.set(path)
        if hasattr(self, "branch_var"):
            self.branch_var.set(f"⧉ {branch}" if branch else "")
        # 工作区变化时同步刷新右侧文件树，保证显示当前目录的代码文件
        if _feature("editor"):
            self._refresh_file_panel()

    # ================= 审批（聊天底部内嵌条） =================
    # 审批超时：用户长时间不响应则自动拒绝，避免工作线程永久挂起
    APPROVAL_TIMEOUT = 600  # 秒

    def _make_approval_bar(self, name, summary, result, done):
        """内嵌审批条：停靠在聊天底部（统计栏与输入框之间），不再弹独立窗口。

        result/done 由按钮回调写入；返回条容器（超时由调用方销毁）。
        """
        import tkinter as _tk2
        from tkinter import scrolledtext as _st

        bar = tk.Frame(self.center, bg=theme.PANEL,
                       highlightthickness=1, highlightbackground=theme.ACCENT)
        head = tk.Frame(bar, bg=theme.PANEL)
        head.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(head, text="\U0001F6E1 " + _t("ui.approve_want", name=name),
                 font=(FONT_UI, 10, "bold"), fg=theme.TEXT,
                 bg=theme.PANEL).pack(side="left")

        closed = [False]   # 幂等防护：按钮/回车/超时销毁可能并发触发

        def _finish(approved: bool):
            if closed[0]:
                return
            closed[0] = True
            result["approved"] = approved
            try:
                bar.destroy()
            except tk.TclError:
                pass
            done.set()

        def _btn(text, bg, fg, hbg, cmd):
            b = tk.Button(head, text=text, command=cmd, width=8, bd=0,
                          relief="flat", cursor="hand2", padx=10, pady=3,
                          font=(FONT_UI, theme.FS_TOOLBAR), bg=bg, fg=fg,
                          activebackground=hbg, highlightthickness=0)
            b.bind("<Enter>", lambda _e: b.config(bg=hbg))
            b.bind("<Leave>", lambda _e: b.config(bg=bg))
            return b
        allow_btn = _btn(_t("btn.allow"), theme.ACCENT, "#ffffff",
                         "#1d4ed8", lambda: _finish(True))
        allow_btn.pack(side="right", padx=(6, 0))
        deny_btn = _btn(_t("btn.deny"), theme.BG, theme.TEXT,
                        theme.BORDER, lambda: _finish(False))
        deny_btn.pack(side="right")

        # 参数摘要：最多 6 行，超出内部滚动
        box = _st.ScrolledText(bar, wrap="word", font=(FONT_MONO, 9),
                               height=max(2, min(6, summary.count("\n") + 1)),
                               relief="flat", borderwidth=0,
                               background=theme.PANEL, foreground=theme.TEXT,
                               highlightthickness=1,
                               highlightbackground=theme.BORDER)
        box.insert("1.0", summary)
        box.config(state="disabled")
        _enable_text_copy(box)
        box.pack(fill="x", padx=10, pady=(0, 8))

        # 键盘：回车=允许，Esc=拒绝（焦点在条内时生效）
        bar.bind("<Return>", lambda _e: _finish(True))
        bar.bind("<Escape>", lambda _e: _finish(False))
        bar.pack(fill="x", padx=16, pady=(0, 4), after=self.stat_frame)
        try:
            allow_btn.focus_set()
        except _tk2.TclError:
            pass
        return bar

    @staticmethod
    def _destroy_if_alive(win):
        try:
            if win.winfo_exists():
                win.destroy()
        except Exception:  # noqa: BLE001
            pass

    def _approve(self, name, args, summary):
        # 双保险：非「每次询问」模式一律放行，不弹审批
        # （正常情况下 Agent 不会在 always/readonly 模式调到这里）
        if self.mode != agent_mod.MODE_ASK:
            return True
        result = {"approved": False}
        done = threading.Event()
        holder = {}

        def _show():
            # 显示前再查一次模式：本轮以 ask 发出、但用户中途已切「总是允许」
            # → 自动允许（所见即所得）
            if self.mode != agent_mod.MODE_ASK:
                result["approved"] = True
                done.set()
                return
            # 内嵌审批条：停靠聊天底部，与聊天同层，不再弹独立窗口
            bar = self._make_approval_bar(name, summary, result, done)
            holder["win"] = bar
            try:
                bar.focus_set()
            except Exception:        # noqa: BLE001
                pass

        self.root.after(0, _show)
        done.wait(timeout=self.APPROVAL_TIMEOUT)
        if not done.is_set():
            self._append(_t("ui.approve_timeout") + "\n", "denied")
            win = holder.get("win")
            if win is not None:
                self.root.after(0, lambda w=win: self._destroy_if_alive(w))
            return False
        return result["approved"]

    # ================= 发送 / 停止 =================
    def _render_queue(self):
        """重绘排队消息栏。"""
        for w in self.queue_bar.winfo_children():
            w.destroy()
        if not self._msg_queue:
            return
        self.queue_bar.pack(fill="x", pady=(0, 2))
        for i, text in enumerate(self._msg_queue):
            ic = tk.Frame(self.queue_bar)
            ic.pack(side="left", padx=(0, 6))
            tk.Label(ic, text="🕐 " + text[:40], font=(FONT_UI, 9), fg="#334155").pack(side="left")
            e = tk.Label(ic, text="✎", font=(FONT_UI, 9), fg="#2563eb", cursor="hand2")
            e.pack(side="left", padx=(4, 0))
            e.bind("<Button-1>", lambda ev, idx=i: self._queue_edit(idx))
            x = tk.Label(ic, text="✕", font=(FONT_UI, 9), fg="#dc2626", cursor="hand2")
            x.pack(side="left", padx=(2, 0))
            x.bind("<Button-1>", lambda ev, idx=i: self._queue_delete(idx))

    def _queue_current(self):
        """把当前输入文字加入排队；清空输入框。"""
        text = self.input.get("1.0", "end").strip()
        if not text:
            return
        if self._placeholder_active:
            self.input.delete("1.0", "end")
            self._placeholder_active = False
        self.input.delete("1.0", "end")
        self._msg_queue.append(text)
        self._render_queue()
        return "break"

    def _queue_edit(self, idx):
        """把排队第 idx 条取回输入框编辑。"""
        if 0 <= idx < len(self._msg_queue):
            text = self._msg_queue.pop(idx)
            self._render_queue()
            if self._placeholder_active:
                self.input.delete("1.0", "end")
                self._placeholder_active = False
            self.input.insert("1.0", text)
            self.input.config(fg="black")
            self.input.focus_set()

    def _queue_delete(self, idx):
        if 0 <= idx < len(self._msg_queue):
            self._msg_queue.pop(idx)
            self._render_queue()

    # ---- /command 斜杠命令 ----
    _COMMANDS = [
        ("/help", "cmd.help", "help"),
        ("/init", "cmd.init", "init"),
        ("/brainstorm", "cmd.brainstorm", "brainstorm"),
        ("/plan", "cmd.plan", "plan"),
        ("/work", "cmd.work", "work"),
        ("/loop", "cmd.loop", "loop"),
        ("/compress", "cmd.compress", "compress"),
        ("/new", "cmd.new", "new"),
        ("/clear", "cmd.clear", "clear"),
        ("/model", "cmd.model", "model"),
        ("/dir", "cmd.dir", "dir"),
        ("/reasoning", "cmd.reasoning", "reasoning"),
        ("/permission", "cmd.permission", "permission"),
        ("/context", "cmd.context", "context"),
        ("/index", "cmd.index", "index"),
        ("/cache", "cmd.cache", "cache"),
        ("/mcp", "cmd.mcp", "mcp"),
        ("/sessions", "cmd.sessions", "sessions"),
        ("/delete", "cmd.delete", "delete"),
        ("/refresh", "cmd.refresh", "refresh"),
    ]

    def _show_command_menu(self, anchor=None):
        """➕ 按钮：斜杠命令速查菜单。

        用统一的候选弹窗（原生气泡菜单在窗口底部会向下展开到屏幕外，
        看起来像"点了没反应"）。点选命令 → 插入输入框（可补参数后发送）。
        """
        cmds = [c for c, _d, _k in self._COMMANDS]
        rows = [(f"{c}   {_t(d)}", _emoji_icon("26a1"))
                for c, d, _k in self._COMMANDS]
        self._command_menu_cmds = [c for c, _d, _k in self._COMMANDS]
        try:
            pop, lb = self._show_token_popup(rows, self._on_command_menu_pick)
            self._command_menu_pop = pop
            self._command_menu_lb = lb
        except Exception as e:        # noqa: BLE001
            self._set_status(str(e))

    def _on_command_menu_pick(self, i):
        cmd = getattr(self, "_command_menu_cmds", [None] * (i + 1))[i]
        if cmd:
            self._insert_command(cmd)

    def _insert_command(self, cmd):
        if self._placeholder_active:
            self.input.delete("1.0", "end"); self._placeholder_active = False
        self.input.insert("insert", cmd + " ")
        self.input.focus_set()

    def _run_command(self, text):
        """本地执行以 / 开头的命令；返回 True 表示已处理（不发给模型）。"""
        import re as _re
        text = text.strip()
        if not text.startswith("/"):
            return False
        m = _re.match(r"^(/\S+)\s*(.*)$", text)
        cmd = (m.group(1) if m else text).lower()
        arg = (m.group(2).strip() if m else "")
        try:
            if cmd in ("/help",):
                self._show_help()
            elif cmd == "/new":
                self._new_session()
            elif cmd == "/clear":
                self.clear()
            elif cmd in ("/permission",):
                self._set_status(_t("st.perm", m=_t("mode.ask"))); self.show_mode_help(arg)
            elif cmd == "/context":
                self._toggle_ctx(); 
            elif cmd in ("/reasoning",):
                self._set_reasoning(arg or "medium")
            elif cmd == "/model":
                self._show_model_menu(anchor=self.cmd_plus)
            elif cmd == "/dir":
                self._change_workspace()
            elif cmd == "/index":
                self._rebuild_codeindex()
            elif cmd == "/cache":
                self._manage_cache()
            elif cmd == "/mcp":
                self._manage_mcp()
            elif cmd == "/sessions":
                self._list_all_sessions()
            elif cmd == "/delete":
                self._delete_current_session()
            elif cmd == "/refresh":
                self._refresh_all()
            elif cmd in ("/compress", "/compact"):
                self._compress_session()
            elif cmd == "/init":
                self._cmd_send(_t("init.prompt"))
            elif cmd == "/brainstorm":
                self._cmd_prompted(arg, _t("brainstorm.prompt"))
            elif cmd == "/plan":
                self._cmd_prompted(arg, _t("plan.prompt"))
            elif cmd == "/work":
                self._cmd_prompted(arg, _t("work.prompt"))
            elif cmd == "/loop":
                self._cmd_prompted(arg, _t("loop.prompt"))
            else:
                self._set_status(_t("q.unknown", c=cmd))
        except Exception as e:  # noqa: BLE001
            self._set_status(_t("q.fail", e=str(e)))
        return True

    def _cmd_send(self, prompt: str):
        """命令注入提示词，走正常发送链路（含计划面板/审批/缓存）。"""
        if self._running:
            self._set_status(_t("ui.running"))
            return
        self._send_with(prompt, [])

    def _cmd_prompted(self, arg: str, prompt: str):
        """带任务参数的模式命令：有参立即发送；无参把模板填进输入框让用户补全。"""
        if arg:
            self._cmd_send(prompt.format(arg=arg))
        else:
            def _w():
                self.input.delete("1.0", "end")
                self.input.insert("1.0", prompt.format(arg="（在这里补充任务描述）"))
                self.input.config(fg="black")
                self._placeholder_active = False
                self.input.focus_set()
            self.root.after(0, _w)
            self._set_status(_t("q.need_arg"))

    def _compress_session(self):
        """/compress：把当前会话历史压缩成摘要，替换旧消息（保留最近几轮原文）。"""
        if self._running:
            self._set_status(_t("ui.running"))
            return
        msgs = list(self.messages or [])
        import context as _ctx
        import llm as _llm
        sys_head = msgs[:1] if (msgs and msgs[0].get("role") == "system") else []
        rest = msgs[len(sys_head):]
        keep_n = int(getattr(config, "CONTEXT_KEEP_ROUNDS", 2)) * 2
        if len(rest) <= keep_n + 2:
            self._set_status(_t("compress.short"))
            return
        to_sum = rest[:-keep_n]
        keep = rest[-keep_n:]
        model = self.current_model
        before = _ctx.estimate_tokens(msgs)
        self._set_status(_t("compress.working"))

        def _worker():
            summary = []
            try:
                smsgs = [{"role": "system", "content": _t("compress.prompt")}] + to_sum
                for ev in _llm.stream_chat(model, smsgs, tools=None):
                    if ev["type"] == "text":
                        summary.append(ev["delta"])
            except Exception as e:        # noqa: BLE001
                self.root.after(0, lambda: self._set_status(
                    _t("compress.fail", e=str(e)[:120])))
                return
            if not summary:
                self.root.after(0, lambda: self._set_status(_t("compress.fail",
                                                                e="empty")))
                return
            new_msgs = sys_head + [
                {"role": "user", "content": _t("compress.header") + "".join(summary)},
                {"role": "assistant", "content": _t("compress.ack")},
            ] + keep
            after = _ctx.estimate_tokens(new_msgs)
            self.messages = new_msgs
            try:
                import sessions as sess_mod
                sess_mod.save(self.session_id, self.messages,
                              getattr(self, "session_title", "") or "会话",
                              workspace=tools.get_workspace())
            except Exception:            # noqa: BLE001  落盘失败不影响本次压缩
                pass
            self.root.after(0, lambda: (
                self._append(_t("compress.done",
                                before=before, after=after) + "\n", "meta"),
                self._set_status(_t("compress.done",
                                    before=before, after=after))))

        threading.Thread(target=_worker, daemon=True).start()

    # ---- 输入框 /命令 联想 ----
    def _cmd_hide(self):
        if getattr(self, "_cmd_pop", None) and self._cmd_pop.winfo_exists():
            try: self._cmd_pop.destroy()
            except Exception: pass
        self._cmd_pop = None

    def _cmd_insert(self):
        try:
            idx = self.input.index("insert")
            line_start = self.input.index(f"{idx} linestart")
            prefix = self.input.get(line_start, idx)
            import re
            m = re.search(r"/[a-z]*$", prefix)
            word = m.group(0) if m else "/"
            start = f"{line_start}+{max(0, len(prefix) - len(word))}c"
            self.input.delete(start, idx)
            # 优先取弹窗列表的实际选中项（键盘选择/鼠标点选都一致）
            i = self._cmd_idx
            try:
                sel = self._cmd_lb.selection()
                if sel:
                    i = _tv_index(self._cmd_lb)
            except Exception:        # noqa: BLE001
                pass
            self.input.insert(start, self._cmd_cands[i] + " ")
        except Exception:            # noqa: BLE001
            pass
        self._cmd_hide()

    # ---- @ 文件/目录选择（参考 Cursor）----
    def _show_token_popup(self, rows, on_pick):
        """输入光标处的候选弹窗（/命令 与 @文件 共用）。

        rows: [(label, icon_photo_or_None)]。
        定位：优先光标下方；下方放不下改到光标上方；最后夹紧屏幕内。
        交互：滚轮滚动；单击 = 选中并回调 on_pick(索引)；图标走彩色 PNG。
        """
        pop = tk.Toplevel(self.root)
        pop.overrideredirect(True)
        lb = ttk.Treeview(pop, columns=("label",), show="tree",
                          selectmode="browse", height=min(len(rows), 10))
        for label, img in rows:
            kw = {"text": label}
            if img is not None:
                kw["image"] = img
            lb.insert("", "end", **kw)
        if rows:
            lb.selection_set(lb.get_children("")[0])
        lb.pack(fill="both", expand=True)

        def _wheel(e):
            lb.yview_scroll(-1 * ((e.delta // 120) or 1), "units")

        def _pick(e):
            sel = lb.selection()
            if sel:
                on_pick(lb.index(sel[0]))

        lb.bind("<MouseWheel>", _wheel)
        lb.bind("<Button-1>", _pick)

        # ---- 键盘：弹窗接管全部按键（焦点显式给列表）----
        # 设计：lb.focus_set() 让键盘事件确定性地进入弹窗；回车/Tab 确认、
        # ↑↓ 选择、Esc 关闭、字符/退格转发回输入框后重过滤。
        # （输入框自己的 KeyPress 处理器仍保留，覆盖点击输入框后的场景。）
        def _popup_key(e):
            k = e.keysym
            if k in ("Return", "KP_Enter", "Tab"):
                on_pick(_tv_index(lb))
                return "break"
            if k == "Escape":
                self._cmd_hide()
                self._at_hide()
                return "break"
            if k in ("Up", "Down"):
                _tv_select(lb, _tv_index(lb) + (1 if k == "Down" else -1))
                return "break"
            if k == "BackSpace":
                self.input.delete("insert-1c", "insert")
                self.root.after(0, self._popup_rescan)
                return "break"
            if e.char and e.char.isprintable():
                self.input.insert("insert", e.char)
                self.root.after(0, self._popup_rescan)
                return "break"
            return None

        for _w in (pop, lb):
            _w.bind("<Key>", _popup_key)
        lb.focus_set()

        # ---- 定位：先算可用空间，再决定上/下 ----
        pop.update_idletasks()
        bbox = self.input.bbox("insert")
        x = self.input.winfo_rootx() + (bbox[0] if bbox else 0)
        caret_y = self.input.winfo_rooty() + (bbox[1] if bbox else 0)
        line_h = (bbox[3] - bbox[1]) if bbox else 20
        h = lb.winfo_reqheight() + 4
        w = max(pop.winfo_reqwidth(), 240)
        sh, sw = pop.winfo_screenheight(), pop.winfo_screenwidth()
        below_y = caret_y + line_h + 6
        if below_y + h <= sh - 8:
            y = below_y                    # 下方放得下 → 光标下方
        else:
            y = max(8, caret_y - h - 6)    # 放不下 → 改到光标上方
        x = max(8, min(x, sw - w - 8))
        pop.geometry("%dx%d+%d+%d" % (w, h, x, y))
        # Windows 上新弹出的 Toplevel 会抢走键盘焦点——必须立刻把焦点还给
        # 输入框，否则回车/方向键事件进不了输入框的绑定
        # （Treeview 原生只响应方向键，这就是"回车选不中"的根源）
        try:
            self.input.focus_set()
        except Exception:            # noqa: BLE001
            pass
        # 焦点持续校正：与窗口管理器抢焦点的过程有竞态，弹窗存活期间
        # 每 80ms 把焦点拉回输入框一次（弹窗销毁后循环自然停止）
        def _reassert_focus():
            if pop.winfo_exists():
                try:
                    if root.focus_displayof() is not self.input:
                        self.input.focus_set()
                except Exception:    # noqa: BLE001
                    pass
                pop.after(80, _reassert_focus)
        _reassert_focus()
        # 双保险：即便焦点被抢到列表上，回车也直接确认
        lb.bind("<Return>", lambda _e: (on_pick(_tv_index(lb)), "break")[1])
        lb.bind("<KP_Enter>", lambda _e: (on_pick(_tv_index(lb)), "break")[1])
        return pop, lb

    def _at_hide(self):
        if getattr(self, "_at_pop", None) and self._at_pop.winfo_exists():
            try: self._at_pop.destroy()
            except Exception: pass
        self._at_pop = None
        self._at_lb = None

    def _at_candidates(self, frag: str) -> list:
        """工作区文件/目录候选：@ 后的片段做子串过滤（忽略大小写）。"""
        import os
        try:
            ws = tools.get_workspace() or os.getcwd()
        except Exception:            # noqa: BLE001
            ws = os.getcwd()
        skip = {".git", "__pycache__", "node_modules", ".venv", "venv",
                "dist", "build", ".idea", ".vscode", "__MACOSX"}
        frag_l = (frag or "").lower()
        out = []
        for root, dirs, files in os.walk(ws):
            rel_root = os.path.relpath(root, ws).replace("\\", "/")
            if rel_root == ".":
                rel_root = ""
            dirs[:] = sorted(d for d in dirs if d not in skip)
            for name in dirs:
                rel = f"{rel_root}/{name}" if rel_root else name
                if frag_l in rel.lower():
                    out.append(rel + "/")
            for name in sorted(files):
                rel = f"{rel_root}/{name}" if rel_root else name
                if frag_l in rel.lower():
                    out.append(rel)
            if len(out) >= 300:
                break
        return out[:80]

    def _at_icon(self, path: str):
        """@ 候选行的彩色图标：目录 📁，文件按扩展名映射。"""
        key = "1f4c1" if path.endswith("/") else _TREE_ICON_MAP.get(
            path.rsplit(".", 1)[-1].lower() if "." in path else "", "1f4c4")
        return _emoji_icon(key)

    def _at_show(self, cands):
        try:
            rows = [(p, self._at_icon(p)) for p in cands]
            pop, lb = self._show_token_popup(rows, lambda _i: self._at_insert())
            self._at_pop = pop
            self._at_lb = lb
        except Exception:            # noqa: BLE001
            pass

    def _at_insert(self):
        path = None
        try:
            sel = self._at_lb.selection()
            if sel:
                path = self._at_cands[_tv_index(self._at_lb)]
        except Exception as e:       # noqa: BLE001
            self._set_status(f"@ 确认异常(读取选中): {e}")
            return
        self._at_hide()
        if not path:
            self._set_status("@ 确认异常: 未取到选中项")
            return
        try:
            idx = self.input.index("insert")
            line_start = self.input.index(f"{idx} linestart")
            prefix = self.input.get(line_start, idx)
            import re
            m = re.search(r"@[^\s@]*$", prefix)
            if m:
                start = f"{line_start}+{m.start(0)}c"
                self.input.delete(start, idx)
                self.input.insert(start, "@" + path + " ")
                self._set_status(f"已插入 @{path}")
            else:
                self.input.insert("insert", "@" + path + " ")
                self._set_status(f"已插入 @{path}（光标处未找到 @token，已追加）")
        except Exception as e:       # noqa: BLE001
            self._set_status(f"@ 确认异常(插入): {e}")

    def _expand_at_refs(self, text: str) -> str:
        """发送前把 @相对路径 展开为绝对路径（仅存在的文件才替换），
        交给 attach.extract_file_refs 自动转附件；目录/未知引用原样保留。"""
        import os
        import re
        try:
            ws = tools.get_workspace() or os.getcwd()
        except Exception:            # noqa: BLE001
            ws = os.getcwd()

        def _sub(m):
            rel = m.group(1).rstrip("/")
            p = os.path.join(ws, rel)
            return p if os.path.isfile(p) else m.group(0)
        return re.sub(r"@([^\s@]+)", _sub, text)

    def _on_input_keypress(self, event):
        """统一 KeyPress 处理（弹窗确认/导航 + 无弹窗时回车发送）。

        全部在 KeyPress 阶段 return "break"：否则 Text 的默认类绑定会先把
        回车变成换行、把方向键变成移动光标。
        优先级：弹窗打开 → 回车/Tab 确认候选、↑↓ 选择、Esc 关闭；
        无弹窗 → 回车发送（Shift=换行走默认；Ctrl/Alt 组合放行专用绑定）。
        """
        cmd_open = getattr(self, "_cmd_pop", None) and self._cmd_pop.winfo_exists()
        at_open = getattr(self, "_at_pop", None) and self._at_pop.winfo_exists()
        k = event.keysym
        char = getattr(event, "char", "") or ""
        # 回车识别兼容 IME：部分输入法会把回车的 keysym 变成别的值（如 Left），
        is_enter = k in ("Return", "KP_Enter") or char in ("\r", "\n")
        is_tab = k == "Tab"
        shift_held = bool(event.state & 0x0001)
        ctrl_held = bool(event.state & 0x0004)

        if cmd_open or at_open:
            if is_enter or is_tab:
                if cmd_open:
                    self._cmd_insert()
                else:
                    self._at_insert()
                return "break"
            if k == "Escape":
                if cmd_open:
                    self._cmd_hide()
                else:
                    self._at_hide()
                return "break"
            if k in ("Up", "Down"):
                d = 1 if k == "Down" else -1
                if cmd_open:
                    self._cmd_idx = _tv_select(self._cmd_lb, self._cmd_idx + d)
                else:
                    self._at_idx = _tv_select(self._at_lb, self._at_idx + d)
                return "break"
            # 字符键/退格：放行默认行为，之后按新内容重过滤候选
            if (len(k) == 1 or k in ("BackSpace", "Delete")) and not is_enter:
                self.root.after(0, self._popup_rescan)
            return None

        # ---- 无弹窗：回车直接发送（Shift+回车=换行走默认）----
        if is_enter and not shift_held and not ctrl_held:
            self._on_return(event)
            return "break"
        return None

    def _input_on_keyrelease(self, event):
        """KeyRelease：弹窗未开时检测 / 或 @ token，打开候选弹窗。"""
        cmd_open = getattr(self, "_cmd_pop", None) and self._cmd_pop.winfo_exists()
        at_open = getattr(self, "_at_pop", None) and self._at_pop.winfo_exists()
        if cmd_open or at_open:
            return None          # 弹窗逻辑在 KeyPress 阶段处理
        k = event.keysym
        if k in ("Return", "KP_Enter", "Tab", "Escape", "Up", "Down", "Left", "Right"):
            return
        if k == "BackSpace":
            return
        self._popup_open_scan()

    def _popup_rescan(self):
        """按当前光标前的 token 重建候选弹窗（输入过滤用）。"""
        self._cmd_hide()
        self._at_hide()
        self._popup_open_scan()

    def _popup_open_scan(self):
        """检测光标前的 /命令 或 @文件 token，打开对应候选弹窗。"""
        import re
        idx = self.input.index("insert")
        line_start = self.input.index(f"{idx} linestart")
        prefix = self.input.get(line_start, idx)
        m_cmd = re.search(r"/[a-z]*$", prefix)
        m_at = re.search(r"@([^\s@]*)$", prefix)
        self._cmd_hide()
        if m_cmd:
            self._at_hide()
            word = m_cmd.group(0)
            # 前缀匹配 + 容错（多打的字母不算错：/brainstorme 也能命中 /brainstorm）
            cands = [c for c, _d, _key in self._COMMANDS
                     if c.startswith(word) or word.startswith(c)]
            if not cands:
                return
            self._cmd_cands = cands
            self._cmd_idx = 0
            try:
                def _pick_cmd(i):
                    self._cmd_idx = i
                    self._cmd_insert()
                rows = [(c, _emoji_icon("26a1")) for c in cands]
                pop, lb = self._show_token_popup(rows, _pick_cmd)
                self._cmd_pop = pop
                self._cmd_lb = lb
            except Exception as e:       # noqa: BLE001
                self._set_status(f"命令弹窗错误: {e}")
            return
        self._at_hide()
        if not m_at:
            return
        cands = self._at_candidates(m_at.group(1))
        if not cands:
            return
        self._at_cands = cands
        self._at_idx = 0
        try:
            rows = [(p, self._at_icon(p)) for p in cands]
            pop, lb = self._show_token_popup(rows, lambda _i: self._at_insert())
            self._at_pop = pop
            self._at_lb = lb
        except Exception as e:       # noqa: BLE001
            self._set_status(f"弹窗错误: {e}")

    def show_mode_help(self, arg):
        # 占位：permission 提示可选项
        self._set_status(_t("st.perm", m=arg or _t("mode.ask")))

    def _send_queued(self):
        """发送全部排队消息（逐条，串行）。"""
        if self._running or not self._msg_queue:
            return
        self._send_with(self._msg_queue.pop(0), [])

    def _refresh_all(self):
        """刷新右侧文件树 + 左侧会话列表 + 模型列表。"""
        try: self._refresh_file_panel()
        except Exception: pass
        try: self._refresh_sidebar()
        except Exception: pass
        try: self._refresh_models()
        except Exception: pass
        self._set_status(_t("top.ready"))

    def _on_send_or_stop(self):
        """发送按钮双态：空闲=发送；运行中=请求停止。"""
        if self._running:
            self.request_stop()
        else:
            self.send()

    def request_stop(self):
        """用户请求中止当前任务（下一检查点生效）；重复请求不重复提示。"""
        if self._stop_requested:
            return
        self._stop_requested = True
        self._set_status(_t("ui.stopping"))
        self._append("\n" + _t("ui.stop_req") + "\n", "meta")

    def _trigger_screenshot(self):
        """多屏/跨屏截图（微信式选区 + 标注），保存后作为图片附件加入聊天。"""
        try:
            import screenshot as _shot
        except Exception as e:            # noqa: BLE001
            self._set_status("截图模块不可用：" + str(e))
            return
        if not _shot.available():
            self._set_status("截图不可用：需 tkinter + Pillow")
            return
        self._set_status("📷 截图：拖选区域，回车保存 / ESC 取消")
        import threading as _th, sys as _sys
        def _work():
            if not _sys.platform.startswith("win32") and hasattr(_shot, "portal_capture"):
                # Linux(Wayland)：portal 真抓屏 → 标注窗确认（保持原路径）
                try:
                    raw = _shot.portal_capture()
                except Exception:        # noqa: BLE001
                    raw = None
                if raw:
                    self.root.after(0, lambda r=raw: self._open_annotate_modal(r, self._on_shot_done))
                else:
                    self.root.after(0, lambda: self._on_shot_done(None))
                return
            # Windows/macOS：微信式——覆盖层按显示器几何 1:1 盖住每一块屏幕，
            # 直接在屏上拖选区域并标注，回车保存为临时 PNG 后自动进附件栏；
            # 覆盖层在独立进程里跑（capture 子进程），不占本窗口主循环。
            try:
                path = _shot.capture()
            except Exception as e:        # noqa: BLE001
                self.root.after(0, lambda msg=str(e): self._set_status("截图失败：" + msg))
                return
            self.root.after(0, lambda p=path: self._on_shot_done(p))
        _th.Thread(target=_work, daemon=True).start()

    def _open_annotate_modal(self, image_path, on_done):
        """居中模态标注对话框（仅文字标注），确认进附件/取消。"""
        try:
            import ui_panel_annotate
            self._set_status("✏️ 点击图片输入文字标注；✔ 保存 / ✕ 取消")
            ui_panel_annotate.show(self, image_path, lambda p: on_done(p))
        except Exception as e:        # noqa: BLE001
            self._set_status("标注界面不可用：" + str(e))
            # 未标注原图直接进附件（兜底）
            self._on_shot_done(image_path)

    def _on_shot_done(self, path):
        if path and path not in self._pending_attachments:
            self._pending_attachments.append(path)
            self._render_attachments()
            self._set_status("✅ 截图已保存待发送")
        elif not path:
            try:
                import screenshot as _shot
                self._set_status(_shot.failure_notice())
            except Exception:            # noqa: BLE001
                self._set_status("截图未完成")

    def _on_escape(self, _event):
        """Esc：任务运行中请求停止；空闲时无操作。"""
        if self._running and not self._stop_requested:
            self.request_stop()
            return "break"
        return None

    def _check_stop(self) -> bool:
        """Agent 每步检查：请求过停止则中止循环。"""
        return self._stop_requested

    def _setup_chat_copy(self):
        """主聊天区可复制（委托给通用 _enable_text_copy）。

        block_tags 传消息块标签：右键「复制本条消息」按 user/assistant
        消息块整体复制（历史会话回放同样生效）。
        """
        _enable_text_copy(
            self.chat,
            block_tags=("user", "assistant", "tool", "toolresult",
                        "toolhead", "toolitem", "toolnote",
                        "meta", "denied"))

    def _on_return(self, event):
        # 回车提交：始终 return "break" 吞掉回车（避免空内容回车插入空行）。
        # 容错：即使 _placeholder_active 状态被卡住（IME 组合、_on_input_key
        # 未触发等），只要内容是真实文本就清掉占位符标记并发送，绝不误删。
        raw = self.input.get("1.0", "end")
        st = raw.strip()
        is_placeholder = self._placeholder_active or st == self.PLACEHOLDER.strip()
        if not st or is_placeholder:
            return "break"               # 仍占位/纯空白：忽略回车
        if self._placeholder_active:
            self._placeholder_active = False
            self.input.config(fg="black")
        self.send()
        return "break"

    def send(self):
        if self._placeholder_active and not self._pending_attachments:
            # 占位符仍活跃且无附件：清掉占位符当无事发生（避免把占位符当正文发送）
            self.input.delete("1.0", "end")
            self.input.config(fg="black")
            self._placeholder_active = False
        if str(self.send_btn.cget("state")) == "disabled":
            return                      # 任务进行中，防重复发送
        if self._placeholder_active:
            # 未输入文字、只发附件：清掉占位符
            self.input.delete("1.0", "end")
            self._placeholder_active = False
        text = self.input.get("1.0", "end").strip()
        if text.startswith("/") and self._run_command(text):
            self.input.delete("1.0", "end")   # 本地执行命令，清空输入
            self._pending_attachments = []
            self._render_attachments()
            return
        attachments = list(self._pending_attachments)
        # @引用展开：@相对路径（选择器插入的）→ 绝对路径，存在才替换
        try:
            text = self._expand_at_refs(text)
        except Exception:            # noqa: BLE001
            pass
        # 本地文件引用自动转附件（file:// URI / 裸盘符路径；图片识图 / 音视频分析）
        file_paths, text = attach.extract_file_refs(text)
        attachments.extend(p for p in file_paths if p not in attachments)
        if not text and not attachments:
            return
        # http(s) 链接自动取材：图片→下载识图；网页→抓正文。
        # 在后台线程抓取（不冻结界面），完成后回到主线程继续发送。
        if weblinks and weblinks.find_urls(text):
            self.send_btn.config(state="disabled")
            self._set_status(_t("ui.fetching"))

            def _fetch_links():
                aug, imgs = weblinks.process(text, log=self._set_status)

                def _resume():
                    self.send_btn.config(state="normal")
                    attachments.extend(p for p in imgs if p not in attachments)
                    self._set_status("")
                    self._send_with(aug, attachments)
                self.root.after(0, _resume)

            threading.Thread(target=_fetch_links, daemon=True).start()
            return
        self._send_with(text, attachments)

    def _route_mode_text(self) -> str:
        return {"auto": _t("route.auto"),
                "cloud": _t("route.cloud")}.get(self._route_override,
                                                _t("route.auto"))

    def _cycle_route_override(self):
        """自动→云端→自动 循环切换，并刷新按钮/状态。"""
        self._route_override = {"auto": "cloud",
                                "cloud": "auto"}.get(self._route_override, "auto")
        # 图标化：按钮固定 🔀，当前模式悬停状态栏可见
        if hasattr(self, "_route_btn") and self._route_btn:
            self._route_btn.config(text="🔀")
        if hasattr(self, "bottom_route_btn") and self.bottom_route_btn:
            self.bottom_route_btn.config(text="🔀")
        self._set_status(_t("route.status", mode=txt))

    def _route_complex(self, text: str) -> str | None:
        """应用层判定任务是否复杂/超本地能力 → 返回应委派的云端模型 key，否则 None。

        不依赖本地模型自觉；命中复杂关键词（分析整库/架构/重构/大改动等）则把本轮
        自动路由到云端 pro（付费才用，本地能搞定不切）。
        """
        if not (config.get_model_dispatch() and config.get_dispatch_smart()):
            return None
        import re
        t = text.strip()
        heavy = re.search(
            r"(分析整个项目|分析整个代码|整个项目|整(库|份)|全部代码|整个代码|"
            r"全面(分析|审查|优化)|架构(评审|分析|设计|重架构)|重构|大规模重构|"
            r"优化.*(全部|整个|所有)|复杂(架构|系统|问题)|整体方案|系统设计|"
            r"深入分析|大改动|review\b|architecture|refactor\b|multi-?file)", t, re.I)
        if not heavy:
            return None
        return config.get_dispatch_pro() or None

    def _send_with(self, text: str, attachments: list):
        """实际发送（send() 完成链接取材等预处理后调用）。"""
        # 识图预路由（智排）：当前模型不支持识图时，自动切到识图模型，而不是拦下发不了。
        # 本地优先：本地大脑（dispatch_model）带识图且在跑 → 用本地；否则回退云端识图。
        # 本轮开始：清空任务步骤(todo)。面板只在模型下发 task_plan 计划后出现；
        # 无计划的简单任务不再显示无意义的占位行
        self._has_plan = False              # 新一轮：等待模型的 task_plan 计划
        self._todo_tool_current = None
        self.todo_items = []
        self._render_todo()
        run_model = self.current_model
        if attachments and self.current_model and not self.current_model.vision:
            has_image = any(isinstance(p, str) and media.classify(p) == "image"
                            for p in attachments)
            if has_image:
                vision_mc = None
                if config.get_model_dispatch() and config.get_dispatch_smart():
                    vk = tools.resolve_dispatch_vision_key()
                    vision_mc = config.find_model(vk) if vk else None
                if vision_mc is not None:
                    if not getattr(self, "_dispatch_notes", None):
                        self._dispatch_notes = []
                    turn_no = sum(1 for m in (self.messages or [])
                                  if m.get("role") == "user") + 1
                    self._dispatch_notes.append({
                        "kind": "model_switch", "turn": turn_no,
                        "on": self.current_model.display_name,
                        "to": vision_mc.display_name,
                        "to_key": vision_mc.key,
                    })
                    self._append(
                        _t("ui.dispatch_vision_switch",
                           on=self.current_model.display_name,
                           to=vision_mc.display_name) + "\n", "dispatch")
                    self._set_status(_t("ui.dispatch_vision_status",
                                        model=vision_mc.display_name))
                    run_model = vision_mc
                else:
                    vision_names = "、".join(m.display_name for m in self.models
                                             if m.vision) or _t("ui.vision_hint")
                    self._append(
                        _t("ui.no_vision",
                           model=self.current_model.display_name,
                           names=vision_names), "denied")
                    return
        self.input.delete("1.0", "end")
        self.input.config(fg="black")
        label = text or _t("ui.send_attach")
        # 轮次号：本条是第几条用户消息（回放时按轮次内插批注用）
        turn_no = sum(1 for m in (self.messages or [])
                      if m.get("role") == "user") + 1
        # 路由覆盖（侧栏按钮）：cloud=强制云端本轮；auto=自动路由
        ov = getattr(self, "_route_override", "auto")
        routed_key = None
        if run_model is self.current_model:
            if ov == "cloud":
                routed_key = (config.get_dispatch_pro()
                              if config.get_model_dispatch() else None)
            else:
                routed_key = self._route_complex(text)
            if routed_key:
                mc = config.find_model(routed_key)
                if mc is not None:
                    if not getattr(self, "_dispatch_notes", None):
                        self._dispatch_notes = []
                    self._dispatch_notes.append({
                        "kind": "model_switch", "turn": turn_no,
                        "on": self.current_model.display_name,
                        "to": mc.display_name, "to_key": mc.key})
                    self._append(
                        _t("ui.dispatch_complex_switch",
                           on=self.current_model.display_name,
                           to=mc.display_name) + "\n", "dispatch")
                    self._set_status(_t("ui.dispatch_complex_status",
                                        model=mc.display_name))
                    run_model = mc
        dispatch_on = config.get_model_dispatch()
        if dispatch_on:
            if not getattr(self, "_dispatch_notes", None):
                self._dispatch_notes = []
            self._dispatch_notes.append({
                "kind": "turn_model", "turn": turn_no,
                "model": run_model.display_name, "key": run_model.key})
        self._append_segments([
            {"text": "▍ ", "tag": "userbar"},
            {"text": _t("ui.you", model=run_model.display_name,
                        label=label) + "\n", "tag": "user"}])
        # 用户消息后内嵌显示附件（图片/音频/视频控件；代码片段则内联展示）
        for p in attachments:
            if isinstance(p, dict):
                self._append(attach.format_snippet(p) + "\n", "user")
            else:
                self._append_media(p)
        if attachments:
            self._pending_attachments = []
            self._render_attachments()

        # 会话：首轮创建 id + 标题 + 绑定目录，立即落盘（不等 LLM 完成，
        # 崩溃/断网也不丢对话）；历史延续（上下文压缩在 Agent 内做）
        import sessions as sess_mod
        if self.session_id is None:
            self.session_id = sess_mod.new_id()
            self.session_title = sess_mod.make_title(text)
            self.sess_btn.config(text="💬 " + self.session_title[:16])
        session_ws = tools.get_workspace()
        # 独立提问模式：每条消息不带历史单独发送（省 token，问题互不干扰）；
        # 回复仍合并进 self.messages，会话记录完整保留。
        standalone = config.get_standalone()
        history = None if standalone else (self.messages if self.messages else None)

        def _persist():
            """把当前消息列表保存到会话（绑定目录）。"""
            msgs = (self.messages or []) + [{"role": "user", "content": text}] \
                if self.messages is None or not any(
                    m.get("role") == "user" and m.get("content") == text
                    for m in self.messages[-3:]) else self.messages
            sess_mod.save(self.session_id, msgs, self.session_title,
                          workspace=session_ws,
                          notes=getattr(self, "_dispatch_notes", None))

        if history is None:          # 首轮：先落盘用户提问
            _persist()

        self._set_status(_t("ui.thinking"))
        self._stop_requested = False
        self._running = True
        self.send_btn.config(text=_t("btn.stop"), fg="#dc2626")
        self._spinner_start(_t("status.thinking"))
        self.badge_busy(_t("ui.running"))

        def worker():
            a = agent_mod.Agent(on_event=self._on_event,
                                on_approval=self._approve,
                                on_stop=self._check_stop,
                                mode=self.mode,
                                model=run_model)
            try:
                final = a.run(text, history=history, attachments=attachments)
            except Exception as e:  # noqa: BLE001
                self._append(_t("ui.error", e=e)+"\n", "denied")
                self._task_failed = True
                final = None
            finally:
                # 无论成功/失败，都把当前消息（含 AI 处理与回复/部分回复）落盘，
                # 避免会话里只留用户提问、丢失 AI 的回应。
                try:
                    msgs = getattr(a, "messages", None)
                    # 兜底：若消息末尾不是 assistant 且确有文本回复，补一条再存
                    if final and msgs:
                        last = msgs[-1] if msgs else None
                        if last is None or last.get("role") != "assistant":
                            msgs = list(msgs) + [{"role": "assistant", "content": final}]
                    if standalone:
                        if self.messages is None:
                            self.messages = []
                        self.messages.extend(msgs[1:] if msgs else [])
                    elif msgs:
                        self.messages = msgs
                    elif self.messages is None:
                        self.messages = []
                    sess_mod.save(self.session_id, self.messages or [],
                                  self.session_title, workspace=session_ws,
                                  notes=getattr(self, "_dispatch_notes", None))
                except Exception:            # noqa: BLE001  落盘失败不阻断界面
                    pass
                # Markdown 重排本回复块（须在末尾空行/模型标注之前——
                # 重排会 delete(块起点, end)，放后面会把它们一并删掉）
                self.root.after(0, self._md_render)
                self._append("\n", "assistant")
                # 回复末尾标注本条实际由哪个模型处理（派发开启时；
                # 用 Agent 最终实际使用的模型——本地回退云端时显示云端）
                if dispatch_on:
                    _actual = getattr(a, "model", None) or run_model
                    self._append(
                        _t("reply.model", model=_actual.display_name) + "\n",
                        "meta")
                self._spinner_stop()   # 完成：移除转动的等待指示
                self.badge_done(ok=not getattr(self, "_task_failed", False))
                self._task_failed = False
                self._set_status(_t("top.ready"))
                self._running = False
                self._stop_requested = False
                self.root.after(0, lambda: self.send_btn.config(
                    text=_t("btn.send"), fg="black", state="normal"))
                self.root.after(0, self._refresh_sidebar)   # 刷新左侧会话列表
                self.root.after(0, self._clear_todo)     # 整轮结束：todo 清单消失

        self._worker_th = threading.Thread(target=worker, daemon=True)
        self._worker_th.start()

    # ================= 帮助 =================
    # 帮助正文统一取自 i18n 的 help.text（中英跟随界面语言）。

    def _show_help(self):
        """帮助窗口（实现在 ui_panel_help.py）。"""
        import ui_panel_help
        ui_panel_help.show(self)

    def _help_drag(self, win, e):
        """帮助窗口拖动（实现在 ui_panel_help.py）。"""
        import ui_panel_help
        ui_panel_help._drag(self, win, e)

    # ================= 附件与媒体展示 =================
    def _pick_attachments(self):
        """选择附件文件（可多选），加入待发送列表。"""
        paths = filedialog.askopenfilenames(parent=self.root, title=_t("pick.attach"))
        added = [p for p in paths if p not in self._pending_attachments]
        self._pending_attachments.extend(added)
        if added:
            self._render_attachments()
            kinds = "、".join(media.classify(p) or _t("msg.file") for p in added)
            self._set_status(_t("msg.attached", n=len(added), kinds=kinds))

    def _remove_attachment(self, idx):
        try:
            self._pending_attachments.pop(idx)
        except IndexError:
            pass
        self._render_attachments()

    def _render_attachments(self):
        """刷新输入框上方的附件预览条。"""
        for w in self.attach_bar.winfo_children():
            w.destroy()
        if not self._pending_attachments:
            self.attach_bar.pack_forget()
            return
        # 显示在输入区（bottom=self.input.master）上方
        self.attach_bar.pack(fill="x", padx=16, pady=(0, 4),
                             before=self.input.master)
        for i, p in enumerate(self._pending_attachments):
            if isinstance(p, dict) and p.get("kind") == "snippet":
                text = attach.snippet_chip(p)   # 已含 📄 + 文件名 + 行号
            else:
                icon = {"image": "🖼", "audio": "🎵", "video": "🎬"}.get(
                    media.classify(p), "📄")
                text = (f"{icon} {os.path.basename(p)[:26]}（"
                        f"{media.file_size_str(os.path.getsize(p))}）")
            chip = tk.Frame(self.attach_bar)
            chip.pack(side="left", padx=(0, 8))
            tk.Label(chip, text=text, font=(FONT_UI, 9),
                     fg="#334155").pack(side="left")
            x = tk.Label(chip, text="✕", font=(FONT_UI, 9), fg="#dc2626",
                         cursor="hand2")
            x.pack(side="left", padx=(3, 0))
            x.bind("<Button-1>", lambda e, idx=i: self._remove_attachment(idx))

    def _append_media(self, path):
        """在聊天区内嵌显示媒体：图片/GIF 动图/音频播放/视频缩略图。

        Text 控件里嵌窗口需临时开启 normal 状态；经 root.after
        在主线程执行；控件引用存 _media_refs 防 Tkinter GC 回收。
        """
        if not isinstance(path, str):
            return                     # 代码片段等非文件附件不嵌媒体
        def _w():
            self.chat.config(state="normal")
            try:
                rng = (self._spinner_range()
                       if self._spinner_after is not None else None)
                pos = rng[0] if rng else "end"
                kind = media.classify(path)
                if kind == "image":
                    self._embed_image(path, pos)
                elif kind in ("audio", "video"):
                    self._embed_av(path, pos, kind)
                else:
                    self.chat.insert(pos, _t("tag.file", path=path) + "\n", "meta")
                self.chat.insert(pos, "\n", "meta")
            except Exception as e:  # noqa: BLE001
                self.chat.insert("end", _t("ui.media_fail", p=path, e=e) + "\n", "meta")
            finally:
                self.chat.see("end")
                self.chat.config(state="disabled")
        self.root.after(0, _w)

    def _embed_image(self, path, pos):
        """内嵌图片；GIF 动图自动循环播放，双击用外部程序打开。"""
        info = media.load_image(path, max_pix=480)
        # 淡灰细边（highlightbackground 可指定颜色，bd 只能是系统色）
        label = tk.Label(self.chat, bd=0, bg="#f1f5f9", padx=6, pady=6,
                         highlightthickness=1, highlightbackground="#cbd5e1",
                         cursor="hand2")
        self.chat.window_create(pos, window=label)
        label.image_ref = info["photo"]              # 防 GC
        if info["frames"]:
            anim = media.GifAnimator(label, info["frames"], info["delays"])
            self._media_refs.append((label, info, anim))
        else:
            label.configure(image=info["photo"])
            self._media_refs.append((label, info))
        label.bind("<Double-Button-1>",
                   lambda e: media.external_open(path))

    def _embed_av(self, path, pos, kind):
        """内嵌音频播放条 / 视频（缩略图+外部播放）。"""
        bar = tk.Frame(self.chat, bg="#f1f5f9", padx=8, pady=6)
        self.chat.window_create(pos, window=bar)
        if kind == "video":
            try:
                thumb = media.video_thumbnail(path)
                if thumb:
                    lab = tk.Label(bar, bd=0, bg="#f1f5f9",
                                   highlightthickness=1,
                                   highlightbackground="#cbd5e1")
                    info = media.load_image(thumb, max_pix=480)
                    lab.configure(image=info["photo"])
                    lab.image_ref = info["photo"]
                    lab.pack(side="top")
                    lab.bind("<Double-Button-1>",
                             lambda e: media.external_open(path))
                    self._media_refs.append((lab, info))
            except Exception:  # noqa: BLE001  无 ffmpeg 等情况
                pass
        name = os.path.basename(path)
        size = (media.file_size_str(os.path.getsize(path))
                if os.path.exists(path) else "?")
        icon = "🎵" if kind == "audio" else "🎬"
        box = {}                                      # 播放器引用容器

        if kind == "audio":
            def _toggle():
                p = box.get("player")
                if p and p.playing:
                    p.stop()
                    btn.config(text=_t("btn.play"))
                    return
                p = media.AudioPlayer(path)
                p.play()
                box["player"] = p
                self._media_refs.append((bar, p))
                btn.config(text=_t("btn.stop2"))
            btn = tk.Button(bar, text=_t("btn.play"), font=(FONT_UI, 9),
                            relief="flat", cursor="hand2", command=_toggle)
            btn.pack(side="left")
        else:
            btn = tk.Button(bar, text=_t("btn.ext_play"), font=(FONT_UI, 9),
                            relief="flat", cursor="hand2",
                            command=lambda: media.external_open(path))
            btn.pack(side="left")
        tk.Label(bar, text=f"{icon} {name[:28]}（{size}）",
                 font=(FONT_UI, 9), fg="#334155",
                 bg="#f1f5f9").pack(side="left", padx=(6, 0))
        dur = media.probe_duration(path)
        if dur:
            tk.Label(bar, text=f"⏱ {dur}", font=(FONT_UI, 9),
                     fg="#64748b", bg="#f1f5f9").pack(side="left", padx=(6, 0))
        tk.Button(bar, text=_t("btn.ext_open"), font=(FONT_UI, 9), relief="flat",
                  cursor="hand2",
                  command=lambda: media.external_open(path)
                  ).pack(side="left", padx=(6, 0))
        self._media_refs.append(bar)

    # ================= MCP 服务器管理 =================
    def _start_mcp(self):
        """后台连接 mcp.json 里启用的 MCP 服务器（不阻塞界面）。"""
        def worker():
            mgr = mcp.get_manager()
            if mgr.connected:
                return
            try:
                if mgr.connect(on_log=lambda m: self._set_status(m)):
                    n = len(mgr.tool_map)
                    self._set_status(_t("mcp.ready", n=n))
            except Exception as e:  # noqa: BLE001
                self._set_status(_t("mcp.conn_fail", e=e))
        threading.Thread(target=worker, daemon=True).start()

    def _manage_mcp(self):
        """MCP 服务器管理窗口（实现在 ui_panel_mcp.py）。"""
        import ui_panel_mcp
        ui_panel_mcp.show(self)

    def _on_close(self):
        """关窗清理：任务进行中先请求停止、等工作线程落盘半程结果，
        再停掉 MCP 子进程。模态本地面板未关时锁定主窗口。"""
        # 模态面板（本地模型管理）还开着 → 不关闭主窗口，聚焦面板
        if getattr(self, "_modal_open", False):
            panel = getattr(self, "_gp_panel", None)
            win = getattr(panel, "win", None) if panel else None
            if win is not None and win.winfo_exists():
                try:
                    win.lift()
                    win.focus_force()
                except Exception:            # noqa: BLE001
                    pass
            return
        # 有任务在跑：协作式停止（agent 会在流中/轮间检测），等工作线程
        # 执行 finally 落盘，避免关窗把聊到一半的回复/会话存成半截
        if getattr(self, "_running", False):
            self._stop_requested = True
            th = getattr(self, "_worker_th", None)
            if th is not None and th.is_alive():
                th.join(timeout=8)
        try:
            mcp.get_manager().stop_all()
        except Exception:  # noqa: BLE001
            pass
        self.root.destroy()

    # ================= 会话管理 =================
    def _show_session_menu(self, anchor=None):
        """会话菜单：新会话 / 当前目录会话 / 全局搜索 / 全部会话 / 删除。锚定在 anchor（默认顶部会话按钮）。"""
        import sessions as sess_mod
        menu = tk.Menu(self.root, tearoff=0, font=(FONT_UI, 10))
        menu.add_command(label=_t("top.new_session"), command=self._new_session)
        menu.add_separator()
        ws = tools.get_workspace()
        items = sess_mod.list_sessions(limit=10, workspace=ws)
        menu.add_command(label=_t("sess.ws_header", ws=ws),
                         state="disabled")
        if not items:
            menu.add_command(label=_t("sess.none"), state="disabled")
        else:
            import time as _time
            for it in items:
                cur = " ✓" if it["id"] == self.session_id else ""
                when = _time.strftime("%m-%d %H:%M", _time.localtime(it["updated"]))
                menu.add_command(
                    label=f"{it['title'][:20]}  ({when}){cur}",
                    command=lambda sid=it["id"]: self._load_session(sid))
        menu.add_separator()
        menu.add_command(label=_t("sess.search"), command=self._search_sessions)
        menu.add_command(label=_t("sess.all"),
                         command=self._list_all_sessions)
        menu.add_separator()
        if self.session_id:
            menu.add_command(label=_t("sess.del_cur"),
                             command=self._delete_current_session)
        target = anchor or self.sess_btn
        x = target.winfo_rootx()
        y = target.winfo_rooty() + target.winfo_height()
        menu.tk_popup(x, y)

    def _search_sessions(self):
        """全局会话搜索（实现在 ui_panel_sessions.py）。"""
        import ui_panel_sessions
        ui_panel_sessions.show_search(self)

    def _list_all_sessions(self):
        """列出全部会话（实现在 ui_panel_sessions.py）。"""
        import ui_panel_sessions
        ui_panel_sessions.show_all(self)

    def _new_session(self, persist: bool = True):
        """开始新会话：persist=True 时立即在当前工作区落盘（出现在侧栏）；
        删除工作区后的重建请传 persist=False——否则新会话马上把刚删除的
        工作区分组又顶回来，看起来像"删不掉"。"""
        import sessions as sess_mod
        self.session_id = sess_mod.new_id()
        self.session_title = _t("sess.new")
        self.messages = []
        if persist:
            try:
                sess_mod.save(self.session_id, [], self.session_title,
                              workspace=tools.get_workspace())
            except Exception:            # noqa: BLE001
                pass
        self.clear()
        self.sess_btn.config(text=_t("top.sessions"))
        self._set_status(_t("sess.started"))
        self._refresh_sidebar()

    def _show_welcome(self):
        """聊天区顶部欢迎/使用说明卡片已移除：使用方式改在输入框占位提示里展示。"""

    def _load_session(self, sid: str):
        """切换到历史会话：载入消息并回放到聊天区。"""
        import sessions as sess_mod
        data = sess_mod.load(sid)
        if data is None:
            self._set_status(_t("sess.load_fail"))
            return
        self.session_id = sid
        self.session_title = data.get("title") or _t("misc.no_title")
        self.messages = data["messages"]
        # 切回会话创建时的工作目录（跨项目载入保持工具操作一致）
        ws = data.get("workspace", "")
        if ws and os.path.isdir(ws) and ws != tools.get_workspace():
            tools.set_workspace(ws)
            config.save_last_workspace(ws)     # 会话载入切目录也记住
            self._close_all_file_views()       # 切目录：关掉旧目录的代码标签
            self._update_workspace_label()
            self._set_status(_t("sess.dir_switch", ws=ws))
        elif not ws:
            # 旧版会话无目录信息：绑定当前目录并回写（升级迁移）
            sess_mod.save(sid, data["messages"], self.session_title,
                          workspace=tools.get_workspace())
        self.clear()
        self.sess_btn.config(text="💬 " + self.session_title[:16])
        # 回放历史：user / assistant 正文显示，工具过程折叠为一行
        def _content_text(c):
            """content 可能是字符串或多模态列表 → 提取文本部分。"""
            if isinstance(c, str):
                return c
            return "\n".join(p.get("text", "") for p in c
                              if isinstance(p, dict) and p.get("type") == "text")
        # 批注按轮次内插：turn=N 的批注渲染在第 N 条用户消息前（与实时顺序一致）
        notes = data.get("notes") or []
        by_turn = {}
        for n in notes:
            by_turn.setdefault(n.get("turn"), []).append(n)
        legacy_notes = by_turn.pop(None, [])       # 无轮次号的旧批注 → 末尾补显

        def _render_note(n):
            if n.get("kind") == "model_switch":
                self._append(
                    _t("ui.dispatch_vision_switch",
                       on=n.get("on", ""), to=n.get("to", "")) + "\n", "dispatch")
            elif n.get("kind") == "turn_model":
                self._append(
                    _t("reply.model", model=n.get("model", "?")) + "\n", "meta")

        user_no = 0
        for m in self.messages:
            role, content = m.get("role"), m.get("content") or ""
            if role == "user":
                user_no += 1
                for n in by_turn.pop(user_no, []):
                    _render_note(n)
                self._append_segments([
                    {"text": "▍ ", "tag": "userbar"},
                    {"text": _t("sess.you", t=_content_text(content)) + "\n",
                     "tag": "user"}])
                # 附件图片只显示占位说明（回放完整图片太重）
                if isinstance(content, list):
                    n_img = sum(1 for p in content
                                if isinstance(p, dict)
                                and p.get("type") == "image_url")
                    if n_img:
                        self._append(_t("sess.n_imgs", n=n_img) + "\n", "meta")
            elif role == "assistant":
                tcs = m.get("tool_calls") or []
                names = [tc["function"]["name"] for tc in tcs]
                if content:
                    self._append(f"{content}\n", "assistant")
                if names:
                    # 模型派发：回放时把"派发给哪个模型"显示出来，其余工具照旧列一行
                    dispatched = []
                    for tc in tcs:
                        if tc["function"]["name"] == "call_model":
                            try:
                                a = json.loads(
                                    tc["function"].get("arguments") or "{}")
                            except Exception:            # noqa: BLE001
                                a = {}
                            key = a.get("model", "")
                            dispatched.append(
                                f"{config.dispatch_target_label(key)}（{key}）")
                    if dispatched:
                        self._append(
                            f"🔁 派发给 {'；'.join(dispatched)}\n", "dispatch")
                    rest = [n for n in names if n != "call_model"]
                    if rest:
                        self._append(f"🔧 {'/'.join(rest)}\n", "tool")
        # 剩余批注（无对应轮次的旧格式）末尾补显
        for n in legacy_notes + [x for ts in by_turn.values() for x in ts]:
            _render_note(n)
        # 历史会话开了派发 → 载入时自动打开派发；
        # 但本地大脑服务没在运行 → 不开，回退非派发（直接用默认模型）
        had_dispatch = any(n.get("kind") == "turn_model" for n in notes)
        if had_dispatch and not config.get_model_dispatch():
            if self._dispatch_brain_healthy():
                config.set_model_dispatch(True)
                self._update_dispatch_btn()
                name = config.get_dispatch_model().split("/")[-1]
                self._set_status(_t("sess.dispatch_restored", name=name))
            else:
                self._set_status(_t("sess.dispatch_fallback"))
        self._set_status(_t("sess.loaded", t=self.session_title))

    def _delete_current_session(self):
        """删除当前会话并开新会话。"""
        import sessions as sess_mod
        from tkinter import messagebox
        if self.session_id and messagebox.askyesno(
                _t("sess.del_title"), _t("sess.del_confirm", t=self.session_title)):
            sess_mod.delete(self.session_id)
            self._set_status(_t("sess.deleted"))
            self._new_session()

    # ================= 语音（单按钮：长按=按住说话，轻点=自动停顿检测） =================
    def _voice_press(self, _event):
        # 自动模式进行中再次按下 → 立即结束并识别
        if getattr(self, "_voice_auto", False):
            rec = getattr(self, "_voice_rec", None)
            if rec:
                self._voice_rec = None
                self._voice_auto = False
                self.voice_btn.config(text=_t("btn.voice"))
                self._transcribe_async(rec.stop_and_save(), had_speech=True)
            return
        if getattr(self, "_voice_rec", None):
            return
        try:
            import voice  # noqa: PLC0415  语音依赖（numpy 等）可选，缺失时优雅降级
            self._voice_rec, _ = voice.start_recording()
            self._voice_press_t = time.time()
            self.voice_btn.config(text=_t("v.recording"))
            self._set_status(_t("v.press_hint"))
        except Exception as e:  # noqa: BLE001
            self._set_status(_t("v.start_fail", e=e))

    def _voice_release(self, _event):
        rec = getattr(self, "_voice_rec", None)
        if rec is None or getattr(self, "_voice_auto", False):
            return
        held = time.time() - getattr(self, "_voice_press_t", 0)
        self._voice_rec = None
        if held >= 0.35:      # 长按：松手即停（按住说话）
            self.voice_btn.config(text=_t("btn.voice"))
            self._transcribe_async(rec.stop_and_save(), had_speech=True)
            return
        # 轻点：切换自动停顿检测，后台等静音达标 / 到时长上限结束
        self._voice_auto = True
        rec.enable_vad()
        self._set_status(_t("v.vad_hint"))

        def worker():
            wav_path, has_speech = rec.wait_vad_stop(silence_sec=1.5, max_sec=30)

            def _done():
                if getattr(self, "_voice_rec", None) is rec:
                    self._voice_rec = None
                if getattr(self, "_voice_auto", False):
                    self._voice_auto = False
                    self.voice_btn.config(text=_t("btn.voice"))
            self.root.after(0, _done)
            self._transcribe_async(wav_path, had_speech=has_speech)

        threading.Thread(target=worker, daemon=True).start()

    def _transcribe_async(self, wav_path, had_speech=True):
        """后台识别 wav，把结果追加到底部输入框（长按 / 自动两个入口共用）。"""
        if not had_speech:
            # 自动模式全程静音：不浪费一次识别
            if wav_path:
                try:
                    import os
                    os.remove(wav_path)
                except OSError:
                    pass
            self._set_status(_t("v.no_speech"))
            return
        if not wav_path:
            self._set_status(_t("v.no_sound"))
            return

        def worker():
            try:
                import voice
                self._set_status(_t("v.transcribing"))
                text = voice.transcribe(wav_path)
                if text:
                    self.root.after(0, lambda: self._insert_voice_text(text))
                    self._set_status(_t("v.got", t=text[:30]))
                else:
                    self._set_status(_t("v.no_speech"))
            except Exception as e:  # noqa: BLE001
                self._append(_t("v.err", e=e) + "\n", "denied")
                self._set_status(_t("v.fail"))
            finally:
                import os
                if wav_path:
                    try:
                        os.remove(wav_path)
                    except OSError:
                        pass

        threading.Thread(target=worker, daemon=True).start()

    def _insert_voice_text(self, text):
        """语音识别结果追加到底部输入框（保留已有内容；先清掉占位符）。"""
        if self._placeholder_active:
            self.input.delete("1.0", "end")
            self.input.config(fg="black")
            self._placeholder_active = False
        else:
            cur = self.input.get("1.0", "end-1c")
            # 已有内容与新增文本都是西文词时补一个空格，避免粘连
            if (cur and cur[-1].isascii() and cur[-1].isalnum()
                    and text[:1].isascii() and text[:1].isalnum()):
                text = " " + text
        self.input.insert("end-1c", text)

    # ================= Agent 事件 =================
    # ---- Markdown 渲染（流式显示原始文本，回复结束后重排）----
    def _md_reset_block(self):
        self._md_block = None
        self._md_buf = []

    def _assistant_append(self, delta):
        def _w():
            self.chat.config(state="normal")
            rng = self._spinner_range() if self._spinner_after is not None else None
            # 插入点必须固化成具体 "行.列"：spinner 已停时绝不能存漂移的 "end"，
            # 否则 _md_render 的 delete(start,"end") 变空操作，
            # 原文保留 + 重排版再插一遍 = 界面上同一回复出现两份
            pos = rng[0] if rng else self.chat.index("end-1c")
            if self._md_block is None:
                self._md_block = pos
                self._md_buf = []
            self._md_buf.append(delta)
            self.chat.insert(pos, delta, "assistant")
            self._update_todo()
            self.chat.see("end")
            self.chat.config(state="disabled")
        self.root.after(0, _w)

    def _md_render(self):
        def _w():
            if self._md_block is None:
                return
            start = self._md_block
            raw = "".join(self._md_buf)
            self.chat.config(state="normal")
            try:
                self.chat.delete(start, "end")
            except Exception:            # noqa: BLE001
                self._md_block = None
                self.chat.config(state="disabled")
                return
            for seg in self._md_format(raw):
                txt = seg.get("text", "")
                tag = seg.get("tag")
                url = seg.get("url")
                if tag == "mdlink":
                    self._link_seq += 1
                    ltag = f"link{self._link_seq}"
                    self.chat.tag_config(ltag, foreground="#2563eb", underline=True)
                    if url:
                        self.chat.tag_bind(ltag, "<Button-1>",
                                           lambda e, u=url: _open_url(u))
                    self.chat.insert("end", txt, ltag)
                elif tag and tag.startswith("mdcodeblock"):
                    self._insert_highlighted_code(txt, seg.get("lang") or "python",
                                                  dark=True, base_tag="mdcodeblock",
                                                  code_font="mdcodeblock")
                elif tag:
                    self.chat.insert("end", txt, tag)
                else:
                    self.chat.insert("end", txt)
            self.chat.see("end")
            self.chat.config(state="disabled")
            self._md_block = None
        self.root.after(0, _w)

    def _md_format(self, text):
        import re
        segs = []
        lines = text.split("\n")
        in_code = False
        code = []
        code_lang = ""
        br = {"text": "\n", "tag": "assistant"}
        for line in lines:
            s = line.strip()
            if s.startswith("```"):
                if in_code:
                    segs.append({"text": "\n".join(code) + "\n", "tag": "mdcodeblock",
                                 "lang": code_lang})
                    code = []
                    in_code = False
                else:
                    in_code = True
                    code_lang = s[3:].strip().split()[0] if len(s) > 3 else ""
                continue
            if in_code:
                code.append(line)
                continue
            m = re.match(r"^(#{1,3})\s+(.*)$", s)
            if m:
                segs.append({"text": m.group(2), "tag": "mdh%d" % len(m.group(1))})
                segs.append(br); continue
            if re.match(r"^([-*])\s+", s):
                segs.append({"text": "• " + s[2:], "tag": "mdlist"}); segs.append(br); continue
            if s.startswith(">"):
                segs.append({"text": s.lstrip("> "), "tag": "mdquote"}); segs.append(br); continue
            if re.match(r"^\d+[.)]\s+", s):
                segs.append({"text": s, "tag": "mdlist"}); segs.append(br); continue
            segs.extend(self._md_inline(line)); segs.append(br)
        if code:
            # 回复被截断在 ``` 围栏中间时，这里会收到未闭合的尾部代码。
            # 空内容（只有围栏/换行）不再渲染成深底色块——避免聊天底部
            # 出现一条无意义的黑色框条。
            tail = "\n".join(code)
            if tail.strip():
                segs.append({"text": tail + "\n", "tag": "mdcodeblock"})
        return segs

    def _md_inline(self, line):
        import re
        segs = []
        pat = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")
        pos = 0
        for m in pat.finditer(line):
            if m.start() > pos:
                segs.append({"text": line[pos:m.start()], "tag": "assistant"})
            tok = m.group(0)
            if tok.startswith("**"):
                segs.append({"text": tok[2:-2], "tag": "mdbold"})
            elif tok.startswith("`"):
                segs.append({"text": tok[1:-1], "tag": "mdcode"})
            elif tok.startswith("["):
                u = re.match(r"\[([^\]]+)\]\(([^)]+)\)", tok)
                segs.append({"text": u.group(1), "tag": "mdlink", "url": u.group(2)})
            else:
                segs.append({"text": tok, "tag": "assistant"})
            pos = m.end()
        if pos < len(line):
            segs.append({"text": line[pos:], "tag": "assistant"})
        return segs

    def _on_event(self, event):
        etype = event["type"]
        if etype == "text":
            self._spinner_stop()      # 有正文输出：先撤掉等待行
            self._assistant_append(event["delta"])
        elif etype == "reasoning":
            self._spinner_stop()
            self._append(event["delta"], "meta")
        elif etype == "model_switch":
            # 本地模型不可用自动回退云端：顶部/底部模型按钮切到实际使用的
            # 模型，避免界面显示一个没在运行的本地模型让用户误以为还在用
            mc = event.get("to")
            if mc is not None:
                self.current_model = mc

                def _switch_btn():
                    self.model_btn.config(text=self._model_btn_label(),
                                          width=self._model_btn_width())
                    self._update_thinking_btn()
                    if hasattr(self, "bottom_model_btn"):
                        self.bottom_model_btn.config(
                            text=self._model_btn_label(),
                            width=self._model_btn_width())
                self.root.after(0, _switch_btn)
                self._set_status(_t("st.model", m=mc.display_name))
        elif etype == "plan":
            # 模型通过 task_plan 下发/更新计划：任务步骤整体替换为计划清单
            self.root.after(0, lambda s=event.get("steps") or []:
                            self._todo_from_plan(s))
        elif etype == "tool_start":
            self._md_reset_block()
            self._todo_start(event.get("name"), event.get("args") or {})
            name = event["name"]
            if name == "write_file":
                self._pending_write_path = (event.get("args") or {}).get("path")
            if name == "call_model":
                # 模型派发：醒目显示派发给哪个模型（角色 + key），task 作参数行
                args = event.get("args") or {}
                target = config.dispatch_target_label(args.get("model", ""))
                segs = [{"text": f"\n🔁 派发给 {target}（{args.get('model', '')}）\n",
                         "tag": "dispatch"}]
                segs += _fmt_tool_args({"task": args.get("task", "")})
            else:
                segs = [{"text": f"\n🔧 {name}\n", "tag": "tool"}]
                segs += _fmt_tool_args(event.get("args") or {})
            self._append_segments(segs)
            self._set_status(_t("evt.tool_run", name=name))
        elif etype == "tool_result":
            self._todo_done(event.get("name"))
            # 写文件/执行命令可能新增或删除工作区文件 → 去抖刷新文件树
            if event.get("name") in ("write_file", "run_shell"):
                self._schedule_fs_refresh()
            self._render_tool_result(event.get("name") or _t("evt.tool"),
                                     event["result"])
            # write_file 完成：刷新已打开的文件标签（path 在 tool_start 记录）
            if event.get("name") == "write_file":
                pth = getattr(self, "_pending_write_path", None)
                if pth:
                    self._reload_editor_tab(pth)
                    self._pending_write_path = None
        elif etype == "round":
            # 一轮工具结束、进入下一轮：重新显示转动的等待
            self._spinner_start(_t("evt.round", n=event["n"]))
        elif etype == "usage":
            self._update_usage(event.get("total") or {})
        elif etype == "cache_hit":
            self.cache_hits += 1
            self.cache_saved_tokens += event.get("saved", 0)
            self._render_usage()
        elif etype == "context_compact":
            self._append(
                _t("evt.compact", before=event["before"], after=event["after"])+"\n",
                "meta")
        elif etype == "tool_denied":
            self._append(_t("evt.denied", name=event["name"])+"\n", "denied")
        elif etype == "media":
            # MCP 工具产出的图片等媒体：内嵌显示
            for p in event.get("paths") or []:
                self._append_media(p)

    def clear(self):
        self.chat.config(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.config(state="disabled")

    # ================= 字号调节（聊天 / 编辑器） =================
    def _show_font_popup(self):
        """Aa 弹窗：聊天与编辑器两行 −/＋ 调节，实时生效并持久化。"""
        pop = tk.Toplevel(self.root)
        pop.title("")
        try:
            pop.overrideredirect(True)
        except Exception:                # noqa: BLE001
            pass
        pop.transient(self.root)
        pop.configure(bg=theme.PANEL, highlightthickness=1,
                      highlightbackground="#d4d4d4")
        # 定位到 Aa 按钮下方（用 lang 按钮附近的右上角：取 ❓ 位置近似）
        self.root.update_idletasks()
        rx = self.root.winfo_rootx() + self.root.winfo_width() - 260
        ry = self.root.winfo_rooty() + 60
        pop.geometry("240x120+%d+%d" % (max(rx, 0), ry))

        tk.Label(pop, text="Aa " + _t("font.title"), bg=theme.PANEL,
                 font=(FONT_UI, 10, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        xb = tk.Label(pop, text="✕", bg=theme.PANEL, fg=theme.MUTED, cursor="hand2",
                      font=(FONT_UI, 10))
        xb.place(relx=1.0, x=-18, y=6)
        xb.bind("<Button-1>", lambda _e: pop.destroy())

        self._font_pop_labels = {}
        for which, key in (("chat", "font.chat"), ("editor", "font.editor")):
            row = tk.Frame(pop, bg=theme.PANEL)
            row.pack(fill="x", padx=10, pady=3)
            tk.Label(row, text=_t(key), bg=theme.PANEL, width=6, anchor="w",
                     font=(FONT_UI, 10)).pack(side="left")
            val = self._font_chat if which == "chat" else self._font_editor
            lbl = tk.Label(row, text=str(val), bg="white", width=3,
                           font=(FONT_MONO, 10))
            lbl.pack(side="right")
            self._font_pop_labels[which] = lbl
            _flat_button(row, text="＋", width=2, font=(FONT_MONO, 10),
                         command=lambda w=which: self._adjust_font(w, 1)
                         ).pack(side="right", padx=(2, 0))
            _flat_button(row, text="－", width=2, font=(FONT_MONO, 10),
                         command=lambda w=which: self._adjust_font(w, -1)
                         ).pack(side="right")
        # Esc / ✕ 关闭（不绑 FocusOut：点 ＋/－ 会让焦点在弹窗内移动，误触关闭）
        pop.bind("<Escape>", lambda _e: pop.destroy())
        pop.focus_set()

    def _adjust_font(self, which: str, delta: int):
        lo, hi = config.FONT_SIZE_MIN, config.FONT_SIZE_MAX
        if which == "chat":
            self._font_chat = max(lo, min(hi, self._font_chat + delta))
            config.set_font_size_chat(self._font_chat)
            # tag 重配置 = 已有聊天文本即时缩放；输入框跟随
            self._append_style()
            self.chat.config(font=(FONT_MONO, self._font_chat))
            self.input.config(font=(FONT_MONO, self._font_chat + 1))
        else:
            self._font_editor = max(lo, min(hi, self._font_editor + delta))
            config.set_font_size_editor(self._font_editor)
            # 所有打开的编辑器视图即时更新
            for frame in self._file_views.values():
                for w in frame.winfo_children():
                    if isinstance(w, scrolledtext.ScrolledText):
                        w.config(font=(FONT_MONO, self._font_editor))
                        w.tag_configure("def", font=(FONT_MONO,
                                                     self._font_editor, "bold"))
        lbl = getattr(self, "_font_pop_labels", {}).get(which)
        if lbl and lbl.winfo_exists():
            lbl.config(text=str(self._font_chat if which == "chat"
                                else self._font_editor))


def _setup_fonts(root):
    """根据系统已安装字体重选 FONT_MONO / FONT_UI（跨平台）。"""
    global FONT_MONO, FONT_UI, FONT_EMOJI
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families(root))

        def pick(candidates, fallback):
            for name in candidates:
                if name in families:
                    return name
            return fallback

        FONT_MONO = pick(_MONO_CANDIDATES, "TkFixedFont")
        FONT_UI = pick(_UI_CANDIDATES, "TkDefaultFont")
        FONT_EMOJI = pick(_FONT_EMOJI_CANDIDATES, FONT_UI)   # 没彩色 emoji 时回退正文字体（显示为黑字形但不报错）
    except Exception:  # noqa: BLE001
        pass  # 查询失败则保留默认，界面仍可用


def _register_dnd_targets(app):
    """聊天区 + 输入框注册拖放目标；支持一次拖入多个文件。"""
    from tkinterdnd2 import DND_FILES

    def _drop(event):
        # Tk DnD 的路径列表用空格分隔，含空格路径包 {…}，splitlist 统一拆
        paths = app.root.tk.splitlist(event.data)
        added = [p for p in paths if os.path.isfile(p)
                 and p not in app._pending_attachments]
        app._pending_attachments.extend(added)
        if added:
            app._render_attachments()
            kinds = "、".join(media.classify(p) or _t("msg.file") for p in added)
            app._set_status(_t("ui.attach_n", n=len(added), kinds=kinds))
        return "copy"                # tkdnd 要求回调返回动作

    def _source_drag(event):
        """文件树的拖拽源：DragInitCmd 回调返回 (动作, 类型, 数据)。"""
        try:
            iid = event.widget.focus() or event.widget.identify_row(event.y)
            vals = event.widget.item(iid, "values") if iid else ("", False)
            if vals and len(vals) >= 2 and str(vals[1]).strip().lower() == "false":
                p = vals[0]
                if p and os.path.isfile(p):
                    return ("copy", DND_FILES, p)
            return ("copy", DND_FILES, "")
        except Exception:        # noqa: BLE001
            return ("copy", DND_FILES, "")

    _targets = [app.chat, app.input, app.attach_bar]
    if getattr(app, "stat_frame", None):
        _targets.append(app.stat_frame)
    for widget in _targets:
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", _drop)
        except Exception:            # noqa: BLE001  个别控件不支持则跳过
            pass

    # 文件树作为拖拽源：按住文件拖出 → 把该文件路径作为拖拽数据，
    # 落到聊天/输入框即加入附件（效果等同"添加到对话"）
    try:
        ft = app.file_tree
        ft.drag_source_register(1, DND_FILES)
        ft.dnd_bind("<<DragInitCmd>>", _source_drag)
    except Exception:            # noqa: BLE001  tkdnd 源注册失败则跳过
        pass


def _setup_dnd(app) -> bool:
    """给普通 Tk 根窗口手动补装 tkdnd（launch 优先直接建 DnD 根）。

    可选依赖：未安装时静默降级（拖放不可用，📎 按钮不受影响）。
    返回是否启用成功。
    """
    try:
        import tkinterdnd2
        root = app.root
        pkg_dir = os.path.join(os.path.dirname(tkinterdnd2.__file__), "tkdnd")
        # 按当前平台 + 位宽挑库目录（x64/arm64/x86，另含 tcl9 变体）
        machine = os.uname().machine if hasattr(os, "uname") else ""
        width = {"x86_64": "x64", "aarch64": "arm64", "arm64": "arm64",
                 "i386": "x86", "i686": "x86", "AMD64": "x64"}.get(machine, "")
        prefix = {"linux": "linux", "win32": "win", "darwin": "osx"}.get(
            sys.platform, "")
        lib_dir = None
        for name in sorted(os.listdir(pkg_dir)):
            if name.startswith(prefix) and width in name:
                lib_dir = os.path.join(pkg_dir, name)
                break
        if not lib_dir:
            return False
        root.tk.eval(f"lappend auto_path {{{lib_dir}}}")
        root.tk.eval("package require tkdnd")
        _register_dnd_targets(app)
        return True
    except Exception:  # noqa: BLE001 未装/平台不匹配 → 静默降级
        return False


_APP_ICONS: list = []        # 持有 PhotoImage 引用，防 Tk 回收导致图标消失


def _set_app_icon(root):
    """设置当前产品的窗口图标：products/<name>/assets/<name>_icon.png。

    仅当该产品目录存在匹配图标时才生效；找不到/解码失败一律静默降级，
    不阻断启动（沿用系统默认图标）。iconphoto 第一个参数 True 让子窗口
    （Toplevel 面板）也继承该图标。
    """
    try:
        import products as _products
        name = _products.active().name
        path = os.path.join(_products.products_dir(), name, "assets",
                            f"{name}_icon.png")
        if not os.path.isfile(path):
            return
        photo = tk.PhotoImage(file=path)
        _APP_ICONS.append(photo)
        root.iconphoto(True, photo)
    except Exception:                # noqa: BLE001  图标缺失/解析失败 → 忽略
        return


def launch():
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()       # 原生支持拖放
        dnd_ready = True
    except Exception:  # noqa: BLE001 未装 tkinterdnd2 → 普通 Tk，拖放降级
        root = tk.Tk()
        dnd_ready = False
    _load_bundled_fonts()   # 先注册项目自带字体，再让 _setup_fonts 能查到它们
    _setup_fonts(root)
    theme.apply(root, base_font=FONT_UI, mono_font=FONT_MONO)   # 设计令牌 + ttk 定制
    app = App(root)
    if dnd_ready:
        _register_dnd_targets(app)
    else:
        _setup_dnd(app)       # 尝试手动补装（成功则同样注册目标）
    root.mainloop()