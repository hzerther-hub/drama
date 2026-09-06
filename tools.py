# -*- coding: utf-8 -*-
"""工具定义 + 执行器。"""

from __future__ import annotations
import glob
import html
import os
import re
import subprocess
import urllib.parse
import urllib.request
from contextlib import contextmanager

import config
import llm

# 当前工作目录（可变，支持 UI 切换）
WORKSPACE = config.WORKSPACE


def set_workspace(path: str):
    """切换工作目录。"""
    global WORKSPACE
    WORKSPACE = path


def get_workspace() -> str:
    return WORKSPACE


@contextmanager
def push_workspace(path: str):
    """临时切换工作目录，with 块结束自动恢复（测试 / 嵌套任务隔离用）。

    用法：
        with tools.push_workspace("/tmp/proj"):
            ...   # 此期间 WORKSPACE 指向 /tmp/proj
    """
    old = WORKSPACE
    set_workspace(path)
    try:
        yield path
    finally:
        set_workspace(old)


def git_branch(workspace: str | None = None) -> str | None:
    """读工作区（或上级目录）当前 git 分支；非仓库 / 失败返回 None。

    只读 .git/HEAD，不调 git 子进程。支持普通仓库与 worktree（.git 为文件）。
    游离 HEAD 时返回短哈希。workspace 默认当前 WORKSPACE。
    """
    root = workspace if workspace is not None else WORKSPACE
    if not root:
        return None
    cur = os.path.abspath(root)
    git_path = None
    while True:
        candidate = os.path.join(cur, ".git")
        if os.path.exists(candidate):
            git_path = candidate
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
    git_dir = git_path
    if os.path.isfile(git_path):
        try:
            with open(git_path, encoding="utf-8") as f:
                line = f.readline().strip()
        except OSError:
            return None
        if not line.lower().startswith("gitdir:"):
            return None
        git_dir = line.split(":", 1)[1].strip()
        if not os.path.isabs(git_dir):
            git_dir = os.path.normpath(
                os.path.join(os.path.dirname(git_path), git_dir))
    head_file = os.path.join(git_dir, "HEAD")
    try:
        with open(head_file, encoding="utf-8") as f:
            ref = f.read().strip()
    except OSError:
        return None
    if ref.startswith("ref:"):
        name = ref[4:].strip()
        if name.startswith("refs/heads/"):
            return name[len("refs/heads/"):]
        if name.startswith("refs/"):
            return name.split("/", 2)[-1]
        return name or None
    return ref[:7] if len(ref) >= 7 else (ref or None)


# ---------------- 沙箱（写操作护栏，非 OS 级隔离） ----------------

def path_in_workspace(path: str, root: str | None = None) -> bool:
    """path（解析后）是否落在工作目录内。大小写/符号链接归一化后判断。"""
    root = root or WORKSPACE
    try:
        r = os.path.normcase(os.path.realpath(root))
        p = os.path.normcase(os.path.realpath(path))
        return p == r or p.startswith(r + os.sep)
    except (OSError, ValueError):
        return False


