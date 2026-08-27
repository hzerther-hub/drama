# 本地编程助手 · 本地模型管理面板

gpulocal 带**主界面**（`main_window.py`）：一屏总览所有本地模型服务的运行状态 / 端口 /
健康检查与 GPU、CPU、内存、磁盘资源摘要，支持快捷 启动 / 停止 / 重启（串行切换）。
「模型管理面板」（GPU/系统/硬件详情、下载、加载日志）从主界面以**模态子窗**打开。

独立 tkinter 程序，**串行管理**本地模型（Linux 用 systemd 用户服务，Windows/macOS
用后台进程守护），并实时显示多卡 GPU / 系统 / 硬件状态。跨平台：**Linux / Windows / macOS**。
界面**中英文双语（默认英文）**，工具栏「EN/中文」按钮切换，语言持久化在
`~/.gpulocal/config.json`（`"language": "en"`）。

> 平台差异：`service_status` / `svc_start` / `svc_stop` / `svc_restart` 为跨平台入口。
> Linux 且有 systemctl → `systemctl --user`（需 `services/*.service` + linger）；
> Windows / macOS / 无 systemd 的 Linux → 后台 `llama-server` 进程（状态文件记录
> pid + 端口，运行状态目录 `~/.gpulocal/run/`），无需 systemd。
> qwen-coder 的本地模型桥接同样走这一套。

## 一键装机（三平台）

| 平台 | 脚本 | 说明 |
|---|---|---|
| Ubuntu/Linux（NVIDIA） | `bash setup.sh` | 工具链 + CUDA → 编译 llama.cpp-dflash2 → systemd 用户服务 → 下载模型 |
| Windows | `powershell -File setup.ps1` | 检查/编译 llama-server.exe（CUDA）→ 提示 PATH 与模型目录 |
| macOS（Metal） | `bash setup-mac.sh` | brew 装 llama.cpp（llama-server 进 PATH）→ 检查 Tkinter → 下载模型 |

三个脚本都支持 `download` 子命令只下模型（`bash setup.sh download` /
`bash setup-mac.sh download`）。macOS 注意：DFlash2 投机解码面向 CUDA（PR#27342），
Metal 下不使用 drafter，27B 按普通解码运行。

## 模型清单
| 模型 | 量化/加速 | 服务 | 端口 | 视觉 | 模型来源（ModelScope） |
|---|---|---|---|---|---|
| Qwen3.8-27B (DFlash2 加速) | Q8_0 + DFlash2 投机解码 | `qwen38-27b-q8.service` | 8097 | `mmproj-BF16.gguf` | `unsloth/Qwen3.8-27B-GGUF` + `z-lab/Qwen3.8-27B-DFlash2` |
| Qwen3-VL-32B (Q6_K) | Q6_K | `qwen3-vl-32b.service` | 8098 | `mmproj-F16.gguf` | `unsloth/Qwen3-VL-32B-Instruct-GGUF` |
| Ornith-1.5-35B-A3B (Q6_K) | Q6_K（双卡，尽量大） | `ornith-1.5-35b.service` | 8099 | `mmproj-Ornith-1.5-35B-BF16.gguf` | `ornith-ai/Ornith-1.5-35B-A3B-GGUF` |

GLM-4.6V-Flash / Qwen2.5-Coder-32B 已 disable，**不在此列**。一次只跑一个模型（串行，44 GiB 显存放不下多个）。

> 注：Ornith-1.5-35B-A3B 为 35B MoE（仅 ~3B 激活），Q6_K 约 26 GiB，用 `--split-mode layer --n-gpu-layers 99` 放两张卡。

## 与 qwen-coder 的关系（内嵌子模块）

本目录是 qwen-coder 的**内嵌本地模型面板**，功能取自独立项目 gpulocal 仓库
（`~/build/gpulocal/`，gitee `local_model_gpu`）。qwen-coder 通过
`localmodels.py` 读取这里的 `MODELS` 注册表、复用 `svc_*` 启停；「打开本地模型
面板」用 `ui.py:_open_gpu_panel` 直接 `ModelPanel(master=self.root)` 在主窗口内
以子窗形式载入（不再是独立进程弹窗）。

### ⬆️ 从独立仓库同步（独立项目更新后）

独立仓库是**功能源头**，把新面板同步进来分两步：

