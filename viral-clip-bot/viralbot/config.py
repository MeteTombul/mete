"""Render ve işleme ayarları için merkezi yapılandırma nesnesi."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RenderOptions:
    # Biçim
    aspect: str = "9:16"          # "9:16" | "1:1" | "16:9"
    fade: float = 0.5             # baş/son fade süresi (sn)

    # Altyazı
    karaoke: bool = True          # kelime kelime vurgulu altyazı
    sub_color: str = "&H00FFFFFF"  # ASS BGR: beyaz
    highlight_color: str = "&H0000E5FF"  # ASS BGR: turuncu/altın vurgu
    font: str = "Arial"

    # Efektler
    progress_bar: bool = True     # altta ilerleme çubuğu
    loudnorm: bool = True         # ses seviyesi normalizasyonu
    logo: Path | None = None      # köşeye bindirilecek logo (png)
    music: Path | None = None     # arka plan müziği (mp3/m4a)
    music_volume: float = 0.12    # fon müziği ses oranı (0-1)

    # Ek çıktılar
    make_thumbnail: bool = True   # kapak görseli üret
    make_srt: bool = True         # .srt altyazı dışa aktar
    make_metadata: bool = True    # Claude ile SEO başlık/açıklama/hashtag

    def resolution(self) -> tuple[int, int]:
        return {
            "9:16": (1080, 1920),
            "1:1": (1080, 1080),
            "16:9": (1920, 1080),
        }.get(self.aspect, (1080, 1920))
