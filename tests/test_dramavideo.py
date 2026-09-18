# -*- coding: utf-8 -*-
"""dramavideo.py：分镜解析、资产缓存、参考图一致性链、ffmpeg 合成。"""

import json
import os
import subprocess

import pytest

import dramavideo


@pytest.fixture
def book(tmp_path, monkeypatch):
    """临时书目录 + 禁用真实 LLM/生成网络。"""
    monkeypatch.setattr(dramavideo, "_book_dir", lambda state: str(tmp_path))
    monkeypatch.setattr(dramavideo.imggen, "available", lambda: True)
    state = {"pid": "novel-t", "title": "测试书",
             "characters": "## 主角：林夏\n善良大学生。"}
    return state, tmp_path


def test_extract_json_tolerates_fences_and_prose():
    assert dramavideo._extract_json(
        "```json\n[{\"a\": 1}]\n```") == [{"a": 1}]
    assert dramavideo._extract_json('前置说明 [{"b": 2}] 后置') == [{"b": 2}]
    assert dramavideo._extract_json("完全不是 JSON") is None


def test_build_cast_three_sections_and_caches(book, monkeypatch):
    state, tmp = book
    asks, gens = [], []

    def fake_ask(st, sys, user):
        asks.append(sys[:12])
        if "选角导演" in sys:
            return '{"林夏": "黑长直发，圆脸，白色卫衣"}'
        if "美术指导" in sys:
            return '{"女生宿舍": "四人间，上床下桌，米色墙砖，午后阳光"}'
        return '{"水桶": "蓝色桶装饮用水，透明水嘴"}'

    def fake_gen(prompt, out, size="", ratio="", image_refs=None,
                 want_url=False):
        gens.append((out, ratio))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"PNG")
        return out, "http://cdn/x.png"

    monkeypatch.setattr(dramavideo, "_ask", fake_ask)
    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    cast = dramavideo.build_cast(state)
    assert cast["林夏"]["type"] == "角色"
    assert cast["女生宿舍"]["type"] == "场景"
    assert cast["水桶"]["type"] == "道具"
    assert len(gens) == 3                        # 三类各出一张基础图
    ratios = {r for _, r in gens}
    assert ratios == {"3:4", "16:9", "1:1"}      # 各类画幅不同
    # 再次构建：全部命中缓存，不再调 LLM / 出图
    dramavideo.build_cast(state)
    assert len(asks) == 3 and len(gens) == 3


def test_migrate_flat_cast_skips_old_role_ask(book, monkeypatch):
    """旧版扁平 cast.json（只有角色）迁移：标 角色done，不重问角色。"""
    state, tmp = book
    # 新布局：图片在 全书/ 子目录下；path 指向真实文件避免触发重生成
    cast_dir = tmp / dramavideo._ASSET_DIR / dramavideo._ASSET_GLOBAL
    cast_dir.mkdir(parents=True, exist_ok=True)
    cast_file = cast_dir / "cast.json"
    png_path = cast_dir / "林夏.png"
    png_path.write_bytes(b"PNG")
    cast_file.write_text(json.dumps(
        {"林夏": {"appearance": "黑长直", "path": str(png_path)},
         "_appearance_done": True}, ensure_ascii=False), encoding="utf-8")
    asks = []

    def fake_ask(st, sys, user):
        asks.append(sys[:6])
        return "{}"

    monkeypatch.setattr(dramavideo, "_ask", fake_ask)
    monkeypatch.setattr(dramavideo.imggen, "generate_ex",
                        lambda *a, **k: pytest.fail("不应出图（有 path）"))
    cast = dramavideo.build_cast(state)
    assert cast["林夏"]["type"] == "角色"         # 已迁移
    assert all("选角" not in a for a in asks)     # 角色段没重问


def test_build_cast_without_characters_stops(book, monkeypatch):
    state, _ = book
    state["characters"] = ""
    cast_file = book[1] / dramavideo._ASSET_DIR / "cast.json"
    assert not cast_file.exists()
    with pytest.raises(Exception) as ei:
        dramavideo.build_cast(state)
    assert "角色设定" in str(ei.value)


def test_build_shots_clamps_duration_and_caches(book, monkeypatch):
    state, tmp = book
    chapter = {"idx": 1, "title": "两面三刀", "text": "正文……"}

    def fake_ask(st, sys, user):
        assert "旁白" in sys                       # 提示词含旁白要求
        return json.dumps([
            {"title": "搬水", "scene": "宿舍", "characters": ["周妍", "林夏"],
             "description": "中景，平视。周妍费力搬水。",
             "camera": "缓慢推近", "mood": "压抑",
             "narration": "谁也没想到，柔弱舍友藏着心机。",
             "dialogue": "好重", "duration": 99},
            {"title": "相助", "scene": "宿舍", "characters": ["林夏"],
             "description": "近景。林夏拎水。", "dialogue": "",
             "duration": 0.5},
        ], ensure_ascii=False)

    monkeypatch.setattr(dramavideo, "_ask", fake_ask)
    shots = dramavideo.build_shots(state, chapter)
    assert shots[0]["duration"] == dramavideo._MAX_SEC   # 99 → 15
    assert shots[1]["duration"] == dramavideo._MIN_SEC   # 0.5 → 4
    assert shots[0]["narration"] == "谁也没想到，柔弱舍友藏着心机。"
    assert shots[0]["camera"] == "缓慢推近" and shots[0]["mood"] == "压抑"
    # 旧格式（无 camera/mood）不炸：字段为空串
    assert shots[1]["camera"] == "" and shots[1]["mood"] == ""
    # 缓存命中：再跑不再调 LLM
    calls = []
    monkeypatch.setattr(dramavideo, "_ask",
                        lambda *a: calls.append(1) or "{}")
    shots2 = dramavideo.build_shots(state, chapter)
    assert shots2 == shots and not calls


