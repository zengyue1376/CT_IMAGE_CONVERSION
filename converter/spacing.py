from __future__ import annotations

import math
from statistics import median

from .types import SeriesMeta


def _norm3(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(v: tuple[float, float, float]) -> tuple[float, float, float] | None:
    n = _norm3(v)
    if not (n > 0):
        return None
    return (v[0] / n, v[1] / n, v[2] / n)


def z_spacing_mm_from_ipp(series: SeriesMeta) -> float | None:
    """
    Robustly estimate slice spacing using adjacent ImagePositionPatient.
    Uses slice normal from ImageOrientationPatient when available; otherwise falls back to using Z coordinate.
    Returns median positive adjacent spacing in mm.
    """
    ipps = [f.image_position_patient for f in series.files if f.image_position_patient is not None]
    if len(ipps) < 3:
        return None

    # compute scalar position along slice normal
    n: tuple[float, float, float] | None = None
    if series.image_orientation_patient is not None:
        a = (series.image_orientation_patient[0], series.image_orientation_patient[1], series.image_orientation_patient[2])
        b = (series.image_orientation_patient[3], series.image_orientation_patient[4], series.image_orientation_patient[5])
        n = _unit(_cross(a, b))

    if n is not None:
        pos = [_dot((ipp[0], ipp[1], ipp[2]), n) for ipp in ipps]
    else:
        pos = [ipp[2] for ipp in ipps]

    pos = sorted(set(pos))
    if len(pos) < 3:
        return None

    diffs = []
    for i in range(1, len(pos)):
        d = abs(pos[i] - pos[i - 1])
        if d > 1e-6:
            diffs.append(d)
    if len(diffs) < 2:
        return None

    m = float(median(diffs))
    if not (m > 0):
        return None
    return m


def z_spacing_mm_fallback(series: SeriesMeta) -> float | None:
    for v in (series.spacing_between_slices, series.slice_thickness):
        if v is None:
            continue
        try:
            vv = float(v)
        except Exception:
            continue
        if vv > 0:
            return vv
    return None


def z_spacing_mm(series: SeriesMeta) -> float | None:
    return z_spacing_mm_from_ipp(series) or z_spacing_mm_fallback(series)