# 高危 shell 命令（大小写不敏感）：只拦"一眼 destructive"的操作，
# 正常开发命令不受影响。
_BLOCKED_SHELL_PATTERNS = [
    r"\brm\s+(?:-\w+\s+)*-\w*[rf]\w*\s+/(?:\s|$|\*)",   # rm -rf / 或 rm -rf /*
    r"\bmkfs(?:\.\w+)?\b",                              # 格式化文件系统
    r"\bdd\s+[^|;]*\bof=/dev/",                         # dd 直写块设备
    r":\(\)\s*\{",                                      # fork bomb :(){ :|:& };:
    r"\b(?:shutdown|reboot|poweroff|halt)\b",           # 关机/重启
    r"\bformat\s+[a-zA-Z]:",                            # Windows 格式化盘符
    r"\b(?:rd|rmdir)\s+/s\s+/q\s+[a-zA-Z]:[\\/]?\s*$",  # rd /s /q C:\
    r"\bdel\s+/[sqfSQF/]+\s+[a-zA-Z]:[\\/]\*",          # del /s /q C:\*
    # --- 以下为护栏扩充（原 8 条只拦"删根目录"级操作）---
    r"\brm\s+(?:-\w+\s+)*-\w*[rf]\w*\s+(?:\.{1,2}|~|\*)(?:\s|$)",  # rm -rf . .. ~ *
    r"\b(?:rd|rmdir)\s+(?:/[a-z]+\s+)*\.{1,2}\s*$",     # rd /s /q .
    r"\bRemove-Item\b(?=[^|;&]*-recurse\b|-r\b)(?=[^|;&]*(?:-force\b|-fo\b|~|\*))",  # PS 递归强删
    r"\bgit\s+reset\s+--hard\b",                        # 丢弃全部未提交修改
    r"\bgit\s+clean\s+(?:-\w+\s+)*-\w*f\w*d\w*|\bgit\s+clean\s+(?:-\w+\s+)*-\w*d\w*f\w*",  # git clean -fd[x]
    r"\bgit\s+(?:checkout|restore)\s+(?:--\s+)?\.(?:\s|$)",  # 整仓丢弃式还原
]
# 预编译一次，避免每次 run_shell 都重复 re.compile
_COMPILED_BLOCKED_PATTERNS = [(p, re.compile(p, re.I))
                              for p in _BLOCKED_SHELL_PATTERNS]


def shell_command_blocked(cmd: str) -> str | None:
    """命中高危模式返回命中的模式，否则 None。"""
    for pat, rx in _COMPILED_BLOCKED_PATTERNS:
        if rx.search(cmd):
            return pat
    return None


# 每个工具：JSON Schema 定义（用于发送给模型）+ 执行函数
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容。返回带行号的文本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径（绝对或相对路径）"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入（或覆盖）文件内容。沙箱限制：只能写工作目录内的路径。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的完整内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出目录内容（文件和子目录）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认当前工作目录"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_plan",
            "description": (
                "制定/更新当前任务的计划清单（3~8 步），会在界面显示为任务步骤。"
                "每步写『做什么、达成什么』的功能描述（如『梳理配置加载流程』），"
                "不要写成工具名或文件名罗列。多步任务开始前必须先调用一次；"
                "每完成一步就重新调用，把已完成步骤的文本前加 '[x] ' 标记。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "计划步骤列表，每项一句功能描述；已完成的前缀 '[x] '",
                    },
                },
                "required": ["steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_search",
            "description": "按通配符查找文件，如 '*.py' 或 '**/*.js'。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "glob 通配符模式"}
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "在文件内容中按正则/关键字搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "要搜索的关键字或正则"},
                    "path": {"type": "string", "description": "目录或文件路径，默认工作目录"},
                },
                "required": ["pattern", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lsp_diagnostics",
            "description": (
                "用 LSP 语言服务器检查代码文件的错误/警告（比正则更准确，"
                "懂类型与导入）。修改代码前后均可调用以核实。"
                "仅支持已安装对应语言服务器的语言（Python/JS/TS/Go/Rust/C++/"
                "Java 等），不支持时返回提示。"),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string",
                             "description": "要检查的文件路径（相对工作目录）"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "index_search",
            "description": "语义检索整个代码库：按相关度返回最相关的代码片段"
                           "（含文件和行号）。回答「XX在哪实现的/怎么用的」这类问题"
                           "时优先用它，比逐个读文件快且省上下文。首次调用会自动建索引。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索内容：功能描述、函数名、类名等"},
                    "top_k": {"type": "integer", "description": "返回片段数，默认 5"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "执行 shell 命令并返回 stdout/stderr。"
                           "（命令需与当前操作系统兼容：Linux/macOS 用 POSIX shell，"
                           "Windows 用 cmd；格式化磁盘、rm -rf /、关机等高危命令"
                           "会被沙箱拦截）",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "联网搜索（Bing/DuckDuckGo/百度自动回退）。返回结果列表（标题/链接/摘要）。"
                           "查最新信息、找库/文档、排查报错时优先使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer",
                                    "description": "返回条数，默认 8，最大 10"},
                },
                "required": ["query"],
            },
        },
    },
]


