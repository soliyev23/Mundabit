"""Darslar uchun audio yaratish (bir martalik, offline).

Bot bu skriptni ishlatmaydi — u faqat tayyor .ogg fayllarni yuboradi.
Shuning uchun piper/onnxruntime/soundfile ishlab chiqarishga o'rnatilmaydi.

Ishlatish:
    pip install --target /tmp/tts piper-tts soundfile
    # ovoz modelini yuklab oling (misol: Amy, AQSh):
    #   https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
    #   (+ .onnx.json)
    PYTHONPATH=/tmp/tts python tools/gen_lesson_audio.py /path/to/amy.onnx
"""
import io, json, sys, wave
from pathlib import Path

import numpy as np
import soundfile as sf
from piper import PiperVoice

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / "english" / "lessons.json"
OUT = ROOT / "english" / "audio"
GAP = 0.5          # bo'laklar orasidagi jimlik, soniya
OPUS_RATE = 24000  # Opus qo'llaydigan chastota (Telegram ovozli xabari uchun)


def main(model: str) -> None:
    voice = PiperVoice.load(model, config_path=model + ".json")

    def say(text: str) -> tuple[np.ndarray, int]:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            voice.synthesize_wav(text, wf)
        with wave.open(io.BytesIO(buf.getvalue())) as wf:
            rate = wf.getframerate()
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), "<i2")
        return pcm.astype("float32") / 32768, rate

    def write(path: Path, chunks: list[np.ndarray], rate: int) -> None:
        parts: list[np.ndarray] = []
        for c in chunks:
            parts += [c, np.zeros(int(rate * GAP), "float32")]
        pcm = np.concatenate(parts)
        n = int(len(pcm) * OPUS_RATE / rate)
        pcm = np.interp(np.linspace(0, len(pcm), n, endpoint=False),
                        np.arange(len(pcm)), pcm).astype("float32")
        buf = io.BytesIO()
        sf.write(buf, pcm, OPUS_RATE, format="OGG", subtype="OPUS")
        path.write_bytes(buf.getvalue())

    OUT.mkdir(parents=True, exist_ok=True)
    lessons = json.loads(LESSONS.read_text(encoding="utf-8"))["lessons"]
    made = 0
    for les in lessons:
        # Alifbo darslari: harf + misol so'z. Harf yolg'iz berilsa Piper uning
        # nomini o'qiydi ("A" → «ey») — bu bizga kerak.
        if les["unit"] == "alphabet" and les["items"] and "letter" in les["items"][0]:
            chunks, rate = [], 22050
            for it in les["items"]:
                a, rate = say(f'{it["letter"]}.')
                b, _ = say(f'{it["word"]}.')
                chunks += [a, b]
            write(OUT / f'lesson_{les["id"]}.ogg', chunks, rate)
            made += 1
        for n, task in enumerate(les["tasks"], 1):
            if not task.get("audio"):
                continue
            a, rate = say(task["audio"])
            write(OUT / f'task_{les["id"]}_{n}.ogg', [a], rate)
            made += 1
    total = sum(f.stat().st_size for f in OUT.glob("*.ogg"))
    print(f"{made} ta fayl, jami {total/1024:.0f} KB → {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
