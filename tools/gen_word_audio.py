"""Lug'atdagi har bir so'z uchun audio (bir martalik, offline).

Bot bu skriptni ishlatmaydi — u faqat tayyor `english/audio/words/<id>.ogg`
fayllarini yuboradi, shuning uchun TTS kutubxonalari serverga o'rnatilmaydi.

Fayl nomi so'zning `id` si bo'yicha — `words.json` dagi id barqaror.

Ishlatish:
    pip install --target /tmp/tts piper-tts soundfile
    PYTHONPATH=/tmp/tts python tools/gen_word_audio.py /path/to/amy.onnx
Mavjud fayllar qayta yaratilmaydi; hammasini yangilash uchun papkani o'chiring.
"""
import io, json, sys, time, wave
from pathlib import Path

import numpy as np
import soundfile as sf
from piper import PiperVoice

ROOT = Path(__file__).resolve().parent.parent
WORDS = ROOT / "english" / "words.json"
OUT = ROOT / "english" / "audio" / "words"
OPUS_RATE = 24000
SILENCE = 0.01     # shu darajadan past — jimlik
PAD = 0.06         # qirqilgandan keyin qoldiriladigan zaxira, soniya


def main(model: str) -> None:
    voice = PiperVoice.load(model, config_path=model + ".json")
    OUT.mkdir(parents=True, exist_ok=True)
    words = json.loads(WORDS.read_text(encoding="utf-8"))["words"]

    made = skipped = 0
    started = time.monotonic()
    for w in words:
        path = OUT / f'{w["id"]}.ogg'
        if path.exists():
            skipped += 1
            continue
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            voice.synthesize_wav(w["word"], wf)
        with wave.open(io.BytesIO(buf.getvalue())) as wf:
            rate = wf.getframerate()
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), "<i2").astype("float32") / 32768

        # boshi va oxiridagi jimlikni qirqamiz — hajm ham, kutish ham kamayadi
        loud = np.where(np.abs(pcm) > SILENCE)[0]
        if len(loud):
            a = max(0, loud[0] - int(rate * PAD))
            b = min(len(pcm), loud[-1] + int(rate * PAD))
            pcm = pcm[a:b]

        n = int(len(pcm) * OPUS_RATE / rate)
        pcm = np.interp(np.linspace(0, len(pcm), n, endpoint=False),
                        np.arange(len(pcm)), pcm).astype("float32")
        out = io.BytesIO()
        sf.write(out, pcm, OPUS_RATE, format="OGG", subtype="OPUS")
        path.write_bytes(out.getvalue())
        made += 1
        if made % 250 == 0:
            done = made + skipped
            print(f"  {done}/{len(words)} — {time.monotonic()-started:.0f}s", flush=True)

    total = sum(f.stat().st_size for f in OUT.glob("*.ogg"))
    print(f"{made} ta yangi, {skipped} ta mavjud edi. Jami {total/1048576:.1f} MB → {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
