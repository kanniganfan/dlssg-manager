@echo off
rem ============================================================
rem  DLSSG Manager - Windows 一键构建脚本
rem  产物: dist\1.9.3\DLSSG Manager.exe + payload\ 便携发行包
rem ============================================================
setlocal
cd /d "%~dp0.."

set "VENV=%CD%\.venv"
set "PY=%VENV%\Scripts\python.exe"
set "BUILD_DIR=%CD%\build\1.9.3"
set "DIST_DIR=%CD%\dist\1.9.3"

if exist "%BUILD_DIR%" (
    echo [错误] 构建目录已存在，为保护其中内容而停止: %BUILD_DIR%
    goto :err
)
if exist "%DIST_DIR%" (
    echo [错误] 输出目录已存在，为保护其中内容而停止: %DIST_DIR%
    goto :err
)
mkdir "%BUILD_DIR%\work" || goto :err
mkdir "%BUILD_DIR%\spec" || goto :err
mkdir "%DIST_DIR%" || goto :err

if not exist "%PY%" (
    echo [1/4] 创建隔离虚拟环境...
    python -m venv "%VENV%" || goto :err
) else (
    echo [1/4] 虚拟环境已存在，跳过
)

echo [2/4] 安装依赖 ^(PySide6 + PyInstaller^)...
"%PY%" -m pip install --quiet --upgrade pip || goto :err
"%PY%" -m pip install --quiet PySide6 pyinstaller || goto :err

echo [3/4] 源码自检...
"%PY%" -m py_compile src\core.py src\ui.py src\i18n.py src\main.py || goto :err

echo [4/4] PyInstaller 打包...
"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "DLSSG Manager" ^
    --icon "%CD%\assets\icon.ico" ^
    --add-data "%CD%\lang;lang" ^
    --distpath "%DIST_DIR%" --workpath "%BUILD_DIR%\work" --specpath "%BUILD_DIR%\spec" src\main.py || goto :err

echo.
echo ============================================================
echo   构建完成: %DIST_DIR%\DLSSG Manager.exe
echo   发布包需包含同级 payload\ 文件夹
echo ============================================================
exit /b 0

:err
echo.
echo [错误] 构建失败，请检查上方输出。
exit /b 1
