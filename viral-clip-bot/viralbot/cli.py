"""Komut satırı arayüzü."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

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

    parser = argparse.ArgumentParser(
        prog="viralbot",
        description="Bir YouTube kanalının en çok izlenen videolarındaki viral anları "
        "bulur, Türkçe altyazı ekler ve başına/sonuna efektli dikey (Shorts) klipler üretir.",
    )
    parser.add_argument("channel_url", help="Kanal URL'si (ör. https://www.youtube.com/@kanaladi)")
    parser.add_argument(
        "-o", "--out", default="cikti", help="Çıktı klasörü (varsayılan: cikti)"
    )
    parser.add_argument(
        "--videos", type=int, default=3, help="İşlenecek en çok izlenen video sayısı (vars. 3)"
    )
    parser.add_argument(
        "--moments", type=int, default=3, help="Video başına klip sayısı (vars. 3)"
    )
    parser.add_argument(
        "--clip-min", type=int, default=15, help="Klip alt süre sınırı, saniye (vars. 15)"
    )
    parser.add_argument(
        "--clip-max", type=int, default=60, help="Klip üst süre sınırı, saniye (vars. 60)"
    )
    parser.add_argument(
        "--whisper-model",
        default=os.environ.get("WHISPER_MODEL", "small"),
        help="Whisper model boyutu: tiny/base/small/medium/large-v3 (vars. small)",
    )
    parser.add_argument(
        "--whisper-device",
        default=os.environ.get("WHISPER_DEVICE", "cpu"),
        help="cpu veya cuda (vars. cpu)",
    )

    args = parser.parse_args(argv)

    problems = _check_dependencies()
    if problems:
        print("Eksik gereksinimler:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    try:
        run(
            channel_url=args.channel_url,
            out_dir=Path(args.out),
            top_videos=args.videos,
            moments_per_video=args.moments,
            whisper_model=args.whisper_model,
            whisper_device=args.whisper_device,
            clip_min=args.clip_min,
            clip_max=args.clip_max,
        )
    except KeyboardInterrupt:
        print("\nİptal edildi.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
