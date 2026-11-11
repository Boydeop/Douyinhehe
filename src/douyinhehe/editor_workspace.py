"""A practical local video editor: playable media, trim controls, masks and real FFmpeg exports.

The UI controls actual files on disk.  FFmpeg renders in a background worker,
then ffprobe validates the output.  Editing never overwrites the source.
"""
from __future__ import annotations

import hashlib
import tempfile
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QPushButton, QSlider, QSplitter,
    QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_AVAILABLE = True
except ImportError:
    MULTIMEDIA_AVAILABLE = False

from .core import user_data_dir
from .logging_support import redact
from .media import EditPreset, probe_video, render_video
from .studio_engine import extract_preview_frame, suggest_chinese_regions
from .studio_ui import MaskCanvas
from .subtitle_qc import audit_srt


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".m4v", ".webm"}
OUTPUT_FORMATS = (
    ("Dọc · 9:16 · 720p (máy yếu)", 720, 1280),
    ("Dọc · 9:16 · 1080p", 1080, 1920),
    ("Ngang · 16:9 · 720p", 1280, 720),
    ("Vuông · 1:1 · 720p", 720, 720),
)


def clip_duration(info: dict) -> float:
    """Duration may come from format or from an individual stream."""
    fields = [info.get("format", {}).get("duration")]
    fields.extend(s.get("duration") for s in info.get("streams", ()) if s.get("codec_type") == "video")
    for field in fields:
        try:
            duration = float(field)
            if 0 < duration < 86400:
                return duration
        except (ValueError, TypeError):
            pass
    return 0.0


def safe_output_path(folder: Path, source: Path, reserved: set[Path] | None = None) -> Path:
    """Allocate a new name. Never overwrite source or an earlier render."""
    folder, source = Path(folder).resolve(), Path(source).resolve()
    reserved = reserved if reserved is not None else set()
    for index in range(1, 10001):
        suffix = "_edited" if index == 1 else f"_edited_{index}"
        target = folder / (source.stem + suffix + ".mp4")
        if target != source and target not in reserved and not target.exists():
            reserved.add(target)
            return target
    raise RuntimeError("Thư mục xuất có quá nhiều tên video trùng.")


def preview_preset(preset: EditPreset, *, source_duration: float = 0.0) -> EditPreset:
    """Restrict a rendered preview to <=5 seconds; no 2-hour preview jobs."""
    start = preset.trim_start
    end = start + 5.0
    if preset.trim_end is not None:
        end = min(end, preset.trim_end)
    if source_duration:
        end = min(end, source_duration)
    if end - start < 0.12:
        raise ValueError("Điểm cắt vượt thời lượng video; không thể xem thử.")
    if preset.width > preset.height:
        size = (640, 360)
    elif preset.width == preset.height:
        size = (480, 480)
    else:
        size = (360, 640)
    return replace(preset, width=size[0], height=size[1], trim_end=end)


