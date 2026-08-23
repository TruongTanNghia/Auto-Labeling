"""Kiem tra ban build PyInstaller truoc khi dong goi.

Dam bao cac DLL runtime MSVC o thu muc goc _internal la ban MOI NHAT trong
toan bo bundle (torch can 14.50; ban 14.44 cua PySide6 ma "thang" o goc se
lam torch_python.dll crash im lang luc khoi dong — loi da gap o build #2).

Chay:  python packaging/check_bundle.py   (exit 0 = OK)
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERNAL = ROOT / "dist" / "AutoLabelStudioAI" / "_internal"
RUNTIME = {
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "vcomp140.dll",
    "concrt140.dll",
}


def file_version(path: Path) -> tuple[int, int, int, int]:
    """Doc FileVersion cua DLL bang WinAPI (khong can pywin32)."""
    ver = ctypes.windll.version
    size = ver.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return (0, 0, 0, 0)
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(str(path), 0, size, buf):
        return (0, 0, 0, 0)
    ptr = ctypes.c_void_p()
    length = wintypes.UINT()
    if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)):
        return (0, 0, 0, 0)

    class VS_FIXEDFILEINFO(ctypes.Structure):
        _fields_ = [
            ("dwSignature", wintypes.DWORD),
            ("dwStrucVersion", wintypes.DWORD),
            ("dwFileVersionMS", wintypes.DWORD),
            ("dwFileVersionLS", wintypes.DWORD),
        ]

    info = ctypes.cast(ptr, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
    ms, ls = info.dwFileVersionMS, info.dwFileVersionLS
    return (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF)


def main() -> int:
    if not INTERNAL.exists():
        print(f"Khong thay {INTERNAL}")
        return 2
    problems = 0
    for name in sorted(RUNTIME):
        copies = [p for p in INTERNAL.rglob("*") if p.name.lower() == name]
        if not copies:
            continue
        root = next((p for p in copies if p.parent == INTERNAL), None)
        newest = max(copies, key=file_version)
        root_v = file_version(root) if root else None
        newest_v = file_version(newest)
        sub = [p for p in copies if p.parent != INTERNAL]
        versions = {file_version(p) for p in copies}
        status = "OK "
        if root is not None and root_v < newest_v:
            status = "LOI"  # ban cu "thang" o goc -> torch se crash
            problems += 1
        elif root is None and len(versions) > 1:
            status = "LOI"  # nhieu phien ban, khong ban nao o goc -> khong xac dinh
            problems += 1
        elif sub:
            status = "WARN"  # con ban trung ten o thu muc con (khong nguy hiem)
        print(
            f"[{status}] {name:22} goc={'.'.join(map(str, root_v)) if root_v else '-':16} "
            f"moi_nhat={'.'.join(map(str, newest_v))}  ban_sao={len(copies)}"
        )
    exe = INTERNAL.parent / "AutoLabelStudioAI.exe"
    print("exe:", "co" if exe.exists() else "THIEU")
    if not exe.exists():
        problems += 1
    print("KET QUA:", "PASS" if problems == 0 else f"FAIL ({problems} van de)")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
