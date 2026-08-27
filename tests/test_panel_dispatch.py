# -*- coding: utf-8 -*-
"""ui_panel_dispatch.py：模型派发设置面板（不启动 Tk，仅测纯逻辑）。"""

import ui_panel_dispatch as panel


class TestDot:
    def test_healthy(self):
        assert panel._dot_of("m", {"m": ("active", True)}) == "●"

    def test_activating(self):
        assert panel._dot_of("m", {"m": ("activating", False)}) == "◐"

    def test_stopped_or_unknown(self):
        assert panel._dot_of("m", {"m": ("inactive", False)}) == "○"
        assert panel._dot_of("m", {}) == "○"


class TestImport:
    def test_show_exists(self):
        assert callable(panel.show)
