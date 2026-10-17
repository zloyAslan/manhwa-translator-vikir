# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('D:/всі проекти/перекладач/app_icon.ico', '.'), ('D:/всі проекти/перекладач/.venv/Lib/site-packages/rapidocr_onnxruntime', 'rapidocr_onnxruntime')]
binaries = []
hiddenimports = ['rapidocr_onnxruntime', 'onnxruntime', 'PIL', 'PyQt6.QtMultimedia']
tmp_ret = collect_all('rapidocr_onnxruntime')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:/всі проекти/перекладач/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['telethon', 'fitz', 'pymupdf', 'torch'],
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
    name='m_translate',
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
    icon=['D:/всі проекти/перекладач/app_icon.ico'],
)
