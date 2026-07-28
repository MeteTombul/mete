"""Viral Clip Bot — masaüstü uygulaması girişi.

Web arayüzünü tarayıcısız, kendi penceresinde açar (pywebview). pywebview
yoksa yerel sunucuyu başlatıp varsayılan tarayıcıda açar.

Çalıştırma:  python app.py   (ya da Windows'ta Baslat.bat çift tıkla)
"""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser

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


def _run_native() -> bool:
    """pywebview varsa uygulamayı kendi penceresinde açar. Başarılıysa True."""
    try:
        import webview  # type: ignore
    except Exception:
        return False
    # Flask WSGI uygulamasını doğrudan pencereye ver
    webview.create_window("Viral Clip Bot", app, width=1040, height=860, min_size=(820, 640))
    webview.start()
    return True


def _run_browser() -> None:
    """Yerel sunucuyu başlat ve varsayılan tarayıcıda aç."""
    threading.Thread(
        target=lambda: app.run(host=HOST, port=PORT, debug=False, use_reloader=False),
        daemon=True,
    ).start()
    time.sleep(1.5)
    webbrowser.open(URL)
    print(f"Uygulama açık: {URL}  (kapatmak için bu pencereyi kapatın / Ctrl+C)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def main() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    _warn_if_no_key()
    if not _run_native():
        _run_browser()


if __name__ == "__main__":
    main()
