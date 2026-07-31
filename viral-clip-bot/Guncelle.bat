@echo off
chcp 65001 >nul
title Guncelle
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Once Baslat.bat'i bir kez calistirin.
  goto :son
)
call ".venv\Scripts\activate.bat"

echo yt-dlp guncelleniyor (Kick/Twitch/YouTube indirme motoru)...
python -m pip install -U yt-dlp

:son
echo.
echo Bitti. Kapatmak icin bir tusa basin.
pause >nul
