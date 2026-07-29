@echo off
chcp 65001 >nul
title TikTok Baglan
cd /d "%~dp0"

echo ============================================
echo   TikTok baglantisi
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [HATA] Once Baslat.bat'i bir kez calistirip kurulumu tamamlayin.
  goto :son
)
call ".venv\Scripts\activate.bat"

if not exist "cikti\secrets\tiktok_app.json" (
  echo [YAPILMASI GEREKEN] Once su dosyayi olusturun:
  echo    cikti\secrets\tiktok_app.json
  echo.
  echo Icerigi soyle olmali:
  echo    {
  echo      "client_key": "TikTok panelindeki Client key",
  echo      "client_secret": "TikTok panelindeki Client secret",
  echo      "redirect_uri": "http://localhost:5599/callback"
  echo    }
  echo.
  echo client_key ve client_secret degerlerini developers.tiktok.com panelinizden alin.
  echo TikTok panelinde Redirect URI olarak da AYNI adresi kaydedin.
  echo Sonra bu dosyaya tekrar cift tiklayin.
  goto :son
)

echo TikTok hesabiniza giris icin tarayici acilacak, izin verin...
echo.
python -m viralbot.tiktok_auth

:son
echo.
echo ---------------------------------------------
echo Islem bitti. Kapatmak icin bir tusa basin.
pause >nul