def test_build_shots_locks_era_vocab_to_cast_looks(book, monkeypatch):
    """传入 cast 时：era 词表发给 LLM，分镜阶段名对齐资产形象阶段。"""
    state, tmp = book
    chapter = {"idx": 1, "title": "t", "text": "x"}
    seen = {}

    def fake_ask(st, sys, user):
        seen["sys"] = sys
        return json.dumps([{"title": "a", "scene": "s", "era": "仙侠",
                            "characters": ["王安平"],
                            "description": "d", "narration": "n",
                            "duration": 5}], ensure_ascii=False)

    monkeypatch.setattr(dramavideo, "_ask", fake_ask)
    cast = {"王安平": {"type": "角色", "appearance": "中年",
                     "looks": {"现代": {"appearance": "衬衫"},
                               "仙侠": {"appearance": "道袍"}}}}
    dramavideo.build_shots(state, chapter, cast=cast)
    assert "现代" in seen["sys"] and "仙侠" in seen["sys"]
    assert "必须优先" in seen["sys"]


def test_keyframe_refs_scene_chars_props_and_caches(book, monkeypatch):
    state, tmp = book
    base = tmp / dramavideo._ASSET_DIR
    base.mkdir(parents=True, exist_ok=True)
    refs_src = {}
    for name, fn in (("林夏", "角色"), ("女生宿舍", "场景"), ("水桶", "道具")):
        p = base / f"{name}.png"
        p.write_bytes(b"PNG")
        refs_src[name] = {"type": fn, "appearance": f"{name}外貌",
                          "path": str(p), "url": ""}
    # 路人甲：在出场角色里但没有资产图 → 不进参考
    refs_src["路人甲"] = {"type": "角色", "appearance": "",
                          "path": str(base / "不存在.png"), "url": ""}
    shot = {"title": "搬水", "scene": "女生宿舍", "characters": ["林夏", "路人甲"],
            "description": "近景。林夏拎起水桶。", "dialogue": "", "duration": 5}
    captured = {}

    def fake_gen(prompt, out, size="", ratio="", image_refs=None,
                 want_url=False):
        captured.update(prompt=prompt, ratio=ratio, refs=image_refs,
                        want_url=want_url)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"PNG")
        return out, "http://cdn/frame.png"

    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    path, url = dramavideo.keyframe(state, refs_src, shot, 1, 1)
    assert url == "http://cdn/frame.png"
    # 参考图顺序：场景空镜首位 → 出场且有图的角色 → 文本提到的道具；
    # 路人甲无资产图 → 不进参考
    assert captured["refs"] == [str(base / "女生宿舍.png"),
                                str(base / "林夏.png"),
                                str(base / "水桶.png")]
    assert "林夏外貌" in captured["prompt"]      # 外貌锚嵌入
    assert "场景空镜" in captured["prompt"]       # 提示词说明参考图构成
    assert captured["ratio"] == "9:16" and captured["want_url"] is True
    # URL 落盘，二次调用直接缓存命中（不再生成）
    monkeypatch.setattr(dramavideo.imggen, "generate_ex",
                        lambda *a, **k: pytest.fail("不应再次生成"))
    path2, url2 = dramavideo.keyframe(state, refs_src, shot, 1, 1)
    assert path2 == path and url2 == url


def test_clip_uses_frame_url(book, monkeypatch):
    state, tmp = book
    shot = {"title": "", "scene": "", "characters": [],
            "description": "中景。", "dialogue": "好重", "duration": 6}
    captured = {}

    def fake_video(prompt, out, image="", seconds=0, timeout=0):
        captured.update(prompt=prompt, image=image, seconds=seconds)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"MP4")
        return out

    monkeypatch.setattr(dramavideo.videogen, "generate", fake_video)
    out = dramavideo.clip(state, shot, "http://cdn/frame.png", 1, 1)
    assert captured["image"] == "http://cdn/frame.png"   # 图生视频（一致性传导）
    assert captured["seconds"] == 6 and "好重" in captured["prompt"]
    # 已存在 → 缓存
    monkeypatch.setattr(dramavideo.videogen, "generate",
                        lambda *a, **k: pytest.fail("不应再次生成"))
    assert dramavideo.clip(state, shot, "", 1, 1) == out


def test_clip_dubs_dialogue_with_ffmpeg(book, monkeypatch):
    """有台词：TTS 合成 → ffmpeg 混流替换音轨，原始流删除。"""
    state, tmp = book
    shot = {"title": "", "scene": "", "characters": [],
            "description": "近景。", "dialogue": "小夏，你真好！", "duration": 5}
    state["drama_tts"] = True            # 默认关：开启才走 TTS 配音
    events, dubs, speaks = [], [], []

    def fake_video(prompt, out, image="", seconds=0, timeout=0):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"RAW")
        return out

    def fake_speak(text, out_path, voice=""):
        speaks.append(text)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"MP3")
        return out_path

    monkeypatch.setattr(dramavideo.videogen, "generate", fake_video)
    monkeypatch.setattr("tts.speak", fake_speak)
    monkeypatch.setattr(dramavideo.shutil, "which", lambda n: "ffmpeg")

    def fake_run(cmd, **kw):
        dubs.append(cmd)
        final = cmd[cmd.index("-shortest") + 1]
        with open(final, "wb") as f:
            f.write(b"DUBBED")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(dramavideo.subprocess, "run", fake_run)
    out = dramavideo.clip(
        state, shot, "", 1, 3, on_event=lambda e: events.append(e))
    assert speaks == ["小夏，你真好！"]
    assert dubs and "-shortest" in dubs[0]
    with open(out, "rb") as f:
        assert f.read() == b"DUBBED"
    assert not os.path.exists(out + ".raw.mp4")         # 中间文件已清理
    assert any(e["kind"] == "dub" for e in events)


