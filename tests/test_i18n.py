# -*- coding: utf-8 -*-
"""i18n.py：中英文案查找与语言切换。"""

import i18n


def test_unknown_key_returns_key():
    assert i18n.t("no.such.key.at.all") == "no.such.key.at.all"


def test_set_and_get_lang():
    old = i18n.get_lang()
    try:
        i18n.set_lang("zh")
        assert i18n.get_lang() == "zh"
        i18n.set_lang("en")
        assert i18n.get_lang() == "en"
        i18n.set_lang("fr")                # 不支持的语言 → 回退 en
        assert i18n.get_lang() == "en"
    finally:
        i18n.set_lang(old)


def test_both_languages_have_content():
    i18n.set_lang("zh")
    zh = i18n.t("top.send")
    i18n.set_lang("en")
    en = i18n.t("top.send")
    i18n.set_lang("zh")
    assert zh and en and zh != "top.send" and en != "top.send"


def test_format_kwargs():
    # 带占位符的 key 应能格式化
    s = i18n.t("think.set", v="high")
    assert "high" in s


def test_all_referenced_keys_exist():
    """静态扫描全部 _t("key") 引用必须在 STRINGS 中有对应条目。

    回归背景：q.unknown 的条目曾在一次清理中被误删，导致未知命令
    直接显示裸键名；kb.build 则是引用了却从未定义过。
    """
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parent.parent
    pat = re.compile(r"_t\(\s*[\"']([a-z0-9_.]+)[\"']")
    files = list(root.glob("*.py")) + list((root / "products").rglob("*.py"))
    missing = set()
    for f in files:
        if f.name == "i18n.py":
            continue
        src = f.read_text(encoding="utf-8")
        for key in pat.findall(src):
            if key.endswith("."):          # _t("novel." + err) 动态拼键前缀
                continue
            if key not in i18n.STRINGS:
                missing.add(f"{key} ({f.name})")
    assert not missing, "缺少 i18n 条目: " + ", ".join(sorted(missing))
