# -*- coding: utf-8 -*-
"""codeindex.py：分词 / 分块 / 建库 / 语义检索。"""

import os

import codeindex


class TestTokenize:
    def test_snake_case_split(self):
        toks = codeindex.tokenize("parse_http_response")
        for w in ("parse_http_response", "parse", "http", "response"):
            assert w in toks

    def test_camel_case_split(self):
        toks = codeindex.tokenize("parseHttpResponse")
        assert "parse" in toks and "response" in toks

    def test_chinese_bigram(self):
        toks = codeindex.tokenize("启动模型服务")
        assert "启动" in toks and "模型" in toks

    def test_stopwords_and_short_words_dropped(self):
        toks = codeindex.tokenize("if a = b: return self")
        assert "if" not in toks and "self" not in toks
        assert "a" not in toks                          # 单字符丢弃


class TestChunking:
    def test_line_numbers_1_based_with_overlap(self):
        lines = [f"line{i}" for i in range(codeindex.CHUNK_LINES * 2)]
        chunks = list(codeindex._chunk_lines(lines))
        assert chunks[0][0] == 1
        assert chunks[0][1] == codeindex.CHUNK_LINES
        # 第二块起点 = 第一块起点 + step（有重叠）
        assert chunks[1][0] == 1 + codeindex.CHUNK_LINES - codeindex.CHUNK_OVERLAP


class TestBuildAndSearch:
    def _make_project(self, tmp_path):
        with open(os.path.join(str(tmp_path), "fruit.py"), "w",
                  encoding="utf-8") as f:
            f.write("def calculate_banana_price(items):\n"
                    "    '''计算香蕉总价'''\n"
                    "    return sum(i.price for i in items)\n" * 3)
        with open(os.path.join(str(tmp_path), "car.py"), "w",
                  encoding="utf-8") as f:
            f.write("def drive_car(speed):\n"
                    "    return speed * 2\n" * 3)
        return str(tmp_path)

    def test_build_then_search(self, tmp_path):
        ws = self._make_project(tmp_path)
        stats = codeindex.build(ws, force=True)
        assert stats.get("files_indexed", 0) >= 2
        hits = codeindex.search(ws, "calculate_banana_price", top_k=3)
        assert hits
        assert hits[0]["file"].endswith("fruit.py")
        assert "banana" in hits[0]["content"]

    def test_incremental_skips_unchanged(self, tmp_path):
        ws = self._make_project(tmp_path)
        first = codeindex.build(ws, force=True)
        second = codeindex.build(ws)               # 不 force → 全跳过
        assert second.get("skipped_unchanged", 0) >= first.get("files_indexed", 0)

    def test_search_empty_workspace(self, tmp_path):
        assert codeindex.search(str(tmp_path), "anything") == []
