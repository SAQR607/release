"""Procedural music beds: gentle royalty-free-by-construction loops per mood.

Moods: happy playful calm wonder mystery tender triumph adventure
All output: float32 stereo at `sr`, length ~= seconds.
"""

from __future__ import annotations

import math

import numpy as np

# chord = semitone offsets from root; progressions are lists of (root_hz, [tones])
def _hz(semi: float) -> float:
    return 440.0 * (2 ** ((semi - 9) / 12))  # semi 0 = C4


MOODS = ("happy", "playful", "calm", "wonder", "mystery", "tender", "triumph", "adventure")

# Manifest music_moods without their own program map onto the closest bed
# (else they would silently fall back to 'happy').
MOOD_ALIASES = {"emotional": "tender", "discovery": "wonder"}

_PROGS: dict[str, dict] = {
    # root: chord degrees (semitones from C), bpm, pad_gain, arp_gain, arp_steps
    "happy": {"chords": [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]], "bpm": 96, "bright": 1.0},
    "playful": {"chords": [[5, 9, 12], [7, 11, 14], [0, 4, 7], [0, 4, 7]], "bpm": 112, "bright": 1.1},
    "calm": {"chords": [[9, 12, 16], [5, 9, 12], [0, 4, 7], [7, 11, 14]], "bpm": 68, "bright": 0.7},
    "wonder": {"chords": [[5, 9, 12, 16], [0, 4, 7, 11], [7, 11, 14, 17], [9, 12, 16, 19]], "bpm": 84, "bright": 1.2},
    "mystery": {"chords": [[9, 12, 16], [2, 5, 9], [9, 12, 16], [5, 9, 12]], "bpm": 72, "bright": 0.6},
    "tender": {"chords": [[0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7]], "bpm": 72, "bright": 0.75},
    "triumph": {"chords": [[0, 4, 7], [7, 11, 14], [5, 9, 12], [0, 4, 7]], "bpm": 100, "bright": 1.15},
    "adventure": {"chords": [[2, 5, 9], [10, 14, 17], [5, 9, 12], [0, 4, 7]], "bpm": 100, "bright": 1.0},
}


def _pad_note(f: float, n: int, sr: int, attack: float, release: float, gain: float) -> np.ndarray:
    t = np.arange(n) / sr
    y = (np.sin(2 * np.pi * f * t)
         + 0.35 * np.sin(4 * np.pi * f * t)
         + 0.12 * np.sin(6 * np.pi * f * t))
    env = np.ones(n, dtype=np.float32)
    a = min(int(attack * sr), n // 2)
    r = min(int(release * sr), n // 2)
    env[:a] = np.linspace(0, 1, a)
    env[n - r:] = np.linspace(1, 0, r)
    # gentle tremolo
    env *= 0.94 + 0.06 * np.sin(2 * np.pi * 0.35 * t)
    return (y * env * gain).astype(np.float32)


def _pluck(f: float, n: int, sr: int, gain: float) -> np.ndarray:
    t = np.arange(n) / sr
    y = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t)
    env = np.exp(-t * 5.5)
    return (y * env * gain).astype(np.float32)


def render_bed(mood: str, seconds: float, sr: int = 44100) -> np.ndarray:
    """Stereo float32 bed, loopable, length ~= seconds."""
    mood = MOOD_ALIASES.get(mood, mood)
    spec = _PROGS.get(mood, _PROGS["happy"])
    chords = spec["chords"]
    bpm = spec["bpm"]
    bright = spec["bright"]
    beat = 60.0 / bpm
    bar = beat * 4
    n_total = int(seconds * sr)
    left = np.zeros(n_total, dtype=np.float32)
    right = np.zeros(n_total, dtype=np.float32)

    t_pos = 0.0
    ci = 0
    seed = 0
    while t_pos < seconds:
        chord = chords[ci % len(chords)]
        start = int(t_pos * sr)
        bar_n = int(min(bar, seconds - t_pos) * sr)
        if bar_n <= 0:
            break
        # pad: root + tones, low octave for warmth
        for k, semi in enumerate(chord):
            f = _hz(semi - 12)
            note = _pad_note(f, bar_n, sr, attack=min(0.6, bar * 0.3),
                             release=min(0.9, bar * 0.35), gain=0.10 / (k + 1) ** 0.4)
            panl = 0.85 if k % 2 == 0 else 0.55
            end = min(start + bar_n, n_total)
            sl = note[: end - start]
            left[start:end] += sl * panl
            right[start:end] += sl * (1.4 - panl)
        # arp: bright triangle-ish plucks, eighth notes
        step = beat / 2
        t2 = t_pos
        idx = 0
        while t2 < t_pos + bar and t2 < seconds:
            semi = chord[(idx * 2 + seed) % len(chord)] + 12
            f = _hz(semi)
            n = int(min(0.5, step * 0.9) * sr)
            pl = _pluck(f, n, sr, gain=0.085 * bright)
            s = int(t2 * sr)
            e = min(s + n, n_total)
            if e > s:
                pan = 0.65 if idx % 2 == 0 else 0.45
                left[s:e] += pl[: e - s] * pan
                right[s:e] += pl[: e - s] * (1.2 - pan)
            t2 += step
            idx += 1
        t_pos += bar
        ci += 1
        seed += 1

    # soft high shimmer for wonder/mystery
    if mood in ("wonder", "mystery"):
        t = np.arange(n_total) / sr
        sh = 0.02 * np.sin(2 * np.pi * 1568.0 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.23 * t))
        left += sh.astype(np.float32)
        right += sh.astype(np.float32) * 0.8

    # normalize to a modest bed level (-18 dBFS-ish)
    peak = max(float(np.abs(left).max()), float(np.abs(right).max()), 1e-6)
    scale = 0.75 / peak
    left *= scale
    right *= scale
    # equal-power-ish crossfade safety: tiny fade at edges
    fade = int(0.05 * sr)
    if fade > 0 and n_total > 2 * fade:
        ramp = np.linspace(0, 1, fade, dtype=np.float32)
        for ch in (left, right):
            ch[:fade] *= ramp
            ch[-fade:] *= ramp[::-1]
    return np.stack([left, right], axis=1)
