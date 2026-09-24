# -*- coding: utf-8 -*-
"""短剧成片：分镜 JSON → 角色形象资产 → 关键帧（多图合成）→ 图生视频 → ffmpeg 合成。

一致性三段传导（与 Pavo 同思路，详见 /novel drama video）：
1. 角色基础形象：详细外貌锚 + 统一风格，每角色一次，全剧复用；
2. 镜头关键帧：分镜描述 + 出场角色形象图作参考图多图合成（长相由参考图锁定）；
3. 镜头视频：关键帧作首帧图生视频（画面继承关键帧，不再漂移）。

产物全部落 novels/<书名>/ 下，按「文件已存在即跳过」断点续造：
短剧资产/<角色>.png + cast.json ｜ 短剧分镜/第N章.json + urls.json
短剧关键帧/N-01.png ｜ 短剧片段/N-01.mp4 ｜ 短剧成片/第N章-<标题>.mp4
"""

from __future__ import annotations

import json
import os
import drama_body_guard as _dbg
import re
import shutil
import subprocess

import imggen
import videogen

try:
    from PIL import Image            # 上传替换资产图用；缺失时该功能降级
except Exception:                    # noqa: BLE001
    Image = None

DEFAULT_STYLE = ("high-quality 3D CG animation still, modern game-engine cinematic "
                    "render, Unreal Engine and Pixar grade quality, semi-realistic "
                    "stylized characters with refined facial features, clean "
                    "sculpted anatomy, detailed skin shader with subtle subsurface "
                    "scattering, PBR materials with crisp detailed textures, "
                    "volumetric cinematic lighting with soft rim light, rich depth "
                    "of field, polished film color grading, detailed environment "
                    "art, sharp focus, consistent character design across shots, "
                    "avoid flat lighting, avoid plastic waxy skin, avoid low-poly "
                    "blurry look, avoid 2D flat cel shading, avoid anime line art")

# 内容审核触发的特殊异常：UI 顶栏接住后可提示「切模型重试」
class DramaModerationError(Exception):
    """视频生成因内容审核被拒——{hint, original_err, provider_id, model}。"""

    def __init__(self, message: str, *, hint: str = "", original_err: str = "",
                 provider_id: str = "", model: str = ""):
        super().__init__(message)
        self.hint = hint
        self.original_err = original_err
        self.provider_id = provider_id
        self.model = model


# ---------------- Agent 注册（借鉴 huobao 4 具名 agent） ----------------
# 4 个具名 agent 中，drama workshop 后 3 个住在这里：
# - extractor           资产生成（角色/场景/道具）
# - storyboard_breaker  分镜生成（含结构化字段 + 火宝规范 video_prompt）
# - prompt_generator    提示词生成（图/视频提示词模板与函数）
# 第一个 script_rewriter 在 novel_chain.AGENT_REGISTRY。
# 注册表只存元数据（display_name / description / 引用函数名）——运行时通过
# get_agent() 解析，避免定义顺序耦合。

AGENT_REGISTRY = {
    "extractor": {
        "display_name": "Extractor（资产抽取）",
        "description": "从剧本文本抽取全书级资产（人物/场景/道具），"
                        "分类型出视觉描述锚 + 中国面孔默认锚",
        "function_name": "build_cast",
        "system_prompts_name": "_SECTION_SYS",
        "asset_template_name": "_ASSET_TPL",
        "cache_markers": ("_done_角色", "_done_场景", "_done_道具"),
    },
    "storyboard_breaker": {
        "display_name": "Storyboard Breaker（拆分镜）",
        "description": "把一章改编为结构化分镜 JSON（标题/场景/角色/道具/时长/"
                        "运镜/情绪/旁白/台词），并二次生成按时间分段的 video_prompt",
        "function_name": "build_shots",
        "video_prompt_fn_name": "_video_prompts",
    },
    "prompt_generator": {
        "display_name": "Prompt Generator（图/视频提示词）",
        "description": "为资产生成基础形象提示词（含画幅 + 中国面孔默认锚）；"
                        "为分镜生成按 3 秒分段的 video_prompt（参考 huobao 火宝规范）",
        "asset_template_name": "_ASSET_TPL",
        "video_prompt_fn_name": "_video_prompts",
    },
}


def list_agents() -> list:
    """枚举 drama workshop 的注册 agent（[{name, display_name, description}]）。"""
    return [{"name": k, "display_name": v.get("display_name", k),
             "description": v.get("description", "")}
            for k, v in AGENT_REGISTRY.items()]


def get_agent(name: str) -> dict | None:
    """按名取 agent 注册项（function 等字段懒解析）。

    返回 dict 包含 name / display_name / description / function / ...；未注册返回 None。
    """
    entry = AGENT_REGISTRY.get(name)
    if not entry:
        return None
    out = {"name": name, **{k: v for k, v in entry.items()
                            if not k.endswith("_name")}}
    for src_key, dst_key in (("function_name", "function"),
                              ("system_prompts_name", "system_prompts"),
                              ("asset_template_name", "asset_template"),
                              ("video_prompt_fn_name", "video_prompt_fn")):
        n = entry.get(src_key)
        if n and dst_key not in out:
            out[dst_key] = globals().get(n)
    return out


def resolve_style(state: dict) -> str:
    """风格回退链：state['drama_style'] → 全局默认 → DEFAULT_STYLE，永不空。"""
    v = (state or {}).get("drama_style")
    if v and isinstance(v, str) and v.strip():
        return v.strip()
    try:
        import json, os
        path = (getattr(__import__("config"), "_MODELS_FILE", None) or
                os.path.join(os.environ.get("APPDATA", "")
                             if os.name == "nt" else os.path.expanduser("~"),
                             "local-ai-studio", "models.json"))
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        v = (data.get("globals") or {}).get("default_drama_style")
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    except Exception:                  # noqa: BLE001
        pass
    return DEFAULT_STYLE


def resolve_comic_style(state: dict) -> str:
    """漫画画风回退链：state['comic_style']（空=跟随 drama_style）→ drama_style。

    漫画线独立画风：state.comic_style 为空字符串则跟随项目视觉风格；非空
    则覆盖。这是 v2.1 新增字段，老 book 在加载时会被 ensure_style_fields()
    兜底初始化为 ''。
    """
    v = (state or {}).get("comic_style")
    if v is None:
        return resolve_style(state)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return resolve_style(state)


def inject_style(state: dict, prompt: str) -> str:
    """v2.1：单点风格注入。所有资产/视频/漫画 prompt 都走这条路径前缀注入
    视觉风格词，禁止 agent prompt 模板自己写风格词（防风格词打架）。

    使用例：
        prompt = inject_style(state, f"{sec}基础形象：" + tpl.format(a=ap))
    """
    s = (prompt or "").strip()
    return f"{resolve_style(state)}。{s}" if s else resolve_style(state)


def inject_comic_style(state: dict, prompt: str) -> str:
    """v2.1：漫画线单点风格注入。comic_style 为空时回退 drama_style。"""
    s = (prompt or "").strip()
    return f"{resolve_comic_style(state)}。{s}" if s else resolve_comic_style(state)


def ensure_style_fields(state: dict) -> None:
    """加载/新建流水线时兜底：缺 drama_style / comic_style 就补成有效值。

    drama_style：回退链结果（落到 state）；下次用户改风格时直接覆写。
    comic_style：空字符串（= 跟随 drama_style）；改成具体画风时也是覆写。
    老 book 第一次打开工作台会自动跑一次。
    """
    if not state.get("drama_style"):
        state["drama_style"] = resolve_style(state)
    if "comic_style" not in state:
        state["comic_style"] = ""        # 默认跟随项目视觉风格


