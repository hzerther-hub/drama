# -*- coding: utf-8 -*-
"""ui 命令解析：零宽字符归一化（粘贴文本里的隐形字符会弄脏命令名）。"""

import re

import ui


def test_normalize_zero_width_replaces_with_space():
    # 零宽字符替代空格时（软换行点），归一成空格而不是删除——
    # 直接删除会把「/novel」「start」粘成「/novelstart」
    assert ui._normalize_zero_width("/novel\u200bstart 书") == "/novel start 书"
    assert ui._normalize_zero_width("/novel\u200dstart 书") == "/novel start 书"
    assert ui._normalize_zero_width("\ufeff/novel") == "/novel"
    assert ui._normalize_zero_width("普通文本不受影响") == "普通文本不受影响"
    assert ui._normalize_zero_width("一、\u200c核心") == "一、 核心"


def test_multiline_command_dispatch():
    # 用户实测场景：多行粘贴 /novel start + 设定。修复前 $ 不匹配字符串
    # 中部换行 → 整段文本被判未知命令（q.unknown）。
    text = "/novel start 一、核心设定\n现实线：42岁的王安平，程序员出身"
    m = re.match(r"^(/\S+)\s*(.*)$", text, re.DOTALL)
    assert m and m.group(1).lower() == "/novel"
    # 多行设定完整保留为参数，供 parse_start_args 当灵感用
    assert m.group(2) == "start 一、核心设定\n现实线：42岁的王安平，程序员出身"


def test_command_regex_matches_after_cleanup():
    # 复刻 _run_command 的解析逻辑：清洗后 /novel 必须命中命令分发
    text = "/novel\u200bstart 一、核心设定\n现实线：王安平"
    clean = ui._normalize_zero_width(text.strip())
    m = re.match(r"^(/\S+)\s*(.*)$", clean, re.DOTALL)
    assert m and m.group(1).lower() == "/novel"
    assert m.group(2).startswith("start 一、核心设定")


def test_command_candidates_respect_mode_flags(monkeypatch):
    # 模式开关关闭 → 对应 /novel 子命令从弹窗/速查菜单消失；开启 → 保留。
    # 直接以假 self 调方法（只触 self._COMMANDS），不实例化 App（无 Tk）。
    import types

    import config

    fake = types.SimpleNamespace(_COMMANDS=ui.App._COMMANDS)

    monkeypatch.setattr(config, "get_mode_flags",
                        lambda: {"drama": False, "comic": True})
    cmds = [c for c, _d, _k in ui.App.command_candidates(fake)]
    assert "/novel drama" not in cmds
    assert "/novel drama new" not in cmds
    assert "/novel comic" in cmds
    assert "/novel comic cast" in cmds
    assert "/help" in cmds                       # 非模式命令不受影响

    monkeypatch.setattr(config, "get_mode_flags",
                        lambda: {"drama": True, "comic": False})
    cmds = [c for c, _d, _k in ui.App.command_candidates(fake)]
    assert "/novel drama" in cmds
    assert "/novel comic" not in cmds
    assert "/novel comic cast" not in cmds
