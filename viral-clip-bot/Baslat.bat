@echo off
chcp 65001 >nul
title Viral Clip Bot
cd /d "%~dp0"

echo ============================================
echo   Viral Clip Bot - baslatiliyor...
echo ============================================
echo.

REM --- Python var mi? ---
where python >nul 2>nul
if errorlevel 1 (
  echo [HATA] Python bulunamadi.
  echo Lutfen https://www.python.org/downloads/ adresinden Python 3.10+ kurun
  echo ve kurulumda "Add Python to PATH" secenegini isaretleyin.
  echo.
  pause
  exit /b 1
)

REM --- ffmpeg var mi? (uyari) ---
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [UYARI] ffmpeg bulunamadi. Video islemek icin gereklidir.
  echo Kurulum: https://www.gyan.dev/ffmpeg/builds/  ^(indirip PATH'e ekleyin^)
  echo.
)

REM --- Ilk kurulum: sanal ortam + bagimliliklar ---
if not exist ".venv\Scripts\python.exe" (
  echo Ilk kurulum yapiliyor, bu birkac dakika surebilir...
  python -m venv .venv
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  echo Kurulum tamam.
  echo.
) else (
  call ".venv\Scripts\activate.bat"
)

REM --- .env yoksa ornekten olustur ---
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo [BILGI] .env olusturuldu. ANTHROPIC_API_KEY anahtarinizi .env dosyasina yazin.
  echo.
)

REM --- Uygulamayi baslat ---
python app.py

pause