# 风格库（参考 Pavo 写法：风格=一段视觉质感公式——渲染质感+线条上色+
# 色调光线+镜头语言——注入每个分镜/资产提示词，而非光杆标签）
STYLE_LIB = (
    # ---- 视觉风格预设（v2.x 替换：8 个色彩饱和、含明确的"避免"项的英文提示词）----
    # 每个预设包含 (name, key, text) 三元；text 为英文提示词片段，会被 inject_style
    # 自动前置到资产/分镜/漫画 prompt 的最前面，作为视觉风格锚点。
    # category 用于 UI 分组（2D / 3D / 真人 / 内置），不参与生成逻辑。
    {"name": "3D 漫剧", "category": "3D", "text":
        "high-quality 3D CG animation still, modern game-engine cinematic render, "
        "Unreal Engine and Pixar grade quality, semi-realistic stylized characters "
        "with refined facial features, clean sculpted anatomy, detailed skin shader "
        "with subtle subsurface scattering, PBR materials with crisp detailed textures, "
        "volumetric cinematic lighting with soft rim light, rich depth of field, "
        "polished film color grading, detailed environment art, sharp focus, "
        "consistent character design across shots, avoid flat lighting, "
        "avoid plastic waxy skin, avoid low-poly blurry look, avoid 2D flat cel shading, "
        "avoid anime line art"},

    {"name": "日漫赛璐璐", "category": "2D", "text":
        "Japanese TV anime style, clean cel shading with hard-edged shadow shapes, "
        "crisp uniform black line art, vivid saturated color palette, expressive "
        "large-eyed character design with on-model proportions, detailed hand-painted "
        "anime backgrounds, dramatic anime key lighting with screentone highlights, "
        "key-visual poster quality, consistent character design across shots, "
        "avoid 3D CGI look, avoid painterly soft blending, avoid watercolor texture, "
        "avoid photorealism, avoid thick western comic outlines"},

    {"name": "吉卜力手绘", "category": "2D", "text":
        "Studio Ghibli hand-drawn animation style, soft painterly brushwork with "
        "organic hand-crafted line quality, lush warm watercolor painted backgrounds, "
        "gentle natural daylight with nostalgic warm glow, muted earthy natural color "
        "palette, whimsical cozy storybook atmosphere, subtle film-grain softness, "
        "theatrical background art quality, consistent character design across shots, "
        "avoid hard cel shading, avoid 3D render look, avoid neon over-saturated colors, "
        "avoid sharp digital edges, avoid photorealism"},

    {"name": "水彩绘本", "category": "2D", "text":
        "delicate watercolor storybook illustration, soft translucent color washes, "
        "visible cold-press paper texture, fluid hand-painted brushstrokes with "
        "gentle pigment bleeds, light airy atmosphere, harmonious pastel palette, "
        "whimsical children book charm, loose expressive edges, consistent character "
        "design across shots, avoid bold black outlines, avoid digital airbrush look, "
        "avoid harsh contrast, avoid 3D rendering, avoid photorealism"},

    {"name": "美式漫画", "category": "2D", "text":
        "Western graphic-novel comic book style, bold confident black ink outlines, "
        "halftone dot shading and screentone gradients, dynamic saturated colors with "
        "dramatic contrast, dramatic spotlight lighting, flat graphic print look, "
        "sharp inking details, dynamic cinematic composition, consistent character "
        "design across shots, avoid painterly soft blending, avoid watercolor washes, "
        "avoid photorealistic rendering, avoid 3D CGI look, avoid anime cel shading"},

    # ---- 原始风格（v2.x 补：从老 STYKE_LIB / README / AGENTS 推断，name 统一 2-3 字）----
    # text 风格：与新预设同构——一段英文质感描述 + "consistent character design
    # across shots" 锚点 + "avoid ..." 反例列表。inject_style 单点注入。

    {"name": "国漫", "category": "2D", "text":
        "modern Chinese donghua 2D animation style, clean confident line work with "
        "elegant flowing curves, vivid saturated color palette, tall stylized "
        "character proportions, dynamic dramatic key poses, layered ink-wash inspired "
        "atmospheric backgrounds, commercial donghua series poster quality, "
        "consistent character design across shots, avoid 3D CGI look, avoid "
        "watercolor soft blending, avoid western comic thick outlines, avoid "
        "photorealism, avoid monochrome flat shading"},



    {"name": "水墨", "category": "2D", "text":
        "Chinese ink-wash animation style, soft brushy textures with mineral pigment "
        "bleeds on rice-paper texture, monochrome indigo-and-ochre palette with sparing "
        "warm accent, asymmetric compositional balance with white-space breathing "
        "room, subtle paper-grain softness, traditional donghua wuxia mood quality, "
        "consistent character design across shots, avoid flat cel shading, avoid "
        "3D CGI render, avoid digital airbrush look, avoid neon over-saturated colors, "
        "avoid photorealism, avoid western comic thick outlines"},

    {"name": "剪纸", "category": "2D", "text":
        "Chinese paper-cutting folk-art style, red symmetrical silhouettes with "
        "intricate saw-tooth paper-cut edge patterns, layered lattice negative-space "
        "carvings, decorative folk-new-year flat-color palette, theatrical planar "
        "composition, folk-cultural poster quality, consistent character design "
        "across shots, avoid gradient shading, avoid 3D CGI render, avoid photorealism, "
        "avoid watercolor texture, avoid thin delicate line work, avoid muted modern "
        "color palette"},

    {"name": "皮影", "category": "2D", "text":
        "Chinese shadow-puppet piying theater style, semi-translucent donkey-skin "
        "texture with jointed articulated character silhouettes, warm amber "
        "backlight transmission glow, intricate carved openwork filigree patterns, "
        "flat theatrical stage composition with screen-projection look, dramatic "
        "puppet-poster quality, consistent character design across shots, avoid "
        "photorealism, avoid 3D CGI render, avoid anime line art, avoid watercolor "
        "texture, avoid photorealistic human skin rendering"},



    {"name": "像素", "category": "2D", "text":
        "16-bit retro pixel art style, crisp chunky pixel grids with hard limited "
        "palette, sharp aliased edges, low-resolution sprite aesthetic, nostalgic "
        "game-console key art quality, clean readable pixel silhouettes, consistent "
        "character design across shots, avoid smooth gradient shading, avoid 3D CGI "
        "render, avoid photorealism, avoid watercolor soft blending, avoid "
        "high-resolution vector clean shapes, avoid anime line art"},

    {"name": "粘土", "category": "3D", "text":
        "stop-motion claymation style, fingerprint-imprinted matte clay surface with "
        "visible hand-crafted texture, soft diffused practical lighting, "
        "miniature-diorama staging with subtle DOF, Aardman whimsical feel, "
        "exaggerated character proportions, consistent character design across shots, "
        "avoid photorealism, avoid anime line art, avoid watercolor blending, avoid "
        "smooth plastic 3D render, avoid sharp digital edges, avoid high-key "
        "commercial lighting"},



    {"name": "皮克斯", "category": "3D", "text":
        "Pixar feature animation 3D style, refined subsurface-scattering skin with "
        "soft cinematic global illumination, polished color script with warm amber "
        "key and cool blue fill, emotionally-driven character performance, "
        "physically-based materials with photoreal tactile texture, consistent "
        "character design across shots, avoid flat cel shading, avoid anime line "
        "art, avoid watercolor texture, avoid dark moody palette, avoid stylized "
        "chibi proportions, avoid hyperrealistic VFX look"},

    {"name": "港片", "category": "真人", "text":
        "Hong Kong retro cinema noir aesthetic, neon-lit rainy nighttime streets with "
        "amber-and-teal split color grading, handheld breathing camera work, "
        "warm tungsten street lamps and wet reflections, classic golden-era HK "
        "cinema mood, consistent character design across shots, avoid 3D CGI look, "
        "avoid anime cel shading, avoid bright daylight palette, avoid pastel "
        "soft tones, avoid digital clean sharp edges, avoid photorealistic VFX "
        "bombast"},

    {"name": "是枝", "category": "真人", "text":
        "Japanese Koreeda-style naturalistic realism, soft window-lit family "
        "interiors, restrained low-saturation muted earthy palette, fixed-camera "
        "observational framing, subtle contemplative emotional understatement, "
        "gentle domestic everyday-life texture, consistent character design "
        "across shots, avoid 3D CGI look, avoid anime cel shading, avoid neon "
        "high-saturation colors, avoid dramatic chiaroscuro, avoid Hollywood VFX "
        "bombast, avoid fantasy costume drama"},

    {"name": "国风 2.5D", "category": "3D", "text":
        "Chinese guofeng 2.5D illustration style, semi-realistic donghua-quality "
        "character art, elegant flowing line work, rich traditional Chinese aesthetic "
        "elements, layered ink-wash inspired atmospheric backgrounds, refined silk "
        "and fabric textures, soft luminous lighting with gentle haze, sophisticated "
        "muted jewel-tone palette, xianxia drama poster quality, consistent character "
        "design across shots, avoid flat cel shading, avoid western comic ink style, "
        "avoid photorealism, avoid plastic 3D look, avoid modern clothing and props "
        "unless specified"},

    {"name": "韩系网漫", "category": "2D", "text":
        "Korean webtoon manhwa style, clean digital painting with soft gradient shading, "
        "slim elegant character proportions, large expressive eyes with detailed "
        "highlights, soft glowing skin rendering, romantic dreamy lighting, modern "
        "pastel-to-vivid color palette, detailed fashion and fabric rendering, "
        "webtoon key visual quality, consistent character design across shots, "
        "avoid heavy black ink outlines, avoid halftone dots, avoid 3D render look, "
        "avoid watercolor paper texture, avoid chibi proportions"},

    {"name": "黑白漫画", "category": "2D", "text":
        "black and white manga illustration, high-contrast monochrome ink work, "
        "dynamic hatching and cross-hatching shading, bold solid blacks with dramatic "
        "negative space, screentone gray gradation, expressive confident ink linework, "
        "cinematic noir lighting, professional manga page quality, consistent "
        "character design across shots, strictly no color, avoid grayscale blur "
        "smudging, avoid painterly soft edges, avoid photorealism, avoid 3D render look"},
)

# 兼容旧引用：只剩纯文本清单
STYLE_PRESETS = tuple(s["text"] for s in STYLE_LIB)


def _preset_lib() -> list:
    """风格库结构副本（name/text/category）。"""
    return [dict(s) for s in STYLE_LIB]


def load_style_lib() -> tuple:
    """读 models.json 风格库：没有就播种全部预设并写回。

    返回 (styles 列表, 默认风格, data, path)；path 为 None 表示无法
    持久化（此时返回内存副本，功能可用但不跨会话）。
    """
    import config
    path = getattr(config, "_MODELS_FILE", None)
    data = {}
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:                  # noqa: BLE001
            data = {}
    glb = data.setdefault("globals", {})
    if not glb.get("drama_styles"):
        glb["drama_styles"] = _preset_lib()
        if path:
            try:
                _save_style_lib(data, path)
            except Exception:              # noqa: BLE001
                pass
    glb.setdefault("default_drama_style", DEFAULT_STYLE)
    return glb["drama_styles"], glb["default_drama_style"], data, path


def _save_style_lib(data: dict, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_style_lib(data: dict, path: str) -> None:
    if path:
        _save_style_lib(data, path)
_ASSET_DIR = "短剧资产"                   # 根目录；其下分全书/ 与 第N章/
_ASSET_GLOBAL = "全书"                    # 全书（长期）资产子目录
def _chapter_asset_subdir(ch) -> str:     # 章节专属（暂时）子目录
    return f"第{ch}章"
_SHOT_DIR = "短剧分镜"
_SCRIPT_DIR = "短剧剧本"
_FRAME_DIR = "短剧关键帧"
_CLIP_DIR = "短剧片段"
_OUT_DIR = "短剧成片"
_MIN_SEC, _MAX_SEC = 4, 15          # Agnes 上限 441 帧@24fps≈18s，留余量


def _book_dir(state: dict) -> str:
    import novel_chain
    return novel_chain._book_dir(state)


_SCREENPLAY_DIR = "短剧剧本"                # 工作台账词改写出的拍摄剧本（优先于小说原文）


def _screenplay_path(state: dict, ch) -> str:
    return os.path.join(_book_dir(state), _SCREENPLAY_DIR, f"第{ch}章-剧本.md")


def _chapter_source_text(state: dict, chapter: dict) -> str:
    """分镜/资产的输入文本：拍摄剧本（短剧剧本/第N章-剧本.md）优先。

    文件存在即覆盖小说原文——工作台「AI 改写→存为拍摄剧本」的产物由此
    进入生产链；删掉该文件即回退原文。「文件存在即缓存」同哲学。
    空文件不算数 → 回退原文，避免空白剧本误删全部 cache。
    """
    p = _screenplay_path(state, chapter.get("idx"))
    if p and os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                t = f.read().strip()
            if t:
                return t
        except OSError:
            pass
    return chapter.get("text") or ""


def _ask(state: dict, system: str, user: str) -> str:
    """v2.1：在 system 提示前自动前缀注入项目视觉风格（单点注入）。

    所有上层调用点（build_cast / build_shots / 资产生成）一律走 _ask()，
    无需再各自手动 f"{style}..."——这套机制保证「风格词单点注入」。
    """
    import novel_chain
    full_system = inject_style(state, system)
    return novel_chain._ask(state, full_system, user)


def _stop(msg: str):
    import novel_chain
    return novel_chain.StageStopError(msg)


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "", str(name or ""))[:24] or "角色"


def _drama_sizes() -> tuple:
    """读 /media 面板的短剧/漫画尺寸配置。

    返回 (图像档位, 短剧比例, 视频尺寸, 漫画档位, 漫画比例)；
    未配置的键回落内置默认（1K / 9:16 / 空=服务端默认 / 1K / 2:3）。
    """
    try:
        import config
        d = config.get_drama()
    except Exception:                  # noqa: BLE001  配置不可用走默认
        d = {}
    return (d.get("image_size") or "1K",
            d.get("image_ratio") or "9:16",
            d.get("video_size") or "",
            d.get("comic_size") or "1K",
            d.get("comic_ratio") or "2:3")


