# Selective Multi-Clip Live Photo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户选择目标设备、用六十进制时间编辑多个独立片段，并修复 Windows 深色主题下消息框文字不可读的问题。

**Architecture:** 保留 `Converter.convert()` 一次处理一个片段的边界，在核心模型中加入输出目标和角色化成品，在流水线内部只生成一次共用媒体并选择性封装。GUI 使用共享时间编辑区管理多个 `ClipSegment`，后台批量工作线程按顺序调用转换器并聚合进度。

**Tech Stack:** Python 3.10+、PySide6、FFmpeg/imageio-ffmpeg、Pillow、pytest、Git。

## Global Constraints

- 每个片段必须分别生成独立成品目录，不拼接片段。
- GUI 目标设备默认全部未选，开始转换前至少选择一个。
- CLI 为向后兼容，在未传 `--target` 时仍生成全部目标。
- 最终目录只包含所选目标文件、`manifest.json` 和 `使用说明.txt`。
- 时间显示使用 `MM:SS.cc`，一小时以上使用 `HH:MM:SS.cc`，内部仍使用浮点秒。
- 当前实现和测试不得推送 GitHub。
- 所有生产代码必须先有能因缺少相应行为而失败的测试。

---

## File Structure

- Create `livephoto/ui/time_spinbox.py`: 六十进制时间格式化、解析和 Qt 控件。
- Modify `livephoto/core/models.py`: 输出目标、片段、角色化输出模型。
- Modify `livephoto/core/pipeline.py`: 共享中间媒体、选择性封装、动态说明和 manifest v3。
- Modify `livephoto/ui/worker.py`: 多片段顺序执行、总进度和取消。
- Modify `livephoto/ui/main_window.py`: 设备复选框、片段列表、时间控件和批量转换交互。
- Modify `livephoto/ui/theme.py`: 高对比度消息框样式和新增控件样式。
- Modify `livephoto/cli.py`: 可重复使用的 `--target` 参数。
- Modify `scripts/verify_bundle.py`: 按 manifest 目标选择性校验。
- Modify `tests/test_models.py`: 新数据模型行为。
- Modify `tests/test_pipeline.py`: 选择性输出、manifest 和清理。
- Create `tests/test_time_spinbox.py`: 时间格式、解析和控件往返。
- Modify `tests/test_ui.py`: 设备选择、片段管理、忙碌状态、批量工作线程和样式。
- Modify `tests/test_cli.py`: CLI 目标参数和新 bundle 模型。
- Modify `tests/test_scripts.py`: 选择性验证器角色规则。
- Modify `README.md`, `docs/ARCHITECTURE.md`, `docs/COMPATIBILITY.md`, `docs/PROJECT_CODE_AND_GIT_GUIDE.md`: 同步行为说明。

---

### Task 1: Prepare a Reproducible Local Test Environment

**Files:**
- Read: `requirements-dev.txt`
- Create locally but keep ignored: `.venv/`

**Interfaces:**
- Consumes: Python at `D:\anaconda3\python.exe` and `requirements-dev.txt`.
- Produces: `.venv\Scripts\python.exe` with all test and UI dependencies.

- [ ] **Step 1: Confirm the current dependency failure**

Run:

```powershell
D:\anaconda3\python.exe -c "import PySide6"
```

Expected: FAIL with `ModuleNotFoundError: No module named 'PySide6'`.

- [ ] **Step 2: Create and populate the ignored virtual environment**

Run:

```powershell
D:\anaconda3\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Expected: dependencies install successfully; `.venv` remains absent from `git status --short`.

- [ ] **Step 3: Establish the baseline**

Run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: existing suite passes before production changes.

---

### Task 2: Add Target, Segment, and Role-Based Output Models

**Files:**
- Modify: `tests/test_models.py`
- Modify: `livephoto/core/models.py`

**Interfaces:**
- Produces: `OUTPUT_TARGETS`, `TARGET_ORDER`, `ClipSegment`, `OutputFile`, updated `ConversionOptions`, updated `OutputBundle`.
- `OutputBundle.by_role(role: str) -> Path | None` is consumed by UI, CLI and pipeline tests.

- [ ] **Step 1: Write failing model tests**

Add tests equivalent to:

```python
def test_options_validate_selected_targets():
    make_options(targets=frozenset({"vivo", "windows"})).validate(8.0)
    with pytest.raises(ValueError, match="至少选择"):
        make_options(targets=frozenset()).validate(8.0)
    with pytest.raises(ValueError, match="输出目标"):
        make_options(targets=frozenset({"unknown"})).validate(8.0)