def test_clip_tts_failure_degrades_to_original(book, monkeypatch):
    """配音失败（无 TTS/无 ffmpeg）：保留模型原声成片，不阻断。"""
    state, tmp = book
    shot = {"title": "", "scene": "", "characters": [],
            "description": "近景。", "dialogue": "台词", "duration": 5}
    state["drama_tts"] = True
    events = []

    def fake_video(prompt, out, image="", seconds=0, timeout=0):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"RAW")
        return out

    def no_speak(*a, **k):
        raise __import__("tts").TTSError("没有可用 TTS")

    monkeypatch.setattr(dramavideo.videogen, "generate", fake_video)
    monkeypatch.setattr("tts.speak", no_speak)
    out = dramavideo.clip(
        state, shot, "", 1, 4, on_event=lambda e: events.append(e))
    assert os.path.exists(out)                          # 原声成片保留
    with open(out, "rb") as f:
        assert f.read() == b"RAW"
    assert any(e["kind"] == "debt" and "配音" in e["label"] for e in events)


def test_concat_requires_ffmpeg(book, monkeypatch):
    monkeypatch.setattr(dramavideo.shutil, "which", lambda name: None)
    with pytest.raises(Exception) as ei:
        dramavideo.concat(["a.mp4"], str(book[1] / "out.mp4"))
    assert "ffmpeg" in str(ei.value)


def test_concat_runs_ffmpeg_and_cleans_list(book, monkeypatch):
    _, tmp = book
    calls = []
    monkeypatch.setattr(dramavideo.shutil, "which", lambda name: "ffmpeg")
    monkeypatch.setattr(dramavideo.subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd)
                        or type("R", (), {"returncode": 0})())
    clips = [str(tmp / "1.mp4"), str(tmp / "2.mp4")]
    out = dramavideo.concat(clips, str(tmp / "ep.mp4"))
    assert out.endswith("ep.mp4")
    assert calls[0][1:4] == ["-y", "-f", "concat"] and "-c" in calls[0]
    assert not os.path.exists(out + ".list.txt")       # 临时清单已清理


def test_run_orchestrates_full_chain(book, monkeypatch):
    state, tmp = book
    state["chapters"] = [{"idx": 1, "title": "两面三刀", "text": "正文"}]
    order = []

    monkeypatch.setattr(dramavideo, "chapter_assets",
                        lambda *a, **k: {})
    monkeypatch.setattr(dramavideo, "build_cast",
                        lambda st, ev=None, stop=None: {"林夏": {
                            "appearance": "黑长直", "path": "", "url": ""}})
    monkeypatch.setattr(
        dramavideo, "build_shots",
        lambda st, c, ev=None, cast=None: [{"title": "t", "scene": "宿舍",
                                 "characters": ["林夏"],
                                 "description": "中景。", "dialogue": "",
                                 "duration": 5}])
    monkeypatch.setattr(dramavideo, "keyframe",
                        lambda st, cast, shot, ch, i, ev=None: (
                            order.append("frame"), ("f.png", "u://f"))[1])
    monkeypatch.setattr(dramavideo, "clip",
                        lambda st, shot, url, ch, i, ev=None: (
                            order.append("clip"), str(tmp / "c.mp4"))[1])
    monkeypatch.setattr(dramavideo, "concat",
                        lambda clips, out: (order.append("concat"), out)[1])
    outs = dramavideo.run(state, 1, 1)
    assert order == ["frame", "clip", "concat"]
    assert outs[0].endswith(".mp4") and "第1章" in outs[0]


def test_run_requires_image_service(book, monkeypatch):
    state, _ = book
    monkeypatch.setattr(dramavideo.imggen, "available", lambda: False)
    state["chapters"] = [{"idx": 1, "title": "x", "text": "y"}]
    with pytest.raises(Exception) as ei:
        dramavideo.run(state, 1, 1)
    assert "图像生成服务" in str(ei.value)


def test_gen_asset_t2i_and_i2i(book, monkeypatch):
    """描述生成=纯文生图；图生图=带当前图为参考+微调提示（更准）。"""
    state, tmp = book
    cur = tmp / dramavideo._ASSET_DIR / "林夏.png"
    cur.parent.mkdir(parents=True, exist_ok=True)
    cur.write_bytes(b"OLD")
    info = {"type": "角色", "appearance": "黑长直", "path": str(cur)}
    captured = {}

    def fake_gen(prompt, out, size="", ratio="", image_refs=None,
                 want_url=False):
        captured.update(prompt=prompt, refs=image_refs, ratio=ratio)
        with open(out, "wb") as f:
            f.write(b"NEW")
        return out, "http://u/x.png"

    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    dramavideo.gen_asset(state, "林夏", dict(info))
    assert not captured["refs"] and "微调" not in captured["prompt"]
    assert captured["ratio"] == "3:4"                     # 角色画幅
    out_info = dramavideo.gen_asset(state, "林夏", dict(info), image_ref=True)
    assert captured["refs"] == [str(cur)]                 # 参考图=当前形象
    assert "主体特征" in captured["prompt"]
    assert out_info["url"] == "http://u/x.png"


