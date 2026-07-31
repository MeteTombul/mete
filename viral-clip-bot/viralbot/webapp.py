"""Basit web arayüzü (Flask).

Çalıştır:  python -m viralbot.webapp   (veya: viralbot-web)
Tarayıcıda: http://127.0.0.1:5000
"""

from __future__ import annotations

import threading
from pathlib import Path

from dotenv import load_dotenv

# .env dosyasındaki ANTHROPIC_API_KEY vb. değişkenleri yükle (masaüstü uygulaması yolu dâhil).
# Önce proje kökündeki .env, bulunamazsa çalışma dizininden yukarı doğru aranır.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    url_for,
)

from . import channel as channel_mod
from .config import RenderOptions
from .pipeline import run as run_pipeline
from .uploaders import available_platforms, get_uploader

app = Flask(__name__)

OUT_DIR = Path("cikti")
SECRETS_DIR = OUT_DIR / "secrets"

# Basit iş durumu (tek iş)
_job = {"running": False, "logs": [], "results": []}
_lock = threading.Lock()


def _log(msg: str) -> None:
    with _lock:
        _job["logs"].append(str(msg))


INDEX_HTML = """
<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Viral Clip Bot</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:820px;margin:24px auto;padding:0 16px;
   background:#0f172a;color:#e2e8f0}
 h1{background:linear-gradient(90deg,#38bdf8,#a78bfa);-webkit-background-clip:text;
   background-clip:text;color:transparent}
 label{display:block;margin:10px 0 4px;font-weight:600}
 input,select{width:100%;padding:8px;border-radius:8px;border:1px solid #334155;
   background:#1e293b;color:#e2e8f0;box-sizing:border-box}
 .row{display:flex;gap:12px}.row>div{flex:1}
 .chk{display:inline-flex;align-items:center;gap:6px;margin:6px 12px 6px 0;font-weight:400}
 .chk input{width:auto}
 button{margin-top:16px;padding:12px 24px;border:0;border-radius:999px;font-weight:700;
   cursor:pointer;background:linear-gradient(90deg,#38bdf8,#a78bfa);color:#0f172a}
 a{color:#38bdf8} .card{background:#1e293b;border:1px solid #334155;border-radius:12px;
   padding:16px;margin:16px 0}
 pre{background:#020617;padding:12px;border-radius:8px;max-height:280px;overflow:auto}
 .acc{display:inline-block;padding:2px 8px;border-radius:6px;font-size:.85rem}
 .ok{background:#14532d}.no{background:#7f1d1d}
</style></head><body>
<h1>🎬 Viral Clip Bot</h1>

<div class="card">
 <b>Hesap durumu</b> (yalnızca resmî API/OAuth ile, kendi hesaplarına):<br>
 {% for p,ok in accounts.items() %}
   <span class="acc {{'ok' if ok else 'no'}}">{{p}}: {{'bağlı' if ok else 'bağlı değil'}}</span>
 {% endfor %}
 <div style="margin-top:8px">
  {% for p in accounts %}
   <a href="{{ url_for('authorize', platform=p) }}">{{p}} yetkilendir</a> &nbsp;
  {% endfor %}
 </div>
 <div style="margin-top:6px">
  <a href="{{ url_for('tiktok_setup') }}">TikTok anahtarlarını gir →</a>
 </div>
</div>

<form id="jobForm">
 <label>Kanal URL'si veya tek video linki</label>
 <input name="channel_url" placeholder="youtube.com/@kanal · youtube.com/watch?v=... · kick.com/yayinci · kick.com/video/..." required>
 <small style="color:#94a3b8">YouTube kanal/video ya da Kick kanal/VOD linki. Kanal linki: en çok
  izlenenleri işler. Tek video/VOD linki: yalnızca onu işler. (Kick kanal listesi bazen
  alınamaz; o zaman tek bir <b>kick.com/video/...</b> linki yapıştır.)</small>
 <div class="row">
  <div><label>Video sayısı</label><input name="videos" type="number" value="3"></div>
  <div><label>Video başına klip</label><input name="moments" type="number" value="3"></div>
  <div><label>Format</label>
   <select name="aspect"><option>9:16</option><option>1:1</option><option>16:9</option></select>
  </div>
 </div>
 <div class="row">
  <div><label>Whisper modeli</label>
   <select name="whisper_model">
     <option>tiny</option><option>base</option><option selected>small</option>
     <option>medium</option><option>large-v3</option>
   </select>
  </div>
  <div><label>Altyazı dili</label>
   <select name="translate">
     <option value="">Videonun dili (otomatik)</option>
     <option value="tr">Türkçe'ye çevir</option>
     <option value="en">İngilizce'ye çevir</option>
   </select>
  </div>
 </div>
 <label>Efektler</label>
 <div>
  <label class="chk"><input type="checkbox" name="karaoke" checked>Karaoke altyazı</label>
  <label class="chk"><input type="checkbox" name="reframe">Yüzle akıllı kırpma</label>
  <label class="chk"><input type="checkbox" name="scenes" checked>Sahne hizalama</label>
  <label class="chk"><input type="checkbox" name="progress_bar" checked>İlerleme çubuğu</label>
  <label class="chk"><input type="checkbox" name="thumbnail" checked>Kapak</label>
  <label class="chk"><input type="checkbox" name="metadata" checked>SEO metası</label>
  <label class="chk"><input type="checkbox" name="skip_music" checked>Müzikleri atla</label>
 </div>
 <label>Otomatik yükle</label>
 <div>
  <label class="chk"><input type="checkbox" name="up_youtube">YouTube</label>
  <label class="chk"><input type="checkbox" name="up_tiktok">TikTok</label>
  <label class="chk"><input type="checkbox" name="up_instagram">Instagram</label>
 </div>

 <div class="card" style="margin-top:12px">
  <b>📤 YouTube yayın zamanlaması</b>
  <div class="row" style="margin-top:8px">
   <div><label>Gizlilik</label>
    <select name="yt_privacy">
      <option value="public" selected>Herkese açık</option>
      <option value="unlisted">Liste dışı</option>
      <option value="private">Özel</option>
    </select>
   </div>
   <div><label>Videolar arası (saat)</label>
    <input name="interval_hours" type="number" step="0.5" value="0"
           placeholder="0 = hepsi hemen">
   </div>
   <div><label>İlk video kaç saat sonra</label>
    <input name="start_hours" type="number" step="0.5" value="0">
   </div>
  </div>
  <small style="color:#94a3b8">Aralık &gt; 0 ise her klip, belirtilen saat arayla YouTube'da
   otomatik <b>herkese açık</b> olur (video kapalıyken bile YouTube yayınlar). 0 ise hepsi
   hemen yayınlanır.</small>
 </div>

 <button id="startBtn" type="submit">Başlat</button>
 <button id="clearBtn" type="button"
   style="background:#334155;color:#e2e8f0">Log'u temizle</button>
</form>

<div class="card">
 <b>Durum:</b> <span id="statusText">{{ 'çalışıyor…' if running else 'hazır' }}</span>
 &nbsp;·&nbsp; <a href="{{ url_for('clips_page') }}">Üretilen klipler →</a>
 <pre id="logs">{{ logs }}</pre>
</div>

<script>
 const form = document.getElementById('jobForm');
 const startBtn = document.getElementById('startBtn');
 const clearBtn = document.getElementById('clearBtn');
 const statusText = document.getElementById('statusText');
 const logsEl = document.getElementById('logs');

 form.addEventListener('submit', async (e) => {
   e.preventDefault();
   startBtn.disabled = true;
   statusText.textContent = 'başlatılıyor…';
   const r = await fetch('{{ url_for("start") }}', { method: 'POST', body: new FormData(form) });
   const d = await r.json().catch(() => ({}));
   if (d && d.ok === false) { statusText.textContent = d.error || 'zaten çalışıyor'; }
   poll();
 });

 clearBtn.addEventListener('click', async () => {
   await fetch('{{ url_for("clear_logs") }}', { method: 'POST' });
   logsEl.textContent = '';
 });

 async function poll() {
   try {
     const r = await fetch('{{ url_for("status") }}');
     const d = await r.json();
     logsEl.textContent = d.logs.join('\\n');
     logsEl.scrollTop = logsEl.scrollHeight;
     startBtn.disabled = d.running;
     statusText.textContent = d.running ? 'çalışıyor…' : 'hazır (yeni işlem yapabilirsin)';
   } catch (e) {}
 }
 setInterval(poll, 1500);
 poll();
</script>
</body></html>
"""

