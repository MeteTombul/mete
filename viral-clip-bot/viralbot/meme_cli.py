"""Meme editör komut satırı arayüzü.

Kullanım:
    python -m viralbot.meme_cli video.mp4
    python -m viralbot.meme_cli video.mp4 -o cikti/meme_video.mp4 --max 10
    python -m viralbot.meme_cli "https://www.youtube.com/watch?v=..." --library memelerim/

Tek bir videoyu (yerel dosya VEYA link) analiz eder ve araya meme/efekt ekler.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import channel as channel_mod
from . import download as download_mod
from .config import RenderOptions
from .meme_editor import analyze_and_edit


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
        prog="viralbot-meme",
        description="Bir videoyu analiz edip araya otomatik meme ve efekt ekler "
        "(donmuş kare + zoom + Türkçe meme yazısı + ses efekti). Dışarıdan meme "
        "dosyası gerektirmez; istenirse kendi meme kütüphanen de kullanılır.",
    )
    p.add_argument(
        "source", metavar="VIDEO",
        help="Yerel video dosyası yolu VEYA bir video linki (YouTube/TikTok/Instagram).",
    )
    p.add_argument(
        "-o", "--out", default=None,
        help="Çıktı dosyası (vars. <kaynak>_meme.mp4)",
    )
    p.add_argument(
        "--max", type=int, default=8, dest="max_inserts",
        help="En fazla kaç meme/efekt sokulsun (vars. 8)",
    )
    p.add_argument(
        "--library", type=Path, default=None,
        help="Kendi meme kütüphanen (görsel/gif + ses efekti klasörü). Opsiyonel.",
    )
    p.add_argument(
        "--no-scenes", action="store_true",
        help="Sahne kesimi analizini kapat (biraz daha hızlı).",
    )
    p.add_argument(
        "--font", default="Arial", help="Meme yazısı fontu (vars. Arial)",
    )
    p.add_argument(
        "--whisper-model", default=os.environ.get("WHISPER_MODEL", "small"),
        help="Whisper modeli: tiny/base/small/medium/large-v3 (vars. small)",
    )
    p.add_argument(
        "--whisper-device", default=os.environ.get("WHISPER_DEVICE", "cpu"),
        help="cpu veya cuda (vars. cpu)",
    )
    p.add_argument(
        "--work", type=Path, default=None,
        help="Geçici çalışma klasörü (vars. <çıktı klasörü>/_meme_work)",
    )

    args = p.parse_args(argv)

    problems = _check_dependencies()
    if problems:
        print("Eksik gereksinimler:", file=sys.stderr)
        for pb in problems:
            print(f"  - {pb}", file=sys.stderr)
        return 1

    # Kaynağı çöz: yerel dosya mı, link mi?
    src_arg = args.source
    local = Path(src_arg)
    if local.exists():
        source = local
    elif channel_mod.is_video_url(src_arg):
        dl_dir = (args.work or Path("cikti") / "_meme_work") / "indirilen"
        print("Link algılandı — video indiriliyor...")
        source = download_mod.download_video(src_arg, dl_dir)
        print(f"İndirildi: {source}")
    else:
        print(
            f"Kaynak bulunamadı: '{src_arg}'. Geçerli bir dosya yolu ya da "
            "video linki verin.",
            file=sys.stderr,
        )
        return 1

    out_path = (
        Path(args.out)
        if args.out
        else source.with_name(source.stem + "_meme.mp4")
    )
    work = args.work or (out_path.parent / "_meme_work")

    opts = RenderOptions(font=args.font)

    try:
        summary = analyze_and_edit(
            source=source,
            out_path=out_path,
            opts=opts,
            work=work,
            whisper_model=args.whisper_model,
            whisper_device=args.whisper_device,
            max_inserts=args.max_inserts,
            use_scenes=not args.no_scenes,
            library_dir=args.library,
            log=print,
        )
    except KeyboardInterrupt:
        print("\nİptal edildi.", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001
        print(f"Hata: {e}", file=sys.stderr)
        return 1

    # Özet JSON'u çıktı yanına yaz
    summary_path = out_path.with_suffix(".meme.json")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✓ Düzenlenmiş video: {out_path}")
    print(f"  Sokulan meme sayısı: {len(summary['insertions'])}")
    print(f"  Özet: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
