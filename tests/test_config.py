# -*- coding: utf-8 -*-
"""config.py：配置目录、工作区状态、models.json、语言设置。"""

import json
import os

import pytest

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
         "api_key": "本地免鉴权占位", "api_type": "openai_compatible",
         "models": []},
    ])
    err = config.rename_provider("gpulocal-8080", "Renamed GPU")
    assert err is None
    assert state["data"]["providers"][0]["name"] == "Renamed GPU"


def test_update_provider_full_edit(monkeypatch):
    state = _seed_providers(monkeypatch, [
        {"id": "p1", "name": "Old", "base_url": "http://old/v1",
         "api_key": "旧key占位", "api_type": "openai_compatible",
         "models": [{"id": "m1", "name": "M1"}]},
        {"id": "gpulocal-x", "name": "GPU", "base_url": "",
         "api_key": "本地免鉴权占位", "api_type": "openai_compatible",
         "models": []},
    ])
    # 全字段编辑
    err = config.update_provider(
        "p1", name="New", base_url="http://new/v1/",
        api_key="新key占位", api_type="anthropic")
    assert err is None
    p = state["data"]["providers"][0]
    assert p["name"] == "New"
    assert p["base_url"] == "http://new/v1"        # 尾斜杠剥掉
    assert p["api_key"] == "新key占位"
    assert p["api_type"] == "anthropic"
    # 部分编辑：None 字段不动；空 api_key 回落 local-noauth 哨兵
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
         "api_key": "本地免鉴权占位", "api_type": "openai_compatible",
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



# ============== 用户可编辑 JSON 损坏时的容错 ==============
# models.json / state.json / mcp.json 都是用户可手改的文件。旧实现在「顶层不是
# 对象」（数组/null/数字，都是合法 JSON 但不是配置对象）或「非 UTF-8」时抛
# AttributeError / UnicodeDecodeError：读 state.json 的那次在模块级执行
# （config.WORKSPACE = _load_last_workspace()），会让整个应用起不来。

class TestMalformedConfigFiles:
    @pytest.fixture(autouse=True)
    def isolated_files(self, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "_STATE_FILE", str(tmp_path / "state.json"))
        monkeypatch.setattr(config, "_MODELS_FILE", str(tmp_path / "models.json"))
        monkeypatch.setattr(config, "MCP_FILE", str(tmp_path / "mcp.json"))
        self.tmp = tmp_path
        return tmp_path

    def _write(self, name, raw):
        (self.tmp / name).write_bytes(raw)

    # ---------------- state.json（启动路径） ----------------
    @pytest.mark.parametrize("raw", [
        b"[1,2]", b"null", b"123", b'"ws"', b"{bad json",
        '{"workspace": "内存"}'.encode("gbk"),
    ])
    def test_broken_state_json_falls_back_to_home(self, raw):
        self._write("state.json", raw)
        assert config._load_last_workspace() == os.path.expanduser("~")

    @pytest.mark.parametrize("raw", [b"[1,2]", b"null", b'"x"', b"{bad"])
    def test_save_workspace_survives_broken_state_json(self, raw, tmp_path):
        self._write("state.json", raw)
        d = str(tmp_path / "proj")
        os.makedirs(d, exist_ok=True)
        config.save_last_workspace(d)          # 旧实现：TypeError
        assert config._load_last_workspace() == d

    def test_save_workspace_keeps_other_keys(self):
        self._write("state.json",
                    json.dumps({"quant_llm_model": "p/m"}).encode())
        config.save_last_workspace("C:/ws")
        assert config.get_quant_llm_model() == "p/m"

    def test_quant_llm_model_survives_broken_state_json(self):
        self._write("state.json", b"[1,2]")
        assert config.get_quant_llm_model() == ""
        config.set_quant_llm_model("p/m")      # 旧实现：TypeError
        assert config.get_quant_llm_model() == "p/m"

    # ---------------- models.json ----------------
    @pytest.mark.parametrize("raw", [
        b"[1,2]", b"null", b'"x"', b"{bad", b"{}",
        '{"default": "内存"}'.encode("gbk"),
    ])
    def test_broken_models_json_uses_defaults(self, raw):
        self._write("models.json", raw)
        models, default = config.load_models()   # 旧实现：AttributeError
        assert models and isinstance(default, str)

    @pytest.mark.parametrize("raw", ["null", '"x"', "[1, 2]", '{"a": 1}', "123"])
    def test_providers_wrong_type_is_normalized(self, raw):
        self._write("models.json", ('{"providers": %s}' % raw).encode())
        assert config._load_models_data()["providers"] == []
        assert config.load_models()[0] == []

    def test_model_entry_wrong_type_is_dropped(self):
        self._write("models.json", json.dumps(
            {"providers": [{"id": "p", "models": ["x", {"id": "m"}]}]}
        ).encode())
        models, _ = config.load_models()
        assert [m.key for m in models] == ["p/m"]

    def test_bad_int_fields_fall_back(self):
        self._write("models.json", json.dumps(
            {"providers": [{"id": "p", "models": [
                {"id": "m", "context_window": "128k", "max_tokens": None}]}]}
        ).encode())
        models, _ = config.load_models()
        assert models[0].context_window == 0
        assert models[0].max_tokens == 0

    def test_defaults_are_not_polluted_by_caller(self):
        """回退到内置默认时返回独立副本：调用方改它不能污染后续读取。"""
        self._write("models.json", b"[1,2]")
        data = config._load_models_data()
        data["providers"].append({"id": "凭空多出来的", "models": []})
        assert config._load_models_data()["providers"] != data["providers"]

    # ---------------- mcp.json ----------------
    @pytest.mark.parametrize("raw", [b"[1,2]", b"null", b'{"servers": []}',
                                     b"{bad", b'"x"'])
    def test_broken_mcp_json_falls_back(self, raw):
        self._write("mcp.json", raw)
        assert config.load_mcp_servers() == {"servers": {}}


