# -*- coding: utf-8 -*-
"""products/ profile 机制：多产品加载、功能开关、默认产品。"""

import pytest

import products


def test_all_products_exist():
    names = products.list_products()
    for p in ("devtool", "devtool_local", "novelwriter", "quant", "devrag"):
        assert p in names


@pytest.mark.parametrize("name", ["devtool", "devtool_local",
                                  "novelwriter", "quant", "devrag"])
def test_profile_loads(name):
    prof = products.load_profile(name)
    assert prof.name == name and prof.title
    # 所有声明的功能开关都是已知 key
    for k in prof.features:
        assert k in products.KNOWN_FEATURES


@pytest.mark.parametrize("name", ["devtool", "devtool_local",
                                  "novelwriter", "quant", "devrag"])
def test_all_products_enable_kb_and_dispatch(name):
    """知识库(rag)与自动派发(dispatch)是全产品线标配开关。"""
    prof = products.load_profile(name)
    assert prof.feature("rag") is True
    assert prof.feature("dispatch") is True


def test_devtool_has_no_local_model():
    prof = products.load_profile("devtool")
    assert prof.feature("gpulocal") is False
    assert prof.feature("dispatch") is True
    assert prof.feature("editor") is True


def test_devtool_local_is_full():
    prof = products.load_profile("devtool_local")
    for k in ("gpulocal", "dispatch", "editor", "voice", "mcp"):
        assert prof.feature(k) is True


def test_novelwriter_features():
    prof = products.load_profile("novelwriter")
    assert prof.feature("editor") is True
    assert prof.feature("gpulocal") is False
    assert prof.feature("rag") is True
    assert prof.feature("dispatch") is True


def test_devrag_enables_kb():
    prof = products.load_profile("devrag")
    assert prof.feature("rag") is True
    assert prof.feature("editor") is True
    assert all(k in products.KNOWN_FEATURES for k in prof.features)
    # 云端版：无本地模型服务器、无英文版
    assert prof.feature("gpulocal") is False
    assert prof.feature("dispatch") is True
    assert prof.feature("zh_only") is True


def test_unknown_product_raises():
    with pytest.raises(FileNotFoundError):
        products.load_profile("no-such-product")


def test_env_selection(monkeypatch):
    monkeypatch.setenv(products.ENV_KEY, "quant")
    products._reset_for_test()
    try:
        assert products.active().name == "quant"
    finally:
        monkeypatch.delenv(products.ENV_KEY)
        products._reset_for_test()


@pytest.mark.parametrize("name", ["devtool", "devtool_local",
                                  "novelwriter", "quant", "devrag"])
def test_app_title_follows_profile(name, monkeypatch):
    """主窗口标题跟随激活产品 profile.title（ui._app_title）。"""
    monkeypatch.setenv(products.ENV_KEY, name)
    products._reset_for_test()
    try:
        import ui
        assert ui._app_title() == products.load_profile(name).title
    finally:
        monkeypatch.delenv(products.ENV_KEY)
        products._reset_for_test()
