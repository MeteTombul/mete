"""Anthropic Claude ile 'viral an' analizi ve altyazı düzenleme.

Resmi Anthropic Python SDK'sı kullanılır. Model varsayılanı en yetenekli
güncel model olan claude-opus-5'tir; adaptif düşünme (adaptive thinking) açıktır.
"""

from __future__ import annotations

import json
import os

import anthropic

MODEL = "claude-opus-5"


def _client() -> anthropic.Anthropic:
    # API anahtarı ortamdan (ANTHROPIC_API_KEY) veya `ant auth login` profilinden çözülür.
    return anthropic.Anthropic()


# En çarpıcı anları seçtirmek için Claude'dan istenen çıktının JSON şeması
MOMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "moments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number", "description": "Klip başlangıcı (saniye)"},
                    "end": {"type": "number", "description": "Klip bitişi (saniye)"},
                    "title": {
                        "type": "string",
                        "description": "Kısa, dikkat çekici Türkçe başlık (Shorts kapağı için)",
                    },
                    "hook": {
                        "type": "string",
                        "description": "İlk 2 saniyede ekrana basılacak merak uyandıran Türkçe cümle",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Bu anın neden viral olabileceğinin kısa Türkçe açıklaması",
                    },
                    "score": {
                        "type": "number",
                        "description": "0-100 arası viral potansiyeli puanı",
                    },
                },
                "required": ["start", "end", "title", "hook", "reason", "score"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["moments"],
    "additionalProperties": False,
}


def find_viral_moments(
    transcript_lines: str,
    energy_hint: str,
    video_duration: float,
    max_moments: int = 3,
    clip_min: int = 15,
    clip_max: int = 60,
) -> list[dict]:
    """Zaman damgalı transkript + ses enerjisi ipucundan viral anları seçer.

    Dönen her öğe: {start, end, title, hook, reason, score}
    """
    client = _client()

    system = (
        "Sen kısa video (YouTube Shorts / Reels / TikTok) editörüsün. "
        "Uzun bir videonun zaman damgalı dökümünü ve saniye bazlı ses enerjisi "
        "ipuçlarını alıp, dikey kısa klip olarak paylaşıldığında en çok izlenecek, "
        "en 'viral' olabilecek anları seçersin. "
        "İyi bir an: net bir başlangıcı ve bitişi olan, ilk saniyede merak uyandıran, "
        "duygusal tepki (şaşkınlık, kahkaha, gerilim, çarpıcı bilgi) barındıran bölümdür. "
        f"Her klip {clip_min}-{clip_max} saniye arası olmalı. Cümle ortasından kesme. "
        "Başlık ve hook metinleri kısa, tıklatıcı ve Türkçe olmalı."
    )

    user = (
        f"Video süresi: {video_duration:.0f} saniye.\n\n"
        f"En fazla {max_moments} adet viral an seç ve puanına göre sırala.\n\n"
        "=== ZAMAN DAMGALI DÖKÜM ===\n"
        f"{transcript_lines}\n\n"
        "=== SANİYE BAZLI SES ENERJİSİ (yüksek = coşku/gürültü/vurgu olabilir) ===\n"
        f"{energy_hint}\n"
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={
            "format": {"type": "json_schema", "schema": MOMENTS_SCHEMA}
        },
    )

    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    data = json.loads(text)
    moments = data.get("moments", [])

    # Süre sınırlarına ve video sınırlarına göre güvenli hale getir
    cleaned: list[dict] = []
    for m in moments:
        start = max(0.0, float(m["start"]))
        end = min(video_duration, float(m["end"]))
        if end - start < 3:  # anlamsız kısa klipleri ele
            continue
        if end - start > clip_max + 15:
            end = start + clip_max
        cleaned.append({**m, "start": start, "end": end})

    cleaned.sort(key=lambda m: m.get("score", 0), reverse=True)
    return cleaned[:max_moments]