def _resolve(path: str) -> str:
    """把相对路径解析到工作目录。"""
    return path if os.path.isabs(path) else os.path.join(WORKSPACE, path)


def _read_file(args):
    p = _resolve(args["path"])
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return f"错误：文件不存在 {p}"
    except IsADirectoryError:
        return f"错误：{p} 是目录"
    numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
    return numbered if numbered else "(空文件)"


def _write_file(args):
    p = _resolve(args["path"])
    if config.SANDBOX and not path_in_workspace(p):
        return (f"错误：沙箱模式禁止写入工作目录之外的路径：{p}\n"
                f"（工作目录：{WORKSPACE}；确需写入请先切换工作目录，"
                f"或设环境变量 LAS_SANDBOX=off）")
    parent = os.path.dirname(p)
    if parent:  # 裸文件名时 dirname 为空，makedirs("") 会抛异常
        os.makedirs(parent, exist_ok=True)
    import checkpoints
    checkpoints.snapshot(p)   # 覆盖前快照（供 /undo 回滚；失败不阻断写入）
    with open(p, "w", encoding="utf-8") as f:
        f.write(args["content"])
    return f"已写入 {p}（{len(args['content'])} 字符）"


def _list_dir(args):
    p = _resolve(args.get("path", WORKSPACE))
    try:
        entries = sorted(os.listdir(p))
    except FileNotFoundError:
        return f"错误：目录不存在 {p}"
    except NotADirectoryError:
        return f"错误：{p} 不是目录"
    out = []
    for e in entries:
        full = os.path.join(p, e)
        marker = "/" if os.path.isdir(full) else ""
        out.append(f"{e}{marker}")
    return "\n".join(out) if out else "(空目录)"


def _glob_search(args):
    pattern = args["pattern"]
    if not os.path.isabs(pattern):
        pattern = os.path.join(WORKSPACE, pattern)
    matches = sorted(glob.glob(pattern, recursive=True))
    # 限制返回数量，避免爆上下文
    if not matches:
        return "未找到匹配文件"
    return "\n".join(matches[:200])


# grep 跳过超过该大小的文件（多为二进制/生成物），避免拖慢整树扫描
_MAX_GREP_FILE = 5 * 1024 * 1024


def _grep_search(args):
    pattern = args["pattern"]
    root = _resolve(args.get("path", WORKSPACE))
    hits = []
    targets = [root] if os.path.isfile(root) else []
    if not targets:
        for dirpath, dirnames, filenames in os.walk(root):
            # 跳过隐藏目录和常见噪音目录
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in
                           ("node_modules", ".git", "__pycache__", "dist", "build")]
            for fn in filenames:
                targets.append(os.path.join(dirpath, fn))
    # 编译正则；无效则按字面量匹配（转义后）
    try:
        rx = re.compile(pattern)
    except re.error:
        rx = re.compile(re.escape(pattern))

    for fpath in targets:
        try:
            if os.path.getsize(fpath) > _MAX_GREP_FILE:
                continue
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if rx.search(line):
                        hits.append(f"{fpath}:{i}: {line.strip()[:160]}")
                        if len(hits) >= 100:
                            return "\n".join(hits) + "\n(结果已截断)"
        except (OSError, UnicodeDecodeError):
            continue
    return "\n".join(hits) if hits else "未找到匹配内容"


