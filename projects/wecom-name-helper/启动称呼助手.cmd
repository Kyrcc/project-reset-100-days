@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0wecom-name-helper.ps1"
if errorlevel 1 pause
