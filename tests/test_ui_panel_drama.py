# -*- coding: utf-8 -*-
"""ui_panel_drama._comic_panels：漫画分镜 md → 出图提示词列表的纯解析。"""

import ui_panel_drama as m

_MD = """# 漫画分镜表（第 1-2 章）

## 第1章《开局》

| 格号 | 画面 | 台词 | 构图 | 出图提示词(英文) |
| --- | --- | --- | --- | --- |
| 1 | 雨夜屋顶 | 「谁？」 | 俯视 | **rainy rooftop, night, wide shot** |
| 2 | 巷口对峙 | 「让开」 | 平视 | dark alley, two silhouettes, close-up |

## 第2章《反转》

| 格号 | 画面 | 台词 | 构图 | 出图提示词(英文) |
| --- | --- | --- | --- | --- |
| 1 | 天台日出 | —— | 远景 | sunrise rooftop, silhouette |
"""


def test_extracts_prompt_cells_of_current_chapter():
    panels = m._comic_panels(_MD, 1)
    assert panels == ["rainy rooftop, night, wide shot",
                      "dark alley, two silhouettes, close-up"]


def test_missing_chapter_returns_empty():
    assert m._comic_panels(_MD, 9) == []


def test_second_chapter_isolated_from_first():
    # 章节段落截断到下一个 ## 标题，互不串格
    assert m._comic_panels(_MD, 2) == ["sunrise rooftop, silhouette"]


def test_skips_header_and_separator_rows():
    md = """## 第3章《单格》

| 格号 | 画面 | 台词 | 构图 | 出图提示词(英文) |
| --- | :---: | --- | --- | --- |
| 1 | 桌前 | 「好」 | 特写 | desk lamp, hands, close-up |
"""
    assert m._comic_panels(md, 3) == ["desk lamp, hands, close-up"]


def test_cap_at_24_panels():
    rows = "\n".join(f"| {i} | 画 | 词 | 构 | prompt {i} |"
                     for i in range(1, 31))
    panels = m._comic_panels(f"## 第4章《爆量》\n\n{rows}\n", 4)
    assert len(panels) == 24
    assert panels[-1] == "prompt 24"
