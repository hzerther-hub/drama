# -*- coding: utf-8 -*-
"""浏览器工具：URL 容错、未装依赖的降级提示、schema 注册与权限分层。"""

from __future__ import annotations

import importlib.util

import pytest

import browser
import tools


# ---------------- normalize_url ----------------

class TestNormalizeUrl:
    def test_bare_domain_gets_https(self):
        """裸域名自动补 https://。"""
        assert browser.normalize_url("example.com") == "https://example.com"

    def test_schemes_passthrough(self):
        """http/https/file/about 原样保留。"""
        assert browser.normalize_url("http://localhost:9999/x") == \
            "http://localhost:9999/x"
        assert browser.normalize_url("https://a.b/c?q=1") == "https://a.b/c?q=1"
        assert browser.normalize_url("file:///D:/x.html").startswith("file://")

    def test_garbage_raises(self):
        """空串/含空格文本直接拒绝。"""
        with pytest.raises(browser.BrowserError):
            browser.normalize_url("")
        with pytest.raises(browser.BrowserError):
            browser.normalize_url("这不是网址")


# ---------------- 未安装 Playwright 的降级提示 ----------------

class TestDegradeHint:
    def test_open_without_playwright(self, monkeypatch):
        """未安装 Playwright 时给安装指引而不是裸报错。"""
        monkeypatch.setattr(browser, "available", lambda: False)
        out = tools.execute_tool("browser_open", {"url": "https://example.com"})
        assert "pip install playwright" in out
        assert out.startswith("错误：")

    def test_screenshot_without_playwright(self, monkeypatch):
        """截图工具同样走降级提示。"""
        monkeypatch.setattr(browser, "available", lambda: False)
        out = tools.execute_tool("browser_screenshot", {})
        assert "playwright" in out.lower()


# ---------------- 注册与权限分层 ----------------

class TestRegistration:
    def test_schemas_and_executors(self):
        """7 个 browser_* 工具都有 schema 和执行器。"""
        names = {s["function"]["name"] for s in tools.TOOL_SCHEMAS}
        for n in ("browser_open", "browser_read", "browser_click",
                  "browser_type", "browser_eval", "browser_screenshot",
                  "browser_close"):
            assert n in names, n
            assert n in tools._EXECUTORS, n

    def test_permission_tiers(self):
        """点击/填表/执行 JS 需审批；open/read/screenshot/close 只读。"""
        for n in ("browser_click", "browser_type", "browser_eval"):
            assert tools.is_write_tool(n), n
        for n in ("browser_open", "browser_read", "browser_screenshot",
                  "browser_close"):
            assert not tools.is_write_tool(n), n

    def test_import_without_playwright(self):
        """未安装 Playwright 时模块仍可导入、available 返回 False。"""
        if importlib.util.find_spec("playwright") is not None:
            pytest.skip("本机已安装 Playwright，跳过缺依赖场景")
        assert browser.available() is False


# ---------------- 系统代理跟随 ----------------

class TestProxy:
    def test_env_override_wins(self, monkeypatch):
        """LAS_BROWSER_PROXY 优先于系统代理；裸地址补 http://。"""
        monkeypatch.setenv("LAS_BROWSER_PROXY", "1.2.3.4:8080")
        monkeypatch.setattr(browser, "_read_system_proxy", lambda: "9.9.9.9:1")
        p = browser._detect_proxy()
        assert p["server"] == "http://1.2.3.4:8080"
        assert "127.0.0.1" in p["bypass"]

    def test_system_proxy_as_fallback(self, monkeypatch):
        """无环境变量时读系统代理（用户浏览器可达性 = agent 浏览器）。"""
        monkeypatch.delenv("LAS_BROWSER_PROXY", raising=False)
        monkeypatch.setattr(browser, "_read_system_proxy",
                            lambda: "127.0.0.1:7890")
        assert browser._detect_proxy()["server"] == "http://127.0.0.1:7890"

    def test_none_when_no_proxy_anywhere(self, monkeypatch):
        """两处都没有代理时返回 None，launch 不带 proxy 参数。"""
        monkeypatch.delenv("LAS_BROWSER_PROXY", raising=False)
        monkeypatch.setattr(browser, "_read_system_proxy", lambda: "")
        assert browser._detect_proxy() is None

    def test_bypass_keeps_loopback_direct(self, monkeypatch):
        """走代理时本机服务（如本地 ComfyUI）仍直连不被劫持。"""
        monkeypatch.setenv("LAS_BROWSER_PROXY", "http://1.2.3.4:8080")
        monkeypatch.setattr(browser, "_read_system_proxy", lambda: "")
        p = browser._detect_proxy()
        assert "localhost" in p["bypass"] and "<local>" in p["bypass"]


# ---------------- weblinks 抓取失败 → 降级提示 ----------------

class TestWeblinksFallbackHint:
    def test_failure_hints_browser_open(self, monkeypatch):
        """轻量抓取被拒时，提示模型改用 browser_open 用真实浏览器打开。"""
        import weblinks

        def boom(url):
            raise ConnectionError("Remote end closed connection")

        monkeypatch.setattr(weblinks, "_fetch", boom)
        res = weblinks._process_one_impl("https://salonboard.com/KLP/top")
        assert "browser_open" in res.part
        assert "抓取失败" in res.part
