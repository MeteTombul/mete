"""Viral an tespiti: ses enerjisi ölçümü + Claude ile transkript analizi."""

from __future__ import annotations

import subprocess
import wave
from array import array
from pathlib import Path

from .claude_client import find_viral_moments
from .transcribe import Transcript


def _extract_audio_energy(video_path: Path, tmp_dir: Path) -> list[float]:
    """Videodan saniye bazlı RMS ses enerjisi çıkarır (numpy'siz, stdlib ile).

    ffmpeg ile 16kHz mono wav'a çevirir, `wave` ile okur, saniyelik RMS hesaplar.
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    wav_path = tmp_dir / (video_path.stem + "_16k.wav")

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video_path),
                "-ac", "1", "-ar", "16000", "-vn",
                str(wav_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001
        return []

    energies: list[float] = []
    with wave.open(str(wav_path), "rb") as wf:
        rate = wf.getframerate()
        frames_per_sec = rate
        while True:
            frames = wf.readframes(frames_per_sec)
            if not frames:
                break
            samples = array("h")
            samples.frombytes(frames)
            if not samples:
                energies.append(0.0)
                continue
            # RMS
            acc = 0
            for s in samples:
                acc += s * s
            rms = (acc / len(samples)) ** 0.5
            energies.append(rms)

    wav_path.unlink(missing_ok=True)
    return energies


def _energy_hint(energies: list[float], top_k: int = 20) -> str:
    """En yüksek enerjili saniyeleri Claude'a ipucu olarak özetler."""
    if not energies:
        return "(ses enerjisi verisi yok)"
    peak = max(energies) or 1.0
    indexed = sorted(enumerate(energies), key=lambda x: x[1], reverse=True)[:top_k]
    indexed.sort(key=lambda x: x[0])
    lines = [
        f"{sec}s: %{round(100 * val / peak)}"
        for sec, val in indexed
    ]
    return "\n".join(lines)


def _transcript_lines(transcript: Transcript) -> str:
    """Segmentleri [başlangıç-bitiş] metin biçiminde satırlara döker."""
    lines = []
    for s in transcript.segments:
        lines.append(f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}")
    return "\n".join(lines)


def _fallback_moments(
    energies: list[float],
    transcript: Transcript,
    duration: float,
    max_moments: int,
    clip_min: int,
    clip_max: int,
) -> list[dict]:
    """Claude olmadan, ses enerjisi (yoksa eşit aralık) ile an seçer. Her zaman klip üretir."""
    win = int(min(clip_max, max(clip_min, 30)))
    chosen: list[dict] = []
    used: list[tuple[float, float]] = []

    def _text_at(start: float, end: float) -> str:
        return " ".join(
            s.text.strip() for s in transcript.segments
            if s.start >= start and s.start < end and s.text.strip()
        ).strip()

    if energies:
        # Kayan pencere enerji ortalamasına göre en yüksek, çakışmayan bölümler
        scores = []
        for start in range(0, max(1, len(energies) - 1), 5):
            seg = energies[start:start + win]
            if seg:
                scores.append((start, sum(seg) / len(seg)))
        scores.sort(key=lambda x: x[1], reverse=True)
        for start, sc in scores:
            end = min(duration, start + win)
            if end - start < clip_min:
                continue
            if any(not (end <= s or start >= e) for s, e in used):
                continue
            used.append((start, end))
            txt = _text_at(start, end)
            chosen.append({
                "start": float(start), "end": float(end),
                "title": (txt[:40] or "Öne çıkan an"),
                "hook": txt[:60], "reason": "ses enerjisi tepe noktası",
                "score": round(sc, 1),
            })
            if len(chosen) >= max_moments:
                break

    if not chosen:
        # Ses verisi yok → videoyu eşit aralıklara böl
        n = max(1, min(max_moments, int(duration // win) or 1))
        step = duration / (n + 1)
        for i in range(1, n + 1):
            start = max(0.0, step * i - win / 2)
            end = min(duration, start + win)
            if end - start < min(clip_min, 5):
                continue
            txt = _text_at(start, end)
            chosen.append({
                "start": float(start), "end": float(end),
                "title": (txt[:40] or f"Bölüm {i}"),
                "hook": txt[:60], "reason": "eşit aralık", "score": 0,
            })
    return chosen[:max_moments]


def detect_moments(
    video_path: Path,
    transcript: Transcript,
    duration: float,
    tmp_dir: Path,
    max_moments: int = 3,
    clip_min: int = 15,
    clip_max: int = 60,
    log=print,
) -> list[dict]:
    """Videodaki en viral olabilecek anları döndürür.

    Önce Claude ile dener; başarısız olursa ya da an döndürmezse ses enerjisi
    tabanlı yedek seçime düşer — böylece her durumda klip üretilir.
    """
    energies = _extract_audio_energy(video_path, tmp_dir)
    hint = _energy_hint(energies)
    lines = _transcript_lines(transcript)

    moments: list[dict] = []
    try:
        moments = find_viral_moments(
            transcript_lines=lines,
            energy_hint=hint,
            video_duration=duration,
            max_moments=max_moments,
            clip_min=clip_min,
            clip_max=clip_max,
        )
    except Exception as e:  # noqa: BLE001
        log(f"  ! Claude an seçimi başarısız ({e}); yedek seçim kullanılacak.")

    if not moments:
        log("  Ses enerjisi tabanlı yedek an seçimi kullanılıyor.")
        moments = _fallback_moments(
            energies, transcript, duration, max_moments, clip_min, clip_max
        )
    return moments