def _index_search(args):
    import codeindex
    query = args["query"]
    top_k = int(args.get("top_k", 5) or 5)
    codeindex.ensure(WORKSPACE)
    hits = codeindex.search(WORKSPACE, query, top_k)
    if not hits:
        return "未检索到相关代码（索引可能为空，或换个关键词试试）"
    out = []
    for h in hits:
        out.append(f"### {h['file']}:{h['start_line']}-{h['end_line']}"
                   f"（相关度 {h['score']}）\n{h['content']}")
    return "\n\n".join(out)


def _strip_tags(s: str) -> str:
    """去掉 HTML 标签并还原实体，用于解析搜索结果页。"""
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _fetch_page(url: str, ua: str) -> str:
    """抓取页面，失败返回空字符串（网络问题由调用方换引擎重试）。"""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": ua,
                          "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""


def _parse_bing(page: str) -> list:
    """解析 Bing 结果页：<h2><a href> 标题 + <p> 摘要。"""
    results = []
    # 每个结果块 <li class="b_algo"> … <h2><a href="URL">标题</a></h2> … <p>摘要</p>
    for block in re.findall(r'<li class="b_algo".*?</li>', page, re.S):
        m = re.search(r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h2>',
                      block, re.S)
        if not m:
            continue
        url, title = m.group(1), _strip_tags(m.group(2))
        if not url.startswith("http"):
            continue
        snip_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
        snip = _strip_tags(snip_m.group(1)) if snip_m else ""
        results.append((title, url, snip))
    return results


def _parse_baidu(page: str) -> list:
    """解析百度结果页：<h3> 标题链接 + c-abstract 摘要。"""
    results = []
    for block in re.findall(r'<div class="result[^"]*"[^>]*>.*?</div>\s*</div>',
                            page, re.S):
        m = re.search(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                      block, re.S)
        if not m:
            continue
        url, title = m.group(1), _strip_tags(m.group(2))
        snip_m = re.search(
            r'class="c-abstract[^"]*"[^>]*>(.*?)(?:</span>|</div>)', block, re.S)
        snip = _strip_tags(snip_m.group(1)) if snip_m else ""
        results.append((title, url, snip))
        if len(results) >= 10:
            break
    return results


def _parse_duckduckgo(page: str) -> list:
    """解析 DuckDuckGo HTML/Lite 版结果页。"""
    results = []
    # html 版：结果链接 class="result__a"，真实地址在 href 的 uddg= 参数里
    blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        page, re.S)
    snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page, re.S)
    for i, (href, title) in enumerate(blocks):
        m = re.search(r"[?&]uddg=([^&]+)", href)
        url = urllib.parse.unquote(m.group(1)) if m else href
        snip = _strip_tags(snips[i]) if i < len(snips) else ""
        results.append((_strip_tags(title), url, snip))
    if results:
        return results
    # lite 版备用布局：链接 class='result-link'，摘要在 class='result-snippet'
    blocks = re.findall(
        r"<a[^>]*class='result-link'[^>]*href=\"([^\" )]+)\"[^>]*>(.*?)</a>",
        page, re.S)
    snips = re.findall(r"class='result-snippet'[^>]*>(.*?)</td>", page, re.S)
    for i, (url, title) in enumerate(blocks):
        m = re.search(r"[?&]uddg=([^&]+)", url)
        real = urllib.parse.unquote(m.group(1)) if m else url
        snip = _strip_tags(snips[i]) if i < len(snips) else ""
        results.append((_strip_tags(title), real, snip))
    return results


