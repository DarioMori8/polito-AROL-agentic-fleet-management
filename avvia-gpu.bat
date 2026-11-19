@echo off
setlocal EnableExtensions DisableDelayedExpansion
call "%~dp0avvia.bat" --gpu %*
exit /b %errorlevel%
