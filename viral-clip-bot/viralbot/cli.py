"""Komut satırı arayüzü."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import RenderOptions
from .pipeline import run


def _check_dependencies() -> list[str]:
    problems = []
    if shutil.which("ffmpeg") is None:
        problems.append("ffmpeg bulunamadı (sistem PATH'inde olmalı).")
    if shutil.which("ffprobe") is None:
        problems.append("ffprobe bulunamadı (ffmpeg ile birlikte gelir).")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        problems.append(
            "ANTHROPIC_API_KEY tanımlı değil (.env dosyasına ekleyin veya export edin)."
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    p = argparse.ArgumentParser(
        prog="viralbot",
        description="Bir YouTube kanalının en çok izlenen videolarındaki viral anları "
        "bulur, Türkçe altyazı/karaoke ekler ve baş/son efektli dikey (Shorts) klipler "
        "+ kapak + SEO metası üretir.",
    )
    p.add_argument("channel_url", help="Kanal URL'si (ör. https://www.youtube.com/@kanaladi)")
    p.add_argument("-o", "--out", default="cikti", help="Çıktı klasörü (vars. cikti)")
    p.add_argument("--videos", type=int, default=3, help="İşlenecek video sayısı (vars. 3)")
    p.add_argument("--moments", type=int, default=3, help="Video başına klip sayısı (vars. 3)")
    p.add_argument("--clip-min", type=int, default=15, help="Klip alt süre, sn (vars. 15)")
    p.add_argument("--clip-max", type=int, default=60, help="Klip üst süre, sn (vars. 60)")
    p.add_argument("--workers", type=int, default=1, help="Paralel video işleme sayısı (vars. 1)")
    p.add_argument(
        "--whisper-model", default=os.environ.get("WHISPER_MODEL", "small"),
        help="Whisper modeli: tiny/base/small/medium/large-v3 (vars. small)",
    )
    p.add_argument(
        "--whisper-device", default=os.environ.get("WHISPER_DEVICE", "cpu"),
        help="cpu veya cuda (vars. cpu)",
    )

    # Biçim ve efekt seçenekleri
    p.add_argument("--aspect", default="9:16", choices=["9:16", "1:1", "16:9"],
                   help="Çıktı formatı (vars. 9:16)")
    p.add_argument("--no-karaoke", action="store_true", help="Kelime kelime karaoke altyazıyı kapat")
    p.add_argument("--no-scenes", action="store_true", help="Sahne kesimi hizalamayı kapat")
    p.add_argument("--no-progress-bar", action="store_true", help="İlerleme çubuğunu kapat")
    p.add_argument("--no-loudnorm", action="store_true", help="Ses normalizasyonunu kapat")
    p.add_argument("--no-thumbnail", action="store_true", help="Kapak üretimini kapat")
    p.add_argument("--no-srt", action="store_true", help="SRT dışa aktarımını kapat")
    p.add_argument("--no-metadata", action="store_true", help="SEO metası üretimini kapat")
    p.add_argument("--logo", type=Path, default=None, help="Köşeye bindirilecek logo (png)")
    p.add_argument("--music", type=Path, default=None, help="Arka plan müziği (mp3/m4a)")
    p.add_argument("--music-volume", type=float, default=0.12, help="Fon müziği ses oranı 0-1 (vars. 0.12)")
    p.add_argument("--sub-color", default="&H00FFFFFF", help="Altyazı rengi (ASS BGR, vars. beyaz)")
    p.add_argument("--highlight-color", default="&H0000E5FF", help="Vurgu rengi (ASS BGR, vars. turuncu)")
    p.add_argument("--font", default="Arial", help="Altyazı fontu (vars. Arial)")

    args = p.parse_args(argv)

    problems = _check_dependencies()
    if problems:
        print("Eksik gereksinimler:", file=sys.stderr)
        for pb in problems:
            print(f"  - {pb}", file=sys.stderr)
        return 1

    opts = RenderOptions(
        aspect=args.aspect,
        karaoke=not args.no_karaoke,
        progress_bar=not args.no_progress_bar,
        loudnorm=not args.no_loudnorm,
        make_thumbnail=not args.no_thumbnail,
        make_srt=not args.no_srt,
        make_metadata=not args.no_metadata,
        logo=args.logo,
        music=args.music,
        music_volume=args.music_volume,
        sub_color=args.sub_color,
        highlight_color=args.highlight_color,
        font=args.font,
    )

    try:
        run(
            channel_url=args.channel_url,
            out_dir=Path(args.out),
            opts=opts,
            top_videos=args.videos,
            moments_per_video=args.moments,
            whisper_model=args.whisper_model,
            whisper_device=args.whisper_device,
            clip_min=args.clip_min,
            clip_max=args.clip_max,
            use_scenes=not args.no_scenes,
            workers=args.workers,
        )
    except KeyboardInterrupt:
        print("\nİptal edildi.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