def test_clip_segment_reuses_time_validation():
    ClipSegment(2.0, 3.0, 3.5).validate(8.0)
    with pytest.raises(ValueError, match="超出视频时长"):
        ClipSegment(7.0, 2.0, 7.5).validate(8.0)

def test_output_bundle_resolves_only_existing_roles(tmp_path):
    photo = tmp_path / "IMG.jpg"
    manifest = tmp_path / "manifest.json"
    instructions = tmp_path / "使用说明.txt"
    bundle = OutputBundle(
        tmp_path,
        (OutputFile("vivo_live_photo_image", photo),),
        manifest,
        instructions,
    )
    assert bundle.by_role("vivo_live_photo_image") == photo
    assert bundle.by_role("iphone_photo") is None
    assert bundle.files == (photo, manifest, instructions)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_models.py -q
```

Expected: FAIL because the new model names and `targets` field do not exist.

- [ ] **Step 3: Implement the models**

Implement these public shapes in `models.py`:

```python
QUALITY_LEVELS = frozenset({"fast", "balanced", "high"})
TARGET_ORDER = ("iphone", "android", "vivo", "windows")
OUTPUT_TARGETS = frozenset(TARGET_ORDER)

@dataclass(frozen=True, slots=True)
class ClipSegment:
    start_time: float = 0.0
    duration: float = 3.0
    cover_time: float = 1.5

    def validate(self, source_duration: float) -> None:
        _validate_clip(self.start_time, self.duration, self.cover_time, source_duration)

@dataclass(frozen=True, slots=True)
class ConversionOptions:
    # retain existing fields in their current order
    targets: frozenset[str] = OUTPUT_TARGETS
    segment_label: str = ""

    def validate(self, source_duration: float) -> None:
        _validate_clip(self.start_time, self.duration, self.cover_time, source_duration)
        if self.quality not in QUALITY_LEVELS:
            raise ValueError("画质档位无效")
        if not self.targets:
            raise ValueError("请至少选择一种兼容设备")
        if not self.targets <= OUTPUT_TARGETS:
            raise ValueError("输出目标无效")

@dataclass(frozen=True, slots=True)
class OutputFile:
    role: str
    path: Path

@dataclass(frozen=True, slots=True)
class OutputBundle:
    directory: Path
    outputs: tuple[OutputFile, ...]
    manifest: Path
    instructions: Path

    def by_role(self, role: str) -> Path | None:
        return next((item.path for item in self.outputs if item.role == role), None)

    @property
    def files(self) -> tuple[Path, ...]:
        return tuple(item.path for item in self.outputs) + (self.manifest, self.instructions)
```

Move current time validation into `_validate_clip(...)` so `ClipSegment` and `ConversionOptions` share exactly one rule set.

- [ ] **Step 4: Run the model tests and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_models.py -q`

Expected: PASS.

- [ ] **Step 5: Commit locally**

```powershell
git add livephoto\core\models.py tests\test_models.py
git commit -m "feat: model selective outputs and clips"
```

---

### Task 3: Generate Only Selected Platform Outputs

**Files:**
- Modify: `tests/test_pipeline.py`
- Modify: `livephoto/core/pipeline.py`

**Interfaces:**
- Consumes: `ConversionOptions.targets`, `ConversionOptions.segment_label`, `OutputFile`, `OutputBundle`.
- Produces: manifest schema 3 with ordered `targets`, optional platform IDs, and actual output roles only.

- [ ] **Step 1: Replace the old all-target test with failing selective tests**

Add parameterized expectations:

