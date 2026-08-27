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
