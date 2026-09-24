@echo off
setlocal
set "OPENMSX_HOME=%~dp0profile"
set "OPENMSX_USER_DATA=%~dp0profile\share"
set "OPENMSX_SYSTEM_DATA=%~dp0share"
if not exist "%OPENMSX_USER_DATA%\systemroms" mkdir "%OPENMSX_USER_DATA%\systemroms"
start "" "%~dp0openmsx.exe" %*
