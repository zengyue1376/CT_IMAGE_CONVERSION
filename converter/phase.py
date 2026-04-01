from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

import yaml

from .types import SeriesMeta


@dataclass(frozen=True)
class PhaseMap:
    mapping: Dict[str, List[str]]

    @staticmethod
    def load(path: str) -> "PhaseMap":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        mapping: Dict[str, List[str]] = {}
        for k, v in data.items():
            if isinstance(v, list):
                mapping[str(k).strip().lower()] = [str(x).strip().lower() for x in v if str(x).strip()]
            else:
                mapping[str(k).strip().lower()] = []
        return PhaseMap(mapping=mapping)


def detect_phase_with_match(
    series: SeriesMeta, *, phase_map: PhaseMap, source_root: str | None = None
) -> tuple[str, str | None, str]:
    parts = [series.series_description, series.protocol_name, series.image_type]
    if source_root:
        parts.append(os.path.basename(source_root))
    hay = " ".join([p for p in parts if p]).lower()

    # deterministic order: try specific keys first (except unknown)
    keys = [k for k in phase_map.mapping.keys() if k != "unknown"]
    for phase in keys:
        for kw in phase_map.mapping.get(phase, []):
            if kw and kw in hay:
                return phase, kw, hay
    return "unknown", None, hay


def detect_phase(series: SeriesMeta, *, phase_map: PhaseMap, source_root: str | None = None) -> str:
    phase, _, _ = detect_phase_with_match(series, phase_map=phase_map, source_root=source_root)
    return phase

