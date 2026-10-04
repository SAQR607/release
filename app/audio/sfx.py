"""Procedural SFX at 44.1 kHz mono (mixed into the master at config gain)."""

from __future__ import annotations

import math
import random

import numpy as np

SR = 44100


def _env(n: int, attack: float, decay: float, sr: int = SR) -> np.ndarray:
    a = max(1, int(attack * sr))
    d = max(1, int(decay * sr))
    a = min(a, n)
    d = min(d, n - a) if n - a > 0 else 1
    env = np.zeros(n, dtype=np.float32)
    env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    end = min(n, a + d)
    env[a:end] = np.linspace(1, 0, end - a, dtype=np.float32) ** 2
    return env


def whoosh(duration: float = 0.55, sr: int = SR) -> np.ndarray:
    n = int(duration * sr)
    rng = np.random.default_rng(11)
    noise = rng.standard_normal(n).astype(np.float32)
    # one-pole lowpass with moving cutoff (sweep) -> cheap approximation
    y = np.zeros(n, dtype=np.float32)
    prev = 0.0
    for i in range(n):
        a = 0.04 + 0.5 * (i / n)
        prev = (1 - a) * prev + a * noise[i]
        y[i] = prev
    y *= _env(n, 0.08, duration - 0.1, sr)
    return y * 1.8


def pop(duration: float = 0.18, sr: int = SR) -> np.ndarray:
    n = int(duration * sr)
    t = np.arange(n) / sr
    f = 520 * np.exp(-t * 14) + 130
    phase = 2 * np.pi * np.cumsum(f) / sr
    y = np.sin(phase).astype(np.float32)
    y *= _env(n, 0.004, duration - 0.01, sr)
    rng = np.random.default_rng(3)
    click = rng.standard_normal(min(80, n)).astype(np.float32) * 0.5
    y[: len(click)] += click * _env(len(click), 0.001, 0.01, sr)
    return y


def chime(seed: int = 7, duration: float = 1.1, sr: int = SR) -> np.ndarray:
    """Sparkle chime: three staggered bell tones."""
    n = int(duration * sr)
    rng = random.Random(seed)
    y = np.zeros(n, dtype=np.float32)
    base = rng.choice([1046.5, 1174.7, 1318.5, 1568.0])
    for k, (mult, gain, delay) in enumerate(((1.0, 0.5, 0.0), (1.5, 0.32, 0.14), (2.0, 0.22, 0.3))):
        d = int(delay * sr)
        m = n - d
        if m <= 0:
            continue
        t = np.arange(m) / sr
        tone = (np.sin(2 * np.pi * base * mult * t)
                + 0.3 * np.sin(2 * np.pi * base * mult * 2.76 * t))
        tone *= np.exp(-t * 4.2) * gain
        y[d:] += tone.astype(np.float32)
    return y


def sparkle(duration: float = 0.7, sr: int = SR) -> np.ndarray:
    n = int(duration * sr)
    rng = np.random.default_rng(5)
    y = np.zeros(n, dtype=np.float32)
    for _ in range(6):
        f = rng.uniform(1600, 3400)
        s = rng.integers(0, max(1, n - int(0.15 * sr)))
        m = min(int(0.18 * sr), n - s)
        t = np.arange(m) / sr
        y[s:s + m] += (np.sin(2 * np.pi * f * t) * np.exp(-t * 16)).astype(np.float32) * 0.4
    return y


def thump(duration: float = 0.3, sr: int = SR) -> np.ndarray:
    n = int(duration * sr)
    t = np.arange(n) / sr
    f = 95 * np.exp(-t * 9) + 48
    phase = 2 * np.pi * np.cumsum(f) / sr
    return (np.sin(phase).astype(np.float32) * _env(n, 0.004, duration - 0.01, sr)) * 1.2


def rain(duration: float = 1.0, sr: int = SR) -> np.ndarray:
    n = int(duration * sr)
    rng = np.random.default_rng(9)
    noise = rng.standard_normal(n).astype(np.float32)
    y = np.zeros(n, dtype=np.float32)
    prev = 0.0
    for i in range(n):
        prev = 0.86 * prev + 0.14 * noise[i]
        y[i] = prev
    y -= y.mean()
    y *= 0.6 + 0.4 * np.sin(2 * np.pi * 7.3 * np.arange(n) / sr).astype(np.float32)
    return y * 2.2


def bell(duration: float = 0.9, sr: int = SR) -> np.ndarray:
    n = int(duration * sr)
    t = np.arange(n) / sr
    y = (np.sin(2 * np.pi * 880 * t) * 0.5
         + np.sin(2 * np.pi * 1320 * t) * 0.3
         + np.sin(2 * np.pi * 1760 * t) * 0.18)
    return (y * np.exp(-t * 3.4)).astype(np.float32)


SFX = ("whoosh", "pop", "chime", "sparkle", "thump", "rain", "bell")


def render(name: str, seed: int = 0, sr: int = SR) -> np.ndarray:
    if name == "whoosh":
        return whoosh(sr=sr)
    if name == "pop":
        return pop(sr=sr)
    if name == "chime":
        return chime(seed=seed or 7, sr=sr)
    if name == "sparkle":
        return sparkle(sr=sr)
    if name == "thump":
        return thump(sr=sr)
    if name == "rain":
        return rain(sr=sr)
    if name == "bell":
        return bell(sr=sr)
    return pop(sr=sr)
