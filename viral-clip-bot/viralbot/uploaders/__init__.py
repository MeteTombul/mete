"""Resmî platform API'leri ile otomatik yükleme.

Her yükleyici (YouTube / TikTok / Instagram) yalnızca kullanıcının kendi
hesabına, OAuth/API token ile erişir. Şifre saklanmaz, tarayıcı otomasyonu
yapılmaz — bu, platform kurallarına uygun tek doğru yöntemdir.
"""

from __future__ import annotations

from pathlib import Path

from .base import Uploader, UploadResult
from .instagram import InstagramUploader
from .tiktok import TikTokUploader
from .youtube import YouTubeUploader

_REGISTRY = {
    "youtube": YouTubeUploader,
    "tiktok": TikTokUploader,
    "instagram": InstagramUploader,
}


def get_uploader(name: str, secrets_dir: Path) -> Uploader:
    key = name.strip().lower()
    if key not in _REGISTRY:
        raise ValueError(f"Bilinmeyen platform: {name} (geçerli: {', '.join(_REGISTRY)})")
    return _REGISTRY[key](secrets_dir)


def available_platforms() -> list[str]:
    return list(_REGISTRY)


__all__ = [
    "Uploader",
    "UploadResult",
    "YouTubeUploader",
    "TikTokUploader",
    "InstagramUploader",
    "get_uploader",
    "available_platforms",
]
