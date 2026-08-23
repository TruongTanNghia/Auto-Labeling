"""Dong goi ban phan phoi cho doi test sau khi PyInstaller build xong.

Chay:  python packaging/make_package.py
Ket qua: dist/AutoLabelStudioAI-v<ver>-windows-x64.zip
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.constants import APP_VERSION  # noqa: E402

DIST = ROOT / "dist" / "AutoLabelStudioAI"
if not (DIST / "AutoLabelStudioAI.exe").exists():
    sys.exit("Chua co dist/AutoLabelStudioAI/AutoLabelStudioAI.exe - hay build PyInstaller truoc.")

# 0. Kiem tra bundle (DLL runtime MSVC o goc phai la ban moi nhat) — tu choi
#    dong goi neu lech, vi se crash im lang khi khoi dong tren may nguoi dung.
import subprocess  # noqa: E402

if subprocess.call([sys.executable, str(ROOT / "packaging" / "check_bundle.py")]) != 0:
    sys.exit("check_bundle FAIL - khong dong goi. Hay build lai bang AutoLabelStudioAI.spec.")

# 1. Tai lieu + huong dan vao ban goi
docs_out = DIST / "docs"
docs_out.mkdir(exist_ok=True)
for name in (
    "DAC-TA-QA.html",
    "TAI-LIEU-KIEM-THU.md",
    "TAI-LIEU-NGHIEP-VU.md",
    "TAI-LIEU-CHUC-NANG-CHI-TIET.md",
    "TAI-LIEU-VAN-HANH.md",
    "TAI-LIEU-HE-THONG.md",
):
    src = ROOT / "docs" / name
    if src.exists():
        shutil.copy2(src, docs_out / name)
shutil.copy2(ROOT / "packaging" / "HUONG-DAN-CHAY.txt", DIST / "HUONG-DAN-CHAY.txt")
shutil.copy2(ROOT / "README.md", DIST / "README.md")

# 2. Nen zip (bo qua cache/log neu co)
zip_path = ROOT / "dist" / f"AutoLabelStudioAI-v{APP_VERSION}-windows-x64.zip"
if zip_path.exists():
    zip_path.unlink()
n = 0
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for p in DIST.rglob("*"):
        if p.is_dir() or "__pycache__" in p.parts:
            continue
        zf.write(p, Path("AutoLabelStudioAI") / p.relative_to(DIST))
        n += 1
size_mb = zip_path.stat().st_size / 1024 / 1024
print(f"OK: {zip_path}  ({n} file, {size_mb:.0f} MB)")
