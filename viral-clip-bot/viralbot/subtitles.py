"""Klibe gömülecek stilli Türkçe altyazı (ASS) + karaoke vurgusu + SRT dışa aktarımı."""

from __future__ import annotations

from pathlib import Path

from .config import RenderOptions
from .transcribe import Transcript, Word


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


def _fmt_srt_time(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _escape(text: str) -> str:
    return text.replace("\n", " ").replace("{", "(").replace("}", ")").strip()


def _header(opts: RenderOptions) -> str:
    w, h = opts.resolution()
    # Punto ve alt boşluk çözünürlüğe göre ölçeklenir
    cap_size = int(h * 0.036)
    hook_size = int(h * 0.041)
    margin_v = int(h * 0.18)
    hook_margin_v = int(h * 0.135)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption, {opts.font}, {cap_size}, {opts.sub_color}, &H000000FF, &H00000000, &H64000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 5, 2, 2, 60, 60, {margin_v}, 1
Style: Hook, {opts.font}, {hook_size}, {opts.highlight_color}, &H000000FF, &H00000000, &H96000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 6, 3, 8, 80, 80, {hook_margin_v}, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _dialogue(start: float, end: float, style: str, text: str) -> str:
    return f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},{style},,0,0,0,,{text}"


def _chunk_words(words: list[Word], size: int = 4) -> list[list[Word]]:
    return [words[i : i + size] for i in range(0, len(words), size)]


def build_ass(
    transcript: Transcript,
    clip_start: float,
    clip_end: float,
    out_path: Path,
    opts: RenderOptions,
    hook: str | None = None,
) -> Path:
    """Klip aralığındaki altyazıyı ASS olarak yazar. Karaoke açıksa kelime kelime vurgular."""
    lines = [_header(opts)]

    if hook:
        lines.append(_dialogue(0.0, 2.5, "Hook", _escape(hook)))

    for seg in transcript.segments:
        if seg.end < clip_start or seg.start > clip_end:
            continue

        if opts.karaoke and seg.words:
            for chunk in _chunk_words(seg.words, size=4):
                for k, active in enumerate(chunk):
                    a_start = max(0.0, active.start - clip_start)
                    a_end = min(clip_end - clip_start, active.end - clip_start)
                    if a_end <= a_start:
                        continue
                    parts = []
                    for idx, w in enumerate(chunk):
                        token = _escape(w.text)
                        if idx == k:
                            parts.append(
                                f"{{\\c{opts.highlight_color}\\fscx112\\fscy112}}{token}{{\\r}}"
                            )
                        else:
                            parts.append(token)
                    text = " ".join(parts)
                    lines.append(_dialogue(a_start, a_end, "Caption", text))
        else:
            start_rel = max(0.0, seg.start - clip_start)
            end_rel = min(clip_end - clip_start, seg.end - clip_start)
            text = _escape(seg.text)
            if end_rel > start_rel and text:
                lines.append(_dialogue(start_rel, end_rel, "Caption", text))

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def export_srt(
    transcript: Transcript,
    clip_start: float,
    clip_end: float,
    out_path: Path,
) -> Path:
    """Klip aralığındaki altyazıyı klibe göreli zamanlarla .srt olarak dışa aktarır."""
    blocks = []
    n = 1
    for seg in transcript.segments:
        if seg.end < clip_start or seg.start > clip_end:
            continue
        start_rel = max(0.0, seg.start - clip_start)
        end_rel = min(clip_end - clip_start, seg.end - clip_start)
        text = seg.text.strip()
        if end_rel <= start_rel or not text:
            continue
        blocks.append(
            f"{n}\n{_fmt_srt_time(start_rel)} --> {_fmt_srt_time(end_rel)}\n{text}\n"
        )
        n += 1
    out_path.write_text("\n".join(blocks), encoding="utf-8")
    return out_path
