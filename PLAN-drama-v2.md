# PLAN-drama-v2.md

> 来源：`E:\xiaoshuo/docs/drama-pipeline.md` 的风格化方法论 × 本仓库
> `dramavideo.py` + `ui_panel_drama.py` 的现状对比分析。**仅设计文档，不动代码**。
>
> 触发背景：用户重置了所有流水线（重新写小说），同时希望从「Easy Drama」
> 借鉴短剧工作流的成熟做法，但保留本仓库「文件系统即缓存」的轻量哲学。
>
> 目标读者：未来我自己（或接手者）有闲余时间时执行改造时按此文档走。
> 排期与优先级在最后。

---

## 0. 当前现状速记

| 层 | 文件 | 大小 | 职责 |
|---|---|---|---|
| 后端 / 引擎 | `dramavideo.py` | ~70KB | 三段流水线 + ffmpeg 拼接；`DEFAULT_STYLE`、`cast.json` I/O、`_done_<类>` 标记、关键帧多图合成 |
| UI | `ui_panel_drama.py` | ~45KB | 四页工作台：大纲 / 资产 / 分镜视频 / 漫画入口 |
| 视频 | `videogen.py` | ~12KB | 多 provider 视频生成 |
| 图像 | `imggen.py` | ~18KB | 角色参考图、关键帧多图合成 |
| 短剧命令 | `novel_chain.py` | ~700KB | `drama_adapt` / `drama_video` / `comic_adapt` / `comic_cast` / `drama_new` |

**目录约定**（`dramavideo.py:10-11`，相对 `novels/<书名>/`）：

```
短剧剧本/    第N章-剧本.md   ← 改写产物；存在即优先于小说原文
短剧资产/    全书/cast.json + 第N章/assets.json + 各 png
短剧分镜/    第N章.json + urls.json
短剧关键帧/  N-01.png ...
短剧片段/    N-01.mp4 ...
短剧成片/    第N章-<标题>.mp4
漫画分镜.md                 ← /novel comic 生成
漫画/        第N-格01.png + 第N-长图.png
```

**当前 `dramavideo.reset(state)` 的清盘范围**：
- 删 `短剧资产/` / `短剧分镜/` / `短剧关键帧/` / `短剧片段/` / `短剧成片/`
- **保留** `短剧剧本/`（拍摄剧本是用户改过的文本）+ state 内的 chapters
- **不删** `漫画分镜.md` / `漫画/`（reset 时漫画目录被忽略）

---

## 1. 对比分析（xiaoshuo vs 本仓库）

### 1.1 借鉴价值分级

| xiaoshuo 做法 | 借鉴价值 | 本仓库现状 | 改造难度 |
|---|---|---|---|
| **视觉风格单点注入**：项目级 `style` + 独立 `comic_style`；agent prompt 不写风格词，提交时统一由系统 inject | **高**——避免同书多风格词打架；风格可中途改 | `DEFAULT_STYLE` 写死 + `_preset_lib` 风格列表；agent prompt（`_ASSET_TPL` / `_SECTION_SYS`）硬编了"电影感写实风格" | 中 |
| **`character_variants` 造型变体表** | **中**——穿越/换装/乔装/战损，跨集一致性需要 | 未实现 | 高（需 schema 改造 + variants UI + setting_tags 匹配） |
| **资产 `comic_image_url` 镜像列** | **高**——同一形象换漫画画风，跨格一致性 | 未实现；目前漫画复用真实风主图 | 中 |
| **分镜硬约束**：8-15s 段落 + 节拍识别 + 台词时长 ≥ 字数/4.5字/秒 + 2s 余量 | **中**——硬规则保护质量 | 章节级时长但缺节拍/台词硬约束 | 中 |
| **去重合并规则**：角色按精确名字、场景按 (地点, 时间段) 二元键 | **中**——减少冗余资产 | 角色精确名字已有；场景仅按 name 二元键 | 小 |
| **Agent 体系（5 agent + skills）** | **低**——本仓库单文件 Python 引擎足够 | novel_chain + dramavideo 已实现 4 个具名 agent | 大 |
| **统一 `sys_task` 任务生命周期** | **低**——本仓库「文件存在即缓存」哲学更轻 | 没有；任务失败靠 LLM 重试 + 用户手动重试 | 大 |
| **后端 + 前端分离（TS + Vue）** | **不借鉴**——架构级差异 | Tk GUI 不动 | — |

