@echo off
REM Double-click this file to start the PTSD system on your laptop.
REM It opens the sign-in pages in your browser. Keep this window open while
REM using the site; close it (or press Ctrl+C) to stop the server.

cd /d "%~dp0"

REM Use the project's virtual environment if it exists, otherwise system Python.
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

REM Open the browser a few seconds after the server starts.
start "" cmd /c "timeout /t 4 >nul && start http://127.0.0.1:5000/auth/login?role=administrator"

echo Starting the server... the admin sign-in page will open in your browser.
%PY% run.py
pause
