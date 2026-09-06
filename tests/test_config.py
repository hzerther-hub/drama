# -*- coding: utf-8 -*-
"""config.py：配置目录、工作区状态、models.json、语言设置。"""

import os

import config


def test_config_dir_points_to_local_ai_studio():
    # conftest 已把 HOME/APPDATA 重定向到临时目录
    assert config.CONFIG_DIR.endswith("local-ai-studio")
    assert config._STATE_FILE == os.path.join(config.CONFIG_DIR, "state.json")


def test_workspace_state_roundtrip(tmp_path):
    d = str(tmp_path / "proj")
    os.makedirs(d)
    config.save_last_workspace(d)
    assert config._load_last_workspace() == d


def test_load_last_workspace_falls_back_when_missing(tmp_path):
    config.save_last_workspace(str(tmp_path / "does-not-exist"))
    # 目录不存在 → 回退到家目录（测试环境下为临时目录，存在）
    assert config._load_last_workspace() == os.path.expanduser("~")


def test_models_data_roundtrip():
    data = config._load_models_data()
    assert isinstance(data.get("providers"), list)
    data["default"] = "test-provider/test-model"
    config._save_models_data(data)
    assert config._load_models_data()["default"] == "test-provider/test-model"


def test_language_roundtrip():
    old = config.get_language()
    try:
        config.set_language("zh")
        assert config.get_language() == "zh"
        config.set_language("en")
        assert config.get_language() == "en"
    finally:
        config.set_language(old)


def test_model_config_defaults():
    m = config.ModelConfig(key="p/m", provider_name="p", model_id="m",
                           display_name="M", base_url="http://x", api_key="k")
    assert m.vision is False
    assert m.reasoning_effort == ""
    assert m.reasoning_choices == ()


def test_font_size_defaults_and_clamp():
    old_c, old_e = config.get_font_size_chat(), config.get_font_size_editor()
    try:
        assert config.get_font_size_chat() == 10     # 默认
        assert config.get_font_size_editor() == 10
        config.set_font_size_chat(13)
        config.set_font_size_editor(9)
        assert config.get_font_size_chat() == 13
        assert config.get_font_size_editor() == 9
        # 越界收敛到 [8, 24]
        config.set_font_size_chat(99)
        config.set_font_size_editor(1)
        assert config.get_font_size_chat() == 24
        assert config.get_font_size_editor() == 8
    finally:
        config.set_font_size_chat(old_c)
        config.set_font_size_editor(old_e)


# ============== Provider CRUD / 重命名 / 唯一性 ==============

def _seed_providers(monkeypatch, providers):
    """让 _load_models_data 返回同一份 providers 列表引用，便于测试断言。"""
    state = {"data": {"providers": list(providers), "default": ""}}
    monkeypatch.setattr(config, "_load_models_data", lambda: state["data"])
    monkeypatch.setattr(config, "_save_models_data",
                        lambda data: state["data"].update(data))
    return state


def test_rename_provider_success(monkeypatch):
    state = _seed_providers(monkeypatch, [
        {"id": "p1", "name": "Original", "base_url": "x", "api_key": "k",
         "api_type": "openai_compatible", "models": [
             {"id": "m1", "name": "M1"}]},
        {"id": "p2", "name": "Other", "base_url": "y", "api_key": "k",
         "api_type": "openai_compatible", "models": []},
    ])
    err = config.rename_provider("p1", "New Name")
    assert err is None
    provs = state["data"]["providers"]
    assert provs[0]["name"] == "New Name"
    # 改名不污染其它 provider
    assert provs[1]["name"] == "Other"


def test_rename_provider_collision(monkeypatch):
    state = _seed_providers(monkeypatch, [
        {"id": "p1", "name": "Original", "base_url": "x", "api_key": "k",
         "api_type": "openai_compatible", "models": []},
        {"id": "p2", "name": "Other", "base_url": "y", "api_key": "k",
         "api_type": "openai_compatible", "models": []},
    ])
    err = config.rename_provider("p1", "Other")
    assert err is not None and "Other" in err
    # 原始 name 未变
    assert state["data"]["providers"][0]["name"] == "Original"


def test_rename_provider_gpulocal_refused(monkeypatch):
    # gpulocal 本地功能已移除：遗留条目允许正常重命名（sync 不存在，不会被覆盖）
    state = _seed_providers(monkeypatch, [
        {"id": "gpulocal-8080", "name": "GPU Local", "base_url": "x",
         "api_key": "local-noauth", "api_type": "openai_compatible",
         "models": []},
    ])
    err = config.rename_provider("gpulocal-8080", "Renamed GPU")
    assert err is None
    assert state["data"]["providers"][0]["name"] == "Renamed GPU"


