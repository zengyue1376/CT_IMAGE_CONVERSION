from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk

from converter import ConversionConfig, NiftiCleanConfig, clean_nifti_by_max_spacing, run_conversion


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PHASE_MAP = os.path.join(APP_DIR, "phase_map.yaml")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DICOM CT → NIfTI 转换工具")
        self.geometry("880x560")

        self._log_q: "queue.Queue[str]" = queue.Queue()
        self._prog_q: "queue.Queue[tuple[int,int]]" = queue.Queue()
        self._worker: threading.Thread | None = None

        self.input_dir = tk.StringVar(value="")
        self.output_dir = tk.StringVar(value="")
        self.phase_map_path = tk.StringVar(value=DEFAULT_PHASE_MAP)

        self.max_thickness = tk.DoubleVar(value=5.0)
        self.min_slices = tk.IntVar(value=16)
        self.enable_localizer = tk.BooleanVar(value=True)
        self.skip_exists = tk.BooleanVar(value=True)
        self.output_prefix = tk.StringVar(value="")
        self.use_series_desc = tk.BooleanVar(value=False)
        self.enable_pos_filter = tk.BooleanVar(value=False)
        self.allowed_positions = tk.StringVar(value="HFS")

        # NIfTI tools tab vars
        self.nifti_dir = tk.StringVar(value="")
        self.nifti_max_spacing = tk.DoubleVar(value=5.0)
        self.nifti_delete = tk.BooleanVar(value=True)

        self._build_ui()
        self.after(100, self._drain_queues)

    def _build_ui(self) -> None:
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        nb = ttk.Notebook(frm)
        nb.pack(fill="x")

        tab_convert = ttk.Frame(nb, padding=10)
        tab_nifti = ttk.Frame(nb, padding=10)
        nb.add(tab_convert, text="DICOM→NIfTI 转换")
        nb.add(tab_nifti, text="NIfTI 处理")

        # --- Tab 1: convert ---
        grid = ttk.Frame(tab_convert)
        grid.pack(fill="x")

        def row(parent, label: str, var: tk.StringVar, browse_cmd):
            r = ttk.Frame(parent)
            r.pack(fill="x", pady=4)
            ttk.Label(r, text=label, width=16).pack(side="left")
            ttk.Entry(r, textvariable=var).pack(side="left", fill="x", expand=True, padx=6)
            ttk.Button(r, text="选择…", command=browse_cmd, width=10).pack(side="left")

        row(grid, "DICOM 输入目录", self.input_dir, self._choose_input)
        row(grid, "NIfTI 输出目录", self.output_dir, self._choose_output)

        r3 = ttk.Frame(grid)
        r3.pack(fill="x", pady=4)
        ttk.Label(r3, text="相位映射文件", width=16).pack(side="left")
        ttk.Entry(r3, textvariable=self.phase_map_path).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r3, text="选择…", command=self._choose_phase_map, width=10).pack(side="left")
        ttk.Button(r3, text="打开编辑", command=self._open_phase_map, width=10).pack(side="left", padx=(6, 0))

        opts = ttk.Labelframe(tab_convert, text="过滤与增量设置", padding=10)
        opts.pack(fill="x", pady=(10, 0))

        o1 = ttk.Frame(opts)
        o1.pack(fill="x", pady=4)
        ttk.Label(o1, text="输出前缀").pack(side="left")
        ttk.Entry(o1, textvariable=self.output_prefix, width=16).pack(side="left", padx=(6, 16))
        ttk.Label(o1, text="最大间距(mm)").pack(side="left")
        ttk.Entry(o1, textvariable=self.max_thickness, width=10).pack(side="left", padx=(6, 16))
        ttk.Label(o1, text="最少切片数").pack(side="left")
        ttk.Entry(o1, textvariable=self.min_slices, width=10).pack(side="left", padx=(6, 16))
        ttk.Checkbutton(o1, text="过滤定位/Scout/Localizer", variable=self.enable_localizer).pack(side="left")

        o2 = ttk.Frame(opts)
        o2.pack(fill="x", pady=4)
        ttk.Checkbutton(o2, text="输出已存在则跳过（不覆盖）", variable=self.skip_exists).pack(side="left")
        ttk.Checkbutton(o2, text="文件名包含 SeriesDescription（prefix_编号_描述）", variable=self.use_series_desc).pack(
            side="left", padx=(16, 0)
        )

        o3 = ttk.Frame(opts)
        o3.pack(fill="x", pady=4)
        ttk.Checkbutton(o3, text="过滤非正常体位（按 PatientPosition）", variable=self.enable_pos_filter).pack(side="left")
        ttk.Label(o3, text="允许体位(逗号分隔)").pack(side="left", padx=(16, 0))
        ttk.Entry(o3, textvariable=self.allowed_positions, width=18).pack(side="left", padx=(6, 0))

        actions1 = ttk.Frame(tab_convert)
        actions1.pack(fill="x", pady=(10, 0))
        self.btn_start = ttk.Button(actions1, text="开始转换", command=self._start)
        self.btn_start.pack(side="left")
        ttk.Button(actions1, text="清空日志", command=self._clear_log).pack(side="left", padx=8)

        # --- Tab 2: nifti tools ---
        grid2 = ttk.Frame(tab_nifti)
        grid2.pack(fill="x")
        row(grid2, "NIfTI 文件夹", self.nifti_dir, self._choose_nifti_dir)

        opts2 = ttk.Labelframe(tab_nifti, text="过滤设置", padding=10)
        opts2.pack(fill="x", pady=(10, 0))
        n1 = ttk.Frame(opts2)
        n1.pack(fill="x", pady=4)
        ttk.Label(n1, text="最大 spacing(mm)").pack(side="left")
        ttk.Entry(n1, textvariable=self.nifti_max_spacing, width=10).pack(side="left", padx=(6, 16))
        ttk.Checkbutton(n1, text="直接删除不符合文件", variable=self.nifti_delete).pack(side="left")

        # 留出后续扩展空间
        ext = ttk.Labelframe(tab_nifti, text="更多功能（预留）", padding=10)
        ext.pack(fill="x", pady=(10, 0))
        ttk.Label(ext, text="后续可在此添加：重采样、重命名、统计、批量检查等。").pack(anchor="w")

        actions2 = ttk.Frame(tab_nifti)
        actions2.pack(fill="x", pady=(10, 0))
        self.btn_nifti_clean = ttk.Button(actions2, text="按 spacing 过滤", command=self._start_nifti_clean)
        self.btn_nifti_clean.pack(side="left")
        ttk.Button(actions2, text="清空日志", command=self._clear_log).pack(side="left", padx=8)

        self.prog = ttk.Progressbar(frm, mode="determinate")
        self.prog.pack(fill="x", pady=(10, 6))
        self.prog_lbl = ttk.Label(frm, text="就绪")
        self.prog_lbl.pack(anchor="w")

        log_box = ttk.Labelframe(frm, text="日志", padding=8)
        log_box.pack(fill="both", expand=True, pady=(10, 0))
        self.txt = tk.Text(log_box, height=18, wrap="none")
        self.txt.pack(fill="both", expand=True)

    def _choose_input(self) -> None:
        d = filedialog.askdirectory(title="选择 DICOM 输入目录")
        if d:
            self.input_dir.set(d)

    def _choose_output(self) -> None:
        d = filedialog.askdirectory(title="选择 NIfTI 输出目录")
        if d:
            self.output_dir.set(d)

    def _choose_nifti_dir(self) -> None:
        d = filedialog.askdirectory(title="选择 NIfTI 文件夹")
        if d:
            self.nifti_dir.set(d)

    def _choose_phase_map(self) -> None:
        p = filedialog.askopenfilename(
            title="选择 phase_map.yaml",
            filetypes=[("YAML", "*.yaml;*.yml"), ("All", "*.*")],
            initialdir=APP_DIR,
        )
        if p:
            self.phase_map_path.set(p)

    def _open_phase_map(self) -> None:
        p = self.phase_map_path.get().strip()
        if not p or not os.path.exists(p):
            messagebox.showerror("错误", "phase_map.yaml 不存在")
            return
        try:
            os.startfile(p)  # type: ignore[attr-defined]
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件：{e}")

    def _clear_log(self) -> None:
        self.txt.delete("1.0", "end")

    def _append_log(self, line: str) -> None:
        self.txt.insert("end", line + "\n")
        self.txt.see("end")

    def _set_progress(self, cur: int, total: int) -> None:
        total = max(total, 1)
        cur = max(0, min(cur, total))
        self.prog["maximum"] = total
        self.prog["value"] = cur
        self.prog_lbl.config(text=f"进度：{cur}/{total}")

    def _start(self) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("提示", "转换正在进行中")
            return

        in_dir = self.input_dir.get().strip()
        out_dir = self.output_dir.get().strip()
        phase_map = self.phase_map_path.get().strip()

        if not in_dir or not os.path.isdir(in_dir):
            messagebox.showerror("错误", "请输入有效的 DICOM 输入目录")
            return
        if not out_dir:
            messagebox.showerror("错误", "请输入 NIfTI 输出目录")
            return
        if not phase_map or not os.path.exists(phase_map):
            messagebox.showerror("错误", "phase_map.yaml 路径无效")
            return

        cfg = ConversionConfig(
            input_dir=in_dir,
            output_dir=out_dir,
            phase_map_path=phase_map,
            output_prefix=self.output_prefix.get().strip(),
            use_series_description_in_name=bool(self.use_series_desc.get()),
            max_spacing_mm=float(self.max_thickness.get()),
            min_slices=int(self.min_slices.get()),
            enable_localizer_filter=bool(self.enable_localizer.get()),
            enable_patient_position_filter=bool(self.enable_pos_filter.get()),
            allowed_patient_positions=self.allowed_positions.get().strip(),
            skip_if_exists=bool(self.skip_exists.get()),
        )

        self.btn_start.config(state="disabled")
        self.btn_nifti_clean.config(state="disabled")
        self._append_log("[INFO] 开始转换…")
        self._set_progress(0, 1)
        self.prog_lbl.config(text="进度：准备中…（扫描可能需要一些时间）")

        def worker():
            try:
                run_conversion(
                    cfg,
                    log=lambda s: self._log_q.put(s),
                    progress=lambda c, t: self._prog_q.put((c, t)),
                )
            except Exception:
                self._log_q.put("[EXCEPTION] 后台任务异常：")
                self._log_q.put(traceback.format_exc())
            finally:
                self._log_q.put("[INFO] 任务结束")
                self._prog_q.put((-1, -1))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _start_nifti_clean(self) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("提示", "有任务正在进行中")
            return

        d = self.nifti_dir.get().strip()
        if not d or not os.path.isdir(d):
            messagebox.showerror("错误", "请输入有效的 NIfTI 文件夹")
            return

        max_s = float(self.nifti_max_spacing.get())
        delete = bool(self.nifti_delete.get())
        if delete:
            ok = messagebox.askyesno("确认删除", "将删除 max spacing 超过阈值的 NIfTI 文件，确认继续？")
            if not ok:
                return

        cfg = NiftiCleanConfig(input_dir=d, max_spacing_mm=max_s, delete=delete)
        self.btn_start.config(state="disabled")
        self.btn_nifti_clean.config(state="disabled")
        self._append_log("[INFO] 开始 NIfTI 过滤…")
        self._set_progress(0, 1)

        def worker():
            try:
                clean_nifti_by_max_spacing(
                    cfg,
                    log=lambda s: self._log_q.put(s),
                    progress=lambda c, t: self._prog_q.put((c, t)),
                )
            except Exception:
                self._log_q.put("[EXCEPTION] 后台任务异常：")
                self._log_q.put(traceback.format_exc())
            finally:
                self._log_q.put("[INFO] 任务结束")
                self._prog_q.put((-1, -1))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _drain_queues(self) -> None:
        try:
            while True:
                line = self._log_q.get_nowait()
                self._append_log(line)
        except queue.Empty:
            pass

        try:
            while True:
                cur, total = self._prog_q.get_nowait()
                if cur == -1 and total == -1:
                    self.btn_start.config(state="normal")
                    self.btn_nifti_clean.config(state="normal")
                    self.prog_lbl.config(text="完成")
                    break
                self._set_progress(cur, total)
        except queue.Empty:
            pass

        self.after(100, self._drain_queues)


if __name__ == "__main__":
    App().mainloop()

