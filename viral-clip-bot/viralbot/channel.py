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


def _platform(url: str) -> str:
    u = url.lower()
    if "kick.com" in u:
        return "kick"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return "other"


def is_video_url(url: str) -> bool:
    """Bağlantı tek bir videoyu mu işaret ediyor? (kanal/oynatma listesi değil)."""
    u = url.lower()
    if "kick.com" in u:
        # kick.com/video/<uuid> ya da .../clip... = tek medya; kick.com/<yayinci> = kanal
        return "/video/" in u or "/clip" in u or "clips.kick" in u
    return (
        "watch?v=" in u
        or "youtu.be/" in u
        or "/shorts/" in u
        or "&v=" in u
    )


def _kick_slug(url: str) -> str | None:
    import re

    m = re.search(r"kick\.com/([^/?#]+)", url, re.I)
    return m.group(1) if m else None


def _kick_channel_videos(slug: str, limit: int) -> list["Video"]:
    """Kick kanalının VOD'larını (yayın kayıtlarını) Kick API'sinden çeker (en iyi çaba)."""
    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    r = requests.get(
        f"https://kick.com/api/v2/channels/{slug}/videos", headers=headers, timeout=30
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        data = data.get("data") or data.get("videos") or []

    vids: list[Video] = []
    for item in data:
        v = item.get("video") if isinstance(item.get("video"), dict) else item
        uuid = (v or {}).get("uuid") or item.get("uuid")
        if not uuid:
            continue
        vids.append(
            Video(
                id=str(uuid),
                title=item.get("session_title") or item.get("title") or "Kick VOD",
                url=f"https://kick.com/video/{uuid}",
                view_count=int(item.get("views") or (v or {}).get("views") or 0),
                duration=item.get("duration") or (v or {}).get("duration"),
            )
        )
    return vids[:limit]


def video_from_url(url: str) -> "Video":
    """Tek bir video bağlantısından Video nesnesi üretir (başlık, id, izlenme)."""
    opts = {"quiet": True, "no_warnings": True, "no_color": True, "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    vid = info.get("id") or "video"
    return Video(
        id=vid,
        title=info.get("title") or "(başlıksız)",
        url=info.get("webpage_url") or url,
        view_count=int(info.get("view_count") or 0),
        duration=info.get("duration"),
    )


def _normalize_channel_url(channel_url: str) -> str:
    """Kanal URL'sinin videolar sekmesini hedeflediğinden emin ol."""
    url = channel_url.rstrip("/")
    if url.endswith("/videos"):
        return url
    # @handle, /channel/UC..., /c/isim, /user/isim biçimlerinin hepsi çalışır
    return url + "/videos"


def _is_music(info: dict) -> bool:
    """Video bir müzik/şarkı içeriği mi? (kategori veya sanatçı/parça bilgisine göre)."""
    cats = info.get("categories") or []
    if any(c and str(c).lower() == "music" for c in cats):
        return True
    # YouTube Music otomatik videolarında bu alanlar dolu olur
    if info.get("track") or info.get("artist"):
        return True
    return False


def _filter_music(videos: list[Video], limit: int, log=None) -> list[Video]:
    """Videoların tam meta verisine bakıp müzikleri eler, ilk `limit` müzik-dışını döndürür."""
    probe_opts = {"quiet": True, "no_warnings": True, "no_color": True, "skip_download": True}
    selected: list[Video] = []
    with YoutubeDL(probe_opts) as ydl:
        # Gereğinden fazla sorgu yapmamak için makul bir tavan (limit x 5)
        for v in videos[: max(limit * 5, limit)]:
            if len(selected) >= limit:
                break
            try:
                info = ydl.extract_info(v.url, download=False)
            except Exception:  # noqa: BLE001
                continue
            if _is_music(info):
                if log:
                    log(f"    ♪ Müzik atlandı: {v.title}")
                continue
            selected.append(v)
    return selected


def list_top_videos(
    channel_url: str, limit: int = 5, skip_music: bool = True, log=None
) -> list[Video]:
    """Kanaldaki videoları izlenme sayısına göre azalan sıralar, ilk `limit` tanesini döndürür.

    `extract_flat` ile videolar hızlıca (tek tek indirmeden) taranır.
    skip_music=True ise müzik/şarkı videoları elenir (bu adım her aday için
    kısa bir meta sorgusu yapar, biraz daha yavaştır).
    """
    if _platform(channel_url) == "kick":
        slug = _kick_slug(channel_url)
        if not slug:
            return []
        vids = _kick_channel_videos(slug, limit * 3)
        vids.sort(key=lambda v: v.view_count, reverse=True)
        return vids[:limit]

    videos_url = _normalize_channel_url(channel_url)

    opts = {
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
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

    if skip_music:
        return _filter_music(videos, limit, log=log)
    return videos[:limit]


def list_latest_videos(channel_url: str, limit: int = 5) -> list[Video]:
    """Kanalın en yeni videolarını (yükleme sırasına göre) döndürür.

    Kanalın /videos sekmesi genelde en yeniyi başa koyar; bu yüzden liste
    sırası korunur (izlenmeye göre sıralanmaz).
    """
    if _platform(channel_url) == "kick":
        slug = _kick_slug(channel_url)
        if not slug:
            return []
        return _kick_channel_videos(slug, limit)

    videos_url = _normalize_channel_url(channel_url)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
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
