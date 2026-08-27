"""图片标注对话框（居中、模态、容器内）—— 对齐 qwen-cordis 截图标注功能。

portal 截好图后弹出本窗：提供 框形/椭圆/直线/箭头/画笔/马赛克/文字 标注，
可选颜色、支持撤销/重做；✔完成把标注烧录进图片保存并回调 on_done(path)，
✕取消回调 on_done(None)。不含“再截图”（截图已由 portal 完成）。
"""
import os
import tempfile

import tkinter as tk
import theme

from PIL import Image, ImageDraw, ImageFont, ImageTk

import ui

COLORS = [("#ef4444", "红"), ("#2563eb", "蓝"), ("#22c55e", "绿"), ("#eab308", "黄"),
          ("#a855f7", "紫"), ("#f97316", "橙"), ("#0f172a", "黑"), ("#ffffff", "白")]
TOOLS = [("select", "选择/调整"), ("rect", "框形"), ("ellipse", "椭圆"), ("line", "直线"),
         ("arrow", "箭头"), ("pen", "画笔"), ("mosaic", "马赛克"), ("text", "文字")]


def _fit(w, h, max_w, max_h):
    sw, sh = w / max_w, h / max_h
    scale = 1.0 if max(sw, sh) <= 1 else 1.0 / max(sw, sh)
    return scale, int(w * scale), int(h * scale)


