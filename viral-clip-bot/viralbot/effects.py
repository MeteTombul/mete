"""ffmpeg ile klip kesme, format dönüştürme, efektler, altyazı gömme ve kapak üretimi."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .config import RenderOptions


def _escape_for_filter(path: Path) -> str:
    """ffmpeg filtergraph içinde dosya yolunu güvenli hale getirir."""
    s = str(path)
    s = s.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
    return s


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


def render_clip(
    source: Path,
    ass_path: Path,
    start: float,
    end: float,
    out_path: Path,
    opts: RenderOptions,
) -> Path:
    """Kaynaktan [start, end] aralığını seçilen formatta viral klip olarak üretir.

    Efektler: bulanık arka plan + ortalanmış video, gömülü altyazı, baş/son fade,
    (opsiyonel) ilerleme çubuğu, logo, arka plan müziği ve ses normalizasyonu.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.1, end - start)
    W, H = opts.resolution()
    ass = _escape_for_filter(ass_path)
    fade = opts.fade
    out_fade = max(0.0, dur - fade - 0.1)

    # --- Girdiler ---
    cmd: list[str] = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{dur:.3f}"]
    logo_idx = None
    music_idx = None
    next_idx = 1
    if opts.logo and Path(opts.logo).exists():
        cmd += ["-i", str(opts.logo)]
        logo_idx = next_idx
        next_idx += 1
    if opts.music and Path(opts.music).exists():
        cmd += ["-stream_loop", "-1", "-i", str(opts.music)]
        music_idx = next_idx
        next_idx += 1

    # --- Video filtre zinciri ---
    v = (
        "[0:v]split=2[bg][fg];"
        f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},boxblur=luma_radius=40:luma_power=1[bgb];"
        f"[fg]scale={W}:-2:force_original_aspect_ratio=decrease[fgs];"
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]ass='{ass}'[subbed]"
    )
    last = "subbed"

    if logo_idx is not None:
        v += (
            f";[{logo_idx}:v]scale={int(W*0.16)}:-1[logo];"
            f"[{last}][logo]overlay=W-w-{int(W*0.03)}:{int(H*0.03)}[wm]"
        )
        last = "wm"

    if opts.progress_bar:
        bar_h = max(8, int(H * 0.008))
        v += (
            f";[{last}]drawbox=x=0:y=H-{bar_h}:w='W*t/{dur:.3f}':h={bar_h}:"
            f"color=0xF5A623@0.9:t=fill[pb]"
        )
        last = "pb"

    v += (
        f";[{last}]fade=t=in:st=0:d={fade},"
        f"fade=t=out:st={out_fade:.2f}:d={fade}[vout]"
    )

    # --- Ses filtre zinciri ---
    voice_chain = "[0:a]"
    if opts.loudnorm:
        voice_chain += "loudnorm=I=-16:TP=-1.5:LRA=11,"
    voice_chain += f"afade=t=in:st=0:d={fade},afade=t=out:st={out_fade:.2f}:d={fade}[voice]"

    if music_idx is not None:
        a = (
            voice_chain + ";"
            f"[{music_idx}:a]volume={opts.music_volume},atrim=0:{dur:.3f},"
            f"afade=t=in:st=0:d={fade},afade=t=out:st={out_fade:.2f}:d={fade}[music];"
            "[music][voice]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[ducked];"
            "[voice][ducked]amix=inputs=2:normalize=0[aout]"
        )
        audio_out = "[aout]"
    else:
        a = voice_chain
        audio_out = "[voice]"

    filter_complex = v + ";" + a

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", audio_out,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-r", "30",
        "-movflags", "+faststart",
        str(out_path),
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return out_path


def make_thumbnail(
    source: Path,
    at_time: float,
    title: str,
    out_path: Path,
    opts: RenderOptions,
    tmp_dir: Path,
) -> Path:
    """Klipten bir kare alır, karartıp üstüne büyük başlık basarak kapak (jpg) üretir."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    W, H = opts.resolution()

    # Başlık için tek karelik ASS
    title_ass = tmp_dir / (out_path.stem + "_title.ass")
    size = int(H * 0.06)
    safe_title = title.replace("{", "(").replace("}", ")").replace("\n", " ")
    title_ass.write_text(
        f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title, {opts.font}, {size}, {opts.sub_color}, &H00000000, &H80000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 6, 4, 2, 80, 80, {int(H*0.1)}, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Title,,0,0,0,,{safe_title}
""",
        encoding="utf-8",
    )
    ass = _escape_for_filter(title_ass)

    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"eq=brightness=-0.12,ass='{ass}'"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", f"{at_time:.3f}", "-i", str(source),
            "-frames:v", "1", "-vf", vf, "-q:v", "3",
            str(out_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    title_ass.unlink(missing_ok=True)
    return out_path
