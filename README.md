# ct_image_conversion

一个用于 **CT DICOM → NIfTI(.nii.gz)** 的小工具（Windows 友好），支持：

- 递归扫描任意目录结构的 DICOM
- 常见脏数据过滤：层厚过大、切片数过少、Localizer/Scout
- 相位识别：通过可编辑的 `phase_map.yaml`（平扫/动脉/静脉/延迟/CTA/Unknown）
- 增量转换：**输出已存在则跳过，绝不覆盖**
- 输出命名包含：相位、层厚、稳定匿名ID、Series短ID
- 转换后端：优先使用 `dcm2niix`（若系统 PATH 可用），否则回退到 SimpleITK(GDCM)

## 安装

建议用虚拟环境：

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行（GUI）

```bash
python app.py
```

GUI 里可以填写“**输出前缀**”，它会出现在所有 NIfTI 文件名最前面（会自动清洗非法字符）。

GUI 顶部有两个 Tab：\n+- `DICOM→NIfTI 转换`：DICOM 扫描、过滤、相位识别、增量转换\n+- `NIfTI 处理`：对已有 NIfTI 文件做批量清理/处理（当前支持按 spacing 最大值过滤删除）\n+
过滤阈值里“最大间距(mm)”指 **X/Y/Z 三个方向间距的最大值**（即 `max(pixel_spacing_row, pixel_spacing_col, slice_spacing)`）不超过该阈值才保留。

其中 Z 方向 `slice_spacing` 会优先用**相邻切片的 `ImagePositionPatient` 差值（结合 `ImageOrientationPatient` 计算法向投影）**推算得到；推算失败才回退到 `SpacingBetweenSlices/SliceThickness`。

可选：开启“过滤非正常体位”后，会按 DICOM `PatientPosition(0018,5100)` 过滤（默认只保留 `HFS`；也可填 `HFS,FFS` 这类逗号分隔列表）。

## 相位映射（phase_map.yaml）

默认文件在 `phase_map.yaml`，你可以自行添加你们医院常见的 `SeriesDescription/ProtocolName` 关键词。

规则：只要关键词命中（不区分大小写），就会被归到对应相位；否则为 `unknown`。

## 输出命名规则

输出文件名形如：

默认（编号在相位/层厚之前）：

`{prefix_可选}_{anonId}_{phase}_t{thickness}mm_{seriesId}.nii.gz`

可选（勾选“文件名包含 SeriesDescription”后）：

`{prefix_可选}_{anonId}_{SeriesDescription}_{seriesId}.nii.gz`

- `anonId`：对 `StudyInstanceUID` 做不可逆短哈希（稳定、外观随机）\n+- `seriesId`：对 `SeriesInstanceUID` 做短哈希（用于区分同一检查下的不同 series）\n+
> 注意：工具不会覆盖已有文件；如果你关闭“输出已存在则跳过”，也只会自动生成 `_dupN` 新文件名。

## 打包成 exe（可选）

安装 pyinstaller 后：

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole app.py
```

生成的可执行文件在 `dist/app.exe`。\n