CLIPS_HTML = """
<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Klipler</title>
<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;
 background:#0f172a;color:#e2e8f0}a{color:#38bdf8}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
 .item{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:10px}
 video{width:100%;border-radius:8px}button{margin-top:8px;padding:8px 14px;border:0;
 border-radius:8px;background:#38bdf8;color:#0f172a;font-weight:700;cursor:pointer}</style>
</head><body>
<h1>Üretilen klipler</h1><a href="{{ url_for('index') }}">← geri</a>
<div class="grid">
 {% for c in clips %}
  <div class="item">
   <video src="{{ url_for('serve_clip', name=c) }}" controls></video>
   <div><a href="{{ url_for('serve_clip', name=c) }}" download>{{ c }}</a></div>
   <form method="post" action="{{ url_for('upload_clip') }}">
     <input type="hidden" name="name" value="{{ c }}">
     <label><input type="checkbox" name="p" value="youtube">YouTube</label>
     <label><input type="checkbox" name="p" value="tiktok">TikTok</label>
     <label><input type="checkbox" name="p" value="instagram">Instagram</label>
     <button>Yükle</button>
   </form>
  </div>
 {% endfor %}
</div>
</body></html>
"""


def _account_status() -> dict[str, bool]:
    status = {}
    for p in available_platforms():
        try:
            status[p] = get_uploader(p, SECRETS_DIR).is_configured()
        except Exception:  # noqa: BLE001
            status[p] = False
    return status


