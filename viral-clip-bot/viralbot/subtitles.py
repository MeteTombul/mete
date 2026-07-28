"""Klibe gömülecek stilli Türkçe altyazı (ASS) üretimi."""

from __future__ import annotations

from pathlib import Path

from .transcribe import Transcript


def _fmt_time(t: float) -> str:
    """Saniyeyi ASS zaman biçimine (h:mm:ss.cs) çevirir."""
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs == 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption, Arial, 68, &H00FFFFFF, &H000000FF, &H00000000, &H64000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 5, 2, 2, 60, 60, 340, 1
Style: Hook, Arial, 78, &H0000E5FF, &H000000FF, &H00000000, &H96000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 6, 3, 8, 80, 80, 260, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _escape(text: str) -> str:
    return text.replace("\n", " ").replace("{", "(").replace("}", ")").strip()


def build_ass(
    transcript: Transcript,
    clip_start: float,
    clip_end: float,
    out_path: Path,
    hook: str | None = None,
) -> Path:
    """Klip aralığına düşen altyazıları, klibe göreli zamanlarla ASS dosyasına yazar.

    hook verilirse ilk ~2.5 saniye ekranın üstünde büyük punto sabit durur.
    """
    lines = [ASS_HEADER]

    if hook:
        lines.append(
            f"Dialogue: 0,{_fmt_time(0)},{_fmt_time(2.5)},Hook,,0,0,0,,{_escape(hook)}"
        )

    for seg in transcript.segments:
        # Klip aralığıyla kesişmeyen segmentleri atla
        if seg.end < clip_start or seg.start > clip_end:
            continue
        start_rel = max(0.0, seg.start - clip_start)
        end_rel = min(clip_end - clip_start, seg.end - clip_start)
        if end_rel <= start_rel:
            continue
        text = _escape(seg.text)
        if not text:
            continue
        lines.append(
            f"Dialogue: 0,{_fmt_time(start_rel)},{_fmt_time(end_rel)},Caption,,0,0,0,,{text}"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
