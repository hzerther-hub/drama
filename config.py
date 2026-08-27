# -*- coding: utf-8 -*-
"""全局配置：模型端点、默认参数。

模型列表从 models.json 加载，用户可以自行编辑该文件增加/删除模型。
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass

# 生成参数
TEMPERATURE = 0.2
MAX_TOKENS = 256000

# Agent 循环安全上限
MAX_TOOL_ROUNDS = 12          # 最多 tool-calling 轮次：读文件+分析+写结论留足空间
TOOL_EXEC_TIMEOUT = 60        # 单个工具执行超时（秒）

# 写操作沙箱（护栏，非操作系统级隔离）：
#   - write_file 只允许写入工作目录之内（含子目录）
#   - run_shell 拦截高危命令（rm -rf /、mkfs、fork bomb、格式化磁盘、关机等）
# 关闭：环境变量 LAS_SANDBOX=off（不推荐；关闭前确保模型输入可信）
SANDBOX = os.environ.get("LAS_SANDBOX", "on").strip().lower() not in \
    ("off", "0", "false", "no")

# 上下文管理（类 DeepSeek Harness：预算 + 渐进压缩）
CONTEXT_BUDGET = 1000000      # 对齐 DSH：deepseek 1M 上下文，超此才压缩
CONTEXT_KEEP_ROUNDS = 2       # 最近 N 轮保留原文
TOOL_RESULT_KEEP = 3000       # 超长工具结果截断保留的字符数

# 缓存设置在 <配置目录>/cache.json（界面「管理缓存」可改），
# 后端可选 auto / sqlite / memory。

# 配置目录（跨平台）：Linux/macOS = ~/.config/local-ai-studio，
# Windows = %APPDATA%\local-ai-studio。所有模块统一从这里取，不要各自硬编码。
import sys as _sys
import shutil as _shutil
if _sys.platform == "win32":
    _base = os.environ.get("APPDATA") or os.path.expanduser("~")
    _CONFIG_DIR = os.path.join(_base, "local-ai-studio")
else:
    _CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "local-ai-studio")
CONFIG_DIR = _CONFIG_DIR   # 对外公开名（cache/sessions/codeindex 复用）
# 旧目录自动迁移，老用户配置不丢（按优先级找第一个存在的）：
#   1) %APPDATA%\wellfuture-coder（上一版名，Windows）
#   2) ~/.config/wellfuture-coder（上一版名；早期 Windows 版本也误用过这里）
#   3) ~/.config/qwen-coder（更早的名字）
if not os.path.exists(_CONFIG_DIR):
    _legacy = []
    if _sys.platform == "win32":
        _legacy.append(os.path.join(_base, "wellfuture-coder"))
    _legacy += [
        os.path.join(os.path.expanduser("~"), ".config", "wellfuture-coder"),
        os.path.join(os.path.expanduser("~"), ".config", "qwen-coder"),
    ]
    for _old in _legacy:
        if os.path.normcase(_old) != os.path.normcase(_CONFIG_DIR) \
                and os.path.exists(_old):
            _shutil.copytree(_old, _CONFIG_DIR)
            break

# 工作目录：工具默认在此目录内操作。
# 启动时恢复上一次使用的目录（存于 state.json），找不到则回退家目录。
_STATE_FILE = os.path.join(_CONFIG_DIR, "state.json")


def _load_last_workspace() -> str:
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            ws = json.load(f).get("workspace", "")
        if ws and os.path.isdir(ws):
            return ws
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return os.path.expanduser("~")


def save_last_workspace(path: str):
    """记住最近一次使用的工作目录。"""
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}
    data["workspace"] = path
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass



WORKSPACE = _load_last_workspace()


def get_quant_llm_model() -> str:
    """量化面板「LLM 兜底」指定的模型 key（存于 state.json）；空 = 未指定。"""
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("quant_llm_model", "") or ""
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""


def set_quant_llm_model(key: str):
    """记住量化 LLM 兜底用哪个模型。"""
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}
    data["quant_llm_model"] = key
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


SYSTEM_PROMPT = (
    "你是编码助手。优先用本地能力完成任务：用工具读文件、搜索代码、执行 shell、联网搜索，"
    "尽量本地解决（本地不额外花钱）。"
    "只有当你确认任务超出本地能力/上下文，或本地缺少所需能力（如识图、超强推理/重分析）时，"
    "才用 call_model 委派给云端：复杂/重推理→deepseek/deepseek-v4-pro；识图→deepseek-v4-flash-vision-exp。"
    "本地能搞定就别委派。"
    "无论本地还是委派，始终精炼作答：只给结论与必要依据，绝不输出大段文件内容或重复列表。"
    "修改/增强代码文件时，必须调用 write_file 把改动真正写回文件（不要只把新内容输出在回复里）；"
    "写完再用 read_file 抽查确认。"
    "完成纪律（必须遵守）："
    "1) 动手前列出完成该任务所需的步骤 todo（读文件→改动→验证→收尾），并逐项完成、逐项确认；"
    "2) 改完必须用 lsp_diagnostics 或运行相关测试/脚本验证，发现问题就修，直到通过；"
    "3) 只有当所有步骤完成且验证通过、目标真正达成时，才给出最终答复；"
    "绝不在半途（改了一部分、还没验证通过）就草草结束。"
    "请始终基于真实工具/委派结果作答，不要编造文件内容。"
    "用户消息可能附带本地媒体文件（图片/音频/视频）路径：图片直接以视觉输入提供；"
    "音频/视频可用 run_shell 调 ffmpeg（ffprobe）提取信息后再分析。"
)


def get_system_prompt() -> str:
    """按当前界面语言返回系统提示（含回复语言指令，中英跟随界面）。"""
    lang = get_language()
    if lang == "zh":
        return SYSTEM_PROMPT + "\n请使用中文回复（与当前界面语言一致）。"
    return SYSTEM_PROMPT + (
        "\nPlease respond in English (matching the current UI language).")

# models.json 存放位置：优先用户配置目录（打包后也可用、便于用户编辑）
# （_CONFIG_DIR 在文件顶部按平台解析：Windows=%APPDATA%，其它=~/.config）
_MODELS_FILE = os.path.join(_CONFIG_DIR, "models.json")
# MCP 服务器配置（JSON-RPC stdio 子进程），见 mcp.py
MCP_FILE = os.path.join(_CONFIG_DIR, "mcp.json")
# MCP 工具返回的图片等媒体落盘目录
MEDIA_DIR = os.path.join(_CONFIG_DIR, "media")
# 附件压缩包解压目录（zip/tar 解到 <文件名>-<哈希>/ 子目录）
EXTRACT_DIR = os.path.join(_CONFIG_DIR, "extract")
# 发给识图模型的图片最大长边（像素）：超过则等比缩小，控制 token 消耗
ATTACH_IMAGE_MAX_PIX = 1568
# 打包/首次运行兜底：项目目录里的 models.json
_BUNDLED_MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json")

_DEFAULT_MODELS = {
    "default": "qwen38-local/qwen3.8-27b-q8",
    "providers": [
        {
            "id": "qwen38-local",
            "name": "本地 Qwen",
            "base_url": "http://127.0.0.1:8097/v1",
            "api_key": "local-noauth",
            "models": [
                {"id": "qwen3.8-27b-q8", "name": "Qwen3.8-27B (DFlash2 加速)"}
            ],
        },
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "",
            "models": [
                {"id": "deepseek-chat", "name": "DeepSeek Chat"},
                {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner"},
            ],
        },
    ],
}


def _ensure_models_file():
    """确保用户配置目录里有 models.json，首次运行自动创建。"""
    if os.path.exists(_MODELS_FILE):
        return
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    # 优先从项目目录复制，否则写入内置默认
    if os.path.exists(_BUNDLED_MODELS):
        import shutil
        shutil.copy(_BUNDLED_MODELS, _MODELS_FILE)
    else:
        import json as _json
        with open(_MODELS_FILE, "w", encoding="utf-8") as f:
            _json.dump(_DEFAULT_MODELS, f, ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class ModelConfig:
    """一个可用的模型：provider + model + 端点。"""
    key: str        # 唯一键，格式 "provider_id/model_id"
    provider_name: str
    model_id: str
    display_name: str
    base_url: str
    api_key: str
    vision: bool = False        # 模型支持识图（多模态输入），models.json 里 "vision": true
    reasoning: bool = False     # 模型支持推理等级（models.json 里 "reasoning": true；设过 effort 也视为支持）
    reasoning_effort: str = ""  # 推理等级（reasoning effort，如 low/medium/high；空=不发送，用模型默认）
    reasoning_choices: tuple = ()  # 该模型支持的等级列表（空 = 按 provider 推断）
    context_window: int = 0      # 上下文窗口（token 数；0 = 未知，用全局 CONTEXT_BUDGET）


# 推理等级支持集合：DeepSeek 扩展集 vs 标准集（OpenAI/Kimi/GLM/本地 llama.cpp）
_DS_REASONING = ("", "none", "low", "medium", "high", "xhigh", "max")
_STD_REASONING = ("", "low", "medium", "high")


def reasoning_choices_for(provider_id: str, provider_name: str, m: dict) -> tuple:
    """返回某模型支持的推理等级集合。

    模型条目可显式声明 "reasoning_efforts": ["low","medium","high"]；
    否则按 provider 推断：名字含 deepseek 用扩展集，其余用标准集。
    """
    raw = m.get("reasoning_efforts")
    if isinstance(raw, list) and raw:
        return tuple(str(x) for x in raw)
    blob = f"{provider_id} {provider_name}".lower()
    return _DS_REASONING if "deepseek" in blob else _STD_REASONING


def load_models() -> tuple[list[ModelConfig], str]:
    """加载 models.json，返回 (模型列表, 默认模型 key)。"""
    _ensure_models_file()
    try:
        with open(_MODELS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = _DEFAULT_MODELS

    models: list[ModelConfig] = []
    for provider in data.get("providers", []):
        pid = provider.get("id", "")
        pname = provider.get("name", pid)
        base_url = provider.get("base_url", "")
        api_key = provider.get("api_key", "")
        for m in provider.get("models", []):
            mid = m.get("id", "")
            mname = m.get("name", mid)
            models.append(ModelConfig(
                key=f"{pid}/{mid}",
                provider_name=pname,
                model_id=mid,
                display_name=mname,
                base_url=base_url,
                api_key=api_key,
                vision=bool(m.get("vision", False)),
                reasoning=bool(m.get("reasoning") or m.get("reasoning_effort")),
                reasoning_effort=str(m.get("reasoning_effort", "") or ""),
                reasoning_choices=reasoning_choices_for(pid, pname, m),
                context_window=int(m.get("context_window", 0) or 0),
            ))
    default = data.get("default", "")
    return models, default


def find_model(key: str) -> ModelConfig | None:
    models, _ = load_models()
    for m in models:
        if m.key == key:
            return m
    return None


def _zh_only_product() -> bool:
    """当前产品是否「仅中文」（zh_only 功能开关）：强制中文、不显示语言切换。"""
    try:
        import products
        return bool(products.feature("zh_only", False))
    except Exception:                # noqa: BLE001  products 缺失 → 不强制
        return False


def get_language() -> str:
    """界面语言：models.json 顶层 "language"，缺省英文。

    产品若为「仅中文」（zh_only），无视存储值强制返回 zh。
    """
    if _zh_only_product():
        return "zh"
    try:
        data = _load_models_data()
        return str(data.get("language", "en"))
    except Exception:                # noqa: BLE001
        return "en"


def set_language(lang: str):
    """保存界面语言；「仅中文」产品强制 zh，不落盘英文。"""
    if _zh_only_product():
        lang = "zh"
    data = _load_models_data()
    lang = "zh" if str(lang).lower() == "zh" else "en"
    if data.get("language") != lang:
        data["language"] = lang
        _save_models_data(data)


def get_standalone() -> bool:
    """独立提问模式：True = 每条消息不带历史上下文单独发送。缺省 False。"""
    try:
        return bool(_load_models_data().get("standalone", False))
    except Exception:                # noqa: BLE001
        return False


def set_standalone(on: bool):
    data = _load_models_data()
    if bool(data.get("standalone", False)) != bool(on):
        data["standalone"] = bool(on)
        _save_models_data(data)


# ---------------- 界面字号（聊天 / 编辑器，持久化） ----------------
FONT_SIZE_MIN, FONT_SIZE_MAX = 8, 24


def _font_size(key: str) -> int:
    try:
        n = int(_load_models_data().get(key, 10))
    except Exception:                # noqa: BLE001
        n = 10
    return max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, n))


def get_font_size_chat() -> int:
    """聊天区基础字号（默认 10）。"""
    return _font_size("font_size_chat")


def set_font_size_chat(n: int):
    data = _load_models_data()
    data["font_size_chat"] = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, int(n)))
    _save_models_data(data)


def get_font_size_editor() -> int:
    """代码编辑器字号（默认 10）。"""
    return _font_size("font_size_editor")


def set_font_size_editor(n: int):
    data = _load_models_data()
    data["font_size_editor"] = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, int(n)))
    _save_models_data(data)


# ---------------- 模型派发（多模型路由） ----------------
# 编排模型先分析用户意图，再把任务派发给合适的模型：
#   · 简单任务 → 本地大脑自己答，或派 dispatch_flash（云端轻量）
#   · 复杂/重推理 → 派 dispatch_pro（云端高性能）
#   · 识图 → 本地大脑带识图就本地看，否则派 dispatch_vision（云端识图）
# 约束：本地模型互相串行（一次只能跑一个），因此本地→本地派发禁止；
# call_model 只派文本子任务（识图由识图模型直接收附件）。
_DISPATCH_DEFAULTS = {
    "model_dispatch": True,                                     # 总开关
    "dispatch_smart": True,                                     # 智排：按任务类型自动路由/识图预路由
    "auto_cloud_fallback": True,                                # 本地模型不可用（加载中/未运行）时自动回退云端
    "dispatch_model": "gpulocal-8097/qwen38-27b-q8",            # 本地大脑
    "dispatch_flash": "deepseek/deepseek-v4-flash",             # 云端简单
    "dispatch_pro": "deepseek/deepseek-v4-pro",                 # 云端复杂/高性能
    "dispatch_vision": "deepseek/deepseek-v4-flash-vision-exp", # 云端识图（必选）
}


def get_dispatch_config() -> dict:
    """返回模型派发配置，缺失字段用默认值补齐。

    model_dispatch / dispatch_smart 归一为 bool；字符串字段去除首尾空白
    （空串则保留默认）。
    """
    d = _load_models_data()
    out = dict(_DISPATCH_DEFAULTS)
    for k in out:
        if k not in d:
            continue
        v = d[k]
        if k in ("model_dispatch", "dispatch_smart", "auto_cloud_fallback"):
            out[k] = bool(v)
        elif isinstance(v, str):
            out[k] = v.strip() or out[k]
    return out


def get_model_dispatch() -> bool:
    """模型派发总开关是否开启。"""
    return bool(get_dispatch_config().get("model_dispatch"))


def get_auto_cloud_fallback() -> bool:
    """本地模型不可用（加载中/未运行）时是否自动回退云端模型。"""
    return bool(get_dispatch_config().get("auto_cloud_fallback"))


def set_model_dispatch(on: bool):
    """开关模型派发。"""
    data = _load_models_data()
    on = bool(on)
    if bool(data.get("model_dispatch", _DISPATCH_DEFAULTS["model_dispatch"])) != on:
        data["model_dispatch"] = on
        _save_models_data(data)


def get_dispatch_smart() -> bool:
    """智排开关：是否按任务类型自动路由（含识图预路由）。"""
    return bool(get_dispatch_config().get("dispatch_smart"))


def set_dispatch_smart(on: bool):
    """开关智排（自动路由/识图预路由）。"""
    data = _load_models_data()
    on = bool(on)
    if bool(data.get("dispatch_smart", _DISPATCH_DEFAULTS["dispatch_smart"])) != on:
        data["dispatch_smart"] = on
        _save_models_data(data)


def get_dispatch_model() -> str:
    """本地大脑模型 key。"""
    return get_dispatch_config()["dispatch_model"]


def set_dispatch_model(key: str):
    _set_dispatch_str("dispatch_model", key)


def get_dispatch_flash() -> str:
    """云端轻量/简单任务派发目标。"""
    return get_dispatch_config()["dispatch_flash"]


def set_dispatch_flash(key: str):
    _set_dispatch_str("dispatch_flash", key)


def get_dispatch_pro() -> str:
    """云端高性能/复杂任务派发目标。"""
    return get_dispatch_config()["dispatch_pro"]


def set_dispatch_pro(key: str):
    _set_dispatch_str("dispatch_pro", key)


def get_dispatch_vision() -> str:
    """云端识图兜底目标（必选）。"""
    return get_dispatch_config()["dispatch_vision"]


def set_dispatch_vision(key: str):
    _set_dispatch_str("dispatch_vision", key)


def _set_dispatch_str(field: str, key: str):
    """设置一个字符串型派发字段；空串或不等于旧值才写盘。"""
    key = (key or "").strip()
    data = _load_models_data()
    if str(data.get(field, _DISPATCH_DEFAULTS[field])).strip() != key:
        data[field] = key
        _save_models_data(data)


def dispatch_target_label(key: str) -> str:
    """派发目标 key 的友好描述（界面/会话回放显示用）。

    命中配置里的三个云端目标 → 中文角色标签；否则原样返回 key。
    """
    cfg = get_dispatch_config()
    if key == cfg["dispatch_pro"]:
        return "云端高性能"
    if key == cfg["dispatch_flash"]:
        return "云端简单"
    if key == cfg["dispatch_vision"]:
        return "云端识图"
    return key


# ---------------- 公司知识库（企业代码 RAG） ----------------
# 多根目录（代码仓库 + 文档）建成持久化知识库；检索 = TF-IDF 兜底 +
# 可选 embedding 增强（kb_embedding 为模型 key，复用其 base_url/api_key/model_id）。
_KB_DEFAULTS = {
    "kb_enabled": False,      # 总开关：开启才提供 kb_search 工具 / 自动注入
    "kb_inject": False,       # 自动注入：每次提问自动检索 top 片段进上下文（省 token）
    "kb_auto": True,          # 自增：检索前自动增量刷新（节流 60s，跳过未变文件）
    "kb_top_k": 4,            # 默认返回片段数
    "kb_embedding": "",       # embedding 模型 key；空 = 纯 TF-IDF
    "kb_roots": [],           # 知识根目录列表
}


def get_kb_config() -> dict:
    """返回知识库配置，缺失字段用默认值补齐（归一类型）。"""
    d = _load_models_data()
    out = dict(_KB_DEFAULTS)
    for k in out:
        if k not in d:
            continue
        v = d[k]
        if k == "kb_roots":
            out[k] = [str(x) for x in v] if isinstance(v, list) else []
        elif k in ("kb_enabled", "kb_inject", "kb_auto"):
            out[k] = bool(v)
        elif k == "kb_top_k":
            try:
                out[k] = max(1, min(20, int(v)))
            except (ValueError, TypeError):
                pass
        elif isinstance(v, str):
            out[k] = v.strip() or out[k]
    return out


def get_kb_roots() -> list[str]:
    """知识根目录列表。"""
    return list(get_kb_config()["kb_roots"])


def set_kb_roots(roots: list[str]):
    """设置知识根目录列表（展开 ~、转绝对路径、去重、排序后写盘）。"""
    roots = sorted({os.path.abspath(os.path.expanduser(r)) for r in roots if r})
    data = _load_models_data()
    data["kb_roots"] = roots
    _save_models_data(data)


def get_kb_enabled() -> bool:
    """知识库总开关。"""
    return bool(get_kb_config()["kb_enabled"])


def set_kb_enabled(on: bool):
    data = _load_models_data()
    on = bool(on)
    if bool(data.get("kb_enabled", _KB_DEFAULTS["kb_enabled"])) != on:
        data["kb_enabled"] = on
        _save_models_data(data)


def get_kb_inject() -> bool:
    """自动注入开关（提问自动带检索上下文）。"""
    return bool(get_kb_config()["kb_inject"])


def set_kb_inject(on: bool):
    data = _load_models_data()
    on = bool(on)
    if bool(data.get("kb_inject", _KB_DEFAULTS["kb_inject"])) != on:
        data["kb_inject"] = on
        _save_models_data(data)


def get_kb_auto() -> bool:
    """自动增量开关（检索前增量刷新，节流 60s）。"""
    return bool(get_kb_config()["kb_auto"])


def set_kb_auto(on: bool):
    data = _load_models_data()
    on = bool(on)
    if bool(data.get("kb_auto", _KB_DEFAULTS["kb_auto"])) != on:
        data["kb_auto"] = on
        _save_models_data(data)


def get_kb_top_k() -> int:
    """默认检索片段数（1..20）。"""
    return int(get_kb_config()["kb_top_k"])


def set_kb_top_k(n: int):
    data = _load_models_data()
    n = max(1, min(20, int(n)))
    if int(data.get("kb_top_k", _KB_DEFAULTS["kb_top_k"])) != n:
        data["kb_top_k"] = n
        _save_models_data(data)


def get_kb_embedding() -> str:
    """embedding 模型 key；空 = 纯 TF-IDF。"""
    return get_kb_config()["kb_embedding"]


def set_kb_embedding(key: str):
    key = (key or "").strip()
    data = _load_models_data()
    if str(data.get("kb_embedding", _KB_DEFAULTS["kb_embedding"])).strip() != key:
        data["kb_embedding"] = key
        _save_models_data(data)


def _load_models_data() -> dict:
    _ensure_models_file()
    try:
        with open(_MODELS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = _DEFAULT_MODELS
    return data


def _save_models_data(data: dict):
    with open(_MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_custom_model(model_ids, base_url: str, api_key: str,
                     display_names=None, vision: bool = False,
                     reasoning_effort: str = "") -> list:
    """批量添加自定义模型（同一端点下可挂多个模型 ID）。

    model_ids: 模型 ID 列表，如 ["deepseek-v4-flash", "deepseek-v4-pro"]
    vision: True 则这批模型标记为识图模型（models.json 写 "vision": true）
    reasoning_effort: 推理等级（写 "reasoning_effort"，如 low/medium/high；空=不写）
    返回新添加（或已存在）的 ModelConfig 列表。
    """
    data = _load_models_data()
    if not api_key:
        api_key = "local-noauth"
    display_names = display_names or []

    pid = "custom"
    provider = next((p for p in data.get("providers", []) if p.get("id") == pid), None)
    if provider is None:
        provider = {"id": pid, "name": "自定义", "base_url": base_url,
                    "api_key": api_key, "models": []}
        data.setdefault("providers", []).append(provider)
    else:
        # 已有 custom provider：端点和 key 以最近一次填写为准
        provider["base_url"] = base_url
        provider["api_key"] = api_key

    added = []
    for i, model_id in enumerate(model_ids):
        model_id = model_id.strip()
        if not model_id:
            continue
        display_name = model_id
        if i < len(display_names) and display_names[i].strip():
            display_name = display_names[i].strip()
        existing = [m for m in provider["models"] if m["id"] == model_id]
        if not existing:
            entry = {"id": model_id, "name": display_name}
            if vision:
                entry["vision"] = True
            if reasoning_effort:
                entry["reasoning_effort"] = reasoning_effort
            provider["models"].append(entry)
        elif vision:
            # 已存在的模型重新添加且勾了识图 → 补上标记
            existing[0]["vision"] = True
        elif reasoning_effort:
            existing[0]["reasoning_effort"] = reasoning_effort
        added.append(ModelConfig(
            key=f"{pid}/{model_id}",
            provider_name=provider.get("name", pid),
            model_id=model_id,
            display_name=display_name,
            base_url=base_url,
            api_key=api_key,
            vision=vision,
            reasoning_effort=reasoning_effort,
        ))

    _save_models_data(data)
    return added


def augment_provider_models(provider_id: str, model_ids: list,
                            vision: bool = False) -> int:
    """给指定 provider 追加尚不存在的模型 ID（端点动态探测用）。

    provider 不存在或 model_ids 为空时直接返回 0。新增模型 name 取 id，
    vision 按参数标记。返回实际新增的模型数。
    """
    ids = [m.strip() for m in (model_ids or []) if m and m.strip()]
    if not ids:
        return 0
    data = _load_models_data()
    provider = next((p for p in data.get("providers", [])
                     if p.get("id") == provider_id), None)
    if provider is None:
        return 0
    existing = {m.get("id") for m in provider.get("models", [])}
    added = 0
    for mid in ids:
        if mid in existing:
            continue
        entry = {"id": mid, "name": mid}
        if vision:
            entry["vision"] = True
        provider.setdefault("models", []).append(entry)
        existing.add(mid)
        added += 1
    if added:
        _save_models_data(data)
    return added


def remove_model(key: str) -> bool:
    """删除一个模型（格式 "provider_id/model_id"）。成功返回 True。

    - custom provider 下的模型删完后整个 provider 一并移除。
    - 若删除的是 default，default 重置为第一个可用模型。
    """
    data = _load_models_data()
    if "/" not in key:
        return False
    pid, mid = key.split("/", 1)
    removed = False
    for provider in data.get("providers", []):
        if provider.get("id") != pid:
            continue
        before = len(provider.get("models", []))
        provider["models"] = [m for m in provider.get("models", [])
                              if m.get("id") != mid]
        removed = len(provider["models"]) < before
        # custom provider 空了就删掉
        if removed and pid == "custom" and not provider["models"]:
            data["providers"] = [p for p in data["providers"] if p is not provider]
        break
    if not removed:
        return False
    # 修正 default
    if data.get("default") == key:
        first = None
        for p in data.get("providers", []):
            for m in p.get("models", []):
                first = f"{p['id']}/{m['id']}"
                break
            if first:
                break
        data["default"] = first or ""
    _save_models_data(data)
    return True


def update_model(key: str, base_url: str | None = None,
                 api_key: str | None = None, model_id: str | None = None,
                 display_name: str | None = None,
                 vision: bool | None = None,
                 reasoning_effort: str | None = None,
                 reasoning: bool | None = None):
    """修改一个已有模型（格式 "provider_id/model_id"）。

    可改：端点、密钥、模型 ID、显示名称、识图标记。返回更新后的
    ModelConfig，找不到返回 None。改 model_id 会同步更新 default 引用。
    vision 传 True/False 设置/取消识图；None = 不动。
    reasoning_effort 传字符串设置推理等级，传空串清掉；None = 不动。
    """
    data = _load_models_data()
    if "/" not in key:
        return None
    pid, mid = key.split("/", 1)
    for provider in data.get("providers", []):
        if provider.get("id") != pid:
            continue
        m = next((x for x in provider.get("models", []) if x.get("id") == mid), None)
        if m is None:
            return None
        if display_name and display_name.strip():
            m["name"] = display_name.strip()
        if model_id and model_id.strip() and model_id.strip() != mid:
            m["id"] = model_id.strip()
        # 端点/密钥为 provider 级配置
        if base_url and base_url.strip():
            provider["base_url"] = base_url.strip()
        if api_key and api_key.strip():
            provider["api_key"] = api_key.strip()
        if vision is not None:
            if vision:
                m["vision"] = True
            else:
                m.pop("vision", None)   # 取消勾选 = 清掉标记
        if reasoning is not None:
            if reasoning:
                m["reasoning"] = True
            else:
                m.pop("reasoning", None)   # 取消 = 不再支持等级选择
        if reasoning_effort is not None:
            if reasoning_effort:
                m["reasoning_effort"] = reasoning_effort
                m["reasoning"] = True      # 设过等级 = 一定支持
            else:
                m.pop("reasoning_effort", None)  # 留空 = 清掉推理等级
        new_key = f"{pid}/{m['id']}"
        if data.get("default") == key:
            data["default"] = new_key
        _save_models_data(data)
        return ModelConfig(
            key=new_key,
            provider_name=provider.get("name", pid),
            model_id=m["id"],
            display_name=m.get("name", m["id"]),
            base_url=provider.get("base_url", ""),
            api_key=provider.get("api_key", ""),
            vision=bool(m.get("vision", False)),
            reasoning=bool(m.get("reasoning") or m.get("reasoning_effort")),
            reasoning_effort=str(m.get("reasoning_effort", "") or ""),
            reasoning_choices=reasoning_choices_for(pid, provider.get("name", pid), m),
        )
    return None


# ================= MCP 服务器配置 =================

def load_mcp_servers() -> dict:
    """读取 mcp.json：{"servers": {名称: {command, args, env, enabled}}}。

    文件不存在或损坏时返回空配置（不抛异常，界面可自行新建）。
    """
    try:
        with open(MCP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("servers"), dict):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {"servers": {}}


def save_mcp_servers(data: dict):
    """保存 mcp.json。"""
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    with open(MCP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