@app.route("/")
def index():
    with _lock:
        logs = "\n".join(_job["logs"][-200:])
        running = _job["running"]
    return render_template_string(
        INDEX_HTML, accounts=_account_status(), logs=logs, running=running
    )


@app.route("/start", methods=["POST"])
def start():
    with _lock:
        if _job["running"]:
            return jsonify(ok=False, error="Bir işlem zaten çalışıyor")
        _job["running"] = True
        _job["logs"] = []
        _job["results"] = []

    f = request.form
    opts = RenderOptions(
        aspect=f.get("aspect", "9:16"),
        reframe=bool(f.get("reframe")),
        translate_to=(f.get("translate") or None),
        skip_music=bool(f.get("skip_music")),
        karaoke=bool(f.get("karaoke")),
        progress_bar=bool(f.get("progress_bar")),
        make_thumbnail=bool(f.get("thumbnail")),
        make_metadata=bool(f.get("metadata")),
    )
    targets = [
        p for p in ("youtube", "tiktok", "instagram") if f.get(f"up_{p}")
    ]
    src_url = f["channel_url"].strip()
    params = dict(
        channel_url=src_url,
        out_dir=OUT_DIR,
        opts=opts,
        moments_per_video=int(f.get("moments", 3)),
        whisper_model=f.get("whisper_model", "small"),
        use_scenes=bool(f.get("scenes")),
        upload_targets=targets,
        secrets_dir=SECRETS_DIR,
        youtube_privacy=f.get("yt_privacy", "public"),
        schedule_interval_hours=float(f.get("interval_hours") or 0),
        schedule_start_hours=float(f.get("start_hours") or 0),
    )
    # Tek video linki mi, kanal mı?
    if channel_mod.is_video_url(src_url):
        try:
            params["videos"] = [channel_mod.video_from_url(src_url)]
            _log("Tek video linki algılandı — sadece bu video işlenecek.")
        except Exception as e:  # noqa: BLE001
            _log(f"Video bilgisi alınamadı: {e}")
    else:
        params["top_videos"] = int(f.get("videos", 3))

    def job():
        try:
            results = run_pipeline(log=_log, **params)
            with _lock:
                _job["results"] = results
        except Exception as e:  # noqa: BLE001
            _log(f"HATA: {e}")
        finally:
            with _lock:
                _job["running"] = False

    threading.Thread(target=job, daemon=True).start()
    return jsonify(ok=True)


@app.route("/status")
def status():
    with _lock:
        return jsonify(running=_job["running"], logs=_job["logs"][-200:])


@app.route("/clear-logs", methods=["POST"])
def clear_logs():
    with _lock:
        if not _job["running"]:
            _job["logs"] = []
    return jsonify(ok=True)


