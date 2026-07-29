"""TikTok yükleyici — Content Posting API (FILE_UPLOAD, Direct Post).

Kurulum:
  1. developers.tiktok.com'da bir uygulama oluştur, "Content Posting API"
     iznini al (video.publish scope).
  2. OAuth ile KENDİ hesabından bir access token al.
  3. Token'ı secrets/tiktok_token.txt içine yaz veya TIKTOK_ACCESS_TOKEN
     ortam değişkeni olarak ver.

Not: TikTok'un denetimden geçmemiş uygulamalarında videolar yalnızca özel
(SELF_ONLY) olarak yüklenebilir; herkese açık yayın için uygulama onayı gerekir.
"""

from __future__ import annotations

import os
from pathlib import Path

from .base import Uploader, UploadResult

API = "https://open.tiktokapis.com/v2"


class TikTokUploader(Uploader):
    name = "tiktok"

    @property
    def token_path(self) -> Path:
        return self.secrets_dir / "tiktok_token.txt"

    def _token(self) -> str | None:
        if os.environ.get("TIKTOK_ACCESS_TOKEN"):
            return os.environ["TIKTOK_ACCESS_TOKEN"].strip()
        if self.token_path.exists():
            from ..util import read_text_any
            return read_text_any(self.token_path).strip()
        return None

    def is_configured(self) -> bool:
        return self._token() is not None

    def authorize(self) -> str:
        # tiktok_app.json (client_key/secret) varsa tek-tıkla OAuth akışını çalıştır.
        app_file = self.secrets_dir / "tiktok_app.json"
        if app_file.exists():
            from ..tiktok_auth import run as tiktok_run
            return tiktok_run(self.secrets_dir)
        return (
            "TikTok bağlamak için önce "
            f"{app_file} oluşturun: "
            '{"client_key":"...","client_secret":"...","redirect_uri":"http://localhost:5599/callback"} '
            "— sonra tekrar 'tiktok yetkilendir'e tıklayın. (Redirect URI'yi TikTok panelinde de "
            "birebir aynı kaydedin.)"
        )

    def upload(self, clip_path: Path, meta: dict) -> UploadResult:
        import requests

        token = self._token()
        if not token:
            return UploadResult("tiktok", "skipped", error="access token yok")

        headers = {"Authorization": f"Bearer {token}"}
        size = clip_path.stat().st_size
        privacy = meta.get("tiktok_privacy", "SELF_ONLY")  # onaysız uygulama için tek seçenek

        try:
            # 1) Yükleme oturumu başlat (FILE_UPLOAD, tek parça)
            init = requests.post(
                f"{API}/post/publish/video/init/",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "post_info": {
                        "title": self._title(meta)[:150],
                        "privacy_level": privacy,
                        "disable_comment": False,
                        "disable_duet": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": size,
                        "chunk_size": size,
                        "total_chunk_count": 1,
                    },
                },
                timeout=60,
            )
            init.raise_for_status()
            data = init.json().get("data", {})
            publish_id = data.get("publish_id")
            upload_url = data.get("upload_url")
            if not upload_url:
                return UploadResult("tiktok", "error", error=f"init yanıtı beklenmedik: {init.text}")

            # 2) Videoyu yükle (PUT)
            with open(clip_path, "rb") as f:
                put = requests.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes 0-{size - 1}/{size}",
                    },
                    data=f,
                    timeout=600,
                )
            put.raise_for_status()

            return UploadResult(
                "tiktok", "ok", id=publish_id,
                extra={"note": "TikTok işlemi tamamladıktan sonra taslaklar/profilde görünür."},
            )
        except Exception as e:  # noqa: BLE001
            return UploadResult("tiktok", "error", error=str(e))
