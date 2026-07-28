"""Yüz tespitiyle akıllı dikey kırpma (auto-reframe).

Klipteki konuşan kişiyi/yüzü örnekleyerek yatay odak noktasını (0..1) hesaplar.
Böylece dikey klipte özne, bulanık arka plan yerine kadraja ortalanabilir.
OpenCV (opencv-python-headless) gerektirir; yoksa 0.5 (orta) döner.
"""

from __future__ import annotations

from pathlib import Path


def compute_focus_x(source: Path, start: float, end: float, samples: int = 12) -> float:
    """Klip aralığından kareler örnekleyip en büyük yüzün ortalama yatay merkezini döndürür.

    Dönüş: 0.0 (sol) .. 1.0 (sağ). Yüz bulunamazsa 0.5.
    """
    try:
        import cv2  # type: ignore
    except Exception:
        return 0.5

    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(str(cascade_path))
    if cascade.empty():
        return 0.5

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        return 0.5

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1.0

    centers: list[float] = []
    dur = max(0.1, end - start)
    for i in range(samples):
        t = start + dur * (i + 0.5) / samples
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
        if len(faces) == 0:
            continue
        # En büyük yüzü seç
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        cx = (x + w / 2) / width
        centers.append(min(1.0, max(0.0, cx)))

    cap.release()
    if not centers:
        return 0.5
    # Aykırı değerleri yumuşatmak için medyan
    centers.sort()
    mid = len(centers) // 2
    if len(centers) % 2:
        return centers[mid]
    return (centers[mid - 1] + centers[mid]) / 2
