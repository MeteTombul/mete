"""Sahne değişimi tespiti (ffmpeg) ve klip sınırlarını sahnelere hizalama."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def detect_scene_cuts(video_path: Path, threshold: float = 0.4) -> list[float]:
    """Videodaki sahne değişimi zamanlarını (saniye) döndürür.

    ffmpeg'in `select='gt(scene,threshold)'` filtresi + showinfo çıktısı kullanılır.
    """
    proc = subprocess.run(
        [
            "ffmpeg", "-i", str(video_path),
            "-filter_complex", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    # showinfo satırları stderr'e yazılır: "... pts_time:12.345 ..."
    times: list[float] = []
    for m in re.finditer(r"pts_time:([0-9.]+)", proc.stderr):
        try:
            times.append(float(m.group(1)))
        except ValueError:
            continue
    return sorted(set(times))


def snap_to_scene(
    start: float,
    end: float,
    cuts: list[float],
    max_shift: float = 1.5,
) -> tuple[float, float]:
    """Klip başlangıç/bitişini yakın bir sahne kesimine kaydırır (max_shift sn içinde).

    Böylece klip cümle/sahne ortasından değil, doğal bir kesimden başlar/biter.
    """
    if not cuts:
        return start, end

    def nearest(t: float) -> float:
        best = t
        best_d = max_shift
        for c in cuts:
            d = abs(c - t)
            if d <= best_d:
                best, best_d = c, d
        return best

    new_start = nearest(start)
    new_end = nearest(end)
    if new_end - new_start < 3:  # aşırı kısalmayı engelle
        return start, end
    return new_start, new_end
