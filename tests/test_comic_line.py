"""漫画支线单元测试：镜像形象 / 分格改编 / 单格出图 / 整章编排。"""
import json
import pathlib
import threading

import pytest

import dramavideo


@pytest.fixture
def book(tmp_path, monkeypatch):
    """临时书目录 + 禁用真实生成网络（与 test_dramavideo 同款隔离）。"""
    monkeypatch.setattr(dramavideo, "_book_dir", lambda state: str(tmp_path))
    monkeypatch.setattr(dramavideo.imggen, "available", lambda: True)
    state = {"pid": "novel-t", "title": "测试书",
             "characters": "## 主角：林夏\n善良大学生。"}
    return state, tmp_path


def _write_cast(state, cast):
    cast_path = pathlib.Path(dramavideo._global_cast_path(state))
    cast_path.parent.mkdir(parents=True, exist_ok=True)
    cast_path.write_text(json.dumps(cast, ensure_ascii=False),
                         encoding="utf-8")


def _fake_gen(calls):
    def fake(prompt, out, size="", ratio="", image_refs=None,
             want_url=False, **kw):
        calls.append({"prompt": prompt, "out": str(out),
                      "refs": list(image_refs or []),
                      "size": size, "ratio": ratio})
        target = pathlib.Path(out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"")
        return str(out), ""
    return fake


# ---------------- gen_asset_comic：镜像不碰主图 ----------------

def test_gen_asset_comic_mirror_keeps_main_intact(book, monkeypatch):
    """漫画镜像只写 comic_path，剧模式主图 path/url 不动；参考图锁特征。"""
    state, tmp = book
    ref_png = tmp / "lin.png"
    ref_png.write_bytes(b"x")
    info = {"type": "角色", "appearance": "黑长直", "path": str(ref_png),
            "url": "http://x/lin.png"}
    seen = []
    monkeypatch.setattr(dramavideo.imggen, "generate_ex", _fake_gen(seen))
    out = dramavideo.gen_asset_comic(state, "林夏", info)
    assert out["path"] == str(ref_png) and out["url"] == "http://x/lin.png"
    assert out["comic_path"].endswith("-comic.png")
    assert seen[0]["refs"] == [str(ref_png)]       # 以剧装图为参考锁特征
    assert "漫画" in seen[0]["prompt"]


def test_gen_asset_comic_era_returns_look(book, monkeypatch):
    """era 分支返回阶段 look 字典（调用方写回），不污染主条目。"""
    state, tmp = book
    info = {"type": "角色", "appearance": "黑长直",
            "looks": {"古装": {"path": "", "appearance": "白衣"}}}
    monkeypatch.setattr(dramavideo.imggen, "generate_ex", _fake_gen([{}]))
    lk = dramavideo.gen_asset_comic(state, "林夏", info, era="古装")
    assert "comic_path" in lk
    assert "comic_path" not in info                 # 主条目未被写


# ---------------- _comic_visual：取图优先级 ----------------

def test_comic_visual_prefers_comic_then_falls_back():
    """era 漫画套 → 主条目漫画图 → era 剧装 → 主条目。"""
    era_comic = {"path": "d.png",
                 "looks": {"现代": {"path": "e.png", "comic_path": "ec.png"}}}
    assert dramavideo._comic_visual(era_comic, "现代")["comic_path"] == "ec.png"
    vis = dramavideo._comic_visual(era_comic)      # 无 era：回退主条目剧装图
    assert (vis.get("comic_path") or vis.get("path")) == "d.png"
    era_only = {"path": "d.png", "looks": {"现代": {"path": "e.png"}}}
    assert dramavideo._comic_visual(era_only, "现代")["path"] == "e.png"
    plain = {"path": "d.png"}
    assert dramavideo._comic_visual(plain, "现代")["path"] == "d.png"


# ---------------- build_comic_panels：改编与缓存 ----------------

def _panel_json(n=9):
    return json.dumps([
        {"title": f"格{i}", "description": f"画面内容{i}，" * 8,
         "image_prompt": f"中景构图{i}", "dialogue": "",
         "scene": "女生宿舍", "characters": ["林夏"], "props": [],
         "era": "现代"} for i in range(1, n + 1)], ensure_ascii=False)


def test_build_comic_panels_parses_and_caches(book, monkeypatch):
    """LLM JSON → 清洗分格列表并落盘缓存；二次调用读缓存，redo 才重改编。"""
    state, tmp = book
    chapter = {"idx": 1, "title": "测试章", "text": "正文"}
    asks = {"n": 0}

    def fake_ask(st, s, u):
        asks["n"] += 1
        return _panel_json(9)

    monkeypatch.setattr(dramavideo, "_ask", fake_ask)
    panels = dramavideo.build_comic_panels(state, chapter, {})
    assert len(panels) == 9
    assert panels[0]["scene"] == "女生宿舍"
    assert panels_path(state, 1).is_file()

    assert dramavideo.build_comic_panels(state, chapter, {}) == panels
    assert asks["n"] == 1                            # 缓存命中：不再调 LLM
    redo = dramavideo.build_comic_panels(state, chapter, {}, redo=True)
    assert len(redo) == 9 and asks["n"] == 2         # redo 重新改编


