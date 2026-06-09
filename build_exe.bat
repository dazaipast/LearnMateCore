@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Сборка LearnMate Core...
echo.

if not exist "venv\Scripts\pyinstaller.exe" (
    echo Установка PyInstaller...
    venv\Scripts\python.exe -m pip install pyinstaller
)

venv\Scripts\pyinstaller.exe LearnMateCore.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo Ошибка сборки.
    pause
    exit /b 1
)

echo.
echo Готово: dist\LearnMate Core.exe
echo Скопируйте этот файл пользователям — Python не нужен.
echo Рядом с .exe создадутся база данных и папка course_materials.
echo.
pause
