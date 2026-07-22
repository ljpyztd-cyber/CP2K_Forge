# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

if "__file__" in globals():
    spec_path = Path(__file__).resolve()
else:
    cwd = Path.cwd()
    spec_path = cwd / "CP2K_FORGE_EXE" / "CP2K_FORGE_EXE.spec"
    if not spec_path.is_file():
        spec_path = cwd / "CP2K_FORGE_EXE.spec"
exe_root = spec_path.parent

a = Analysis(
    [str(exe_root / "run.py")],
    pathex=[str(exe_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt5.QtOpenGL",
        "cp2k_forge_backend",
        "cp2k_forge_backend.generation",
        "cp2k_forge_backend.multiwfn",
        "cp2k_forge_backend.patcher",
        "cp2k_forge_backend.rules",
        "cp2k_forge_backend.structure_table",
        "cp2k_forge_backend.local_slurm",
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
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CP2K_FORGE",
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