### 1.2 风格系统升级（最优先）

**目标**：让 agent prompt 不含风格词，统一由落盘/提交时 inject。

**问题**：本仓库现在 `_ASSET_TPL` 里硬编"电影感写实风格，统一色调与打光，画面细腻，短剧质感"，agent 读到模板就把这个风格词作为锚点写进 final_prompt，导致风格词四处出现。

**改造**（5 处修改）：
1. `_ASSET_TPL` 里删除"电影感写实风格..."前缀 → 改成"按【项目视觉风格】渲染，简洁生成式提示词"
2. `build_cast()` / `build_shots()` 在调用 `_ask()` 前用 `system` 注入"项目视觉风格 = X"作为引导
3. `final_prompt` 落盘前，调用方（`save_*` 函数）prepend `style_lib[state.drama_style].text + '\n\n'`
4. 视频 prompt 同样：`_video_prompts()` 调用方 prepend
5. 风格选择 UI：工作台顶栏 + 设置菜单都暴露（AGENTS.md 已声明 settings 菜单底部两个 checkbutton 管 drama/comic 模式；现在加第三栏「🎨 视觉风格」）

### 1.3 资产持久化分层

**保留跨 reset 的**（用户手改/手填，是权威）：
- 拍摄剧本 `短剧剧本/第N章-剧本.md`（当前已保留）
- 全书级资产 `短剧资产/全书/cast.json`（**目前 reset 会删整个 `短剧资产/`，bug**）
- 项目视觉风格（**目前不存在，需要新增**）
- 漫画画风 `dramas.comic_style`（同上）

**章级缓存可重做**（reset 应该删）：
- 分镜表 `短剧分镜/第N章.json`
- 关键帧 `短剧关键帧/N-XX.png`
- 视频片段 `短剧片段/N-XX.mp4`
- 成片 `短剧成片/第N章-xxx.mp4`

**章级专属可重做**（reset 该删）：
- 章级道具 `短剧资产/第N章/assets.json`

**改造**：`dramavideo.reset()` 拆为：
```python
def reset_drama(state) -> int:
    """仅清 drama 缓存（分镜/关键帧/片段/成片）；保留剧本 + cast + 章级资产"""
    # 删 _SHOT_DIR / _FRAME_DIR / _CLIP_DIR / _OUT_DIR
    # 不动 _SCREENPLAY_DIR / _ASSET_DIR / 短剧剧本/

def reset_comic(state) -> int:
    """仅清 comic 缓存；保留 drama + cast + 剧本"""
    # 删 漫画/ / 漫画分镜.md
    # 不动 短剧资产/ / 短剧剧本/

def reset_assets(state) -> int:
    """仅清全书+章级资产；保留剧本 + 视觉风格 + 漫画资产镜像"""
    # 删 _ASSET_DIR（重提，重出图会重新走全套）
```

UI 加 3 个独立 reset 按钮（位于工作台顶栏右侧的「⚠ 高级操作」折叠菜单），互不误伤。

### 1.4 漫画资产独立化

**当前问题**：漫画线跟 drama 线共用 `cast.json` 的 `image_url` —— 但漫画需要的是漫画画风，drama 用的是真实风。一个共用 URL 同时喂两个 prompt，模型自由发挥，跨格一致性难保证。

**改造**（11 处 schema 变更）：
```python
# cast.json / assets.json schema 升 1
{
    "角色A": {
        "type": "角色", "appearance": "...", "path": "短剧资产/全书/角色A.png",
        "url": "...",                        # 真实风三视图（视频线主锚）
        "comic_image_url": "...",             # 漫画画风镜像（漫画线主锚）
        "comic_path": "短剧资产/全书/角色A.comic.png",
        "comic_style": "韩漫风"               # 出图时选的画风，可改；改后提示词重生
    },
    "_done_角色": True
}
```

