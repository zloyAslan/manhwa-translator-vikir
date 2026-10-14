@echo off
chcp 65001 > nul
title Manhwa Master Downloader — Telegram Cloud Relay

echo ======================================================================
echo    MANHWA MASTER DOWNLOADER - TELEGRAM CLOUD RELAY
echo    Стрімінг глав манхви у Telegram-сховище через оперативну пам'ять
echo ======================================================================
echo.

set PYTHON_EXE=..\..\.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

"%PYTHON_EXE%" "%~dp0main.py"

pause
