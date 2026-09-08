# -*- coding: utf-8 -*-
"""聊天输入框交互：回车发送 / @ 文件与 / 命令候选弹窗（自 ui.py 抽出）。

职责单一：输入框键盘事件分发 + 候选弹窗生命周期。
按键决策矩阵 decide() 是纯函数，可脱离 Tk 做单元测试；
弹窗控制器通过注入 app 与图标函数工作，不反向依赖 ui 模块。
"""

from __future__ import annotations

import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import tools
import dircache
from i18n import t


# ---------------- Treeview 候选框小工具 ----------------

def tv_select(lb, i) -> int:
    """选中第 i 行（夹紧范围）并滚动可见，返回实际 i。

    lb 可能为 None：弹窗刚被销毁（hide）而按键事件仍在队列里——竞态下
    直接放弃本次选中，不抛 AttributeError。
    """
    if lb is None:
        return 0
    try:
        kids = lb.get_children("")
    except KeyError:                       # 控件已销毁（tkinter 抛 KeyError）
        return 0
    if not kids:
        return 0
    i = max(0, min(i, len(kids) - 1))
    lb.selection_set(kids[i])
    lb.see(kids[i])
    return i


def tv_index(lb) -> int:
    """当前选中行索引（无选中返回 0）。lb 为 None（弹窗已销毁）返回 0。"""
    if lb is None:
        return 0
    sel = lb.selection()
    return lb.index(sel[0]) if sel else 0


# ---------------- 按键决策矩阵（纯函数） ----------------

def decide(popup: str | None, k: str, char: str,
           shift: bool, ctrl: bool, exact_cmd: bool = False):
    """返回输入框对一次 KeyPress 的处置。

    popup: None | "cmd" | "at"（命令/文件候选弹窗）。
    返回值：
      ("confirm", popup)  回车/Tab 确认候选
      ("hide", popup)     Esc 关闭弹窗
      ("nav", +1/-1)      ↑↓ 移动候选选中项
      "rescan"            字符/退格：放行默认插入，随后重过滤候选
      "send"              无弹窗回车 → 发送
      None                其余放行 Text 默认行为（换行/移动光标）
    回车识别兼容 IME：部分输入法会改写 keysym，char 仍为 \\r/\\n。
    """
    is_enter = k in ("Return", "KP_Enter") or char in ("\r", "\n")
    if popup:
        if is_enter or k == "Tab":
            # 已输入完整命令（如 /help）时回车=直接发送，而非原样重插候选
            if popup == "cmd" and is_enter and exact_cmd:
                return "send"
            return ("confirm", popup)
        if k == "Escape":
            return ("hide", popup)
        if k in ("Up", "Down"):
            return ("nav", 1 if k == "Down" else -1)
        if (len(k) == 1 or k in ("BackSpace", "Delete")) and not is_enter:
            return "rescan"
        return None
    if is_enter and not shift and not ctrl:
        return "send"
    return None


