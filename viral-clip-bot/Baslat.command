#!/usr/bin/env bash
# macOS: çift tıklayarak çalıştırın (gerekirse: sağ tık > Aç).
cd "$(dirname "$0")" || exit 1

echo "============================================"
echo "  Viral Clip Bot - başlatılıyor..."
echo "============================================"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[HATA] python3 bulunamadı. https://www.python.org/downloads/ adresinden kurun."
  read -r -p "Çıkmak için Enter..."; exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[UYARI] ffmpeg bulunamadı. Kurulum:  brew install ffmpeg"
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "İlk kurulum yapılıyor, birkaç dakika sürebilir..."
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
read -r -p "Kapatmak için Enter..."