新增工作台按钮：
- **「📖 出 comic 镜像」** —— 批量给 cast + chapter assets 生成 `comic_image_url`，出图时把主图作为参考图一并传入（防止镜像不像主形象）
- **「🎨 切换漫画画风」** —— 改 `comic_style` 后**只重生 comic_image_url 不动 video 主图**

成本：每章 0-5 个角色 + 1-3 个场景 + 0-3 个道具，每张图生成同真实风等价的资源消耗；与视频线独立排队，不阻塞视频生成。

### 1.5 章节级 cache 命中规则

**当前规则**：`短剧分镜/第N章.json` 存在即跳过整个分镜阶段。但用户可能改了剧本后想重拆——目前没有 UI 入口，只能手动删文件。

**改造**：
- 工作台「剧本环节」底部加「🔄 改剧本后点这里清分镜缓存」按钮（已实际存在于 `_save_screenplay()`：line 708 自动删除 `第N章.json`）。已有但只在 save 后触发，不在外部 UI 暴露。
- 增加章节信息卡片的"提示"：当 `短剧剧本/第N章-剧本.md` 与 `短剧分镜/第N章.json` 同时存在但 mtime 剧本更新时，工作台顶部黄色提示「剧本改了，是否重拆分镜？」

### 1.6 UI 工作台分流（不强制做短剧）

**当前入口**：剧集工作台一打开就 4 个 tab：大纲 / 资产 / 分镜视频 / 漫画。漫画 tab 是"如果模型 flag 开了就能用"的隐藏入口。

**改造**（小动作）：
- 工作台启动时，先弹一个模式选择 modal：「🎬 做短剧 / 📖 做漫画 / 🔀 都做」（一次性选，记 state 标志 `_drama_workflow_mode`）。
- 选择「📖 做漫画」时 → 工作台只剩 3 tab：大纲 / 资产 / 漫画格（**没有"分镜视频"tab**）。
- 工作台 config flag：`_drama_workflow_mode in {"drama","comic","both"}`，落 `state["drama_workflow_mode"]`。
- 重置 `state["drama_workflow_mode"] = "both"` 由 ⚙ 设置菜单「创作模式」提供。

这样"我只想把小说内容画成漫画贴小红书"的轻量场景不再走视频线。

---

## 2. 实施路线（分期，每期独立可验证）

### v2.1：风格系统单点注入（**P0**，~150 行）

文件：`dramavideo.py` + `ui_panel_drama.py` + `novel_chain.py`（AGENTS.md 提的 `state.drama_style` 持久化字段需要写到 novel_chain.py）

改动：
1. `state["drama_style"] = "电影感写实风格"` 默认；`state["comic_style"] = ""`（空 = 跟随项目视觉风格）
2. `_ASSET_TPL` / `_SECTION_SYS` / `_SHOT_SYS` 删除硬编风格词 → 改"[由项目视觉风格决定]"
3. `finalize_*()` 落盘前 `prepend style_lib[state.drama_style].text`
4. `_video_prompts()` 落库前 prepend
5. 工作台顶栏视觉风格下拉（按 `_preset_lib()` 列表）
6. 设置菜单 ⚙ 顶部加「视觉风格」选 picker（持久化到 state）

验收：相同剧本两本书，一本用"国漫风"一本用"电影感写实风格"，同章节同分镜的 final_prompt 内容除前缀外一致；cast.json 的 url 不动。

### v2.2：reset 拆 3 路 + cast 不被误删（**P0**，~80 行）

文件：`dramavideo.py`

改动：
1. `reset(state)` 拆为 `reset_drama` / `reset_comic` / `reset_assets`，各自独立函数
2. 旧 `reset(state)` 保留为「全清」接口（内部依次调 3 个），保证兼容
3. UI 工作台加 3 个 reset 按钮 + 二次确认

验收：`reset_drama` 后 cast.json 仍存在；`reset_comic` 后短剧成片仍存在。

### v2.3：资产 comic_image_url 镜像列（**P1**，~400 行）

文件：`dramavideo.py` + `ui_panel_drama.py` + `imggen.py`

