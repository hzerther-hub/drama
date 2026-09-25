# -*- coding: utf-8 -*-
"""视频/关键帧 prompt 的人体解剖守门员：手/脚按角色级自适配。

设计：default 5 根手指 + 5 趾；state.characters 里若为某角色显式标
了「断手/无臂/多指/少指/义肢/六指/瘸/独脚/无脚/义足」等异常，
则严格按描述来，没标的走默认 5+5 约束。同名匹配 = 该角色异常。
"""
from __future__ import annotations

import re as _re

_HAND_KEYWORDS = {
    "手": ["断手", "无手", "无臂", "独臂", "单臂", "义肢", "截肢",
           "多指", "六指", "少指", "并指", "缺指", "无指", "无手指",
           "缺手", "手指缺失", "指节缺失", "手指融合", "畸形手"],
    "脚": ["断脚", "无脚", "独脚", "跛", "瘸", "拐", "义足",
           "假肢", "缺脚", "无足", "脚趾缺失", "脚畸形", "失去右脚", "失去左脚", "失去双脚", "缺右脚", "缺左脚"],
}


def _character_appearance_excerpt(state: dict, names):
    """从 state.characters 抽出每个名字的外貌锚段（首段 400 字内）。"""
    chars = (state or {}).get("characters", "") or ""
    out = {}
    for n in names or []:
        pat = _re.escape(n) + r".+?(?=" + chr(92) + "n## |" + chr(92) + "Z)"
        m = _re.search(pat, chars, _re.DOTALL)
        if m:
            out[n] = m.group(0)[:400]
    return out


def _has_anomaly(desc: str, limb: str) -> bool:
    if not desc:
        return False
    for kw in _HAND_KEYWORDS[limb]:
        if kw in desc:
            return True
    return False


def body_guard(state, names) -> str:
    """手/脚解剖约束：默认每人 5 根手指 + 5 趾；state.characters 显式标异常则按其描述。"""
    if not names:
        names = []
    excs = _character_appearance_excerpt(state, names)
    hand_notes, foot_notes = [], []
    for n in names:
        d = excs.get(n, "")
        if not d:
            continue
        if _has_anomaly(d, "手"):
            hand_notes.append(f"（{n} 在 state.characters 已注明手部异常，严格按描述画）")
        if _has_anomaly(d, "脚"):
            foot_notes.append(f"（{n} 在 state.characters 已注明脚部异常，严格按描述画）")
    if hand_notes:
        hand_line = ("出场人物手部都按 5 根手指画（除非 state.characters 显式标了"
                     "「少/多/并/断指」等异常）：" + "；".join(hand_notes) + "。")
    else:
        hand_line = ("出场人物手部都按 5 根手指画，无六指、无并指、无指节缺失、"
                     "无手指融合/弯折畸形；手部比例与人物体型一致。")
    if foot_notes:
        foot_line = ("出场人物脚部都按 5 趾画（除非 state.characters 显式标了"
                     "「少/多趾/瘸/断脚」等异常）：" + "；".join(foot_notes) + "。")
    else:
        foot_line = ("出场人物脚部都按 5 趾画，无多趾、无并趾、无趾节缺失、"
                     "无脚趾融合/弯折畸形；脚部比例与人物体型一致。")
    limb_line = ("人物均为正常人形：两条手臂、两条腿，无第三只手、无三条腿、"
                 "无多余肢体、无肢体复制或扭曲拉长。")
    ghost_line = ("画面同一时刻每名角色只出现一个人影，无重影、无分身、"
                  "无多人复制；五官位置稳定不畸变、不融化，长相前后一致。")
    logo_line = ("画面不出现真实品牌标志、不出现可辨识的真人明星脸。")
    return hand_line + " " + foot_line + " " + limb_line + " " + ghost_line + " " + logo_line
