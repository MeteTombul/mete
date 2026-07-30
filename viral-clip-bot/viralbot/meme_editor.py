"""Tek bir videoyu analiz edip araya meme/efekt sokan editör.

Akış:
    video (dosya veya link)
      → Whisper ile döküm
      → ses enerjisi + sahne kesimleri
      → Claude sokma noktalarını planlar {time, style, text, sound, duration}
      → ffmpeg: kaynak parçalara bölünür, aralara meme "interstitial"leri eklenir
      → tüm parçalar birleştirilir → düzenlenmiş.mp4

Dışarıdan hiç varlık gerektirmez: donmuş kare + dramatik zoom + iri Türkçe meme
yazısı + sentezlenmiş ses efekti üretir. İsteğe bağlı `MemeLibrary` verilirse
kategoriye uygun görsel ve ses override'ları kullanılır.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import claude_client
from . import moments as moments_mod
from . import scenes as scenes_mod
from .config import RenderOptions
from .effects import _escape_for_filter, _run_ffmpeg, probe_duration, probe_resolution
from .meme_library import MemeLibrary
from .transcribe import Transcript


@dataclass
class MemeInsertion:
    time: float
    style: str          # "freeze" | "zoom" | "funny"
    category: str
    text: str
    sound: str          # "boom" | "ding" | "airhorn" | "whoosh" | "none"
    duration: float
    reason: str = ""


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _has_audio(path: Path) -> bool:
    """Videoda ses akışı olup olmadığını döndürür."""
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path),
        ],
        capture_output=True, text=True,
    )
    return "audio" in proc.stdout


def _scene_hint(cuts: list[float], max_items: int = 40) -> str:
    if not cuts:
        return "(sahne kesimi bulunamadı)"
    shown = cuts[:max_items]
    return ", ".join(f"{c:.1f}" for c in shown)


def _sfx_input(name: str, d: float, library: MemeLibrary | None) -> tuple[list[str], str]:
    """Ses efekti için ffmpeg girdi argümanları + [1:a]'ya uygulanacak filtreyi döndürür."""
    override = library.sound_override(name) if library else None
    if override:
        return (["-i", str(override)], "volume=1")

    if name == "boom":
        return (
            ["-f", "lavfi", "-i", f"sine=frequency=80:duration={d:.3f}"],
            f"lowpass=f=150,volume=5,afade=t=out:st=0.04:d={max(0.05, d - 0.04):.3f}",
        )
    if name == "ding":
        dd = min(d, 0.5)
        return (
            ["-f", "lavfi", "-i", f"sine=frequency=1180:duration={dd:.3f}"],
            f"volume=2.5,afade=t=out:st=0.05:d={max(0.05, dd - 0.05):.3f}",
        )
    if name == "airhorn":
        expr = "0.5*sin(2*PI*233*t)+0.4*sin(2*PI*311*t)+0.3*sin(2*PI*349*t)"
        return (
            ["-f", "lavfi", "-i", f"aevalsrc={expr}:d={d:.3f}:s=48000"],
            f"volume=2.5,afade=t=out:st={max(0.05, d - 0.15):.3f}:d=0.15",
        )
    if name == "whoosh":
        return (
            ["-f", "lavfi", "-i", f"anoisesrc=d={d:.3f}:c=pink:a=0.7"],
            f"highpass=f=250,afade=t=in:st=0:d={d * 0.5:.3f},"
            f"afade=t=out:st={d * 0.5:.3f}:d={d * 0.5:.3f},volume=2.5",
        )
    # none
    return (["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"], "anull")


