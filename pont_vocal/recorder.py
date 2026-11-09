import logging
import os
import sys
import threading
import time
import wave
from pathlib import Path

import pymumble_py3 as pymumble
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED

from pont_vocal.config import load_config
from pont_vocal.log import setup_log

log = logging.getLogger(__name__)

MUMBLE_RATE = 48000
FRAME_S = 0.01
SILENCE_S = 1.5


def lost_packets(expected, sequence):
    if expected is None:
        return 0
    return max(0, sequence - expected)


def next_sequence(sequence, duration):
    return sequence + round(duration / FRAME_S)


def wav_path(out_dir, start):
    day = time.strftime("%Y-%m-%d", time.localtime(start))
    name = time.strftime("%H%M%S", time.localtime(start))
    return out_dir / day / f"{name}.wav"


def empty_take():
    return {"pcm": bytearray(), "start": None, "last": None, "expected": None, "lost": 0, "max_gap": 0.0, "chunks": 0}


def save(take, out_dir):
    path = wav_path(out_dir, take["start"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(MUMBLE_RATE)
        wav.writeframes(bytes(take["pcm"]))
    log.info(
        f"{path.name} {len(take['pcm']) / (MUMBLE_RATE * 2):.1f}s paquets={take['chunks']} "
        f"perdus={take['lost']} trou_max={take['max_gap'] * 1000:.0f}ms"
    )


def main():
    out_dir = Path(__file__).resolve().parent.parent / "logs" / "enregistreur"
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_log(open(out_dir / "journal.log", "a", buffering=1, encoding="utf-8"))
    config = load_config()
    speaker = os.environ.get("MUMBLE_NAME", "claude")
    lock = threading.Lock()
    take = empty_take()

    def flush_if_silent(now):
        nonlocal take
        if take["last"] is not None and now - take["last"] > SILENCE_S:
            save(take, out_dir)
            take = empty_take()

    def on_sound(user, chunk):
        if user["name"] != speaker:
            return
        now = time.time()
        with lock:
            flush_if_silent(now)
            if take["start"] is None:
                take["start"] = now
            if take["last"] is not None:
                take["max_gap"] = max(take["max_gap"], now - take["last"])
            take["lost"] += lost_packets(take["expected"], chunk.sequence)
            take["expected"] = next_sequence(chunk.sequence, chunk.duration)
            take["pcm"].extend(chunk.pcm)
            take["last"] = now
            take["chunks"] += 1

    client = pymumble.Mumble(config.mumble_host, "enregistreur", port=64738, password=config.mumble_password, reconnect=True)
    client.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, on_sound)
    client.set_receive_sound(True)
    client.start()
    client.is_ready()
    log.info(f"enregistreur connecté, écoute {speaker}")
    while True:
        time.sleep(0.5)
        with lock:
            flush_if_silent(time.time())


if __name__ == "__main__":
    sys.exit(main())
