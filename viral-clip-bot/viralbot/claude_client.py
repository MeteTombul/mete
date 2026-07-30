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


META_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Tıklatıcı, <=70 karakter Türkçe başlık"},
        "description": {
            "type": "string",
            "description": "2-3 cümlelik Türkçe açıklama (Shorts açıklaması için)",
        },
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "5-8 adet ilgili hashtag (# ile)",
        },
    },
    "required": ["title", "description", "hashtags"],
    "additionalProperties": False,
}


def generate_metadata(clip_transcript: str, moment_title: str) -> dict:
    """Bir klibin metni için SEO başlık/açıklama/hashtag üretir."""
    client = _client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=(
            "Sen bir sosyal medya editörüsün. Verilen kısa klip metnine göre "
            "YouTube Shorts / TikTok için Türkçe başlık, açıklama ve hashtag üret. "
            "Başlık merak uyandırsın, clickbait'e kaçmadan çarpıcı olsun."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Klip ana teması: {moment_title}\n\n"
                    f"Klip metni:\n{clip_transcript}\n\n"
                    "Bu klip için başlık, açıklama ve hashtag üret."
                ),
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": META_SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)


_LANG_NAMES = {"tr": "Türkçe", "en": "İngilizce"}


def translate_segments(texts: list[str], target: str) -> list[str]:
    """Altyazı segmentlerini hedef dile çevirir (sıra ve sayı korunur).

    target: "tr" (Türkçe) veya "en" (İngilizce).
    """
    if not texts:
        return []
    lang_name = _LANG_NAMES.get(target, target)
    client = _client()

    schema = {
        "type": "object",
        "properties": {
            "translations": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["translations"],
        "additionalProperties": False,
    }
    numbered = "\n".join(f"{i}\t{t}" for i, t in enumerate(texts))
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=(
            f"Sen bir altyazı çevirmenisin. Sana numaralı altyazı satırları verilecek. "
            f"Her satırı {lang_name} diline, doğal ve akıcı biçimde çevir. "
            "Satır sayısını ve sırasını KORU; her giriş için tam bir çeviri döndür. "
            "Konuşma dilini koru, aşırı resmileştirme."
        ),
        messages=[{"role": "user", "content": numbered}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    data = json.loads(next((b.text for b in resp.content if b.type == "text"), "{}"))
    out = data.get("translations", [])
    # Güvenlik: sayı uyuşmazsa orijinali koru/tamamla
    if len(out) < len(texts):
        out = out + texts[len(out):]
    return out[: len(texts)]


# --- Meme editör: araya meme/efekt sokma noktalarını Claude ile planla ---

MEME_INSERT_SCHEMA = {
    "type": "object",
    "properties": {
        "insertions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "number",
                        "description": "Meme'in videoya sokulacağı an (saniye). "
                        "Bir cümlenin/vurgunun hemen BİTİMİNE denk gelmeli.",
                    },
                    "style": {
                        "type": "string",
                        "enum": ["freeze", "zoom", "funny"],
                        "description": "freeze: dramatik donmuş kare (gerilim/şaşkınlık). "
                        "zoom: ani zoom-punch (vurgu). funny: parlak komik pop.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Meme'in duygusu/kategorisi (kütüphane eşleştirmesi için): "
                        "ör. sok, kahkaha, dusun, sus, alkis, hayir, wow.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Ekrana basılacak KISA, iri, tümü BÜYÜK HARF Türkçe meme "
                        "yazısı (en fazla 4-5 kelime). Emoji kullanma.",
                    },
                    "sound": {
                        "type": "string",
                        "enum": ["boom", "ding", "airhorn", "whoosh", "none"],
                        "description": "Meme anında çalacak ses efekti.",
                    },
                    "duration": {
                        "type": "number",
                        "description": "Meme'in ekranda kalacağı süre (saniye, 0.8-2.5 arası).",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Bu ana neden meme konduğunun kısa Türkçe açıklaması.",
                    },
                },
                "required": ["time", "style", "category", "text", "sound", "duration", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["insertions"],
    "additionalProperties": False,
}


def plan_meme_insertions(
    transcript_lines: str,
    energy_hint: str,
    scene_hint: str,
    video_duration: float,
    max_inserts: int = 8,
    library_tags: str = "",
) -> list[dict]:
    """Videonun akışına göre araya meme/efekt sokulacak anları planlar.

    Dönen her öğe: {time, style, category, text, sound, duration, reason}
    """
    client = _client()

    system = (
        "Sen TikTok/YouTube/Instagram tarzı komik 'meme edit' yapan bir video editörüsün. "
        "Sana uzun bir videonun zaman damgalı dökümü, saniye bazlı ses enerjisi ve sahne "
        "kesimleri verilir. Görevin: izleyiciyi güldürecek/şaşırtacak şekilde videonun "
        "AKIŞINI BOZMADAN, uygun anların hemen ardına kısa meme/efekt sokmak.\n"
        "İyi bir sokma anı: bir cümlenin çarpıcı bitişi, komik/absürt bir ifade, ani sessizlik, "
        "şaşırtıcı bilgi, gerilim ya da 'kayıt durur' türü anlardır.\n"
        "Kurallar: meme'leri anların BİTİMİNE koy (cümle ortasına değil). Aynı anlara yığma; "
        "sokmalar en az 4-5 saniye aralıklı olsun. Yazılar KISA ve BÜYÜK HARF Türkçe olsun. "
        "Videoyu meme'e boğma — sadece gerçekten güçlü anları seç."
    )

    lib = (
        f"\n=== KULLANILABİLİR MEME KÜTÜPHANE ETİKETLERİ ===\n{library_tags}\n"
        "Uygun olduğunda 'category' alanını bu etiketlere yakın seç.\n"
        if library_tags.strip()
        else ""
    )

    user = (
        f"Video süresi: {video_duration:.0f} saniye.\n\n"
        f"En fazla {max_inserts} adet meme/efekt sokma noktası seç, zamana göre sıralı ver.\n"
        f"{lib}\n"
        "=== ZAMAN DAMGALI DÖKÜM ===\n"
        f"{transcript_lines}\n\n"
        "=== SANİYE BAZLI SES ENERJİSİ (yüksek = coşku/vurgu/gürültü) ===\n"
        f"{energy_hint}\n\n"
        "=== SAHNE KESİMLERİ (saniye) ===\n"
        f"{scene_hint}\n"
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": MEME_INSERT_SCHEMA}},
    )

    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    data = json.loads(text)
    inserts = data.get("insertions", [])

    cleaned: list[dict] = []
    for it in inserts:
        t = max(0.3, min(video_duration - 0.3, float(it["time"])))
        dur = float(it.get("duration", 1.4))
        dur = max(0.6, min(2.5, dur))
        cleaned.append({**it, "time": t, "duration": dur})

    cleaned.sort(key=lambda x: x["time"])

    # Çok yakın sokmaları ele (en az 4 sn aralık)
    spaced: list[dict] = []
    last_t = -999.0
    for it in cleaned:
        if it["time"] - last_t < 4.0:
            continue
        spaced.append(it)
        last_t = it["time"]
    return spaced[:max_inserts]
