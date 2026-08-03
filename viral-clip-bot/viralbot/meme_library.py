"""Kullanıcının kendi meme varlıklarını (görsel/gif/klip + ses efektleri) yöneten kütüphane.

Kütüphane opsiyoneldir: hiç varlık verilmese de meme editör çalışır (donmuş kare +
efekt + Claude'un yazdığı meme metni). Kütüphane verilirse, Claude'un seçtiği
`category` etiketine göre en uygun görsel/klip/ses eşleştirilir.

Klasör yapısı (hepsi opsiyonel):
    <lib>/
        gorseller/   *.jpg *.png *.gif   → araya sokulacak meme görselleri/klipleri
        sesler/      boom.* ding.* airhorn.* whoosh.*  → ses efekti override'ları
        manifest.json  (opsiyonel) → { "dosya.png": ["sok", "wow"] }

Etiket çıkarımı: manifest.json yoksa etiketler dosya adından türetilir
(ör. `sok_wow_yuz.png` → ["sok", "wow", "yuz"]).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
_SOUND_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}

# Claude'un ürettiği ses adları için standart set
_SOUND_NAMES = {"boom", "ding", "airhorn", "whoosh"}


@dataclass
class MemeAsset:
    path: Path
    tags: list[str]
    kind: str  # "image" | "clip"


@dataclass
class MemeLibrary:
    root: Path | None = None
    assets: list[MemeAsset] = field(default_factory=list)
    sounds: dict[str, Path] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str | None) -> "MemeLibrary":
        if not root:
            return cls()
        root = Path(root)
        if not root.exists():
            return cls(root=root)

        manifest: dict[str, list[str]] = {}
        mpath = root / "manifest.json"
        if mpath.exists():
            try:
                manifest = json.loads(mpath.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                manifest = {}

        assets: list[MemeAsset] = []
        img_dir = root / "gorseller"
        search_dirs = [d for d in (img_dir, root) if d.exists()]
        seen: set[Path] = set()
        for d in search_dirs:
            for p in sorted(d.iterdir()):
                if p in seen or not p.is_file():
                    continue
                ext = p.suffix.lower()
                if ext in _IMAGE_EXT:
                    kind = "image"
                elif ext in _VIDEO_EXT:
                    kind = "clip"
                else:
                    continue
                seen.add(p)
                tags = manifest.get(p.name) or _tags_from_name(p.stem)
                assets.append(MemeAsset(path=p, tags=tags, kind=kind))

        sounds: dict[str, Path] = {}
        snd_dir = root / "sesler"
        if snd_dir.exists():
            for p in snd_dir.iterdir():
                if p.is_file() and p.suffix.lower() in _SOUND_EXT:
                    name = p.stem.lower()
                    if name in _SOUND_NAMES:
                        sounds[name] = p

        return cls(root=root, assets=assets, sounds=sounds)

    def is_empty(self) -> bool:
        return not self.assets and not self.sounds

    def tags_summary(self) -> str:
        """Claude'a verilecek, kullanılabilir kategori etiketlerinin özeti."""
        if not self.assets:
            return ""
        all_tags: list[str] = []
        for a in self.assets:
            for t in a.tags:
                if t not in all_tags:
                    all_tags.append(t)
        return ", ".join(all_tags)

    def match(self, category: str) -> MemeAsset | None:
        """Bir kategoriye en uygun meme varlığını döndürür (yoksa None).

        Basit puanlama: etiket tam eşleşmesi > içeren eşleşme. Deterministik
        olması için ilk en yüksek puanlı varlık seçilir.
        """
        if not self.assets or not category:
            return None
        cat = _norm(category)
        best: MemeAsset | None = None
        best_score = 0
        for a in self.assets:
            score = 0
            for t in a.tags:
                nt = _norm(t)
                if nt == cat:
                    score = max(score, 3)
                elif nt and (nt in cat or cat in nt):
                    score = max(score, 2)
            if score > best_score:
                best, best_score = a, score
        return best

    def sound_override(self, name: str) -> Path | None:
        return self.sounds.get((name or "").lower())


def _tags_from_name(stem: str) -> list[str]:
    parts = re.split(r"[\s_\-.]+", stem.lower())
    return [p for p in parts if p]


def _norm(s: str) -> str:
    s = s.lower().strip()
    # Türkçe karakterleri sadeleştir (eşleştirme toleransı için)
    table = str.maketrans("çğıöşü", "cgiosu")
    return s.translate(table)