```python
@pytest.mark.parametrize(
    ("targets", "expected_roles", "forbidden_calls"),
    [
        (frozenset({"iphone"}), {"iphone_photo", "iphone_video", "instructions"}, {"android", "vivo:45"}),
        (frozenset({"android"}), {"android_motion_photo", "instructions"}, {"apple-jpeg", "apple-mov", "vivo:45"}),
        (frozenset({"vivo"}), {"vivo_live_photo_image", "vivo_live_photo_video", "instructions"}, {"apple-jpeg", "apple-mov", "android"}),
        (frozenset({"windows"}), {"windows_photo", "windows_video", "instructions"}, {"apple-jpeg", "apple-mov", "android", "vivo:45"}),
    ],
)
def test_converter_generates_only_selected_targets(tmp_path, targets, expected_roles, forbidden_calls):
    calls = []
    conversion = options(tmp_path, targets=targets)
    bundle = Converter(Toolchain(Path("ffmpeg")), **fake_dependencies(calls)).convert(conversion)
    manifest = json.loads(bundle.manifest.read_text(encoding="utf-8"))
    assert {item["role"] for item in manifest["files"]} == expected_roles
    assert {item.role for item in bundle.outputs} == expected_roles - {"instructions"}
    assert not forbidden_calls.intersection(calls)
    assert manifest["schema_version"] == 3
    assert manifest["targets"] == [target for target in TARGET_ORDER if target in targets]
```

Also add tests asserting exactly one video transcode and one cover extraction for multi-target conversion, dynamic instructions omit unselected headings, a segment label appears in the directory, and failure/cancellation leave no temporary directory.

- [ ] **Step 2: Run pipeline tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py -q`

Expected: FAIL because the pipeline still creates every platform output and schema version 2.

- [ ] **Step 3: Implement an internal path map and conditional verification**

Use role keys rather than an all-required bundle:

```python
def _output_paths(root: Path, stem: str, vivo_stem: str) -> dict[str, Path]:
    return {
        "iphone_photo": root / f"{stem}.jpg",
        "iphone_video": root / f"{stem}.mov",
        "android_motion_photo": root / f"{stem}MP.jpg",
        "vivo_live_photo_image": root / f"{vivo_stem}.jpg",
        "vivo_live_photo_video": root / f"{vivo_stem}.mp4",
        "windows_photo": root / f"{stem}_Windows封面.jpg",
        "windows_video": root / f"{stem}_Windows.mp4",
    }

def _verify_outputs(paths: Mapping[str, Path], targets: frozenset[str], asset_id: str | None, vivo_id: str | None) -> None:
    if "iphone" in targets:
        jpeg_id = inspect_live_jpeg(paths["iphone_photo"])
        mov_info = inspect_live_mov(paths["iphone_video"])
        if jpeg_id != asset_id or mov_info.asset_id != asset_id:
            raise ValueError("iPhone 配对文件的资产标识不一致")
        if mov_info.sample_value != -1:
            raise ValueError("iPhone MOV 的封面定时样本无效")
    if "android" in targets:
        inspect_motion_photo(paths["android_motion_photo"])
    if "vivo" in targets:
        vivo_info = verify_vivo_pair(
            paths["vivo_live_photo_image"], paths["vivo_live_photo_video"]
        )
        if vivo_info.live_photo_id != vivo_id:
            raise ValueError("vivo/iQOO 配对文件的资产标识不一致")
```

Tests must inject one `verify_fn(paths, targets, asset_id, vivo_id)` callable and record which targets were verified.

- [ ] **Step 4: Implement shared intermediate media and selected packaging**

Inside the temporary directory use `.common.mp4` and `.common.jpg`. Run one `build_transcode_command` and one `build_cover_command`, then:

```python
if "windows" in targets:
    shutil.copy2(common_photo, paths["windows_photo"])
    shutil.copy2(common_video, paths["windows_video"])
if "iphone" in targets:
    self.apple_jpeg_fn(common_photo, paths["iphone_photo"], asset_id)
    self.apple_mov_fn(common_video, paths["iphone_video"], asset_id, relative_cover, options.duration)
if "android" in targets:
    self.motion_fn(common_photo, common_video, paths["android_motion_photo"], presentation_us)
