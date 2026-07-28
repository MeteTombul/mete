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


def detect_moments(
    video_path: Path,
    transcript: Transcript,
    duration: float,
    tmp_dir: Path,
    max_moments: int = 3,
    clip_min: int = 15,
    clip_max: int = 60,
) -> list[dict]:
    """Videodaki en viral olabilecek anları döndürür."""
    energies = _extract_audio_energy(video_path, tmp_dir)
    hint = _energy_hint(energies)
    lines = _transcript_lines(transcript)

    return find_viral_moments(
        transcript_lines=lines,
        energy_hint=hint,
        video_duration=duration,
        max_moments=max_moments,
        clip_min=clip_min,
        clip_max=clip_max,
    )
