@echo off
title Creative Automation Watcher

chcp 65001 > nul

cd /d "%~dp0"

echo ========================================
echo Creative Automation Watcher Running
echo ========================================
echo.
echo 이 창을 닫으면 자동화가 중지됩니다.
echo.
echo Google Sheets를 수정하면 자동 생성됩니다.
echo.

python scripts\watch_automation.py

pause