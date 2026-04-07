# ct_image_conversion

一个用于 **CT DICOM → NIfTI(.nii.gz)** 的小工具（Windows 友好），支持：

- 递归扫描任意目录结构的 DICOM
- 常见脏数据过滤：切片数过少、Localizer/Scout、体位过滤（可选）
- 相位识别：通过可编辑的 `phase_map.yaml`（平扫/动脉/静脉/延迟/CTA/Unknown）
- 增量转换：**输出已存在则跳过，绝不覆盖**
- 输出命名包含：相位/层厚（来自最终 NIfTI spacing）、稳定匿名ID、Series短ID
- 转换后端：优先使用 `dcm2niix`（若系统 PATH 可用），否则回退到 SimpleITK(GDCM/ITK)
- 转换后按 NIfTI header 做过滤：按 `max(spacing)` 和 `size[2]` 终筛，不合格会删除刚生成的 NIfTI

## 安装（Python 依赖）

建议用虚拟环境：

**Windows（PowerShell）**

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

可选：将项目目录加入 `PYTHONPATH`，或始终在仓库根目录执行 `python cli.py`，以便能导入 `converter` 包。

## 可选（推荐）：安装 dcm2niix

`dcm2niix` 是**外部可执行文件**（不是 pip 包）。本工具会优先调用它来做 DICOM→NIfTI（更接近常用/3D Slicer 生态转换效果）。

- 要求：`dcm2niix` 在系统 `PATH` 可用
- 验证：

```bash
dcm2niix -h
```

若未安装/不可用，会自动回退到 SimpleITK 后端。

## 命令行（CLI，适合 Linux 服务器）

在仓库根目录执行 `python cli.py`（或 `python3 cli.py`）。支持子命令；**旧写法** `python cli.py -i DICOM_DIR -o OUT_DIR` 仍会自动视为 `convert`。

```bash
# 查看帮助
python cli.py --help
python cli.py convert --help
python cli.py nifti-clean --help
python cli.py nifti-resample --help
```

### `convert`：DICOM → NIfTI

```bash
python cli.py convert -i /data/dicom_root -o /data/nifti_out \
  --phase-map /path/to/phase_map.yaml \
  --max-spacing 5.0 --min-slices 16 \
  --prefix MyStudy
```

常用参数：`--use-series-description`、`--filter-patient-position`、`--allowed-patient-positions HFS,FFS`、`--no-localizer-filter`、`--no-skip-exists`。

与旧版等价（无子命令）：

```bash
python cli.py -i /data/dicom_root -o /data/nifti_out --phase-map phase_map.yaml
```

### `nifti-clean`：按 max(spacing) 删除 NIfTI

**会先建议用 `--dry-run` 只看日志，不删文件。**

```bash
python cli.py nifti-clean -i /data/nifti --max-spacing 5.0 --dry-run
python cli.py nifti-clean -i /data/nifti --max-spacing 5.0
```

### `nifti-resample`：批量重采样到指定 spacing `[x,y,z]` mm

```bash
python cli.py nifti-resample -i /data/nifti_in -o /data/nifti_out --spacing 1,1,1
python cli.py nifti-resample -i /data/nifti_in -o /data/nifti_out --spacing 0.8,0.8,1.5 --interp nearest
```

默认若输出文件已存在则跳过；需要覆盖时加 `--no-skip-exists`。

## 运行（GUI）

```bash
python app.py
```

GUI 顶部有两个 Tab：

- `DICOM→NIfTI 转换`：DICOM 扫描、过滤、相位识别、增量转换
- `NIfTI 处理`：对已有 NIfTI 文件做批量清理/处理（当前支持按 spacing 最大值过滤删除）

### DICOM→NIfTI：过滤说明

- **最大间距(mm)**：按最终输出 NIfTI 的 header spacing 判断
  - 若 `max(spacing) > 阈值`，会删除刚生成的 NIfTI 并在日志标记为跳过
  - 同时会按 NIfTI 的 `size[2]` 再检查最少切片数，不够也会删除并跳过
- **体位过滤（可选）**：按 DICOM `PatientPosition(0018,5100)` 过滤（默认只保留 `HFS`；也可填 `HFS,FFS` 这类逗号分隔列表）

## 相位映射（phase_map.yaml）

默认文件在 `phase_map.yaml`，你可以自行添加你们医院常见的 `SeriesDescription/ProtocolName` 关键词。

规则：只要关键词命中（不区分大小写），就会被归到对应相位；否则为 `unknown`。

## 输出命名规则

默认（编号在相位/层厚之前）：

`{prefix_可选}_{anonId}_{phase}_t{thickness}mm_{seriesId}.nii.gz`

可选（勾选“文件名包含 SeriesDescription”后）：

`{prefix_可选}_{anonId}_{SeriesDescription}_{seriesId}.nii.gz`

- `anonId`：对 `StudyInstanceUID` 做不可逆短哈希（稳定、外观随机）
- `seriesId`：对 `SeriesInstanceUID` 做短哈希（用于区分同一检查下的不同 series）

> 注意：工具不会覆盖已有文件；如果你关闭“输出已存在则跳过”，也只会自动生成 `_dupN` 新文件名。

## NIfTI 处理 Tab（按 spacing 删除）

在 `NIfTI 处理` 页里可以选择一个文件夹，按 NIfTI 的 `max(spacing)` 过滤并删除不符合阈值的文件。

删除操作不可恢复，界面会二次确认；建议先备份，或先把“直接删除不符合文件”取消勾选做试运行。

## 打包成 exe（可选）

安装 pyinstaller 后：

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole app.py
```

生成的可执行文件在 `dist/app.exe`。
