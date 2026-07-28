"""ffmpeg ile klip kesme, 9:16 dönüştürme, efekt ve altyazı gömme."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _escape_for_filter(path: Path) -> str:
    """ffmpeg filtergraph içinde dosya yolunu güvenli hale getirir."""
    s = str(path)
    # Windows sürücü harfi ve genel özel karakterler
    s = s.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
    return s


def render_clip(
    source: Path,
    ass_path: Path,
    start: float,
    end: float,
    out_path: Path,
    fade: float = 0.5,
) -> Path:
    """Kaynaktan [start, end] aralığını dikey 9:16 viral klip olarak üretir.

    - Bulanık arka plan + ortalanmış video (dolgusuz dikey görünüm)
    - Başta fade-in, sonda fade-out (görüntü + ses) = 'başa ve sona efekt'
    - Gömülü stilli Türkçe altyazı ve hook metni (ASS)
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.1, end - start)
    ass = _escape_for_filter(ass_path)

    out_fade_start = max(0.0, dur - fade - 0.1)

    vf = (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=luma_radius=40:luma_power=1[bgb];"
        "[fg]scale=1080:-2:force_original_aspect_ratio=decrease[fgs];"
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]ass='{ass}'[subbed];"
        f"[subbed]fade=t=in:st=0:d={fade},"
        f"fade=t=out:st={out_fade_start:.2f}:d={fade}[vout]"
    )
    af = (
        f"afade=t=in:st=0:d={fade},"
        f"afade=t=out:st={out_fade_start:.2f}:d={fade}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(source),
        "-t", f"{dur:.3f}",
        "-filter_complex", vf,
        "-map", "[vout]",
        "-map", "0:a?",
        "-af", af,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-r", "30",
        "-movflags", "+faststart",
        str(out_path),
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return out_path


def probe_duration(path: Path) -> float:
    """Videonun süresini saniye olarak döndürür (ffprobe)."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())