def _anchored_appearance(ap: str) -> str:
    """面孔锚：默认补「中国人面孔（东亚）」，防模型默认出西方面孔。

    通用规则（非针对某本书）：中文网文角色绝大多数为华人；描述已写明
    人种/面孔特征（无论中外）时不重复添加，尊重原文设定。
    """
    t = str(ap or "")
    if re.search(r"西方|欧美|白人|金发|碧眼|高鼻|深目|外国人|美国|欧洲|俄国"
                 r"|混合血统|混血", t):
        return t
    if re.search(r"中国人|华人|华裔|东亚|东方面孔|国字脸|鹅蛋脸|瓜子脸"
                 r"|亚洲面孔|面孔|长相", t):
        return t
    return (t + "，" if t else "") + "中国人面孔（东亚）"


def _json_load(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                  # noqa: BLE001
        return default


def _json_dump(path: str, data) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _extract_json(text: str):
    """从 LLM 回复中剥出 JSON（容忍 ```json 围栏与前后说明文字）。"""
    t = re.sub(r"```(?:json)?", "", text or "").strip()
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        i, j = t.find(open_ch), t.rfind(close_ch)
        if 0 <= i < j:
            try:
                return json.loads(t[i:j + 1])
            except json.JSONDecodeError:
                continue
    return None


# ---------------- 1. 资产库（角色 / 场景 / 道具） ----------------

_ASSET_SECTIONS = ("角色", "场景", "道具")

# 各类资产的基础形象提示词与画幅：角色立绘 / 场景空镜 / 道具特写
_ASSET_TPL = {
    # 角色参考指令包角色档案标准：正面站立全身、白底、头身比、从头到脚
    "角色": ("{a}。角色设定图：正面站立全身像，头到脚完整无裁切，自然直立"
             "站姿无动作，纯白色背景无杂物；头身比例标准，五官清晰，"
             "从发型到鞋袜的完整穿搭；气质与职业身份相符（服饰配件按描述，"
             "不要脑补成其它职业）。", "3:4"),
    # 场景参考指令包场景设计标准：无人纯场景 + 环境/时间/氛围/视觉特征
    "场景": ("{a}。无人纯场景空镜，画面中不能出现任何人物；环境类型、"
             "时间时段光线状态、空间氛围、材质与标志性陈设缺一可辨，"
             "前中后景层次清晰，光线统一。", "16:9"),
    "道具": ("{a}。道具特写，纯色背景，道具居中，材质细节清晰。", "1:1"),
}

_SECTION_SYS = {
    "角色": ("你是选角导演。从角色设定与章节文本中提取每个「人物」（主角+配角）"
             "的外貌锚。方法：①先确定该人物在原文中的职业/身份/阶层——角色设定"
             "写了就直接用，没写就从其言行、技能、所处场景推断；②把这个职业/"
             "身份翻译成可见视觉特征：服饰款式与档次、职业配件（眼镜/工具/"
             "武器/包袋/饰物）、肤质（日晒/白净/精致/粗糙）、体态（挺拔/佝偻/"
             "健壮/单薄）——四者都要与该职业一致，禁止套用与原文身份不符的"
             "形象；③若人物跨时代/阶段出现（以原文为准，阶段名自定，如 现代/"
             "古代/校园/仙侠/童年/老年），必须按阶段分别描述服装外貌，"
             "不能混。输出：每阶段 30-60 字确定性描述（性别年龄感、面孔人种"
             "与脸型——中文网文角色默认中国人东亚面孔，除非原文明确是"
             "外国人、发型、体型、该阶段的职业化服装与标志配件）。"
             '只输出 JSON：{"人物名": {"阶段名": "外貌服装描述", ...}, ...}'
             "（单阶段人物也用单键字典，如 {\"现代\": \"…\"}）；"
             "只要人物，不要场景/道具。"),
    "场景": ("你是美术指导。从世界观与章节文本中提取**在多个章节反复出现的"
             "核心场景/空间**（全书级长期资产，如主角家、公司、常去的街道）——"
             "只挑反复出现的，某章独有的场景不用列。每个给 30-60 字确定性视觉"
             "描述：空间结构、陈设家具、材质色调、光线氛围。"
             '只输出 JSON：{"场景名": "视觉描述", ...}，4-8 个。'),
    "道具": ("你是道具师。从章节文本中提取**贯穿多章剧情的关键道具**（全书级"
             "长期资产，如信物、手机、反复出现的工具）——只挑反复推动剧情的，"
             "某章用过即弃的不列。每个给 20-50 字外观描述：形状、材质、颜色、"
             "新旧程度。"
             '只输出 JSON：{"道具名": "外观描述", ...}，2-6 个，'
             "不要把场景/人物算进来。"),
}


def _migrate_flat_cast(cast: dict) -> dict:
    """旧版扁平 cast.json（只有角色，无 type）迁移为三类结构。"""
    if not cast or any(isinstance(v, dict) and v.get("type")
                       for k, v in cast.items() if not k.startswith("_")):
        return cast
    out = {k: {**v, "type": "角色"} if isinstance(v, dict) else v
           for k, v in cast.items()}
    out["_done_角色"] = True            # 旧角色锚已提取过，不重问
    return out


def find_asset(state: dict, name: str):
    """按名字找资产：先全书 cast，再各章 assets.json。

    精确未命中时做包含式模糊匹配（如「大前门香烟」→「香烟」），
    唯一命中才采用，多个/零个候选抛错并列出名字。
    返回 (info, store_path)；找不到返回 None。聊天改图覆盖原图用。
    """
    key = (name or "").strip()
    if not key:
        return None
    import glob as _glob
    stores = [(_global_cast_path(state),
               _json_load(_global_cast_path(state), {}))]
    for p in sorted(_glob.glob(os.path.join(
            _book_dir(state), _ASSET_DIR, "第*章", "assets.json"))):
        stores.append((p, _json_load(p, {})))
    exact, partial = [], []
    for sp, store in stores:
        for k, info in store.items():
            if k.startswith("_") or not isinstance(info, dict):
                continue
            if k == key:
                exact.append((info, sp))
            elif len(key) >= 2 and (key in k or k in key):
                partial.append((k, info, sp))
    if exact:
        return exact[0]
    names = sorted({k for k, _i, _sp in partial})
    if len(names) == 1:
        k = names[0]
        for sp, store in stores:
            if isinstance(store.get(k), dict):
                return store[k], sp
        return None
    if len(names) > 1:
        raise _stop(f"「{key}」模糊匹配到多个资产：{'、'.join(names)}"
                    "——请说明是哪一个")
    return None


def edit_asset(state: dict, name: str, instruction: str) -> str:
    """按指令编辑已有资产并覆盖原图（图生图：原图为参考 + 修改指令）。

    供聊天 image_gen 工具的 asset_name 参数调用；返回新图路径。
    """
    found = find_asset(state, name)
    if not found:
        raise _stop(f"资产库中找不到「{name}」")
    info, store_path = found
    has_original = bool(info.get("path") and os.path.exists(info["path"]))
    new_info = gen_asset(state, name, dict(info), custom_prompt=instruction,
                         image_ref=has_original)
    info["path"], info["url"] = new_info.get("path"), new_info.get("url")
    store = _json_load(store_path, {})
    store[name] = info
    _json_dump(store_path, store)
    return info["path"]


def build_cast(state: dict, on_event=None, stop=None, redo: bool = False) -> dict:
    """资产库：提取 角色 / 场景 / 道具 三类基础形象并生成参考图。

    cast.json 结构：{名: {"type","appearance","path","url"}} + "_done_<类>"
    进度位；已生成图直接复用（断点续造）。三类分开提取、分开出图：
    角色 3:4 立绘、场景 16:9 空镜、道具 1:1 特写。
    """
    on_event = on_event or (lambda e: None)
    cast_path = _global_cast_path(state)
    cast = _migrate_flat_cast(_json_load(cast_path, {}))
    # 路径迁移：旧 png 在 短剧资产/ 顶层而非 全书/ 子目录 → 当作缺图重生成
    global_subdir = os.path.join(os.path.dirname(cast_path), "")   # 末尾带 / 检查
    for k, v in list(cast.items()):
        if k.startswith("_") or not isinstance(v, dict):
            continue
        p = v.get("path") or ""
        if p and (not p.startswith(global_subdir)
                 or not os.path.exists(p)):
            v["path"] = ""               # 触发下方补出图
    chars_md = (state.get("characters") or "").strip()
    world_md = (state.get("world") or "").strip()
    chapters_txt = "\n".join((c.get("text") or "")
                             for c in state.get("chapters", []))[:6000]
    if not chars_md and not cast:
        raise _stop("还没有角色设定（先跑完「角色」阶段，或 /novel start 新书）")
    for sec in _ASSET_SECTIONS:
        if cast.get(f"_done_{sec}"):
            continue
        if sec == "角色":
            src = (f"世界观：\n{world_md}\n\n角色设定：\n{chars_md}"
                    if world_md else
                    f"角色设定：\n{chars_md}")
        elif sec == "场景":
            src = f"世界观：\n{world_md}\n\n章节文本：\n{chapters_txt}"
        else:
            src = f"章节文本：\n{chapters_txt}"
        text = _ask(state, _SECTION_SYS[sec], src + "\n请输出 JSON。")
        data = _extract_json(text)
        if isinstance(data, dict) and data:
            for k, v in data.items():
                k = str(k).strip()
                if not k or k.startswith("_"):
                    continue
                old = cast.get(k) or {}
                looks = {}
                if isinstance(v, dict) and v:
                    # 多阶段形象：{"现代": "…", "古装": "…"}
                    for era, desc in v.items():
                        era = str(era).strip()
                        if era and str(desc).strip():
                            looks[era] = {"appearance": str(desc).strip()}
                    appearance = (next(iter(looks.values()))
                                  ["appearance"] if looks else "")
                else:
                    appearance = str(v).strip()
                entry = {"type": sec, "appearance": appearance,
                         **{kk: vv for kk, vv in old.items()
                            if kk in ("path", "url", "looks")}}
                if sec == "角色":
                    old_looks = (old.get("looks") or {}) if isinstance(old, dict) else {}
                    for era, lk in looks.items():
                        merged = {**lk, **{kk2: vv2 for kk2, vv2
                                           in (old_looks.get(era) or {}).items()
                                           if kk2 in ("path", "url")}}
                        looks[era] = merged
                    if looks:
                        entry["looks"] = looks
                cast[k] = entry
            cast[f"_done_{sec}"] = True
            _json_dump(cast_path, cast)
    for name, info in list(cast.items()):
        if name.startswith("_") or not isinstance(info, dict):
            continue
        looks = info.get("looks") or {}
        looks_todo = ([lk for lk in looks.values()]
                      if redo else
                      [lk for lk in looks.values() if not lk.get("path")])
        if info.get("path") and not looks_todo and not redo:
            continue                      # 主图+各阶段图齐全
        if stop is not None and stop.is_set():
            raise _stop("已手动停止：已生成的形象保留，重跑命令自动续造")
        sec = info.get("type") or "角色"
        tpl, ratio = _ASSET_TPL.get(sec, _ASSET_TPL["角色"])
        _, out = _resolve_asset_path(state, name, info)   # 全书/目录
        if not info.get("path") or redo:                  # redo=覆盖原图
            on_event({"type": "drama_media", "kind": "cast",
                      "label": f"{name}（{sec}）"})
            path, url = imggen.generate_ex(
                # v2.1 单点风格注入（保留远程新增的 _drama_sizes() 尺寸解析）
                inject_style(state, f"{sec}基础形象：" +
                             tpl.format(a=_anchored_appearance(
                                 info.get("appearance", "")))),
                out, size=_drama_sizes()[0], ratio=ratio)
            info["path"], info["url"] = path, url
            _json_dump(cast_path, cast)
        # 角色多阶段形象（现代/古装…）：逐套补图；默认套复用主图。
        # 脸部一致性：后续每套都以默认套主图为参考图做图生图——脸由图像
        # 锁定，只换该阶段的服装发型，避免文字约束下的「同人多脸」。
        first_era = next(iter(looks), "")
        for era, lk in looks.items():
            if era == first_era:
                lk.setdefault("path", info.get("path"))
                lk.setdefault("url", info.get("url"))
                continue
            if lk.get("path"):
                continue
            lk_out = out.replace(".png", f"-{_safe_name(era)}.png")
            on_event({"type": "drama_media", "kind": "cast",
                      "label": f"{name}（{sec}·{era}）"})
            face_ref = info.get("path") or ""
            refs = [face_ref] if face_ref and os.path.exists(face_ref) else []
            try:
                lp, lu = imggen.generate_ex(
                    # v2.1 单点风格注入 + 远程新增的 _drama_sizes() 尺寸解析
                    inject_style(state, f"{sec}基础形象·{era}阶段：" +
                                 tpl.format(a=_anchored_appearance(
                                     lk.get("appearance", ""))) +
                                 ("。参考图是同一人物：严格保持参考图的脸型五官、发际线"
                                  "与体格不变，仅更换为本阶段的服装发型与配饰。"
                                  if refs else
                                  "。同一人物：保持脸型五官与体格特征与其它阶段一致，"
                                  "仅更换该阶段的服装发型。")),
                    lk_out, size=_drama_sizes()[0], ratio=ratio, image_refs=refs)
                lk["path"], lk["url"] = lp, lu
            except Exception as e:          # noqa: BLE001  单套失败不阻断
                on_event({"type": "drama_media", "kind": "debt",
                          "label": f"{name}·{era} 形象生成跳过：{e}"})
            _json_dump(cast_path, cast)
    return cast


def three_view(state: dict, name: str, info: dict, on_event=None) -> str:
    """角色三视图设定图：左 1/3 面部特写 + 右 2/3 正/侧/背全身（16:9 白底）。

    以定妆照为参考图锁脸（同一人），给后续关键帧多一个高一致性参考源；
    产物存 全书/{name}-三视图.png，存在即复用。
    """
    on_event = on_event or (lambda e: None)
    base = _global_base(state)
    out = os.path.join(base, f"{_safe_name(name)}-三视图.png")
    if os.path.exists(out):
        return out
    src = info.get("path") or ""
    if not src or not os.path.exists(src):
        raise _stop("先有该角色的形象图，才能生成三视图"
                    f"（{name} 还没有定妆照）")
    on_event({"type": "drama_media", "kind": "cast",
              "label": f"{name} 三视图"})
    imggen.generate_ex(
        # v2.1 单点风格注入 + 远程新增的 _drama_sizes() 尺寸解析
        inject_style(state, "角色三视图设定图：以参考图角色为同一人；16:9 版面，"
                     "左侧三分之一为该角色面部特写，右侧三分之二从左到右依次为"
                     "正面、侧面、背面全身立像；自然直立站姿无动作，纯白色背景，"
                     "人物比例与头身比严格一致，三个视图的服装发型配饰完全相同，"
                     "线条清晰流畅，视觉焦点集中在角色身上。"),
        out, size=_drama_sizes()[0], ratio="16:9", image_refs=[src])
    return out


def gen_asset(state: dict, name: str, info: dict, on_event=None,
              image_ref: bool = False, prompt_extra: str = "",
              custom_prompt: str = "", fallback_dir: str = "") -> dict:
    """重新生成单个资产的基础形象图；返回更新后的 info（写回 cast.json 由调用方）。

    image_ref=False：描述生成（纯文生图，描述大改时用）。
    image_ref=True：图生图——以现有形象图为参考图 + 描述提示词，
    保持主体特征只做微调（更准）。
    custom_prompt：用户自填的完整提示词——非空时取代模板/描述作为主体
    提示词（仍保留风格锚与画幅），想完全自己控制画面时用。
    fallback_dir：info 无 path 时的输出目录（调用方传自己 store 所在目录，
    避免章节专属资产错写到全书目录）。
    """
    on_event = on_event or (lambda e: None)
    out = info.get("path") or os.path.join(
        fallback_dir or _global_base(state), f"{_safe_name(name)}.png")
    sec = info.get("type") or "角色"
    tpl, ratio = _ASSET_TPL.get(sec, _ASSET_TPL["角色"])
    if custom_prompt.strip():
        prompt = inject_style(state, custom_prompt.strip())
    else:
        prompt = inject_style(state, f"{sec}基础形象：" +
                                     tpl.format(a=_anchored_appearance(
                                         info.get("appearance", ""))))
    refs = []
    if image_ref and os.path.exists(out):
        refs.append(out)
        prompt += ("。以参考图为基础仅按提示微调：保持人物身份/场景布局/"
                   "道具形态等主体特征一致，不要重画。")
    if prompt_extra:
        prompt += f"。{prompt_extra.strip('。 ')}"
    on_event({"type": "drama_media", "kind": "cast",
              "label": f"{name}（{sec}·{'图生图' if refs else '描述生成'}）"})
    path, url = imggen.generate_ex(prompt, out, size=_drama_sizes()[0], ratio=ratio,
                                   image_refs=refs, want_url=True)
    info["path"], info["url"] = path, url
    return info


def gen_look(state: dict, name: str, info: dict, era: str,
             on_event=None, custom_prompt: str = "") -> dict:
    """重新生成角色某阶段形象（现代/古装…）；返回更新后的 look 字典。

    脸部一致性：以角色主图为参考图做图生图——脸由图像锁定，只换该阶段
    的服装发型配饰（与 build_cast 补图同一约束）。写回 cast.json 由调用方。
    """
    on_event = on_event or (lambda e: None)
    looks = info.get("looks") or {}
    lk = looks.get(era) or {}
    main = info.get("path") or ""
    out = lk.get("path") or os.path.join(
        _global_base(state), f"{_safe_name(name)}-{_safe_name(era)}.png")
    sec = info.get("type") or "角色"
    tpl, ratio = _ASSET_TPL.get(sec, _ASSET_TPL["角色"])
    if custom_prompt.strip():
        prompt = inject_style(state, custom_prompt.strip())
    else:
        prompt = inject_style(state, f"{sec}基础形象·{era}阶段：" +
                                     tpl.format(a=_anchored_appearance(
                                         lk.get("appearance")
                                         or info.get("appearance", ""))))
    refs = []
    if main and os.path.exists(main):
        refs.append(main)
        prompt += ("。参考图是同一人物：严格保持参考图的脸型五官、发际线"
                   "与体格不变，仅更换为本阶段的服装发型与配饰。")
    on_event({"type": "drama_media", "kind": "cast",
              "label": f"{name}（{sec}·{era}）"})
    path, url = imggen.generate_ex(prompt, out, size=_drama_sizes()[0], ratio=ratio,
                                   image_refs=refs, want_url=True)
    lk = dict(lk)
    lk["path"], lk["url"] = path, url
    return lk


def replace_asset_image(state: dict, name: str, info: dict,
                        src_path: str, fallback_dir: str = "") -> dict:
    """用本地图片替换资产基础形象（转 PNG 落资产目录）；返回更新后的 info。"""
    if Image is None:
        raise _stop("替换图片需要 PIL（pip install pillow）")
    out = info.get("path") or os.path.join(
        fallback_dir or _global_base(state), f"{_safe_name(name)}.png")
    img = Image.open(src_path)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    img.save(out, "PNG")
    info["path"], info["url"] = out, ""
    return info


def _asset_subdir(state: dict, info: dict, ch: int = 0) -> str:
    """资产物理子目录：场景/角色 → 全书（长期）；临时/缺信息 → 给定章/全书。"""
    return (_chapter_asset_subdir(ch) if ch
            else _ASSET_GLOBAL)


def _resolve_asset_path(state: dict, name: str, info: dict,
                        ch: int = 0) -> tuple:
    """返回 (json 路径, png 路径)。json 在子目录根，png 与 json 同目录。"""
    sub = _asset_subdir(state, info, ch)
    base = os.path.join(_book_dir(state), _ASSET_DIR, sub)
    return (os.path.join(base, "cast.json"
                         if sub == _ASSET_GLOBAL else "assets.json"),
            os.path.join(base, f"{_safe_name(name)}.png"))


def _resolve_asset_image(state: dict, name: str, info: dict,
                          base: str = "") -> None:
    """info['path'] 缺失但 url 存在时，从 URL 下载到 base 目录并回填 path。

    是 gen_asset() / 手动上传替换之外的第三条补图路径——专给「生图服务只返回 URL
    未本地落盘」的旧数据做事后补建。path 已有则跳过；url 与 path 都空则不动（视为
    资产尚未生成）。download 失败时静默不抛——调用方按"未变更"处理即可。
    """
    p = (info.get("path") or "").strip()
    if p and os.path.exists(p):
        return
    url = (info.get("url") or "").strip()
    if not url or not base:
        return
    out = os.path.join(base, f"{_safe_name(name)}.png")
    try:
        from videogen import download as _vg_download
        _vg_download(url, out)
        if os.path.exists(out):
            info["path"] = out
    except Exception:                  # noqa: BLE001
        pass


def _global_base(state: dict) -> str:
    return os.path.join(_book_dir(state), _ASSET_DIR, _ASSET_GLOBAL)


def _global_cast_path(state: dict) -> str:
    return os.path.join(_global_base(state), "cast.json")


def _chapter_assets_path(state: dict, ch: int) -> str:
    return os.path.join(_book_dir(state), _ASSET_DIR,
                        _chapter_asset_subdir(ch), "assets.json")


def _reuse_existing_assets(state: dict, need: dict) -> dict:
    """跨章/跨库复用同名资产（通用一致性：同脸同物不重画）。

    扫描 全书/cast.json 与 短剧资产/第*章/assets.json，凡名字在 need
    里且已有可用图片的，返回 {名: info}（类型按 need 判定）。
    """
    found = {}
    base = os.path.join(_book_dir(state), _ASSET_DIR)
    import glob as _glob
    sources = [_global_cast_path(state)] + sorted(
        _glob.glob(os.path.join(base, "第*章", "assets.json")))
    for src in sources:
        data = _json_load(src, {})
        for nm, info in data.items():
            if nm in need and isinstance(info, dict):
                p = info.get("path") or ""
                if p and os.path.exists(p) and nm not in found:
                    found[nm] = {**info, "type": need[nm]}
    return found


def chapter_assets(state: dict, chapter: dict, shots: list, cast: dict,
                   on_event=None, redo: bool = False) -> dict:
    """章节专属（暂时）资产：分镜引用了、但全书资产里没有的名字。

    类型按引用位置自动判定（scene 字段→场景、characters→角色、props→
    道具），LLM 只补视觉描述；存 第N章.assets.json，出图同目录。
    已有文件命中缓存；下次跑其它章不影响本章。
    """
    on_event = on_event or (lambda e: None)
    path = _chapter_assets_path(state, chapter["idx"])
    local = _json_load(path, {})
    need = {}                       # 名 → 类型（引用位置决定）
    for s in shots:
        for nm, sec in ([( (s.get("scene") or "").strip(), "场景")]
                        + [(str(c).strip(), "角色")
                           for c in (s.get("characters") or [])]
                        + [(str(c).strip(), "道具")
                           for c in (s.get("props") or [])]):
            if nm and nm not in cast and nm not in local \
                    and not nm.startswith("_"):
                need.setdefault(nm, sec)
    # 跨章复用（通用一致性）：同名资产其它章已出过图 → 直接沿用，
    # 同一临时角色/道具跨章不再生成第二张不同的图
    if need:
        for nm, info in _reuse_existing_assets(state, need).items():
            local[nm] = info
            need.pop(nm, None)
        if need or local:
            _json_dump(path, local)
    if need and not local.get("_done"):
        names = "\n".join(f"- {nm}（{sec}）" for nm, sec in need.items())
        text = _ask(
            state,
            "你是美术指导。为下列名字逐个写确定性视觉描述——角色写外貌"
            "（性别年龄感、发型、脸型、体型、服装），场景写空间陈设材质光线，"
            "道具写形状材质颜色新旧。每个 30-60 字，只要看得见的部分。"
            '只输出 JSON：{"名字": "视觉描述", ...}，与列表一一对应。',
            f"名单：\n{names}\n请输出 JSON。")
        data = _extract_json(text)
        if isinstance(data, dict) and data:
            for nm, desc in data.items():
                nm = str(nm).strip()
                if nm in need:
                    old = local.get(nm) or {}
                    local[nm] = {"type": need[nm], "appearance": str(desc),
                                 **{k: v for k, v in old.items()
                                    if k in ("path", "url")}}
            local["_done"] = True
            _json_dump(path, local)
    base = os.path.join(_book_dir(state), _ASSET_DIR,
                        _chapter_asset_subdir(chapter["idx"]))
    for name, info in list(local.items()):
        if (name.startswith("_") or not isinstance(info, dict)
                or (info.get("path") and not redo)):
            continue
        sec = info.get("type") or "道具"
        tpl, ratio = _ASSET_TPL.get(sec, _ASSET_TPL["道具"])
        out = os.path.join(base, f"{_safe_name(name)}.png")
        on_event({"type": "drama_media", "kind": "cast",
                  "label": f"{name}（{sec}·第{chapter['idx']}章）"})
        try:
            p, url = imggen.generate_ex(
                # v2.1 单点风格注入 + 远程新增的 _drama_sizes() 尺寸解析
                inject_style(state, f"{sec}基础形象：" + tpl.format(
                    a=_anchored_appearance(info.get("appearance", "")))),
                out, size=_drama_sizes()[0], ratio=ratio)
            info["path"], info["url"] = p, url
        except Exception as e:          # noqa: BLE001  单个失败不阻断
            on_event({"type": "drama_media", "kind": "debt",
                      "label": f"{name} 形象生成跳过：{e}"})
        _json_dump(path, local)
    return local


def effective_cast(cast: dict, local: dict) -> dict:
    """本章生效资产 = 全书（长期）+ 本章专属（暂时，同名覆盖全书）。"""
    merged = dict(cast)
    merged.update({k: v for k, v in (local or {}).items()
                   if not k.startswith("_") and isinstance(v, dict)})
    return merged


# ---------------- 2. 分镜表（LLM → JSON） ----------------

def _clean_text(t: str, limit: int = 0) -> str:
    """分镜字段消毒：剔 <think> 块（含内容）、代码围栏（含语言标签）、引导语。"""
    t = re.sub(r"<think>.*?</think>", "", str(t or ""), flags=re.S)
    t = re.sub(r"```[a-zA-Z]*", "", t)            # 围栏起始（含语言标签）
    t = re.sub(r"```", "", t)                    # 围栏结束
    t = re.sub(r"</?[a-zA-Z][^>]{0,80}>", "", t)      # 残留 HTML/标记标签
    # 引导语只剥字符串前 80 字符内的（避免误伤正文里「以下是…」「让我…」）
    head = t.strip()[:80]
    head = re.sub(r"^(好的|以下是|根据要求[，,]?|让我们?[，,]?)[\s，,]*,?\s*",
                  "", head)
    t = head + t.strip()[80:]
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit] if limit else t


