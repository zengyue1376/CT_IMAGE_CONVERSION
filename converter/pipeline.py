from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .filters import apply_filters
from .naming import build_output_basename, pick_non_overwriting_path
from .nifti import convert_series_to_nifti
from .nifti_info import read_nifti_info
from .phase import PhaseMap, detect_phase_with_match
from .scan import scan_series
from .spacing import z_spacing_mm


LogFn = Callable[[str], None]


@dataclass(frozen=True)
class ConversionConfig:
    input_dir: str
    output_dir: str
    phase_map_path: str
    output_prefix: str = ""
    use_series_description_in_name: bool = False
    max_spacing_mm: float = 5.0
    min_slices: int = 16
    enable_localizer_filter: bool = True
    enable_patient_position_filter: bool = False
    allowed_patient_positions: str = "HFS"
    skip_if_exists: bool = True


@dataclass
class ConversionResult:
    scanned_series: int = 0
    converted: int = 0
    skipped: int = 0
    failed: int = 0


def run_conversion(cfg: ConversionConfig, *, log: Optional[LogFn] = None, progress: Optional[Callable[[int, int], None]] = None) -> ConversionResult:
    if log is None:
        log = lambda _: None
    if progress is None:
        progress = lambda _, __: None

    input_dir = os.path.abspath(cfg.input_dir)
    output_dir = os.path.abspath(cfg.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    phase_map = PhaseMap.load(cfg.phase_map_path)
    groups = scan_series(input_dir, log=log)
    keys = list(groups.keys())

    res = ConversionResult(scanned_series=len(keys))
    total = len(keys)

    for i, key in enumerate(keys, start=1):
        progress(i, total)
        series = groups[key]
        t0 = time.perf_counter()
        z = z_spacing_mm(series)
        xy = series.pixel_spacing
        spacings = []
        if xy is not None:
            spacings.extend([xy[0], xy[1]])
        if z is not None:
            spacings.append(z)
        max_s = max(spacings) if spacings else None
        log(
            "[SERIES] "
            f"i={i}/{total} files={len(series.files)} "
            f"patient_position={(series.patient_position or 'unknown')} "
            f"spacing_xy={(('%.3f,%.3f' % xy) if xy is not None else 'unknown')} "
            f"spacing_z={(('%.3fmm' % z) if z is not None else 'unknown')} "
            f"spacing_max={('%.3fmm' % max_s) if max_s is not None else 'unknown'} "
            f"desc={series.series_description!r} protocol={series.protocol_name!r} "
            f"study={series.study_instance_uid} series={series.series_instance_uid}"
        )

        allowed = {p.strip().upper() for p in (cfg.allowed_patient_positions or "").split(",") if p.strip()}
        if not allowed:
            allowed = {"HFS"}

        decision = apply_filters(
            series,
            min_slices=cfg.min_slices,
            enable_localizer_filter=cfg.enable_localizer_filter,
            enable_patient_position_filter=cfg.enable_patient_position_filter,
            allowed_patient_positions=allowed,
        )
        if not decision.ok:
            res.skipped += 1
            log(f"[SKIP] {decision.reason} | key={series.key} | elapsed={time.perf_counter()-t0:.3f}s")
            continue

        phase, matched_kw, hay = detect_phase_with_match(series, phase_map=phase_map, source_root=input_dir)
        if matched_kw:
            log(f"[PHASE] phase={phase} matched={matched_kw!r}")
        else:
            log(f"[PHASE] phase=unknown (no keyword hit) hay={hay[:120]!r}")

        base = build_output_basename(
            series,
            phase=phase,
            prefix=cfg.output_prefix,
            use_series_description=cfg.use_series_description_in_name,
        )
        out_path, exists = pick_non_overwriting_path(output_dir, base)

        if exists and cfg.skip_if_exists:
            res.skipped += 1
            log(f"[SKIP] SKIP_EXISTS | out={out_path}")
            continue

        # Ensure we still never overwrite: if exists and skip disabled, create a non-overwriting dup name
        if exists:
            n = 1
            while True:
                candidate = os.path.join(output_dir, f"{base}_dup{n}.nii.gz")
                if not os.path.exists(candidate):
                    out_path = candidate
                    break
                n += 1
            log(f"[INFO] 目标已存在，改用新文件名 out={out_path}")

        try:
            convert_series_to_nifti(series, out_path, log=log)

            # Post-conversion filtering based on actual NIfTI header (matches what training truly sees)
            info = read_nifti_info(out_path)
            if info.size[2] < int(cfg.min_slices):
                os.remove(out_path)
                res.skipped += 1
                log(f"[SKIP] SKIP_NIFTI_TOO_FEW_SLICES({info.size[2]}<{cfg.min_slices}) | out={out_path}")
                continue
            if info.max_spacing > float(cfg.max_spacing_mm):
                os.remove(out_path)
                res.skipped += 1
                log(
                    f"[SKIP] SKIP_NIFTI_MAX_SPACING_TOO_LARGE({info.max_spacing:.3f}mm>{cfg.max_spacing_mm:.3f}mm) "
                    f"| spacing={info.spacing} | out={out_path}"
                )
                continue

            res.converted += 1
            log(f"[OK] out={out_path} | nifti_spacing={info.spacing} | elapsed={time.perf_counter()-t0:.3f}s")
        except Exception as e:
            res.failed += 1
            log(f"[FAIL] key={series.key} | err={e} | elapsed={time.perf_counter()-t0:.3f}s")

    progress(total, total)
    log(f"[DONE] scanned={res.scanned_series} converted={res.converted} skipped={res.skipped} failed={res.failed}")
    return res

