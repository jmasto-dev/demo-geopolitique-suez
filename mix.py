"""Score (VSCO 2 CE + VCSL), foley, and French voiceover mix for Suez (30.0 s, 48 kHz)."""
import os, sys, json
import numpy as np
import soundfile as sf
import soxr

LIB = os.environ.get('LIB', '/home/devuser/lemo-opuscar')
sys.path.insert(0, LIB)
from core.audio import sampler as S
from core.audio.sfx import SR, add, bp, lp, brown, noise, env_exp, norm, t_

HERE = os.path.dirname(os.path.abspath(__file__))
DUR = 30.0
N = int(round(DUR * SR))

def duck_env(vo_spans, fade=0.22, floor=0.20):
    env = np.ones(N, dtype=np.float32)
    f = int(fade * SR)
    for t0, t1 in vo_spans:
        i0, i1 = max(0, int(t0 * SR) - f), min(N, int(t1 * SR) + f)
        a0, a1 = max(0, int(t0 * SR)), min(N, int(t1 * SR))
        if a0 > i0: env[i0:a0] = np.minimum(env[i0:a0], np.linspace(1.0, floor, a0 - i0))
        env[a0:a1] = np.minimum(env[a0:a1], floor)
        if i1 > a1: env[a1:i1] = np.minimum(env[a1:i1], np.linspace(floor, 1.0, i1 - a1))
    return env

def main():
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    with open(os.path.join(HERE, 'lines.json'), encoding='utf-8') as f:
        lines = json.load(f)
    vo_buf = np.zeros((N, 2), dtype=np.float32)
    vo_spans = []
    for L in lines:
        w, sr = sf.read(os.path.join(HERE, 'voices', f"{L['id']}.wav"), dtype='float32')
        if w.ndim > 1: w = w.mean(axis=1)
        if sr != SR: w = soxr.resample(w, sr, SR)
        w = norm(np.tanh(w * 1.3) / 1.3) * 0.72
        add(vo_buf, w, L['t'], gain=1.0, pan=0.0)
        vo_spans.append((L['t'], L['t'] + len(w) / SR))

    # 84 BPM chamber score: vibraphone_bowed, cellos_pizz, horn, timpani, cellos
    BEAT = 60.0 / 84.0
    ev = [
        (0.0, 'vibraphone_bowed', 'E4', 5.0, 0.45, -0.2),
        (0.0, 'cellos_pizz', 'E2', 0.8, 0.60, 0.15),
        (2.85, 'cellos_pizz', 'B2', 0.8, 0.55, 0.15),
        (6.5, 'cellos_pizz', 'E2', 0.6, 0.60, 0.1),
        (8.0, 'cellos_pizz', 'G2', 0.6, 0.58, -0.1),
        (10.0, 'cellos_pizz', 'E2', 0.6, 0.60, 0.1),
        (14.0, 'horn', 'E3', 4.2, 0.62, 0.15),
        (14.0, 'timpani', 'E2', 1.8, 0.72, 0.0),
        # Silence 18.5..20.5 s before Cape detour
        (20.5, 'cellos', 'E2', 7.5, 0.55, -0.2),
        (21.0, 'horn', 'B2', 5.0, 0.52, 0.2),
        (23.0, 'vibraphone_bowed', 'B4', 4.5, 0.38, -0.25),
    ]
    S.seed(2024)
    score = S.room(S.render(ev, dur=DUR, master=False), size=0.45, mix=0.2)

    fol = np.zeros((N, 2), dtype=np.float32)
    add(fol, lp(brown(DUR), 380) * 0.12, 0.0, gain=1.0, pan=0.0)
    # Dive whoosh, route ignition shimmer, and pullout sweep
    add(fol, norm(bp(noise(1.6), 220, 1200) * np.sin(np.pi * t_(1.6) / 1.6)) * 0.35, 1.0, gain=0.7, pan=0.0)
    add(fol, norm(bp(noise(0.9), 1800, 5600) * env_exp(0.9, 0.28)) * 0.35, 6.8, gain=0.75, pan=0.1)
    add(fol, norm(bp(noise(1.4), 260, 1400) * np.sin(np.pi * t_(1.4) / 1.4)) * 0.35, 20.5, gain=0.7, pan=0.0)

    duck = duck_env(vo_spans)
    mix = score * duck[:, None] * 0.45 + fol * 0.6 + vo_buf
    peak = np.abs(mix).max()
    if peak > 0.92: mix *= 0.92 / peak
    out = os.path.join(HERE, 'out', 'mix.wav')
    sf.write(out, mix, SR, subtype='PCM_16')
    print(f'wrote {out} ({DUR}s)')

if __name__ == '__main__':
    main()
