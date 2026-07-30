# 🎬 Viral Clip Bot

Bir YouTube kanalının **en çok izlenen** videolarını tarar, her videodaki **viral olabilecek anları** yapay zekâ ile bulur, o anlardan **dikey (9:16 Shorts/Reels) klipler** keser, üzerine **Türkçe altyazı** basar ve klibin **başına/sonuna efekt** ekler.

Ekstra olarak: **karaoke altyazı** (kelime kelime vurgu), **sahne kesimine hizalama**, **kapak görseli**, **SEO başlık/açıklama/hashtag**, **ilerleme çubuğu**, **ses normalizasyonu**, **logo/watermark**, **arka plan müziği** (ducking'li), **format seçeneği** (9:16 / 1:1 / 16:9), **SRT dışa aktarımı**, **paralel işleme**, **yüz tespitiyle akıllı kırpma (auto-reframe)**, **web arayüzü** ve **YouTube / TikTok / Instagram'a otomatik yükleme**.

## 🔒 Hesap erişimi hakkında (önemli)

Otomatik yükleme, hesaplarına **yalnızca her platformun resmî API'si ve OAuth ile** erişir:
YouTube Data API, TikTok Content Posting API, Instagram Graph API. Bot **şifre saklamaz**,
tarayıcıdan otomatik giriş yapmaz. Kendi geliştirici uygulamanı (client id/secret) oluşturup
token verirsin; bot bu token ile **senin kendi** hesaplarına video yükler — içerik üreticiler
için standart ve platform kurallarına uygun yöntem budur. Token dosyaları `secrets/` klasöründe
tutulur ve `.gitignore` ile depoya girmez.

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

## 🖥️ Masaüstü uygulaması olarak çalıştırma (en kolay)

Terminal bilmene gerek yok — çift tıkla açılan bir uygulama penceresi olarak gelir.

### Windows
1. **Python 3.10+** kur → https://www.python.org/downloads/
   Kurulumda **“Add Python to PATH”** kutusunu işaretle.
2. **ffmpeg** kur → https://www.gyan.dev/ffmpeg/builds/ (indir, `bin` klasörünü PATH'e ekle).
3. Klasördeki **`Baslat.bat`** dosyasına **çift tıkla**.
   - İlk açılışta gerekli her şeyi otomatik kurar (birkaç dakika).
   - `.env` dosyası oluşur → içine **`ANTHROPIC_API_KEY`** anahtarını yaz.
   - Uygulama, **Chrome'un uygulama penceresinde** (sekmesiz/adres çubuğusuz) açılır; kanal URL'sini gir, **Başlat**'a bas.

### macOS
`Baslat.command` dosyasına çift tıkla (ilk seferde: sağ tık → **Aç**). `ffmpeg` için: `brew install ffmpeg`.

### Linux
Terminalde `./baslat.sh` çalıştır. `ffmpeg` için: `sudo apt install ffmpeg`.

> Uygulama, sistemde kurulu **Google Chrome**'u "uygulama modu" (`--app`) ile temiz, native
> görünümlü bir pencerede açar (kendi ayrı profiliyle; normal Chrome oturumuna karışmaz).
> Chrome yoksa **Edge** denenir, o da yoksa varsayılan tarayıcıda açılır.

---

## Kurulum (geliştirici / manuel)

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
# Kanal: en çok izlenen videoları işler
python -m viralbot "https://www.youtube.com/@KANAL_ADI"

# Tek video: yalnızca o videoyu analiz eder, viral kısımlarından Shorts üretir
python -m viralbot "https://www.youtube.com/watch?v=VIDEO_ID"
```

> Kanal linki mi yoksa tek video linki mi verdiğin **otomatik algılanır**. Tek video için
> `--moments` ile o videodan kaç klip çıkacağını ayarlayabilirsin (ör. `--moments 5`).

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
  --whisper-device cpu \  # cpu veya cuda (GPU varsa çok daha hızlı)
  --translate tr \        # altyazıyı Türkçe'ye çevir (tr) veya İngilizce'ye (en)
                          #   verilmezse videonun kendi dili otomatik algılanır
  --include-music         # müzik videolarını da dâhil et (varsayılan: elenir)

# Biçim ve efektler
  --aspect 9:16 \         # 9:16 | 1:1 | 16:9
  --reframe \             # yüz tespitiyle özneye ortalanmış kırpma
  --logo logo.png \       # köşeye watermark
  --music fon.mp3 \       # arka plan müziği (ducking'li)
  --music-volume 0.12 \
  --sub-color '&H00FFFFFF' \      # altyazı rengi (ASS BGR)
  --highlight-color '&H0000E5FF' \# karaoke vurgu rengi
  --font Arial

# Kapatma anahtarları
  --no-karaoke  --no-scenes  --no-progress-bar \
  --no-loudnorm --no-thumbnail --no-srt --no-metadata

# Otomatik yükleme + YouTube zamanlı yayın
  --upload youtube \
  --yt-privacy public \            # public | unlisted | private (vars. public)
  --schedule-interval-hours 6 \    # her 6 saatte bir video otomatik herkese açık
  --schedule-start-hours 2 \       # ilk video 2 saat sonra yayınlansın
  --secrets-dir secrets
```

### YouTube zamanlı yayın nasıl çalışır?

`--schedule-interval-hours` (veya web arayüzünde **"Videolar arası (saat)"**) 0'dan büyükse,
her klip **özel** yüklenir ve YouTube tarafından belirlenen saatte **otomatik herkese açık**
olur (`publishAt`). Bilgisayarın o an kapalı olsa bile YouTube videoyu zamanı gelince yayınlar.
Aralık 0 ise tüm klipler **hemen herkese açık** yüklenir.

> ⚠️ **YouTube API notu:** Google projeniz **denetimden (audit) geçmemişse**, API ile yüklenen
> videolar herkese açık yapılsa bile YouTube tarafından **özel** olarak kilitlenebilir. Bu,
> Google'ın bir güvenlik politikasıdır; herkese açık API yüklemesi için projenizin YouTube
> API uygunluk denetiminden geçmesi gerekir. Denetime kadar videoları YouTube Studio'dan elle
> herkese açık yapabilirsiniz.

## 🤖 Otomatik / zamanlanmış üretim

Kanalı sürekli izleyip **yeni yüklenen** videolar geldikçe otomatik klip üretir (ve istenirse yükler):

```bash
# Sürekli izle: her saat başı yeni videoları kontrol et, otomatik üret + YouTube'a yükle
python -m viralbot "https://youtube.com/@KANAL" \
  --watch --interval 3600 --upload youtube

# Tek kontrol turu (cron/görev zamanlayıcı ile birlikte kullanışlı):
python -m viralbot "https://youtube.com/@KANAL" --once --upload youtube
```

- İlk `--watch` turunda mevcut videolar "işlenmiş" işaretlenir; yalnızca **bundan sonra** gelen yeni yüklemeler işlenir (geçmişi baştan üretmez).
- İşlenen video kimlikleri `cikti/_islenen.json`'da tutulur → aynı video iki kez işlenmez.
- Sunucuda `--once`'ı cron'a bağlayarak da tam otomatik bir hat kurabilirsin (ör. `0 * * * *`).

## 🌐 Web arayüzü

Terminal yerine tarayıcıdan kullanmak için:

```bash
python -m viralbot.webapp
# Tarayıcı: http://127.0.0.1:5000
```

Arayüzden kanal URL'si + seçenekleri girip **Başlat**'a basarsın; canlı log akar,
üretilen klipleri izleyip indirebilir ve tek tıkla platformlara yükleyebilirsin.

## ⇪ Otomatik yükleme kurulumu

Tokenlar `--secrets-dir` (vars. `cikti/secrets`) klasöründen okunur.

**YouTube**
1. Google Cloud Console → "YouTube Data API v3"ü etkinleştir.
2. OAuth istemcisi (Masaüstü) oluştur, JSON'u `secrets/youtube_client_secret.json` yap.
3. İlk kez yetkilendir: `python -m viralbot --authorize youtube "x"` — tarayıcı açılır,
   kendi hesabınla onay verirsin; token `secrets/youtube_token.json`'a kaydedilir.

**TikTok**
- developers.tiktok.com'da uygulama + `video.publish` izni al, OAuth ile access token üret.
- `TIKTOK_ACCESS_TOKEN` env değişkeni ya da `secrets/tiktok_token.txt` dosyasına yaz.
- Uygulama onaylı değilse videolar yalnızca özel (SELF_ONLY) yüklenir.

**Instagram** (Reels)
- Professional/Business hesap + bağlı Facebook Sayfası gerekir.
- Uzun ömürlü access token ve `ig_user_id` al, `secrets/instagram.json`'a yaz.
- IG Graph API yerel dosya kabul etmez: klibi herkese açık bir URL'ye koyup
  `ozet.json` meta'sındaki `public_url` alanına o adresi vermelisin.

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
| `reframe.py` | OpenCV ile yüz tespiti → akıllı dikey kırpma odağı |
| `config.py` | Render seçenekleri (biçim, tema, efekt anahtarları) |
| `pipeline.py` | Uçtan uca akış (paralel işleme, yükleme) |
| `uploaders/` | YouTube / TikTok / Instagram resmî API yükleyicileri |
| `scheduler.py` | Otomatik izleme: yeni videoları bulup işleyen zamanlayıcı |
| `webapp.py` | Flask web arayüzü |
| `cli.py` | Komut satırı arayüzü |
