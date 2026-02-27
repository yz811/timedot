# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import PyQt6

_system_icuuc = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'System32', 'icuuc.dll')

binaries = collect_dynamic_libs('PyQt6')
datas = collect_data_files(
    'PyQt6',
    includes=[
        'Qt6/plugins/**/*',
        'Qt6/translations/**/*',
        'Qt6/resources/**/*',
    ],
)

a = Analysis(
    ['timedot_nnlv.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=['pkgutil'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_timedot_qt.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Conda's icuuc.dll has versioned exports that break Qt6Core.dll import.
# Force a compatible ICU DLL that exports unsuffixed symbols.
a.binaries = [b for b in a.binaries if not (len(b) >= 1 and str(b[0]).lower() == 'icuuc.dll')]
if os.path.exists(_system_icuuc):
    a.binaries += [('icuuc.dll', _system_icuuc, 'BINARY')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    [],
    name='TimeDots',
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['TimeDots.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TimeDots',
)
