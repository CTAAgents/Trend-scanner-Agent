@echo off
chcp 65001 >nul
title QuantNova 服务管理器

echo ========================================
echo   QuantNova 服务管理器
echo ========================================
echo.

cd /d "%~dp0"

:menu
echo 请选择操作:
echo   [1] 启动后台服务
echo   [2] 停止后台服务
echo   [3] 查看服务状态
echo   [4] 查看日志
echo   [5] 退出
echo.
set /p choice=请输入选择 (1-5): 

if "%choice%"=="1" goto start_service
if "%choice%"=="2" goto stop_service
if "%choice%"=="3" goto show_status
if "%choice%"=="4" goto show_log
if "%choice%"=="5" goto exit

echo 无效选择，请重试
echo.
goto menu

:start_service
echo.
echo 正在启动QuantNova服务...
start /b pythonw scripts\core\main.py > logs\service.log 2>&1
echo 服务已启动
echo 日志文件: logs\service.log
echo.
pause
goto menu

:stop_service
echo.
echo 正在停止服务...
taskkill /f /im pythonw.exe /fi "WINDOWTITLE eq QuantNova*" >nul 2>&1
echo 服务已停止
echo.
pause
goto menu

:show_status
echo.
echo 服务状态:
tasklist /fi "imagename eq pythonw.exe" | findstr pythonw
if errorlevel 1 (
    echo 服务未运行
)
echo.
pause
goto menu

:show_log
echo.
if exist logs\service.log (
    type logs\service.log
) else (
    echo 日志文件不存在
)
echo.
pause
goto menu

:exit
exit
