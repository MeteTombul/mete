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
</div>

<form method="post" action="{{ url_for('start') }}">
 <label>Kanal URL'si</label>
 <input name="channel_url" placeholder="https://www.youtube.com/@kanaladi" required>
 <div class="row">
  <div><label>Video sayısı</label><input name="videos" type="number" value="3"></div>
  <div><label>Video başına klip</label><input name="moments" type="number" value="3"></div>
  <div><label>Format</label>
   <select name="aspect"><option>9:16</option><option>1:1</option><option>16:9</option></select>
  </div>
 </div>
 <label>Whisper modeli</label>
 <select name="whisper_model">
   <option>tiny</option><option>base</option><option selected>small</option>
   <option>medium</option><option>large-v3</option>
 </select>
 <label>Efektler</label>
 <div>
  <label class="chk"><input type="checkbox" name="karaoke" checked>Karaoke altyazı</label>
  <label class="chk"><input type="checkbox" name="reframe">Yüzle akıllı kırpma</label>
  <label class="chk"><input type="checkbox" name="scenes" checked>Sahne hizalama</label>
  <label class="chk"><input type="checkbox" name="progress_bar" checked>İlerleme çubuğu</label>
  <label class="chk"><input type="checkbox" name="thumbnail" checked>Kapak</label>
  <label class="chk"><input type="checkbox" name="metadata" checked>SEO metası</label>
 </div>
 <label>Otomatik yükle</label>
 <div>
  <label class="chk"><input type="checkbox" name="up_youtube">YouTube</label>
  <label class="chk"><input type="checkbox" name="up_tiktok">TikTok</label>
  <label class="chk"><input type="checkbox" name="up_instagram">Instagram</label>
 </div>
 <button {{ 'disabled' if running }}>Başlat</button>
</form>

<div class="card">
 <b>Durum:</b> {{ 'çalışıyor…' if running else 'boşta' }}
 &nbsp;·&nbsp; <a href="{{ url_for('clips_page') }}">Üretilen klipler →</a>
 <pre id="logs">{{ logs }}</pre>
</div>

<script>
 setInterval(async ()=>{
   const r = await fetch('{{ url_for("status") }}'); const d = await r.json();
   document.getElementById('logs').textContent = d.logs.join('\\n');
 }, 1500);
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
            return redirect(url_for("index"))
        _job["running"] = True
        _job["logs"] = []
        _job["results"] = []

    f = request.form
    opts = RenderOptions(
        aspect=f.get("aspect", "9:16"),
        reframe=bool(f.get("reframe")),
        karaoke=bool(f.get("karaoke")),
        progress_bar=bool(f.get("progress_bar")),
        make_thumbnail=bool(f.get("thumbnail")),
        make_metadata=bool(f.get("metadata")),
    )
    targets = [
        p for p in ("youtube", "tiktok", "instagram") if f.get(f"up_{p}")
    ]
    params = dict(
        channel_url=f["channel_url"],
        out_dir=OUT_DIR,
        opts=opts,
        top_videos=int(f.get("videos", 3)),
        moments_per_video=int(f.get("moments", 3)),
        whisper_model=f.get("whisper_model", "small"),
        use_scenes=bool(f.get("scenes")),
        upload_targets=targets,
        secrets_dir=SECRETS_DIR,
    )

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
    return redirect(url_for("index"))


@app.route("/status")
def status():
    with _lock:
        return jsonify(running=_job["running"], logs=_job["logs"][-200:])


@app.route("/authorize/<platform>")
def authorize(platform):
    try:
        msg = get_uploader(platform, SECRETS_DIR).authorize()
    except Exception as e:  # noqa: BLE001
        msg = f"Hata: {e}"
    return f"<p>{msg}</p><a href='{url_for('index')}'>← geri</a>"


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
