"""Uçtan uca akış: kanal -> en çok izlenen videolar -> viral anlar -> altyazılı efektli klipler."""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import channel as channel_mod
from . import claude_client
from . import download as download_mod
from . import effects as effects_mod
from . import moments as moments_mod
from . import scenes as scenes_mod
from . import subtitles as subtitles_mod
from . import transcribe as transcribe_mod
from .config import RenderOptions
from .transcribe import Transcript

_print_lock = threading.Lock()


def _slug(text: str, maxlen: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen] or "klip"


def _clip_text(transcript: Transcript, start: float, end: float) -> str:
    parts = [
        s.text.strip()
        for s in transcript.segments
        if s.end >= start and s.start <= end and s.text.strip()
    ]
    return " ".join(parts)


def _process_video(
    index: int,
    total: int,
    video,
    work: Path,
    clips_dir: Path,
    opts: RenderOptions,
    whisper_model: str,
    whisper_device: str,
    moments_per_video: int,
    clip_min: int,
    clip_max: int,
    use_scenes: bool,
    log,
) -> list[dict]:
    tag = f"[Video {index}/{total}]"
    log(f"\n{tag} {video.title}")

    log(f"{tag} İndiriliyor...")
    src = download_mod.download_video(video.url, work)
    duration = effects_mod.probe_duration(src)

    log(f"{tag} Altyazıya çevriliyor (Whisper)...")
    transcript = transcribe_mod.transcribe(
        src, model_size=whisper_model, device=whisper_device, language="tr"
    )

    cuts: list[float] = []
    if use_scenes:
        log(f"{tag} Sahne değişimleri tespit ediliyor...")
        cuts = scenes_mod.detect_scene_cuts(src)

    log(f"{tag} Viral anlar Claude ile seçiliyor...")
    mmts = moments_mod.detect_moments(
        src, transcript, duration, work,
        max_moments=moments_per_video, clip_min=clip_min, clip_max=clip_max,
    )
    log(f"{tag} {len(mmts)} an bulundu.")

    results: list[dict] = []
    for j, m in enumerate(mmts, 1):
        start, end = m["start"], m["end"]
        if use_scenes and cuts:
            start, end = scenes_mod.snap_to_scene(start, end, cuts)

        base = f"{_slug(video.title)}-{index}-{j}"
        ass_path = work / f"{base}.ass"
        subtitles_mod.build_ass(
            transcript, start, end, ass_path, opts, hook=m.get("hook")
        )

        clip_path = clips_dir / f"{base}.mp4"
        try:
            effects_mod.render_clip(src, ass_path, start, end, clip_path, opts)
        except Exception as e:  # noqa: BLE001
            log(f"{tag} ! Klip üretilemedi ({base}): {e}")
            continue

        meta = {
            "video": video.title,
            "video_url": video.url,
            "clip": str(clip_path),
            "start": round(start, 2),
            "end": round(end, 2),
            "moment_title": m.get("title"),
            "hook": m.get("hook"),
            "reason": m.get("reason"),
            "score": m.get("score"),
        }

        # SRT dışa aktarımı
        if opts.make_srt:
            srt_path = clips_dir / f"{base}.srt"
            subtitles_mod.export_srt(transcript, start, end, srt_path)
            meta["srt"] = str(srt_path)

        # Kapak
        if opts.make_thumbnail:
            try:
                thumb = clips_dir / f"{base}.jpg"
                effects_mod.make_thumbnail(
                    src, start + (end - start) * 0.4,
                    m.get("title") or "", thumb, opts, work,
                )
                meta["thumbnail"] = str(thumb)
            except Exception as e:  # noqa: BLE001
                log(f"{tag} ! Kapak üretilemedi ({base}): {e}")

        # SEO metası (Claude)
        if opts.make_metadata:
            try:
                seo = claude_client.generate_metadata(
                    _clip_text(transcript, start, end), m.get("title") or ""
                )
                meta["seo"] = seo
                txt = clips_dir / f"{base}.txt"
                txt.write_text(
                    f"BAŞLIK: {seo.get('title')}\n\n"
                    f"AÇIKLAMA:\n{seo.get('description')}\n\n"
                    f"HASHTAG: {' '.join(seo.get('hashtags', []))}\n",
                    encoding="utf-8",
                )
            except Exception as e:  # noqa: BLE001
                log(f"{tag} ! SEO metası üretilemedi ({base}): {e}")

        results.append(meta)
        log(f"{tag} ✓ {clip_path.name}  —  “{m.get('title')}”  (puan: {m.get('score')})")

    return results


def run(
    channel_url: str,
    out_dir: Path,
    opts: RenderOptions,
    top_videos: int = 3,
    moments_per_video: int = 3,
    whisper_model: str = "small",
    whisper_device: str = "cpu",
    clip_min: int = 15,
    clip_max: int = 60,
    use_scenes: bool = True,
    workers: int = 1,
    log=print,
) -> list[dict]:
    """Tüm akışı çalıştırır ve üretilen kliplerin meta verilerini döndürür."""
    out_dir = Path(out_dir)
    work = out_dir / "_work"
    clips_dir = out_dir / "klipler"
    work.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)

    def safe_log(msg):
        with _print_lock:
            log(msg)

    safe_log(f"[1/5] Kanal taranıyor: {channel_url}")
    videos = channel_mod.list_top_videos(channel_url, limit=top_videos)
    if not videos:
        safe_log("Hiç video bulunamadı. URL'yi kontrol edin.")
        return []
    safe_log(f"  En çok izlenen {len(videos)} video seçildi:")
    for v in videos:
        safe_log(f"    • {v.title}  ({v.view_count:,} izlenme)")

    results: list[dict] = []
    total = len(videos)

    def work_fn(i_video):
        i, video = i_video
        return _process_video(
            i, total, video, work, clips_dir, opts,
            whisper_model, whisper_device, moments_per_video,
            clip_min, clip_max, use_scenes, safe_log,
        )

    if workers <= 1:
        for item in enumerate(videos, 1):
            results.extend(work_fn(item))
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(work_fn, item) for item in enumerate(videos, 1)]
            for fut in as_completed(futs):
                try:
                    results.extend(fut.result())
                except Exception as e:  # noqa: BLE001
                    safe_log(f"! Video işlenemedi: {e}")

    summary_path = out_dir / "ozet.json"
    summary_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    safe_log(f"\nBitti. {len(results)} klip üretildi → {clips_dir}")
    safe_log(f"Özet: {summary_path}")
    return results