def test_gen_asset_custom_prompt_overrides(book, monkeypatch):
    """自填提示词：取代模板/描述成为主体提示词（仍保留风格锚）。"""
    state, tmp = book
    captured = {}

    def fake_gen(prompt, out, size="", ratio="", image_refs=None,
                 want_url=False):
        captured["prompt"] = prompt
        return out, ""

    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    info = {"type": "道具", "appearance": "旧描述", "path": ""}
    dramavideo.gen_asset(state, "搪瓷缸", dict(info),
                         custom_prompt="白色搪瓷缸，缸身印红色奖字，磕碰痕迹")
    p = captured["prompt"]
    assert "白色搪瓷缸" in p and "旧描述" not in p    # 自填提示词生效
    assert dramavideo.DEFAULT_STYLE[:4] in p          # 风格锚保留


def test_replace_asset_image_from_local(book, tmp_path):
    """上传替换：本地图转 PNG 落资产目录，path 指向新文件。"""
    from PIL import Image as PILImage
    state, tmp = book
    src = tmp_path / "my.png"
    PILImage.new("RGB", (64, 64), "#336699").save(src)
    # 新布局：replace_asset_image 落 全书/ 子目录
    out = tmp / dramavideo._ASSET_DIR / dramavideo._ASSET_GLOBAL / "王安平.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    info = {"type": "角色", "appearance": "x"}
    new = dramavideo.replace_asset_image(state, "王安平", info, str(src))
    assert new["path"] == str(out) and out.exists()
    with PILImage.open(out) as im:
        assert im.size == (64, 64)


def test_chapter_assets_and_effective_merge(book, monkeypatch):
    """章节专属资产：分镜引用而全书缺的 → 类型自动判定 + LLM 描述 + 出图。"""
    state, tmp = book
    chapter = {"idx": 2, "title": "外务山", "text": "正文"}
    shots = [
        {"title": "a", "scene": "外务山货栈", "characters": ["林夏", "散修老者"],
         "props": ["储物袋"], "description": "d", "dialogue": "", "duration": 5},
    ]
    cast = {"林夏": {"type": "角色", "appearance": "x", "path": "",
                     "url": ""}}                     # 全书已有林夏
    asks, gens = [], []

    def fake_ask(st, sys, user):
        asks.append(user)
        return '{"外务山货栈": "木架货栈…", "散修老者": "灰袍老者…", "储物袋": "青布袋…"}'

    def fake_gen(prompt, out, size="", ratio="", image_refs=None,
                 want_url=False):
        gens.append((os.path.basename(out), prompt[:10]))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"P")
        return out, ""

    monkeypatch.setattr(dramavideo, "_ask", fake_ask)
    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    local = dramavideo.chapter_assets(state, chapter, shots, cast)
    # 类型按引用位置判定；林夏全书已有 → 不进章节资产
    assert local["外务山货栈"]["type"] == "场景"
    assert local["散修老者"]["type"] == "角色"
    assert local["储物袋"]["type"] == "道具"
    assert "林夏" not in local
    assert len(gens) == 3                          # 三个新资产各出一张图
    # 再次调用：文件缓存命中，不再提取/出图
    monkeypatch.setattr(dramavideo, "_ask",
                        lambda *a: pytest.fail("不应再次提取"))
    monkeypatch.setattr(dramavideo.imggen, "generate_ex",
                        lambda *a, **k: pytest.fail("不应再次出图"))
    assert dramavideo.chapter_assets(state, chapter, shots, cast) == local
    # 合并：本章专属覆盖全书同名
    merged = dramavideo.effective_cast(cast, local)
    assert merged["林夏"] is cast["林夏"]          # 全书资产原样
    assert merged["储物袋"] is local["储物袋"]     # 本章资产并入
    cast2 = dict(cast); cast2["储物袋"] = {"type": "道具", "appearance": "旧"}
    merged2 = dramavideo.effective_cast(cast2, local)
    assert merged2["储物袋"] is local["储物袋"]    # 同名：本章覆盖全书


def test_clip_prompt_separates_visual_and_voice(book, monkeypatch):
    """视频提示词：画面/配音分离——只许念旁白台词，锁中文普通话。"""
    state, tmp = book
    shot = {"title": "", "scene": "", "characters": [],
            "description": "近景，平视机位。50mm焦段。林夏拎水。",
            "narration": "谁也没想到，柔弱舍友藏着心机。",
            "dialogue": "好重", "duration": 5}
    captured = {}

    def fake_video(prompt, out, image="", seconds=0, timeout=0):
        captured["prompt"] = prompt
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"M")
        return out

    monkeypatch.setattr(dramavideo.videogen, "generate", fake_video)
    dramavideo.clip(state, shot, "", 1, 9)
    p = captured["prompt"]
    assert "画面：" in p and "配音要求" in p
    assert "不要朗读" in p and "中文普通话" in p and "不要出现英语" in p
    assert "旁白（第三人称解说，整句朗读）" in p
    assert "台词（角色对白）" in p
    # 无旁白无台词：明确只要环境音
    shot2 = dict(shot, narration="", dialogue="")
    dramavideo.clip(state, shot2, "", 1, 10)
    assert "环境音" in captured["prompt"] and "不要生成任何人声" in captured["prompt"]


