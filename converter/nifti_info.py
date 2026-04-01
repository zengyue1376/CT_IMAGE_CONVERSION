from __future__ import annotations

from dataclasses import dataclass

import SimpleITK as sitk


@dataclass(frozen=True)
class NiftiInfo:
    spacing: tuple[float, float, float]
    size: tuple[int, int, int]

    @property
    def max_spacing(self) -> float:
        return float(max(self.spacing))


def read_nifti_info(path: str) -> NiftiInfo:
    """
    Read NIfTI header info only (spacing/size) without loading all pixels.
    """
    r = sitk.ImageFileReader()
    r.SetFileName(path)
    r.ReadImageInformation()
    sp = tuple(float(x) for x in r.GetSpacing())
    sz = tuple(int(x) for x in r.GetSize())
    # ensure 3D tuple even if 2D
    if len(sp) == 2:
        sp = (sp[0], sp[1], 1.0)
    if len(sz) == 2:
        sz = (sz[0], sz[1], 1)
    return NiftiInfo(spacing=sp[:3], size=sz[:3])

