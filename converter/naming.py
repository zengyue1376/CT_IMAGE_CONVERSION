from __future__ import annotations

import base64
import hashlib
import os
import re

from .types import SeriesMeta
from .spacing import z_spacing_mm


_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def _b32_short_sha1(text: str, n: int) -> str:
    h = hashlib.sha1(text.encode("utf-8", errors="ignore")).digest()
    b32 = base64.b32encode(h).decode("ascii").lower().rstrip("=")
    return b32[:n]


def stable_anon_id(series: SeriesMeta) -> str:
    # stable across re-runs; does not include PHI like PatientName
    return _b32_short_sha1(series.study_instance_uid, 8)


def stable_series_id(series: SeriesMeta) -> str:
    return _b32_short_sha1(series.series_instance_uid, 6)


def sanitize_filename(s: str) -> str:
    s = s.strip()
    if not s:
        return "unknown"
    s = _SAFE.sub("_", s)
    s = s.strip("._-")
    return s or "unknown"


def thickness_mm(series: SeriesMeta) -> float | None:
    # For naming/filters we prefer spacing derived from adjacent IPP (more robust),
    # falling back to DICOM tags when needed.
    return z_spacing_mm(series)


def build_output_basename(
    series: SeriesMeta,
    *,
    phase: str,
    prefix: str = "",
    use_series_description: bool = False,
) -> str:
    anon = stable_anon_id(series)
    sid = stable_series_id(series)
    t = thickness_mm(series)
    t_str = f"{t:.2f}mm" if t is not None else "unknown"
    prefix = sanitize_filename(prefix) if prefix and prefix.strip() else ""
    if use_series_description:
        desc = sanitize_filename(series.series_description or "no_desc")
        if prefix:
            return sanitize_filename(f"{prefix}_{anon}_{desc}_{sid}")
        return sanitize_filename(f"{anon}_{desc}_{sid}")

    # default: put anon "number" before phase/thickness
    if prefix:
        return sanitize_filename(f"{prefix}_{anon}_{phase}_t{t_str}_{sid}")
    return sanitize_filename(f"{anon}_{phase}_t{t_str}_{sid}")


def pick_non_overwriting_path(out_dir: str, basename: str, suffix: str = ".nii.gz") -> tuple[str, bool]:
    """
    Returns (path, exists_already).
    If exact target exists, we will not overwrite. Caller can decide to skip.
    If exact target doesn't exist, returns that path.
    If later collision happens (very rare), caller can ask again with different basename.
    """
    p = os.path.join(out_dir, basename + suffix)
    return p, os.path.exists(p)