def _web_search(args):
    """联网搜索：多引擎自动回退（Bing → DuckDuckGo → 百度），零第三方依赖。"""
    query = (args.get("query") or "").strip()
    max_results = min(int(args.get("max_results", 8) or 8), 10)
    if not query:
        return "错误：query 不能为空"

    ua = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    q = urllib.parse.quote(query)
    engines = [
        ("Bing", f"https://www.bing.com/search?q={q}&setmkt=zh-CN&count=10",
         _parse_bing),
        ("DuckDuckGo", f"https://html.duckduckgo.com/html/?q={q}",
         _parse_duckduckgo),
        ("百度", f"https://www.baidu.com/s?wd={q}&rn=10", _parse_baidu),
    ]
    tried = []
    results = []
    used = ""
    for name, url, parse in engines:
        tried.append(name)
        page = _fetch_page(url, ua)
        if not page:
            continue
        results = parse(page)
        if results:
            used = name
            break

    if not results:
        return (f"搜索失败或无结果：{query}\n"
                f"（已尝试 {'、'.join(tried)}；可稍后重试或换关键词）")
    lines = []
    for i, (title, url, snip) in enumerate(results[:max_results], 1):
        lines.append(f"{i}. {title}\n   {url}\n   {snip[:200]}")
    return f"（搜索引擎：{used}，共 {min(len(results), max_results)} 条）\n\n" + \
        "\n\n".join(lines)

def _run_shell(args):
    cmd = args.get("command")
    if cmd is None or not str(cmd).strip():
        return ("错误：command 参数为空，无法执行。"
                "请修正参数后重试，或改用其他工具/方法继续当前任务。")
    cmd = str(cmd)
    if config.SANDBOX:
        hit = shell_command_blocked(cmd)
        if hit:
            return (f"错误：沙箱拦截了高危命令（规则 {hit}）。"
                    f"确需执行请由用户手动运行，或设 LAS_SANDBOX=off 关闭沙箱。")
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=config.TOOL_EXEC_TIMEOUT, cwd=WORKSPACE)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        parts = []
        if out:
            parts.append(out)
        if err:
            parts.append(f"[stderr]\n{err}")
        if r.returncode != 0:
            parts.append(f"[退出码 {r.returncode}]")
        return "\n".join(parts) if parts else "(无输出)"
    except subprocess.TimeoutExpired:
        return f"错误：命令超时（>{config.TOOL_EXEC_TIMEOUT}秒）"


# ---------------- 模型派发（call_model：把文本子任务派发给其它模型） ----------------
# 编排大脑分析意图后，用 call_model 把一段文本子任务派给已配置的云端目标。
# 约束：本地模型串行（一次一个）——本地→本地派发禁止；只派文本，不带图片。

# call_model 子任务时注入的子系统提示：让子模型只专注于该子任务、简洁作答。
_DISPATCH_SUB_PROMPT = (
    "你是一个子任务执行模型。请只完成用户给你的这段子任务，输出简洁、准确、"
    "可用的结果即可，不要复述任务，不要询问上下文，不要在结果里加入与任务无关的内容。"
)
# 子任务结果回填主循环前的字符上限（防止撑爆主循环上下文；后续 context 压缩会再收紧）。
DISPATCH_RESULT_KEEP = 8000

CALL_MODEL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "call_model",
        "description": (
            "把一段文本子任务委派给另一个（云端）模型处理（云端才花钱，非必要不用）。"
            "只有当本地确实搞不定时才用：任务复杂/重推理/超出你上下文与能力，或本地缺少所需能力"
            "（识图、专门领域专长等），或你尝试后仍无法高质量完成。本地能搞定就别委派。"
            "目标选择：复杂、重推理、需更强能力→deepseek/deepseek-v4-pro；含图片/识图→deepseek-v4-flash-vision-exp。"
            "model=目标模型 key；task=交给它的完整子任务提示词（尽量自包含）；"
            "reasoning_effort 可选（复杂任务可设 high）。只做文本子任务，不要传图片。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model": {"type": "string",
                          "description": "目标模型 key（已配置的派发目标之一）"},
                "task": {"type": "string",
                         "description": "交给目标模型的子任务提示词"},
                "reasoning_effort": {"type": "string",
                                     "description": "可选：推理等级（low/medium/high）"},
            },
            "required": ["model", "task"],
        },
    },
}


