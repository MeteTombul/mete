"""Çok platformlu kaynak çözümleme (YouTube / Twitch / Kick / diğer) — yt-dlp tabanlı.

Verilen bağlantının kanal mı yoksa tek video/VOD/klip mi olduğunu algılar;
kanal ise en çok izlenen (veya en yeni) videoları listeler.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from yt_dlp import YoutubeDL


@dataclass
class Video:
    id: str
    title: str
    url: str
    view_count: int
    duration: int | None = None


# ---------------------------------------------------------------------------
# Platform algılama
# ---------------------------------------------------------------------------

def _platform(url: str) -> str:
    u = url.lower()
    if "kick.com" in u:
        return "kick"
    if "twitch.tv" in u:
        return "twitch"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return "other"


def is_video_url(url: str) -> bool:
    """Bağlantı tek bir videoyu/VOD'u/klibi mi işaret ediyor? (kanal değil)."""
    u = url.lower()
    p = _platform(u)
    if p == "kick":
        return "/video/" in u or "/clip" in u or "clips.kick" in u
    if p == "twitch":
        return bool(re.search(r"/videos/\d+", u)) or "/clip/" in u or "clips.twitch" in u
    if p == "youtube":
        return (
            "watch?v=" in u or "youtu.be/" in u or "/shorts/" in u or "&v=" in u
        )
    # Bilinmeyen platform: kanal gibi görünmüyorsa tek video say
    return True


# ---------------------------------------------------------------------------
# Ortak yt-dlp yardımcıları
# ---------------------------------------------------------------------------

_BASE_OPTS = {"quiet": True, "no_warnings": True, "no_color": True, "skip_download": True}


def _video_from_entry(e: dict) -> Video | None:
    vid = e.get("id")
    if not vid:
        return None
    url = e.get("url") or e.get("webpage_url") or ""
    if url and not url.startswith("http"):
        # extract_flat bazen sadece id verir
        url = f"https://www.youtube.com/watch?v={vid}"
    return Video(
        id=str(vid),
        title=e.get("title") or "(başlıksız)",
        url=url,
        view_count=int(e.get("view_count") or 0),
        duration=e.get("duration"),
    )


def _flat_entries(url: str, limit: int) -> list[dict]:
    """Bir kanal/oynatma listesi URL'sinden videoları düz (hızlı) çıkarır."""
    opts = {
        **_BASE_OPTS,
        "extract_flat": "in_playlist",
        "playlistend": max(1, limit),
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    raw = info.get("entries") or ([] if info.get("id") is None else [info])
    flat: list[dict] = []
    for e in raw:
        if not e:
            continue
        # Kanal sekmeleri iç içe olabilir (YouTube: Videos/Shorts/Live)
        if e.get("entries"):
            for e2 in e["entries"]:
                if e2:
                    flat.append(e2)
        else:
            flat.append(e)
    return flat


def video_from_url(url: str) -> Video:
    """Tek bir video/VOD/klip bağlantısından Video nesnesi üretir."""
    with YoutubeDL(_BASE_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
    vid = info.get("id") or "video"
    return Video(
        id=str(vid),
        title=info.get("title") or "(başlıksız)",
        url=info.get("webpage_url") or url,
        view_count=int(info.get("view_count") or 0),
        duration=info.get("duration"),
    )


# ---------------------------------------------------------------------------
# Kanal URL normalleştirme
# ---------------------------------------------------------------------------

def _normalize_channel_url(url: str) -> str:
    p = _platform(url)
    u = url.rstrip("/")
    if p in ("youtube", "twitch"):
        if u.endswith("/videos"):
            return u
        # Bilinen sekmeleri temizle
        for tab in ("/featured", "/streams", "/shorts", "/about"):
            if u.endswith(tab):
                u = u[: -len(tab)]
        return u + "/videos"
    return u  # kick / diğer: olduğu gibi


# ---------------------------------------------------------------------------
# Müzik filtresi (yalnızca YouTube, yıkıcı değil)
# ---------------------------------------------------------------------------

def _is_music(info: dict) -> bool:
    cats = info.get("categories") or []
    if any(c and str(c).lower() == "music" for c in cats):
        return True
    if info.get("track") or info.get("artist"):
        return True
    return False


def _filter_music(videos: list[Video], limit: int, log=None) -> list[Video]:
    """Aday videoların meta verisine bakıp müzikleri eler (başarısız olursa boş döner)."""
    selected: list[Video] = []
    with YoutubeDL(_BASE_OPTS) as ydl:
        for v in videos[: max(limit * 4, limit)]:
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


# ---------------------------------------------------------------------------
# Kick kanal VOD listesi (API — en iyi çaba)
# ---------------------------------------------------------------------------

def _kick_slug(url: str) -> str | None:
    m = re.search(r"kick\.com/([^/?#]+)", url, re.I)
    return m.group(1) if m else None


def _kick_channel_videos(slug: str, limit: int) -> list[Video]:
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


# ---------------------------------------------------------------------------
# Genel kanal listeleme
# ---------------------------------------------------------------------------

def list_top_videos(
    channel_url: str, limit: int = 5, skip_music: bool = True, log=None
) -> list[Video]:
    """Kanaldaki videoları izlenmeye göre sıralar, ilk `limit` tanesini döndürür."""
    p = _platform(channel_url)

    if p == "kick":
        vids: list[Video] = []
        slug = _kick_slug(channel_url)
        if slug:
            try:
                vids = _kick_channel_videos(slug, limit * 3)
            except Exception as e:  # noqa: BLE001
                if log:
                    log(f"    Kick API listesi alınamadı: {e}")
        if not vids:
            try:
                vids = [v for e in _flat_entries(channel_url, limit * 3)
                        if (v := _video_from_entry(e))]
            except Exception:  # noqa: BLE001
                vids = []
        vids.sort(key=lambda v: v.view_count, reverse=True)
        return vids[:limit]

    # YouTube / Twitch / diğer
    try:
        entries = _flat_entries(_normalize_channel_url(channel_url), limit * 4)
    except Exception as e:  # noqa: BLE001
        if log:
            log(f"    Liste alınamadı: {e}")
        entries = []
    vids = [v for e in entries if (v := _video_from_entry(e))]
    vids.sort(key=lambda v: v.view_count, reverse=True)

    if skip_music and p == "youtube":
        filtered = _filter_music(vids, limit, log=log)
        if filtered:  # yıkıcı değil: filtre bir şey bulduysa kullan, yoksa filtresiz devam
            return filtered
    return vids[:limit]


def list_latest_videos(channel_url: str, limit: int = 5) -> list[Video]:
    """Kanalın en yeni videolarını (yükleme sırasına göre) döndürür."""
    p = _platform(channel_url)

    if p == "kick":
        slug = _kick_slug(channel_url)
        if not slug:
            return []
        try:
            return _kick_channel_videos(slug, limit)
        except Exception:  # noqa: BLE001
            return []

    try:
        entries = _flat_entries(_normalize_channel_url(channel_url), limit)
    except Exception:  # noqa: BLE001
        entries = []
    return [v for e in entries if (v := _video_from_entry(e))][:limit]
