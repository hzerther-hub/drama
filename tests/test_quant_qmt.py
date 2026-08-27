# -*- coding: utf-8 -*-
"""quant v1.0：QMT 探活 + 互转面板模块测试。"""

from products.quant import qmt


# ---- QMT 探活（注入进程名单，不碰真机）----

def test_probe_terminal_running():
    r = qmt.probe(["XtMiniQmt.exe", "explorer.exe"])
    assert r["terminal_running"] is True
    assert r["processes"] == ["XtMiniQmt.exe"]
    assert "运行中" in r["detail"]


def test_probe_case_insensitive():
    r = qmt.probe(["xtminiqmt.EXE"])
    assert r["terminal_running"] is True


def test_probe_not_found():
    r = qmt.probe(["explorer.exe", "chrome.exe"])
    assert r["terminal_running"] is False
    assert r["processes"] == []
    assert "未检测到" in r["detail"]


def test_probe_detail_mentions_sdk_state(monkeypatch):
    monkeypatch.setattr(qmt, "xtquant_available", lambda: True)
    r = qmt.probe(["XtItClient.exe"])
    assert "xtquant 可用" in r["detail"]
    r2 = qmt.probe([])
    assert "xtquant 可用" in r2["detail"] and "未运行" in r2["detail"]


def test_list_process_names_fallback(monkeypatch):
    """无 psutil 时走命令兜底且不炸。"""
    monkeypatch.setattr(qmt, "_names_via_psutil", lambda: None)
    monkeypatch.setattr(qmt, "_names_via_command", lambda: ["a.exe"])
    assert qmt.list_process_names() == ["a.exe"]


# ---- 面板模块可导入（不建 Tk 根窗口）----

def test_panel_module_imports():
    import ui_panel_quant
    assert callable(ui_panel_quant.show)


def test_quant_feature_flag():
    """quant 功能开关：量化产品开；devtool_local（本部署）也已启用；其余默认关。"""
    import products
    assert products.load_profile("quant").feature("quant") is True
    assert products.load_profile("devtool_local").feature("quant", False) is True
    for name in ("devtool", "novelwriter"):
        assert products.load_profile(name).feature("quant", False) is False
