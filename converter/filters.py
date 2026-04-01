from __future__ import annotations

from dataclasses import dataclass

from .types import SeriesMeta


LOCALIZER_KEYWORDS = (
    "localizer",
    "scout",
    "定位",
    "定侧",
    "topogram",
    "surview",
)


@dataclass(frozen=True)
class FilterDecision:
    ok: bool
    reason: str = ""


def _effective_thickness_mm(series: SeriesMeta) -> float | None:
    for v in (series.slice_thickness, series.spacing_between_slices):
        if v is None:
            continue
        if v <= 0:
            continue
        return float(v)
    return None


def is_localizer(series: SeriesMeta) -> bool:
    text = f"{series.series_description} {series.protocol_name} {series.image_type}".lower()
    return any(k in text for k in LOCALIZER_KEYWORDS)


def apply_filters(
    series: SeriesMeta,
    *,
    min_slices: int,
    enable_localizer_filter: bool,
    enable_patient_position_filter: bool,
    allowed_patient_positions: set[str],
) -> FilterDecision:
    if series.modality.strip().upper() != "CT":
        return FilterDecision(False, "SKIP_NOT_CT")

    if enable_patient_position_filter:
        pos = (series.patient_position or "").strip().upper()
        if not pos:
            return FilterDecision(False, "SKIP_NO_PATIENT_POSITION")
        if pos not in allowed_patient_positions:
            return FilterDecision(False, f"SKIP_PATIENT_POSITION({pos})")

    if enable_localizer_filter and is_localizer(series):
        return FilterDecision(False, "SKIP_LOCALIZER")

    if len(series.files) < int(min_slices):
        return FilterDecision(False, f"SKIP_TOO_FEW_SLICES({len(series.files)}<{min_slices})")

    return FilterDecision(True, "OK")

