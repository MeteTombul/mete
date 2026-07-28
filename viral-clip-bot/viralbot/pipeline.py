"""Uçtan uca akış: kanal -> en çok izlenen videolar -> viral anlar -> altyazılı klipler."""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import channel as channel_mod
from . import download as download_mod
from . import effects as effects_mod
from . import moments as moments_mod
from . import subtitles as subtitles_mod
from . import transcribe as transcribe_mod


def _slug(text: str, maxlen: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen] or "klip"


def run(
    channel_url: str,
    out_dir: Path,
    top_videos: int = 3,
    moments_per_video: int = 3,
    whisper_model: str = "small",
    whisper_device: str = "cpu",
    clip_min: int = 15,
    clip_max: int = 60,
    log=print,
) -> list[dict]:
    """Tüm akışı çalıştırır ve üretilen kliplerin meta verilerini döndürür."""
    out_dir = Path(out_dir)
    work = out_dir / "_work"
    clips_dir = out_dir / "klipler"
    work.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)

    log(f"[1/5] Kanal taranıyor: {channel_url}")
    videos = channel_mod.list_top_videos(channel_url, limit=top_videos)
    if not videos:
        log("Hiç video bulunamadı. URL'yi kontrol edin.")
        return []
    log(f"  En çok izlenen {len(videos)} video seçildi:")
    for v in videos:
        log(f"    • {v.title}  ({v.view_count:,} izlenme)")

    results: list[dict] = []

    for i, video in enumerate(videos, 1):
        log(f"\n[Video {i}/{len(videos)}] {video.title}")

        log("  [2/5] İndiriliyor...")
        src = download_mod.download_video(video.url, work)
        duration = effects_mod.probe_duration(src)

        log("  [3/5] Altyazıya çevriliyor (Whisper)...")
        transcript = transcribe_mod.transcribe(
            src, model_size=whisper_model, device=whisper_device, language="tr"
        )

        log("  [4/5] Viral anlar Claude ile seçiliyor...")
        mmts = moments_mod.detect_moments(
            src, transcript, duration, work,
            max_moments=moments_per_video, clip_min=clip_min, clip_max=clip_max,
        )
        log(f"    {len(mmts)} an bulundu.")

        log("  [5/5] Klipler üretiliyor (altyazı + efekt)...")
        for j, m in enumerate(mmts, 1):
            base = f"{_slug(video.title)}-{i}-{j}"
            ass_path = work / f"{base}.ass"
            subtitles_mod.build_ass(
                transcript, m["start"], m["end"], ass_path, hook=m.get("hook")
            )
            clip_path = clips_dir / f"{base}.mp4"
            try:
                effects_mod.render_clip(src, ass_path, m["start"], m["end"], clip_path)
            except Exception as e:  # noqa: BLE001
                log(f"    ! Klip üretilemedi ({base}): {e}")
                continue

            meta = {
                "video": video.title,
                "video_url": video.url,
                "clip": str(clip_path),
                "start": m["start"],
                "end": m["end"],
                "title": m.get("title"),
                "hook": m.get("hook"),
                "reason": m.get("reason"),
                "score": m.get("score"),
            }
            results.append(meta)
            log(f"    ✓ {clip_path.name}  —  “{m.get('title')}”  (puan: {m.get('score')})")

    # Özet dosyası
    summary_path = out_dir / "ozet.json"
    summary_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"\nBitti. {len(results)} klip üretildi → {clips_dir}")
    log(f"Özet: {summary_path}")
    return results
