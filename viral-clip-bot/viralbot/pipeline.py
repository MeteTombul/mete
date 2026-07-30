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
from . import reframe as reframe_mod
from . import scenes as scenes_mod
from . import subtitles as subtitles_mod
from . import transcribe as transcribe_mod
from . import uploaders as uploaders_mod
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
    upload_targets: list[str],
    secrets_dir: Path,
    youtube_privacy: str,
    next_publish_time,
    log,
) -> list[dict]:
    tag = f"[Video {index}/{total}]"
    log(f"\n{tag} {video.title}")

    log(f"{tag} İndiriliyor...")
    src = download_mod.download_video(video.url, work)
    duration = effects_mod.probe_duration(src)

    log(f"{tag} Altyazıya çevriliyor (Whisper, dil otomatik)...")
    transcript = transcribe_mod.transcribe(
        src, model_size=whisper_model, device=whisper_device, language=None
    )
    log(f"{tag} Algılanan dil: {transcript.language}")

    # İstenirse altyazıyı hedef dile çevir (zaman damgaları korunur)
    if opts.translate_to and transcript.language != opts.translate_to:
        log(f"{tag} Altyazı '{opts.translate_to}' diline çevriliyor (Claude)...")
        try:
            texts = [s.text for s in transcript.segments]
            translated = claude_client.translate_segments(texts, opts.translate_to)
            for seg, tr in zip(transcript.segments, translated):
                seg.text = tr
                seg.words = []  # çeviri sonrası kelime zamanlamaları geçersiz → segment altyazı
        except Exception as e:  # noqa: BLE001
            log(f"{tag} ! Çeviri başarısız, orijinal dil kullanılacak: {e}")

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

        focus_x = None
        if opts.reframe:
            focus_x = reframe_mod.compute_focus_x(src, start, end)

        clip_path = clips_dir / f"{base}.mp4"
        try:
            effects_mod.render_clip(src, ass_path, start, end, clip_path, opts, focus_x=focus_x)
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

        # Otomatik yükleme (resmî API + OAuth)
        if upload_targets:
            # Zamanlama: klip başına yayın zamanı (None ise hemen yayınlanır)
            pub_at = next_publish_time() if next_publish_time else None
            up_meta = dict(meta)
            if pub_at:
                up_meta["publish_at"] = pub_at
                up_meta["privacy"] = "private"  # publishAt için gerekli (o zaman herkese açılır)
                meta["scheduled_publish_at"] = pub_at
            else:
                up_meta["privacy"] = youtube_privacy

            uploads = []
            for platform in upload_targets:
                try:
                    up = uploaders_mod.get_uploader(platform, secrets_dir)
                    if not up.is_configured():
                        log(f"{tag} ↷ {platform}: yapılandırılmamış, atlandı ({up.authorize()})")
                        uploads.append({"platform": platform, "status": "skipped"})
                        continue
                    res = up.upload(clip_path, up_meta)
                    uploads.append({
                        "platform": res.platform, "status": res.status,
                        "url": res.url, "id": res.id, "error": res.error,
                    })
                    if res.status == "ok":
                        when = f" (yayın: {pub_at})" if pub_at else " (herkese açık)"
                        log(f"{tag} ⇪ {platform}: yüklendi{when} {res.url or res.id or ''}")
                    else:
                        log(f"{tag} ⚠ {platform}: {res.error}")
                except Exception as e:  # noqa: BLE001
                    log(f"{tag} ⚠ {platform} yükleme hatası: {e}")
                    uploads.append({"platform": platform, "status": "error", "error": str(e)})
            meta["uploads"] = uploads

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
    upload_targets: list[str] | None = None,
    secrets_dir: Path | None = None,
    videos: list | None = None,
    youtube_privacy: str = "public",
    schedule_start_hours: float = 0.0,
    schedule_interval_hours: float = 0.0,
    log=print,
) -> list[dict]:
    """Tüm akışı çalıştırır ve üretilen kliplerin meta verilerini döndürür.

    `videos` verilirse kanal taranmaz; verilen video listesi işlenir (zamanlayıcı
    yeni videoları buradan geçirir).
    """
    out_dir = Path(out_dir)
    work = out_dir / "_work"
    clips_dir = out_dir / "klipler"
    work.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)
    upload_targets = upload_targets or []
    secrets_dir = Path(secrets_dir) if secrets_dir else (out_dir / "secrets")

    def safe_log(msg):
        with _print_lock:
            log(msg)

    # Zamanlı yayın: klip başına ilerleyen yayın zamanı üreteci (UTC, RFC3339)
    import itertools
    from datetime import datetime, timedelta, timezone

    _pub_counter = itertools.count()
    _pub_lock = threading.Lock()
    _base_time = datetime.now(timezone.utc) + timedelta(hours=schedule_start_hours)

    def next_publish_time():
        if not schedule_interval_hours or schedule_interval_hours <= 0:
            return None  # zamanlama yok → hemen (herkese açık) yüklenir
        with _pub_lock:
            i = next(_pub_counter)
        t = _base_time + timedelta(hours=schedule_interval_hours * i)
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")

    if videos is None:
        safe_log(f"[1/5] Kanal taranıyor: {channel_url}")
        videos = channel_mod.list_top_videos(
            channel_url, limit=top_videos, skip_music=opts.skip_music, log=safe_log
        )
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
            clip_min, clip_max, use_scenes, upload_targets, secrets_dir,
            youtube_privacy, next_publish_time, safe_log,
        )

    if workers <= 1:
        for item in enumerate(videos, 1):
            try:
                results.extend(work_fn(item))
            except Exception as e:  # noqa: BLE001
                safe_log(f"! Video atlandı ({item[1].title}): {e}")
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(work_fn, item) for item in enumerate(videos, 1)]
            for fut in as_completed(futs):
                try:
                    results.extend(fut.result())
                except Exception as e:  # noqa: BLE001
                    safe_log(f"! Video işlenemedi: {e}")

    summary_path = out_dir / "ozet.json"
    existing: list = []
    if summary_path.exists():
        try:
            existing = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            existing = []
    summary_path.write_text(
        json.dumps(existing + results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    safe_log(f"\nBitti. {len(results)} klip üretildi → {clips_dir}")
    safe_log(f"Özet: {summary_path}")
    return results