def test_clean_text_strips_think_and_fences():
    assert dramavideo._clean_text("<think>推理过程</think>正文内容") == "正文内容"
    # 围栏只剥围栏本身；前 80 字符内的引导语会被剥掉
    assert dramavideo._clean_text("```以下是分镜```") == "分镜"
    # 引导语只剥前 80 字符内的（避免误伤正文中段的「以下是…」「让我…」）
    assert dramavideo._clean_text("好的，以下是分镜正文") == "以下是分镜正文"
    assert dramavideo._clean_text("```json\n以下是分镜\n```") == "分镜"  # 围栏剥后开头仍是「以下是」
    # 中段出现「以下是」不会被错剥
    assert "以下是" in dramavideo._clean_text("开头##\n" + "X" * 90 + "以下是真正的关键词")
    # HTML 标签/多余空白
    assert dramavideo._clean_text("<b>好的</b>正文") == "正文"  # 「好的」被引导语规则吃掉
    assert dramavideo._clean_text("  多  余\n空白\t ") == "多 余 空白"
    assert dramavideo._clean_text("正常描述", 4) == "正常描述"[:4]


def test_resolve_style_fallback_chain(monkeypatch):
    """风格永不空：state → 全局默认 → DEFAULT_STYLE。"""
    assert dramavideo.resolve_style({"drama_style": "  书级风格 "}) == "书级风格"
    import io, json
    # state 没值 → 从全局默认读
    monkeypatch.setattr("config._MODELS_FILE", "/_doesnt_exist_.json")
    fake = {"globals": {"default_drama_style": "全局默认"}}
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: io.StringIO(json.dumps(fake)))
    assert dramavideo.resolve_style({}) == "全局默认"
    # 全局也没 → DEFAULT_STYLE
    def boom(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr("builtins.open", boom)
    assert dramavideo.resolve_style({}) == dramavideo.DEFAULT_STYLE


def test_load_style_lib_seeds_presets(tmp_path, monkeypatch):
    """风格库：models.json 没有 globals 时自动播种全部预设并写回。"""
    mp = tmp_path / "models.json"
    mp.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("config._MODELS_FILE", str(mp))
    styles, default, data, path = dramavideo.load_style_lib()
    assert len(styles) == len(dramavideo.STYLE_PRESETS)
    cats = {s["category"] for s in styles}
    assert {"2D", "3D", "真人"} <= cats
    texts = [s["text"] for s in styles]
    assert any("国漫" in t for t in texts)        # 用户点的国漫/剪纸在库
    assert any("剪纸" in t for t in texts)
    assert default == dramavideo.DEFAULT_STYLE
    # 已写回磁盘：第二次读不重播种、数量一致
    import json as _j
    on_disk = _j.loads(mp.read_text(encoding="utf-8"))
    assert len(on_disk["globals"]["drama_styles"]) == len(styles)
    styles2, _, _, _ = dramavideo.load_style_lib()
    assert [s["text"] for s in styles2] == texts



def test_reset_wipes_drama_outputs_only(book):
    """reset：删光五个短剧目录，小说正文/大纲原样保留。"""
    state, tmp = book
    (tmp / "正文").mkdir(exist_ok=True)
    (tmp / "正文" / "第0001章-x.md").write_text("正文", encoding="utf-8")
    (tmp / "大纲").mkdir(exist_ok=True)
    (tmp / "大纲" / "总纲.md").write_text("纲", encoding="utf-8")
    files = []
    for d, names in ((dramavideo._ASSET_DIR, ["cast.json", "王安平.png"]),
                     (dramavideo._SHOT_DIR, ["第1章.json", "urls.json"]),
                     (dramavideo._FRAME_DIR, ["1-01.png"]),
                     (dramavideo._CLIP_DIR, ["1-01.mp4"]),
                     (dramavideo._OUT_DIR, ["第1章-x.mp4"])):
        sub = tmp / d
        sub.mkdir(parents=True, exist_ok=True)
        for nm in names:
            (sub / nm).write_bytes(b"x")
            files.append(sub / nm)
    n = dramavideo.reset(state)
    assert n == len(files)
    for f in files:
        assert not f.exists()
    assert (tmp / "正文" / "第0001章-x.md").exists()   # 正文不动
    assert (tmp / "大纲" / "总纲.md").exists()
    for d in (dramavideo._ASSET_DIR, dramavideo._SHOT_DIR,
              dramavideo._FRAME_DIR, dramavideo._CLIP_DIR,
              dramavideo._OUT_DIR):
        assert not (tmp / d).exists()                   # 目录清掉

def test_drop_media_targets_chapter_or_shot(book):
    state, tmp = book
    fr = tmp / dramavideo._FRAME_DIR
    cl = tmp / dramavideo._CLIP_DIR
    for d in (fr, cl):
        d.mkdir(parents=True, exist_ok=True)
    for name in ("1-01.png", "1-02.png", "2-01.png"):
        (fr / name).write_bytes(b"x")
    (cl / "1-01.mp4").write_bytes(b"x")
    # 整章删除
    assert dramavideo.drop_media(state, 1) == 3
    assert not (fr / "1-01.png").exists()
    assert (fr / "2-01.png").exists()          # 别章不受影响
    # 单镜删除
    fr2 = tmp / dramavideo._FRAME_DIR / "2-02.png"
    fr2.write_bytes(b"x")
    assert dramavideo.drop_media(state, 2, shot=2) == 1
    assert not fr2.exists()


def test_run_skips_failed_shot_and_concats_rest(book, monkeypatch):
    """单镜失败记质量债继续，末尾只合成已完成片段（不阻断）。"""
    state, tmp = book
    state["chapters"] = [{"idx": 1, "title": "测试", "text": "正文"}]
    events = []
    monkeypatch.setattr(dramavideo, "chapter_assets",
                        lambda *a, **k: {})
    monkeypatch.setattr(dramavideo, "build_cast", lambda st, ev=None, stop=None: {})
    monkeypatch.setattr(
        dramavideo, "build_shots",
        lambda st, c, ev=None, cast=None: [{"title": "a", "scene": "s", "characters": [],
                                 "description": "d", "dialogue": "",
                                 "duration": 5}] * 2)
    monkeypatch.setattr(dramavideo, "keyframe",
                        lambda *a, **k: ("f.png", "u://f"))

    def flaky_clip(st, shot, url, ch, i, ev=None):
        if i == 1:
            raise dramavideo.videogen.VidError("HTTP Error 429")
        return str(tmp / "ok.mp4")

    monkeypatch.setattr(dramavideo, "clip", flaky_clip)
    monkeypatch.setattr(dramavideo, "concat",
                        lambda clips, out: (clips, out)[1])
    outs = dramavideo.run(state, 1, 1,
                          on_event=lambda e: events.append(e))
    assert outs, "有片段就应产出成片"
    kinds = [e["kind"] for e in events]
    assert "debt" in kinds                       # 债务事件已上报
    assert any("重跑" in (e.get("label") or "") for e in events
               if e["kind"] == "debt")


def test_run_all_failed_raises(book, monkeypatch):
    state, _ = book
    state["chapters"] = [{"idx": 1, "title": "x", "text": "y"}]
    monkeypatch.setattr(dramavideo, "chapter_assets",
                        lambda *a, **k: {})
    monkeypatch.setattr(dramavideo, "build_cast", lambda st, ev=None, stop=None: {})
    monkeypatch.setattr(
        dramavideo, "build_shots",
        lambda st, c, ev=None, cast=None: [{"title": "a", "scene": "", "characters": [],
                                 "description": "d", "dialogue": "",
                                 "duration": 5}])
    monkeypatch.setattr(dramavideo, "keyframe",
                        lambda *a, **k: (_ for _ in ()).throw(
                            dramavideo.imggen.ImgError("x")))
    monkeypatch.setattr(dramavideo, "clip",
                        lambda *a, **k: (_ for _ in ()).throw(
                            dramavideo.videogen.VidError("429")))
    with pytest.raises(Exception) as ei:
        dramavideo.run(state, 1, 1)
    assert "都失败" in str(ei.value)


def test_run_redo_drops_existing_media(book, monkeypatch):
    state, tmp = book
    state["chapters"] = [{"idx": 1, "title": "x", "text": "y"}]
    fr = tmp / dramavideo._FRAME_DIR / "1-01.png"
    fr.parent.mkdir(parents=True, exist_ok=True)
    fr.write_bytes(b"old")
    events = []
    monkeypatch.setattr(dramavideo, "chapter_assets",
                        lambda *a, **k: {})
    monkeypatch.setattr(dramavideo, "build_cast", lambda st, ev=None, stop=None: {})
    monkeypatch.setattr(
        dramavideo, "build_shots",
        lambda st, c, ev=None, cast=None: [{"title": "a", "scene": "", "characters": [],
                                 "description": "d", "dialogue": "",
                                 "duration": 5}])
    monkeypatch.setattr(dramavideo, "keyframe",
                        lambda *a, **k: ("f.png", ""))
    monkeypatch.setattr(dramavideo, "clip", lambda *a, **k: "c.mp4")
    monkeypatch.setattr(dramavideo, "concat", lambda clips, out: out)
    dramavideo.run(state, 1, 1, redo=True,
                   on_event=lambda e: events.append(e))
    assert any(e["kind"] == "redo" for e in events)
    assert not fr.exists()                       # 旧产物已删，走重新生成


def test_build_cast_multi_era_looks(book, monkeypatch):
    """跨时代角色：提取多阶段形象并逐套出图（默认套复用主图名）。"""
    state, tmp = book
    gens = []

    def fake_ask(st, sys, user):
        if "选角导演" in sys:
            return json.dumps({"王安平": {"现代": "灰色格子衬衫，双肩包，程序员",
                                          "仙侠": "青布道袍，束发木簪"}}, ensure_ascii=False)
        return "{}"

    def fake_gen(prompt, out, size="", ratio="", image_refs=None, want_url=False):
        gens.append({"name": os.path.basename(out), "xianxia": "仙侠" in prompt,
                     "same": "同一人物" in prompt, "refs": image_refs,
                     "out": out, "prompt": prompt})
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"P")
        return out, "http://u"

    monkeypatch.setattr(dramavideo, "_ask", fake_ask)
    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    cast = dramavideo.build_cast(state)
    info = cast["王安平"]
    assert set(info["looks"]) == {"现代", "仙侠"}
    # 主图 + 仙侠套各一张；仙侠套提示词含阶段与「同一人物」锚
    names = [g["name"] for g in gens]
    assert "王安平.png" in names and "王安平-仙侠.png" in names
    extra = next(g for g in gens if g["name"] == "王安平-仙侠.png")
    main = next(g for g in gens if g["name"] == "王安平.png")
    assert extra["xianxia"] and extra["same"]
    # 脸链：仙侠套以默认套主图为参考图（图生图锁脸，不靠文字）
    assert extra["refs"] == [main["out"]]
    assert "严格保持参考图的脸型五官" in extra["prompt"]
    # 默认套（现代）复用主图路径
    assert info["looks"]["现代"]["path"].endswith("王安平.png")
    assert info["looks"]["仙侠"]["path"].endswith("王安平-仙侠.png")


