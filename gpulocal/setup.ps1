# setup.ps1 — gpulocal 本地模型面板 · Windows 一键准备脚本
# -----------------------------------------------------------------------------
# 用途：Windows 上没有 systemd，本面板改用以【后台进程】方式启动 llama.cpp
#       server（见 local_model_panel.py 的 svc_*/win_svc_*）。本脚本负责：
#         1) 检查/编译 llama-server.exe（llama.cpp），
#         2) 下载模型（可选，走 ModelScope），
#         3) 提示如何运行面板与配置路径。
# 需要：git、CMake 3.14+、Visual Studio 2022 生成工具（含 C++ 桌面工作负载）。
# 以管理员 PowerShell 或普通 PowerShell 均可运行本脚本。
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"
$LLAMA_DIR = Join-Path $HOME "llama.cpp"
$BUILD_DIR = Join-Path $LLAMA_DIR "build\bin\Release"
$SERVER = "llama-server.exe"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

function Find-LlamaServer {
    # 优先 PATH，其次默认编译目录
    if (Get-Command $SERVER -ErrorAction SilentlyContinue) {
        return (Get-Command $SERVER).Source
    }
    $f = Join-Path $BUILD_DIR $SERVER
    if (Test-Path $f) { return $f }
    return $null
}

Write-Step "检查 llama-server.exe"
$serverPath = Find-LlamaServer
if ($serverPath) {
    Write-Host "  已找到: $serverPath" -ForegroundColor Green
} else {
    Write-Host "  未找到，准备从源码编译 llama.cpp ..." -ForegroundColor Yellow
    foreach ($t in @("git", "cmake")) {
        if (-not (Get-Command $t -ErrorAction SilentlyContinue)) {
            throw "缺少 $t，请先安装：https://git-scm.com / https://cmake.org"
        }
    }
    Write-Step "克隆/更新 llama.cpp 到 $LLAMA_DIR"
    if (-not (Test-Path $LLAMA_DIR)) {
        git clone https://github.com/ggerganov/llama.cpp.git $LLAMA_DIR
    } else {
        Push-Location $LLAMA_DIR; git pull --ff-only; Pop-Location
    }
    Write-Step "配置并编译（CUDA 版，需 NVIDIA 驱动 + CUDA Toolkit）"
    Push-Location $LLAMA_DIR
    cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release --target llama-server -j
    Pop-Location
    $serverPath = Find-LlamaServer
    if (-not $serverPath) { throw "编译产物未找到：$BUILD_DIR\$SERVER" }
    Write-Host "  编译完成: $serverPath" -ForegroundColor Green
}

Write-Step "检查模型下载工具 (modelscope，可选)"
if (Get-Command python -ErrorAction SilentlyContinue) {
    python -m pip show modelscope | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  未安装 modelscope，可运行:  python -m pip install modelscope"
    }
}

Write-Step "下一步"
Write-Host @"

1) 把 $serverPath 所在目录加入 PATH，或在 local_model_panel.py 的
   MODELS 各项里增加 "llama_server": "<完整路径>\llama-server.exe"。
2) 把模型（GGUF 及 mmproj）放到对应 models_dir（默认 C:\Users\<你>\models\<模型>\）。
3) 运行面板：
   python local_model_panel.py
   —— Windows 上以【后台进程】方式启停模型，不再依赖 systemd。

关于 --split-mode layer --n-gpu-layers 99：单卡时删除这两个参数；
多卡 NVLink 时保留。DFlash 投机解码仅 27B 使用（--spec-type draft-dflash）。
"@ -ForegroundColor Gray
