from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DicomFileMeta:
    path: str
    instance_number: Optional[int]
    image_position_patient: Optional[tuple[float, float, float]]


@dataclass
class SeriesMeta:
    key: str  # typically StudyUID|SeriesUID
    study_instance_uid: str
    series_instance_uid: str
    series_description: str
    protocol_name: str
    modality: str
    image_type: str
    patient_position: str
    image_orientation_patient: Optional[tuple[float, float, float, float, float, float]]
    pixel_spacing: Optional[tuple[float, float]]
    slice_thickness: Optional[float]
    spacing_between_slices: Optional[float]
    files: list[DicomFileMeta] = field(default_factory=list)

