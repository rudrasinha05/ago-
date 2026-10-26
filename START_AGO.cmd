@echo off
setlocal
cd /d "%~dp0"
echo AGO LOCAL - START
echo Existing projects and database are preserved. No paid AI providers.
powershell.exe -NoProfile -File "%~dp0scripts\ago-start.ps1"
set "AGO_EXIT=%ERRORLEVEL%"
if not "%AGO_EXIT%"=="0" (
    echo.
    echo AGO startup stopped. Read the message above; no force reset was performed.
)
echo.
echo To stop AGO normally, use Ctrl+C while its server window is active.
pause
exit /b %AGO_EXIT%