class InputController:
    """输入框键盘事件与候选弹窗（/命令、@文件、➕ 速查菜单共用弹窗）。"""

    def __init__(self, app, emoji_icon, tree_icon_map):
        self.app = app
        self.emoji_icon = emoji_icon          # ui._emoji_icon 注入（避免环导入）
        self.tree_icon_map = tree_icon_map    # ui._TREE_ICON_MAP 注入
        self._cmd_pop = None
        self._cmd_lb = None
        self._cmd_cands: list = []
        self._cmd_idx = 0
        self._at_pop = None
        self._at_lb = None
        self._at_cands: list = []
        self._at_idx = 0
        self._menu_pop = None
        self._menu_lb = None
        self._menu_cmds: list = []

    # ---------------- 键盘事件入口 ----------------

    def on_keypress(self, event):
        """KeyPress 统一入口：返回 "break" 才能拦下 Text 类绑定（换行/移光标）。"""
        popup = self._popup_kind()
        k = event.keysym
        char = getattr(event, "char", "") or ""
        shift = bool(event.state & 0x0001)
        # ➕ 速查菜单开着时焦点仍在输入框（show_token_popup 抢焦点后归还），
        # 菜单自己的 <Key> 绑定收不到物理 Esc，必须在输入框路径关它
        if (popup is None and k == "Escape"
                and self._menu_pop is not None
                and self._menu_pop.winfo_exists()):
            self.menu_hide()
            return "break"
        ctrl = bool(event.state & 0x0004)
        word = self._cmd_word() if popup == "cmd" else ""
        cand = self._cmd_cands[self._cmd_idx] if (
            popup == "cmd" and self._cmd_cands) else None
        exact_cmd = popup == "cmd" and bool(word) and word == cand
        act = decide(popup, k, char, shift, ctrl, exact_cmd)
        if act is None:
            return None
        if act == "send":
            self.app._on_return(event)
            return "break"
        if act == "rescan":
            # 字符/退格：放行默认行为，之后按新内容重过滤候选
            self.app.root.after(0, self.rescan)
            return None
        kind, what = act[1], act[0]
        if kind == "cmd":
            if what == "confirm":
                self.cmd_insert()
            elif what == "hide":
                self.cmd_hide()
            else:
                self._cmd_idx = tv_select(self._cmd_lb, self._cmd_idx + act[1])
        else:
            if what == "confirm":
                self.at_insert()
            elif what == "hide":
                self.at_hide()
            else:
                self._at_idx = tv_select(self._at_lb, self._at_idx + act[1])
        return "break"

    def _cmd_word(self) -> str:
        """光标前正在输入的 /命令 token（未匹配到返回空串）。"""
        inp = self.app.input
        idx = inp.index("insert")
        line_start = inp.index(f"{idx} linestart")
        m = re.search(r"/[a-z]*$", inp.get(line_start, idx))
        return m.group(0) if m else ""

    def on_keyrelease(self, event):
        """KeyRelease：弹窗未开时检测 / 或 @ token，打开候选弹窗。"""
        if self._popup_kind():
            return None          # 弹窗逻辑在 KeyPress 阶段处理
        k = event.keysym
        if k in ("Return", "KP_Enter", "Tab", "Escape", "Up", "Down",
                 "Left", "Right", "BackSpace"):
            return
        self.open_scan()

    def _popup_kind(self) -> str | None:
        if self._cmd_pop is not None and self._cmd_pop.winfo_exists():
            return "cmd"
        if self._at_pop is not None and self._at_pop.winfo_exists():
            return "at"
        return None

    # ---------------- 候选弹窗重建 ----------------

    def rescan(self):
        """按当前光标前的 token 重建候选弹窗（输入过滤用）。"""
        self.cmd_hide()
        self.at_hide()
        self.open_scan()

    def open_scan(self):
        """检测光标前的 /命令 或 @文件 token，打开对应候选弹窗。"""
        idx = self.app.input.index("insert")
        line_start = self.app.input.index(f"{idx} linestart")
        prefix = self.app.input.get(line_start, idx)
        m_cmd = re.search(r"/[a-z]*$", prefix)
        m_at = re.search(r"@([^\s@]*)$", prefix)
        self.cmd_hide()
        self.menu_hide()   # ➕ 速查菜单与候选弹窗互斥，避免叠着挡视线
        if m_cmd:
            self.at_hide()
            word = m_cmd.group(0)
            # 前缀匹配 + 容错（多打的字母不算错：/brainstorme 也能命中 /brainstorm）
            cands = [c for c, _d, _key in self.app._COMMANDS
                     if c.startswith(word) or word.startswith(c)]
            if not cands:
                return
            self._cmd_cands = cands
            self._cmd_idx = 0

            def _pick_cmd(i):
                self._cmd_idx = i
                self.cmd_insert()

            rows = [(c, self.emoji_icon("26a1")) for c in cands]
            try:
                pop, lb = self.show_token_popup(rows, _pick_cmd)
                self._cmd_pop = pop
                self._cmd_lb = lb
            except Exception as e:       # noqa: BLE001
                self.app._set_status(f"命令弹窗错误: {e}")
            return
        self.at_hide()
        if not m_at:
            return
        cands = self.at_candidates(m_at.group(1))
        if not cands:
            # 静默无弹窗会让"@"像坏了一样；至少在状态栏说明原因
            self.app._set_status("@ 无匹配文件候选")
            return
        self._at_cands = cands
        self._at_idx = 0
        try:
            rows = [(p, self.at_icon(p)) for p in cands]
            pop, lb = self.show_token_popup(rows, lambda _i: self.at_insert())
            self._at_pop = pop
            self._at_lb = lb
        except Exception as e:       # noqa: BLE001
            self.app._set_status(f"弹窗错误: {e}")

    # ---------------- / 命令候选 ----------------
    def menu_hide(self):
        """销毁 ➕ 速查菜单弹窗并清空引用（与 cmd_hide/at_hide 同型）。"""
        if self._menu_pop is not None and self._menu_pop.winfo_exists():
            try:
                self._menu_pop.destroy()
            except Exception:         # noqa: BLE001
                pass
        self._menu_pop = None
        self._menu_lb = None

    def cmd_hide(self):
        if self._cmd_pop is not None and self._cmd_pop.winfo_exists():
            try:
                self._cmd_pop.destroy()
            except Exception:         # noqa: BLE001
                pass
        self._cmd_pop = None
        self._cmd_lb = None

    def cmd_insert(self):
        try:
            inp = self.app.input
            idx = inp.index("insert")
            line_start = inp.index(f"{idx} linestart")
            prefix = inp.get(line_start, idx)
            m = re.search(r"/[a-z]*$", prefix)
            word = m.group(0) if m else "/"
            start = f"{line_start}+{max(0, len(prefix) - len(word))}c"
            inp.delete(start, idx)
            # 优先取弹窗列表的实际选中项（键盘选择/鼠标点选都一致）
            i = self._cmd_idx
            try:
                if self._cmd_lb.selection():
                    i = tv_index(self._cmd_lb)
            except Exception:         # noqa: BLE001
                pass
            inp.insert(start, self._cmd_cands[i] + " ")
        except Exception:             # noqa: BLE001
            pass
        self.cmd_hide()

    # ---------------- @ 文件候选 ----------------

    def at_hide(self):
        if self._at_pop is not None and self._at_pop.winfo_exists():
            try:
                self._at_pop.destroy()
            except Exception:         # noqa: BLE001
                pass
        self._at_pop = None
        self._at_lb = None

    def at_candidates(self, frag: str) -> list:
        """工作区文件/目录候选：@ 后的片段做子串过滤（忽略大小写）。

        清单来自 dircache 的目录快照（TTL 30s，切目录/手动刷新时失效），
        每次按键只做内存子串过滤，大仓库不再全盘 os.walk。
        """
        import os
        try:
            ws = tools.get_workspace() or os.getcwd()
        except Exception:             # noqa: BLE001
            ws = os.getcwd()
        frag_l = (frag or "").lower()
        files = dircache.list_files(ws)
        return [p for p in files if frag_l in p.lower()][:80]

    def at_icon(self, path: str):
        """@ 候选行的彩色图标：目录 📁，文件按扩展名映射。"""
        key = "1f4c1" if path.endswith("/") else self.tree_icon_map.get(
            path.rsplit(".", 1)[-1].lower() if "." in path else "", "1f4c4")
        return self.emoji_icon(key)

    def at_insert(self):
        path = None
        try:
            sel = self._at_lb.selection()
            if sel:
                path = self._at_cands[tv_index(self._at_lb)]
        except Exception as e:       # noqa: BLE001
            self.app._set_status(f"@ 确认异常(读取选中): {e}")
            return
        self.at_hide()
        if not path:
            self.app._set_status("@ 确认异常: 未取到选中项")
            return
        try:
            inp = self.app.input
            idx = inp.index("insert")
            line_start = inp.index(f"{idx} linestart")
            prefix = inp.get(line_start, idx)
            m = re.search(r"@[^\s@]*$", prefix)
            if m:
                start = f"{line_start}+{m.start(0)}c"
                inp.delete(start, idx)
                inp.insert(start, "@" + path + " ")
                self.app._set_status(f"已插入 @{path}")
            else:
                inp.insert("insert", "@" + path + " ")
                self.app._set_status(f"已插入 @{path}（光标处未找到 @token，已追加）")
        except Exception as e:       # noqa: BLE001
            self.app._set_status(f"@ 确认异常(插入): {e}")

    # ---------------- ➕ 斜杠命令速查菜单 ----------------

    def show_command_menu(self, anchor=None):
        """➕ 按钮：斜杠命令速查菜单（点选命令 → 插入输入框，可补参数后发送）。"""
        app = self.app
        rows = [(f"{c}   {t(d)}", self.emoji_icon("26a1"))
                for c, d, _k in app._COMMANDS]
        self._menu_cmds = [c for c, _d, _k in app._COMMANDS]
        try:
            pop, lb = self.show_token_popup(rows, self.on_command_menu_pick)
            self._menu_pop = pop
            self._menu_lb = lb
        except Exception as e:        # noqa: BLE001
            app._set_status(str(e))

    def on_command_menu_pick(self, i):
        cmd = self._menu_cmds[i] if i < len(self._menu_cmds) else None
        self.menu_hide()   # 选中即关：点完菜单不应留在屏上
        if cmd:
            self.insert_command(cmd)

    def insert_command(self, cmd):
        app = self.app
        if app._placeholder_active:
            app.input.delete("1.0", "end")
            app._placeholder_active = False
        app.input.insert("insert", cmd + " ")
        app.input.focus_set()

    # ---------------- 共用候选弹窗 ----------------

    def show_token_popup(self, rows, on_pick):
        """输入光标处的候选弹窗（/命令 与 @文件 共用）。

        rows: [(label, icon_photo_or_None)]。
        定位：优先光标下方；下方放不下改到光标上方；最后夹紧屏幕内。
        交互：滚轮滚动；单击 = 选中并回调 on_pick(索引)；图标走彩色 PNG。
        """
        app = self.app
        pop = tk.Toplevel(app.root)
        pop.overrideredirect(True)
        # Windows：弹窗创建后焦点立刻还给输入框，主窗口被激活时 WM 会把
        # 自己抬高，把不抢焦点的 overrideredirect 弹窗压在下面——弹窗
        # 坐标正常却整块不可见。-topmost 压住 z 序（与 ui.py 拖拽预览窗
        # 同一做法），焦点仍留给输入框，不影响键盘交互。
        try:
            pop.attributes("-topmost", True)
        except Exception:             # noqa: BLE001
            pass
        lb = ttk.Treeview(pop, show="tree",
                          selectmode="browse", height=min(len(rows), 10))
        for label, img in rows:
            kw = {"text": label}
            if img is not None:
                kw["image"] = img
            lb.insert("", "end", **kw)
        if rows:
            lb.selection_set(lb.get_children("")[0])
        # 树列默认 ~200px，长描述会被截断。按最长行实测像素宽定列宽：
        # 字体取 ttk 主题里 Treeview 实际用的（跟随 theme.apply），图标 ≤18px
        try:
            spec = ttk.Style(pop).lookup("Treeview", "font") or "TkDefaultFont"
            _f = tkfont.Font(font=spec)
            text_w = max((_f.measure(s) for s, _img in rows), default=0)
        except Exception:             # noqa: BLE001  量宽失败退回默认宽
            text_w = 0
        col_w = text_w + 18 + 16      # 图标 + 图文间距与列内边距
        lb.column("#0", width=col_w, minwidth=col_w, stretch=False)
        lb.pack(fill="both", expand=True)

        def _wheel(e):
            lb.yview_scroll(-1 * ((e.delta // 120) or 1), "units")

        def _pick(e):
            # 控件级 <Button-1> 先于 Treeview 类绑定执行：此刻 selection
            # 还是上一次点击的行（慢一拍）。直接取指针下的行，选中后
            # 再回调，保证点哪行插哪行；点空白区不做事、弹窗保留。
            row = lb.identify_row(e.y)
            if not row:
                return
            tv_select(lb, lb.index(row))
            on_pick(lb.index(row))

        lb.bind("<MouseWheel>", _wheel)
        lb.bind("<Button-1>", _pick)

        # ---- 键盘：弹窗接管全部按键（焦点显式给列表）----
        # 设计：lb.focus_set() 让键盘事件确定性地进入弹窗；回车/Tab 确认、
        # ↑↓ 选择、Esc 关闭、字符/退格转发回输入框后重过滤。
        # （输入框自己的 KeyPress 处理器仍保留，覆盖点击输入框后的场景。）
        def _popup_key(e):
            k = e.keysym
            if k in ("Return", "KP_Enter", "Tab"):
                on_pick(tv_index(lb))
                return "break"
            if k == "Escape":
                self.cmd_hide()
                self.menu_hide()
                self.at_hide()
                return "break"
            if k in ("Up", "Down"):
                tv_select(lb, tv_index(lb) + (1 if k == "Down" else -1))
                return "break"
            if k == "BackSpace":
                app.input.delete("insert-1c", "insert")
                app.root.after(0, self.rescan)
                return "break"
            if e.char and e.char.isprintable():
                app.input.insert("insert", e.char)
                app.root.after(0, self.rescan)
                return "break"
            return None

        for _w in (pop, lb):
            _w.bind("<Key>", _popup_key)
        lb.focus_set()

        # ---- 定位：先算可用空间，再决定上/下 ----
        pop.update_idletasks()
        bbox = app.input.bbox("insert")
        x = app.input.winfo_rootx() + (bbox[0] if bbox else 0)
        caret_y = app.input.winfo_rooty() + (bbox[1] if bbox else 0)
        line_h = (bbox[3] - bbox[1]) if bbox else 20
        h = lb.winfo_reqheight() + 4
        sh, sw = pop.winfo_screenheight(), pop.winfo_screenwidth()
        w = max(pop.winfo_reqwidth(), col_w + 6, 240)
        w = min(w, sw - 16)           # 兜底：超长内容不顶出屏幕
        below_y = caret_y + line_h + 6
        if below_y + h <= sh - 8:
            y = below_y                    # 下方放得下 → 光标下方
        else:
            y = max(8, caret_y - h - 6)    # 放不下 → 改到光标上方
        x = max(8, min(x, sw - w - 8))
        pop.geometry("%dx%d+%d+%d" % (w, h, x, y))
        # Windows 上新弹出的 Toplevel 会抢走键盘焦点——必须立刻把焦点还给
        # 输入框，否则回车/方向键事件进不了输入框的绑定
        # （Treeview 原生只响应方向键，这就是"回车选不中"的根源）
        try:
            app.input.focus_set()
        except Exception:             # noqa: BLE001
            pass
        # 焦点持续校正：与窗口管理器抢焦点的过程有竞态，弹窗存活期间
        # 每 80ms 把焦点拉回输入框一次（弹窗销毁后循环自然停止）
        def _reassert_focus():
            if pop.winfo_exists():
                try:
                    if app.root.focus_displayof() is not app.input:
                        app.input.focus_set()
                except Exception:     # noqa: BLE001
                    pass
                pop.after(80, _reassert_focus)
        _reassert_focus()
        # 双保险：即便焦点被抢到列表上，回车也直接确认
        lb.bind("<Return>", lambda _e: (on_pick(tv_index(lb)), "break")[1])
        lb.bind("<KP_Enter>", lambda _e: (on_pick(tv_index(lb)), "break")[1])
        return pop, lb
