@echo off
rem S8 subtract/mask in-game test map build
rem   build.bat      : euddraft 0.11.0.1 (eudplib 0.81.0)
rem   build.bat old  : C:\euddraft0.9.2.0\euddraft.exe (eudplib 0.76.14)
rem output : build\S8_SubtractTest.scx (also copied to the StarCraft Maps folder if it exists)
rem base   : C:\euddraft0.9.2.0\CBTest.scx is copied to build\base.scx (the original is never modified)
setlocal
cd /d "%~dp0"
if not exist build mkdir build
if not exist build\base.scx copy /y "C:\euddraft0.9.2.0\CBTest.scx" build\base.scx >nul
set "ED=C:\euddraft0.11.0.1\euddraft.exe"
if /i "%~1"=="old" set "ED=C:\euddraft0.9.2.0\euddraft.exe"
echo [S8] %ED%
"%ED%" s8_ingame.eds
if errorlevel 1 (
  echo [S8] build failed
  exit /b 1
)
set "MAPS=C:\Program Files (x86)\StarCraft\Maps"
if exist "%MAPS%" (
  copy /y build\S8_SubtractTest.scx "%MAPS%\S8_SubtractTest.scx" >nul && echo [S8] copied to %MAPS%\S8_SubtractTest.scx
)
echo [S8] done: %~dp0build\S8_SubtractTest.scx
endlocal
