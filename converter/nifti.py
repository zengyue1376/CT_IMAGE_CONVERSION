from __future__ import annotations

from typing import Callable, List, Optional

import SimpleITK as sitk

from .dcm2niix import convert_series_with_dcm2niix
from .spacing import _cross, _dot, _unit  # reuse tested vector ops
from .types import SeriesMeta


LogFn = Callable[[str], None]


def sort_files_for_series(series: SeriesMeta) -> List[str]:
    """
    Sort slices using the same core idea as ITK/Slicer: order by position along slice normal.
    Falls back to InstanceNumber/path when orientation/position is missing.
    """

    n = None
    if series.image_orientation_patient is not None:
        a = (series.image_orientation_patient[0], series.image_orientation_patient[1], series.image_orientation_patient[2])
        b = (series.image_orientation_patient[3], series.image_orientation_patient[4], series.image_orientation_patient[5])
        n = _unit(_cross(a, b))

    def key_fn(f):
        if f.image_position_patient is not None and n is not None:
            ipp = f.image_position_patient
            s = _dot((ipp[0], ipp[1], ipp[2]), n)
            return (0, s, f.path)
        if f.image_position_patient is not None:
            ipp = f.image_position_patient
            return (1, ipp[2], ipp[1], ipp[0], f.path)
        if f.instance_number is not None:
            return (2, f.instance_number, f.path)
        return (3, f.path)

    files = sorted(series.files, key=key_fn)
    return [f.path for f in files]


def convert_series_to_nifti(series: SeriesMeta, out_path: str, *, log: Optional[LogFn] = None) -> None:
    """
    DICOM Series -> NIfTI.
    Preferred backend: dcm2niix (matches common Slicer-compatible conversion behavior).
    Fallback backend: SimpleITK (ITK/GDCM) with robust slice ordering.
    """
    if log is None:
        log = lambda _: None

    # 1) try dcm2niix if available
    try:
        used = convert_series_with_dcm2niix(series, out_path=out_path, log=log)
        if used:
            log("[BACKEND] dcm2niix")
            return
    except Exception as e:
        log(f"[WARN] dcm2niix 转换失败，回退到 SimpleITK：{e}")

    # 2) fallback: SimpleITK
    file_list = sort_files_for_series(series)
    if not file_list:
        raise ValueError("empty series")

    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(file_list)
    image = reader.Execute()
    sitk.WriteImage(image, out_path, True)
    log("[BACKEND] SimpleITK")

