# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
    ('style.qss', '.'),
    ('fasteners_bolt_script.py', '.'),
    ('gears_script.py', '.'),
    ('text_model_runner.py', '.'),   # still fine to keep
    ('cad_primitives.py', '.'),      # NEW: make cad_primitives visible to freecadcmd
    ],
    hiddenimports=[],
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
    name='AI_CAD_Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AI_CAD_Assistant',
)
