"""Kokoro TTS via kokoro-onnx (quantized ONNX, CPU, disk-cached)."""

from __future__ import annotations

import hashlib
import os
import urllib.request
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models" / "kokoro"
MODEL_PATH = MODEL_DIR / "model_quantized.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"
SR_NATIVE = 24000

MODEL_URL = (
    "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/"
    "resolve/main/onnx/model_quantized.onnx"
)
VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/"
    "download/model-files-v1.1/voices-v1.0.bin"
)

_engine = None


def models_present() -> bool:
    return MODEL_PATH.exists() and VOICES_PATH.exists()


def ensure_models() -> None:
    """Download model + voices once (~120 MB total)."""
    if models_present():
        return
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for url, dst in ((MODEL_URL, MODEL_PATH), (VOICES_URL, VOICES_PATH)):
        if not dst.exists():
            tmp = dst.with_suffix(dst.suffix + ".part")
            urllib.request.urlretrieve(url, tmp)
            tmp.replace(dst)


def _engine_singleton():
    global _engine
    if _engine is None:
        warnings.filterwarnings("ignore")
        ensure_models()
        import onnxruntime as rt

        import kokoro_onnx as ko
        import kokoro_onnx.session as sess_mod

        def _patched(model_path: str):
            so = rt.SessionOptions()
            so.intra_op_num_threads = int(os.environ.get("TTS_THREADS") or os.cpu_count() or 2)
            so.inter_op_num_threads = 1
            so.graph_optimization_level = rt.GraphOptimizationLevel.ORT_ENABLE_ALL
            return rt.InferenceSession(
                model_path, sess_options=so, providers=rt.get_available_providers()
            )

        sess_mod.create_session = _patched
        ko.create_session = _patched
        _engine = ko.Kokoro(str(MODEL_PATH), str(VOICES_PATH))
    return _engine


def synth(text: str, voice: str = "af_bella", speed: float = 1.0,
          cache_dir: Path | None = None) -> tuple[np.ndarray, int]:
    """Synthesize speech -> (float32 samples, sr). Cached on disk when possible."""
    if not text.strip():
        return np.zeros(0, dtype=np.float32), SR_NATIVE
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha1(f"{text}|{voice}|{speed}".encode()).hexdigest()
        f = cache_dir / f"{key}.wav"
        if f.exists():
            import soundfile as sf

            data, sr = sf.read(f, dtype="float32")
            return data, sr
    eng = _engine_singleton()
    samples, sr = eng.create(text, voice=voice, speed=speed, lang="en-us")
    samples = np.asarray(samples, dtype=np.float32)
    if cache_dir is not None:
        import soundfile as sf

        sf.write(f, samples, sr)
    return samples, sr


def resample(samples: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr or samples.size == 0:
        return samples.astype(np.float32)
    n_out = int(round(samples.size * dst_sr / src_sr))
    x_old = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, samples).astype(np.float32)
