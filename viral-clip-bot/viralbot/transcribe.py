"""Konuşmayı zaman damgalı altyazıya çevirme (faster-whisper)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class Transcript:
    language: str
    segments: list[Segment]

    def full_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments)


def transcribe(
    video_path: Path,
    model_size: str = "small",
    device: str = "cpu",
    language: str | None = "tr",
) -> Transcript:
    """Videonun sesini yazıya döker.

    language=None verilirse dil otomatik algılanır. Türkçe için "tr" sabitlemek
    daha doğru sonuç verir.
    """
    # Lazy import: faster-whisper ağır bir bağımlılık, sadece gerektiğinde yükle
    from faster_whisper import WhisperModel

    compute_type = "int8" if device == "cpu" else "float16"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    segments_iter, info = model.transcribe(
        str(video_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,  # sessizlikleri ayıklar, daha temiz zamanlama
    )

    segments: list[Segment] = []
    for seg in segments_iter:
        words = [
            Word(start=w.start, end=w.end, text=w.word)
            for w in (seg.words or [])
            if w.start is not None and w.end is not None
        ]
        segments.append(
            Segment(start=seg.start, end=seg.end, text=seg.text, words=words)
        )

    return Transcript(language=info.language, segments=segments)