if "vivo" in targets:
    self.vivo_fn(common_photo, common_video, paths["vivo_live_photo_image"], paths["vivo_live_photo_video"], live_photo_id=vivo_id, image_time=image_time)
```

Unlink common files before manifest creation. Build `OutputFile` objects only for existing selected paths.

- [ ] **Step 5: Implement selected instructions and manifest v3**

Split instructions into a shared heading and four named sections. Include a platform section only when its target is selected. Write manifest fields:

```python
"schema_version": 3,
"segment_label": options.segment_label,
"targets": [target for target in TARGET_ORDER if target in options.targets],
"asset_id": asset_id,
"vivo_live_photo_id": vivo_id,
```

The `files` list contains selected `OutputFile` records plus `instructions` and never contains common temp paths.

- [ ] **Step 6: Run pipeline tests and the related core tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py tests\test_apple.py tests\test_android.py tests\test_vivo.py tests\test_transcode.py -q
```

Expected: PASS with monotonic progress ending at 100.

- [ ] **Step 7: Commit locally**

```powershell
git add livephoto\core\pipeline.py tests\test_pipeline.py
git commit -m "feat: generate selected device outputs"
```

---

### Task 4: Add the Sexagesimal Time Spin Box

**Files:**
- Create: `tests/test_time_spinbox.py`
- Create: `livephoto/ui/time_spinbox.py`

**Interfaces:**
- Produces: `format_time(seconds: float) -> str`, `parse_time(text: str) -> float`, `TimeSpinBox`.
- Consumed by `MainWindow._time_spin()` and segment summaries.

- [ ] **Step 1: Write failing pure-function and widget tests**

```python
@pytest.mark.parametrize(("seconds", "text"), [
    (3.0, "00:03.00"),
    (85.5, "01:25.50"),
    (3723.5, "01:02:03.50"),
])
def test_format_time(seconds, text):
    assert format_time(seconds) == text

@pytest.mark.parametrize(("text", "seconds"), [
    ("01:25.50", 85.5),
    ("01:02:03.50", 3723.5),
    ("3.25", 3.25),
])
def test_parse_time(text, seconds):
    assert parse_time(text) == pytest.approx(seconds)

def test_time_spin_box_round_trip(app):
    spin = TimeSpinBox()
    spin.setValue(85.5)
    assert spin.text() == "01:25.50"
    assert spin.valueFromText("02:03.40") == pytest.approx(123.4)
```

Add invalid cases for empty strings, seconds `>= 60` in colon format, and minutes `>= 60` in three-field format.

- [ ] **Step 2: Run and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_time_spinbox.py -q`

Expected: collection FAIL because `livephoto.ui.time_spinbox` does not exist.

- [ ] **Step 3: Implement formatting, parsing, validation, and the widget**

```python
def format_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, rest = divmod(centiseconds, 360_000)
    minutes, rest = divmod(rest, 6_000)
    whole_seconds, fraction = divmod(rest, 100)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"
    return f"{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"

class TimeSpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(2)
        self.setSingleStep(0.1)
        self.setRange(0.0, 99_999.0)

    def textFromValue(self, value: float) -> str:
        return format_time(value)

    def valueFromText(self, text: str) -> float:
        return parse_time(text)

    def validate(self, text: str, position: int):
        # return Acceptable for parseable complete values,
        # Intermediate for digits/colon/dot prefixes, Invalid otherwise
```

The parser raises `ValueError` only as a pure function; the Qt override converts incomplete input into validator states.

- [ ] **Step 4: Run and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_time_spinbox.py -q`

Expected: PASS.

- [ ] **Step 5: Commit locally**

```powershell
git add livephoto\ui\time_spinbox.py tests\test_time_spinbox.py
git commit -m "feat: add sexagesimal time input"
```

---

### Task 5: Add Sequential Batch Conversion

**Files:**
- Modify: `tests/test_ui.py`
- Modify: `livephoto/ui/worker.py`

**Interfaces:**
- Produces: `BatchConversionWorker(converter, options: tuple[ConversionOptions, ...])`.
- Signals: `progress(int, str)`, `completed(tuple[OutputBundle, ...])`, `failed(str)`, `finished()`.