def test_keyframe_picks_look_by_era(book, monkeypatch):
    """关键帧按镜头 era 选形象：仙侠镜用仙侠装参考图，无 era 用默认。"""
    state, tmp = book
    base = tmp / dramavideo._ASSET_DIR / dramavideo._ASSET_GLOBAL
    base.mkdir(parents=True, exist_ok=True)
    modern = base / "王安平.png"; modern.write_bytes(b"M")
    xianxia = base / "王安平-仙侠.png"; xianxia.write_bytes(b"X")
    cast = {"王安平": {
        "type": "角色", "appearance": "现代装",
        "path": str(modern),
        "looks": {"现代": {"appearance": "格子衫", "path": str(modern)},
                  "仙侠": {"appearance": "青布道袍", "path": str(xianxia)}}}}
    captured = {}

    def fake_gen(prompt, out, size="", ratio="", image_refs=None, want_url=False):
        captured["refs"] = image_refs
        captured["prompt"] = prompt
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"F")
        return out, "u"

    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    shot_x = {"title": "t", "scene": "外务山", "era": "仙侠",
              "characters": ["王安平"], "props": [],
              "description": "中景。", "narration": "", "dialogue": "",
              "duration": 5}
    dramavideo.keyframe(state, cast, shot_x, 1, 1)
    assert str(xianxia) in captured["refs"]          # 仙侠镜 → 仙侠装
    assert "青布道袍" in captured["prompt"] and "仙侠" in captured["prompt"]
    # 无 era / era 未收录 → 默认套
    shot_m = dict(shot_x, era="", scene="智术科技园区")
    (tmp / dramavideo._FRAME_DIR / "1-02.png").unlink(missing_ok=True)
    dramavideo.keyframe(state, cast, shot_m, 1, 2)
    assert str(modern) in captured["refs"]
    # era 措辞偏差（「仙侠历练期」）→ 包含式模糊匹配命中「仙侠」装
    shot_f = dict(shot_x, era="仙侠历练期")
    (tmp / dramavideo._FRAME_DIR / "1-03.png").unlink(missing_ok=True)
    dramavideo.keyframe(state, cast, shot_f, 1, 3)
    assert str(xianxia) in captured["refs"]


