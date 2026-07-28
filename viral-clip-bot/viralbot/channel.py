"""Kanal videolarını listeleme ve en çok izlenenleri seçme (yt-dlp)."""

from __future__ import annotations

from dataclasses import dataclass

from yt_dlp import YoutubeDL


@dataclass
class Video:
    id: str
    title: str
    url: str
    view_count: int
    duration: int | None = None


def _normalize_channel_url(channel_url: str) -> str:
    """Kanal URL'sinin videolar sekmesini hedeflediğinden emin ol."""
    url = channel_url.rstrip("/")
    if url.endswith("/videos"):
        return url
    # @handle, /channel/UC..., /c/isim, /user/isim biçimlerinin hepsi çalışır
    return url + "/videos"


def list_top_videos(channel_url: str, limit: int = 5) -> list[Video]:
    """Kanaldaki videoları izlenme sayısına göre azalan sıralar, ilk `limit` tanesini döndürür.

    `extract_flat` ile videolar hızlıca (tek tek indirmeden) taranır.
    """
    videos_url = _normalize_channel_url(channel_url)

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }

    entries: list[dict] = []
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(videos_url, download=False)
        for entry in info.get("entries") or []:
            if not entry:
                continue
            entries.append(entry)

    videos: list[Video] = []
    for e in entries:
        vid = e.get("id")
        if not vid:
            continue
        videos.append(
            Video(
                id=vid,
                title=e.get("title") or "(başlıksız)",
                url=e.get("url") or f"https://www.youtube.com/watch?v={vid}",
                view_count=int(e.get("view_count") or 0),
                duration=e.get("duration"),
            )
        )

    # extract_flat bazı kanallarda view_count vermez; o zaman sıralama liste sırasını korur
    videos.sort(key=lambda v: v.view_count, reverse=True)
    return videos[:limit]


def list_latest_videos(channel_url: str, limit: int = 5) -> list[Video]:
    """Kanalın en yeni videolarını (yükleme sırasına göre) döndürür.

    Kanalın /videos sekmesi genelde en yeniyi başa koyar; bu yüzden liste
    sırası korunur (izlenmeye göre sıralanmaz).
    """
    videos_url = _normalize_channel_url(channel_url)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "playlistend": limit,
    }
    videos: list[Video] = []
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(videos_url, download=False)
        for e in info.get("entries") or []:
            if not e or not e.get("id"):
                continue
            videos.append(
                Video(
                    id=e["id"],
                    title=e.get("title") or "(başlıksız)",
                    url=e.get("url") or f"https://www.youtube.com/watch?v={e['id']}",
                    view_count=int(e.get("view_count") or 0),
                    duration=e.get("duration"),
                )
            )
    return videos[:limit]
