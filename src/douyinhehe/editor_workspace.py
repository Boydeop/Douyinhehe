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
from .project_io import save_project, load_project, EXTENSION
from .editor_ops import (clip_duration, safe_output_path, preview_preset,
                         preset_from_editor_state, seconds_label)
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
        self._source_generation = 0
        self._frame_generation = 0
        self._clip_states: dict[Path, dict] = {}
        self._build()
        self._default_edit_state = self._capture_edit_state()
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
        self.add_button.setToolTip("Nhập MP4, MOV, MKV, M4V hoặc WebM để chỉnh sửa cục bộ")
        header.addWidget(self.add_button)
        self.preview_button = QPushButton("▶ Xem thử bản dựng 5 giây")
        self.preview_button.clicked.connect(self.render_preview)
        self.preview_button.setToolTip("Render 5 giây thật bằng FFmpeg trước khi xuất")
        header.addWidget(self.preview_button)
        self.export_one_button = QPushButton("Xuất clip đang chọn")
        self.export_one_button.setObjectName("primaryAction")
        self.export_one_button.clicked.connect(lambda: self.export(batch=False))
        self.export_one_button.setToolTip("Xuất clip mới; không thay đổi bản gốc")
        header.addWidget(self.export_one_button)
        main.addLayout(header)

        project_actions = QHBoxLayout()
        self.open_project_button = QPushButton("Mở dự án .dhyproj")
        self.open_project_button.setToolTip("Khôi phục danh sách video và thiết lập chỉnh sửa từng clip")
        self.open_project_button.clicked.connect(self.open_project_file)
        project_actions.addWidget(self.open_project_button)
        self.save_project_button = QPushButton("Lưu dự án")
        self.save_project_button.setToolTip("Tạo bản sao lưu .bak trước khi cập nhật dự án")
        self.save_project_button.clicked.connect(self.save_project_file)
        project_actions.addWidget(self.save_project_button)
        project_actions.addStretch()
        main.addLayout(project_actions)

        hint = QLabel("01  Nhập clip     →     02  Xem và chọn điểm cắt     →     03  Chỉnh màu / che chữ     →     04  Xem thử và xuất")
        hint.setObjectName("hintText")
        hint.setWordWrap(True)
        main.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_box = QVBoxLayout(left)
        left_box.setContentsMargins(0, 0, 7, 0)
        left_box.setSpacing(7)
        library_row = QHBoxLayout()
        library_row.addWidget(QLabel("THƯ VIỆN VIDEO"))
        library_row.addStretch(1)
        self.clip_count_label = QLabel("0 clip")
        self.clip_count_label.setObjectName("hintText")
        library_row.addWidget(self.clip_count_label)
        left_box.addLayout(library_row)
        self.clip_list = QListWidget()
        self.clip_list.setObjectName("clipLibrary")
        self.clip_list.setMinimumWidth(180)
        self.clip_list.setMaximumHeight(155)
        self.clip_list.currentItemChanged.connect(self.select_clip)
        left_box.addWidget(self.clip_list)
        clip_actions = QHBoxLayout()
        self.remove_button = QPushButton("Bỏ clip")
        self.remove_button.clicked.connect(self.remove_clip)
        clip_actions.addWidget(self.remove_button)
        self.clear_button = QPushButton("Xóa danh sách")
        self.clear_button.clicked.connect(self.clear_clips)
        clip_actions.addWidget(self.clear_button)
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

        self.clip_details = QLabel("Chưa mở video. Nhấn “Nhập video” hoặc kéo thả file vào cửa sổ.")
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
        note = QLabel("“Xuất tất cả” giữ thông số cắt, màu, chữ và vùng che riêng từng clip. "
                      "Hãy mở và xem thử từng clip trước khi xuất hàng loạt.")
        note.setObjectName("hintText")
        note.setWordWrap(True)
        form.addWidget(note)
        self.export_all_button = QPushButton("Xuất toàn bộ clip trong danh sách")
        self.export_all_button.setObjectName("primaryAction")
        self.export_all_button.clicked.connect(lambda: self.export(batch=True))
        form.addWidget(self.export_all_button)
        form.addStretch(1)
        self.inspector.addTab(tab, "Xuất MP4")

    def save_project_file(self):
        if self._busy:
            return self._error("Hãy hoàn thành render trước khi lưu dự án.")
        if not self.sources:
            return self._error("Chưa có clip nào để lưu.")
        project_dir = user_data_dir() / "projects"
        try:
            project_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return self._error(str(exc))
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu dự án Douyinhehe",
            str(project_dir / "MyStudio.dhyproj"),
            "Douyinhehe Project (*.dhyproj)")
        if not path:
            return
        try:
            states = dict(self._clip_states)
            if self.source is not None:
                states[self.source] = self._capture_edit_state()
            items = [(source, states.get(source, self._default_edit_state))
                     for source in self.sources]
            result = save_project(Path(path), items, self.source)
            self._clip_states = states
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return self._error(str(exc))
        self.status_label.setText(f"Đã lưu {len(items)} clip: {result}")

    def _expand_project_state(self, state: dict) -> dict:
        """Bridge the portable project schema to the 3.8 Qt inspector snapshot."""
        result = dict(state)
        size_index = result["size"]
        if size_index < 0 or size_index >= self.size.count():
            raise ValueError("Định dạng video trong dự án không được hỗ trợ.")
        result["output_size"] = tuple(self.size.itemData(size_index))
        result["fit_mode"] = ("crop", "pad", "blur")[result["fit"]]
        result["mask_mode"] = ("blur", "solid")[result["mask_type"]]
        return result

    def open_project_file(self):
        if self._busy:
            return self._error("Hãy hoàn thành render trước khi mở dự án.")
        path, _ = QFileDialog.getOpenFileName(
            self, "Mở dự án Douyinhehe",
            str(user_data_dir() / "projects"),
            "Douyinhehe Project (*.dhyproj)")
        if not path:
            return
        try:
            entries, selected = load_project(Path(path))
            missing = [p.name for p, _ in entries if not p.is_file()]
            present = [(p, self._expand_project_state(state))
                       for p, state in entries if p.is_file()]
            if not present:
                raise ValueError("Không tìm thấy video nguồn của dự án. Hãy khôi phục file video.")
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            return self._error(str(exc))
        if self.sources:
            answer = QMessageBox.question(
                self, "Thay danh sách clip hiện tại?",
                "Dự án mới sẽ thay thế danh sách hiện tại. Hãy lưu dự án cũ trước nếu cần.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.clear_clips()
        self._clip_states = {p: state for p, state in present}
        self.import_files([p for p, _ in present])
        if selected is not None:
            for i in range(self.clip_list.count()):
                item = self.clip_list.item(i)
                if Path(item.data(Qt.ItemDataRole.UserRole)) == selected:
                    self.clip_list.setCurrentRow(i)
                    break
        self.status_label.setText(
            f"Đã mở {len(present)} clip." +
            (f" Thiếu {len(missing)} file nguồn." if missing else "")
        )
        if missing:
            QMessageBox.warning(self, "Thiếu video nguồn",
                                "Hãy khôi phục các file gốc:\n" + "\n".join(missing[:10]))

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

    def _capture_edit_state(self) -> dict:
        """Keep edits separately for each local clip until the app closes."""
        return {
            "size": self.size.currentIndex(),
            "output_size": tuple(self.size.currentData()),
            "fit": self.fit.currentIndex(),
            "fit_mode": self.fit.currentData(),
            "brightness": self.brightness.value(),
            "contrast": self.contrast.value(),
            "saturation": self.saturation.value(),
            "trim_start": self.trim_start.value(),
            "trim_end": self.trim_end.value(),
            "mask_type": self.mask_type.currentIndex(),
            "mask_mode": self.mask_type.currentData(),
            "masks": tuple(self.canvas.regions()),
            "cta": self.cta.text(),
            "source_url": self.source_url.text(),
            "subtitle": self.subtitle.text(),
            "voice": self.voice.text(),
        }

    def _restore_edit_state(self, saved: dict) -> None:
        for name in ("size", "fit", "mask_type"):
            getattr(self, name).setCurrentIndex(saved[name])
        for name in ("brightness", "contrast", "saturation", "trim_start", "trim_end"):
            getattr(self, name).setValue(saved[name])
        for name in ("cta", "source_url", "subtitle", "voice"):
            getattr(self, name).setText(saved[name])
        self.canvas.set_regions(saved["masks"])

    def select_clip(self, item, _previous=None):
        if self.source is not None and self.source in self.sources:
            self._clip_states[self.source] = self._capture_edit_state()
        self._source_generation += 1
        self._frame_generation += 1
        if item is None:
            self.source = None
            self._frame = None
            self._refresh_enabled()
            return
        source = Path(item.data(Qt.ItemDataRole.UserRole))
        self.source = source
        generation = self._source_generation
        self._frame = None
        self.source_duration = 0.0
        self._duration_ms = 0
        self.seek.setValue(0)
        self._restore_edit_state(self._clip_states.get(source, self._default_edit_state))
        self.preview_stack.setCurrentIndex(0)
        if self.player is not None:
            self.player.stop()
            self.player.setSource(QUrl.fromLocalFile(str(source)))
        self.clip_details.setText("Đang đọc thông số: " + source.name)
        self._refresh_enabled()

        def ready(info):
            if self.source != source or generation != self._source_generation:
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
        self._clip_states.pop(path, None)
        self.clip_list.takeItem(index)
        if self.clip_list.count():
            self.clip_list.setCurrentRow(min(index, self.clip_list.count() - 1))
            selected = self.clip_list.currentItem()
            if selected is not None and self.source != Path(selected.data(Qt.ItemDataRole.UserRole)):
                self.select_clip(selected)
        else:
            self.select_clip(None)
            self.clip_details.setText("Chưa chọn video.")
        self._refresh_enabled()

    def clear_clips(self):
        if self.player:
            self.player.stop()
        self.sources.clear()
        self._clip_states.clear()
        self.source = None
        self._source_generation += 1
        self._frame_generation += 1
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
        self.save_project_button.setEnabled(bool(self.sources) and not self._busy)
        self.open_project_button.setEnabled(not self._busy)
        self.remove_button.setEnabled(self.clip_list.currentRow() >= 0 and not self._busy)
        self.clear_button.setEnabled(bool(self.sources) and not self._busy)
        self.clip_count_label.setText(f"{len(self.sources)} clip")

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
        return preset_from_editor_state(self._capture_edit_state())

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
        self._frame_generation += 1
        generation = self._frame_generation
        source_generation = self._source_generation
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
            if (self.source != path or generation != self._frame_generation or
                    source_generation != self._source_generation):
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
            # Do not replace a preview while Qt's player may keep it open on Windows.
            destination = safe_output_path(
                user_data_dir() / "previews",
                Path("preview-" + hashlib.sha256(str(source).encode()).hexdigest()[:12] + ".mp4"),
            )
        except (ValueError, PermissionError, FileNotFoundError) as exc:
            return self._error(str(exc))
        self._busy_state(True, "Đang dựng bản xem trước 5 giây…")
        source_generation = self._source_generation
        def done(result):
            self._busy_state(False, "Đã tạo video xem trước: " + str(result))
            if self.source != source or source_generation != self._source_generation:
                return  # Do not switch playback to an unrelated clip.
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
            # The UI owns a single inspector. Freeze its current state and
            # combine it with *each clip's own* previously saved state.
            # Do not apply the selected clip's mask or trim to other sources.
            if not self.rights.isChecked():
                raise PermissionError("Hãy xác nhận quyền biên tập và sử dụng tất cả video.")
            if not self.output_folder.text().strip():
                raise ValueError("Chưa chọn thư mục xuất.")
            folder = Path(self.output_folder.text()).expanduser().resolve()
            current_state = self._capture_edit_state()
            states = dict(self._clip_states)
            if self.source is not None:
                states[self.source] = current_state
            allocated: set[Path] = set()
            jobs: list[tuple[Path, Path, EditPreset]] = []
            for source in files:
                state = states.get(source, self._default_edit_state)
                preset = preset_from_editor_state(state)
                if not self._check_subtitles(preset):
                    return
                jobs.append((source, safe_output_path(folder, source, allocated), preset))
            if batch and len(files) > 1:
                answer = QMessageBox.question(
                    self, "Xuất hàng loạt", f"Xuất {len(files)} clip với thiết lập riêng của từng clip?\\n"
                    "File gốc sẽ không bị ghi đè.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
        except (ValueError, KeyError, TypeError, PermissionError, OSError, FileNotFoundError) as exc:
            return self._error(str(exc))
        self._busy_state(True, f"Đang render {len(jobs)} clip…")

        def task(progress):
            outputs, failures = [], []
            for i, (source, target, preset) in enumerate(jobs, 1):
                progress(f"[{i}/{len(jobs)}] Render video: {source.name}")
                try:
                    outputs.append(render_video(source, target, preset, progress))
                except Exception as exc:
                    failures.append(f"{source.name}: {redact(str(exc))[:350]}")
            if not outputs:
                raise RuntimeError("Không xuất được MP4 nào.\\n" + "\\n".join(failures[:4]))
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
                QMessageBox.warning(self, "Một số clip lỗi", "\\n".join(failures[:8]))
            else:
                QMessageBox.information(
                    self, "Đã xuất video thật",
                    f"Đã xuất {len(outputs)} MP4 và kiểm tra bằng FFprobe.\\n"
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