- [ ] **Step 1: Write failing worker tests**

Create a fake converter that records segment labels and emits `[0, 50, 100]`. Assert:

```python
assert calls == ["片段01", "片段02"]
assert progress == [
    (0, "[片段 1/2] 开始"),
    (25, "[片段 1/2] 处理中"),
    (50, "[片段 1/2] 完成"),
    (50, "[片段 2/2] 开始"),
    (75, "[片段 2/2] 处理中"),
    (100, "[片段 2/2] 完成"),
]
assert completed == [(bundle1, bundle2)]
```

Add cancellation and “片段 2：planned failure” tests.

- [ ] **Step 2: Run and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_ui.py -k batch -q`

Expected: FAIL because `BatchConversionWorker` does not exist.

- [ ] **Step 3: Implement the batch worker**

```python
class BatchConversionWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def run(self) -> None:
        bundles = []
        total = len(self.options)
        try:
            for index, option in enumerate(self.options):
                if self._cancel.is_set():
                    raise RuntimeError("用户取消了转换")
                prefix = f"[片段 {index + 1}/{total}]"
                bundle = self.converter.convert(
                    option,
                    progress=lambda value, text, i=index, p=prefix: self.progress.emit(
                        round((i + value / 100) / total * 100), f"{p} {text}"
                    ),
                    cancel=self._cancel.is_set,
                )
                bundles.append(bundle)
            self.completed.emit(tuple(bundles))
        except Exception as exc:
            message = str(exc) if "取消" in str(exc) else f"片段 {len(bundles) + 1}：{exc}"
            self.failed.emit(message)
        finally:
            self.finished.emit()
```

Keep `cancel()` backed by one shared `threading.Event`.

- [ ] **Step 4: Run and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_ui.py -k batch -q`

Expected: PASS.

- [ ] **Step 5: Commit locally**

```powershell
git add livephoto\ui\worker.py tests\test_ui.py
git commit -m "feat: convert multiple clips sequentially"
```

---

### Task 6: Build Device Selection and Multi-Clip UI

**Files:**
- Modify: `tests/test_ui.py`
- Modify: `livephoto/ui/main_window.py`

**Interfaces:**
- Consumes: `ClipSegment`, `TARGET_ORDER`, `TimeSpinBox`, `format_time`, `BatchConversionWorker`.
- Produces UI attributes: `segment_list`, `add_segment_button`, `remove_segment_button`, `target_checks: dict[str, QCheckBox]`.

- [ ] **Step 1: Write failing control and initial-state tests**

Assert that:

```python
assert window.segment_list.count() == 1
assert window.segment_list.currentRow() == 0
assert window.start_spin.text() == "00:00.00"
assert all(not box.isChecked() for box in window.target_checks.values())
assert window.convert_button.isEnabled() is False
```

After selecting `vivo`, providing valid input/output and applying `VideoInfo`, assert the button becomes enabled.

- [ ] **Step 2: Run and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_ui.py -k "workflow_controls or target" -q`

Expected: FAIL because new controls and time display do not exist.

- [ ] **Step 3: Replace time widgets and add the target card**

Use `TimeSpinBox` in `_time_spin()`. Add target checkboxes with stable keys:

```python
TARGET_LABELS = {
    "iphone": "iPhone / iPad",
    "android": "标准 Android",
    "vivo": "vivo / iQOO",
    "windows": "Windows",
}
self.target_checks = {}
for target in TARGET_ORDER:
    box = QCheckBox(TARGET_LABELS[target])
    box.stateChanged.connect(self.update_action_state)
    self.target_checks[target] = box
```

Insert this card before the save-location card and renumber later cards.

- [ ] **Step 4: Write failing add/switch/delete tests**

Exercise real controls:

```python
window.apply_video_info(VideoInfo(20.0, 1920, 1080, 30.0, True))
window.start_spin.setValue(2.0)
window.duration_spin.setValue(3.0)
window.cover_spin.setValue(3.0)
window.add_segment()
assert window.segment_list.count() == 2
assert window.start_spin.value() == 5.0
window.segment_list.setCurrentRow(0)
assert window.start_spin.value() == 2.0
window.remove_segment()
assert window.segment_list.count() == 1
assert window.remove_segment_button.isEnabled() is False
```

- [ ] **Step 5: Run and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_ui.py -k segment -q`

