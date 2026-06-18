@echo off
chcp 65001 >nul
title QuantNova - 期货趋势跟踪决策辅助系统

echo ========================================
echo   QuantNova 期货趋势跟踪决策辅助系统
echo   推理重于规则
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请安装Python 3.10+
    pause
    exit /b 1
)
echo Python环境正常

echo.
echo [2/3] 检查依赖...
pip show pandas >nul 2>&1
if errorlevel 1 (
    echo 首次运行，正在安装依赖...
    pip install -r requirements.txt
)
echo 依赖检查完成

echo.
echo [3/3] 启动系统...
echo.
python scripts\core\main.py

pause
