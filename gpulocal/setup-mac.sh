#!/usr/bin/env bash
# =============================================================================
# gpulocal 本地模型面板 · macOS 一键准备脚本
# -----------------------------------------------------------------------------
# macOS 没有 systemd，面板以【后台进程】方式启停 llama-server
# （见 local_model_panel.py 的 svc_* → win_svc_* 进程守护路径）。
# 本脚本负责：
#   1) 用 Homebrew 安装 llama.cpp（含 Metal 加速的 llama-server，进 PATH）、
#      git、modelscope（pip 用户安装）；
#   2) 检查 Tkinter（面板 GUI 依赖；python.org / brew python 自带，
#      缺了会提示装 python-tk）；
#   3) 从 ModelScope 下载模型到 ~/models/<模型目录>（与注册表 models_dir 一致）。
#
# 用法：  bash setup-mac.sh            # 一键装好工具链 + 下载模型
#         bash setup-mac.sh download   # 只下载模型
#         bash setup-mac.sh toolchain  # 只装工具链（不下载模型）
# =============================================================================
set -euo pipefail 2>/dev/null || true

# ---- ModelScope 仓库（与 setup.sh 保持一致） ────────────────────────────────
Q38_REPO="unsloth/Qwen3.8-27B-GGUF"               # Qwen3.8-27B 主模型(Q8_0)+mmproj
VL_REPO="unsloth/Qwen3-VL-32B-Instruct-GGUF"          # Qwen3-VL-32B (Q6_K)
ORN_REPO="ornith-ai/Ornith-1.5-35B-A3B-GGUF"          # Ornith-1.5-35B-A3B (Q6_K)
Q38_DIR="$HOME/models/Qwen3.8-27B-GGUF"
VL_DIR="$HOME/models/Qwen3-VL-32B-GGUF"
ORN_DIR="$HOME/models/Ornith-1.5-35B-A3B-GGUF"

log(){ echo; echo "==> $*"; }

# ---- Phase 0: Homebrew + llama.cpp + python/tk ──────────────────────────────
install_toolchain(){
  if ! command -v brew >/dev/null 2>&1; then
    echo "未找到 Homebrew。先安装：https://brew.sh"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
  fi

  log "安装 llama.cpp（Metal 加速）+ git"
  brew install llama.cpp git
  command -v llama-server && llama-server --version || true

  log "检查 Tkinter（面板 GUI 依赖）"
  if python3 -c "import tkinter" 2>/dev/null; then
    python3 -c "import tkinter; print('  tkinter', tkinter.TkVersion)"
  else
    echo "  !! 当前 python3 缺 tkinter。任选其一："
    echo "     - brew install python-tk@3.13（按你的 python 版本调整）"
    echo "     - 或装 python.org 官方 Python（自带 tkinter）"
  fi

  log "安装 modelscope（pip 用户安装）"
  python3 -m pip install --user modelscope || \
    python3 -m pip install --user --break-system-packages modelscope || true
  python3 -m modelscope --version 2>/dev/null || \
    echo "  !! modelscope 未就绪，可稍后手动: python3 -m pip install --user modelscope"
}

# ---- Phase 1: 下载模型 ──────────────────────────────────────────────────────
dl(){
  local repo="$1" dir="$2" files="$3"
  mkdir -p "$dir"
  # 文件作为位置参数传入；--local-dir 直接下载目录
  # shellcheck disable=SC2086
  python3 -m modelscope download "$repo" $files --local-dir "$dir"
}

download_models(){
  if ! python3 -m modelscope --version >/dev/null 2>&1; then
    log "安装 modelscope"
    python3 -m pip install --user modelscope || \
      python3 -m pip install --user --break-system-packages modelscope
  fi

  log "下载 Qwen3-VL-32B (Q6_K)  ← ${VL_REPO}"
  dl "$VL_REPO" "$VL_DIR" "Qwen3-VL-32B-Instruct-Q6_K.gguf mmproj-F16.gguf"

  log "下载 Ornith-1.5-35B-A3B (Q6_K)  ← ${ORN_REPO}"
  dl "$ORN_REPO" "$ORN_DIR" "Ornith-1.5-35B-Q6_K.gguf mmproj-Ornith-1.5-35B-BF16.gguf"

  log "下载 Qwen3.8-27B (Q8_0 + mmproj)  ← ${Q38_REPO}"
  dl "$Q38_REPO" "$Q38_DIR" "Qwen3.8-27B-Q8_0.gguf mmproj-BF16.gguf"
  echo "  注：DFlash2 投机解码 drafter 面向 CUDA(PR#27342)，macOS/Metal 下不使用；"
  echo "      面板在无 drafter 文件时按普通解码运行。"

  echo "  模型目录：$Q38_DIR / $VL_DIR / $ORN_DIR"
}

# ---- 主流程 ─────────────────────────────────────────────────────────────────
case "${1:-}" in
  download)  download_models ;;
  toolchain) install_toolchain ;;
  *)
    install_toolchain
    download_models
    echo
    echo "全部完成。启动面板："
    echo "    python3 $(cd "$(dirname "$0")" && pwd)/local_model_panel.py"
    echo "macOS 上以【后台进程】方式启停模型（状态目录 ~/.gpulocal/run/），"
    echo "无需 systemd；llama-server 已在 PATH 中，注册表无需改路径。"
    ;;
esac