# ---------------- 公司知识库（企业代码 RAG，kb_search 工具） ----------------
# 只在「公司知识库已启用」时暴露（见 kb_schema），与 index_search（工作区）互补：
# kb_search 覆盖配置的多个公司根目录（代码仓库 + 文档）。
KB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "kb_search",
        "description": (
            "检索公司知识库（企业代码 + 文档）：按相关度返回最相关的代码/文档片段"
            "（含知识根目录、文件与行号）。回答涉及公司内部代码/文档、跨仓库问题时"
            "优先用它，比逐个读文件快且省上下文。首次调用会自动建索引；"
            "与 index_search（当前工作目录）不同，kb_search 覆盖配置的多个公司根目录。"),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "检索内容：功能描述、函数名、类名、文档关键词等"},
                "top_k": {"type": "integer",
                          "description": "返回片段数，默认取配置（4）"},
            },
            "required": ["query"],
        },
    },
}


def _kb_search(args: dict) -> str:
    """kb_search 执行器：检索公司知识库（只读，结果可缓存）。"""
    import codera
    roots = config.get_kb_roots()
    if not roots:
        return ("错误：公司知识库尚未配置知识根目录。请在「📚 知识库」面板"
                "添加代码/文档目录后再检索。")
    query = (args.get("query") or "").strip()
    if not query:
        return "错误：query 不能为空"
    try:
        top_k = int(args.get("top_k", 0) or config.get_kb_top_k())
    except (TypeError, ValueError):
        top_k = config.get_kb_top_k()
    codera.maybe_auto_refresh(roots)
    hits = codera.search(query, top_k)
    if not hits:
        return ("未在知识库检索到相关内容（索引可能为空，或换个关键词；"
                "可在「📚 知识库」面板重建索引后重试）")
    out = []
    for h in hits:
        out.append(f"### [{h['source']} 相关度 {h['score']}] "
                   f"{h['root']}/{h['file']}:{h['start_line']}-{h['end_line']}\n"
                   f"{h['content']}")
    return "\n\n".join(out)


def kb_schema() -> list:
    """公司知识库「已启用」时才提供 kb_search 工具。

    前提（与面板开关一致）：rag 产品功能开启 + kb_enabled + 已配置知识根目录。
    任一不满足 → 不暴露该工具（与 call_model_schema 相同模式）。
    """
    try:
        import products
        if not products.feature("rag", False):
            return []
    except Exception:                    # noqa: BLE001  products 缺失 → 视为未启用
        return []
    if not config.get_kb_enabled():
        return []
    if not config.get_kb_roots():
        return []
    return [KB_SEARCH_SCHEMA]


def _is_local_key(model_key: str) -> bool:
    """模型是否指向本地端点（127.0.0.1 / localhost）。"""
    mc = config.find_model(model_key)
    if mc is None:
        return False
    return any(h in mc.base_url for h in ("127.0.0.1", "localhost"))


def _local_healthy(model_key: str) -> bool:
    """给定本地模型 key，判断对应服务是否已启动且健康。

    借助 localmodels（复用 gpulocal 的 systemd/进程守护 + /v1/models 健康检查）。
    任何异常（gpulocal 缺失、找不到模型、服务未运行）都返回 False。
    """
    try:
        import localmodels
    except Exception:                # noqa: BLE001  gpulocal 目录缺失 → 降级
        return False
    try:
        models = localmodels.list_models()
    except Exception:                # noqa: BLE001
        return False
    if not models:
        return False
    for cfg in models.values():
        key = "%s/%s" % (localmodels.provider_id(cfg),
                         localmodels.model_id(cfg))
        if key == model_key:
            state, healthy = localmodels.status_of(cfg)
            return bool(state == "active" and healthy)
    return False


