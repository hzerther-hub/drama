# -*- coding: utf-8 -*-
"""文件树多选拖拽相关 helper 的覆盖测试。

覆盖：
1. ``bindtags`` 顺序的 guard test：确认 widget path 在 ttk.Treeview class 之前；
   这是「多选拖拽能用」的隐含前提，若 Tk 升级 / 换 ttk 实现变了顺序，本测试会失败提醒。
2. ``_resolve_drag_items``：根据「按下点 iid」与「按下前的 selection」推出真正要拖的条目。
3. 真实 ttk.Treeview 多选行为仍可用：调 helper 后 selection 不被静默重置。
"""

import sys
import tkinter as tk

import pytest
from tkinter import ttk

from ui import App


# ============================================================
# 1) bindtags 顺序 guard：多选 drag 的隐含前提
# ============================================================

@pytest.fixture(scope="module")
def _root():
    """一个 Tk root 给整个模块复用：withdraw + 不显式 show。"""
    try:
        r = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"无 Tk 可用：{e}")
    r.withdraw()
    yield r
    r.destroy()


def _tv(_root):
    return ttk.Treeview(_root, selectmode="extended", show="tree")


def test_default_bindtags_widget_first_then_class(_root):
    """tk 默认 bindtags = [widget_path, 'Treeview', '.', 'all']，
    widget 在 class 之前；这是「user binding 先于 ttk 类 binding 跑」的前提。
    若有升级改动顺序，这里会失败提醒。"""
    tv = _tv(_root)
    bt = list(tv.bindtags())
    assert bt[0] == str(tv),     f"widget path 应在首位，实际 {bt!r}"
    assert bt[1] == "Treeview",  f"ttk class 应该在 widget 之后，实际 {bt!r}"


def test_user_binding_runs_before_class_for_button1(_root):
    """在 widget 上绑的 <Button-1> handler 顺序先于 ttk.Treeview 类 binding；
    所以 _press 期间 self.file_tree.selection() 仍反映按下前的多选。"""
    tv = _tv(_root)
    for iid in ("a", "b", "c"):
        tv.insert("", "end", iid=iid, text=iid)
    tv.selection_add("a", "b", "c")
    captured = []

    def cap(e):
        captured.append(set(tv.selection()))

    tv.bind("<Button-1>", cap, add="+")
    tv.event_generate("<Button-1>", x=10, y=10)
    _root.update_idletasks()
    assert captured == [{"a", "b", "c"}], \
        f"user binding 跑时 selection 应仍是多选，实际 {captured!r}"


# ============================================================
# 2) _resolve_drag_items：核心策略 pure-function 测
# ============================================================

class _FakeTree:
    """只假冒 ``item(iid, "values")`` 给 ``_resolve_drag_items`` 用。"""

    def __init__(self, items):
        # items: dict[iid] = (path, bool is_dir)
        self._vals = items

    def item(self, iid, what):
        if what != "values":
            raise AssertionError(f"unexpected item({iid}, {what!r})")
        return self._vals.get(iid, ("", ""))


def _resolve_on(items, clicked_iid, selection):
    """把 ``_resolve_drag_items`` 绑到只有 ``file_tree`` 属性的 stub 上调。"""
    class _Stub:
        file_tree = _FakeTree(items)
    return App._resolve_drag_items(_Stub(), clicked_iid, selection)


def test_resolve_returns_multi_when_clicked_within_selection():
    items = {
        "a": ("C:\\tmp\\a.png", False),
        "b": ("C:\\tmp\\b.png", False),
        "c": ("C:\\tmp\\c.png", False),
    }
    sel = ["a", "b", "c"]
    out = _resolve_on(items, clicked_iid="b", selection=sel)
    assert sorted(p for p, _ in out) == sorted(v[0] for v in items.values())
    assert all(isd is False for _, isd in out)


def test_resolve_returns_single_when_clicked_outside_selection():
    items = {
        "a": ("C:\\tmp\\a.png", False),
        "b": ("C:\\tmp\\b.png", False),
    }
    sel = ["a"]
    out = _resolve_on(items, clicked_iid="b", selection=sel)
    assert out == [("C:\\tmp\\b.png", False)]


def test_resolve_returns_single_when_only_one_selected():
    """多选只剩 1 条时不再走 multi 路径，按下点决定。"""
    items = {
        "a": ("C:\\tmp\\a.png", False),
        "b": ("C:\\tmp\\b.png", False),
    }
    sel = ["a"]
    out = _resolve_on(items, clicked_iid="a", selection=sel)
    assert out == [("C:\\tmp\\a.png", False)]


def test_resolve_returns_empty_when_no_clicked_iid():
    items = {"a": ("C:\\tmp\\a.png", False)}
    out = _resolve_on(items, clicked_iid="", selection=["a"])
    assert out == []


def test_resolve_handles_dirs_and_files_mixed():
    items = {
        "d1": ("C:\\proj\\src", True),
        "d2": ("C:\\proj\\imgs", True),
        "f1": ("C:\\proj\\src\\x.txt", False),
    }
    sel = ["d1", "d2", "f1"]
    out = _resolve_on(items, clicked_iid="d1", selection=sel)
    dirs = sorted(p for p, isd in out if isd is True)
    files = sorted(p for p, isd in out if isd is False)
    assert dirs == ["C:\\proj\\imgs", "C:\\proj\\src"]
    assert files == ["C:\\proj\\src\\x.txt"]


def test_resolve_skips_iids_with_empty_path():
    items = {
        "a": ("C:\\tmp\\a.png", False),
        "b": ("", False),                            # path 为空
        "c": ("C:\\tmp\\c.png", False),
    }
    sel = ["a", "b", "c"]
    out = _resolve_on(items, clicked_iid="a", selection=sel)
    paths = [p for p, _ in out]
    assert "C:\\tmp\\a.png" in paths
    assert "C:\\tmp\\c.png" in paths
    assert all(p for p in paths)


def test_resolve_swallows_item_lookup_errors():
    """item() 抛异常的 iid 跳过，其他继续。"""
    class _BoomTree(_FakeTree):
        def item(self, iid, what):
            if iid == "b":
                raise RuntimeError("oops")
            return super().item(iid, what)

    items = {
        "a": ("C:\\tmp\\a.png", False),
        "b": ("C:\\tmp\\b.png", False),
    }

    class _Stub:
        file_tree = _BoomTree(items)
    out = App._resolve_drag_items(_Stub(), clicked_iid="a", selection=["a", "b"])
    # b 抛异常被吞；a 正常返回
    assert out == [("C:\\tmp\\a.png", False)]


# ============================================================
# 3) 真实 ttk.Treeview 多选 + selection API
# ============================================================

def test_real_treeview_extended_multi_select(_root):
    """selectmode='extended' 留下多选 = Shift/Ctrl 拖拽的入口前提。"""
    tv = _tv(_root)
    for iid in ("a", "b", "c"):
        tv.insert("", "end", iid=iid, text=iid)
    tv.selection_add("a", "b", "c")
    assert set(tv.selection()) == {"a", "b", "c"}
    # 单条 add 不破坏多选
    tv.selection_remove("a")
    assert set(tv.selection()) == {"b", "c"}
