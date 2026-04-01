from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import SimpleITK as sitk


LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]


@dataclass(frozen=True)
class NiftiCleanConfig:
    input_dir: str
    max_spacing_mm: float
    delete: bool = True


@dataclass
class NiftiCleanResult:
    scanned: int = 0
    deleted: int = 0
    kept: int = 0
    failed: int = 0


def iter_nifti_files(root_dir: str) -> Iterable[str]:
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            low = fn.lower()
            if low.endswith(".nii") or low.endswith(".nii.gz"):
                yield os.path.join(dirpath, fn)


def max_spacing_of_nifti(path: str) -> float:
    reader = sitk.ImageFileReader()
    reader.SetFileName(path)
    img = reader.Execute()
    sp = img.GetSpacing()  # (x,y,z)
    if not sp:
        return float("inf")
    return float(max(sp))


def clean_nifti_by_max_spacing(
    cfg: NiftiCleanConfig,
    *,
    log: Optional[LogFn] = None,
    progress: Optional[ProgressFn] = None,
) -> NiftiCleanResult:
    if log is None:
        log = lambda _: None
    if progress is None:
        progress = lambda _, __: None

    input_dir = os.path.abspath(cfg.input_dir)
    files = list(iter_nifti_files(input_dir))
    total = len(files)
    res = NiftiCleanResult(scanned=total)
    log(f"[NIFTI] 扫描到 {total} 个 NIfTI 文件")

    for i, p in enumerate(files, start=1):
        progress(i, total if total > 0 else 1)
        try:
            m = max_spacing_of_nifti(p)
            if m > float(cfg.max_spacing_mm):
                if cfg.delete:
                    os.remove(p)
                    res.deleted += 1
                    log(f"[DEL] max_spacing={m:.3f}mm > {cfg.max_spacing_mm:.3f}mm | {p}")
                else:
                    res.kept += 1
                    log(f"[HIT] max_spacing={m:.3f}mm > {cfg.max_spacing_mm:.3f}mm | {p}")
            else:
                res.kept += 1
                log(f"[KEEP] max_spacing={m:.3f}mm | {p}")
        except Exception as e:
            res.failed += 1
            log(f"[FAIL] {p} | {e}")

    progress(total, total if total > 0 else 1)
    log(f"[NIFTI_DONE] scanned={res.scanned} kept={res.kept} deleted={res.deleted} failed={res.failed}")
    return res

