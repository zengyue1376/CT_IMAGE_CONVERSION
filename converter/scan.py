from __future__ import annotations

import os
from typing import Dict, Iterable, Optional

import pydicom
from pydicom.errors import InvalidDicomError

from .types import DicomFileMeta, SeriesMeta


def _safe_get_str(ds: pydicom.Dataset, name: str) -> str:
    v = getattr(ds, name, None)
    if v is None:
        return ""
    try:
        return str(v)
    except Exception:
        return ""


def _safe_get_float(ds: pydicom.Dataset, name: str) -> Optional[float]:
    v = getattr(ds, name, None)
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _safe_get_int(ds: pydicom.Dataset, name: str) -> Optional[int]:
    v = getattr(ds, name, None)
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _safe_get_ipp(ds: pydicom.Dataset) -> Optional[tuple[float, float, float]]:
    ipp = getattr(ds, "ImagePositionPatient", None)
    if ipp is None:
        return None
    try:
        vals = [float(x) for x in ipp]
        if len(vals) != 3:
            return None
        return (vals[0], vals[1], vals[2])
    except Exception:
        return None


def _safe_get_pixel_spacing(ds: pydicom.Dataset) -> Optional[tuple[float, float]]:
    ps = getattr(ds, "PixelSpacing", None)
    if ps is None:
        return None
    try:
        vals = [float(x) for x in ps]
        if len(vals) != 2:
            return None
        # DICOM PixelSpacing = [row_spacing, col_spacing] in mm
        if vals[0] <= 0 or vals[1] <= 0:
            return None
        return (vals[0], vals[1])
    except Exception:
        return None


def _safe_get_iop(ds: pydicom.Dataset) -> Optional[tuple[float, float, float, float, float, float]]:
    iop = getattr(ds, "ImageOrientationPatient", None)
    if iop is None:
        return None
    try:
        vals = [float(x) for x in iop]
        if len(vals) != 6:
            return None
        return (vals[0], vals[1], vals[2], vals[3], vals[4], vals[5])
    except Exception:
        return None


def iter_candidate_files(root_dir: str) -> Iterable[str]:
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            yield p


def scan_series(root_dir: str, *, log: Optional[callable] = None) -> Dict[str, SeriesMeta]:
    """
    Recursively scan DICOM files and group them by (StudyInstanceUID, SeriesInstanceUID).
    This does NOT assume any specific folder organization.
    """
    if log is None:
        log = lambda _: None

    groups: Dict[str, SeriesMeta] = {}
    total = 0
    dicom_ok = 0
    for path in iter_candidate_files(root_dir):
        total += 1
        if total % 2000 == 0:
            log(f"[SCAN] scanned_files={total} dicom_headers_ok={dicom_ok} series={len(groups)}")
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True, force=True, specific_tags=[
                "StudyInstanceUID",
                "SeriesInstanceUID",
                "SeriesDescription",
                "ProtocolName",
                "Modality",
                "ImageType",
                "PatientPosition",
                "PixelSpacing",
                "ImageOrientationPatient",
                "SliceThickness",
                "SpacingBetweenSlices",
                "InstanceNumber",
                "ImagePositionPatient",
            ])
        except (InvalidDicomError, PermissionError, OSError):
            continue
        except Exception as e:
            log(f"[WARN] 读取失败，跳过：{path} ({e})")
            continue

        study_uid = _safe_get_str(ds, "StudyInstanceUID").strip()
        series_uid = _safe_get_str(ds, "SeriesInstanceUID").strip()
        modality = _safe_get_str(ds, "Modality").strip()
        if not study_uid or not series_uid:
            continue
        dicom_ok += 1

        key = f"{study_uid}|{series_uid}"
        if key not in groups:
            groups[key] = SeriesMeta(
                key=key,
                study_instance_uid=study_uid,
                series_instance_uid=series_uid,
                series_description=_safe_get_str(ds, "SeriesDescription").strip(),
                protocol_name=_safe_get_str(ds, "ProtocolName").strip(),
                modality=modality,
                image_type=_safe_get_str(ds, "ImageType").strip(),
                patient_position=_safe_get_str(ds, "PatientPosition").strip().upper(),
                image_orientation_patient=_safe_get_iop(ds),
                pixel_spacing=_safe_get_pixel_spacing(ds),
                slice_thickness=_safe_get_float(ds, "SliceThickness"),
                spacing_between_slices=_safe_get_float(ds, "SpacingBetweenSlices"),
            )

        groups[key].files.append(
            DicomFileMeta(
                path=path,
                instance_number=_safe_get_int(ds, "InstanceNumber"),
                image_position_patient=_safe_get_ipp(ds),
            )
        )

    log(f"[INFO] 扫描完成：共发现 {len(groups)} 个 Series（从 {total} 个文件候选中识别）")
    return groups

