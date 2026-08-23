# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

datas = [
    ('app/i18n/*.json', 'app/i18n'),
    ('app.ico', '.'),
]
datas += collect_data_files('ultralytics')
datas += collect_data_files('shapely')

hiddenimports = [
    'app',
    'app.config',
    'app.constants',
    'app.controllers',
    'app.controllers.app_controller',
    'app.core',
    'app.core.exporters',
    'app.core.frame_extractor',
    'app.core.image_quality',
    'app.core.importers',
    'app.core.inference',
    'app.core.trainer',
    'app.i18n',
    'app.models',
    'app.models.database',
    'app.models.entities',
    'app.models.repository',
    'app.plugins',
    'app.plugins.base',
    'app.plugins.builtin',
    'app.theme',
    'app.theme.icons',
    'app.theme.style',
    'app.utils',
    'app.utils.logger',
    'app.utils.paths',
    'app.views',
    'app.views.main_window',
    'app.views.sidebar',
    'app.views.pages',
    'app.views.pages.autolabel_page',
    'app.views.pages.base_page',
    'app.views.pages.dashboard_page',
    'app.views.pages.dataset_page',
    'app.views.pages.editor_page',
    'app.views.pages.extract_page',
    'app.views.pages.import_page',
    'app.views.pages.settings_page',
    'app.views.pages.stats_page',
    'app.views.pages.train_page',
    'app.views.widgets',
    'app.views.widgets.canvas',
    'app.views.widgets.charts',
    'app.views.widgets.common',
    'app.views.widgets.image_list',
    'app.workers',
    'app.workers.autolabel_worker',
    'app.workers.base',
    'app.workers.export_worker',
    'app.workers.extract_worker',
    'app.workers.import_worker',
    'app.workers.train_worker',
    'ultralytics',
    'shapely',
    'PySide6.QtSvg',
]
hiddenimports += collect_submodules('ultralytics')
hiddenimports += collect_submodules('shapely')
hiddenimports += collect_submodules('app')

binaries = []
binaries += collect_dynamic_libs('shapely')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- Runtime DLL MSVC: chi giu MOT ban o thu muc goc, uu tien ban cua torch ---
# torch (14.50) moi hon PySide6/shiboken6 (14.44). Windows nap DLL o goc
# _internal truoc; neu ban cu "thang" o goc (thu tu gom cua PyInstaller khong
# xac dinh giua cac lan build) -> torch_python.dll access violation khi
# import torch (crash im lang luc khoi dong). Ep ban moi nhat o goc va bo
# cac ban trung ten trong thu muc con de ket qua build luon dung.
_RUNTIME = {
    "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll", "vcruntime140.dll", "vcruntime140_1.dll",
    "vcomp140.dll", "concrt140.dll",
}


def _dedupe_runtime(binaries):
    import os

    best = {}  # ten thuong -> (uu_tien, (dest, src, kind))
    keep = []
    for dest, src, kind in binaries:
        name = os.path.basename(dest).lower()
        if name not in _RUNTIME:
            keep.append((dest, src, kind))
            continue
        prio = 2 if "torch" in src.lower().replace("\\", "/") else 1
        cur = best.get(name)
        if cur is None or prio > cur[0]:
            best[name] = (prio, (name, src, kind))  # dest = ten o goc
    for _, entry in best.values():
        keep.append(entry)
    return keep


a.binaries = _dedupe_runtime(a.binaries)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoLabelStudioAI',
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
    icon='app.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutoLabelStudioAI',
)
