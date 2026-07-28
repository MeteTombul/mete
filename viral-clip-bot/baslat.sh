#!/usr/bin/env bash
# Linux: ./baslat.sh
cd "$(dirname "$0")" || exit 1

echo "== Viral Clip Bot =="

command -v python3 >/dev/null 2>&1 || { echo "[HATA] python3 gerekli."; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || echo "[UYARI] ffmpeg bulunamadı (sudo apt install ffmpeg)."

if [ ! -x ".venv/bin/python" ]; then
  echo "İlk kurulum yapılıyor..."
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

[ -f .env ] || { cp .env.example .env; echo "[BİLGİ] .env oluşturuldu — ANTHROPIC_API_KEY yazın."; }

python app.py
