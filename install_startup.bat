@echo off
chcp 65001 >nul
title QuantNova 开机自启动安装

echo ========================================
echo   QuantNova 开机自启动安装
echo ========================================
echo.

cd /d "%~dp0"

echo 正在创建开机自启动任务...
echo.

schtasks /create /tn "QuantNova" /tr "\"%~dp0service.bat\" start" /sc onlogon /rl highest /f

if errorlevel 1 (
    echo.
    echo 创建失败！请以管理员身份运行此脚本。
    echo.
    echo 手动设置方法：
    echo 1. 按 Win+R，输入 taskschd.msc
    echo 2. 创建基本任务
    echo 3. 名称: QuantNova
    echo 4. 触发器: 当用户登录时
    echo 5. 操作: 启动程序
    echo 6. 程序: %~dp0service.bat
    echo 7. 参数: start
) else (
    echo.
    echo 开机自启动任务创建成功！
    echo 任务名称: QuantNova
    echo.
    echo 管理方法：
    echo 1. 查看: schtasks /query /tn "QuantNova"
    echo 2. 删除: schtasks /delete /tn "QuantNova" /f
    echo 3. 手动运行: schtasks /run /tn "QuantNova"
)

echo.
pause
