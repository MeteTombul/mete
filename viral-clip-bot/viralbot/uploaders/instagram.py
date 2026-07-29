"""Instagram (Reels) yükleyici — Instagram Graph API.

Kurulum:
  1. Facebook Developers'ta bir uygulama oluştur, Instagram Graph API ekle.
  2. Instagram hesabın bir "Professional/Business" hesabı olmalı ve bir
     Facebook Sayfası'na bağlı olmalı.
  3. Uzun ömürlü bir access token ve IG kullanıcı kimliğini (ig_user_id) al.
  4. secrets/instagram.json içine yaz:
     {"access_token": "...", "ig_user_id": "1784..."}
     veya IG_ACCESS_TOKEN / IG_USER_ID ortam değişkenlerini ayarla.

ÖNEMLİ: Instagram Graph API yerel dosya kabul etmez; videonun herkese açık
bir URL'de barınması gerekir. Klibi bir yere (S3, kendi sunucun vb.) yükleyip
meta["public_url"] alanına o adresi ver.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .base import Uploader, UploadResult

GRAPH = "https://graph.facebook.com/v21.0"


class InstagramUploader(Uploader):
    name = "instagram"

    @property
    def config_path(self) -> Path:
        return self.secrets_dir / "instagram.json"

    def _creds(self) -> tuple[str | None, str | None]:
        token = os.environ.get("IG_ACCESS_TOKEN")
        user_id = os.environ.get("IG_USER_ID")
        if (not token or not user_id) and self.config_path.exists():
            from ..util import read_text_any
            data = json.loads(read_text_any(self.config_path))
            token = token or data.get("access_token")
            user_id = user_id or data.get("ig_user_id")
        return token, user_id

    def is_configured(self) -> bool:
        token, user_id = self._creds()
        return bool(token and user_id)

    def authorize(self) -> str:
        return (
            "Instagram için uzun ömürlü access token ve ig_user_id alıp "
            f"{self.config_path} dosyasına yazın (veya IG_ACCESS_TOKEN / IG_USER_ID)."
        )

    def upload(self, clip_path: Path, meta: dict) -> UploadResult:
        import requests

        token, user_id = self._creds()
        if not token or not user_id:
            return UploadResult("instagram", "skipped", error="access token / ig_user_id yok")

        public_url = meta.get("public_url")
        if not public_url:
            return UploadResult(
                "instagram", "skipped",
                error="Instagram herkese açık bir video URL'si ister (meta['public_url']).",
            )

        caption = self._description(meta) or self._title(meta)
        try:
            # 1) Medya konteyneri oluştur
            create = requests.post(
                f"{GRAPH}/{user_id}/media",
                data={
                    "media_type": "REELS",
                    "video_url": public_url,
                    "caption": caption,
                    "access_token": token,
                },
                timeout=60,
            )
            create.raise_for_status()
            creation_id = create.json().get("id")
            if not creation_id:
                return UploadResult("instagram", "error", error=f"konteyner yok: {create.text}")

            # 2) İşlenmesini bekle
            for _ in range(30):
                st = requests.get(
                    f"{GRAPH}/{creation_id}",
                    params={"fields": "status_code", "access_token": token},
                    timeout=30,
                ).json()
                code = st.get("status_code")
                if code == "FINISHED":
                    break
                if code == "ERROR":
                    return UploadResult("instagram", "error", error="medya işleme hatası")
                time.sleep(5)

            # 3) Yayınla
            pub = requests.post(
                f"{GRAPH}/{user_id}/media_publish",
                data={"creation_id": creation_id, "access_token": token},
                timeout=60,
            )
            pub.raise_for_status()
            media_id = pub.json().get("id")
            return UploadResult("instagram", "ok", id=media_id)
        except Exception as e:  # noqa: BLE001
            return UploadResult("instagram", "error", error=str(e))
