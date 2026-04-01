from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional

from .types import SeriesMeta


LogFn = Callable[[str], None]


def find_dcm2niix() -> str | None:
    """
    Returns absolute path to dcm2niix executable if available in PATH.
    """
    exe = shutil.which("dcm2niix")
    return exe


@dataclass(frozen=True)
class Dcm2niixOptions:
    compress: bool = True  # .nii.gz


def _link_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except Exception:
        shutil.copy2(src, dst)


def convert_series_with_dcm2niix(
    series: SeriesMeta,
    *,
    out_path: str,
    log: Optional[LogFn] = None,
    opts: Optional[Dcm2niixOptions] = None,
) -> bool:
    """
    Convert one Series using dcm2niix by staging its DICOM files into a temp folder.
    Returns True if dcm2niix was used successfully, False if dcm2niix is not available.
    Raises on execution error.
    """
    if log is None:
        log = lambda _: None
    if opts is None:
        opts = Dcm2niixOptions()

    exe = find_dcm2niix()
    if not exe:
        return False

    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)

    # dcm2niix writes into a directory with -o and uses -f for filename (without extension).
    base_name = os.path.basename(out_path)
    if base_name.lower().endswith(".nii.gz"):
        stem = base_name[:-7]
    elif base_name.lower().endswith(".nii"):
        stem = base_name[:-4]
    else:
        stem = os.path.splitext(base_name)[0]

    with tempfile.TemporaryDirectory(prefix="ct_dcm2niix_") as tmp:
        # stage series dicoms
        for idx, f in enumerate(series.files):
            # keep extension-less to reduce weirdness, but preserve unique names
            dst = os.path.join(tmp, f"{idx:06d}.dcm")
            _link_or_copy(f.path, dst)

        cmd = [
            exe,
            "-b",
            "n",  # no BIDS json
            "-z",
            "y" if opts.compress else "n",
            "-o",
            out_dir,
            "-f",
            stem,
            tmp,
        ]
        log(f"[DCM2NIIX] {' '.join(cmd)}")
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.stdout.strip():
            log("[DCM2NIIX_OUT] " + p.stdout.strip().replace("\n", " | "))
        if p.stderr.strip():
            log("[DCM2NIIX_ERR] " + p.stderr.strip().replace("\n", " | "))
        if p.returncode != 0:
            raise RuntimeError(f"dcm2niix failed (code={p.returncode})")

    # dcm2niix may create .nii or .nii.gz depending on -z.
    # Ensure expected out_path exists; otherwise try to locate generated file.
    if os.path.exists(out_path):
        return True

    alt = os.path.join(out_dir, stem + (".nii.gz" if opts.compress else ".nii"))
    if os.path.exists(alt) and os.path.abspath(alt) != os.path.abspath(out_path):
        # move/rename to match requested path (still no overwrite: caller already ensured out_path is free)
        os.replace(alt, out_path)
        return True

    # last resort: find any nifti with matching stem
    for fn in os.listdir(out_dir):
        low = fn.lower()
        if low.startswith(stem.lower()) and (low.endswith(".nii") or low.endswith(".nii.gz")):
            cand = os.path.join(out_dir, fn)
            if os.path.abspath(cand) != os.path.abspath(out_path):
                os.replace(cand, out_path)
            return True

    raise FileNotFoundError("dcm2niix did not produce expected nifti output")