def validate_dispatch_target(model: str) -> tuple:
    """校验 call_model 的派发目标是否允许。返回 (True/False, 错误串或 None)。

    允许：配置里的三个云端目标（flash/pro/vision）。
    拒绝：本地模型（本地大脑自身=自我调用会递归，其它本地=串行互斥），
          以及不在白名单里的任何目标。
    """
    cfg = config.get_dispatch_config()
    cloud = {cfg["dispatch_flash"], cfg["dispatch_pro"], cfg["dispatch_vision"]}
    if model in cloud:
        return True, None
    if _is_local_key(model):
        if model == cfg["dispatch_model"]:
            return False, "错误：不能派发给当前本地大脑自身（避免自我调用）"
        return False, "错误：本地模型互斥，不能派发给其它本地模型"
    return False, f"错误：派发目标不在白名单内：{model}"


def resolve_dispatch_vision_key() -> str:
    """识图预路由应选用的模型 key。

    本地优先：本地大脑（dispatch_model）带识图且已在运行健康 → 用本地；
    否则回退云端识图（dispatch_vision）。找不到可用识图返回空串。
    """
    cfg = config.get_dispatch_config()
    lb = cfg["dispatch_model"]
    if lb and _is_local_key(lb) and _local_healthy(lb):
        mc = config.find_model(lb)
        if mc is not None and mc.vision:
            return lb
    return cfg["dispatch_vision"]


def _truncate_dispatch(text: str, keep: int) -> str:
    """保头尾截断派发结果。"""
    if len(text) <= keep:
        return text
    head = keep * 2 // 3
    tail = keep - head
    return text[:head] + f"\n…[已压缩，原 {len(text)} 字符]\n" + text[-tail:]


def _call_model(args):
    """call_model 执行器：把文本子任务派发给目标模型，返回其文本结果。"""
    model = (args.get("model") or "").strip()
    task = (args.get("task") or "").strip()
    effort = (args.get("reasoning_effort") or "").strip()
    if not model or not task:
        return "错误：call_model 需要 model 与 task 参数"
    if not config.get_model_dispatch():
        return "错误：模型派发未开启，无法调用其它模型"
    ok, err = validate_dispatch_target(model)
    if not ok:
        return err
    mc = config.find_model(model)
    if mc is None:
        return f"错误：派发目标不存在：{model}"
    # 允许按次指定推理等级：复制一个带指定 reasoning_effort 的配置，不改全局。
    if effort:
        import dataclasses
        try:
            mc = dataclasses.replace(mc, reasoning_effort=effort)
        except Exception:            # noqa: BLE001  异常字段时保持原配置
            pass
    messages = [
        {"role": "system", "content": _DISPATCH_SUB_PROMPT},
        {"role": "user", "content": task},
    ]
    collected = []
    try:
        for ev in llm.stream_chat(mc, messages, None):
            if ev["type"] == "text":
                collected.append(ev["delta"])
    except llm.LLMError as e:
        return f"错误：派发失败：{e}"
    text = "".join(collected)
    if not text:
        return "（派发目标未返回内容）"
    return _truncate_dispatch(text, DISPATCH_RESULT_KEEP)


def _lsp_diagnostics(args: dict) -> str:
    """lsp_diagnostics 执行器：LSP 检查文件错误/警告（只读）。"""
    path = (args.get("path") or "").strip()
    if not path:
        return "错误：缺少参数 path"
    import lsp as lsp_mod
    full = _resolve(path)
    if not os.path.isfile(full):
        return f"错误：文件不存在 {path}"
    lang = lsp_mod.language_of(full)
    if not lang:
        return f"错误：不识别的文件类型（无对应语言）：{path}"
    if not lsp_mod.available_for(lang):
        return (f"提示：{path} 的语言（{lsp_mod.lang_id_of(lang)}）"
                "未安装 LSP 服务器，无法检查。可安装后重试。")
    c = lsp_mod.LSPClient.for_file(full)
    if c is None:
        return f"错误：无法启动 LSP 客户端：{path}"
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        diags = c.diag(content, wait=2.0)
    except Exception as e:                    # noqa: BLE001
        return f"错误：LSP 检查失败：{e}"
    finally:
        c.close()
    if not diags:
        return f"✓ {path}：无错误/警告"
    lines = [f"{path}：{len(diags)} 条诊断"]
    lines += [f"  第{d['line']}行 {d['mark']} {d['msg']}" for d in diags[:30]]
    if len(diags) > 30:
        lines.append(f"  …（其余 {len(diags) - 30} 条略）")
    return "\n".join(lines)


