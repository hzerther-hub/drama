"""把「易好短剧」web 平台(E:/xiaoshuo)的项目数据移植到 novelwriter 书稿目录。

数据流：web 平台 SQLite(dramas/episodes/characters/scenes/props/character_variants)
  → novels/<书名>/{大纲,设定集,正文,短剧剧本,短剧资产} + CONFIG_DIR/pipelines/<pid>.json
移植后剧集工作台(novel drama)可直接续作：拍摄剧本存在即优先、cast 资产可补图、
漫画按钮可对移植章节生成分镜。

用法（工作区根目录下）：
    python port_yihao_novel.py [web_db路径] [--drama-id N] [--force]

幂等：pipeline JSON 已存在且非 --force 时跳过写入。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys

import config
import pipeline as _pl
import novel_chain

DEFAULT_DB = r"E:\xiaoshuo\data\yihao.sqlite3"
DEFAULT_DRAMA_ID = 1


def _safe_name(name: str) -> str:
    """目录/文件名净化：去路径非法字符与首尾空白（与 novel_chain._safe_name 同思路）。"""
    return re.sub(r'[\\/:*?"<>|\r\n]+', "", (name or "").strip()) or "untitled"


def _parse_tags(raw: str | None) -> list[str]:
    """character_variants.tags / setting_tags 的 JSON 数组字符串 → 标签列表。"""
    if not raw:
        return []
    try:
        arr = json.loads(raw)
    except Exception:                       # noqa: BLE001
        return []
    if not isinstance(arr, list):
        return []
    return [str(t).strip() for t in arr if str(t).strip()]


def _fetch(db: sqlite3.Connection, drama_id: int) -> dict:
    row = db.execute(
        "SELECT * FROM dramas WHERE id=? AND deleted_at IS NULL", (drama_id,)
    ).fetchone()
    if row is None:
        raise SystemExit(f"web 库中不存在 drama_id={drama_id}")
    drama = dict(zip([c[0] for c in db.execute("SELECT * FROM dramas LIMIT 1").description], row))

    def rows(sql: str, args: tuple = ()):
        cur = db.execute(sql, args)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    eps = rows(
        "SELECT * FROM episodes WHERE drama_id=? AND deleted_at IS NULL "
        "ORDER BY episode_number", (drama_id,))
    chars = rows(
        "SELECT * FROM characters WHERE drama_id=? AND deleted_at IS NULL "
        "ORDER BY sort_order, id", (drama_id,))
    scenes = rows(
        "SELECT * FROM scenes WHERE drama_id=? AND deleted_at IS NULL ORDER BY id",
        (drama_id,))
    props = rows(
        "SELECT * FROM props WHERE drama_id=? AND deleted_at IS NULL ORDER BY id",
        (drama_id,))
    variants = rows(
        "SELECT cv.* FROM character_variants cv JOIN characters c "
        "ON c.id=cv.character_id WHERE c.drama_id=? AND cv.deleted_at IS NULL "
        "ORDER BY cv.sort_order, cv.id", (drama_id,))
    style = ""
    srow = db.execute(
        "SELECT prompt FROM style_presets WHERE value=?",
        (drama.get("style") or "",)).fetchone()
    if srow:
        style = srow[0] or ""
    return {"drama": drama, "episodes": eps, "characters": chars,
            "scenes": scenes, "props": props, "variants": variants,
            "style": style}


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _variants_block(variants: list[dict], character_id: int) -> str:
    mine = [v for v in variants if v.get("character_id") == character_id]
    if not mine:
        return ""
    lines = ["", "### 造型变体", ""]
    for v in mine:
        tags = "/".join(_parse_tags(v.get("tags")))
        lines.append(f"- **{v.get('label') or '未命名'}**"
                     f"（标签：{tags or '无'}）：{v.get('costume_desc') or ''}")
    return "\n".join(lines) + "\n"


def _copy_image(src_rel: str | None, static_root: str, dest_dir: str,
                base_name: str) -> str:
    """把 web 平台 static/ 相对路径的图拷进书资产目录，返回绝对路径（无图返回 ''）。"""
    if not src_rel:
        return ""
    name = os.path.basename(src_rel)
    if not name:
        return ""
    rel = src_rel.replace("\\", "/")
    if rel.startswith("/"):
        rel = rel[1:]
    if rel.startswith("static/"):
        rel = rel[len("static/"):]
    src = os.path.join(static_root, rel)
    if not os.path.isfile(src):
        src = os.path.join(static_root, name)
        if not os.path.isfile(src):
            return ""
    stem, ext = os.path.splitext(name)
    safe_stem = _safe_name(base_name) or stem
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{safe_stem}{ext or '.png'}")
    if not os.path.isfile(dest):
        shutil.copyfile(src, dest)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db", nargs="?", default=DEFAULT_DB)
    ap.add_argument("--drama-id", type=int, default=DEFAULT_DRAMA_ID)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.db):
        raise SystemExit(f"web 数据库不存在：{args.db}")

    db = sqlite3.connect(args.db)
    data = _fetch(db, args.drama_id)
    db.close()

    drama, eps = data["drama"], data["episodes"]
    if not eps:
        raise SystemExit("该项目没有可移植的剧集（episodes 为空）")

    pid = _safe_name(drama.get("title") or f"drama-{drama['id']}")
    title = drama.get("title") or pid
    book = os.path.join(novel_chain._novels_root(), pid)
    os.makedirs(book, exist_ok=True)

    pipe_path = os.path.join(config.CONFIG_DIR, "pipelines", f"{pid}.json")
    if os.path.isfile(pipe_path) and not args.force:
        print(f"⏭ 已存在 {pipe_path}（--force 可覆盖）")
    else:
        # ---- 正文/章节（state.chapters 与 正文/*.md 同源）----
        chapters = []
        for ep in eps:
            idx = int(ep.get("episode_number") or (len(chapters) + 1))
            text = (ep.get("content") or "").strip()
            if not text:
                continue
            chap_title = (ep.get("title") or f"第{idx}章").strip()
            chap = {"idx": idx, "title": chap_title, "text": text,
                    "summary": text[:160].replace("\n", " "), "issues": []}
            chapters.append(chap)
            _write(os.path.join(book, novel_chain._DIR_TEXT,
                                f"第{idx:04d}章-{_safe_name(chap_title)}.md"),
                   f"# {chap_title}\n\n{text}\n")
        chapters.sort(key=lambda c: c["idx"])

        # ---- 拍摄剧本：存在即优先于原文 ----
        for ep in eps:
            script = (ep.get("script_content") or "").strip()
            if not script:
                continue
            idx = int(ep.get("episode_number") or 0)
            _write(os.path.join(book, dramavideo_scr_dir(),
                                f"第{idx}章-剧本.md"),
                   f"# {ep.get('title') or idx} · 拍摄剧本\n\n{script}\n")

        # ---- 设定集/大纲（界面「剧本大纲」页左侧导航直接可编辑）----
        chars = data["characters"]
        variants = data["variants"]
        ch_list = "\n".join(f"- 第{c['idx']}章《{c['title']}》" for c in chapters)
        framing = (f"题材：{drama.get('genre') or '短剧'}\n"
                   f"画幅：{drama.get('aspect_ratio') or '16:9'}　"
                   f"风格：{drama.get('style') or '3d'}\n"
                   f"简介：{drama.get('description') or title}\n")
        outline = (f"# {title} · 总纲\n\n{framing}\n## 分集\n\n{ch_list}\n")
        scene_lines = "\n".join(
            f"- **{s.get('location')}**（{s.get('time') or '时间未定'}）："
            f"{s.get('prompt') or ''}　光影：{s.get('lighting') or ''}"
            for s in data["scenes"]) or "（暂无）"
        world = (f"# 世界观\n\n## 场景\n\n{scene_lines}\n\n"
                 f"## 视觉风格\n\n{data['style'] or drama.get('style') or ''}\n")
        char_md = []
        for c in chars:
            char_md.append(
                f"## {c.get('name')}（{c.get('role') or '角色'}）\n\n"
                f"- 样貌：{c.get('appearance') or ''}\n"
                f"- 妆造：{c.get('styling') or ''}\n"
                f"- 描述：{c.get('description') or ''}"
                + _variants_block(variants, int(c["id"])) + "\n")
        characters_md = ("# 角色设定\n\n" + ("\n".join(char_md) or "（暂无）") + "\n")
        contract = ("# 故事合约\n\n"
                    "- 保持角色样貌/服装跨镜头一致；服装随时代/场景标签切换时必须整体切换。\n"
                    "- 每章结尾留钩子；风格与总纲一致。\n")
        plan = ("\n".join(f"- 第{c['idx']}章《{c['title']}》：约 "
                          f"{len(c['text'])} 字" for c in chapters) + "\n")

        _write(os.path.join(book, novel_chain._DIR_OUTLINE,
                            novel_chain._OUTLINE_FILE), outline)
        _write(os.path.join(book, novel_chain._DIR_SETTING, "世界观.md"), world)
        _write(os.path.join(book, novel_chain._DIR_SETTING, "故事合约.md"), contract)
        _write(os.path.join(book, novel_chain._DIR_SETTING, "角色.md"), characters_md)

        # ---- 短剧资产 cast.json（含 web 侧已生成图）----
        static_root = os.path.join(os.path.dirname(os.path.abspath(args.db)),
                                   "static")
        cast_dir = os.path.join(book, "短剧资产", "全书")
        cast: dict = {}
        for c in chars:
            img = _copy_image(c.get("image_url") or c.get("local_path"),
                              static_root, cast_dir, c.get("name") or "")
            cast[c["name"]] = {
                "type": "角色",
                "appearance": "；".join(x for x in (
                    c.get("appearance") or "", c.get("styling") or "") if x),
                "path": img, "url": ""}
        for s in data["scenes"]:
            img = _copy_image(s.get("image_url") or s.get("local_path"),
                              static_root, cast_dir, f"场景-{s.get('location')}")
            cast[s["location"]] = {
                "type": "场景",
                "appearance": f"{s.get('prompt') or ''}（光影：{s.get('lighting') or ''}）",
                "path": img, "url": ""}
        for p_ in data["props"]:
            img = _copy_image(p_.get("image_url") or p_.get("local_path"),
                              static_root, cast_dir, f"道具-{p_.get('name')}")
            cast[p_["name"]] = {
                "type": "道具", "appearance": p_.get("description") or "",
                "path": img, "url": ""}
        done = {f"_done_{t}": True for t in ("角色", "场景", "道具")
                if any(v.get("type") == t for v in cast.values()
                       if isinstance(v, dict))}
        _write(os.path.join(cast_dir, "cast.json"),
               json.dumps({**cast, **done}, ensure_ascii=False, indent=1))

        # ---- pipeline 状态（chapters[].text 必须在 state 里，工作台靠它列出章节）----
        words = [len(c["text"]) for c in chapters]
        avg = sum(words) // max(len(words), 1)
        state = {
            "pid": pid,
            "title": title,
            "framing": framing,
            "outline": outline,
            "world": world,
            "contract": contract,
            "characters": characters_md,
            "volume": f"第 1-{len(chapters)} 章｜{title}",
            "chapter_plan": plan,
            "chapters": chapters,
            "total_chapters": len(chapters),
            # 每章字数目标：取移植章节均长按 500 取整，UI/命令均可改
            "ch_words": max(500, min(int(round(avg / 500) * 500), 20000)),
            "ported_from": {"db": args.db, "drama_id": args.drama_id},
        }
        p = _pl.Pipeline(pid, title, novel_chain.STAGES, state)
        p.cursor = "chapters"
        p.save()
        print(f"✅ pipeline → {pipe_path}")

    print(f"✅ 书稿目录 → {book}")
    print("   大纲/设定集/正文/短剧剧本/短剧资产 已就绪；"
          "在 novelwriter 里 /novel pick 或最近书籍即可进入剧集工作台")


def dramavideo_scr_dir() -> str:
    """与 dramavideo._SCREENPLAY_DIR 保持一致（避免 import 70KB 模块）。"""
    return "短剧剧本"


if __name__ == "__main__":
    sys.exit(main())
