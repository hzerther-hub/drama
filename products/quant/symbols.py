# -*- coding: utf-8 -*-
"""标的代码转换：各平台代码格式互转，IR 内部统一用聚宽格式做规范形。

    聚宽/PTrade : 000001.XSHE / 600519.XSHG
    掘金 gm.api : SZSE.000001 / SHSE.600519
    QMT xtquant : 000001.SZ   / 600519.SH
"""

from __future__ import annotations

_JQ_EX = {"XSHE", "XSHG"}
_TO_JQ = {"SZSE": "XSHE", "SHSE": "XSHG", "SZ": "XSHE", "SH": "XSHG"}
_FROM_JQ = {
    "gm":  {"XSHE": "SZSE", "XSHG": "SHSE"},
    "qmt": {"XSHE": "SZ", "XSHG": "SH"},
}


def to_canonical(symbol: str) -> str:
    """任意平台格式 → 聚宽规范形。无法识别时原样返回（保守不臆造）。"""
    s = symbol.strip()
    head, sep, tail = s.partition(".")
    if not sep:
        return s
    if tail.upper() in _JQ_EX:                     # 已是聚宽格式
        return head + "." + tail.upper()
    if head.upper() in _TO_JQ:                     # 掘金格式 SZSE.000001
        return f"{tail}.{_TO_JQ[head.upper()]}"
    if tail.upper() in _TO_JQ:                     # QMT 格式 000001.SZ
        return f"{head}.{_TO_JQ[tail.upper()]}"
    return s


def from_canonical(symbol: str, platform: str) -> str:
    """聚宽规范形 → 平台格式。joinquant/ptrade 原样；未知平台原样。"""
    s = to_canonical(symbol)
    code, sep, ex = s.partition(".")
    mapping = _FROM_JQ.get(platform)
    if not sep or mapping is None or ex not in mapping:
        return s
    if platform == "gm":
        return f"{mapping[ex]}.{code}"
    return f"{code}.{mapping[ex]}"                 # qmt
