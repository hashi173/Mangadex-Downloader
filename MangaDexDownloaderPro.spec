# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Get project root
project_root = Path('. ').resolve()
source_dir = project_root / 'source'

a = Analysis(
    ['source/main.py'],
    pathex=[str(source_dir)],  # Add source to path
    binaries=[],
    datas=[],
    hiddenimports=[
        'gui',
        'gui.main_window',
        'api',
        'api. mangadex_api',
        'downloader',
        'downloader.turbo_downloader',
        'PIL',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.  ImageTk',
        'reportlab',
        'reportlab. pdfgen',
        'reportlab.pdfgen.canvas',
        'reportlab.lib.  pagesizes',
        'tkinter',
        'tkinter. ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'requests',
        'urllib3',
        'threading',
        'zipfile',
        'hashlib',
        'io',
        're',
        'time',
        'os',
        'sys',
        'concurrent',
        'concurrent.futures',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a. scripts,
    a.binaries,
    a. datas,
    [],
    name='MangaDexDownloaderPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',  # Optional
)