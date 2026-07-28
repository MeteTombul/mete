"""Yükleyiciler için ortak temel sınıf ve sonuç tipi."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UploadResult:
    platform: str
    status: str            # "ok" | "error" | "skipped"
    url: str | None = None
    id: str | None = None
    error: str | None = None
    extra: dict = field(default_factory=dict)


class Uploader:
    """Tüm platform yükleyicilerinin ortak arayüzü."""

    name = "base"

    def __init__(self, secrets_dir: Path):
        self.secrets_dir = Path(secrets_dir)
        self.secrets_dir.mkdir(parents=True, exist_ok=True)

    def is_configured(self) -> bool:
        """Gerekli kimlik bilgileri/token mevcut mu?"""
        raise NotImplementedError

    def authorize(self) -> str:
        """İlk kez yetkilendirme (OAuth) akışı. Talimat/URL döndürür."""
        raise NotImplementedError

    def upload(self, clip_path: Path, meta: dict) -> UploadResult:
        """Klibi platforma yükler."""
        raise NotImplementedError

    # Ortak yardımcılar --------------------------------------------------

    def _title(self, meta: dict, default: str = "Yeni klip") -> str:
        seo = meta.get("seo") or {}
        return seo.get("title") or meta.get("moment_title") or default

    def _description(self, meta: dict) -> str:
        seo = meta.get("seo") or {}
        desc = seo.get("description") or meta.get("reason") or ""
        tags = seo.get("hashtags") or []
        if tags:
            desc = (desc + "\n\n" + " ".join(tags)).strip()
        return desc

    def _hashtags(self, meta: dict) -> list[str]:
        seo = meta.get("seo") or {}
        return [t.lstrip("#") for t in (seo.get("hashtags") or [])]