Expected: FAIL because segment methods do not exist.

- [ ] **Step 6: Implement segment persistence and list summaries**

Maintain:

```python
self._segments = [ClipSegment()]
self._current_segment_index = 0
self._loading_segment = False
```

Implement the state transition methods with these exact responsibilities:

```python
def _save_current_segment(self) -> None:
    if self._loading_segment or not 0 <= self._current_segment_index < len(self._segments):
        return
    self._segments[self._current_segment_index] = ClipSegment(
        self.start_spin.value(), self.duration_spin.value(), self.cover_spin.value()
    )
    self._refresh_segment_list()

def _segment_selected(self, row: int) -> None:
    if row < 0 or row == self._current_segment_index:
        return
    self._save_current_segment()
    self._current_segment_index = row
    self._load_segment(row)

def remove_segment(self) -> None:
    if len(self._segments) == 1:
        return
    index = self._current_segment_index
    del self._segments[index]
    self._current_segment_index = min(index, len(self._segments) - 1)
    self._refresh_segment_list()
    self._load_segment(self._current_segment_index)
```

`_load_segment` blocks spin-box signals while loading all three values, then calls `_start_changed`, `_duration_changed`, and `_cover_changed` once to synchronize ranges and sliders. `_refresh_segment_list` blocks list signals, replaces each summary with `片段 N　开始 → 结束　封面 time`, restores the current row, and enables deletion only when the list contains more than one item. `add_segment` follows the default-start and remaining-duration rules from the approved design and immediately loads the appended item.

- [ ] **Step 7: Write failing batch-start tests**

Monkeypatch `BatchConversionWorker` and assert `start_conversion()` passes one `ConversionOptions` per segment, identical selected target sets, sequential labels `片段01`, `片段02`, and one shared output directory.

- [ ] **Step 8: Run and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_ui.py -k start_conversion -q`

Expected: FAIL because the window still creates a single `ConversionWorker`.

- [ ] **Step 9: Integrate validation, batch worker and completion handling**

Build options with:

```python
targets = frozenset(key for key, box in self.target_checks.items() if box.isChecked())
options = tuple(
    ConversionOptions(
        input_path=input_path,
        output_dir=output_dir,
        start_time=segment.start_time,
        duration=segment.duration,
        cover_time=segment.cover_time,
        mute=self.mute_check.isChecked(),
        quality=str(self.quality_combo.currentData()),
        targets=targets,
        segment_label=f"片段{index:02d}" if len(self._segments) > 1 else "",
    )
    for index, segment in enumerate(self._segments, start=1)
)
```

Use `BatchConversionWorker`; `_on_completed` accepts a tuple, logs every directory, sets `_result_dir` to the common output root, and reports the generated count.

- [ ] **Step 10: Update busy-state coverage and run UI tests**

Include list/buttons/checks in `set_busy`. Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ui.py tests\test_time_spinbox.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit locally**

```powershell
git add livephoto\ui\main_window.py tests\test_ui.py
git commit -m "feat: select devices and edit multiple clips"
```

---

### Task 7: Fix Message Box Contrast

**Files:**
- Modify: `tests/test_ui.py`
- Modify: `livephoto/ui/theme.py`

**Interfaces:**
- Produces: explicit `QMessageBox`, `QMessageBox QLabel`, and `QMessageBox QPushButton` colors in `APP_STYLE`.

- [ ] **Step 1: Write the failing style regression test**

```python
def test_message_boxes_have_explicit_high_contrast_colors():
    assert "QMessageBox { background: #f4f7fb;" in APP_STYLE
    assert "QMessageBox QLabel { color: #17233c;" in APP_STYLE
    assert "QMessageBox QPushButton" in APP_STYLE
    assert "color: #17233c" in message_button_rule
```

Parse the relevant selector block rather than passing because the same color occurs elsewhere.

- [ ] **Step 2: Run and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_ui.py -k message_boxes -q`

