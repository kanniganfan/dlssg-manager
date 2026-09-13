@echo off
rem ============================================================
rem  DLSSG Manager - Windows 一键构建脚本
rem  产物: dist\DLSSG Manager.exe (单文件, 需将 payload\ 放同级)
rem ============================================================
setlocal
cd /d "%~dp0.."

set "VENV=%CD%\.venv"
set "PY=%VENV%\Scripts\python.exe"

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
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "DLSSG Manager" ^
    --icon "%CD%\assets\icon.ico" ^
    --add-data "%CD%\lang;lang" ^
    --distpath dist --workpath build --specpath build src\main.py || goto :err

echo.
echo ============================================================
echo   构建完成: dist\DLSSG Manager.exe
echo   运行前请将上游 payload\ 文件夹放在 exe 同级目录
echo   ^(见 README「致谢与出处」, 或直接下载 Release 附件^)
echo ============================================================
exit /b 0

:err
echo.
echo [错误] 构建失败，请检查上方输出。
exit /b 1