def call_model_schema() -> list:
    """模型派发「已生效」时才提供 call_model 工具。

    生效条件（与 UI 状态点一致）：总开关开启 + 指定了本地大脑（dispatch_model）
    + 该本地模型已在运行且健康。任一不满足 → 不暴露该工具（视为未开启）。
    """
    if not config.get_model_dispatch():
        return []
    model_key = config.get_dispatch_model()
    if not model_key:
        return []
    if not _local_healthy(model_key):
        return []
    return [CALL_MODEL_SCHEMA]


def _task_plan(args: dict) -> str:
    """任务计划工具本体：只做校验与确认，界面渲染由 agent 发 plan 事件完成。"""
    steps = args.get("steps")
    if not isinstance(steps, list) or not steps:
        return "错误：steps 必须是非空的字符串数组"
    steps = [str(s).strip() for s in steps if str(s).strip()]
    if len(steps) < 2:
        return "错误：计划至少需要 2 步；单步任务直接做即可，不必调用 task_plan"
    done_n = sum(1 for s in steps if s.lower().startswith("[x]"))
    return (f"任务计划已更新：共 {len(steps)} 步（已完成 {done_n}）。"
            f"请按计划逐步执行；每完成一步就重新调用 task_plan 更新状态，"
            f"全部完成后给出最终答复。")


_EXECUTORS = {
    "read_file": _read_file,
    "write_file": _write_file,
    "list_dir": _list_dir,
    "glob_search": _glob_search,
    "grep_search": _grep_search,
    "index_search": _index_search,
    "kb_search": _kb_search,
    "run_shell": _run_shell,
    "web_search": _web_search,
    "lsp_diagnostics": _lsp_diagnostics,
    "call_model": _call_model,
    "task_plan": _task_plan,
}


def execute_tool(name: str, arguments: dict) -> str:
    """执行工具，返回结果字符串。未知工具/执行异常都返回错误文本。

    错误只作为普通工具结果回给模型（循环不中断），并附上
    「继续任务」的提示，避免模型看到报错就停下来。
    """
    fn = _EXECUTORS.get(name)
    if fn is None:
        return f"错误：未知工具 {name}"
    try:
        return fn(arguments)
    except Exception as e:  # noqa: BLE001
        return (f"错误：{type(e).__name__}: {e}\n"
                f"（此工具执行失败。请检查参数后重试，或改用其他工具/"
                f"其他方法继续完成当前任务，不要因此停止。）")


# 可写工具：执行前需要用户批准
WRITE_TOOLS = {"write_file", "run_shell"}


def is_write_tool(name: str) -> bool:
    return name in WRITE_TOOLS


_READONLY_SCHEMAS: list | None = None


def readonly_schemas():
    """只读模式下的工具列表（去掉可写工具）。"""
    global _READONLY_SCHEMAS
    if _READONLY_SCHEMAS is None:
        _READONLY_SCHEMAS = [s for s in TOOL_SCHEMAS
                             if s["function"]["name"] not in WRITE_TOOLS]
    return _READONLY_SCHEMAS


def describe_arguments(name: str, args: dict) -> str:
    """把工具参数格式化成人类可读的摘要，用于审批弹窗。

    任何参数为 null/缺失都返回字符串（绝不让下游拿到 None）。
    """
    if name == "run_shell":
        return str(args.get("command") or "")
    if name == "write_file":
        content = str(args.get("content") or "")
        preview = content if len(content) <= 300 else content[:300] + "\n…(截断)"
        return f"文件: {args.get('path') or ''}\n\n{preview}"
    return "\n".join(f"{k}: {v}" for k, v in args.items())