Expected: FAIL because no `QMessageBox` selector exists.

- [ ] **Step 3: Add complete message-box styles**

```css
QMessageBox { background: #f4f7fb; }
QMessageBox QLabel { color: #17233c; background: transparent; min-width: 260px; }
QMessageBox QPushButton {
    min-width: 76px; background: #ffffff; color: #17233c;
    border: 1px solid #9db2ce;
}
QMessageBox QPushButton:hover { background: #edf5ff; border-color: #1769e0; }
QMessageBox QPushButton:pressed { background: #dcecff; }
QMessageBox QPushButton:focus { border: 2px solid #1769e0; }
```

- [ ] **Step 4: Run and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_ui.py -k message_boxes -q`

Expected: PASS.

- [ ] **Step 5: Commit locally**

```powershell
git add livephoto\ui\theme.py tests\test_ui.py
git commit -m "fix: improve message box contrast"
```

---

### Task 8: Update CLI and the Independent Bundle Verifier

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `tests/test_scripts.py`
- Modify: `livephoto/cli.py`
- Modify: `scripts/verify_bundle.py`

**Interfaces:**
- CLI produces `ConversionOptions.targets` from repeated `--target` values.
- Verifier consumes manifest v3 `targets` and verifies only the required role set.

- [ ] **Step 1: Write failing CLI and verifier tests**

```python
args = build_parser().parse_args([
    "convert", "input.mp4", "--output", "out",
    "--target", "vivo", "--target", "windows",
])
assert args.target == ["vivo", "windows"]
```

Assert `main()` passes `frozenset({"vivo", "windows"})`, while omitting flags passes `OUTPUT_TARGETS`. Replace the fixed `REQUIRED_ROLES` test with target-to-role mapping tests.

- [ ] **Step 2: Run and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_cli.py tests\test_scripts.py -q`

Expected: FAIL because `--target` and selective verification do not exist.

- [ ] **Step 3: Implement repeatable CLI targets**

```python
convert.add_argument(
    "--target",
    action="append",
    choices=TARGET_ORDER,
    help="输出目标，可重复使用；默认生成全部",
)
# when constructing options
targets=frozenset(args.target) if args.target else OUTPUT_TARGETS,
```

Update fake `OutputBundle` construction to use `OutputFile` tuples.

- [ ] **Step 4: Make verification role-driven**

Define:

```python
TARGET_ROLES = {
    "iphone": {"iphone_photo", "iphone_video"},
    "android": {"android_motion_photo"},
    "vivo": {"vivo_live_photo_image", "vivo_live_photo_video"},
    "windows": {"windows_photo", "windows_video"},
}
```

Expected roles are the union for manifest targets plus `instructions`. Always verify hashes and images. Run Apple, Android and vivo structural checks only if their roles exist. Probe and codec-check every existing video role independently; do not require a Windows MP4 to validate another platform.

- [ ] **Step 5: Run and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_cli.py tests\test_scripts.py -q`

Expected: PASS.

- [ ] **Step 6: Commit locally**

```powershell
git add livephoto\cli.py scripts\verify_bundle.py tests\test_cli.py tests\test_scripts.py
git commit -m "feat: expose targets in CLI and verifier"
```

---

### Task 9: Update Documentation and Static Repository Checks

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/COMPATIBILITY.md`
- Modify: `docs/PROJECT_CODE_AND_GIT_GUIDE.md`
- Modify: `tests/test_documentation.py`

**Interfaces:**
- Documents the implemented GUI, CLI, file roles and manifest v3 behavior.

- [ ] **Step 1: Find stale statements before editing**

Run:

```powershell
Get-ChildItem README.md,docs -Recurse -File -Include *.md | Select-String -Pattern "一次生成|兼容包|schema_version|片段"
```

Expected: old descriptions that imply all devices are always generated.

- [ ] **Step 2: Update exact user workflows and examples**

Document:

- device checkboxes and the at-least-one rule;
- `MM:SS.cc` time entry;
- one output directory per segment;
- selective file table and manifest v3;
- repeated CLI example: `--target vivo --target windows`;
- selected-only instructions and the fact that internal temporary media is cleaned.