def build_shots(state: dict, chapter: dict, on_event=None,
                cast: dict | None = None) -> list:
    """把一章改编为结构化分镜 JSON（含影视语言描述），缓存到分镜目录。

    cast 传入时把已有形象阶段名（looks 键）作为 era 词表发给 LLM，
    分镜 era 与资产阶段名对齐，关键帧才能命中对应套形象。
    """
    path = os.path.join(_book_dir(state), _SHOT_DIR,
                        f"第{chapter['idx']}章.json")
    cached = _json_load(path, None)
    if isinstance(cached, list) and cached:
        return cached
    on_event = on_event or (lambda e: None)
    on_event({"type": "drama_media", "kind": "shots", "label": chapter["title"]})
    era_names = sorted({str(k) for info in (cast or {}).values()
                        if isinstance(info, dict)
                        for k in ((info.get("looks") or {}))})
    era_rule = ("每个镜头标注 era（所处时代/阶段，与该镜头场景一致，"
                "角色服装随 era 走）。"
        + (f"era 必须优先从这些已生成形象的阶段名里选："
           f"{'、'.join(era_names)}——没有合适再自创简短新词。"
           if era_names else ""))
    text = _ask(
        state,
        "你是短剧导演。把小说章节改编为竖屏短剧分镜表（参考火宝短剧规范）。"
        "一个镜头=一个分镜段落=一次视频生成任务，全程只发生在一个场景内。"
        # v2.1：画面风格由 inject_style 在 prompt 前缀注入；此处不再硬写
        "description 必须体现项目视觉风格的质感与光影词汇。"
        "【拆段规则】先识别叙事节拍（地点转移/规则揭示/情绪爆发/反转是强制"
        "切段点），一条因果链（铺垫-发生-反应）不拆散到不同段落；"
        "总量锚定：目标镜头数 ≈ 章节字数÷500字每分钟÷12秒，允许±20%。"
        "【段落时长分层】过渡段（赶路/空镜/转场）8-10 秒；叙事段（常规剧情/"
        "对话）10-15 秒；爆点段（特写/反转/情感爆发）12-15 秒。"
        "【description 子镜头化】每段内含 2-4 个子镜头，按"
        "「【镜头1】…【镜头2】…」逐个写：每个 2-6 秒聚焦一个画面单元"
        "（一个动作/一个反应/一个特写），景别优先近景/特写/中近景（竖屏"
        "小屏少用远景），子镜头间可切镜（换景别/角度/对象，硬切）；"
        "台词写在对应【镜头N】内，格式「角色名说：「台词」」，"
        "旁白写「旁白：…」；情绪转可见描写（不写「他很紧张」，写"
        "「手指攥紧杯沿」）。"
        "【表演克制】禁止写尖叫、嘶吼、大喊、惊恐大喊、放声大哭等夸大表演，"
        "台词不堆叹号；受惊写成微反应（僵住、后退半步、手一抖），"
        "台词保持日常语气，情绪靠微表情与节奏传达。"
        "相邻镜头必须承接：动作从上一镜结束状态自然延续，时间/地点/光线/"
        "道具状态一致，不重复上一镜已用过的镜头设计。"
        "原文血腥暴力等敏感描写自动改为中性表达（如「喷血」→「衣襟染上"
        "暗色痕迹」），剧情不变。"
        "camera 写本镜主导运镜（推近/拉远/横移/摇/跟拍/固定），mood 写本镜"
        "情绪氛围（如 紧张/温馨/压抑/燃），供配音语气与表演参考。"
        "duration 硬规则：≥（旁白字数+台词字数）÷4.5字每秒 + 2 秒表演余量，"
        "装不下的台词拆到下一镜，人物没说完话就切镜是重大缺陷；"
        "但节奏要明快，无台词镜头不超 10 秒，拖沓慢镜是短剧大忌。"
        + era_rule +
        "每个镜头再写一句 narration 旁白解说词（第三人称说书人口吻，"
        "15-40 字，交代前情/心理/转折，让观众听得懂剧情；纯对白镜也要有）。"
        '只输出 JSON 数组：[{"title": "镜头小标题", "scene": "场景名", '
        '"era": "时代阶段", '
        '"characters": ["出场角色名"], "props": ["出场关键道具名"], '
        '"description": "【镜头1】…【镜头2】…", "camera": "运镜", '
        '"mood": "情绪氛围", '
        '"narration": "旁白解说词", '
        '"dialogue": "关键台词（可为空）", "duration": 秒数}]。'
        "scene/characters/props 用简短通用名"
        "（同物同名，别一章里出现「手机」「电话」两种叫法）。",
        f"小说正文（第 {chapter['idx']} 章《{chapter['title']}》）：\n"
        f"{chapter['text']}")
    shots = _extract_json(text)
    if not isinstance(shots, list) or not shots:
        raise _stop(f"第 {chapter['idx']} 章分镜生成失败（LLM 未返回 JSON）")
    clean = []
    for s in shots:
        if not isinstance(s, dict) or not s.get("description"):
            continue
        try:
            sec = float(s.get("duration") or 5)
        except (TypeError, ValueError):
            sec = 5
        clean.append({
            "title": _clean_text(s.get("title"), 30),
            "scene": _clean_text(s.get("scene")),
            "era": _clean_text(s.get("era"), 12),
            "characters": [_clean_text(c) for c in (s.get("characters") or [])][:4],
            "props": [_clean_text(c) for c in (s.get("props") or [])][:3],
            "description": _clean_text(s["description"]),
            "camera": _clean_text(s.get("camera"), 20),
            "mood": _clean_text(s.get("mood"), 12),
            "narration": _clean_text(s.get("narration"), 80),
            "dialogue": _clean_text(s.get("dialogue")),
            "duration": max(_MIN_SEC, min(_MAX_SEC, sec)),
        })
    if not clean:
        raise _stop(f"第 {chapter['idx']} 章分镜解析为空")
    _video_prompts(state, chapter, clean)      # 二次生成：3秒分段时间轴
    _json_dump(path, clean)
    return clean


