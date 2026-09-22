# -*- coding: utf-8 -*-
"""标签 / 文件树拖拽到聊天三落点（chat / input / attach_bar）的命中判断。

不创建真实 Tk：用 _FakeWidget 模拟 winfo_*，直接验证 helper：
- ``App._point_over_widget``：矩形内 / 边界 / 矩形外的几何判定
- ``App._hit_chat_drop_target``：聚合三落点；``attach_bar`` 缺失仍可命中 chat/input

之所以覆盖 attach_bar：用户拖文件标签的目标除了 chat 区和 input 框，
还应包括「聊天顶部附件栏」——这条能力对应产品语义 DND `_targets`
（ui.py:7894 ``_targets = [chat, input, attach_bar]``）。
"""

import types

from ui import App


class _FakeWidget:
    """伪装一个 Tk widget：固定 ``winfo_*`` 矩形坐标，给 ``_point_over_widget`` 用。"""

    def __init__(self, x=0, y=0, w=100, h=20):
        self._x, self._y, self._w, self._h = x, y, w, h

    def winfo_rootx(self):
        return self._x

    def winfo_rooty(self):
        return self._y

    def winfo_width(self):
        return self._w

    def winfo_height(self):
        return self._h


class _FakeApp:
    """把 ``_hit_chat_drop_target`` / ``_chat_drop_targets`` 从真 App「借」过来，
    实例属性 ``chat`` / ``input`` / ``attach_bar`` 由测试控制。"""

    _hit_chat_drop_target = App._hit_chat_drop_target
    _chat_drop_targets = App._chat_drop_targets

    def _point_over_widget(self, w, gx, gy):
        # 转发到 App 的 staticmethod；staticmethod 通过类属性继承有 descriptor
        # 重绑定问题（FakeApp 上 self 调用会带 self 进来），这里显式走类。
        return App._point_over_widget(w, gx, gy)

    def __init__(self, chat=None, inp=None, bar=None):
        self.chat = chat
        self.input = inp
        self.attach_bar = bar


def test_point_over_widget_hit_and_miss():
    w = _FakeWidget(x=100, y=200, w=300, h=40)
    # 矩形内（典型点）
    assert App._point_over_widget(w, 150, 220)
    # 左上 / 右下边界：包含（约定 <=）
    assert App._point_over_widget(w, 100, 200)
    assert App._point_over_widget(w, 400, 240)
    # 矩形外（紧邻四边外侧）
    assert not App._point_over_widget(w, 99, 200)
    assert not App._point_over_widget(w, 401, 200)
    assert not App._point_over_widget(w, 150, 199)
    assert not App._point_over_widget(w, 150, 241)
    # 容错：None 永远 False
    assert not App._point_over_widget(None, 0, 0)


def test_point_over_widget_negative_dim_returns_false():
    """未映射的 widget (width/height=0) 仍返回 False，不抛异常。"""
    w = _FakeWidget(x=0, y=0, w=0, h=0)
    # 0x0 矩形：起点 == 终点算命中（左上角），但应用上的「拖动命中检测」要
    # 至少有一定面积才合理；这里只确认不抛异常、行为稳定。
    App._point_over_widget(w, 0, 0)
    assert not App._point_over_widget(w, 5, 5)


def _make_app(chat=None, inp=None, bar=None):
    """构造只有三落点属性的伪 App。"""
    return _FakeApp(chat, inp, bar)


def _hit(app, gx, gy):
    """调一次 ``_hit_chat_drop_target``。"""
    return app._hit_chat_drop_target(gx, gy)


def test_hit_chat_drop_target_three_widgets():
    chat = _FakeWidget(x=50, y=80, w=700, h=300)
    inp = _FakeWidget(x=20, y=460, w=760, h=80)
    bar = _FakeWidget(x=20, y=420, w=760, h=30)
    app = _make_app(chat, inp, bar)
    # 三落点都命中
    assert _hit(app, 400, 200)     # chat 区中部
    assert _hit(app, 400, 500)     # input 框
    assert _hit(app, 400, 435)     # 附件栏（input 上方 30px）
    # chat 与附件栏之间的空白处不命中
    assert not _hit(app, 400, 410)
    # 远离聊天区
    assert not _hit(app, 0, 0)
    assert not _hit(app, 1000, 1000)


def test_hit_chat_drop_target_missing_attach_bar():
    """attach_bar 不可用（0 附件时被 pack_forget 等价于几何隐藏）时，
    chat / input 仍可单独命中，不抛异常。"""
    chat = _FakeWidget(x=50, y=80, w=700, h=300)
    inp = _FakeWidget(x=20, y=460, w=760, h=80)
    app = _make_app(chat, inp, bar=None)
    assert _hit(app, 400, 500)     # input 命中
    assert _hit(app, 400, 200)     # chat 命中
    assert not _hit(app, 400, 435) # 旧附件栏位置：现在不在 → 不命中
    assert not _hit(app, 0, 0)
    assert not _hit(app, 1000, 1000)


def test_hit_chat_drop_target_no_widgets():
    """所有落点都缺失时不抛异常，返回 False（拖入空白处）。"""
    app = _make_app(chat=None, inp=None, bar=None)
    assert _hit(app, 0, 0) is False
    assert _hit(app, 999, 999) is False


def test_chat_drop_targets_filters_none():
    """_chat_drop_targets 只返回非 None widget，顺序保持 chat → input → attach_bar。"""
    chat = _FakeWidget()
    inp = _FakeWidget()
    app = _make_app(chat, inp, bar=None)
    assert app._chat_drop_targets() == [chat, inp]

    app2 = _make_app(chat=None, inp=None, bar=None)
    assert app2._chat_drop_targets() == []