改动：
1. cast.json / assets.json schema 升级（v2.1 已部分涉及）
2. 工作台「📖 出 comic 镜像」按钮（批量）→ 调 `imggen.image_with_refs()`，参考图 = 主图，prompt = `comic_style + appearance`
3. 漫画格生成时优先用 comic_image_url，没有时回退 image_url
4. 工作台卡片显示主图 + comic 图并列（左右两个缩略图）

验收：同一角色在视频线 + 漫画线都认得出是「王安平」；改 comic_style 后漫画镜像重生、视频线不动。

### v2.4：分镜硬约束 + 台词不越权（**P1**，~200 行）

文件：`dramavideo.py`

改动：
1. `_SHOT_SYS` 加节拍识别指令："识别【开场】【触发】【高潮】【收尾】标记，转折点强制切段"
2. `_SHOT_SYS` 加节奏分层："过渡段 8-10s / 叙事段 10-15s / 爆点段 12-15s"
3. 加台词时长硬下限：`if 段落台词字数/4.5 + 2 > duration: 拆到下一段`
4. `_video_prompts()` system prompt 加硬约束："所有台词必须从 description 提取，不创作新台词"
5. validator：生成的 video_prompt 含未在 description 出现的台词时告警

验收：跑同一剧本，对比前后 video_prompt 中台词覆盖率与画面描写丰富度。

### v2.5：UI 工作流模式分流（**P2**，~120 行）

文件：`ui_panel_drama.py` + `config.py` + `novel_chain.py`

改动：
1. 新增 `state["drama_workflow_mode"]`，默认 "both"
2. 工作台启动时一次性弹模式选择 modal（除非 state 已有）
3. 模式 = "comic" 时隐藏"分镜视频"tab，保留"漫画格"
4. 设置菜单 ⚙ 加模式选择

验收：模式选 comic → 工作台看不到"分镜视频"；选 drama → 看不到"漫画格"；选 both → 全显示。

### v2.6：场景二元键去重 + 资产类型化（**P2**，~250 行）

文件：`dramavideo.py` + `novel_chain.py`

改动：
1. 场景去重规则：`(location.strip().lower(), time.strip())` 二元键匹配
2. 现有 `effective_cast()` 扩展到含场景
3. cast.json 资产类型字段：`"角色" / "场景" / "道具"`，每个都有独立 `comic_image_url`
4. agent prompt 明确"不要问现有"，直接调用 `read_existing_assets()`（已有）

验收：同名不同时间段的场景是两个独立条目（"仙界·白天" ≠ "仙界·夜晚"）；同名相同时段合并。

### v2.7：造型变体表（**P3**，~600 行）

文件：`dramavideo.py` + `ui_panel_drama.py` + `novel_chain.py`

这是最大块——xiaoshuo 的核心特色，但工作量也最大。预估要新增 `character_variants` schema、`variants` UI tab、setting_tags 匹配算法、`storyboard_characters.variant_id` 人工覆盖 UI、变体参考图选择逻辑。建议**单独一期**做。

### v2.8：统一任务追踪 sys_task（**P3**，~500 行）

文件：新建 `task_gen.py` + 改 `imggen.py` / `videogen.py`

本仓库现在靠"文件存在即跳过"+ UI 状态条做任务追踪，足够轻量。sys_task 是 xiaoshuo 的全栈式需求，本仓库不一定需要。建议**搁置**，除非多任务并发场景出问题。

---

## 3. 风险与权衡

| 风险 | 缓解 |
|---|---|
| 风格词单点注入改 prompt 模板后，老 prompt 重生成的 final_prompt 会变短，可能影响一致性 | 改版前跑一轮小型回归（同一本书同章节生成 3 次 final_prompt，diff 比较） |
| comic_image_url 多生一张图 = 资源消耗 ×2 | 出镜像走单独排队（`/novel drama cast comic`），不影响视频线 |
| 分镜硬约束（节拍/台词时长）可能让模型出稿失败率上升 | 在 state 上加 `drama_relax_constraints` flag 暂时放开 |
| reset 拆 3 路后，UI 必须引导用户选 | 工作台顶栏「⚠ 高级操作」折叠菜单 + 二次确认框 + 取消 = 一键撤销 |
| 工作流模式分流后，"two 选了 comic 但忘了切回 both"的尴尬 | 顶栏模式标签常驻显示；`/novel drama video` 命令在 comic-only 模式下默认给 ⚠ 提示 |

