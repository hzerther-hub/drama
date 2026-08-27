# -*- coding: utf-8 -*-
"""attach.extract_file_refs：消息里的本地文件引用自动转附件。"""

import os
import sys

import pytest

import attach


def _uri_of(path: str) -> str:
    """把绝对路径转成 file:/// URI（Windows 盘符用正斜杠形式）。"""
    return "file:///" + path.replace("\\", "/")


def _same(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == \
        os.path.normcase(os.path.normpath(b))


class TestFileUri:
    def test_existing_file_extracted(self, tmp_path):
        p = tmp_path / "a.png"
        p.write_bytes(b"\x89PNG")
        paths, rest = attach.extract_file_refs(f"看这张 {_uri_of(str(p))} 谢谢")
        assert len(paths) == 1 and _same(paths[0], str(p))
        assert "file://" not in rest

    def test_missing_file_kept_in_text(self, tmp_path):
        uri = _uri_of(str(tmp_path / "nope.png"))
        paths, rest = attach.extract_file_refs(f"路径 {uri}")
        assert paths == []
        assert uri in rest

    def test_percent_decoded(self, tmp_path):
        p = tmp_path / "图片.png"
        p.write_bytes(b"x")
        uri = "file:///" + attach.urllib.parse.quote(
            str(p).replace("\\", "/"))
        paths, _ = attach.extract_file_refs(uri)
        assert len(paths) == 1 and _same(paths[0], str(p))

    def test_any_file_type_attached(self, tmp_path):
        # file:// 是显式引用：非媒体文件（如 txt）也转附件（文档就地分析）
        p = tmp_path / "notes.txt"
        p.write_text("hello", encoding="utf-8")
        paths, _ = attach.extract_file_refs(f"docs: {_uri_of(str(p))}")
        assert len(paths) == 1 and _same(paths[0], str(p))


class TestBareWinPath:
    """裸盘符路径：仅媒体文件转附件（monkeypatch 隔离，跨平台可跑）。"""

    @pytest.fixture
    def fake_fs(self, monkeypatch):
        exists = {"C:/wx/img.png", "C:\\wx\\img.png", "C:/wx/notes.txt",
                  "D:/media/song.mp3"}
        monkeypatch.setattr(os.path, "isfile",
                            lambda p: p.replace("\\", "/") in
                            {x.replace("\\", "/") for x in exists})
        monkeypatch.setattr(attach.media, "classify",
                            lambda p: ("image" if p.lower().endswith(".png")
                                       else "audio" if p.lower().endswith(".mp3")
                                       else ""))

    def test_forward_slash_media_attached(self, fake_fs):
        paths, rest = attach.extract_file_refs("图在 C:/wx/img.png 那里")
        assert paths == ["C:/wx/img.png"]
        assert "img.png" not in rest

    def test_backslash_media_attached(self, fake_fs):
        paths, _ = attach.extract_file_refs("C:\\wx\\img.png")
        assert paths == ["C:\\wx\\img.png"]

    def test_non_media_kept_for_tools(self, fake_fs):
        # 存在但非媒体（txt）→ 保留原文，模型可用 read_file 自己读
        text = "日志在 C:/wx/notes.txt"
        paths, rest = attach.extract_file_refs(text)
        assert paths == []
        assert rest == text

    def test_missing_kept(self, fake_fs):
        text = "没有 E:/gone.png 这个文件"
        paths, rest = attach.extract_file_refs(text)
        assert paths == []
        assert "E:/gone.png" in rest

    def test_not_matched_inside_word(self, fake_fs):
        # "ABC:/x.png" 里 C:/ 前是字母 → 不是路径的一部分
        text = "变量 ABC:/wx/img.png 不算路径"
        paths, _ = attach.extract_file_refs(text)
        assert paths == []

    def test_dedupe_with_uri(self, fake_fs):
        paths, _ = attach.extract_file_refs(
            "file:///C:/wx/img.png 和 C:/wx/img.png 是同一个")
        assert paths == ["C:/wx/img.png"]


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason="真实盘符路径仅 Windows 可建")
class TestBareWinPathRealFs:
    def test_real_wechat_style_path(self, tmp_path):
        p = tmp_path / "wxid_abc123.png"
        p.write_bytes(b"\x89PNG")
        paths, rest = attach.extract_file_refs(f"微信图片 {p} 帮我看看")
        assert len(paths) == 1 and _same(paths[0], str(p))
        assert "wxid" not in rest


class TestSnippetHelper:
    """代码片段附件（编辑器右键「加入聊天」）的格式化辅助。"""

    def _att(self):
        return {"kind": "snippet", "path": r"D:\repos\app\requirements.php",
                "start_line": 110, "end_line": 135,
                "content": "array(\n    \"name\" => \"PDO\",\n);"}

    def test_chip_includes_file_and_lines(self):
        chip = attach.snippet_chip(self._att())
        assert "requirements.php" in chip
        assert "110" in chip and "135" in chip

    def test_format_includes_file_lines_and_content(self):
        block = attach.format_snippet(self._att())
        assert "requirements.php" in block
        assert "110" in block and "135" in block
        assert 'array(' in block            # 代码花括号原样保留（拼接非 str.format）

    def test_format_braces_safe(self):
        # 内容含花括号大括号不应触发格式化异常
        att = dict(self._att(),
                   content="def f():\n    return {}\n    \"a\": {1, 2}")
        block = attach.format_snippet(att)
        assert "{1, 2}" in block