def _video_prompts(state: dict, chapter: dict, shots: list):
    """给每个分镜段落二次生成 video_prompt（火宝规范）：按 3 秒分段。

    每镜结构：信息头（出场人物+场景+道具）+ 连续时间分段行；第一段建立
    空间，切镜用「切到/切回」衔接，台词分配到对应段，情绪转可见描写。
    失败静默跳过（clip() 回退旧模板），成功则写进各 s["video_prompt"]。
    """
    todo = [i for i, s in enumerate(shots) if s.get("description")]
    if not todo:
        return
    try:
        lines = []
        for i in todo:
            s = shots[i]
            lines.append(
                f"镜头{i + 1}（{int(s['duration'])}秒，场景「{s['scene']}」，"
                f"角色{'、'.join(s['characters']) or '无'}，"
                f"道具{'、'.join(s['props']) or '无'}）：\n{s['description']}")
        text = _ask(
            state,
            "你是视频提示词工程师（火宝规范）。把每个分镜段落的 description"
            "转成按时间分段的视频生成提示词。规则："
            "段数=时长÷3秒向上取整，各段时间连续无重叠；"
            "每段一行「N-M秒：景别运镜，主体+具体动作与表情，台词或旁白」；"
            "第一段必须建立空间（场景+机位+角色位置）；子镜头切镜处用"
            "「切到/切回」衔接并重述景别；台词写「角色名说：「台词」」"
            "从 description 的对应【镜头N】提取，3 秒念不完拆多段，"
            "不得创作 description 之外的新台词；情绪转可见动作描写；"
            "表演克制写实：禁止尖叫/大喊/夸张惊吓动作，受惊用微反应"
            "（僵住、后退半步），台词按日常音量说话；"
            "一个段落只发生在一个场景。"
            '只输出 JSON：{"1": "第一镜 video_prompt", "2": "..."}'
            "（键=镜头号，字符串内用换行分隔时间段）。",
            "\n\n".join(lines))
        data = _extract_json(text)
        if isinstance(data, dict):
            for i in todo:
                v = data.get(str(i + 1)) or data.get(i + 1)
                if isinstance(v, str) and v.strip():
                    shots[i]["video_prompt"] = _clean_text(v)
    except Exception:                      # noqa: BLE001 失败不阻断，回退模板
        pass