- [ ] **Step 3: Run documentation checks**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\check_markdown_links.py
.\.venv\Scripts\python.exe scripts\check_repository.py
.\.venv\Scripts\python.exe -m pytest tests\test_documentation.py tests\test_project_metadata.py tests\test_repository_hygiene.py -q
git diff --check
```

Expected: all checks pass and no trailing whitespace exists.

- [ ] **Step 4: Commit locally**

```powershell
git add README.md docs tests\test_documentation.py
git commit -m "docs: explain selective multi-clip conversion"
```

---

### Task 10: Full Automated, Real-Media, and Visual Verification

**Files:**
- Potentially modify only tests or production files when a newly reproduced defect requires a new RED/GREEN cycle.
- Create ignored local artifacts under `tests\generated\`.

**Interfaces:**
- Consumes the complete application.
- Produces evidence of automated, FFmpeg and visual correctness without pushing GitHub.

- [ ] **Step 1: Run the complete automated suite**

Run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_markdown_links.py
.\.venv\Scripts\python.exe scripts\check_repository.py
git diff --check
```

Expected: every test and checker passes with no warning or traceback.

- [ ] **Step 2: Generate a real test video**

Run:

```powershell
New-Item -ItemType Directory -Path tests\generated -Force | Out-Null
.\.venv\Scripts\python.exe scripts\make_sample_video.py tests\generated\sample.mp4 --duration 8
```

Expected: an 8-second H.264/AAC test file is created in an ignored directory.

- [ ] **Step 3: Run single-target real conversions**

Run separate CLI conversions for `vivo` and `windows`, then verify each directory:

```powershell
.\.venv\Scripts\python.exe -m livephoto convert tests\generated\sample.mp4 --output tests\generated\vivo --target vivo
.\.venv\Scripts\python.exe -m livephoto convert tests\generated\sample.mp4 --output tests\generated\windows --target windows
$vivoDir = (Get-ChildItem -LiteralPath tests\generated\vivo -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
$windowsDir = (Get-ChildItem -LiteralPath tests\generated\windows -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
.\.venv\Scripts\python.exe scripts\verify_bundle.py $vivoDir
.\.venv\Scripts\python.exe scripts\verify_bundle.py $windowsDir
```

Expected: only selected platform roles exist and both verifiers succeed. Resolve actual timestamped directories with `Get-ChildItem`, never a hard-coded timestamp.

- [ ] **Step 4: Run a multi-target real conversion**

Run:

```powershell
.\.venv\Scripts\python.exe -m livephoto convert tests\generated\sample.mp4 --output tests\generated\multi --target iphone --target android --target vivo --target windows
```

Verify the timestamped directory with `scripts\verify_bundle.py`.

Expected: all selected structures validate, source media was transcoded once according to progress/log evidence, and manifest schema is 3.

- [ ] **Step 5: Run the application smoke test**

Run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m livephoto --smoke-test
```

Expected: exit code 0 without a Qt traceback.

- [ ] **Step 6: Capture and inspect UI and completion dialog**

Use `scripts/capture_ui.py tests\generated\main-window.png` for the main window. For the message box, add `--dialog` to `capture_ui.py` in a RED/GREEN cycle: first extend `tests/test_scripts.py` to assert `build_parser().parse_args(["out.png", "--dialog"]).dialog is True`, watch it fail, extract a `build_parser()` function, and make `--dialog` show a child `QMessageBox` carrying the completion text before grabbing that message box into the requested PNG. Run `scripts/capture_ui.py tests\generated\message-box.png --dialog`, then inspect both images.

Expected visual checks:

- four device choices are visible;
- segment add/delete controls and selected segment are clear;
- time values render as `00:03.00` rather than decimal seconds with a suffix;
- message-box background is light and text/buttons are clearly readable;
- no text clipping or overlapping controls at the minimum window size.

- [ ] **Step 7: Check local-only Git state and report**

Run:

```powershell
git status --short --branch
git log --oneline origin/main..HEAD
```

Expected: local branch is ahead of `origin/main`; no `git push` is executed. Report all test counts, real conversion paths, screenshots, and remaining limitations to the user.
