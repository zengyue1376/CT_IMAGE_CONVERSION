from __future__ import annotations

import argparse
import os

from converter import ConversionConfig, run_conversion


def main() -> None:
    p = argparse.ArgumentParser(description="CT DICOM -> NIfTI converter (incremental, no overwrite).")
    p.add_argument("-i", "--input", required=True, help="DICOM input root directory")
    p.add_argument("-o", "--output", required=True, help="NIfTI output directory")
    p.add_argument("--phase-map", default="phase_map.yaml", help="phase_map.yaml path")
    p.add_argument("--prefix", default="", help="output nifti filename prefix (optional)")
    p.add_argument("--use-series-description", action="store_true", help="use SeriesDescription in output filename")
    p.add_argument("--max-spacing", type=float, default=5.0, help="max spacing among x/y/z (mm) to keep")
    p.add_argument("--min-slices", type=int, default=16, help="min number of slices to keep")
    p.add_argument("--no-localizer-filter", action="store_true", help="disable localizer/scout filtering")
    p.add_argument("--filter-patient-position", action="store_true", help="filter by PatientPosition (e.g. keep HFS only)")
    p.add_argument("--allowed-patient-positions", default="HFS", help="allowed PatientPosition values, comma separated")
    p.add_argument("--no-skip-exists", action="store_true", help="do not skip existing outputs (still never overwrite)")
    args = p.parse_args()

    cfg = ConversionConfig(
        input_dir=args.input,
        output_dir=args.output,
        phase_map_path=args.phase_map,
        output_prefix=args.prefix,
        use_series_description_in_name=bool(args.use_series_description),
        max_spacing_mm=args.max_spacing,
        min_slices=args.min_slices,
        enable_localizer_filter=not args.no_localizer_filter,
        enable_patient_position_filter=bool(args.filter_patient_position),
        allowed_patient_positions=str(args.allowed_patient_positions),
        skip_if_exists=not args.no_skip_exists,
    )

    def log(s: str) -> None:
        print(s, flush=True)

    run_conversion(cfg, log=log)


if __name__ == "__main__":
    main()