def panels_path(state, ch):
    return (pathlib.Path(dramavideo._book_dir(state))
            / dramavideo._COMIC_DIR / f"第{ch}章.json")


def test_build_comic_panels_empty_raises(book, monkeypatch):
    """LLM 未返回 JSON 时报可读错误。"""
    state, tmp = book
    monkeypatch.setattr(dramavideo, "_ask", lambda st, s, u: "不是 JSON")
    with pytest.raises(Exception) as ei:
        dramavideo.build_comic_panels(
            state, {"idx": 2, "title": "t", "text": "x"}, {})
    assert "漫画分格" in str(ei.value)


# ---------------- comic_panel_image：装配顺序与缓存 ----------------

def test_comic_panel_image_scene_first_and_caches(book, monkeypatch):
    """参考图场景首位；出图后缓存命中不再调用生成。"""
    state, tmp = book
    scene_png = tmp / "宿舍.png"
    scene_png.write_bytes(b"s")
    role_png = tmp / "lin.png"
    role_png.write_bytes(b"c")
    cast = {"女生宿舍": {"type": "场景", "appearance": "四人间",
                         "path": str(scene_png)},
            "林夏": {"type": "角色", "appearance": "黑长直",
                     "path": str(role_png)}}
    panel = {"title": "格1", "description": "她推门而入",
             "image_prompt": "中景，推门瞬间", "dialogue": "",
             "scene": "女生宿舍", "characters": ["林夏"], "props": [],
             "era": ""}
    calls = []
    monkeypatch.setattr(dramavideo.imggen, "generate_ex", _fake_gen(calls))
    out = dramavideo.comic_panel_image(state, cast, panel, 1, 1)
    assert str(out).endswith("1-01.png")
    assert calls and calls[0]["refs"][0] == str(scene_png)  # 场景首位
    assert str(role_png) in calls[0]["refs"]
    assert calls[0]["size"] == dramavideo._drama_sizes()[3]  # 漫画档位

    def boom(*a, **k):
        raise AssertionError("缓存命中不应再出图")

    monkeypatch.setattr(dramavideo.imggen, "generate_ex", boom)
    assert dramavideo.comic_panel_image(state, cast, panel, 1, 1) == out


# ---------------- run_comic：整章编排 ----------------

def test_run_comic_generates_mirrors_panels_images(book, monkeypatch):
    """整章跑：镜像形象补齐 → 分格落盘 → 逐格出图。"""
    state, tmp = book
    state["chapters"] = [{"idx": 1, "title": "测试章", "text": "正文内容"}]
    scene_png = tmp / "宿舍.png"
    scene_png.write_bytes(b"s")
    _write_cast(state, {"女生宿舍": {"type": "场景", "appearance": "四人间",
                                     "path": str(scene_png)}})
    monkeypatch.setattr(dramavideo, "_ask",
                        lambda st, s, u: _panel_json(3))
    calls = []
    monkeypatch.setattr(dramavideo.imggen, "generate_ex", _fake_gen(calls))
    out_cast = dramavideo.run_comic(state, 1)
    comic_dir = (pathlib.Path(dramavideo._book_dir(state))
                 / dramavideo._COMIC_DIR)
    assert (comic_dir / "第1章.json").is_file()
    assert (comic_dir / "1-01.png").is_file()
    assert (comic_dir / "1-03.png").is_file()
    assert out_cast["女生宿舍"]["comic_path"]        # 场景镜像已生成
    assert any("场景" in c["prompt"] for c in calls)  # 镜像生成走过场景模板


def test_run_comic_empty_cast_raises(book):
    """资产库为空时给出可操作的报错。"""
    state, tmp = book
    state["chapters"] = [{"idx": 1, "title": "t", "text": "x"}]
    with pytest.raises(Exception) as ei:
        dramavideo.run_comic(state, 1)
    assert "资产库为空" in str(ei.value)


def test_run_comic_respects_stop_flag(book, monkeypatch):
    """stop 置位时中断且保留已完成产物。"""
    state, tmp = book
    state["chapters"] = [{"idx": 1, "title": "t", "text": "x"}]
    _write_cast(state, {"女生宿舍": {"type": "场景", "appearance": "四人间",
                                     "path": ""}})
    monkeypatch.setattr(dramavideo, "_ask",
                        lambda st, s, u: _panel_json(2))
    monkeypatch.setattr(dramavideo.imggen, "generate_ex", _fake_gen([{}]))
    stop = threading.Event()
    stop.set()
    with pytest.raises(Exception):
        dramavideo.run_comic(state, 1, stop=stop)
