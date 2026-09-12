# -*- coding: utf-8 -*-
"""发布/导出：EPUB 清单与正文文件名同源（防丢章）+ 各格式基本形态。

关键回归：export_epub 曾用 range(1, N+1) 生成清单、却用 c['idx'] 命名正文
文件，章号一旦不是 1..N 连续（删章/插章/历史脏数据）就会声明不存在的
cN.xhtml、并漏掉真实存在的章文件 → 阅读器丢章或直接报错。
"""

import re
import zipfile

import publisher


def _state(dirpath, chapters, title="测试书"):
    return {"dir": str(dirpath), "idea": "一句话灵感", "pid": "p1",
            "outline": f"《{title}》\n\n大纲正文", "chapters": chapters}


def _ch(idx, text="正文段落。\n\n第二段。"):
    return {"idx": idx, "title": f"第{idx}章", "text": text}


def _opf(path):
    with zipfile.ZipFile(path) as z:
        return z.read("OEBPS/content.opf").decode("utf-8")


def _hrefs(opf):
    return re.findall(r"href='([^']+)'", opf)


def _ids(opf):
    return re.findall(r"<item id='([^']+)'", opf)


def _idrefs(opf):
    return re.findall(r"idref='([^']+)'", opf)


class TestEpub:
    def test_idx_not_contiguous_keeps_manifest_in_sync(self, tmp_path):
        """回归：idx=[1,3] 时清单不得留下悬空引用，也不能漏声明真实文件。"""
        out = publisher.export_epub(_state(tmp_path, [_ch(1), _ch(3)]),
                                    str(tmp_path / "b.epub"))
        with zipfile.ZipFile(out) as z:
            names = set(z.namelist())
        opf = _opf(out)
        declared = {"OEBPS/" + h for h in _hrefs(opf)}
        actual = {n for n in names if n.endswith(".xhtml")}
        # 正文按位置编号 → 文件名连续；这与清单声明必须完全一致
        assert actual == {"OEBPS/c1.xhtml", "OEBPS/c2.xhtml"}
        assert declared == actual, "清单与正文文件不同源（悬空引用或漏声明）"
        assert _ids(opf) == _idrefs(opf)              # spine 指向存在的 item

    def test_chapters_written_in_reading_order(self, tmp_path):
        out = publisher.export_epub(_state(tmp_path, [_ch(1, "甲"), _ch(3, "乙")]),
                                    str(tmp_path / "b.epub"))
        opf = _opf(out)
        assert _ids(opf) == ["c1", "c2"]
        with zipfile.ZipFile(out) as z:
            assert "甲" in z.read("OEBPS/c1.xhtml").decode("utf-8")
            # 章号 3 是第二篇，按位置落到 c2.xhtml（内容与清单一致）
            assert "乙" in z.read("OEBPS/c2.xhtml").decode("utf-8")

    def test_contiguous_idx_unchanged(self, tmp_path):
        out = publisher.export_epub(
            _state(tmp_path, [_ch(i) for i in (1, 2, 3)]),
            str(tmp_path / "b.epub"))
        assert _hrefs(_opf(out)) == ["c1.xhtml", "c2.xhtml", "c3.xhtml"]

    def test_empty_chapters_still_valid_zip(self, tmp_path):
        out = publisher.export_epub(_state(tmp_path, []), str(tmp_path / "b.epub"))
        with zipfile.ZipFile(out) as z:
            assert z.read("mimetype") == b"application/epub+zip"
            assert _hrefs(_opf(out)) == []
            assert z.testzip() is None

    def test_escapes_title_and_body(self, tmp_path):
        st = _state(tmp_path, [{"idx": 1, "title": "a<b>",
                                "text": "x < y & z"}], title="书&名")
        out = publisher.export_epub(st, str(tmp_path / "b.epub"))
        opf = _opf(out)
        assert "书&amp;名" in opf and "<title>书&名" not in opf
        with zipfile.ZipFile(out) as z:
            assert "x &lt; y &amp; z" in z.read("OEBPS/c1.xhtml").decode("utf-8")


class TestOtherFormats:
    def test_export_txt_has_titles_and_body(self, tmp_path):
        out = publisher.export_txt(_state(tmp_path, [_ch(1, "甲文")]),
                                   str(tmp_path / "b.txt"))
        text = open(out, encoding="utf-8").read()
        assert text.startswith("测试书\n\n")
        assert "第1章" in text and "甲文" in text

    def test_export_html_wraps_paragraphs(self, tmp_path):
        out = publisher.export_html(_state(tmp_path, [_ch(1, "一段\n\n二段")]),
                                    str(tmp_path / "b.html"))
        html = open(out, encoding="utf-8").read()
        assert html.startswith("<!doctype html>")
        assert "<h2>第1章</h2>" in html
        assert html.count("<p>") == 2

    def test_export_md_includes_outline_file_when_present(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text("大纲正文", encoding="utf-8")
        st = _state(tmp_path, [_ch(1, "甲文")])
        st["file"] = str(plan)
        out = publisher.export_md(st, str(tmp_path / "b.md"))
        md = open(out, encoding="utf-8").read()
        assert md.startswith("大纲正文")
        assert "## 第1章" in md


class TestHelpers:
    def test_book_title_prefers_outline_brackets(self):
        assert publisher._book_title({"outline": "《书名》\n其余"}) == "书名"

    def test_book_title_falls_back_to_idea(self):
        assert publisher._book_title({"idea": "灵感句"}) == "灵感句"

    def test_safe_filename_strips_windows_illegal(self):
        assert publisher._safe_filename('a<b>c:d/e\\f|g?h*i') == "abcdefghi"

    def test_safe_filename_never_empty(self):
        assert publisher._safe_filename("   ") == "novel"

    def test_webhook_requires_config(self, monkeypatch):
        monkeypatch.delenv("LAS_PUBLISH_WEBHOOK_URL", raising=False)
        try:
            publisher.publish_webhook(_state(".", [_ch(1)]), 1, 1)
        except publisher.PublishError as e:
            assert "Webhook" in str(e)
        else:
            raise AssertionError("未配置 Webhook 时应抛 PublishError")
