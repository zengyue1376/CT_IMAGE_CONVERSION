from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import SimpleITK as sitk


LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]


@dataclass(frozen=True)
class NiftiResampleConfig:
    input_dir: str
    output_dir: str
    target_spacing: tuple[float, float, float]  # (x,y,z)
    interpolator: str = "linear"  # "linear" | "nearest"
    skip_if_exists: bool = True


@dataclass
class NiftiResampleResult:
    scanned: int = 0
    written: int = 0
    skipped: int = 0
    failed: int = 0


def iter_nifti_files(root_dir: str) -> Iterable[str]:
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            low = fn.lower()
            if low.endswith(".nii") or low.endswith(".nii.gz"):
                yield os.path.join(dirpath, fn)


def _interpolator(name: str) -> int:
    n = (name or "").strip().lower()
    if n in ("nearest", "nn", "nearestneighbor"):
        return sitk.sitkNearestNeighbor
    return sitk.sitkLinear


def _ensure_spacing(sp: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = float(sp[0]), float(sp[1]), float(sp[2])
    if not (x > 0 and y > 0 and z > 0):
        raise ValueError("target spacing must be positive")
    return (x, y, z)


def _output_path(input_path: str, input_root: str, output_root: str) -> str:
    rel = os.path.relpath(input_path, input_root)
    # keep directory structure; always write .nii.gz
    base = rel
    if base.lower().endswith(".nii.gz"):
        base = base[:-7]
    elif base.lower().endswith(".nii"):
        base = base[:-4]
    return os.path.join(output_root, base + ".nii.gz")


def resample_nifti_folder(
    cfg: NiftiResampleConfig,
    *,
    log: Optional[LogFn] = None,
    progress: Optional[ProgressFn] = None,
) -> NiftiResampleResult:
    if log is None:
        log = lambda _: None
    if progress is None:
        progress = lambda _, __: None

    in_dir = os.path.abspath(cfg.input_dir)
    out_dir = os.path.abspath(cfg.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    target = _ensure_spacing(cfg.target_spacing)
    files = list(iter_nifti_files(in_dir))
    total = len(files)
    res = NiftiResampleResult(scanned=total)
    log(f"[RS] 扫描到 {total} 个 NIfTI 文件")
    log(f"[RS] target_spacing={target} interpolator={cfg.interpolator} out_dir={out_dir}")

    interp = _interpolator(cfg.interpolator)

    for i, p in enumerate(files, start=1):
        progress(i, total if total > 0 else 1)
        out_path = _output_path(p, in_dir, out_dir)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        if cfg.skip_if_exists and os.path.exists(out_path):
            res.skipped += 1
            log(f"[SKIP] EXISTS | {out_path}")
            continue

        try:
            img = sitk.ReadImage(p)
            in_sp = img.GetSpacing()
            in_sz = img.GetSize()

            # compute new size to preserve physical extent
            new_size = [
                max(1, int(math.floor(in_sz[d] * (in_sp[d] / target[d]) + 0.5))) for d in range(3)
            ]

            rf = sitk.ResampleImageFilter()
            rf.SetInterpolator(interp)
            rf.SetOutputSpacing(target)
            rf.SetSize(new_size)
            rf.SetOutputDirection(img.GetDirection())
            rf.SetOutputOrigin(img.GetOrigin())
            rf.SetTransform(sitk.Transform())
            rf.SetDefaultPixelValue(0)

            out = rf.Execute(img)
            sitk.WriteImage(out, out_path, True)
            res.written += 1
            log(f"[OK] {p} -> {out_path} | spacing {tuple(in_sp)} -> {target} | size {tuple(in_sz)} -> {tuple(new_size)}")
        except Exception as e:
            res.failed += 1
            log(f"[FAIL] {p} | {e}")

    progress(total, total if total > 0 else 1)
    log(f"[RS_DONE] scanned={res.scanned} written={res.written} skipped={res.skipped} failed={res.failed}")
    return res

