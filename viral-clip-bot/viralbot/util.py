"""Küçük yardımcılar."""

from __future__ import annotations

from pathlib import Path


def read_text_any(path: Path) -> str:
    """Bir metin dosyasını kodlamadan bağımsız okur (UTF-8, BOM'lu UTF-8, UTF-16 ...).

    Windows Not Defteri dosyayı "Unicode" (UTF-16) kaydettiğinde bile çalışır;
    böylece secrets/*.json dosyaları hangi kodlamada olursa olsun okunabilir.
    """
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")
