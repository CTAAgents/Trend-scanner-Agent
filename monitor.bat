@echo off
chcp 65001 >nul
title QuantNova 状态监控

echo ========================================
echo   QuantNova 状态监控
echo ========================================
echo.

cd /d "%~dp0"

:refresh
cls
echo [%time%] QuantNova 状态监控
echo ========================================
echo.

echo [系统状态]
if exist logs\service.log (
    echo 最后日志时间: 
    powershell -command "Get-Item logs\service.log | Select-Object -ExpandProperty LastWriteTime"
) else (
    echo 日志文件不存在
)
echo.

echo [进程状态]
tasklist /fi "imagename eq pythonw.exe" | findstr pythonw
if errorlevel 1 (
    echo 服务未运行
)
echo.

echo [资源使用]
powershell -command "Get-Process pythonw -ErrorAction SilentlyContinue | Select-Object CPU, WorkingSet64 | Format-Table"
echo.

echo [最近日志]
if exist logs\service.log (
    powershell -command "Get-Content logs\service.log -Tail 10"
) else (
    echo 无日志
)
echo.

echo ========================================
echo 按 Ctrl+C 退出，每30秒自动刷新
timeout /t 30 >nul
goto refresh
