"""The film's music, made here (nothing to license): a tanpura-like drone in C under make_video's pad, and a struck
bowl wherever one is asked for."""

import numpy as np
from scipy.signal import butter, sosfilt

import make_video as mv

RATE = mv.RATE


def tanpura(seconds: float) -> np.ndarray:
    """A tanpura-like drone in C, mono: Pa, Sa, Sa and low Sa plucked in turn, each ringing out through its harmonics."""
    n = int(seconds * RATE)
    out = np.zeros(n)
    t = np.arange(int(4.5 * RATE)) / RATE
    k = np.arange(1, 13)[:, None]
    for i, at in enumerate(range(0, n, int(1.25 * RATE))):
        f = (98.0, 130.81, 130.81, 65.41)[i % 4]
        note = (np.sin(2 * np.pi * f * k * t + k) / k**0.8 * np.exp(-t * (0.5 + 0.3 * k))).sum(axis=0) * np.clip(t / 0.01, 0, 1)
        end = min(n, at + len(t))
        out[at:end] += note[: end - at]
    out = sosfilt(butter(2, 2200, "low", fs=RATE, output="sos"), out)
    return out / max(np.abs(out).max(), 1e-9)


def bowl(seconds: float) -> np.ndarray:
    """A struck singing bowl on G: four inharmonic partials, each beating slowly and dying away."""
    t = np.arange(int(seconds * RATE)) / RATE
    partials = ((1.0, 1.0), (2.76, 0.45), (5.4, 0.2), (8.93, 0.08))
    tone = sum(a * np.sin(2 * np.pi * 392.0 * r * t) * (1 + 0.25 * np.sin(2 * np.pi * (0.7 + r) * t)) * np.exp(-t * r / 4)
               for r, a in partials)
    return tone * np.clip(t / 0.004, 0, 1)


def music(seconds: float, bowls: tuple = ()) -> np.ndarray:
    """Stereo at RATE: the pad and the drone, with a bowl struck at each time in `bowls` (seconds)."""
    n = int(seconds * RATE)
    drone = tanpura(seconds)
    bed = 0.6 * mv.pad(seconds)[:n] + 0.4 * np.stack([drone, drone * 0.96], axis=1)
    for at in bowls:
        ring = bowl(min(9.0, seconds - at)) * 0.5
        i = int(at * RATE)
        bed[i : i + len(ring)] += ring[:, None]
    return bed
