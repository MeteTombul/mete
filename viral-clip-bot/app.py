"""Viral Clip Bot — masaüstü uygulaması girişi (Chrome uygulama penceresi).

Web arayüzünü, Chrome'un "uygulama modu" (--app) ile sekmesiz/adres çubuğusuz
temiz bir pencerede açar. Chrome bulunamazsa varsayılan tarayıcıda açılır.

Çalıştırma:  python app.py   (ya da Windows'ta Baslat.bat çift tıkla)
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from viralbot.webapp import SECRETS_DIR, app

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"


def _warn_if_no_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "UYARI: ANTHROPIC_API_KEY tanımlı değil. Viral an ve SEO metası üretimi "
            "çalışmaz. .env dosyasına anahtarınızı ekleyin.",
            file=sys.stderr,
        )


def _find_chrome() -> str | None:
    """Sistemde Chrome (veya Chromium/Edge) çalıştırılabilir yolunu bulur."""
    # PATH üzerinden
    for name in ("google-chrome", "google-chrome-stable", "chrome", "chromium",
                 "chromium-browser", "microsoft-edge", "msedge"):
        found = shutil.which(name)
        if found:
            return found

    candidates: list[str] = []
    if sys.platform.startswith("win"):
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        candidates += [
            rf"{pf}\Google\Chrome\Application\chrome.exe",
            rf"{pf86}\Google\Chrome\Application\chrome.exe",
            rf"{local}\Google\Chrome\Application\chrome.exe",
            # Chrome yoksa Edge de --app destekler
            rf"{pf86}\Microsoft\Edge\Application\msedge.exe",
            rf"{pf}\Microsoft\Edge\Application\msedge.exe",
        ]
    elif sys.platform == "darwin":
        candidates += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]

    for c in candidates:
        if Path(c).exists():
            return c
    return None


def _wait_for_server(timeout: float = 15.0) -> bool:
    """Flask sunucusu yanıt verene kadar bekler."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _start_server() -> None:
    threading.Thread(
        target=lambda: app.run(host=HOST, port=PORT, debug=False, use_reloader=False),
        daemon=True,
    ).start()


def main() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    _warn_if_no_key()

    _start_server()
    if not _wait_for_server():
        print("Sunucu başlatılamadı.", file=sys.stderr)
        sys.exit(1)

    chrome = _find_chrome()
    if chrome:
        # Ayrı bir profil klasörü: kendi bağımsız uygulama penceresi olarak açılır,
        # kullanıcının normal Chrome oturumuna karışmaz ve pencere boyutunu hatırlar.
        profile = Path(__file__).resolve().parent / ".chrome-profil"
        profile.mkdir(exist_ok=True)
        print(f"Uygulama Chrome penceresinde açılıyor: {URL}")
        proc = subprocess.Popen([
            chrome,
            f"--app={URL}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1040,860",
        ])
        try:
            proc.wait()  # Pencere kapanınca uygulamadan çıkılır
        except KeyboardInterrupt:
            pass
    else:
        print("Chrome bulunamadı, varsayılan tarayıcıda açılıyor...")
        webbrowser.open(URL)
        print(f"Uygulama açık: {URL}  (kapatmak için bu pencereyi kapatın / Ctrl+C)")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
