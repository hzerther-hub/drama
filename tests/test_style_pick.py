# -*- coding: utf-8 -*-
"""ensure_picked：每本书首次确认风格，记下后不再弹出；无书不弹。"""

import types

import pytest

import ui_panel_style_pick as m


def _app_with_pipe(state):
    """最小 app：ensure_picked 通过 _novel_pipe.state 读 state。"""
    pipe = types.SimpleNamespace(state=state)
    return types.SimpleNamespace(_novel_pipe=pipe, root=object())


def test_no_book_does_not_pick(monkeypatch):
    """没载入任何书：ensure_picked 静默返回 False。"""
    app = types.SimpleNamespace(_novel_pipe=None, root=object())
    monkeypatch.setattr(m, "_book_state", lambda app: (None, None))
    assert m.ensure_picked(app, app.root) is False


def test_picked_flag_short_circuits(monkeypatch):
    """已确认过的书：ensure_picked 直接 True，不弹窗、不改 state。"""
    state = {"_ch_style_picked": True, "drama_style": "沿用"}
    app = _app_with_pipe(state)
    monkeypatch.setattr(m.tk, "Toplevel", lambda *a, **k: pytest.fail("不应弹窗"))
    assert m.ensure_picked(app, app.root) is True
    assert state["drama_style"] == "沿用"