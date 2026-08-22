"""Smoke test ban exe: khoi chay voi LOCALAPPDATA sach, doi 20s, kiem tra
tien trinh con song + log duoc ghi + khong co traceback, roi tat."""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "AutoLabelStudioAI" / "AutoLabelStudioAI.exe"
if not EXE.exists():
    sys.exit(f"Khong thay {EXE}")

sandbox = Path(tempfile.mkdtemp(prefix="als_exe_"))
env = dict(os.environ, LOCALAPPDATA=str(sandbox))
print("Chay:", EXE)
proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent), env=env)
time.sleep(20)
alive = proc.poll() is None
print("Tien trinh con song sau 20s:", alive, "| exit code:", proc.poll())

logs = (
    list((sandbox / "AutoLabelStudioAI" / "logs").glob("*.log"))
    if (sandbox / "AutoLabelStudioAI").exists()
    else []
)
print("File log:", [p.name for p in logs])
ok_log = False
for lp in logs:
    txt = lp.read_text(encoding="utf-8", errors="ignore")
    tail = txt[-1500:]
    print("--- tail log ---\n" + tail)
    ok_log = "Traceback" not in txt and "ERROR" not in txt.upper().replace("NO ERROR", "")
if alive:
    proc.kill()
settings = sandbox / "AutoLabelStudioAI" / "settings.json"
print("settings.json tao ra:", settings.exists())
ok = alive and bool(logs) and ok_log
print("\nSMOKE EXE:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
