@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHON_MANAGER_AUTOMATIC_INSTALL=false"
where py.exe >nul 2>&1
if errorlevel 1 goto :missing
py.exe -3 -B "%~dp0devstate.py" --toolkit "%~dp0." rehearse %*
set "AIDBACKUP_EXIT=%ERRORLEVEL%"
if not defined AIDBACKUP_NO_PAUSE pause
exit /b %AIDBACKUP_EXIT%
:missing
echo Python 3.11 or newer with the Windows py launcher is required.
echo Install Python from python.org, then run this launcher again.
echo Nothing was backed up or restored. Read README.md before running.
if not defined AIDBACKUP_NO_PAUSE pause
exit /b 2
