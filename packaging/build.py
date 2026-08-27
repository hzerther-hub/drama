#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2 打包管线：一条命令出某个产品的当前平台安装包。

用法：
    python packaging/build.py                 # 默认产品 devtool_local
    python packaging/build.py devtool         # 纯云端版
    python packaging/build.py quant --clean   # 清掉 build/ 缓存重打

产物：dist/<exe_name>-<platform>/ （Windows .exe / macOS .app / Linux 可执行文件）
CI：.github/workflows/test.yml 的 package 任务对三平台各跑一次。

产品感知：读 products/<name>/profile.json——
  · gpulocal 功能关 → 不打 gpulocal/ 数据目录（包更小）
  · exe_name 决定产物名
注意：本脚本只生成 spec 并调 PyInstaller；图标/签名属 E3（品牌体系）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import products  # noqa: E402

# AI 重栈不打进包（语音识别走系统/运行时安装；包体积从 ~3.9GB 回到 ~150MB）
_EXCLUDES = [
    "torch", "torchvision", "torchaudio", "torchao", "torchcodec",
    "torch_c_dlpack_ext", "triton", "tokenspeed_triton",
    "faster_whisper", "ctranslate2", "onnx", "onnxruntime",
    "rapidocr_onnxruntime", "cuda_python",
]

_SPEC = """# -*- mode: python ; coding: utf-8 -*-
# 本文件由 packaging/build.py 生成，请勿手改（改动请改 build.py）
import os

a = Analysis(
    [{entry_script!r}],
    pathex=[{root!r}],
    binaries=[],
    datas={datas!r},
    hiddenimports={hiddenimports!r},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={excludes!r},
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name={exe_name!r},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""


def _platform_tag() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def build(product_name: str, clean: bool = False) -> str:
    prof = products.load_profile(product_name)
    exe_name = prof.exe_name or "LocalAIStudio"

    # ---- 数据文件：按产品功能开关决定（源路径用绝对路径，spec 在子目录）----
    def _abs(src: str) -> str:
        return src if os.path.isabs(src) else os.path.join(ROOT, src)

    datas = [(os.path.join(ROOT, "fonts"), "fonts")]
    # 所有产品的 profile.json 打进包（运行时 import products 要读）
    for name in products.list_products():
        datas.append((os.path.join(ROOT, "products", name, "profile.json"),
                      os.path.join("products", name)))
    # tkinterdnd2 的 tkdnd 平台库是 Tcl 数据文件，不会被自动收集
    hidden = []
    try:
        import tkinterdnd2 as _tkdnd2_pkg
        datas.append((os.path.join(os.path.dirname(_tkdnd2_pkg.__file__), "tkdnd"),
                      "tkinterdnd2/tkdnd"))
        hidden.append("tkinterdnd2")
    except ImportError:
        print("[build] 提示：未装 tkinterdnd2，拖放功能降级（打包继续）")
    if prof.feature("gpulocal"):
        datas.append((os.path.join(ROOT, "gpulocal"), "gpulocal"))  # 本地模型面板/服务/装机脚本
    datas = [(_abs(s), d) for s, d in datas]

    # ---- 生成 spec ----
    spec_path = os.path.join(ROOT, "packaging", f"{exe_name}.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(_SPEC.format(entry_script=os.path.join(ROOT, "main.py"),
                             root=ROOT, datas=datas, hiddenimports=hidden,
                             excludes=_EXCLUDES, exe_name=exe_name))
    print(f"[build] spec: {spec_path}")

    if clean:
        shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)

    # ---- 调 PyInstaller ----
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm",
           "--distpath", os.path.join(ROOT, "dist"),
           "--workpath", os.path.join(ROOT, "build"),
           spec_path]
    print("[build] 运行:", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)

    # ---- 归拢产物：dist/<exe_name>-<platform>/ ----
    out_dir = os.path.join(ROOT, "dist", f"{exe_name}-{_platform_tag()}")
    os.makedirs(out_dir, exist_ok=True)
    moved = []
    for fn in os.listdir(os.path.join(ROOT, "dist")):
        if fn.startswith(exe_name) and not fn.endswith(".spec") and \
                os.path.isfile(os.path.join(ROOT, "dist", fn)):
            shutil.move(os.path.join(ROOT, "dist", fn),
                        os.path.join(out_dir, fn))
            moved.append(fn)
    print(f"[build] 完成 → {out_dir}")
    for m in moved:
        print("   ", m)
    return out_dir


def main():
    ap = argparse.ArgumentParser(description="按产品打包（PyInstaller）")
    ap.add_argument("product", nargs="?", default=products.DEFAULT_PRODUCT,
                    choices=products.list_products())
    ap.add_argument("--clean", action="store_true", help="清 build/ 缓存重打")
    args = ap.parse_args()
    build(args.product, clean=args.clean)


if __name__ == "__main__":
    main()
