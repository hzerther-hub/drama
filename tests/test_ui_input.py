# -*- coding: utf-8 -*-
"""ui_input.decide：输入框按键决策矩阵（纯函数，无 Tk 依赖）。"""

import ui_input


def test_plain_enter_sends():
    assert ui_input.decide(None, "Return", "\r", False, False) == "send"
    assert ui_input.decide(None, "KP_Enter", "\r", False, False) == "send"
    # IME 改写 keysym 但 char 仍为 \r → 仍识别为回车
    assert ui_input.decide(None, "Left", "\r", False, False) == "send"


def test_shift_ctrl_enter_not_send():
    # Shift+回车=换行（Text 默认），Ctrl+回车走专用 <Control-Return> 绑定
    assert ui_input.decide(None, "Return", "\r", True, False) is None
    assert ui_input.decide(None, "Return", "\r", False, True) is None


def test_popup_open_enter_confirms_not_send():
    assert ui_input.decide("at", "Return", "\r", False, False) == ("confirm", "at")
    assert ui_input.decide("cmd", "Return", "\r", False, False) == ("confirm", "cmd")
    assert ui_input.decide("at", "Tab", "", False, False) == ("confirm", "at")


def test_popup_escape_and_navigation():
    assert ui_input.decide("at", "Escape", "", False, False) == ("hide", "at")
    assert ui_input.decide("cmd", "Escape", "", False, False) == ("hide", "cmd")
    assert ui_input.decide("at", "Down", "", False, False) == ("nav", 1)
    assert ui_input.decide("at", "Up", "", False, False) == ("nav", -1)


def test_popup_char_rescan():
    assert ui_input.decide("at", "a", "a", False, False) == "rescan"
    assert ui_input.decide("cmd", "BackSpace", "\b", False, False) == "rescan"
    assert ui_input.decide("at", "Delete", "", False, False) == "rescan"


def test_popup_other_keys_pass_through():
    assert ui_input.decide("at", "Home", "", False, False) is None
    assert ui_input.decide("cmd", "F5", "", False, False) is None


def test_visible_commands_falls_back_without_app_method():
    # 假 app 没有 command_candidates（旧 App / 测试替身）→ 退回全量 _COMMANDS
    import types

    full = [("/novel drama", "d", "novel"), ("/help", "h", "help")]
    fake_self = types.SimpleNamespace(
        app=types.SimpleNamespace(_COMMANDS=full))
    assert ui_input.InputController._visible_commands(fake_self) == full


def test_visible_commands_uses_candidates_when_present():
    # 有 command_candidates → 弹窗/速查菜单只显示过滤后的命令（模式开关联动）
    import types

    full = [("/novel drama", "d", "novel"), ("/help", "h", "help")]
    filtered = [full[1]]
    fake_self = types.SimpleNamespace(
        app=types.SimpleNamespace(
            _COMMANDS=full, command_candidates=lambda: filtered))
    assert ui_input.InputController._visible_commands(fake_self) == filtered