def test_update_provider_full_edit(monkeypatch):
    state = _seed_providers(monkeypatch, [
        {"id": "p1", "name": "Old", "base_url": "http://old/v1",
         "api_key": "sk-old", "api_type": "openai_compatible",
         "models": [{"id": "m1", "name": "M1"}]},
        {"id": "gpulocal-x", "name": "GPU", "base_url": "",
         "api_key": "local-noauth", "api_type": "openai_compatible",
         "models": []},
    ])
    # 全字段编辑
    err = config.update_provider(
        "p1", name="New", base_url="http://new/v1/",
        api_key="sk-new", api_type="anthropic")
    assert err is None
    p = state["data"]["providers"][0]
    assert p["name"] == "New"
    assert p["base_url"] == "http://new/v1"        # 尾斜杠剥掉
    assert p["api_key"] == "sk-new"
    assert p["api_type"] == "anthropic"
    # 部分编辑：None 字段不动；空 api_key 回落 local-noauth
    assert config.update_provider("p1", api_key="") is None
    assert state["data"]["providers"][0]["api_key"] == "local-noauth"
    assert config.update_provider("p1", name=None, base_url=None) is None
    assert state["data"]["providers"][0]["name"] == "New"
    # gpulocal-* 遗留条目同样可编辑
    assert config.update_provider("gpulocal-x", name="GPU") is None
    # 名字冲突仍拦
    state2 = _seed_providers(monkeypatch, [
        {"id": "a", "name": "Alpha", "base_url": "", "api_key": "",
         "api_type": "openai_compatible", "models": []},
        {"id": "b", "name": "Beta", "base_url": "", "api_key": "",
         "api_type": "openai_compatible", "models": []},
    ])
    assert config.update_provider("b", name="Alpha") is not None
    assert state2["data"]["providers"][1]["name"] == "Beta"


def test_rename_provider_missing(monkeypatch):
    _seed_providers(monkeypatch, [
        {"id": "p1", "name": "X", "base_url": "", "api_key": "",
         "api_type": "openai_compatible", "models": []},
    ])
    err = config.rename_provider("ghost", "Whatever")
    assert err is not None


def test_rename_provider_empty(monkeypatch):
    state = _seed_providers(monkeypatch, [
        {"id": "p1", "name": "X", "base_url": "", "api_key": "",
         "api_type": "openai_compatible", "models": []},
    ])
    assert config.rename_provider("p1", "   ") is not None
    assert state["data"]["providers"][0]["name"] == "X"


def test_add_provider_uniqueness_and_validity(monkeypatch):
    state = _seed_providers(monkeypatch, [
        {"id": "p1", "name": "First", "base_url": "", "api_key": "",
         "api_type": "openai_compatible", "models": []},
    ])

    # id 冲突
    assert "id" in (config.add_provider("p1", "Anything") or "")
    # name 冲突
    assert "First" in (config.add_provider("p2", "First") or "")
    # 非法 id
    assert config.add_provider("Bad ID!", "Cool") is not None
    # gpulocal 拒绝
    assert "gpulocal" in (config.add_provider("gpulocal-9999", "X") or "")
    # 成功
    assert config.add_provider("p2", "Second") is None
    assert any(p["id"] == "p2" for p in state["data"]["providers"])


def test_delete_provider_cascades_models(monkeypatch):
    state = _seed_providers(monkeypatch, [
        {"id": "p1", "name": "X", "base_url": "", "api_key": "",
         "api_type": "openai_compatible", "models": [
             {"id": "m1", "name": "M1"},
             {"id": "m2", "name": "M2"}]},
        {"id": "gpulocal-x", "name": "GPU", "base_url": "",
         "api_key": "local-noauth", "api_type": "openai_compatible",
         "models": []},
    ])
    # gpulocal-* 遗留条目允许删除（功能已移除，无 sync 覆盖）
    assert config.delete_provider("gpulocal-x") is True
    # 普通 provider 级联删除
    assert config.delete_provider("p1") is True
    ids = {p["id"] for p in state["data"]["providers"]}
    assert "p1" not in ids and "gpulocal-x" not in ids


def test_check_provider_uniqueness_helper():
    data = {"providers": [
        {"id": "a", "name": "Alpha"},
        {"id": "b", "name": "Beta"},
    ]}
    assert config._check_provider_uniqueness(data) is None
    assert config._check_provider_uniqueness(data, new_id="a") is not None
    assert config._check_provider_uniqueness(data, new_name="Alpha") is not None
    # 排除自己
    assert config._check_provider_uniqueness(
        data, exclude_id="a", new_id="a") is None
    assert config._check_provider_uniqueness(
        data, exclude_id="a", new_name="Alpha") is None
