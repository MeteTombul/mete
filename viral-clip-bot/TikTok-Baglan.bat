@echo off
chcp 65001 >nul
title TikTok Baglan
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Once Baslat.bat'i bir kez calistirin (kurulum icin).
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"

echo.
echo TikTok baglaniyor...
echo ( cikti\secrets\tiktok_app.json dosyasinda client_key ve client_secret dolu olmali )
echo.
python -m viralbot.tiktok_auth
echo.
pause
