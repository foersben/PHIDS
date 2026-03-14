# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PHIDS release bundles."""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve().parent
src_root = project_root / "src"

hiddenimports = sorted(set(collect_submodules("uvicorn") + collect_submodules("websockets")))

datas = [
    (str(src_root / "phids" / "api" / "templates"), "phids/api/templates"),
]

if (project_root / "examples").exists():
    datas.append((str(project_root / "examples"), "examples"))

if (project_root / "README.md").exists():
    datas.append((str(project_root / "README.md"), "."))


a = Analysis(
    [str(src_root / "phids" / "__main__.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.scripts,
    [],
    exclude_binaries=True,
    name="phids",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="phids",
)
