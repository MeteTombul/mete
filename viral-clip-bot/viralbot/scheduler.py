"""Otomatik/zamanlanmış üretim: kanalı izleyip yeni videoları otomatik işler.

Belirli aralıklarla kanalın en yeni videolarına bakar; daha önce işlenmemiş
olanları klip üretim akışından geçirir ve (istenirse) otomatik yükler.
İşlenen video kimlikleri bir durum dosyasında tutulur, böylece aynı video
iki kez işlenmez.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import channel as channel_mod
from .config import RenderOptions
from .pipeline import run as run_pipeline


def _state_path(out_dir: Path) -> Path:
    return out_dir / "_islenen.json"


def _load_state(out_dir: Path) -> set[str]:
    p = _state_path(out_dir)
    if p.exists():
        try:
            return set(json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            return set()
    return set()


def _save_state(out_dir: Path, ids: set[str]) -> None:
    _state_path(out_dir).write_text(
        json.dumps(sorted(ids), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def tick(
    channel_url: str,
    out_dir: Path,
    opts: RenderOptions,
    check_count: int = 5,
    log=print,
    **run_kwargs,
) -> list[dict]:
    """Tek bir kontrol turu: yeni videoları bul ve işle. İşlenenlerin metasını döndürür."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    processed = _load_state(out_dir)

    latest = channel_mod.list_latest_videos(channel_url, limit=check_count)
    new = [v for v in latest if v.id not in processed]

    if not new:
        log("Yeni video yok.")
        return []

    log(f"{len(new)} yeni video bulundu, işleniyor...")
    results = run_pipeline(
        channel_url=channel_url,
        out_dir=out_dir,
        opts=opts,
        videos=new,
        log=log,
        **run_kwargs,
    )

    processed.update(v.id for v in new)
    _save_state(out_dir, processed)
    return results


def watch(
    channel_url: str,
    out_dir: Path,
    opts: RenderOptions,
    interval: int = 3600,
    check_count: int = 5,
    seed_existing: bool = True,
    log=print,
    **run_kwargs,
) -> None:
    """Sürekli izleme döngüsü: her `interval` saniyede yeni videoları işler.

    seed_existing=True ise ilk turda mevcut son videolar 'işlenmiş' sayılır,
    yalnızca bundan SONRA gelen yeni yüklemeler işlenir (geçmişi baştan üretmez).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if seed_existing and not _state_path(out_dir).exists():
        log("İlk kurulum: mevcut videolar işaretleniyor (yalnızca yeni yüklemeler işlenecek)...")
        latest = channel_mod.list_latest_videos(channel_url, limit=max(check_count, 30))
        _save_state(out_dir, {v.id for v in latest})

    log(f"İzleme başladı. Her {interval} sn'de bir kontrol edilecek. (Ctrl+C ile durdur)")
    while True:
        try:
            tick(channel_url, out_dir, opts, check_count=check_count, log=log, **run_kwargs)
        except Exception as e:  # noqa: BLE001
            log(f"Tur hatası (yok sayılıp devam edilecek): {e}")
        time.sleep(interval)