def test_chapter_assets_reuse_across_chapters(book, monkeypatch):
    """跨章一致性：同名章节资产在别章出过图 → 直接沿用，不再重画。"""
    import shutil
    state, tmp = book
    # 第 2 章已有「散修老者」形象
    ch2_dir = tmp / dramavideo._ASSET_DIR / "第2章"
    ch2_dir.mkdir(parents=True, exist_ok=True)
    old_png = ch2_dir / "散修老者.png"
    old_png.write_bytes(b"FACE")
    dramavideo._json_dump(str(ch2_dir / "assets.json"), {
        "散修老者": {"type": "角色", "appearance": "灰袍",
                     "path": str(old_png), "url": ""}, "_done": True})
    shots = [{"title": "t", "scene": "", "era": "",
              "characters": ["散修老者"], "props": [],
              "description": "d", "narration": "", "dialogue": "",
              "duration": 5}]
    asked = []
    monkeypatch.setattr(dramavideo, "_ask",
                        lambda *a: asked.append(1) or "{}")
    monkeypatch.setattr(dramavideo.imggen, "generate_ex",
                        lambda *a, **k: pytest.fail("复用不应再出图"))
    local = dramavideo.chapter_assets(
        state, {"idx": 5, "title": "x", "text": "y"}, shots, {})
    assert local["散修老者"]["path"] == str(old_png)   # 沿用第2章的图
    assert not asked                                    # 也没问 LLM


def test_keyframe_force_regenerates_existing(book, monkeypatch):
    """force=True 无视「文件存在即缓存」：重出图并更新 urls.json。"""
    state, tmp = book
    frame_dir = tmp / dramavideo._FRAME_DIR
    frame_dir.mkdir(parents=True, exist_ok=True)
    old = frame_dir / "1-01.png"
    old.write_bytes(b"OLD")
    dramavideo._json_dump(dramavideo._urls_path(state), {"1-01": "http://old"})
    shot = {"title": "", "scene": "", "characters": [],
            "description": "近景。", "dialogue": "", "duration": 5}
    calls = []

    def fake_gen(prompt, out, size="", ratio="", image_refs=None,
                 want_url=False):
        calls.append(out)
        with open(out, "wb") as f:
            f.write(b"NEW")
        return out, "http://new/frame.png"

    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    path, url = dramavideo.keyframe(state, {}, shot, 1, 1, force=True)
    assert calls == [str(old)]                     # 真的重生成了
    assert url == "http://new/frame.png"
    assert old.read_bytes() == b"NEW"
    assert dramavideo._json_load(
        dramavideo._urls_path(state), {})["1-01"] == "http://new/frame.png"
    # 不带 force → 缓存命中，直接返回（path+新 URL）
    monkeypatch.setattr(dramavideo.imggen, "generate_ex",
                        lambda *a, **k: pytest.fail("不应再次生成"))
    path2, url2 = dramavideo.keyframe(state, {}, shot, 1, 1)
    assert path2 == str(old) and url2 == "http://new/frame.png"


