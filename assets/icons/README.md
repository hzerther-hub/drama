# 图标素材

界面图标统一为**彩色 PNG**，由两个 MIT 许可的图标库栅格化而来（`LICENSE`）：

| 用途 | 图标库 | 风格 |
|---|---|---|
| 文件树、`@文件` 弹窗 | [Material Icon Theme](https://github.com/material-extensions/vscode-material-icon-theme) | VS Code 同款彩色文件图标，按扩展名给色，专为 16px 文件树设计 |
| 工具条、弹窗按钮 | [Fluent Emoji](https://github.com/microsoft/fluentui-emoji)（Color 版） | 微软彩色 emoji，体量大、小尺寸下仍认得出 |

- **为什么是 PNG**：UI 是 Tkinter，`tk.PhotoImage` 只认 PNG/GIF、不认 SVG，
  所以先用 `gen_icons.js` 把 SVG 栅格化成 128×128 PNG。
- **命名**：语义名（`file-py.png`、`folder.png`、`bot.png`…），由
  `ui._TREE_ICON_MAP`（扩展名 → 素材名）和 `ui._ICON_ALIAS`（emoji 码点 → 素材名）
  引用；两个映射都查 `ui._emoji_icon()`，素材缺失时回退 emoji 字形（界面不崩）。
- **换图标库**：只改 `gen_icons.js` 里 `FILE_ICONS` / `UI_ICONS` 两张表，
  `ui.py` 不用动——代码只认语义名。

重新生成：

```bash
npm i @resvg/resvg-js        # 预编译包，无需系统依赖
node assets/icons/gen_icons.js
```

> 选型备注：曾评估 iconfont 的「文件类型」图标集（如 cid=54289，78 个、原创免费），
> 但其图标是「文件页 + 扩展名文字」设计，靠文字表意；在本项目 16px 的文件树里
> 文字糊成一团不可读，且缺 `py`/`folder`。故改用按图形表意的 Material Icon Theme。