def regen_video_prompt(state: dict, chapter_idx: int, shot_idx: int) -> str:
    """单镜 video_prompt 重生成：只改目标镜头、结果落盘、其他镜不受影响。

    越界镜头号 → 不写、不炸、返回空串。LLM 失败（空 JSON）→ 原文件
    不动，返回空串（调用方可当作"未变更"处理）。v2.1 风格由 _ask() 透传
    inject_style，agent prompt 无需再手动前缀风格词。
    """
    path = os.path.join(_book_dir(state), _SHOT_DIR,
                        f"第{chapter_idx}章.json")
    shots = _json_load(path, [])
    if not isinstance(shots, list) or shot_idx < 1 or shot_idx > len(shots):
        return ""
    s = shots[shot_idx - 1]
    desc = (s.get("description") or "").strip()
    if not desc:
        return ""
    sys_p = ("你是视频提示词工程师。把单条分镜的 description 写成按时间分段的"
             "视频生成提示词：每段以「N-M秒：景别运镜，主体+动作+台词」格式，"
             "段数=时长÷3秒向上取整。严格遵循 description，不创作新台词。"
             "表演克制写实：禁止尖叫/大喊/夸张惊吓动作，受惊用微反应"
             "（僵住、后退半步），台词按日常音量。"
             "输出必须是 JSON：{\"1\": \"0-3秒：…\"}")
    user_p = (f"分镜 #{shot_idx}（{int(s.get('duration', 0))}秒，场景"
              f"「{s.get('scene', '')}」，角色{'、'.join(s.get('characters') or []) or '无'}，"
              f"道具{'、'.join(s.get('props') or []) or '无'}）：\n{desc}")
    try:
        raw = _ask(state, sys_p, user_p)
        data = _extract_json(raw) or {}
        v = data.get("1") or data.get(1)
        if isinstance(v, str) and v.strip():
            v = _clean_text(v)
            s["video_prompt"] = v
            _json_dump(path, shots)
            return v
    except Exception:                  # noqa: BLE001
        pass
    return ""


# ---------------- 3. 关键帧 + 镜头视频 ----------------

def _urls_path(state: dict) -> str:
    return os.path.join(_book_dir(state), _SHOT_DIR, "urls.json")


def keyframe(state: dict, cast: dict, shot: dict, ch: int, i: int,
             on_event=None, force: bool = False) -> tuple:
    """镜头关键帧：场景+角色+道具参考图多图合成保持一致。返回 (path, url)。

    文件存在即缓存（整批跑断点续造）；force=True 无视缓存重新生成
    （工作台单镜「生成关键帧」点按即重生成）。
    """
    on_event = on_event or (lambda e: None)
    base = os.path.join(_book_dir(state), _FRAME_DIR)
    out = os.path.join(base, f"{ch}-{i:02d}.png")
    if os.path.exists(out) and not force:
        url = _json_load(_urls_path(state), {}).get(f"{ch}-{i:02d}", "")
        return out, url
    refs, scene_ref, who, props = [], None, [], []

    def _img(info):
        p = (info or {}).get("path") or ""
        return p if p and os.path.exists(p) else None

    body_text = shot["description"] + " " + shot.get("dialogue", "")
    shot_props = set(shot.get("props") or [])
    scene_name = (shot.get("scene") or "").strip()
    era = (shot.get("era") or "").strip()

    def _role_visual(name, info):
        """按镜头时代选角色形象：looks[era] 命中用该套，否则默认套。

        精确未命中再做包含式模糊匹配（分镜写「科技修仙期」也能
        命中资产阶段「修仙」），避免措辞偏差静默退回默认装。
        """
        looks = (info or {}).get("looks") or {}
        if not isinstance(looks, dict) or not looks:
            return info or {}
        if era and looks.get(era):
            return looks[era]
        if era:
            for k, v in looks.items():
                if k and (k in era or era in k):
                    return v
        return info or {}

    for name, info in cast.items():
        if name.startswith("_") or not isinstance(info, dict):
            continue
        sec = info.get("type") or "角色"
        if sec == "角色" and name in shot["characters"]:
            vis = _role_visual(name, info)
            p = (vis.get("path") or info.get("path") or "")
            p = p if p and os.path.exists(p) else None
            if p:
                refs.append(p)
            ap = (vis.get("appearance") or info.get("appearance") or "")
            if ap:
                ap = _anchored_appearance(ap)
                who.append(f"{name}·{era}（{ap}）" if era else f"{name}（{ap}）")
        elif sec == "场景" and scene_name and not scene_ref:
            p = _img(info)
            if p and (name in scene_name or scene_name in name):
                scene_ref = p                       # 场景空镜放参考图首位
        elif sec == "道具" and (name in shot_props or name in body_text):
            p = _img(info)
            if p:
                props.append(p)
    if scene_ref:
        refs.insert(0, scene_ref)
    refs.extend(props)
    prompt = (inject_style(state, f"{shot['description']}。") +
              f"场景：{scene_name}。出场角色：{'、'.join(who) or '（无）'}。"
              "参考图依次为场景空镜、角色形象、道具，"
              "严格保持参考图中场景布置、角色长相与道具外观一致。"
              "画面中不要出现任何字幕、文字、标题、水印或字母字符。竖屏构图。"
            + " " + _dbg.body_guard(state, who))
    on_event({"type": "drama_media", "kind": "frame",
              "label": f"第{ch}章 镜头{i}"})
    path, url = imggen.generate_ex(prompt, out, size=_drama_sizes()[0],
                                   ratio=_drama_sizes()[1],
                                   image_refs=refs, want_url=True)
    if url:
        urls = _json_load(_urls_path(state), {})
        urls[f"{ch}-{i:02d}"] = url
        _json_dump(_urls_path(state), urls)
    return path, url


def _ffmpeg_exe() -> str:
    """返回可用的 ffmpeg 可执行文件路径。

    优先系统 PATH（便于测试 monkeypatch `dramavideo.shutil.which`）；
    缺失则回退到 imageio-ffmpeg 捆绑二进制（pip install imageio-ffmpeg，
    Windows 也能免装 ffmpeg 直接跑）。两者都没装则返回 ""。
    """
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg              # noqa: PLC0415  懒导入
        return imageio_ffmpeg.get_ffmpeg_exe() or ""
    except Exception:                  # noqa: BLE001
        return ""


def dub(video_path: str, audio_path: str, out_path: str) -> str:
    """ffmpeg 把配音替换到视频音轨（-shortest 对齐时长）。"""
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        raise _stop("未安装 ffmpeg（配音混流与整集合成都需要它；"
                    "pip install imageio-ffmpeg 可免系统依赖，"
                    "或安装说明见 docs/novel-setup.md）")
    subprocess.run([ffmpeg, "-y", "-i", video_path, "-i", audio_path,
                    "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-shortest", out_path],
                   capture_output=True, timeout=300, check=True)
    return out_path


def clip(state: dict, shot: dict, frame_url: str, ch: int, i: int,
         on_event=None, force: bool = False) -> str:
    """镜头视频：有关键帧 URL 用图生视频（一致性传导），否则文生视频降级。

    文件存在即缓存（断点续造）；force=True 无视缓存重新生成（工作台
    单镜「生成镜头视频」点按即重生成）。

    音频默认用视频模型自带的同步语音（台词写在提示词里，模型自己配）。
    仅当 state["drama_tts"] 打开时才追加 TTS 配音（ffmpeg 混流替换音轨，
    TTS/ffmpeg 不可用或失败则保留模型原声，不阻断）。
    """
    on_event = on_event or (lambda e: None)
    out = os.path.join(_book_dir(state), _CLIP_DIR, f"{ch}-{i:02d}.mp4")
    if os.path.exists(out) and not force:
        return out
    return _render_clip(state, shot, frame_url, ch, i, out, on_event)


def _speech_seconds(shot: dict) -> int:
    """旁白+台词按中文语速（约 4 字/秒）估完读时长，另加 1.5s 收尾余量。

    视频模型给多长画面就只能说多长的话——镜头时长低于这个数时，
    台词必然被截断（人物没说完就切镜），所以渲染前取两者较大值。
    """
    spoken = len((shot.get("narration") or "").strip()) + \
        len((shot.get("dialogue") or "").strip())
    need = int(spoken / 4.0 + 1.5 + 0.999)
    return max(_MIN_SEC, min(_MAX_SEC, need))


