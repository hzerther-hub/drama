#!/usr/bin/env bash
# =============================================================================
# 本地编程助手 · GPU 工作站模型栈 一键安装脚本（需 sudo，会提示输入密码）
# -----------------------------------------------------------------------------
# 机器：2x RTX 2080 Ti (NVLink 级联, 44 GiB) / Xeon W-2150B / Ubuntu 24.04
# 内容：工具链+CUDA toolkit → llama.cpp-dflash2(PR#27342) → systemd 用户服务
#       → （可选）从 ModelScope 下载模型
#
# 用法：  bash setup.sh            # 一次性装好工具链/编译/服务
#         bash setup.sh download   # 只下载模型（跳过编译/系统安装）
# =============================================================================
set -euo pipefail 2>/dev/null || true

# ---- 可调参数 ────────────────────────────────────────────────────────────────
LLAMA_DIR="$HOME/llama.cpp-dflash2"
BIN_DIR="$LLAMA_DIR/build/bin"
DEST="/home/wellfuture/build/gpulocal/services"      # 本脚本所在 services 目录
# ---- ModelScope 仓库 ───────────────────────────────────────────────────────
Q38_REPO="unsloth/Qwen3.8-27B-GGUF"               # Qwen3.8-27B 主模型(Q8_0)+mmproj
Q38_DR_REPO="z-lab/Qwen3.8-27B-DFlash2"           # DFlash2 drafter 源(safetensors，需转GGUF)
VL_REPO="unsloth/Qwen3-VL-32B-Instruct-GGUF"          # Qwen3-VL-32B (Q6_K)
ORN_REPO="ornith-ai/Ornith-1.5-35B-A3B-GGUF"          # Ornith-1.5-35B-A3B (Q6_K)
Q38_DIR="$HOME/models/Qwen3.8-27B-GGUF"
VL_DIR="$HOME/models/Qwen3-VL-32B-GGUF"
ORN_DIR="$HOME/models/Ornith-1.5-35B-A3B-GGUF"

log(){ echo; echo "==> $*"; }

# ---- Phase 0: 工具链 / CUDA toolkit / python ────────────────────────────────
install_toolchain(){
  log "安装 构建工具 + CUDA toolkit + python3-tk/pip"
  sudo apt update
  sudo apt install -y build-essential cmake git curl \
                     nvidia-cuda-toolkit \
                     python3-tk python3-pip
  nvcc --version || true
  python3 -c "import tkinter; print('tkinter', tkinter.TkVersion)"
}

# ---- Phase 1: llama.cpp-dflash2 (未合并 PR #27342) ──────────────────────────
build_llama(){
  log "克隆并构建 llama.cpp（PR #27342 / DFlash2）"
  if [ ! -d "$LLAMA_DIR" ]; then
    git clone https://github.com/ggerganov/llama.cpp.git "$LLAMA_DIR"
  fi
  cd "$LLAMA_DIR"
  git fetch origin pull/27342/head:pr-27342 || echo "!! PR#27342 拉取失败，请改用手动 patch"
  git checkout pr-27342 || git checkout -b pr-27342 pr-27342
  cmake -B build -DGGML_CUDA=ON -DGGML_CUDA_FA=ON -DGGML_NATIVE=ON -DGGML_OPENMP=ON
  cmake --build build --target llama-server -j"$(nproc)"
  "$BIN_DIR/llama-server" --version
}

# ---- Phase 3: systemd 用户服务 + linger ─────────────────────────────────────
install_services(){
  log "启用 linger 并安装用户服务"
  sudo loginctl enable-linger "$(whoami)" || true
  mkdir -p "$HOME/.config/systemd/user"
  cp "$DEST/qwen38-27b-q8.service" "$DEST/qwen3-vl-32b.service" \
     "$DEST/ornith-1.5-35b.service" "$HOME/.config/systemd/user/"
  systemctl --user daemon-reload
  systemctl --user status qwen38-27b-q8.service qwen3-vl-32b.service ornith-1.5-35b.service 2>&1 || true
  echo "  服务已加载。默认 disable；用面板或用以下命令启动："
  echo "    systemctl --user start qwen38-27b-q8.service   # 27B, 端口8097"
  echo "    systemctl --user start qwen3-vl-32b.service    # VL32B, 端口8098"
  echo "    systemctl --user start ornith-1.5-35b.service  # Ornith-1.5-35B, 端口8099"
}

# ---- Phase 4: 安装 modelscope 并下载模型 ────────────────────────────────────
pip_install_modelscope(){
  log "安装 modelscope"
  pip install --user modelscope 2>/dev/null || sudo pip install modelscope || true
  command -v modelscope || python3 -m modelscope --version || true
}

dl(){
  local repo="$1" dir="$2" files="$3"
  mkdir -p "$dir"
  # 文件作为位置参数传入；--local-dir 直接下载目录
  # shellcheck disable=SC2086
  modelscope download "$repo" $files --local-dir "$dir"
}

download_models(){
  pip_install_modelscope
  log "下载 Qwen3-VL-32B (Q6_K)  ← ${VL_REPO}"
  dl "$VL_REPO" "$VL_DIR" "Qwen3-VL-32B-Instruct-Q6_K.gguf mmproj-F16.gguf"
  log "下载 Ornith-1.5-35B-A3B (Q6_K, 双卡)  ← ${ORN_REPO}"
  dl "$ORN_REPO" "$ORN_DIR" "Ornith-1.5-35B-Q6_K.gguf mmproj-Ornith-1.5-35B-BF16.gguf"
  if [ -n "$Q38_REPO" ]; then
    log "下载 Qwen3.8-27B (Q8_0 + mmproj)  ← ${Q38_REPO}"
    dl "$Q38_REPO" "$Q38_DIR" "Qwen3.8-27B-Q8_0.gguf mmproj-BF16.gguf"
    log "下载 DFlash2 drafter 源(safetensors)  ← ${Q38_DR_REPO}"
    dl "$Q38_DR_REPO" "$Q38_DIR/drafter-src" "model.safetensors"
    echo "  !! DFlash2 drafter 需用 convert_hf_to_gguf.py 转成 Qwen3.8-27B-DFlash2-Q4_K_M.gguf"
  else
    echo "  !! Qwen3.8-27B 未配置 ModelScope 仓库(Q38_REPO)，请补充后重跑 download。"
  fi
  echo "  模型目录：$Q38_DIR / $VL_DIR / $ORN_DIR"
}

# ---- 主流程 ─────────────────────────────────────────────────────────────────
case "${1:-}" in
  download) download_models ;;
  *)
    install_toolchain
    build_llama
    install_services
    download_models
    echo
    echo "全部完成。启动面板："
    echo "    python3 /home/wellfuture/build/gpulocal/local_model_panel.py"
    ;;
esac
