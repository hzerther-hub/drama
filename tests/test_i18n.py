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
