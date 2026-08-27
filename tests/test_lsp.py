# -*- coding: utf-8 -*-
"""lsp.py：多语言 LSP 支持的纯逻辑部分（不启动真实服务器）。"""

import os

import lsp
import pytest


class TestLanguageOf:
    def test_common_exts(self):
        assert lsp.language_of("a.py") == "python"
        assert lsp.language_of("a.jsx") == "js"
        assert lsp.language_of("a.tsx") == "ts"
        assert lsp.language_of("a.rs") == "rust"
        assert lsp.language_of("a.java") == "java"
        assert lsp.language_of("a.cs") == "cs"
        assert lsp.language_of("a.rb") == "ruby"
        assert lsp.language_of("a.kt") == "kotlin"
        assert lsp.language_of("a.swift") == "swift"
        assert lsp.language_of("a.yaml") == "yaml"
        assert lsp.language_of("a.go") == "go"

    def test_unknown(self):
        assert lsp.language_of("a.txt") == ""
        assert lsp.language_of("a.xyz123") == ""

    def test_lang_id_mapping(self):
        assert lsp.lang_id_of("python") == "python"
        assert lsp.lang_id_of("js") == "javascript"
        assert lsp.lang_id_of("cs") == "csharp"
        assert lsp.lang_id_of("sh") == "shellscript"


class TestProbeWorkspace:
    def test_counts_and_order(self, tmp_path, monkeypatch):
        # 造 3 个 py + 1 个 ts（node_modules 里的不算）
        for i in range(3):
            (tmp_path / f"m{i}.py").write_text("x=1")
        (tmp_path / "a.ts").write_text("let x")
        (tmp_path / "node_modules" / "dep").mkdir(parents=True)
        (tmp_path / "node_modules" / "dep" / "b.ts").write_text("let y")
        monkeypatch.setattr(lsp, "available_for", lambda l: True)
        assert lsp.probe_workspace(str(tmp_path)) == ["python", "ts"]

    def test_skips_vendor_dirs(self, tmp_path, monkeypatch):
        (tmp_path / "build").mkdir()
        (tmp_path / "build" / "x.go").write_text("x")
        monkeypatch.setattr(lsp, "available_for", lambda l: True)
        assert lsp.probe_workspace(str(tmp_path)) == []

    def test_missing_dir(self):
        assert lsp.probe_workspace("/no/such/dir") == []

    def test_filters_unavailable(self, tmp_path, monkeypatch):
        (tmp_path / "x.go").write_text("x")
        monkeypatch.setattr(lsp, "available_for", lambda l: l == "python")
        assert lsp.probe_workspace(str(tmp_path)) == []


class TestFormatDiags:
    def test_ok(self):
        items = [
            {"range": {"start": {"line": 4, "character": 0}},
             "severity": 1, "message": "undefined name 'foo'"},
            {"range": {"start": {"line": 9, "character": 2}},
             "severity": 2, "message": "unused variable\nmore lines"},
        ]
        out = lsp.format_diags(items)
        assert out == [
            {"line": 5, "mark": "✗", "msg": "undefined name 'foo'"},
            {"line": 10, "mark": "⚠", "msg": "unused variable"},
        ]

    def test_empty_and_malformed(self):
        assert lsp.format_diags([]) == []
        assert lsp.format_diags([{"bogus": 1}, None]) == []


class TestClientBasics:
    def test_for_file_unknown_lang(self):
        assert lsp.LSPClient.for_file("/x/a.txt") is None

    def test_for_file_no_server(self, monkeypatch):
        monkeypatch.setattr(lsp.shutil, "which", lambda n: None)
        assert lsp.LSPClient.for_file("/x/a.py") is None

    def test_langid_not_hardcoded(self):
        """多语言关键修复：didOpen 的 languageId 按文件语言传，不再硬编码 python。"""
        c = lsp.LSPClient(["/bin/cat"], "/ws", "/x/a.ts", lang="ts")
        assert c._langid == "typescript"
        c2 = lsp.LSPClient(["/bin/cat"], "/ws", "/x/a.py")
        assert c2._langid == "python"

    def test_diagnostics_collected_from_notice(self):
        c = lsp.LSPClient(["/bin/cat"], "/ws", "/x/a.py")
        c._take_notice({"method": "textDocument/publishDiagnostics",
                        "params": {"uri": c._uri,
                                   "items": [{"range": {"start": {"line": 0}},
                                              "severity": 1,
                                              "message": "boom"}]}})
        assert len(c.diagnostics) == 1