def _meme_ass(
    text: str, style: str, W: int, H: int, d: float, opts: RenderOptions, ass_path: Path
) -> None:
    """Meme yazısı için tek olaylı ASS dosyası yazar (punch-in animasyonlu)."""
    size = int(H * 0.085)
    # Konum: komik → altta (2), dramatik/zoom → ortada (5)
    align = 2 if style == "funny" else 5
    margin_v = int(H * 0.12) if align == 2 else 0
    # Renk: funny sarı vurgu, diğerleri beyaz
    primary = "&H0000E5FF" if style == "funny" else opts.sub_color
    safe = (
        text.replace("{", "(").replace("}", ")").replace("\\", "")
        .replace("\n", "\\N").strip()
    )
    end_cs = f"0:00:{min(d, 9.99):05.2f}"
    ass_path.write_text(
        f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Meme, {opts.font}, {size}, {primary}, &H00000000, &H90000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, {max(4, int(H * 0.006))}, {max(3, int(H * 0.004))}, {align}, 60, 60, {margin_v}, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{end_cs},Meme,,0,0,0,,{{\\fad(70,70)}}{{\\fscx55\\fscy55}}{{\\t(0,140,\\fscx100\\fscy100)}}{safe}
""",
        encoding="utf-8",
    )


def _render_segment(
    source: Path, start: float, dur: float, W: int, H: int, fps: int,
    src_has_audio: bool, out_path: Path,
) -> None:
    """Kaynağın [start, start+dur] aralığını tek biçimli parametrelerle yeniden kodlar."""
    vf = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[v]"
    )
    cmd = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{dur:.3f}"]
    if src_has_audio:
        fc = vf + ";[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a]"
    else:
        cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        fc = vf + ";[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo[a]"
    cmd += [
        "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-video_track_timescale", "30000",
        str(out_path),
    ]
    _run_ffmpeg(cmd)


def _render_interstitial(
    source: Path, at: float, ins: MemeInsertion, W: int, H: int, fps: int,
    opts: RenderOptions, library: MemeLibrary | None, tmp: Path, out_path: Path,
) -> None:
    """Tek bir meme "araya sokma" parçasını üretir."""
    d = ins.duration
    frame = tmp / f"{out_path.stem}_frame.png"
    _run_ffmpeg([
        "ffmpeg", "-y", "-ss", f"{at:.3f}", "-i", str(source),
        "-frames:v", "1", "-q:v", "2", str(frame),
    ])

    ass_path = tmp / f"{out_path.stem}.ass"
    _meme_ass(ins.text, ins.style, W, H, d, opts, ass_path)
    ass = _escape_for_filter(ass_path)

    # Zoom animasyonu (zoompan) + renk ayarı stile göre.
    # crop ile animasyon yapılamaz (çıkış boyutu sabit olmalı); zoompan kullanılır.
    frames = max(1.0, d * fps)
    if ins.style == "zoom":
        zexpr = "min(zoom+0.020,1.20)"       # ani punch
        eq = "eq=saturation=1.1:contrast=1.15"
    elif ins.style == "funny":
        zexpr = f"min(zoom+{0.06 / frames:.6f},1.06)"  # hafif
        eq = "eq=saturation=1.5:brightness=0.05:contrast=1.05"
    else:  # freeze (dramatik)
        zexpr = f"min(zoom+{0.16 / frames:.6f},1.16)"  # yavaş yaklaşma
        eq = "eq=saturation=0.15:brightness=-0.12:contrast=1.10"

    zoompan = (
        f"zoompan=z='{zexpr}':d=1:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={W}x{H}:fps={fps}"
    )
    base_v = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,{eq},{zoompan}"
    )

    # Ses efekti girdisi (input 1)
    sfx_args, sfx_filter = _sfx_input(ins.sound, d, library)

    # Kütüphaneden görsel eşleşmesi var mı?
    asset = library.match(ins.category) if library else None
    asset_img = asset if (asset and asset.kind == "image") else None

    cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{d:.3f}", "-i", str(frame)]
    cmd += sfx_args  # input 1 = ses

    if asset_img is not None:
        cmd += ["-loop", "1", "-t", f"{d:.3f}", "-i", str(asset_img.path)]  # input 2 = meme görseli
        asset_scale = int(W * 0.72)
        fc = (
            f"[0:v]{base_v},boxblur=luma_radius=18:luma_power=1,eq=brightness=-0.08[bg];"
            f"[2:v]scale={asset_scale}:-1:force_original_aspect_ratio=decrease[mm];"
            f"[bg][mm]overlay=(W-w)/2:(H-h)/2[ov];"
            f"[ov]ass='{ass}',fps={fps},format=yuv420p[v];"
            f"[1:a]{sfx_filter},aresample=48000,apad,atrim=0:{d:.3f}[a]"
        )
    else:
        fc = (
            f"[0:v]{base_v},ass='{ass}',fps={fps},format=yuv420p[v];"
            f"[1:a]{sfx_filter},aresample=48000,apad,atrim=0:{d:.3f}[a]"
        )

    cmd += [
        "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
        "-t", f"{d:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-video_track_timescale", "30000",
        str(out_path),
    ]
    _run_ffmpeg(cmd)
    frame.unlink(missing_ok=True)


def _concat(pieces: list[Path], out_path: Path, tmp: Path) -> None:
    """Parçaları concat demuxer ile birleştirir ve tek geçişte yeniden kodlar."""
    list_file = tmp / "concat_list.txt"
    lines = []
    for p in pieces:
        ap = str(p.resolve()).replace("'", "'\\''")
        lines.append(f"file '{ap}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _run_ffmpeg([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        str(out_path),
    ])
    list_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Ana giriş noktaları
# ---------------------------------------------------------------------------

def edit_video_with_memes(
    source: Path,
    insertions: list[MemeInsertion],
    out_path: Path,
    opts: RenderOptions,
    work: Path,
    library: MemeLibrary | None = None,
    log=print,
) -> Path:
    """Verilen sokma planına göre kaynağı meme'lerle düzenler ve çıktıyı üretir."""
    source = Path(source)
    out_path = Path(out_path)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    duration = probe_duration(source)
    W, H = probe_resolution(source)
    fps = 30
    src_audio = _has_audio(source)

    # Geçerli, sıralı sokmalar (video sınırları içinde)
    ins = [
        i for i in sorted(insertions, key=lambda x: x.time)
        if 0.3 < i.time < duration - 0.2
    ]
    if not ins:
        raise ValueError("Uygulanacak geçerli meme sokma noktası yok.")

    pieces: list[Path] = []
    prev = 0.0
    for idx, item in enumerate(ins):
        t = item.time
        if t - prev > 0.3:  # önceki segment
            seg = work / f"seg_{idx:03d}.mp4"
            _render_segment(source, prev, t - prev, W, H, fps, src_audio, seg)
            pieces.append(seg)
        meme = work / f"meme_{idx:03d}.mp4"
        try:
            _render_interstitial(source, t, item, W, H, fps, opts, library, work, meme)
            pieces.append(meme)
            log(f"  + {t:6.1f}s  [{item.style}/{item.sound}]  “{item.text}”")
        except Exception as e:  # noqa: BLE001
            log(f"  ! {t:6.1f}s meme üretilemedi, atlandı: {e}")
        prev = t

    # Kuyruk segmenti
    if duration - prev > 0.3:
        seg = work / "seg_tail.mp4"
        _render_segment(source, prev, duration - prev, W, H, fps, src_audio, seg)
        pieces.append(seg)

    if not pieces:
        raise RuntimeError("Birleştirilecek parça üretilemedi.")

    log(f"  {len(pieces)} parça birleştiriliyor...")
    _concat(pieces, out_path, work)

    # Ara parçaları temizle
    for p in pieces:
        p.unlink(missing_ok=True)
    return out_path


def analyze_and_edit(
    source: Path,
    out_path: Path,
    opts: RenderOptions,
    work: Path,
    whisper_model: str = "small",
    whisper_device: str = "cpu",
    max_inserts: int = 8,
    use_scenes: bool = True,
    library_dir: Path | str | None = None,
    transcript: Transcript | None = None,
    log=print,
) -> dict:
    """Uçtan uca: videoyu analiz edip meme'lerle düzenlenmiş çıktı üretir.

    Döndürür: {"output": <yol>, "insertions": [...]} özet sözlüğü.
    """
    from . import transcribe as transcribe_mod

    source = Path(source)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)

    library = MemeLibrary.load(library_dir)
    if library and not library.is_empty():
        log(f"Meme kütüphanesi yüklendi: {len(library.assets)} görsel, "
            f"{len(library.sounds)} ses override.")

    duration = probe_duration(source)

    if transcript is None:
        log("Video altyazıya çevriliyor (Whisper, dil otomatik)...")
        transcript = transcribe_mod.transcribe(
            source, model_size=whisper_model, device=whisper_device, language=None
        )
        log(f"Algılanan dil: {transcript.language}")

    log("Ses enerjisi çıkarılıyor...")
    energies = moments_mod._extract_audio_energy(source, work)
    energy_hint = moments_mod._energy_hint(energies)

    cuts: list[float] = []
    if use_scenes:
        log("Sahne kesimleri tespit ediliyor...")
        cuts = scenes_mod.detect_scene_cuts(source)
    scene_hint = _scene_hint(cuts)

    lines = moments_mod._transcript_lines(transcript)

    log("Meme/efekt sokma noktaları Claude ile planlanıyor...")
    plan = claude_client.plan_meme_insertions(
        transcript_lines=lines,
        energy_hint=energy_hint,
        scene_hint=scene_hint,
        video_duration=duration,
        max_inserts=max_inserts,
        library_tags=library.tags_summary() if library else "",
    )
    if not plan:
        raise RuntimeError("Claude uygun meme sokma noktası bulamadı.")
    log(f"{len(plan)} sokma noktası planlandı.")

    insertions = [
        MemeInsertion(
            time=float(p["time"]),
            style=p.get("style", "freeze"),
            category=p.get("category", ""),
            text=p.get("text", ""),
            sound=p.get("sound", "none"),
            duration=float(p.get("duration", 1.4)),
            reason=p.get("reason", ""),
        )
        for p in plan
    ]

    log("Meme'ler videoya işleniyor (ffmpeg)...")
    edit_video_with_memes(
        source, insertions, out_path, opts, work, library=library, log=log
    )
    log(f"Bitti → {out_path}")

    return {
        "output": str(out_path),
        "duration": round(duration, 2),
        "insertions": [
            {
                "time": round(i.time, 2), "style": i.style, "category": i.category,
                "text": i.text, "sound": i.sound, "duration": round(i.duration, 2),
                "reason": i.reason,
            }
            for i in insertions
        ],
    }
