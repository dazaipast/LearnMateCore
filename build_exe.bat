@echo off
cd /d "%~dp0"

echo Building LearnMate Core...
echo.

if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv not found. Create it first:
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "venv\Scripts\pyinstaller.exe" (
    echo Installing PyInstaller...
    venv\Scripts\python.exe -m pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: failed to install PyInstaller.
        pause
        exit /b 1
    )
)

venv\Scripts\pyinstaller.exe LearnMateCore.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    pause
    exit /b 1
)

echo.
echo DONE: dist\LearnMate Core.exe
echo Copy this file to users - Python is not required.
echo Database and course_materials folder will appear next to the exe on first run.
echo.
pause