```bash
# 1) 复制独立仓库的代码文件到本目录
cp ~/build/gpulocal/local_model_panel.py gpulocal/local_model_panel.py
cp ~/build/gpulocal/main_window.py gpulocal/main_window.py
cp ~/build/gpulocal/setup.sh gpulocal/setup.sh
cp ~/build/gpulocal/setup.ps1 gpulocal/setup.ps1
cp ~/build/gpulocal/setup-mac.sh gpulocal/setup-mac.sh
cp ~/build/gpulocal/README.md gpulocal/README.md
cp -r ~/build/gpulocal/services/. gpulocal/services/
```

```bash
# 2) 重新应用「可挂载」改造（独立仓库版是继承 tk.Tk，不能直接嵌入主窗口）。
#    对 local_model_panel.py 做以下改动：
#      a. class ModelPanel(tk.Tk):        →  class ModelPanel:
#      b. def __init__(self):             →  def __init__(self, master=None):
#           super().__init__()            →  self.win = tk.Toplevel(master) if master is not None else tk.Tk()
#      c. 类体内所有 Tk/Misc 方法接收者 self → self.win
#         （title/geometry/minsize/after/configure/…），
#         以及所有 (tk|ttk).\w+(self, …) 容器构造的第一个参数 self → self.win
#      d. ttk.Style(self) → ttk.Style(self.win)
#      e. main() 里 app.mainloop() → app.win.mainloop()
```

覆盖后运行验证：`python3 -m py_compile gpulocal/local_model_panel.py`
且 `python3 gpulocal/local_model_panel.py`（独立）+ 主应用内打开面板均正常。

## 文件
- `main_window.py` —— gpulocal 主界面（模型服务总览 + 资源摘要 + 快捷启停 + 模态打开管理面板）
- `local_model_panel.py` —— tkinter 模型管理面板（启动/停止/重启/刷新/下载 + 状态详情），独立运行时其 `main()` 进入主界面
- `services/qwen38-27b-q8.service` —— 27B 用户服务单元模板（Linux，systemd）
- `services/qwen3-vl-32b.service` —— VL-32B 用户服务单元模板
- `services/ornith-1.5-35b.service` —— Ornith-1.5-35B 用户服务单元模板
- `setup.ps1` —— Windows 准备脚本（编译 llama-server.exe / 提示下载模型）
- `setup.sh` —— Ubuntu/Linux 一键安装（工具链/CUDA/llama.cpp 编译/服务/下载模型）
- `setup-mac.sh` —— macOS 一键准备（brew 装 llama.cpp / 检查 Tkinter / 下载模型）

## 安装
```bash
# Ubuntu/Linux（NVIDIA，需 sudo）：
bash setup.sh            # 全流程：装工具链+编译+服务+下载
bash setup.sh download   # 只下载模型

# Windows（PowerShell）：
powershell -File setup.ps1

# macOS（需先装 Homebrew）：
bash setup-mac.sh            # 全流程：装 llama.cpp+下载模型
bash setup-mac.sh download   # 只下载模型
bash setup-mac.sh toolchain  # 只装工具链
```

## 运行
```bash
# Linux 如缺 tkinter/pip：sudo apt install -y python3-tk python3-pip
# macOS 如缺 tkinter：brew install python-tk@3.13（按 python 版本调整）
python3 main_window.py          # 主界面（推荐入口）
python3 local_model_panel.py    # 兼容入口：同样进入主界面
```

主界面：选中模型行 → 启动 / 停止 / 重启（自动先停其它模型）；点「模型管理面板」
以模态子窗打开完整面板（GPU/系统/硬件详情、加载日志、下载模型）。「下载模型」
从 ModelScope 拉取所选模型的 GGUF。

## 双卡 NVLink 关键启动参数（已写入 service 单元）
- `--split-mode layer --n-gpu-layers 99` 按层拆到双卡
- `--flash-attn on --cache-type-k/v q8_0` 省显存
- 27B 额外：`--spec-type draft-dflash --spec-draft-model <drafter> --spec-draft-ngl 99 --spec-draft-n-max 5`

## DFlash2 drafter 转换（GGUF）
DFlash2 drafter 源是 safetensors（`z-lab/Qwen3.8-27B-DFlash2`），需转成 GGUF：
```bash
pip install torch            # convert_hf_to_gguf.py 依赖
python3 ~/llama.cpp-dflash2/convert_hf_to_gguf.py \
    ~/models/Qwen3.8-27B-GGUF/drafter-src \
    --target-model-dir ~/models/Qwen3.8-27B-HF \      # 主模型 HF 元数据(需下载 Qwen/Qwen3.8-27B)
    --outtype q4_k_m \
    --outfile ~/models/Qwen3.8-27B-GGUF/Qwen3.8-27B-DFlash2-Q4_K_M.gguf
```