def seconds_label(ms: int) -> str:
    secs = max(0, int(ms) // 1000)
    return f"{secs // 60:02d}:{secs % 60:02d}"


class EditorWorkspace(QWidget):
    """A compact, task-first video editor, hosted within the existing app shell."""

    def __init__(self, owner: QWidget):
        super().__init__(owner)
        self.owner = owner
        self.source: Path | None = None
        self.sources: list[Path] = []
        self.source_duration = 0.0
        self._duration_ms = 0
        self._dragging = False
        self._busy = False
        self._frame: Path | None = None
        self._last_export: Path | None = None
        self._build()
        self.setAcceptDrops(True)

    def _build(self):
        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        title = QLabel("Studio biên tập video")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        self.add_button = QPushButton("＋ Nhập video")
        self.add_button.clicked.connect(self.choose_files)
        header.addWidget(self.add_button)
        self.preview_button = QPushButton("▶ Xem thử bản dựng 5 giây")
        self.preview_button.clicked.connect(self.render_preview)
        header.addWidget(self.preview_button)
        self.export_one_button = QPushButton("Xuất clip đang chọn")
        self.export_one_button.setObjectName("primaryAction")
        self.export_one_button.clicked.connect(lambda: self.export(batch=False))
        header.addWidget(self.export_one_button)
        main.addLayout(header)

        hint = QLabel("Chọn MP4/MOV/MKV • phát và tua trực tiếp • đặt điểm cắt • khoanh vùng che chữ • xuất MP4 mới")
        hint.setObjectName("hintText")
        hint.setWordWrap(True)
        main.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_box = QVBoxLayout(left)
        left_box.setContentsMargins(0, 0, 7, 0)
        left_box.setSpacing(7)
        left_box.addWidget(QLabel("DANH SÁCH CLIP"))
        self.clip_list = QListWidget()
        self.clip_list.setMinimumWidth(180)
        self.clip_list.setMaximumHeight(185)
        self.clip_list.currentItemChanged.connect(self.select_clip)
        left_box.addWidget(self.clip_list)
        clip_actions = QHBoxLayout()
        remove = QPushButton("Bỏ clip")
        remove.clicked.connect(self.remove_clip)
        clip_actions.addWidget(remove)
        clear = QPushButton("Xóa danh sách")
        clear.clicked.connect(self.clear_clips)
        clip_actions.addWidget(clear)
        left_box.addLayout(clip_actions)

        self.preview_stack = QStackedWidget()
        self.preview_stack.setMinimumHeight(360)
        self.canvas = MaskCanvas()
        self.canvas.setMinimumSize(250, 310)
        if MULTIMEDIA_AVAILABLE:
            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.player.setAudioOutput(self.audio_output)
            self.audio_output.setVolume(0.6)
            self.video_widget = QVideoWidget()
            self.player.setVideoOutput(self.video_widget)
            self.player.positionChanged.connect(self._position_changed)
            self.player.durationChanged.connect(self._duration_changed)
            self.player.errorOccurred.connect(self._player_error)
            self.preview_stack.addWidget(self.video_widget)
            self.preview_stack.addWidget(self.canvas)
        else:
            self.player = None
            self.video_widget = QLabel("Phát trực tiếp cần Qt Multimedia.\nVẫn có thể xem khung, chỉnh sửa và xuất bằng FFmpeg.")
            self.video_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.video_widget.setWordWrap(True)
            self.preview_stack.addWidget(self.video_widget)
            self.preview_stack.addWidget(self.canvas)
        left_box.addWidget(self.preview_stack, 1)

        playback = QHBoxLayout()
        self.play_button = QPushButton("▶ Phát")
        self.play_button.clicked.connect(self.play_pause)
        playback.addWidget(self.play_button)
        restore = QPushButton("↩ Clip gốc")
        restore.clicked.connect(self.restore_original)
        playback.addWidget(restore)
        self.time_label = QLabel("00:00 / 00:00")
        playback.addWidget(self.time_label)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.sliderPressed.connect(self._start_scrub)
        self.seek.sliderReleased.connect(self._end_scrub)
        playback.addWidget(self.seek, 1)
        left_box.addLayout(playback)

        trim_controls = QHBoxLayout()
        mark_in = QPushButton("⌞ Lấy điểm bắt đầu")
        mark_in.clicked.connect(lambda: self.trim_start.setValue(self.current_seconds()))
        trim_controls.addWidget(mark_in)
        mark_out = QPushButton("⌝ Lấy điểm kết thúc")
        mark_out.clicked.connect(lambda: self.trim_end.setValue(self.current_seconds()))
        trim_controls.addWidget(mark_out)
        mask_button = QPushButton("▧ Khoanh vùng che")
        mask_button.clicked.connect(self.show_mask_frame)
        trim_controls.addWidget(mask_button)
        left_box.addLayout(trim_controls)

        self.clip_details = QLabel("Chưa mở file. Nhấn “Nhập video” hoặc kéo file vào cửa sổ.")
        self.clip_details.setObjectName("hintText")
        self.clip_details.setWordWrap(True)
        left_box.addWidget(self.clip_details)
        splitter.addWidget(left)

        right = QWidget()
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(7, 0, 0, 0)
        self.inspector = QTabWidget()
        right_box.addWidget(self.inspector)
        self._build_picture_tab()
        self._build_mask_tab()
        self._build_text_tab()
        self._build_export_tab()
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([630, 420])
        main.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.status_label = QLabel("Sẵn sàng. Chưa có file nào được chỉnh sửa.")
        self.status_label.setObjectName("hintText")
        self.status_label.setWordWrap(True)
        footer.addWidget(self.status_label, 1)
        self.busy_bar = QProgressBar()
        self.busy_bar.setMaximumWidth(175)
        self.busy_bar.setRange(0, 100)
        self.busy_bar.setValue(0)
        self.busy_bar.hide()
        footer.addWidget(self.busy_bar)
        self.open_output_button = QPushButton("Mở MP4 đã xuất")
        self.open_output_button.setEnabled(False)
        self.open_output_button.clicked.connect(self.open_output)
        footer.addWidget(self.open_output_button)
        main.addLayout(footer)
        self._refresh_enabled()

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float, value: float = 0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(step)
        spin.setValue(value)
        return spin

    def _build_picture_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        form.setVerticalSpacing(12)
        self.size = QComboBox()
        for name, w, h in OUTPUT_FORMATS:
            self.size.addItem(name, (w, h))
        form.addRow("Khung đầu ra", self.size)
        self.fit = QComboBox()
        self.fit.addItem("Cắt vừa khung", "crop")
        self.fit.addItem("Giữ toàn cảnh, viền đen", "pad")
        self.fit.addItem("Nền mờ", "blur")
        form.addRow("Hiển thị", self.fit)
        self.brightness = self._spin(-0.5, 0.5, .05)
        self.contrast = self._spin(.5, 2.0, .1, 1)
        self.saturation = self._spin(0, 2.0, .1, 1)
        form.addRow("Độ sáng", self.brightness)
        form.addRow("Tương phản", self.contrast)
        form.addRow("Bão hòa", self.saturation)
        self.trim_start = self._spin(0, 36000, .25)
        self.trim_end = self._spin(0, 36000, .25)
        self.trim_end.setSpecialValueText("Đến hết")
        form.addRow("Cắt từ (giây)", self.trim_start)
        form.addRow("Cắt đến (giây)", self.trim_end)
        reset = QPushButton("Đặt lại màu và điểm cắt")
        reset.clicked.connect(self.reset_picture)
        form.addRow(reset)
        self.inspector.addTab(tab, "Khung & màu")

    def _build_mask_tab(self):
        tab = QWidget()
        form = QVBoxLayout(tab)
        note = QLabel("Tạm dừng video, chọn “Khoanh vùng che” rồi kéo chuột trên khung hình. "
                      "Những vùng đã chọn được áp dụng vào video xuất.")
        note.setWordWrap(True)
        note.setObjectName("hintText")
        form.addWidget(note)
        self.mask_type = QComboBox()
        self.mask_type.addItem("Làm mờ vùng chọn", "blur")
        self.mask_type.addItem("Che kín vùng chọn", "solid")
        form.addWidget(self.mask_type)
        capture = QPushButton("Khoanh vùng trên khung đang xem")
        capture.clicked.connect(self.show_mask_frame)
        form.addWidget(capture)
        ocr = QPushButton("Tự nhận diện chữ Trung tại khung này")
        ocr.clicked.connect(self.detect_subtitles)
        form.addWidget(ocr)
        clear = QPushButton("Xóa tất cả vùng che")
        clear.clicked.connect(self.canvas.clear_regions)
        form.addWidget(clear)
        return_play = QPushButton("↩ Quay về trình phát")
        return_play.clicked.connect(lambda: self.preview_stack.setCurrentIndex(0))
        form.addWidget(return_play)
        form.addStretch(1)
        self.inspector.addTab(tab, "Che phụ đề")

    def _build_text_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        form.setVerticalSpacing(11)
        self.cta = QLineEdit()
        self.cta.setPlaceholderText("Không nhập thì không thêm chữ quảng bá")
        form.addRow("CTA trên video", self.cta)
        self.source_url = QLineEdit()
        self.source_url.setPlaceholderText("URL gốc (tùy chọn), không lưu giấy tờ cá nhân")
        form.addRow("Nguồn", self.source_url)
        self.subtitle = QLineEdit()
        subrow = QHBoxLayout()
        subrow.addWidget(self.subtitle)
        subbrowse = QPushButton("SRT…")
        subbrowse.clicked.connect(lambda: self._choose_optional(self.subtitle, "Phụ đề (*.srt)"))
        subrow.addWidget(subbrowse)
        form.addRow("Phụ đề", subrow)
        self.voice = QLineEdit()
        voicerow = QHBoxLayout()
        voicerow.addWidget(self.voice)
        voicebrowse = QPushButton("Audio…")
        voicebrowse.clicked.connect(lambda: self._choose_optional(self.voice, "Âm thanh (*.wav *.mp3 *.m4a)"))
        voicerow.addWidget(voicebrowse)
        form.addRow("Thuyết minh", voicerow)
        self.inspector.addTab(tab, "Chữ & âm thanh")

    def _build_export_tab(self):
        tab = QWidget()
        form = QVBoxLayout(tab)
        form.addWidget(QLabel("THƯ MỤC ĐÍCH"))
        browse_row = QHBoxLayout()
        self.output_folder = QLineEdit(str(user_data_dir() / "exports"))
        browse_row.addWidget(self.output_folder, 1)
        chooser = QPushButton("Chọn…")
        chooser.clicked.connect(self.choose_output_folder)
        browse_row.addWidget(chooser)
        form.addLayout(browse_row)
        self.rights = QCheckBox("Tôi có quyền biên tập và sử dụng những clip này")
        form.addWidget(self.rights)
        form.addWidget(QLabel("Bản xuất dùng H.264/AAC; file gốc luôn được giữ nguyên."))
        note = QLabel("“Xuất tất cả” áp dụng một preset cho toàn bộ clip. Các điểm cắt và vùng che sẽ dùng chung; "
                      "nên xem thử trước khi xuất hàng loạt.")
        note.setObjectName("hintText")
        note.setWordWrap(True)
        form.addWidget(note)
        self.export_all_button = QPushButton("Xuất toàn bộ clip trong danh sách")
        self.export_all_button.setObjectName("primaryAction")
        self.export_all_button.clicked.connect(lambda: self.export(batch=True))
        form.addWidget(self.export_all_button)
        form.addStretch(1)
        self.inspector.addTab(tab, "Xuất MP4")

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn video để biên tập", "", "Video (*.mp4 *.mov *.mkv *.webm *.m4v)"
        )
        self.import_files(paths)

    def import_files(self, paths):
        for raw in paths:
            file = Path(raw).expanduser().resolve()
            if not file.is_file() or file.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            if file not in self.sources:
                self.sources.append(file)
                item = QListWidgetItem(file.name)
                item.setToolTip(str(file))
                item.setData(Qt.ItemDataRole.UserRole, str(file))
                self.clip_list.addItem(item)
        if self.sources and self.clip_list.currentRow() < 0:
            self.clip_list.setCurrentRow(0)
        self._refresh_enabled()

    def select_clip(self, item, _previous=None):
        if item is None:
            self.source = None
            self._refresh_enabled()
            return
        source = Path(item.data(Qt.ItemDataRole.UserRole))
        self.source = source
        self._frame = None
        self.source_duration = 0.0
        self._duration_ms = 0
        self.seek.setValue(0)
        self.canvas.clear_regions()
        self.preview_stack.setCurrentIndex(0)
        if self.player is not None:
            self.player.stop()
            self.player.setSource(QUrl.fromLocalFile(str(source)))
        self.clip_details.setText("Đang đọc thông số: " + source.name)
        self._refresh_enabled()

        def ready(info):
            if self.source != source:
                return
            self.source_duration = clip_duration(info)
            self._duration_ms = int(self.source_duration * 1000)
            streams = [x for x in info.get("streams", ()) if x.get("codec_type") == "video"]
            video = streams[0] if streams else {}
            self.clip_details.setText(
                f"{source.name}  •  {video.get('width', '?')}×{video.get('height', '?')}  •  "
                f"{self.source_duration:.1f}s"
            )
            self._position_changed(0)

        self.owner.job("Đọc video nguồn", lambda report: probe_video(source), ready)

    def remove_clip(self):
        index = self.clip_list.currentRow()
        if index < 0:
            return
        path = Path(self.clip_list.item(index).data(Qt.ItemDataRole.UserRole))
        if self.player:
            self.player.stop()
        self.sources.remove(path)
        self.clip_list.takeItem(index)
        self.source = None
        if self.clip_list.count():
            self.clip_list.setCurrentRow(min(index, self.clip_list.count() - 1))
        else:
            self.clip_details.setText("Chưa chọn video.")
        self._refresh_enabled()

    def clear_clips(self):
        if self.player:
            self.player.stop()
        self.sources.clear()
        self.source = None
        self._frame = None
        self.clip_list.clear()
        self.canvas.clear_regions()
        self.clip_details.setText("Chưa chọn video.")
        self._refresh_enabled()

    def _refresh_enabled(self):
        available = self.source is not None and self.source.is_file()
        for button in (self.play_button, self.preview_button, self.export_one_button):
            button.setEnabled(available and not self._busy)
        self.export_all_button.setEnabled(bool(self.sources) and not self._busy)
        self.add_button.setEnabled(not self._busy)

    def _position_changed(self, position):
        if not self._dragging and self._duration_ms > 0:
            self.seek.setValue(min(1000, max(0, round(position * 1000 / self._duration_ms))))
        self.time_label.setText(
            f"{seconds_label(position)} / {seconds_label(self._duration_ms)}"
        )

    def _duration_changed(self, duration):
        if duration > 0:
            self._duration_ms = duration
            self._position_changed(self.current_millis())

    def _player_error(self, _error, message):
        if message and self.source:
            self.status_label.setText("Phát video gặp lỗi: " + message[:200] +
                                      ". Có thể dùng xem khung FFmpeg và xuất MP4.")

    def current_millis(self):
        return int(self.player.position()) if self.player else round(
            self.seek.value() * self._duration_ms / 1000
        )

    def current_seconds(self):
        return self.current_millis() / 1000

    def _start_scrub(self):
        self._dragging = True

    def _end_scrub(self):
        self._dragging = False
        position = round(self.seek.value() * self._duration_ms / 1000)
        if self.player:
            self.player.setPosition(position)
        self._position_changed(position)

    def play_pause(self):
        if not self.source:
            return
        self.preview_stack.setCurrentIndex(0)
        if self.player is None:
            self.show_mask_frame()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_button.setText("▶ Phát")
        else:
            self.player.play()
            self.play_button.setText("⏸ Tạm dừng")

    def restore_original(self):
        if not self.source:
            return
        if self.player:
            self.player.stop()
            self.player.setSource(QUrl.fromLocalFile(str(self.source)))
            self.player.setPosition(0)
        self.preview_stack.setCurrentIndex(0)
        self.play_button.setText("▶ Phát")
        self.status_label.setText("Đã quay lại video gốc, các chỉnh sửa vẫn được giữ.")

    def _choose_optional(self, widget, kind):
        file, _ = QFileDialog.getOpenFileName(self, "Chọn tệp", "", kind)
        if file:
            widget.setText(file)

    def choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Chọn thư mục xuất video", self.output_folder.text()
        )
        if folder:
            self.output_folder.setText(folder)

    def reset_picture(self):
        self.brightness.setValue(0)
        self.contrast.setValue(1)
        self.saturation.setValue(1)
        self.trim_start.setValue(0)
        self.trim_end.setValue(0)

    def _preset(self) -> EditPreset:
        w, h = self.size.currentData()
        end = self.trim_end.value() or None
        regions = tuple(replace(r, mode=self.mask_type.currentData())
                        for r in self.canvas.regions())
        preset = EditPreset(
            width=w, height=h, fit=self.fit.currentData(),
            brightness=self.brightness.value(), contrast=self.contrast.value(),
            saturation=self.saturation.value(), cta=self.cta.text().strip(),
            original_url=self.source_url.text().strip(),
            subtitle=Path(self.subtitle.text()).expanduser() if self.subtitle.text().strip() else None,
            narration=Path(self.voice.text()).expanduser() if self.voice.text().strip() else None,
            masks=regions, trim_start=self.trim_start.value(), trim_end=end,
        )
        preset.validate()
        return preset

    def _authorized_preset(self) -> EditPreset:
        if not self.rights.isChecked():
            raise PermissionError("Hãy xác nhận bạn có quyền chỉnh sửa và sử dụng các video.")
        return self._preset()

    def show_mask_frame(self):
        if not self.source:
            return self._error("Hãy chọn một file video trước.")
        if self.player:
            self.player.pause()
            self.play_button.setText("▶ Phát")
        path = self.source
        position = self.current_seconds()
        fit = self.fit.currentData()
        w, h = self.size.currentData()
        if w > h:
            width, height = 640, 360
        elif w == h:
            width, height = 480, 480
        else:
            width, height = 360, 640
        digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
        temp = user_data_dir() / "previews" / f"{digest}-{round(position * 10)}-{fit}.png"
        def ready(frame):
            if self.source != path:
                return
            self._frame = Path(frame)
            self.canvas.set_image(frame)
            self.preview_stack.setCurrentIndex(1)
            self.status_label.setText("Kéo chuột trên video để khoanh vùng che chữ.")
        self.owner.job(
            "Đọc khung video", lambda report: extract_preview_frame(
                path, temp, seconds=position, fit=fit, width=width, height=height
            ), ready
        )

    def detect_subtitles(self):
        if not self.source:
            return self._error("Chọn video trước khi nhận diện phụ đề.")
        if not self._frame:
            return self._error("Nhấn “Khoanh vùng che” để nạp một khung hình trước.")
        frame = self._frame
        def done(result):
            regions, message = result
            if self._frame != frame:
                return
            old = self.canvas.regions()
            self.canvas.set_regions((old + regions)[:12])
            self.status_label.setText(message)
            QMessageBox.information(self, "OCR tiếng Trung", message)
        self.owner.job("Nhận diện chữ Trung", lambda report: suggest_chinese_regions(frame), done)

    def _check_subtitles(self, preset):
        if not preset.subtitle:
            return True
        issues = audit_srt(preset.subtitle)
        problems = [item for item in issues if item.severity == "error"]
        if problems:
            raise ValueError("SRT có timecode không hợp lệ. Sửa phụ đề trước khi xuất.")
        if issues:
            result = QMessageBox.question(
                self, "Cảnh báo phụ đề",
                f"Có {len(issues)} cảnh báo về tốc độ đọc hoặc độ dài. Tiếp tục?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            return result == QMessageBox.StandardButton.Yes
        return True

    def _busy_state(self, active, message):
        self._busy = active
        self._refresh_enabled()
        self.busy_bar.setVisible(active)
        if active:
            self.busy_bar.setRange(0, 0)
        else:
            self.busy_bar.setRange(0, 100)
            self.busy_bar.setValue(0)
        self.status_label.setText(message)

    def render_preview(self):
        if not self.source:
            return self._error("Hãy nhập một video thật trước khi xem thử.")
        try:
            preset = self._authorized_preset()
            if not self._check_subtitles(preset):
                return
            sample = preview_preset(preset, source_duration=self.source_duration)
            source = self.source
            destination = (user_data_dir() / "previews" /
                           f"edited-{hashlib.sha256(str(source).encode()).hexdigest()[:12]}.mp4")
        except (ValueError, PermissionError, FileNotFoundError) as exc:
            return self._error(str(exc))
        self._busy_state(True, "Đang dựng bản xem trước 5 giây…")
        def done(result):
            self._busy_state(False, "Đã tạo video xem trước: " + str(result))
            self.preview_stack.setCurrentIndex(0)
            if self.player:
                self.player.stop()
                self.player.setSource(QUrl.fromLocalFile(str(result)))
                self.player.play()
                self.play_button.setText("⏸ Tạm dừng")
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(result)))
        self.owner.job(
            "Render xem thử video thật",
            lambda progress: render_video(source, destination, sample, progress),
            done,
            lambda error: self._busy_state(False, "Render xem thử thất bại: " + error[:200]),
        )

    def export(self, *, batch: bool):
        files = tuple(self.sources) if batch else ((self.source,) if self.source else ())
        if not files:
            return self._error("Hãy chọn file video trước khi xuất.")
        try:
            preset = self._authorized_preset()
            if not self._check_subtitles(preset):
                return
            if not self.output_folder.text().strip():
                raise ValueError("Chưa chọn thư mục xuất.")
            folder = Path(self.output_folder.text()).expanduser().resolve()
            if not str(folder):
                raise ValueError("Chưa chọn thư mục xuất.")
            if batch and len(files) > 1:
                answer = QMessageBox.question(
                    self, "Xuất hàng loạt", f"Áp dụng cùng một preset cho {len(files)} video?\n"
                    "Vùng che và điểm cắt sẽ dùng chung.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            allocated = set()
            jobs = [(file, safe_output_path(folder, file, allocated)) for file in files]
        except (ValueError, PermissionError, OSError, FileNotFoundError) as exc:
            return self._error(str(exc))
        self._busy_state(True, f"Đang render {len(jobs)} clip…")
        def task(progress):
            outputs, failures = [], []
            for i, (source, target) in enumerate(jobs, 1):
                progress(f"[{i}/{len(jobs)}] Render video: {source.name}")
                try:
                    outputs.append(render_video(source, target, preset, progress))
                except Exception as exc:
                    failures.append(f"{source.name}: {redact(str(exc))[:350]}")
            if not outputs:
                raise RuntimeError("Không xuất được MP4 nào.\n" + "\n".join(failures[:4]))
            return outputs, failures

        def done(result):
            outputs, failures = result
            self._last_export = outputs[0]
            self.open_output_button.setEnabled(True)
            self._busy_state(
                False,
                f"Đã xuất {len(outputs)} file MP4 ở {folder}" +
                (f" · {len(failures)} clip lỗi" if failures else ""),
            )
            if failures:
                QMessageBox.warning(self, "Một số clip lỗi", "\n".join(failures[:8]))
            else:
                QMessageBox.information(
                    self, "Đã xuất video thật",
                    f"Đã xuất {len(outputs)} MP4 và kiểm tra bằng FFprobe.\n"
                    f"File đầu tiên: {outputs[0]}",
                )
        self.owner.job(
            "Xuất MP4 bằng FFmpeg", task, done,
            lambda error: self._busy_state(False, "Render thất bại: " + error[:240]),
        )

    def open_output(self):
        if self._last_export and self._last_export.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_export)))
        else:
            self._error("Chưa có video đã xuất để mở.")

    def _error(self, message):
        self.status_label.setText(message)
        QMessageBox.warning(self, "Studio video", message)

    def dragEnterEvent(self, event):
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self.import_files(urls)
        event.acceptProposedAction()
