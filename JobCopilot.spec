"""PyInstaller build specification for the Job Copilot desktop executable.

This file describes the frozen app entry point, bundled data, and hidden
imports needed to ship the Windows build.
"""

# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

chromadb_datas, chromadb_binaries, chromadb_hiddenimports = collect_all('chromadb')
genai_datas, genai_binaries, genai_hiddenimports = collect_all('google.genai')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[*chromadb_binaries, *genai_binaries],
    datas=[
        *chromadb_datas,
        *genai_datas,
        ('data', 'data'),
        ('.env', '.'),
    ],
    hiddenimports=[
        *chromadb_hiddenimports,
        *genai_hiddenimports,
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'docx',
        'dotenv',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JobCopilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='JobCopilot',
)