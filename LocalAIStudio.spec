# -*- mode: python ; coding: utf-8 -*-


# tkinterdnd2 的 tkdnd 平台库（.so/.dll/.dylib）是 Tcl 数据文件，
# 不会被自动收集；整个包带进 tkdnd/ 才能拖放
import os
import tkinterdnd2 as _tkdnd2_pkg
_tkdnd2_dir = os.path.dirname(_tkdnd2_pkg.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('fonts', 'fonts'),
            (os.path.join(_tkdnd2_dir, 'tkdnd'), 'tkinterdnd2/tkdnd'),
            ('gpulocal', 'gpulocal')],
    hiddenimports=['tkinterdnd2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # AI 重栈不打进包（语音识别走系统/运行时安装，包体积从 3.9GB 回到 ~150MB）
        'torch', 'torchvision', 'torchaudio', 'torchao', 'torchcodec',
        'torch_c_dlpack_ext', 'triton', 'tokenspeed_triton',
        'faster_whisper', 'ctranslate2', 'onnx', 'onnxruntime',
        'rapidocr_onnxruntime', 'cuda_python',
    ],
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
    name='LocalAIStudio',
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
