# -*- coding: utf-8 -*-
"""ui_panel_dispatch.py：模型派发设置面板（不启动 Tk，仅测纯逻辑）。"""

import io

import config
import ui_panel_dispatch as panel


def _mc(key, vision=False, reasoning=False):
    return config.ModelConfig(key=key, provider_name="p",
                              model_id=key.split("/")[-1], display_name=key,
                              base_url="https://api.example.com/v1", api_key="k",
                              vision=vision, reasoning=reasoning)


class TestCloudItems:
    def test_skips_gpulocal_legacy(self):
        """本地功能已移除：gpulocal-* 遗留条目不作为派发目标。"""
        items = panel._cloud_items([_mc("gpulocal-8097/qwen"), _mc("deepseek/pro")])
        assert items == [("deepseek/pro", "deepseek/pro")]

    def test_capability_icons(self):
        items = panel._cloud_items([_mc("a/vision", vision=True, reasoning=True)])
        assert items == [("👁🧠 a/vision", "a/vision")]

    def test_keeps_order(self):
        items = panel._cloud_items([_mc("a/1"), _mc("b/2")])
        assert [k for _t, k in items] == ["a/1", "b/2"]


class TestImport:
    def test_show_exists(self):
        assert callable(panel.show)

    def test_no_retired_api_in_source(self):
        """回归：面板不得引用 (B) 收敛删掉的 API（否则打开面板即崩）。"""
        src = io.open(panel.__file__, encoding="utf-8").read()
        retired = ("brain_healthy", "localmodels", "_is_local_key",
                   'cfg["dispatch_model"]', 'cfg["dispatch_vision"]',
                   "set_dispatch_model", "set_dispatch_vision")
        assert [p for p in retired if p in src] == []
