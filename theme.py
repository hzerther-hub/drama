# -*- coding: utf-8 -*-
"""界面设计令牌：颜色/间距集中定义 + ttk clam 定制主题。

浅色 slate 体系 + 蓝色主题色，与全局扁平风一致。全 UI 的颜色都从这里取：
换肤/做暗色模式只需改本文件（未来加 DARK 色板 + 开关即可）。

theme.apply(root, base_font, mono_font) 基于 ttk 自带 clam 主题定制
Treeview（行高/去框）、Scrollbar（细、无刻痕）、PanedWindow（细分隔条），
消除系统默认控件的"原生粗糙感"；未装 clam（极老环境）静默跳过，不阻断启动。
"""

from __future__ import annotations

# ---------------- 颜色 ----------------
BG = "#f8fafc"            # 窗口底 / 按钮底
PANEL = "#ffffff"         # 面板、聊天区底
BORDER = "#e2e8f0"        # 1px 分隔线、行内代码底
TEXT = "#0f172a"          # 主文字
MUTED = "#64748b"         # 次要文字、提示、分组标题
ACCENT = "#2563eb"        # 主题色：链接、选中、强调条
ACCENT_SOFT = "#dbeafe"   # 主题色浅底：用户气泡
ACCENT_FAINT = "#eff6ff"  # 更浅：按钮悬停
SUCCESS = "#16a34a"       # 成功/生效
DANGER = "#dc2626"        # 停止/错误
DISPATCH = "#7c3aed"      # 模型派发/切换提示（紫）
BOT_BUBBLE = "#f1f5f9"    # 助手气泡底
STRIPE = "#f8fafc"        # 列表斑马纹
CODE_BLOCK_BG = "#0f172a"  # 代码块深底
CODE_BLOCK_FG = "#e2e8f0"  # 代码块文字

# ---------------- 间距节奏（px） ----------------
SP_1, SP_2, SP_3, SP_4 = 4, 8, 12, 16

# ---------------- 字号（工具条统一，不能忽大忽小） ----------------
FS_TOOLBAR = 11   # 工具条文字按钮统一字号（模型/语言/字体/附件/发送…）
FS_ICON = 11      # 工具条纯图标按钮统一字号（与文字按钮同大小）


def apply(root, base_font: str = "TkDefaultFont", mono_font: str = "TkFixedFont"):
    """全量应用：窗口底色 + clam 定制（Treeview/滚动条/分栏条/右键菜单）。

    base_font / mono_font 传字体族名（如 ui.FONT_UI），树列表与菜单跟随。
    幂等：重复调用只覆盖同样式。
    """
    root.configure(bg=BG)
    import tkinter.ttk as ttk
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:                     # noqa: BLE001  无 clam → 保持默认
        return

    # 树列表：加行高、去边框、选中态用主题色
    style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                    foreground=TEXT, borderwidth=0, relief="flat",
                    rowheight=26, font=(base_font, 10))
    style.map("Treeview",
              background=[("selected", ACCENT_SOFT)],
              foreground=[("selected", TEXT)])
    style.configure("Treeview.Heading", background=PANEL, relief="flat",
                    borderwidth=0, font=(base_font, 10, "bold"))
    style.map("Treeview.Heading", background=[("active", PANEL)])

    # 滚动条：细、无箭头刻痕、浅槽
    style.configure("Vertical.TScrollbar", background=BORDER,
                    troughcolor=PANEL, borderwidth=0, arrowsize=11,
                    gripcount=0)
    style.map("Vertical.TScrollbar",
              background=[("active", MUTED), ("pressed", MUTED)])
    style.configure("Horizontal.TScrollbar", background=BORDER,
                    troughcolor=PANEL, borderwidth=0, gripcount=0)

    # 分栏分隔条：细线化
    style.configure("TPaned", borderwidth=0)

    # 右键/下拉菜单（tk.Menu）：白底、无立体边框、主题色悬停
    root.option_add("*Menu.background", PANEL)
    root.option_add("*Menu.foreground", TEXT)
    root.option_add("*Menu.borderWidth", 1)
    root.option_add("*Menu.activeBorderWidth", 0)
    root.option_add("*Menu.activeBackground", ACCENT_FAINT)
    root.option_add("*Menu.font", (base_font, 10))
