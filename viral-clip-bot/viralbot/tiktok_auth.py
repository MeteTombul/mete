"""TikTok tek-tıkla yetkilendirme yardımcısı.

TikTok'a giriş yaptırır, geri dönüşteki `code`'u otomatik yakalar, access
token'a çevirir ve secrets/tiktok_token.txt dosyasına kaydeder. Böylece
elle curl/istek atmana gerek kalmaz.

Önce secrets/tiktok_app.json oluştur:
  {
    "client_key": "TikTok panelindeki Client key",
    "client_secret": "TikTok panelindeki Client secret",
    "redirect_uri": "http://localhost:5599/callback"
  }
Ve TikTok panelinde Redirect URI olarak TAM OLARAK aynı adresi kaydet.

Çalıştır:  python -m viralbot.tiktok_auth   (ya da TikTok-Baglan.bat)
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets as pysecrets
import string
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPES = "video.publish,video.upload"
DEFAULT_REDIRECT = "http://localhost:5599/callback"


class _Handler(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _Handler.code = params["code"][0]
            msg = "TikTok yetkilendirmesi alındı. Bu sekmeyi kapatabilirsiniz."
        elif "error" in params:
            _Handler.error = params.get("error_description", params["error"])[0]
            msg = f"Hata: {_Handler.error}"
        else:
            msg = "Bekleniyor..."
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><body style='font-family:sans-serif'><h3>{msg}</h3></body></html>".encode())

    def log_message(self, *args):  # sessiz
        pass


def _make_pkce() -> tuple[str, str]:
    """PKCE code_verifier ve code_challenge (S256, base64url) üretir."""
    alphabet = string.ascii_letters + string.digits + "-._~"
    verifier = "".join(pysecrets.choice(alphabet) for _ in range(64))
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _exchange_code(
    client_key: str, client_secret: str, code: str, redirect_uri: str, code_verifier: str
) -> dict:
    import requests

    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def run(secrets_dir: Path, log=print) -> str:
    """TikTok OAuth akışını çalıştırır ve access token'ı kaydeder. Durum mesajı döndürür."""
    secrets_dir = Path(secrets_dir)
    secrets_dir.mkdir(parents=True, exist_ok=True)
    app_file = secrets_dir / "tiktok_app.json"
    token_file = secrets_dir / "tiktok_token.txt"

    if not app_file.exists():
        return (
            f"Önce {app_file} dosyasını oluşturun: "
            '{"client_key":"...","client_secret":"...","redirect_uri":"http://localhost:5599/callback"}'
        )

    from .util import read_text_any
    raw = read_text_any(app_file)
    # Kopyala-yapıştırdan gelen eğri/akıllı tırnakları düz tırnağa çevir
    for bad, good in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'")):
        raw = raw.replace(bad, good)
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as e:
        return (
            f"{app_file} geçerli bir JSON değil ({e}). Dosyanın tam olarak şöyle "
            'olduğundan emin olun (değerler DÜZ çift tırnak içinde): '
            '{"client_key":"...","client_secret":"...","redirect_uri":"http://localhost:5599/callback"}'
        )
    client_key = cfg.get("client_key", "").strip()
    client_secret = cfg.get("client_secret", "").strip()
    redirect_uri = cfg.get("redirect_uri", DEFAULT_REDIRECT).strip()
    if not client_key or not client_secret:
        return "tiktok_app.json içinde client_key ve client_secret dolu olmalı."

    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5599

    # PKCE (TikTok zorunlu kılar)
    code_verifier, code_challenge = _make_pkce()

    # Yetkilendirme URL'sini aç
    auth_query = urllib.parse.urlencode({
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": "viralbot",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"{AUTH_URL}?{auth_query}"

    _Handler.code = None
    _Handler.error = None
    server = http.server.HTTPServer((host, port), _Handler)

    log(f"Tarayıcı açılıyor, TikTok hesabınızla giriş yapıp izin verin...\n{auth_url}")
    threading.Thread(target=lambda: webbrowser.open(auth_url), daemon=True).start()

    # code veya hata gelene kadar istekleri işle (kullanıcı izin verene kadar)
    while _Handler.code is None and _Handler.error is None:
        server.handle_request()
    server.server_close()

    if _Handler.error:
        return f"Yetkilendirme reddedildi/hata: {_Handler.error}"

    try:
        data = _exchange_code(
            client_key, client_secret, _Handler.code, redirect_uri, code_verifier
        )
    except Exception as e:  # noqa: BLE001
        return f"Token alınamadı: {e}"

    access = data.get("access_token")
    if not access:
        return f"Yanıtta access_token yok: {data}"

    token_file.write_text(access, encoding="utf-8")
    refresh = data.get("refresh_token")
    if refresh:
        (secrets_dir / "tiktok_refresh.txt").write_text(refresh, encoding="utf-8")
    return f"TikTok bağlandı! Access token kaydedildi → {token_file}"


def main() -> None:
    secrets = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("cikti") / "secrets"
    print(run(secrets))


if __name__ == "__main__":
    main()