def test_import_config_survives_broken_state_json(tmp_path):
    """state.json 损坏时 `import config` 必须成功（WORKSPACE 在模块级求值）。"""
    import subprocess
    import sys

    cfg = tmp_path / "local-ai-studio"
    cfg.mkdir()
    (cfg / "state.json").write_bytes(b"[1,2]")
    env = dict(os.environ)
    env.update(APPDATA=str(tmp_path), LOCALAPPDATA=str(tmp_path),
               HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = subprocess.run([sys.executable, "-c",
                        "import config; print(config.WORKSPACE)"],
                       env=env, capture_output=True, text=True, timeout=180)
    assert p.returncode == 0, p.stderr


def test_media_service_env_priority(monkeypatch):
    for k in ("LAS_IMAGE_BASE_URL", "LAS_IMAGE_MODEL", "LAS_IMAGE_API_KEY",
              "LAS_VIDEO_BASE_URL", "LAS_VIDEO_MODEL", "LAS_VIDEO_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    data = {"providers": [{"id": "agnes", "base_url": "https://a.cn/v1",
                           "api_key": "sk-1", "image_model": "mi",
                           "video_model": "mv"}]}
    monkeypatch.setattr(config, "_load_models_data", lambda: data)
    # env 覆盖供应商配置
    monkeypatch.setenv("LAS_IMAGE_BASE_URL", "https://local/v1")
    monkeypatch.setenv("LAS_IMAGE_MODEL", "sd")
    svc = config.image_service()
    assert svc["base_url"] == "https://local/v1" and svc["provider_id"] == ""
    # 未设 env 的视频服务回退供应商
    vs = config.video_service()
    assert vs["provider_id"] == "agnes" and vs["model"] == "mv"


def test_media_service_skips_unkeyed_providers(monkeypatch):
    for k in ("LAS_IMAGE_BASE_URL", "LAS_IMAGE_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(config, "_load_models_data", lambda: {"providers": [
        {"id": "agnes", "base_url": "https://a.cn/v1", "api_key": "",
         "image_model": "mi"},                        # key 未填 → 跳过
        {"id": "st", "base_url": "https://s.cn/v1", "api_key": "sk-ok",
         "image_model": "sensenova-u1.5-lite"},       # 有效
    ]})
    svc = config.image_service()
    assert svc["provider_id"] == "st"
    # 没有任何可用服务
    monkeypatch.setattr(config, "_load_models_data", lambda: {"providers": []})
    assert config.image_service() == {}
    assert config.video_service() == {}


def test_load_models_dedupes_duplicate_keys(monkeypatch):
    # 脏数据防御：同一 provider 下重复登记的模型只保留首个
    state = _seed_providers(monkeypatch, [
        {"id": "glm", "name": "GLM", "base_url": "x", "api_key": "k",
         "api_type": "openai_compatible",
         "models": [{"id": "glm-5.3", "name": "A"},
                    {"id": "glm-5.3", "name": "B"}]},
    ])
    models, _ = config.load_models()
    keys = [m.key for m in models]
    assert keys.count("glm/glm-5.3") == 1
    assert models[0].display_name == "A"          # 保留首个


def test_mode_flags_defaults_persist_and_unknown_key():
    # 先归位到默认（整个会话共享临时 CONFIG_DIR，可能残留别的用例状态）
    config.set_mode_flag("drama", True)
    config.set_mode_flag("comic", False)
    assert config.get_mode_flags() == {"drama": True, "comic": False}

    config.set_mode_flag("comic", True)
    assert config.get_mode_flags()["comic"] is True
    # 写盘持久：不经缓存直接重读文件（模拟重启）
    data = config._load_models_data()
    assert data["modes"]["comic"] is True

    # 未知 key 静默忽略；重复设为同值不报错
    config.set_mode_flag("unknown", True)
    assert "unknown" not in config.get_mode_flags()
    config.set_mode_flag("comic", True)
    config.set_mode_flag("comic", False)
    assert config.get_mode_flags()["comic"] is False
