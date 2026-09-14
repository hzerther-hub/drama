// 生成 assets/icons/*.png —— 本目录图标素材全部由两个 MIT 许可的彩色图标库栅格化而来。
//
//   文件树 / @文件弹窗：Material Icon Theme（VS Code 同款彩色文件图标，MIT）
//                       —— 按扩展名给色，专为 16px 文件树设计，小尺寸下清楚。
//   工具条 / 弹窗按钮  ：Fluent Emoji（微软，MIT）Color 版
//                       —— 彩色、体量大、16px 下仍认得出。
//
// 为什么必须是 PNG：UI 是 Tkinter，tk.PhotoImage 只认 PNG/GIF、不认 SVG。
//
// 重新生成：
//   npm i @resvg/resvg-js        # 预编译包，无系统依赖
//   node assets/icons/gen_icons.js
//
// 素材名是「语义名」（file-py / folder / bot / brain…），由 ui._TREE_ICON_MAP
// （扩展名 → 素材名）和 ui._ICON_ALIAS（emoji 码点 → 素材名）引用。
// 换图标库只改下面两张表，ui.py 不用动。
const fs = require("fs");
const path = require("path");
const { Resvg } = require("@resvg/resvg-js");

// 语义名 -> Material Icon Theme 图标名
const FILE_ICONS = {
  "file-py": "python",
  "file-js": "javascript",
  "file-ts": "typescript",
  "file-html": "html",
  "file-css": "css",
  "file-md": "markdown",
  "file-text": "document",
  "file-json": "json",
  "file-cog": "settings",
  "file-notebook": "jupyter",
  "file-image": "image",
  "file-sheet": "table",
  "file-archive": "zip",
  "file-pdf": "pdf",
  "file-doc": "word",
  "file-audio": "audio",
  "file-video": "video",
  "file-shell": "console",
  "file-generic": "document",
  folder: "folder",
};

// 语义名 -> Fluent Emoji 的 "文件夹/文件名"（Color 版：assets/<目录>/Color/<文件>_color.svg）
const UI_ICONS = {
  bot: ["Robot", "robot"],
  brain: ["Brain", "brain"],
  settings: ["Gear", "gear"],
  chat: ["Speech balloon", "speech_balloon"],
  refresh: ["Counterclockwise arrows button", "counterclockwise_arrows_button"],
  help: ["White question mark", "white_question_mark"],
  camera: ["Camera with flash", "camera_with_flash"],
  timer: ["Timer clock", "timer_clock"],
  link: ["Link", "link"],
  scissors: ["Scissors", "scissors"],
  lock: ["Locked", "locked"],
  shield: ["Shield", "shield"],
  zap: ["High voltage", "high_voltage"],
  route: ["Shuffle tracks button", "shuffle_tracks_button"],
  quant: ["Chart increasing", "chart_increasing"],
  kb: ["Books", "books"],
  circle: ["White circle", "white_circle"],
  ban: ["Prohibited", "prohibited"],
  turtle: ["Turtle", "turtle"],
  flame: ["Fire", "fire"],
  rocket: ["Rocket", "rocket"],
};

const MIT_CDN = "https://cdn.jsdelivr.net/npm/material-icon-theme@latest/icons/";
const FLUENT_CDN = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/";
const OUT_DIR = __dirname;
const SIZE = 128;                 // ui._emoji_icon 会按 2 的幂逐级缩到 ~16px

async function fetchText(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`拉取失败 ${res.status}：${url}`);
  return await res.text();
}

function render(svg, outName) {
  const resvg = new Resvg(svg, {
    fitTo: { mode: "width", value: SIZE },
    background: "rgba(0,0,0,0)",
  });
  fs.writeFileSync(path.join(OUT_DIR, outName + ".png"), resvg.render().asPng());
}

(async () => {
  const failed = [];
  let ok = 0;

  for (const [asset, icon] of Object.entries(FILE_ICONS)) {
    try {
      render(await fetchText(MIT_CDN + icon + ".svg"), asset);
      ok++;
    } catch (e) {
      failed.push(`${asset}(${icon}): ${e.message}`);
    }
  }

  for (const [asset, [dir, file]] of Object.entries(UI_ICONS)) {
    try {
      const url = FLUENT_CDN + encodeURIComponent(dir) + `/Color/${file}_color.svg`;
      render(await fetchText(url), asset);
      ok++;
    } catch (e) {
      failed.push(`${asset}(${dir}): ${e.message}`);
    }
  }

  console.log(`已生成 ${ok} 个图标 → ${OUT_DIR}`);
  if (failed.length) {
    console.error("失败：\n  " + failed.join("\n  "));
    process.exitCode = 1;
  }
})();