def _render_clip(state: dict, shot: dict, frame_url: str, ch: int, i: int,
                 out: str, on_event) -> str:
    """渲染一条镜头视频到指定路径（clip 与抽卡 gen_clip_take 共用）。"""
    narration = (shot.get("narration") or "").strip()
    dialogue = (shot.get("dialogue") or "").strip()
    camera = (shot.get("camera") or "").strip()
    mood = (shot.get("mood") or "").strip()
    # 画面指令与配音指令分离：模型同步语音只许念「旁白/台词」，
    # 风格与分镜术语（机位/焦段/运镜）绝不能被读出来，且锁死中文普通话。
    # 屏显文字一律禁止：模型烧录的字幕中英夹杂、汉字常渲染成乱码，
    # 解说信息由配音承担，画面保持纯净
    vp = (shot.get("video_prompt") or "").strip()
    if vp:
        # 火宝式 3 秒分段时间轴：段内已含切镜衔接与台词分配，直接用
        prompt = (inject_style(state, "按时间分段执行以下画面：") +
                  "\n" + vp + "\n"
                  "画面中不要出现任何字幕、文字、标题、水印或字母字符；"
                  "分段之间用硬切，全程不跨场景。"
                  + _dbg.body_guard(state, who))
        if camera:
            prompt += f"主导运镜：{camera}。"
    else:
        prompt = (inject_style(state, f"画面：{shot['description']}。") +
                  "画面中不要出现任何字幕、文字、标题、水印或字母字符。"
                  + _dbg.body_guard(state, who))
        if camera:
            prompt += f"镜头运动：{camera}。"
        elif dialogue:
            prompt += "镜头运动：固定（台词段镜头必须稳定，不切换不推拉）。"
    if mood:
        prompt += f"本镜情绪氛围：{mood}。"
    # 节奏控制：短剧忌王家卫式慢镜头——动作干脆、运镜流畅、不留凝滞
    prompt += ("表演与节奏：人物动作干脆利落、目标明确，"
               "不要慢动作、不要长时间静止凝视或发呆式停顿。")
    # 表演克制：视频模型默认倾向夸张短剧腔（大呼小叫/一惊一乍），
    # 必须明令「日常音量+微反应」压住，比事后反复抽卡省得多
    prompt += ("表演分寸：所有角色按日常音量自然说话，"
               "禁止尖叫、嘶吼、大喊、大呼小叫、放声痛哭；"
               "受惊或震惊用克制反应（僵住、后退半步、瞳孔微缩、沉默一拍），"
               "禁止夸张的肢体后仰、双手抱头、面部扭曲式惊吓表演；"
               "情绪靠微表情与节奏传达，表演自然写实，像真人实拍电影。")
    # 声音设计（借鉴漫剧指令包）：环境音服务剧情，禁止背景音乐
    prompt += ("\n环境音：按画面写真实环境音与动作音效（风声/脚步声/水声/"
               "衣物摩擦等，2-3 种即可，服务剧情不堆砌）；禁止背景音乐。")
    prompt += ("\n配音要求：成片语音只朗读下面标注的内容，画面描述、风格说明"
               "等其它文字一律不要朗读、不要复述；全程中文普通话，"
               "不要出现英语或任何其它语言；台词要完整说完、旁白要完整读完，"
               "人物说到一半不得结束镜头。"
               "只有说话的角色才有张嘴和口型动作，口型与台词严格同步；"
               "画外音旁白期间画面人物保持沉默，只有眼神、表情和细微动作；"
               "台词使用中文引号“”。")
    if mood:
        prompt += f"语气贴合「{mood}」的情绪。"
    prompt += "\n"
    if narration:
        prompt += f"旁白（第三人称解说，整句朗读）：{narration}\n"
    if dialogue:
        prompt += f"台词（角色对白）：{dialogue}"
    if not narration and not dialogue:
        prompt += "旁白/台词：无——本镜只有环境音，不要生成任何人声。"
    sec = max(float(shot.get("duration") or _MIN_SEC), _speech_seconds(shot))
    on_event({"type": "drama_media", "kind": "clip",
              "label": f"第{ch}章 镜头{i}", "sec": sec})
    # TTS 配音（需 drama_tts 开关 + ffmpeg）：有台词配台词，纯旁白镜配旁白
    # ——Seedance 1.0 系列视频无原生语音，靠这条补声
    spoken = dialogue or narration
    want_dub = bool(state.get("drama_tts")) and spoken
    # 顶栏 provider/resolution 覆盖（state["drama_video_provider"] 缺省回落到 env/全局）
    res = (state.get("drama_video_resolution") or "").strip()
    preferred = (state.get("drama_video_provider") or "").strip()
    # 超时按时长缩放：长视频（15s/441帧）云端常超 4 分钟，240s 固定值会误杀
    try:
        raw = videogen.generate(prompt, out if not want_dub else out + ".raw.mp4",
                                image=frame_url, resolution=res, seconds=sec,
                                timeout=max(240.0, sec * 30.0),
                                preferred_provider_id=preferred)
    except videogen.VidError as e:
        # 内容审核切模型（参考火宝 v3.1）：错误分类后抛专用异常，
        # UI 顶栏接住后可一键切到下一个 provider 重试。
        cls = videogen.classify_error(str(e))
        svc_now = videogen._service()  # noqa: SLF001
        if cls["category"] == "moderation":
            on_event({"type": "drama_media", "kind": "moderation",
                      "label": f"第{ch}章 镜头{i}（审核拒绝）",
                      "hint": cls.get("hint") or "",
                      "original": str(e)[:300],
                      "provider_id": svc_now.get("provider_id", ""),
                      "model": svc_now.get("model", "")})
            raise DramaModerationError(
                f"内容审核拒绝：{cls.get('hint') or '请尝试切模型'}",
                hint=cls.get("hint") or "",
                original_err=str(e)[:300],
                provider_id=svc_now.get("provider_id", ""),
                model=svc_now.get("model", "")) from e
        raise
    if not want_dub:
        return raw
    import tts
    try:
        on_event({"type": "drama_media", "kind": "dub",
                  "label": f"第{ch}章 镜头{i} 配音"})
        audio = tts.speak(spoken.strip(),
                          out.replace(".mp4", ".dub.mp3"))
        dub(raw, audio, out)
        os.remove(raw)
        return out
    except Exception as e:              # noqa: BLE001  配音失败不阻断
        on_event({"type": "drama_media", "kind": "debt",
                  "label": f"第{ch}章 镜头{i} 配音跳过：{e}"})
        if raw != out:
            try:
                os.replace(raw, out)    # 保留模型原声成片
            except OSError:
                pass
        return out


# ---------------- 3.5 抽卡（同镜多候选，择优入片） ----------------

def list_takes(state: dict, ch: int, i: int) -> list:
    """某镜头已抽的卡：[(take号, 视频路径)]，按号升序。主成片不在列。"""
    import glob as _glob
    base = os.path.join(_book_dir(state), _CLIP_DIR)
    if not os.path.isdir(base):
        return []
    out = []
    for p in _glob.glob(os.path.join(base, f"{ch}-{i:02d}-take*.mp4")):
        m = re.search(r"take(\d+)\.mp4$", p)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)


def gen_clip_take(state: dict, shot: dict, frame_url: str, ch: int, i: int,
                  on_event=None) -> str:
    """视频抽卡：同一关键帧再生成一条候选，存为独立 take。

    不动当前成片（主文件）——生成模型有随机性，一条不满意就再抽，
    满意的用 select_clip_take 换成主成片；已有的 take 全部保留可回选。
    """
    takes = list_takes(state, ch, i)
    n = (takes[-1][0] + 1) if takes else 1
    out = os.path.join(_book_dir(state), _CLIP_DIR,
                       f"{ch}-{i:02d}-take{n}.mp4")
    on_event = on_event or (lambda e: None)
    return _render_clip(state, shot, frame_url, ch, i, out, on_event)


def select_clip_take(state: dict, ch: int, i: int, take_path: str) -> str:
    """把抽到的卡设为当前成片：拷贝覆盖主文件（take 保留，之后还能改选）。

    整集合成（concat）只认主文件，选完卡重新合成即用上新片段。
    """
    canon = os.path.join(_book_dir(state), _CLIP_DIR, f"{ch}-{i:02d}.mp4")
    if os.path.abspath(take_path) == os.path.abspath(canon):
        return canon
    os.makedirs(os.path.dirname(canon) or ".", exist_ok=True)
    shutil.copyfile(take_path, canon)
    return canon


def take_thumb(video_path: str, out_png: str) -> str:
    """ffmpeg 抽视频首帧做缩略图（take 预览用）；无 ffmpeg/失败返回空串。"""
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        return ""
    try:
        subprocess.run([ffmpeg, "-y", "-i", video_path, "-frames:v", "1",
                        out_png], capture_output=True, timeout=60, check=True)
        return out_png if os.path.exists(out_png) else ""
    except Exception:                   # noqa: BLE001  预览失败降级为文字
        return ""


# ---------------- 4. ffmpeg 合成 ----------------

def concat(clips: list, out_path: str, on_event=None) -> str:
    """ffmpeg concat 拼接整集；先无损 copy，失败回退重编码。

    选择性拼接：列表里不存在的文件会被跳过（不阻断），on_event 非空时
    推送 {"type":"drama_media","kind":"concat_skip","label":...,"names":[...]}
    让 UI 顶部状态栏提示已跳过的镜头。返回拼接产物路径；列表全部缺失抛错。
    """
    on_event = on_event or (lambda e: None)
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        raise _stop("未安装 ffmpeg（整集合成需要；"
                    "pip install imageio-ffmpeg 可免系统依赖，"
                    "或安装说明见 docs/novel-setup.md，装后重跑本命令即可续造）")
    valid = [p for p in clips if p and os.path.exists(str(p))]
    missing = [p for p in clips if p and not os.path.exists(str(p))]
    if missing:
        names = sorted({os.path.basename(os.path.splitext(m)[0])
                        for m in missing})
        on_event({"type": "drama_media", "kind": "concat_skip",
                  "label": f"已跳过 {len(missing)} 个未生成镜头",
                  "names": names})
    if not valid:
        raise _stop("可拼接的文件数为 0：请先生成至少一个镜头视频")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    lst = out_path + ".list.txt"
    with open(lst, "w", encoding="utf-8") as f:
        for p in valid:
            f.write("file '" + str(p).replace("'", "'\\''") + "'\n")
    try:
        subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0",
                        "-i", lst, "-c", "copy", out_path],
                       capture_output=True, timeout=600, check=True)
    except subprocess.CalledProcessError:
        subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0",
                        "-i", lst, "-c:v", "libx264", "-crf", "23",
                        "-c:a", "aac", out_path],
                       capture_output=True, timeout=1200, check=True)
    finally:
        try:
            os.remove(lst)
        except OSError:
            pass
    return out_path