---

## 4. 排期建议

| 期 | 内容 | 工作量 | 是否阻塞写新书 |
|---|---|---|---|
| **v2.1** | 风格系统单点注入 | 150 行 / 1–2 天 | **是**——不换风格词位置，永远要选风格就得每次手动补 |
| **v2.2** | reset 拆 3 路 | 80 行 / 0.5 天 | **是**——当前 reset() 会误删 cast 是 bug |
| **v2.3** | 资产 comic_image_url 镜像列 | 400 行 / 4–5 天 | 否——漫画可后做 |
| **v2.4** | 分镜硬约束 + 台词不越权 | 200 行 / 2 天 | 否 |
| **v2.5** | UI 工作流模式分流 | 120 行 / 1 天 | 否 |
| **v2.6** | 场景二元键去重 | 250 行 / 2 天 | 否 |
| v2.7 | 造型变体表 | 600 行 / 1 周 | 否 |
| v2.8 | 统一任务追踪 | 500 行 / 1 周 | 否 |

**建议执行顺序**：v2.2 → v2.1 → v2.5 → v2.4 → v2.3 → v2.6 → v2.7 → v2.8。
v2.2 修 bug 优先；v2.1 解锁风格中途切换；v2.5 解锁"我只想画漫画"的轻量场景；其余按用户场景出现再触发。

---

## 5. 关联文件清单（实施时按此核对）

实施时建议同步修改以下文件（按版本段分组）：

**v2.1**:
- `dramavideo.py` —— `_ASSET_TPL`、`_SECTION_SYS`、`build_cast`、`_finalize_*`、`_video_prompts`
- `novel_chain.py` —— state schema 加 `drama_style` / `comic_style`
- `ui_panel_drama.py` —— 工作台顶栏视觉风格下拉
- `config.py` —— `get_drama_style() / set_drama_style()`

**v2.2**:
- `dramavideo.py` —— `reset()` 拆 3 路
- `ui_panel_drama.py` —— 「⚠ 高级操作」折叠菜单 + 3 个 reset 按钮 + 二次确认
- `i18n.py` —— `ds.reset_*` 字符串

**v2.5**:
- `config.py` —— `set_drama_workflow_mode() / get_drama_workflow_mode()`
- `novel_chain.py` —— state schema 加 `drama_workflow_mode`
- `ui_panel_drama.py` —— 启动模式选择 modal、tab 显隐逻辑

**v2.3 / v2.4 / v2.6 / v2.7 / v2.8** 留待 v2.1+v2.2 上线后再排。

---

## 6. 不做的事

为防止范围蔓延，下面这些**不在本次改造范围**，记在这里作为明确的反例：

- **不重写 agent 编排为 TS / Mastra 风格**——本仓库 Python 单文件引擎足够轻量，agent 数 ≤ 6，重写 ROI 低
- **不做后端 + 前端分离**——架构级差异，Tk GUI 保留
- **不做统一 `sys_task` 任务追踪（v2.8）**——本仓库「文件存在即缓存」哲学够用
- **不做 PostgreSQL 存储**——文件系统是设计选择
- **不做双角色主形象（同一角色有真实风 + 漫画风两套基础形象）**——comic_image_url 镜像列已足够
- **不做实时协作 / 多用户**——单用户本地工具

---

## 7. 验证清单（每期完成后跑）

- `python -m py_compile *.py` 通过
- `python -m pytest tests/ -q` 不退化（baseline 471 passed + 1 skipped，v2.1+v2.2 跑完不应掉）
- 手动跑一遍完整 happy-path：`/novel start <灵感> → 跑完全章 → /novel drama → 工作台三页走完 → /novel drama video 跑出来 mp4`
- 看 visual 一致性：同一角色在不同分镜里长相一致（v2.1 风格注入生效的关键验证）
- 看 file-not-found 风险：v2.2 跑后 cast.json 是否仍存在