def _font(size):
    for c in ("C:/Windows/Fonts/msyh.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def show(app, image_path, on_done):
    from tkinter import simpledialog as _sd

    win = tk.Toplevel(app.root)
    win.title("图片标注")
    win.configure(bg=theme.BOT_BUBBLE)
    ui._make_modal(win, app.root)

    img = Image.open(image_path).convert("RGB")
    ow, oh = img.size
    scale, dw, dh = _fit(ow, oh, 720, 520)
    disp = img.resize((dw, dh))
    photo = ImageTk.PhotoImage(disp)

    canvas = tk.Canvas(win, width=dw, height=dh, bg="#0f172a",
                       highlightthickness=0, cursor="crosshair")
    canvas.pack(padx=12, pady=(12, 4))
    canvas.create_image(0, 0, image=photo, anchor="nw")
    canvas.image = photo

    HANDLE = 6
    state = {"tool": "rect", "color": "#ef4444", "width": 3, "textsize": 12,
             "shapes": [], "redo": [], "drawing": None, "cur": None,
             "selected": None, "resize": None}

    def _draw_shape(canvas, s):
        t, col, w = s["type"], s["color"], s["width"]
        T = {"tags": "shape"}
        if t == "rect":
            return canvas.create_rectangle(s["x1"], s["y1"], s["x2"], s["y2"],
                                           outline=col, width=w, **T)
        if t == "ellipse":
            return canvas.create_oval(s["x1"], s["y1"], s["x2"], s["y2"],
                                      outline=col, width=w, **T)
        if t == "line":
            return canvas.create_line(s["x1"], s["y1"], s["x2"], s["y2"],
                                      fill=col, width=w, **T)
        if t == "arrow":
            import math
            x1, y1, x2, y2 = s["x1"], s["y1"], s["x2"], s["y2"]
            ang = math.atan2(y2 - y1, x2 - x1)
            ah = max(8, w * 2.5)
            return canvas.create_line(x1, y1, x2, y2, fill=col, width=w,
                                      arrow="last", arrowshape=(ah, ah, ah * 0.7), **T)
        if t == "pen":
            pts = s.get("pts") or []
            return canvas.create_line(*[c for p in pts for c in p], fill=col, width=w,
                                      capstyle="round", joinstyle="round", **T)
        if t == "mosaic":
            pts = s.get("pts") or []
            return canvas.create_line(*[c for p in pts for c in p], fill=col, width=w * 5,
                                      capstyle="round", joinstyle="round", **T)
        if t == "text":
            return canvas.create_text(s["x1"], s["y1"], text=s.get("text", ""),
                                      fill=col, font=(ui.FONT_UI, s.get("textsize", state["textsize"]), "bold"),
                                      anchor="w", **T)
        return None

    def _redraw():
        canvas.delete("shape")
        for s in state["shapes"]:
            _draw_shape(canvas, s)

    def _hit(x, y):
        for s in reversed(state["shapes"]):
            if s["type"] in ("pen", "mosaic"):
                if any(abs(px - x) < HANDLE + s["width"] and abs(py - y) < HANDLE + s["width"]
                       for px, py in s.get("pts", [])):
                    return s
            elif s["type"] == "text":
                ts = s.get("textsize", 12)
                xa, ya = s["x1"], s["y1"]
                xb = xa + max(40, len(s.get("text", "")) * ts * 0.9) + 6
                yb = ya + ts * 1.6
                if (xa - 4) <= x <= xb and (ya - ts) <= y <= yb:
                    return s
            else:
                x1, y1, x2, y2 = s["x1"], s["y1"], s["x2"], s["y2"]
                if min(x1, x2) - HANDLE <= x <= max(x1, x2) + HANDLE and \
                   min(y1, y2) - HANDLE <= y <= max(y1, y2) + HANDLE:
                    return s
        return None

    def _handles(s):
        x1, y1, x2, y2 = s["x1"], s["y1"], s["x2"], s["y2"]
        w = HANDLE
        return [(x1, y1), ((x1 + x2) / 2, y1), (x2, y1), (x2, (y1 + y2) / 2),
                (x2, y2), ((x1 + x2) / 2, y2), (x1, y2), (x1, (y1 + y2) / 2)]
    _HANDSET = None
    def _draw_handles():
        canvas.delete("handles")
        s = state.get("selected")
        if not s:
            state["_HANDSET"] = None
            return
        if s["type"] == "text":
            # 文字：画选中框（无 8 手柄，但可见选中态；字号可改）
            ts = s.get("textsize", 12)
            x1, y1 = s["x1"], s["y1"]
            x2 = x1 + max(40, len(s.get("text", "")) * ts * 0.9)
            y2 = y1 + ts * 1.6
            canvas.create_rectangle(x1 - 3, y1 - ts, x2, y2,
                                    outline="#0a84ff", width=1, dash=(2, 2), tags="handles")
            canvas.create_text(x1 - 3, y1 - ts, text=str(s.get("textsize", ts)),
                               fill="#0a84ff", font=(ui.FONT_UI, 8), anchor="sw", tags="handles")
            state["_HANDSET"] = None
            return
        if s["type"] in ("pen", "mosaic"):
            return
        state["_HANDSET"] = _handles(s)
        for hx, hy in state["_HANDSET"]:
            canvas.create_rectangle(hx - 3, hy - 3, hx + 3, hy + 3,
                                    fill="#0a84ff", outline="white", tags="handles")
        canvas.create_rectangle(min(s["x1"], s["x2"]), min(s["y1"], s["y2"]),
                                max(s["x1"], s["x2"]), max(s["y1"], s["y2"]),
                                outline="#0a84ff", width=1, dash=(2, 2), tags="handles")

    def _on_press(e):
        t = state["tool"]
        if t == "select":
            # 先判手柄命中，其次形状命中
            hs = state.get("_HANDSET")
            if hs and state.get("selected"):
                for i, (hx, hy) in enumerate(hs):
                    if abs(e.x - hx) <= HANDLE + 2 and abs(e.y - hy) <= HANDLE + 2:
                        state["resize"] = i
                        return
            s = _hit(e.x, e.y)
            state["selected"] = s
            state["resize"] = None
            _draw_handles()
            return
        if t == "text":
            txt = _sd.askstring("文字", "输入文字：", parent=win)
            if txt and txt.strip():
                s = {"type": "text", "x1": e.x, "y1": e.y,
                     "color": state["color"], "width": state["width"],
                     "text": txt.strip(), "textsize": state["textsize"]}
                state["shapes"].append(s); state["redo"].clear(); _redraw()
            return
        s = {"type": t, "x1": e.x, "y1": e.y, "x2": e.x, "y2": e.y,
             "color": state["color"], "width": state["width"],
             "pts": [(e.x, e.y)] if t in ("pen", "mosaic") else []}
        state["cur"] = s
        if t in ("pen", "mosaic"):
            state["drawing"] = _draw_shape(canvas, s)     # 临时绘制，释放时才入列
        else:
            _redraw()

    def _on_motion(e):
        t = state["tool"]
        if t == "select":
            s = state.get("selected")
            if s and state.get("resize") is not None and s["type"] not in ("pen", "mosaic", "text"):
                x1, y1, x2, y2 = s["x1"], s["y1"], s["x2"], s["y2"]
                i = state["resize"]
                # 8 手柄:0 左上,1 上中,2 右上,3 右中,4 右下,5 下中,6 左下,7 左中
                for j in range(8):
                    if i == 0: x1, y1 = e.x, e.y
                    elif i == 1: y1 = e.y
                    elif i == 2: x2, y1 = e.x, e.y
                    elif i == 3: x2 = e.x
                    elif i == 4: x2, y2 = e.x, e.y
                    elif i == 5: y2 = e.y
                    elif i == 6: x1, y2 = e.x, e.y
                    elif i == 7: x1 = e.x
                    break
                s["x1"], s["y1"], s["x2"], s["y2"] = x1, y1, x2, y2
                _redraw(); _draw_handles()
            return
        s = state.get("cur")
        if not s or t in ("text",):
            return
        if t in ("pen", "mosaic"):
            s["pts"].append((e.x, e.y))
            if state.get("drawing") is not None:
                canvas.delete(state["drawing"])
            state["drawing"] = _draw_shape(canvas, s)
        else:
            s["x2"], s["y2"] = e.x, e.y
            _redraw()

    def _on_release(e):
        t = state["tool"]
        if t == "select":
            state["resize"] = None
            if state.get("selected"):
                _draw_handles()
            return
        s = state.get("cur")
        if not s or t in ("text",):
            return
        if t in ("pen", "mosaic"):
            if state.get("drawing") is not None:
                canvas.delete(state["drawing"])
        else:
            s["x2"], s["y2"] = e.x, e.y
            if abs(s["x2"] - s["x1"]) + abs(s["y2"] - s["y1"]) < 4:
                state["cur"] = None
                return
        state["shapes"].append(s)
        state["redo"].clear()
        state["cur"] = None
        state["drawing"] = None
        _redraw()

    canvas.bind("<Delete>", lambda e: _del_sel())

    def _del_sel():
        s = state.get("selected")
        if s and s in state["shapes"]:
            state["shapes"].remove(s)
            state["selected"] = None
            state["redo"].clear()
            _redraw(); _draw_handles()

    canvas.bind("<ButtonPress-1>", _on_press)
    canvas.bind("<B1-Motion>", _on_motion)
    canvas.bind("<ButtonRelease-1>", _on_release)

    tbar = tk.Frame(win, bg="#f1f5f9")
    tbar.pack(fill="x", padx=12, pady=(8, 0))
    var_tool = tk.StringVar(value="rect")
    for key, name in TOOLS:
        tk.Radiobutton(tbar, text=name, value=key, variable=var_tool, bg="#f1f5f9",
                       font=(ui.FONT_UI, 9), command=lambda k=key: state.__setitem__("tool", k)
                       ).pack(side="left")
    tk.Label(tbar, text="颜色:", bg="#f1f5f9", fg="#64748b", font=(ui.FONT_UI, 9)).pack(side="left", padx=(10, 2))
    swatches = []
    def _pick_color(c):
        state["color"] = c
        for hx, btn in swatches:
            btn.config(highlightbackground=("#0a84ff" if hx == c else "#f1f5f9"),
                       highlightthickness=2)
    for hexc, _name in COLORS:
        btn = tk.Button(tbar, bg=hexc, width=2, relief="flat", cursor="hand2",
                        command=lambda c=hexc: _pick_color(c), bd=0, padx=0, pady=2)
        btn.pack(side="left", padx=1)
        swatches.append((hexc, btn))
    _pick_color("#ef4444")
    tk.Label(tbar, text="宽度:", bg="#f1f5f9", fg="#64748b", font=(ui.FONT_UI, 9)).pack(side="left", padx=(8, 2))
    var_w = tk.IntVar(value=3)
    tk.Spinbox(tbar, from_=1, to=10, textvariable=var_w, width=3, font=(ui.FONT_UI, 9),
               command=lambda: state.__setitem__("width", var_w.get())).pack(side="left")
    tk.Label(tbar, text="字号:", bg="#f1f5f9", fg="#64748b", font=(ui.FONT_UI, 9)).pack(side="left", padx=(8, 2))
    var_fs = tk.IntVar(value=12)
    def _fs_changed():
        state["textsize"] = var_fs.get()
        sel = state.get("selected")
        if sel and sel["type"] == "text":
            sel["textsize"] = var_fs.get()
            _redraw(); _draw_handles()
    tk.Spinbox(tbar, from_=6, to=48, textvariable=var_fs, width=3, font=(ui.FONT_UI, 9),
               command=_fs_changed).pack(side="left")

    tbar2 = tk.Frame(win, bg="#f1f5f9")
    tbar2.pack(fill="x", padx=12, pady=(4, 6))
    ui._flat_button(tbar2, text="↶ 撤销", command=lambda: _undo(), width=7).pack(side="left")
    ui._flat_button(tbar2, text="↷ 重做", command=lambda: _redo(), width=7).pack(side="left", padx=4)
    tk.Label(tbar2, text="拖动画形状 / 点图输文字，界面即标注", bg="#f1f5f9", fg="#64748b",
             font=(ui.FONT_UI, 9)).pack(side="left", padx=(12, 0))
    ui._flat_button(tbar2, text="✔ 完成", command=lambda: _save(), width=8,
                    font=(ui.FONT_UI, 10)).pack(side="right")
    ui._flat_button(tbar2, text="✕ 取消", command=lambda: _cancel(), width=8,
                    font=(ui.FONT_UI, 10)).pack(side="right", padx=(0, 8))

    def _undo():
        if state["shapes"]:
            state["redo"].append(state["shapes"].pop())
            _redraw()

    def _redo():
        if state["redo"]:
            state["shapes"].append(state["redo"].pop())
            _redraw()

    def _draw_pil(draw, s):
        col, w = s["color"], max(1, int(s["width"] / max(scale, 1e-6)))
        if s["type"] in ("rect", "ellipse"):
            box = [c / max(scale, 1e-6) for c in (s["x1"], s["y1"], s["x2"], s["y2"])]
            draw.rectangle(box, outline=col, width=w) if s["type"] == "rect" else \
                draw.ellipse(box, outline=col, width=w)
        elif s["type"] == "line":
            draw.line([s["x1"] / max(scale, 1e-6), s["y1"] / max(scale, 1e-6),
                       s["x2"] / max(scale, 1e-6), s["y2"] / max(scale, 1e-6)], fill=col, width=w)
        elif s["type"] == "arrow":
            import math
            x1, y1, x2, y2 = [c / max(scale, 1e-6) for c in (s["x1"], s["y1"], s["x2"], s["y2"])]
            ang = math.atan2(y2 - y1, x2 - x1)
            ah = max(10, w * 2.5)
            draw.line([x1, y1, x2, y2], fill=col, width=w)
            draw.line([x2, y2, x2 - ah * math.cos(ang - 0.5), y2 - ah * math.sin(ang - 0.5)], fill=col, width=w)
            draw.line([x2, y2, x2 - ah * math.cos(ang + 0.5), y2 - ah * math.sin(ang + 0.5)], fill=col, width=w)
        elif s["type"] == "pen":
            pts = [c / max(scale, 1e-6) for p in s.get("pts", []) for c in p]
            if pts:
                draw.line(pts, fill=col, width=w, joint="curve")
        elif s["type"] == "mosaic":
            # 马赛克：对路径周围做像素化插值（简化为加粗模糊色块）
            pts = [(c / max(scale, 1e-6)) for p in s.get("pts", []) for c in p]
            if pts:
                draw.line(pts, fill=col, width=w * 5, joint="curve")
        elif s["type"] == "text":
            f = _font(max(8, int(s.get("textsize", state["textsize"]) / max(scale, 1e-6))))
            draw.text((s["x1"] / max(scale, 1e-6), s["y1"] / max(scale, 1e-6)),
                      s.get("text", ""), fill=col, font=f)

    def _save():
        out = ImageDraw.Draw(img)
        for s in state["shapes"]:
            _draw_pil(out, s)
        fd, out_path = tempfile.mkstemp(suffix=".png", prefix="annot_")
        os.close(fd)
        img.save(out_path)
        win.destroy()
        on_done(out_path)

    def _cancel():
        win.destroy()
        on_done(None)

    var_tool.trace_add("write", lambda *a: state.__setitem__("tool", var_tool.get()))

    win.update_idletasks()
    x = app.root.winfo_rootx() + (app.root.winfo_width() - dw) // 2
    y = app.root.winfo_rooty() + (app.root.winfo_height() - dh) // 2 - 40
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    canvas.focus_set()