def run_assets(state: dict, ch_start: int = 0, ch_end: int = 0,
               on_event=None, stop=None, redo: bool = False) -> dict:
    """只做资产生成（不出关键帧/视频），供先期调整形象。

    ch_start=0：仅全书资产；给出范围则顺带生成该范围各章的分镜
    （LLM 拆分镜，缓存）与章节专属资产。返回各类计数。
    """
    on_event = on_event or (lambda e: None)
    cast = build_cast(state, on_event, stop=stop, redo=redo)
    n_cast = sum(1 for k, v in cast.items()
                 if not k.startswith("_") and isinstance(v, dict)
                 and v.get("path"))
    out = {"cast": n_cast, "chapters": {}}
    if ch_start:
        chapters = [c for c in state.get("chapters", [])
                    if ch_start <= c["idx"] <= ch_end and c.get("text")]
        for c in chapters:
            if stop is not None and stop.is_set():
                raise _stop("已手动停止：已生成资产保留，重跑续造")
            shots = build_shots(state, c, on_event, cast=cast)
            local = chapter_assets(state, c, shots, cast, on_event,
                                   redo=redo)
            out["chapters"][c["idx"]] = sum(
                1 for k, v in local.items()
                if not k.startswith("_") and isinstance(v, dict) and v.get("path"))
    return out


def drop_media(state: dict, ch: int, shot: int = 0) -> int:
    """删除某章（或某镜）的关键帧+片段，使其可重新生成。返回删除数。"""
    n = 0
    for d in (_FRAME_DIR, _CLIP_DIR):
        if shot:
            p = os.path.join(_book_dir(state), d, f"{ch}-{shot:02d}.*")
        else:
            p = os.path.join(_book_dir(state), d, f"{ch}-*.*")
        import glob as _glob
        for f in _glob.glob(p):
            try:
                os.remove(f)
                n += 1
            except OSError:
                pass
    return n


def reset(state: dict) -> int:
    """删掉全部短剧产物（资产/分镜/关键帧/片段/成片）；小说正文不受影响。

    返回删除的文件数；之后 /novel drama video 会从零重建
    （重新提取资产、重新拆分镜、全部重新生成）。
    """
    import glob as _glob
    n = 0
    base = _book_dir(state)
    for d in (_ASSET_DIR, _SHOT_DIR, _FRAME_DIR, _CLIP_DIR, _OUT_DIR):
        p = os.path.join(base, d)
        if not os.path.isdir(p):
            continue
        for f in _glob.glob(os.path.join(p, "**", "*"), recursive=True):
            if os.path.isfile(f):
                try:
                    os.remove(f)
                    n += 1
                except OSError:
                    pass
        try:
            os.rmdir(p)                # 清空后顺手移除目录本身
        except OSError:
            pass
    return n


def run_clips_batch(state: dict, ch: int, on_event=None, stop=None,
                   only_missing: bool = True) -> dict:
    """单章批量生成关键帧+镜头视频（UI 顶栏「批量生成视频」按钮用）。

    仅做关键帧 + 视频两件事，不跑资产提取（资产已是前置）；也不做合成——
    合成由 UI 另起按钮触发（可选择性拼接）。返回：
      {"ok": [path,...], "fail": [(i, err_str),...], "skipped_existing": [i,...]}

    only_missing=True（默认）跳过已有 mp4 的镜头，仅补缺失的（重试失败用）。
    only_missing=False 强制重生成（先删关键帧+片段，参考 drop_media）。
    """
    on_event = on_event or (lambda e: None)

    def _stopped():
        return stop is not None and stop.is_set()

    chapters = state.get("chapters") or []
    chobj = next((c for c in chapters if c.get("idx") == ch), None)
    if not chobj:
        raise _stop(f"第 {ch} 章不存在")
    shots_path = os.path.join(_book_dir(state), _SHOT_DIR,
                              f"第{ch}章.json")
    shots = _json_load(shots_path, None)
    if not isinstance(shots, list) or not shots:
        raise _stop(f"第 {ch} 章还没有分镜——先跑 /novel drama 生成该章分镜")
    if only_missing is False:
        n = drop_media(state, ch)
        if n:
            on_event({"type": "drama_media", "kind": "redo",
                      "label": f"第{ch}章（已删 {n} 个产物，强制重生成）"})
    cast = _json_load(_global_cast_path(state), {})
    local = _json_load(_chapter_assets_path(state, ch), {})
    cast_ch = effective_cast(cast, local)
    ok, fail, skipped = [], [], []
    for i, shot in enumerate(shots, 1):
        if _stopped():
            raise _stop("已手动停止：已完成镜头保留，重跑自动续造")
        clip_path = os.path.join(_book_dir(state), _CLIP_DIR,
                                 f"{ch}-{i:02d}.mp4")
        if only_missing and os.path.exists(clip_path):
            skipped.append(i)
            continue
        url = ""
        try:
            _, url = keyframe(state, cast_ch, shot, ch, i, on_event)
        except Exception as e:           # noqa: BLE001  单镜失败不阻断
            err = str(e)
            fail.append((i, err))
            on_event({"type": "drama_media", "kind": "debt",
                      "label": f"第{ch}章 镜头{i} 关键帧失败：{err[:80]}"})
            continue
        try:
            ok.append(clip(state, shot, url, ch, i, on_event))
        except Exception as e:           # noqa: BLE001
            err = str(e)
            fail.append((i, err))
            on_event({"type": "drama_media", "kind": "debt",
                      "label": f"第{ch}章 镜头{i} 视频失败：{err[:80]}"})
    return {"ok": ok, "fail": fail, "skipped_existing": skipped}


# ---------------- 总入口 ----------------

def run(state: dict, ch_start: int, ch_end: int, on_event=None,
        redo: bool = False, stop=None, stop_after: str = "") -> list:
    """按章范围跑完整链：资产 → 分镜 → 关键帧 → 镜头视频 → 合成。

    redo=True 时先删范围内各章的关键帧与片段（角色形象/分镜表保留），
    全部重新生成。单个镜头失败不阻断（记质量债继续跑，末尾合成已完成
    片段；重跑本命令自动补造缺失镜头）。stop 为 threading.Event：置位后
    在资产/章节/镜头边界停下（已完成产物保留）。

    stop_after：手动模式——跑到该阶段为止停下（"" = 全自动一跑到底），
    可选 assets / shots / keyframes / clips / compose。停下后可手工调整
    产物（改分镜 JSON、替换关键帧图），再跑下一阶段命令续造：已完成的
    产物自动跳过，不会覆盖手工修改。返回每章成片路径列表。
    """
    on_event = on_event or (lambda e: None)
    order = ("assets", "shots", "keyframes", "clips", "compose")
    do = {s: True for s in order}
    if stop_after in do:
        for s in order[order.index(stop_after) + 1:]:
            do[s] = False

    def _stopped():
        return stop is not None and stop.is_set()

    if not imggen.available():
        raise _stop("未配置图像生成服务（/novel drama video 需要它出形象与关键帧；"
                    "请在供应商管理给 Agnes 或商汤填 API Key）")
    chapters = [c for c in state.get("chapters", [])
                if ch_start <= c["idx"] <= ch_end and c.get("text")]
    if not chapters:
        raise _stop("所选范围没有已完成章节")
    if redo:
        for c in chapters:
            n = drop_media(state, c["idx"])
            if n:
                on_event({"type": "drama_media", "kind": "redo",
                          "label": f"第{c['idx']}章（已删 {n} 个产物，重生成）"})
    cast = build_cast(state, on_event, stop=stop)
    if not do["shots"]:
        raise _stop("✅ 阶段「形象资产」完成——可替换 media 下形象图后，"
                    "跑 /novel drama shots 继续")
    outs = []
    debts = []
    for c in chapters:
        if _stopped():
            raise _stop("已手动停止：已完成产物保留，重跑命令自动续造")
        shots = build_shots(state, c, on_event, cast=cast)
        if stop_after == "shots":
            continue
        local = chapter_assets(state, c, shots, cast, on_event)
        cast_ch = effective_cast(cast, local)   # 长期 + 本章暂时
        clips = []
        for i, shot in enumerate(shots, 1):
            if _stopped():
                raise _stop("已手动停止：已完成产物保留，重跑命令自动续造")
            url = ""
            if do["keyframes"]:
                try:
                    _, url = keyframe(state, cast_ch, shot, c["idx"], i, on_event)
                except Exception as e:       # noqa: BLE001  单镜失败不阻断
                    debts.append(f"第{c['idx']}章 镜头{i} 关键帧：{e}")
                    on_event({"type": "drama_media", "kind": "debt",
                              "label": f"第{c['idx']}章 镜头{i} 关键帧失败，跳过"})
            if do["clips"]:
                try:
                    clips.append(clip(state, shot, url, c["idx"], i, on_event))
                except Exception as e:       # noqa: BLE001
                    debts.append(f"第{c['idx']}章 镜头{i} 视频：{e}")
                    on_event({"type": "drama_media", "kind": "debt",
                              "label": f"第{c['idx']}章 镜头{i} 视频失败，跳过"})
        if do["clips"] and not clips:
            continue                      # 本章全军覆没：不合成，重跑续造
        if not do["compose"]:
            continue                      # 手动分步：未到合成阶段
        out = os.path.join(_book_dir(state), _OUT_DIR,
                           f"第{c['idx']}章-{_safe_name(c['title'])}.mp4")
        on_event({"type": "drama_media", "kind": "concat",
                  "label": f"第{c['idx']}章（{len(clips)}/{len(shots)} 镜）"})
        outs.append(concat(clips, out))
        on_event({"type": "drama_media", "kind": "done", "label": c["title"],
                  "path": out})
    boundary = {
        "shots": "✅ 阶段「分镜」完成——可手工调整 分镜目录 下的 JSON，"
                 "然后跑 /novel drama frames 继续",
        "keyframes": "✅ 阶段「关键帧」完成——可替换不满意的关键帧图，"
                     "然后跑 /novel drama clips 继续",
        "clips": "✅ 阶段「镜头视频」完成——可先试看各镜头，"
                 "然后跑 /novel drama compose 合成整集",
    }
    if stop_after in boundary:
        on_event({"type": "drama_media", "kind": "stage",
                  "label": boundary[stop_after]})
        raise _stop(boundary[stop_after])
    if debts:
        on_event({"type": "drama_media", "kind": "debt",
                  "label": "；".join(debts[:5])
                  + (f"（等 {len(debts)} 项）" if len(debts) > 5 else "")
                  + " —— 重跑 /novel drama video 会自动补造缺失镜头"})
    if not outs:
        raise _stop("所有镜头生成都失败了：\n" + "\n".join(debts[:6]
                    + (["……"] if len(debts) > 6 else [])))
    return outs