TIKTOK_SETUP_HTML = """
<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TikTok anahtarları</title>
<style>body{font-family:system-ui,sans-serif;max-width:640px;margin:24px auto;padding:0 16px;
 background:#0f172a;color:#e2e8f0}a{color:#38bdf8}
 label{display:block;margin:12px 0 4px;font-weight:600}
 input{width:100%;padding:8px;border-radius:8px;border:1px solid #334155;background:#1e293b;
 color:#e2e8f0;box-sizing:border-box}
 button{margin-top:16px;padding:12px 24px;border:0;border-radius:999px;font-weight:700;
 cursor:pointer;background:linear-gradient(90deg,#38bdf8,#a78bfa);color:#0f172a}
 .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;margin:16px 0}
 code{background:#020617;padding:2px 6px;border-radius:4px}</style></head><body>
<h1>TikTok anahtarları</h1>
<a href="{{ url_for('index') }}">← geri</a>
<div class="card">
 developers.tiktok.com'daki uygulamandan <b>Client key</b> ve <b>Client secret</b> değerlerini
 buraya yapıştır. TikTok panelinde <b>Redirect URI</b> olarak da
 <code>http://localhost:5599/callback</code> kaydetmeyi unutma.
</div>
{% if saved %}<div class="card">✓ Kaydedildi. Şimdi
 <a href="{{ url_for('authorize', platform='tiktok') }}">TikTok'u yetkilendir →</a></div>{% endif %}
{% if error %}<div class="card">⚠ {{ error }}</div>{% endif %}
<form method="post">
 <label>Client key</label>
 <input name="client_key" value="{{ client_key }}" required>
 <label>Client secret</label>
 <input name="client_secret" value="{{ client_secret }}" required>
 <label>Redirect URI</label>
 <input name="redirect_uri" value="{{ redirect_uri }}">
 <button>Kaydet</button>
</form>
</body></html>
"""


@app.route("/tiktok/setup", methods=["GET", "POST"])
def tiktok_setup():
    import json as _json
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    app_file = SECRETS_DIR / "tiktok_app.json"
    ck = cs = ""
    redirect = "http://localhost:5599/callback"
    saved = False
    error = None

    if app_file.exists():
        try:
            from .util import read_text_any
            cfg = _json.loads(read_text_any(app_file))
            ck = cfg.get("client_key", "")
            cs = cfg.get("client_secret", "")
            redirect = cfg.get("redirect_uri", redirect)
        except Exception:  # noqa: BLE001
            pass

    if request.method == "POST":
        ck = request.form.get("client_key", "").strip()
        cs = request.form.get("client_secret", "").strip()
        redirect = request.form.get("redirect_uri", "").strip() or redirect
        if not ck or not cs:
            error = "Client key ve Client secret boş olamaz."
        else:
            app_file.write_text(
                _json.dumps(
                    {"client_key": ck, "client_secret": cs, "redirect_uri": redirect},
                    ensure_ascii=False, indent=2,
                ),
                encoding="utf-8",
            )
            saved = True

    return render_template_string(
        TIKTOK_SETUP_HTML, client_key=ck, client_secret=cs,
        redirect_uri=redirect, saved=saved, error=error,
    )


@app.route("/authorize/<platform>")
def authorize(platform):
    try:
        msg = get_uploader(platform, SECRETS_DIR).authorize()
    except Exception as e:  # noqa: BLE001
        msg = f"Hata: {e}"
    extra = ""
    if platform == "tiktok":
        extra = (
            f" &nbsp;|&nbsp; <a href='{url_for('tiktok_setup')}'>"
            "TikTok anahtarlarını formdan gir →</a>"
        )
    return (
        f"<div style='font-family:system-ui;max-width:640px;margin:24px auto;padding:0 16px'>"
        f"<p>{msg}</p><a href='{url_for('index')}'>← geri</a>{extra}</div>"
    )


@app.route("/clips")
def clips_page():
    clips_dir = OUT_DIR / "klipler"
    clips = sorted(p.name for p in clips_dir.glob("*.mp4")) if clips_dir.exists() else []
    return render_template_string(CLIPS_HTML, clips=clips)


@app.route("/clip/<path:name>")
def serve_clip(name):
    return send_from_directory(OUT_DIR / "klipler", name)


@app.route("/upload", methods=["POST"])
def upload_clip():
    name = request.form["name"]
    platforms = request.form.getlist("p")
    clip_path = OUT_DIR / "klipler" / name
    # ozet.json içinden meta bul
    meta = {"moment_title": name}
    import json
    summary = OUT_DIR / "ozet.json"
    if summary.exists():
        for m in json.loads(summary.read_text(encoding="utf-8")):
            if Path(m.get("clip", "")).name == name:
                meta = m
                break
    msgs = []
    for p in platforms:
        try:
            up = get_uploader(p, SECRETS_DIR)
            if not up.is_configured():
                msgs.append(f"{p}: yapılandırılmamış")
                continue
            res = up.upload(clip_path, meta)
            msgs.append(f"{p}: {res.status} {res.url or res.error or ''}")
        except Exception as e:  # noqa: BLE001
            msgs.append(f"{p}: hata {e}")
    return "<br>".join(msgs) + f"<p><a href='{url_for('clips_page')}'>← geri</a>"


def main() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
