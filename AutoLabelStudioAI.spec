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
    'app.plugins.sam2_plugin',
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
