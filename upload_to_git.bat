@echo off
chcp 65001 >nul
echo ==========================================
echo       Git 仓库初始化与上传工具
echo ==========================================
echo.

:: 1. 检查 Git 是否安装
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Git！
    echo 请先下载并安装 Git: https://git-scm.com/downloads
    echo 安装完成后，请重新运行此脚本。
    pause
    exit /b
)

echo [1/5] 检测到 Git，准备初始化仓库...
echo.

:: 2. 初始化仓库
if not exist ".git" (
    git init
    echo 仓库初始化完成。
) else (
    echo 仓库已存在，跳过初始化。
)
echo.

:: 3. 添加文件并提交
echo [2/5] 添加文件到暂存区...
git add .
echo.

echo [3/5] 提交更改...
git commit -m "Initial commit: 项目初始化 (由 Trae 助手生成)"
echo.

:: 4. 关联远程仓库
echo [4/5] 关联远程仓库
echo https://github.com/wthdyfg/PC_control_wifi_595_apt0316_gui (例如 https://github.com/wthdyfg/PC_control_wifi_595_apt0316_gui.git)
echo 如果只想本地管理，直接按回车跳过。
set /p REMOTE_URL="远程仓库地址: "

if "%REMOTE_URL%"=="" (
    echo.
    echo 已跳过远程关联。您的项目现在已在本地进行版本管理。
    goto :END
)

:: 检查是否已经有关联
git remote get-url origin >nul 2>nul
if %errorlevel% equ 0 (
    echo 检测到已存在 origin 关联，正在更新...
    git remote set-url origin %REMOTE_URL%
) else (
    git remote add origin %REMOTE_URL%
)

:: 5. 推送代码
echo.
echo [5/5] 正在推送到远程仓库...
git branch -M main
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [警告] 推送失败。可能是因为：
    echo 1. 仓库非空（请先手动 pull）
    echo 2. 权限不足（请检查账号密码或 SSH Key）
    echo 3. 网络问题
) else (
    echo.
    echo [成功] 项目已成功上传！
)

:END
echo.
echo ==========================================
echo               操作结束
echo ==========================================
pause
