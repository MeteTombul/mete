"""Tek bir videoyu indirme (yt-dlp)."""

from __future__ import annotations

from pathlib import Path

from yt_dlp import YoutubeDL


def download_video(url: str, out_dir: Path, max_height: int = 1080) -> Path:
    """Videoyu mp4 olarak indirir ve dosya yolunu döndürür.

    max_height: dikey klip 1080x1920 olacağı için 1080p yeterli; daha yüksek
    çözünürlük indirmek gereksiz yer/bant genişliği tüketir.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(out_dir / "%(id)s.%(ext)s")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": outtmpl,
        "format": (
            f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"best[height<={max_height}][ext=mp4]/best"
        ),
        "merge_output_format": "mp4",
    }

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Birleştirilmiş dosyanın gerçek yolunu bul
        vid = info["id"]
        candidate = out_dir / f"{vid}.mp4"
        if candidate.exists():
            return candidate
        # Nadiren farklı uzantı kalabilir
        for p in out_dir.glob(f"{vid}.*"):
            if p.suffix in {".mp4", ".mkv", ".webm"}:
                return p
    raise FileNotFoundError(f"İndirilen dosya bulunamadı: {url}")
