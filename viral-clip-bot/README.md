# 🎬 Viral Clip Bot

Bir YouTube kanalının **en çok izlenen** videolarını tarar, her videodaki **viral olabilecek anları** yapay zekâ ile bulur, o anlardan **dikey (9:16 Shorts/Reels) klipler** keser, üzerine **Türkçe altyazı** basar ve klibin **başına/sonuna efekt** ekler.

Ekstra olarak: **karaoke altyazı** (kelime kelime vurgu), **sahne kesimine hizalama**, **kapak görseli**, **SEO başlık/açıklama/hashtag**, **ilerleme çubuğu**, **ses normalizasyonu**, **logo/watermark**, **arka plan müziği** (ducking'li), **format seçeneği** (9:16 / 1:1 / 16:9), **SRT dışa aktarımı** ve **paralel işleme**.

> Yalnızca **izinli / telifsiz / kendi** içeriğiniz üzerinde kullanın. Başkasının içeriğini izinsiz indirmek ve yeniden yayınlamak YouTube kurallarına ve telif hakkına aykırı olabilir.

## Nasıl çalışır?

```
Kanal URL'si
   │
   ├─ 1) yt-dlp ile videolar taranır → izlenmeye göre ilk N video
   ├─ 2) Seçilen videolar indirilir
   ├─ 3) faster-whisper ile konuşma Türkçe altyazıya çevrilir (zaman damgalı)
   ├─ 4) Claude (claude-opus-5) transkript + ses enerjisini analiz edip
   │      en çarpıcı/viral anları seçer (başlık, hook ve puanla birlikte)
   └─ 5) ffmpeg her an için dikey klip üretir:
          bulanık arka plan + ortalanmış video + gömülü altyazı
          + baş/son fade efekti + üstte "hook" metni
```

Çıktı: `cikti/klipler/*.mp4` ve tüm klipleri özetleyen `cikti/ozet.json`.

## Kurulum

Gereksinimler: **Python 3.10+**, **ffmpeg** (ve ffprobe) sistemde kurulu olmalı.

```bash
# ffmpeg (yoksa)
#   macOS:   brew install ffmpeg
#   Ubuntu:  sudo apt install ffmpeg
#   Windows: https://ffmpeg.org/download.html

cd viral-clip-bot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env dosyasına Anthropic API anahtarınızı yazın
```

## Kullanım

```bash
python -m viralbot "https://www.youtube.com/@KANAL_ADI"
```

Seçenekler:

```bash
python -m viralbot "https://www.youtube.com/@KANAL" \
  --out cikti \            # çıktı klasörü
  --videos 3 \            # işlenecek en çok izlenen video sayısı
  --moments 3 \           # video başına klip sayısı
  --clip-min 15 \         # klip alt süre (sn)
  --clip-max 60 \         # klip üst süre (sn)
  --workers 2 \           # paralel video işleme
  --whisper-model small \ # tiny/base/small/medium/large-v3
  --whisper-device cpu    # cpu veya cuda (GPU varsa çok daha hızlı)

# Biçim ve efektler
  --aspect 9:16 \         # 9:16 | 1:1 | 16:9
  --logo logo.png \       # köşeye watermark
  --music fon.mp3 \       # arka plan müziği (ducking'li)
  --music-volume 0.12 \
  --sub-color '&H00FFFFFF' \      # altyazı rengi (ASS BGR)
  --highlight-color '&H0000E5FF' \# karaoke vurgu rengi
  --font Arial

# Kapatma anahtarları
  --no-karaoke  --no-scenes  --no-progress-bar \
  --no-loudnorm --no-thumbnail --no-srt --no-metadata
```

## Klip başına üretilen dosyalar

| Dosya | İçerik |
|------|--------|
| `<klip>.mp4` | Altyazılı, efektli dikey klip |
| `<klip>.jpg` | Başlık bindirilmiş kapak görseli |
| `<klip>.srt` | Ayrı altyazı dosyası |
| `<klip>.txt` | Claude'un ürettiği SEO başlık + açıklama + hashtag |
| `ozet.json` | Tüm kliplerin meta verisi (tek dosya) |

## İpuçları

- **Doğruluk vs hız:** Türkçe için altyazı kalitesi `small` modelde iyi, `medium`/`large-v3` daha da iyi ama yavaş. GPU'nuz varsa `--whisper-device cuda` kullanın.
- **Maliyet:** Yalnızca "viral an seçimi" adımı Claude API kullanır (video başına 1 istek). Altyazı ve video işleme tamamen yereldir.
- **API anahtarı:** `ANTHROPIC_API_KEY` ortam değişkeni veya `ant auth login` profili otomatik okunur.

## Modüller

| Dosya | Görev |
|------|------|
| `channel.py` | Kanal videolarını listeler, izlenmeye göre sıralar |
| `download.py` | Videoyu indirir |
| `transcribe.py` | Whisper ile zaman damgalı altyazı |
| `claude_client.py` | Claude ile viral an seçimi + SEO metası (JSON şemalı) |
| `moments.py` | Ses enerjisi ölçümü + Claude analizini birleştirir |
| `scenes.py` | Sahne değişimi tespiti ve klip sınırlarını hizalama |
| `subtitles.py` | Karaoke/düz ASS altyazı + SRT dışa aktarımı |
| `effects.py` | ffmpeg: kesme, format, efekt, altyazı gömme, kapak |
| `config.py` | Render seçenekleri (biçim, tema, efekt anahtarları) |
| `pipeline.py` | Uçtan uca akış (paralel işleme) |
| `cli.py` | Komut satırı arayüzü |