def test_clip_force_regenerates_existing(book, monkeypatch):
    """force=True 无视缓存重出视频；不带 force 命中缓存不再生成。"""
    state, tmp = book
    clip_dir = tmp / dramavideo._CLIP_DIR
    clip_dir.mkdir(parents=True, exist_ok=True)
    old = clip_dir / "1-01.mp4"
    old.write_bytes(b"OLD")
    shot = {"title": "", "scene": "", "characters": [],
            "description": "中景。", "dialogue": "", "duration": 5}
    calls = []

    def fake_video(prompt, out, image="", seconds=0, timeout=0):
        calls.append(out)
        with open(out, "wb") as f:
            f.write(b"NEW")
        return out

    monkeypatch.setattr(dramavideo.videogen, "generate", fake_video)
    out = dramavideo.clip(state, shot, "", 1, 1, force=True)
    assert calls == [str(old)]
    assert old.read_bytes() == b"NEW"
    monkeypatch.setattr(dramavideo.videogen, "generate",
                        lambda *a, **k: pytest.fail("不应再次生成"))
    assert dramavideo.clip(state, shot, "", 1, 1) == out


def test_gen_asset_fallback_dir_for_pathless_asset(book, monkeypatch):
    """无 path 的资产（章节专属）生成到 fallback_dir，而不是全书目录；
    返回的 info 必须带新 path/url（调用方靠它回写 store）。"""
    state, tmp = book
    ch_dir = tmp / dramavideo._ASSET_DIR / "第3章"
    ch_dir.mkdir(parents=True, exist_ok=True)

    def fake_gen(prompt, out, size="", ratio="", image_refs=None,
                 want_url=False):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"PNG")
        return out, "http://cdn/x.png"

    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    info = dramavideo.gen_asset(state, "水桶", {"type": "道具",
                                                "appearance": "木桶"},
                                fallback_dir=str(ch_dir))
    assert os.path.dirname(info["path"]) == str(ch_dir)   # 落在章节目录
    assert os.path.exists(info["path"]) and info["url"] == "http://cdn/x.png"


def test_gen_look_locks_face_to_main_image(book, monkeypatch):
    """阶段形象重生成：主图作参考图（脸由图像锁定），出图落阶段专属文件。"""
    state, tmp = book
    base = tmp / dramavideo._ASSET_DIR / dramavideo._ASSET_GLOBAL
    base.mkdir(parents=True, exist_ok=True)
    main = base / "林夏.png"
    main.write_bytes(b"MAIN")
    info = {"type": "角色", "appearance": "林夏现代装",
            "path": str(main), "url": "",
            "looks": {"现代": {"appearance": "现代装", "path": str(main)},
                      "古装": {"appearance": "古装}"}}}
    captured = {}

    def fake_gen(prompt, out, size="", ratio="", image_refs=None,
                 want_url=False):
        captured.update(prompt=prompt, refs=image_refs, out=out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"PNG")
        return out, "http://cdn/look.png"

    monkeypatch.setattr(dramavideo.imggen, "generate_ex", fake_gen)
    lk = dramavideo.gen_look(state, "林夏", info, "古装")
    assert captured["refs"] == [str(main)]            # 主图锁脸
    assert "古装" in captured["prompt"] and "古装}" in captured["prompt"]
    assert "脸型五官" in captured["prompt"]            # 锁脸约束提示词
    assert lk["path"].endswith("林夏-古装.png") and os.path.exists(lk["path"])
    assert lk["url"] == "http://cdn/look.png"


def test_gen_clip_take_accumulates_and_select(book, monkeypatch):
    """抽卡：每次生成独立 take（主成片不动）；采用=拷贝覆盖主文件。"""
    state, tmp = book
    shot = {"title": "", "scene": "", "characters": [],
            "description": "中景。", "dialogue": "", "duration": 5}
    monkeypatch.setattr(dramavideo.videogen, "generate", fake_video_bytes)

    t1 = dramavideo.gen_clip_take(state, shot, "http://cdn/f.png", 1, 4)
    t2 = dramavideo.gen_clip_take(state, shot, "http://cdn/f.png", 1, 4)
    assert t1.endswith("1-04-take1.mp4") and t2.endswith("1-04-take2.mp4")
    takes = dramavideo.list_takes(state, 1, 4)
    assert [n for n, _ in takes] == [1, 2]
    canon = os.path.join(tmp, dramavideo._CLIP_DIR, "1-04.mp4")
    assert not os.path.exists(canon)              # 抽卡不动主成片

    dramavideo.select_clip_take(state, 1, 4, t2)
    assert os.path.exists(canon)
    assert open(canon, "rb").read() == open(t2, "rb").read()
    assert len(dramavideo.list_takes(state, 1, 4)) == 2   # take 保留可回选
    # 选主文件自身 = 无操作
    dramavideo.select_clip_take(state, 1, 4, canon)


def test_take_thumb_degrades_without_ffmpeg(book, monkeypatch):
    """无 ffmpeg：缩略图返回空串不抛错（预览降级为文字）。"""
    monkeypatch.setattr(dramavideo.shutil, "which", lambda n: None)
    assert dramavideo.take_thumb("x.mp4", "out.png") == ""


def test_take_thumb_uses_ffmpeg(book, monkeypatch, tmp_path):
    ran = {}

    def fake_run(cmd, **kw):
        ran["cmd"] = cmd
        with open(cmd[-1], "wb") as f:
            f.write(b"PNG")
        return 0

    monkeypatch.setattr(dramavideo.shutil, "which", lambda n: "ffmpeg")
    monkeypatch.setattr(dramavideo.subprocess, "run", fake_run)
    out = tmp_path / "thumb.png"
    assert dramavideo.take_thumb("x.mp4", str(out)) == str(out)
    assert ran["cmd"][-2:] == ["1", str(out)]     # -frames:v 1


def fake_video_bytes(prompt, out, image="", seconds=0, timeout=0):
    """抽卡测试共用：写盘模拟视频产物，按 out 内容区分。"""
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write(b"MP4:" + out.encode().split(b"\\")[-1])
    return out
