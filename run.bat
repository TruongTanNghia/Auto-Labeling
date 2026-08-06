@echo off
REM AutoLabel Studio AI - khoi chay ung dung
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python trong PATH.
    echo Cai Python 3.10+ tai https://www.python.org/downloads/
    pause
    exit /b 1
)

python -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo Chua co PySide6. Dang cai dat cac goi phu thuoc...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [LOI] Cai dat that bai.
        pause
        exit /b 1
    )
)

python main.py %*
if errorlevel 1 pause
endlocal
