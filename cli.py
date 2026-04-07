from __future__ import annotations

import argparse
import os
import sys

from converter import (
    ConversionConfig,
    NiftiCleanConfig,
    NiftiResampleConfig,
    clean_nifti_by_max_spacing,
    resample_nifti_folder,
    run_conversion,
)

KNOWN_SUBCOMMANDS = frozenset({"convert", "nifti-clean", "nifti-resample"})


def _prepend_convert_if_legacy(argv: list[str]) -> list[str]:
    """兼容旧用法: python cli.py -i DIR -o OUT（无子命令时视为 convert）。"""
    if len(argv) < 2:
        return argv
    first = argv[1]
    if first in KNOWN_SUBCOMMANDS or first in ("-h", "--help"):
        return argv
    if first.startswith("-"):
        return [argv[0], "convert"] + argv[1:]
    return argv


def _cmd_convert(args: argparse.Namespace) -> None:
    cfg = ConversionConfig(
        input_dir=args.input,
        output_dir=args.output,
        phase_map_path=args.phase_map,
        output_prefix=args.prefix or "",
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


def _cmd_nifti_clean(args: argparse.Namespace) -> None:
    cfg = NiftiCleanConfig(
        input_dir=args.input,
        max_spacing_mm=args.max_spacing,
        delete=not args.dry_run,
    )

    def log(s: str) -> None:
        print(s, flush=True)

    clean_nifti_by_max_spacing(cfg, log=log)


def _cmd_nifti_resample(args: argparse.Namespace) -> None:
    parts = [p.strip() for p in args.spacing.split(",")]
    if len(parts) != 3:
        raise SystemExit("--spacing 必须是三个数字，逗号分隔，例如 1,1,1 或 0.8,0.8,1.5")
    try:
        target = (float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError as e:
        raise SystemExit(f"无效的 spacing: {args.spacing}") from e

    cfg = NiftiResampleConfig(
        input_dir=args.input,
        output_dir=args.output,
        target_spacing=target,
        interpolator=args.interp,
        skip_if_exists=not args.no_skip_exists,
    )

    def log(s: str) -> None:
        print(s, flush=True)

    resample_nifti_folder(cfg, log=log)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CT DICOM/NIfTI 批处理 CLI（适合 Linux 服务器无 GUI 使用）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # DICOM → NIfTI（与旧版相同，也可显式写 convert）
  python cli.py convert -i /data/dicom -o /data/nifti --phase-map phase_map.yaml

  # 兼容旧命令（自动视为 convert）
  python cli.py -i /data/dicom -o /data/nifti

  # 删除 max(spacing) 超过阈值的 NIfTI（危险：先 --dry-run 预览）
  python cli.py nifti-clean -i /data/nifti --max-spacing 5.0 --dry-run
  python cli.py nifti-clean -i /data/nifti --max-spacing 5.0

  # 重采样到指定 spacing (x,y,z mm)
  python cli.py nifti-resample -i /data/in -o /data/out --spacing 1,1,1
  python cli.py nifti-resample -i /data/in -o /data/out --spacing 0.8,0.8,1.5 --interp nearest
""",
    )
    sub = parser.add_subparsers(dest="command", required=True, help="子命令")

    p_conv = sub.add_parser("convert", help="DICOM 递归扫描 → NIfTI（dcm2niix 优先）")
    p_conv.add_argument("-i", "--input", required=True, help="DICOM 根目录")
    p_conv.add_argument("-o", "--output", required=True, help="NIfTI 输出目录")
    p_conv.add_argument("--phase-map", default="phase_map.yaml", help="phase_map.yaml 路径")
    p_conv.add_argument("--prefix", default="", help="输出文件名前缀（可选）")
    p_conv.add_argument("--use-series-description", action="store_true", help="文件名包含 SeriesDescription")
    p_conv.add_argument("--max-spacing", type=float, default=5.0, help="NIfTI 终筛：max(spacing) 上限 (mm)")
    p_conv.add_argument("--min-slices", type=int, default=16, help="最少切片数（DICOM 预筛 + NIfTI size[2] 终筛）")
    p_conv.add_argument("--no-localizer-filter", action="store_true", help="关闭 Localizer/Scout 过滤")
    p_conv.add_argument("--filter-patient-position", action="store_true", help="按 PatientPosition 过滤")
    p_conv.add_argument(
        "--allowed-patient-positions",
        default="HFS",
        help="允许的体位，逗号分隔，如 HFS 或 HFS,FFS",
    )
    p_conv.add_argument("--no-skip-exists", action="store_true", help="输出已存在仍转换（仍不覆盖，会 _dupN）")
    p_conv.set_defaults(_handler=_cmd_convert)

    p_clean = sub.add_parser("nifti-clean", help="按 NIfTI max(spacing) 删除不合格文件")
    p_clean.add_argument("-i", "--input", required=True, help="NIfTI 根目录（递归）")
    p_clean.add_argument("--max-spacing", type=float, required=True, help="超过该 max(spacing)(mm) 则删除")
    p_clean.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 [HIT]/[KEEP]，不删除文件",
    )
    p_clean.set_defaults(_handler=_cmd_nifti_clean)

    p_rs = sub.add_parser("nifti-resample", help="批量重采样到目标 spacing (x,y,z mm)")
    p_rs.add_argument("-i", "--input", required=True, help="输入 NIfTI 根目录（递归）")
    p_rs.add_argument("-o", "--output", required=True, help="输出根目录（保持相对路径结构）")
    p_rs.add_argument(
        "--spacing",
        required=True,
        help="目标 spacing，逗号分隔，如 1,1,1 或 0.8,0.8,1.5",
    )
    p_rs.add_argument(
        "--interp",
        choices=["linear", "nearest"],
        default="linear",
        help="插值方式（分割标签请用 nearest）",
    )
    p_rs.add_argument(
        "--no-skip-exists",
        action="store_true",
        help="输出已存在也重写（默认跳过已存在）",
    )
    p_rs.set_defaults(_handler=_cmd_nifti_resample)

    return parser


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        build_parser().print_help()
        return
    argv = _prepend_convert_if_legacy(sys.argv)
    parser = build_parser()
    args = parser.parse_args(argv[1:])
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        raise SystemExit(2)
    handler(args)


if __name__ == "__main__":
    main()
