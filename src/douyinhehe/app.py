"""PySide6 Vietnamese desktop interface. All blocking work runs off the UI thread."""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QDateTime, Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateTimeEdit, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from .affiliate import Metrics
from .batch import create_local_manifest, enqueue_manifest, run_queue
from .delivery import DESTINATIONS, delivery_preflight
from .core import KEYWORDS, LicenseGrant, Store, opportunity_score, user_data_dir
from .credentials import get_secret, save_secret
from .downloader import (download_authorized, parse_douyin_urls, is_channel_url,
                         classify_douyin_url, f2_worker_executable, selected_video_from_profile)
from .diagnostics import downloader_status, update_ytdlp
from .subtitle_qc import audit_srt, preview_five_seconds
from .glossary import load_glossary, save_glossary, validate_glossary
from .logging_support import export_redacted_logs, redact, write_event
from .cta_presets import CTAStyle, load_preset, save_preset
from .affiliate_reports import import_report
from .tts_adapters import get_tts_engine
from .media import EditPreset, find_binary, render_video
from .publisher import PostizClient
from .subtitles import transcribe_to_srt, translate_srt, text_to_voice
from .studio_ui import MaskCanvas
from .studio_engine import MaskRegion, suggest_chinese_regions, extract_preview_frame
from PySide6.QtWidgets import QListWidget, QStackedWidget, QSlider, QFrame
from dataclasses import replace
import hashlib
import tempfile


class WorkerSignals(QObject):
    progress = Signal(str)
    completed = Signal(object)
    failed = Signal(str)


class Work(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(self.signals.progress.emit)
            self.signals.completed.emit(result)
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


def field(hint="", initial=""):
    value = QLineEdit(initial)
    value.setPlaceholderText(hint)
    return value


def paragraph(hint="", height=100):
    value = QPlainTextEdit()
    value.setPlaceholderText(hint)
    value.setMaximumHeight(height)
    return value


def group(name):
    panel = QGroupBox(name)
    panel.setLayout(QFormLayout())
    return panel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Douyinhehe Studio 3.4 · Video Editor Preview")
        self.setMinimumSize(1080, 700)
        self.resize(1450, 900)
        self.store = Store()
        self.pool = QThreadPool.globalInstance()
        self._workers = set()
        self._studio_frame = None
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(228)
        navbox = QVBoxLayout(sidebar)
        navbox.setContentsMargins(12, 20, 12, 15)
        brand = QLabel("▶  DOUYINHEHE")
        brand.setObjectName("brand")
        navbox.addWidget(brand)
        navbox.addWidget(QLabel("AFFILIATE VIDEO STUDIO"))
        self.nav = QListWidget()
        self.nav.setObjectName("navigation")
        self.nav.setSpacing(3)
        navbox.addWidget(self.nav, 1)
        navbox.addWidget(QLabel("Chỉ video có quyền sử dụng"))
        outer.addWidget(sidebar)
        workspace = QWidget()
        body = QVBoxLayout(workspace)
        body.setContentsMargins(20, 16, 20, 10)
        heading = QLabel("Douyinhehe Workspace")
        heading.setObjectName("heading")
        headline = QHBoxLayout()
        headline.addWidget(heading)
        headline.addStretch(1)
        log_toggle = QPushButton("Nhật ký")
        log_toggle.setToolTip("Hiện hoặc ẩn nhật ký kỹ thuật")
        headline.addWidget(log_toggle)
        body.addLayout(headline)
        intro = QLabel("Douyinhehe 3.4 preview  |  Video editor  |  OCR offline  |  FFmpeg")
        intro.setObjectName("subheading")
        body.addWidget(intro)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumHeight(120)
        self.logs.setVisible(False)
        log_toggle.clicked.connect(lambda: self.logs.setVisible(not self.logs.isVisible()))
        body.addWidget(self.logs)
        outer.addWidget(workspace, 1)
        self.setCentralWidget(root)
        for title, builder in [
            ("Khám phá", self.build_research),
            ("Tải Douyin", self.build_download),
            ("Studio chỉnh sửa", self.build_editor),
            ("Phụ đề · Dịch", self.build_translation),
            ("Affiliate", self.build_affiliate),
            ("Lên lịch", self.build_publish),
            ("Cài đặt", self.build_settings),
            ("Hàng đợi batch", self.build_batch_queue),
            ("Kiểm tra video", self.build_delivery_check),
        ]:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 10, 10, 10)
            builder(layout)
            if title == "Studio chỉnh sửa":
                # A playable timeline must occupy the viewport, not sit inside a long form scroll.
                self.pages.addWidget(widget)
            else:
                layout.addStretch()
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(widget)
                self.pages.addWidget(scroll)
            self.nav.addItem(title)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(1)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0f1117; color: #f4f6f9;
                font-family: 'Segoe UI'; font-size: 14px; }
            QFrame#sidebar, QListWidget#navigation { background: #171a22; border: none; }
            QLabel#brand { font-size: 20px; font-weight: 800; color: #ff5a62; padding: 7px 0 17px 0; }
            QLabel#heading { font-size: 24px; font-weight: 750; padding: 4px 0; }
            QLabel#subheading, QLabel#hintText, QLabel#pageDescription {
                color: #b5bbc8; font-size: 13px; padding: 3px 0; }
            QLabel#pageTitle { font-size: 24px; font-weight: 750; padding: 4px 0; }
            QListWidget#navigation::item { padding: 14px 13px; margin: 3px 0;
                border-radius: 9px; color: #dde2e9; }
            QListWidget#navigation::item:selected { background: #41262b;
                color: #ffffff; border-left: 4px solid #fa5f66; }
            QListWidget#navigation::item:hover { background: #292f3a; }
            QGroupBox { border: 1px solid #383f4b; border-radius: 12px;
                margin-top: 20px; padding: 17px 13px 13px 13px; font-weight: 650;
                background: #1b2029; }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; top: 3px;
                padding: 0 7px; color: #f2f5f8; }
            QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
            QDateTimeEdit {
                background: #252b35; border: 1px solid #525b6b;
                border-radius: 7px; padding: 9px; color: #f4f6f9;
                selection-background-color: #8c363e; }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {
                border: 2px solid #ff727b; }
            QComboBox::drop-down { border: none; width: 28px; }
            QPushButton { background: #303743; color: #f7f8fa;
                border: 1px solid #515967; border-radius: 8px;
                padding: 10px 14px; min-height: 26px; font-weight: 650; }
            QPushButton:hover { background: #424a56; border-color: #747c8b; }
            QPushButton:pressed { background: #6e303b; }
            QPushButton:focus { border: 2px solid #ff8b95; }
            QPushButton#primaryAction { background: #e34251; color: #ffffff;
                border: 1px solid #ef6170; font-size: 14px; }
            QPushButton#primaryAction:hover { background: #f05260; }
            QPushButton:disabled { background: #2a2d34; color: #9a9faa; }
            QCheckBox { padding: 9px 3px; spacing: 10px; }
            QScrollArea { border: none; }
            QScrollBar:vertical { background: #1b2029; width: 12px; }
            QScrollBar::handle:vertical { background: #495361; border-radius: 6px; }
            QProgressBar { border: 1px solid #505968; border-radius: 7px;
                background: #292f39; text-align: center; min-height: 27px; }
            QProgressBar::chunk { background: #ea4d5e; border-radius: 6px; }
            QSlider::groove:horizontal { height: 7px; background: #4a515b; border-radius: 3px; }
            QSlider::handle:horizontal { background: #ff6774; width: 16px; margin: -5px 0; border-radius: 7px; }
            QToolTip { background: #272d38; color: white; border: 1px solid #6d7887; }
            QTabWidget::pane { border: 1px solid #3b4351; border-radius: 8px; background: #1c222c; }
            QTabBar::tab { background: #242b37; color: #d7deea; border-radius: 7px;
                padding: 11px 14px; margin: 3px; }
            QTabBar::tab:selected { background: #443039; color: white;
                border-bottom: 2px solid #ff6474; }
            QSplitter::handle { background: #3b4351; width: 6px; }
            QListWidget { background: #1d232e; border: 1px solid #404958;
                border-radius: 8px; padding: 4px; }
            QListWidget::item { padding: 8px; border-radius: 5px; }
            QListWidget::item:selected { background: #33495e; color: #ffffff; }
        """)
        self.log("Khởi động thành công. Chưa có API hay quyền đăng nào được kích hoạt mặc định.")

    def log(self, msg):
        line = redact(str(msg))[:1500]
        self.logs.appendPlainText(line)
        try:
            write_event("desktop", line)
        except OSError:
            pass

    def job(self, title, fn, on_done=None, on_error=None):
        work = Work(fn)
        self._workers.add(work)
        work.signals.progress.connect(self.log)

        def success(value):
            self.log(f"✓ {title}: hoàn tất")
            self._workers.discard(work)
            if on_done:
                on_done(value)

        def failure(err):
            self._workers.discard(work)
            self.log(f"✗ {title}: {err}")
            if on_error:
                on_error(err)
            QMessageBox.warning(self, title, redact(err)[:1400])

        work.signals.completed.connect(success)
        work.signals.failed.connect(failure)
        self.log(f"▶ {title}")
        self.pool.start(work)

    def alert(self, error):
        self.log("Lỗi đầu vào: " + str(error))
        QMessageBox.warning(self, "Dữ liệu chưa hợp lệ", redact(str(error)))

    def chooser(self, entry: QLineEdit, *, save=False, multi=False, filter="Video (*.mp4 *.mov);;All files (*)"):
        if save:
            chosen, _ = QFileDialog.getSaveFileName(self, "Đường dẫn xuất", entry.text(), filter)
        elif multi:
            chosen, _ = QFileDialog.getOpenFileNames(self, "Chọn các tệp", "", filter)
            chosen = "\n".join(chosen)
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, "Chọn tệp", "", filter)
        if chosen:
            entry.setText(chosen)

    def build_research(self, layout):
        panel = group("Thư viện từ khóa Trung Quốc (không cần AI)")
        self.research_niche = QComboBox()
        self.research_niche.addItems(KEYWORDS.keys())
        panel.layout().addRow("Ngách", self.research_niche)
        keyword_display = paragraph("Từ khóa sẽ xuất hiện tại đây", 105)
        keyword_display.setReadOnly(True)
        panel.layout().addRow("Từ khóa", keyword_display)
        def refresh():
            keyword_display.setPlainText("\n".join(KEYWORDS[self.research_niche.currentText()]))
        self.research_niche.currentTextChanged.connect(refresh)
        refresh()
        layout.addWidget(panel)
        panel2 = group("Chấm điểm cơ hội thủ công · 0–100")
        self.research_scores = []
        for label in ("Hiểu công dụng trong 3 giây", "Tương tác thực", "Hợp sản phẩm affiliate",
                      "Hình ảnh rõ/ít chữ Trung", "Mức độ mới"):
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(70)
            self.research_scores.append(spin)
            panel2.layout().addRow(label, spin)
        score_button = QPushButton("Tính điểm cơ hội")
        panel2.layout().addRow(score_button)
        score_button.clicked.connect(lambda: self.log("Điểm cơ hội: " + str(opportunity_score(
            *(spin.value() for spin in self.research_scores))) + "/100 (heuristic, không dự đoán doanh thu)"))
        layout.addWidget(panel2)
        panel3 = group("Nguồn đã lưu trong thư viện")
        self.research_saved = paragraph("Chưa có nguồn", 170)
        self.research_saved.setReadOnly(True)
        panel3.layout().addRow(self.research_saved)
        refresh_btn = QPushButton("Làm mới danh sách nguồn")
        refresh_btn.clicked.connect(self.refresh_sources)
        panel3.layout().addRow(refresh_btn)
        layout.addWidget(panel3)
        self.refresh_sources()

    def refresh_sources(self):
        self.research_saved.setPlainText("\n".join(
            f"#{v['id']} · {v['niche'] or 'Chưa chọn ngách'} · {v['url']}"
            for v in self.store.sources()) or "Chưa lưu nguồn")

    def build_download(self, layout):
        """Task-first downloader screen: input on left, run configuration on right."""
        heading = QLabel("Tải video Douyin")
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        description = QLabel("Dán link video hoặc hồ sơ. Ứng dụng tự nhận dạng nguồn và chọn engine hỗ trợ.")
        description.setObjectName("pageDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        row = QWidget()
        columns = QHBoxLayout(row)
        columns.setContentsMargins(0, 5, 0, 0)
        columns.setSpacing(16)

        sources = QGroupBox("01   Nguồn nội dung")
        src = QVBoxLayout(sources)
        src.setSpacing(12)
        self.download_urls = paragraph("Mỗi dòng một URL Douyin. Có thể dán nguyên đoạn chia sẻ.", 145)
        self.download_urls.setMinimumHeight(145)
        src.addWidget(QLabel("Liên kết video hoặc kênh"))
        src.addWidget(self.download_urls)
        self.down_selected_btn = QPushButton("Chỉ lấy video đang mở từ link kênh (?vid)")
        self.down_selected_btn.setToolTip("Dùng video được chọn trong link hồ sơ, không tải cả kênh.")
        self.down_selected_btn.clicked.connect(self.on_download_selected_video)
        self.down_selected_btn.setEnabled(False)
        src.addWidget(self.down_selected_btn)
        self.down_mode = QComboBox()
        self.down_mode.addItem("Tự nhận dạng (khuyên dùng)", "auto")
        self.down_mode.addItem("Chỉ tải video đơn lẻ / danh sách", "batch")
        self.down_mode.addItem("Tải bài đăng của kênh", "channel")
        src.addWidget(QLabel("Loại nguồn"))
        src.addWidget(self.down_mode)
        self.down_detect = QLabel("Dán URL để kiểm tra loại nguồn.")
        self.down_detect.setObjectName("hintText")
        self.down_detect.setWordWrap(True)
        src.addWidget(self.down_detect)
        src.addStretch(1)

        rights = QGroupBox("Quyền sử dụng")
        rights_layout = QVBoxLayout(rights)
        self.check_commercial = QCheckBox("Video được cấp quyền sử dụng thương mại")
        self.check_derivative = QCheckBox("Có quyền chỉnh sửa và đăng lại video")
        rights_layout.addWidget(self.check_commercial)
        rights_layout.addWidget(self.check_derivative)
        rights_help = QLabel("Không yêu cầu tải lên hợp đồng hay giấy tờ cá nhân. "
                             "Bạn tự chịu trách nhiệm tuân thủ quyền sử dụng nội dung và yêu cầu ghi nguồn.")
        rights_help.setWordWrap(True)
        rights_help.setObjectName("hintText")
        rights_layout.addWidget(rights_help)
        src.addWidget(rights)
        columns.addWidget(sources, 3)

        options = QGroupBox("02   Cài đặt tải xuống")
        form = QVBoxLayout(options)
        form.setSpacing(11)
        form.addWidget(QLabel("Thư mục lưu"))
        self.down_folder = field("Thư mục lưu video", str(user_data_dir() / "downloads"))
        form.addWidget(self.down_folder)
        browse = QPushButton("Chọn thư mục")
        browse.clicked.connect(lambda: self._folder(self.down_folder))
        form.addWidget(browse)
        form.addWidget(QLabel("Số video tối đa"))
        self.down_limit = QSpinBox()
        self.down_limit.setRange(0, 5000)
        self.down_limit.setSpecialValueText("Không giới hạn (chỉ nguyên kênh)")
        self.down_limit.setValue(50)
        form.addWidget(self.down_limit)
        form.addWidget(QLabel("Ngách sản phẩm"))
        self.down_niche = QComboBox()
        self.down_niche.addItems(KEYWORDS.keys())
        form.addWidget(self.down_niche)
        self.down_engine = QLabel("")
        self.down_engine.setObjectName("hintText")
        self.down_engine.setWordWrap(True)
        form.addWidget(self.down_engine)
        form.addStretch(1)
        self.down_progress = QProgressBar()
        self.down_progress.setRange(0, 100)
        self.down_progress.setValue(0)
        self.down_progress.setFormat("Sẵn sàng")
        form.addWidget(self.down_progress)
        self.down_button = QPushButton("Bắt đầu tải video")
        self.down_button.setObjectName("primaryAction")
        self.down_button.setMinimumHeight(45)
        self.down_button.clicked.connect(self.on_download)
        form.addWidget(self.down_button)
        columns.addWidget(options, 2)
        layout.addWidget(row)

        history = QGroupBox("03   Video đã lưu gần đây")
        history_layout = QVBoxLayout(history)
        self.down_history = QPlainTextEdit()
        self.down_history.setReadOnly(True)
        self.down_history.setMaximumHeight(125)
        self.down_history.setPlaceholderText("Video tải xong sẽ xuất hiện trong thư mục đã chọn.")
        history_layout.addWidget(self.down_history)
        layout.addWidget(history)
        self.download_urls.textChanged.connect(self.on_down_urls_change)
        self.down_mode.currentIndexChanged.connect(self.on_down_urls_change)
        self.on_down_urls_change()
        self.refresh_download_history()

    def refresh_download_history(self):
        rows = [row for row in self.store.sources() if row.get("file_path")]
        self.down_history.setPlainText("\n".join(
            Path(v["file_path"]).name + "   ·   " + v["url"] for v in rows[:12]
        ) or "Chưa có video nào được ghi nhận. Hãy tải nguồn được cấp phép.")

    def on_down_urls_change(self, *_):
        text = self.download_urls.toPlainText().strip()
        if not text:
            self.down_selected_btn.setEnabled(False)
            self.down_detect.setText("Nhập URL Douyin để xác định chế độ tải.")
            self.down_engine.setText("Video: yt-dlp    •    Nguyên kênh: F2 chuyên dụng")
            return
        try:
            urls = parse_douyin_urls(text)
            profiles = sum(is_channel_url(link) for link in urls)
            videos = len(urls) - profiles
            self.down_selected_btn.setEnabled(
                len(urls) == 1 and selected_video_from_profile(urls[0]) is not None)
            mode = self.down_mode.currentData()
            if mode == "auto":
                self.down_detect.setText(
                    f"Nhận diện: {profiles} kênh, {videos} liên kết video. "
                    "Ứng dụng sẽ chọn đúng engine cho từng URL."
                )
            else:
                self.down_detect.setText(f"Nhận diện: {profiles} kênh, {videos} liên kết video.")
            ready = f2_worker_executable() is not None
            self.down_engine.setText(
                ("F2: đã cài trong bản portable" if ready else
                 "F2: chưa tìm thấy engine trong thư mục bin") +
                "   •   yt-dlp: tải video đơn lẻ"
            )
        except ValueError as exc:
            self.down_selected_btn.setEnabled(False)
            self.down_detect.setText(str(exc))
            self.down_engine.setText("Hãy nhập liên kết Douyin HTTPS hợp lệ.")

    def on_download_selected_video(self):
        try:
            urls = parse_douyin_urls(self.download_urls.toPlainText())
            if len(urls) != 1:
                raise ValueError("Hãy nhập một URL hồ sơ có video được chọn.")
            selected = selected_video_from_profile(urls[0])
            if selected is None:
                raise ValueError("Link không chứa ?vid= hợp lệ.")
            self.download_urls.setPlainText(selected)
            self.down_mode.setCurrentIndex(0)
            self.log("Đã chọn video đang mở: " + selected)
        except ValueError as exc:
            self.alert(exc)

    def _folder(self, entry):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục", entry.text())
        if folder:
            entry.setText(folder)

    def on_download(self):
        try:
            urls = parse_douyin_urls(self.download_urls.toPlainText())
            grants = [LicenseGrant(url, "", "", self.check_commercial.isChecked(),
                                   self.check_derivative.isChecked()) for url in urls]
            for grant in grants:
                grant.validate()
            folder = Path(self.down_folder.text()).expanduser()
            limit = self.down_limit.value()
            mode = self.down_mode.currentData()
            niche = self.down_niche.currentText()
            if mode == "channel" and any(not is_channel_url(url) for url in urls):
                raise ValueError("Chế độ Nguyên kênh chỉ nhận URL /user/....")
            if mode == "batch" and any(is_channel_url(url) for url in urls):
                raise ValueError("Bạn đã dán URL kênh. Chuyển sang Tự nhận diện để dùng F2.")
            if limit == 0 and any(is_channel_url(url) for url in urls):
                answer = QMessageBox.question(
                    self, "Tải không giới hạn",
                    "Tải toàn bộ nội dung kênh có thể tốn nhiều dung lượng. Tiếp tục?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return
            if mode == "batch" and limit == 0:
                raise ValueError("Video đơn lẻ yêu cầu giới hạn tải lớn hơn 0.")
        except Exception as exc:
            return self.alert(exc)

        self.down_button.setEnabled(False)
        self.down_progress.setRange(0, 0)
        self.down_progress.setFormat("Đang tải...")
        def task(report):
            completed = 0
            failed = []
            for index, grant in enumerate(grants, 1):
                report(f"Nguồn {index}/{len(grants)}: {grant.original_url}")
                try:
                    self.store.save_source(grant, niche)
                    completed += len(download_authorized(
                        grant.original_url, folder, grant, self.store, limit, report, mode=mode))
                except Exception as exc:
                    failed.append(f"{index}: {redact(str(exc))}")
                    report(f"Không thành công nguồn {index}: {redact(str(exc))}")
            return completed, failed

        def done(result):
            completed, failed = result
            self.down_button.setEnabled(True)
            self.down_progress.setRange(0, 100)
            self.down_progress.setValue(100 if not failed else 0)
            self.down_progress.setFormat(f"{completed} video mới" if not failed else
                                         f"{completed} video, {len(failed)} nguồn lỗi")
            self.refresh_sources()
            self.refresh_download_history()
            if failed:
                QMessageBox.warning(self, "Một số nguồn chưa tải được",
                                    "\n".join(failed[:8]) + "\nBạn có thể thử từng URL video.")
            else:
                QMessageBox.information(self, "Đã hoàn tất", f"Đã ghi nhận {completed} video mới.")

        def failed(_):
            self.down_button.setEnabled(True)
            self.down_progress.setRange(0, 100)
            self.down_progress.setValue(0)
            self.down_progress.setFormat("Lỗi tải")
        self.job("Tải Douyin", task, done, on_error=failed)

    def build_editor(self, layout):
        """Embed the real playable editor rather than a long FFmpeg settings form."""
        from .editor_workspace import EditorWorkspace
        self.editor_workspace = EditorWorkspace(self)
        layout.addWidget(self.editor_workspace, 1)

    def build_translation(self, layout):
        panel = group("Nhận dạng Trung → SRT · chạy offline với faster-whisper")
        self.stt_file = field("Đường dẫn video có lời nói tiếng Trung")
        self.stt_model = QComboBox()
        self.stt_model.addItems(["tiny", "base", "small", "medium"])
        self.stt_model.setCurrentText("small")
        browse = QPushButton("Chọn video")
        browse.clicked.connect(lambda: self.chooser(self.stt_file))
        panel.layout().addRow("Video", self.stt_file)
        panel.layout().addRow(browse)
        panel.layout().addRow("Model offline", self.stt_model)
        go = QPushButton("TẠO PHỤ ĐỀ TRUNG (.srt)")
        go.clicked.connect(self.on_transcribe)
        panel.layout().addRow(go)
        layout.addWidget(panel)
        trans = group("Gemini Free API · Dịch phụ đề Trung → Việt")
        self.translate_src = field("File SRT tiếng Trung")
        self.translate_dest = field("File SRT tiếng Việt")
        self.translate_model = field("Model phải có quyền dùng Free Tier", "gemini-3.1-flash-lite")
        self.translate_confirm = QCheckBox("Tôi xác nhận Gemini project đang ở Free Tier và hiểu hạn mức thực tế")
        self.translate_niche = QComboBox()
        self.translate_niche.addItems(["Gia dụng", "Nhà bếp", "Mỹ phẩm"])
        self.translate_niche.currentTextChanged.connect(self.on_load_glossary)
        self.translate_context = paragraph("Ví dụ: video hướng dẫn đồ bếp, đối tượng người xem là sinh viên", 70)
        self.translate_glossary = paragraph("Glossary JSON Trung → Việt", 110)
        self.translate_review = QCheckBox("Hậu kiểm bản dịch bằng lượt Gemini thứ hai (tốn thêm quota)")
        save_terms = QPushButton("LƯU GLOSSARY NGÁCH")
        save_terms.clicked.connect(self.on_save_glossary)
        self.on_load_glossary()
        browse_srt = QPushButton("Chọn SRT nguồn")
        browse_srt.clicked.connect(lambda: self.chooser(self.translate_src, filter="SRT (*.srt)"))
        for label, w in (("Nguồn", self.translate_src), ("", browse_srt), ("Đích", self.translate_dest),
                     ("Model", self.translate_model), ("Ngách", self.translate_niche),
                     ("Glossary JSON", self.translate_glossary), ("", save_terms),
                     ("Ngữ cảnh", self.translate_context), ("", self.translate_review),
                     ("", self.translate_confirm)):
            trans.layout().addRow(label, w)
        btn = QPushButton("DỊCH BẰNG GEMINI (không tự trả phí)")
        btn.clicked.connect(self.on_translate)
        trans.layout().addRow(btn)
        layout.addWidget(trans)
        voice = group("Lồng tiếng · SAPI/pyttsx3 hoặc Piper local")
        self.voice_text = paragraph("Dán lời thoại tiếng Việt (cần Windows cài giọng tiếng Việt)", 100)
        self.voice_dest = field("Đường dẫn WAV đích", str(user_data_dir() / "voice.wav"))
        self.voice_engine = QComboBox()
        self.voice_engine.addItem("Giọng hệ thống (SAPI / pyttsx3)", "system")
        self.voice_engine.addItem("Piper offline (cần model giọng Việt)", "piper")
        self.piper_exe = field("Đường dẫn piper.exe")
        self.piper_model = field("Đường dẫn model Piper .onnx")
        voice.layout().addRow("Engine", self.voice_engine)
        voice.layout().addRow("Piper", self.piper_exe)
        voice.layout().addRow("Model Piper", self.piper_model)
        voice.layout().addRow("Lời thoại", self.voice_text)
        voice.layout().addRow("Xuất", self.voice_dest)
        voice_btn = QPushButton("TẠO GIỌNG ĐỌC VIỆT (.wav)")
        voice_btn.clicked.connect(self.on_voice)
        voice.layout().addRow(voice_btn)
        layout.addWidget(voice)

    def on_load_glossary(self, *_):
        try:
            terms = load_glossary(self.translate_niche.currentText())
            self.translate_glossary.setPlainText(json.dumps(terms, ensure_ascii=False, indent=2))
        except Exception as exc:
            self.alert(exc)

    def on_save_glossary(self):
        try:
            terms = validate_glossary(json.loads(self.translate_glossary.toPlainText()))
            self.log("Đã lưu: " + str(save_glossary(self.translate_niche.currentText(), terms)))
        except Exception as exc:
            self.alert(exc)

    def on_transcribe(self):
        source = Path(self.stt_file.text())
        target = source.with_suffix(".zh.srt")
        model = self.stt_model.currentText()
        self.job("Nhận dạng tiếng Trung", lambda report: transcribe_to_srt(source, target, model_name=model),
                 lambda path: (self.log(f"SRT: {path}"), self.translate_src.setText(str(path)),
                               self.translate_dest.setText(str(path.with_suffix(".vi.srt")))))

    def on_translate(self):
        source = Path(self.translate_src.text())
        target = Path(self.translate_dest.text())
        model = self.translate_model.text().strip()
        confirmed = self.translate_confirm.isChecked()
        try:
            secret = get_secret("gemini")
            if not secret:
                raise ValueError("Chưa lưu Gemini API key ở tab Cài đặt.")
            if source.resolve() == target.resolve():
                raise ValueError("Phải dùng file SRT đích khác file nguồn.")
            terms = validate_glossary(json.loads(self.translate_glossary.toPlainText()))
            context = self.translate_context.toPlainText()
            review = self.translate_review.isChecked()
        except Exception as exc:
            return self.alert(exc)
        self.job("Dịch phụ đề Gemini", lambda report: translate_srt(source, target, self.store,
                     api_key=secret, model_name=model, confirmed_free_tier=confirmed,
                     glossary=terms, context=context, review=review),
                 lambda path: (self.log(f"Đã dịch: {path}"), self.edit_srt.setText(str(path))))

    def on_voice(self):
        text = self.voice_text.toPlainText()
        target = Path(self.voice_dest.text())
        try:
            engine = get_tts_engine(self.voice_engine.currentData(),
                                   piper_exe=Path(self.piper_exe.text()),
                                   piper_model=Path(self.piper_model.text()))
        except Exception as exc:
            return self.alert(exc)
        self.job("Giọng đọc Việt", lambda report: engine.synthesize(text, target),
                 lambda path: (self.log(f"WAV: {path}"), self.edit_narration.setText(str(path))))

    def build_affiliate(self, layout):
        panel = group("Kho sản phẩm affiliate & chiến dịch theo ngách")
        self.product_name = field("Tên sản phẩm")
        self.product_link = field("https://... (link affiliate chính thức)")
        self.product_niche = QComboBox()
        self.product_niche.addItems(KEYWORDS.keys())
        self.product_campaign = field("VD: thu hút người xem / bán sản phẩm / tăng follow")
        for name, widget in (("Sản phẩm", self.product_name), ("Link hoa hồng", self.product_link),
                             ("Ngách", self.product_niche), ("Chiến dịch", self.product_campaign)):
            panel.layout().addRow(name, widget)
        save = QPushButton("LƯU SẢN PHẨM")
        save.clicked.connect(self.on_product)
        panel.layout().addRow(save)
        self.products_view = paragraph("Kho sản phẩm sẽ hiển thị tại đây", 190)
        self.products_view.setReadOnly(True)
        panel.layout().addRow(self.products_view)
        layout.addWidget(panel)
        metrics = group("Hiệu quả chiến dịch · tính từ số liệu thực nhập")
        self.metric_fields = []
        for name in ("Lượt xem", "Click", "Đơn", "Hoa hồng"):
            spin = QDoubleSpinBox() if name == "Hoa hồng" else QSpinBox()
            spin.setRange(0, 999_999_999)
            self.metric_fields.append(spin)
            metrics.layout().addRow(name, spin)
        calc = QPushButton("TÍNH CTR · CHUYỂN ĐỔI · RPM")
        calc.clicked.connect(self.on_metrics)
        metrics.layout().addRow(calc)
        layout.addWidget(metrics)
        report = group("Báo cáo affiliate CSV theo campaign / video_id / platform")
        self.affiliate_report = field("CSV có campaign, video_id, platform, views, clicks, orders, commission")
        report.layout().addRow("CSV", self.affiliate_report)
        browse = QPushButton("Chọn CSV báo cáo")
        browse.clicked.connect(lambda: self.chooser(self.affiliate_report, filter="CSV (*.csv)"))
        report.layout().addRow(browse)
        run = QPushButton("TỔNG HỢP VIDEO → CLICK → ĐƠN → HOA HỒNG")
        run.clicked.connect(self.on_affiliate_report)
        report.layout().addRow(run)
        self.report_summary = paragraph("Chưa nhập báo cáo", 200)
        self.report_summary.setReadOnly(True)
        report.layout().addRow(self.report_summary)
        layout.addWidget(report)
        self.refresh_products()

    def on_affiliate_report(self):
        self.job("Báo cáo affiliate", lambda report: import_report(Path(self.affiliate_report.text())),
                 lambda rows: self.report_summary.setPlainText(json.dumps(rows, ensure_ascii=False, indent=2)))

    def on_product(self):
        try:
            self.store.save_product(self.product_name.text(), self.product_niche.currentText(),
                                    self.product_link.text(), self.product_campaign.text())
            self.refresh_products()
        except Exception as exc:
            self.alert(exc)

    def refresh_products(self):
        self.products_view.setPlainText("\n".join(
            f"#{p['id']} [{p['niche']}] {p['name']} | {p['campaign']} | {p['affiliate_url']}"
            for p in self.store.products()) or "Chưa có sản phẩm")

    def on_metrics(self):
        try:
            metrics = Metrics(*(x.value() for x in self.metric_fields)).as_dict()
            self.log(f"CTR {metrics['ctr_percent']}% | CVR {metrics['conversion_percent']}% | "
                     f"Hoa hồng / 1.000 view: {metrics['revenue_per_1000_views']}")
        except Exception as exc:
            self.alert(exc)

    def build_publish(self, layout):
        panel = group("Lên lịch qua Postiz · kết nối cloud độc lập (máy tắt vẫn có thể đăng)")
        explanation = QLabel("Chỉ sử dụng các kênh đã OAuth và được Postiz hỗ trợ.\n"
                             "Upload lên cloud trước khi tắt máy; lịch trên máy không tự chạy khi máy tắt.")
        explanation.setWordWrap(True)
        panel.layout().addRow(explanation)
        self.postiz_file = field("Video đã render .mp4")
        browse = QPushButton("Chọn MP4 xuất bản")
        browse.clicked.connect(lambda: self.chooser(self.postiz_file))
        self.postiz_date = QDateTimeEdit()
        self.postiz_date.setCalendarPopup(True)
        self.postiz_date.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.postiz_date.setDateTime(QDateTime.currentDateTime().addDays(1))
        self.postiz_caption = paragraph("Viết CTA có thể dùng trên nền tảng đích, khai báo affiliate và ghi nguồn Douyin", 130)
        self.postiz_integrations = paragraph('Ví dụ: [{"id":"integration-id","provider":"youtube","settings":{"__type":"youtube"}}]', 150)
        get_channels = QPushButton("XEM CÁC KÊNH ĐÃ KẾT NỐI POSTIZ")
        get_channels.clicked.connect(self.on_channels)
        for label, widget in (("Video", self.postiz_file), ("", browse), ("Ngày/giờ máy", self.postiz_date),
                              ("Nội dung/nguồn", self.postiz_caption), ("Kênh + settings JSON", self.postiz_integrations),
                              ("", get_channels)):
            panel.layout().addRow(label, widget)
        self.postiz_review = QCheckBox("Tôi đã rà soát quyền đăng, nguồn, link affiliate và thông số từng kênh")
        panel.layout().addRow(self.postiz_review)
        schedule = QPushButton("UPLOAD & LÊN LỊCH BÀI ĐĂNG THẬT")
        schedule.clicked.connect(self.on_schedule)
        panel.layout().addRow(schedule)
        layout.addWidget(panel)

    def _postiz_credentials(self):
        secret = get_secret("postiz")
        if not secret:
            raise ValueError("Chưa lưu Postiz API key ở Cài đặt.")
        return secret, self.postiz_base.text().strip()

    def on_channels(self):
        try:
            secret, base = self._postiz_credentials()
        except Exception as exc:
            return self.alert(exc)

        def task(report):
            with PostizClient(secret, base) as client:
                return client.integrations()
        def done(integrations):
            self.log(f"Đã tìm thấy {len(integrations)} kênh. Cần điều chỉnh provider settings trước khi lên lịch.")
            selected = []
            for item in integrations:
                provider = item.get("identifier") or item.get("provider") or item.get("type") or ""
                selected.append({"id": item.get("id"), "provider": provider,
                                 "settings": {"__type": provider}})
            self.postiz_integrations.setPlainText(json.dumps(selected, ensure_ascii=False, indent=2))
        self.job("Tải các kênh Postiz", task, done)

    def on_schedule(self):
        try:
            if not self.postiz_review.isChecked():
                raise PermissionError("Cần đánh dấu duyệt quyền và kiểm tra trước khi đăng.")
            secret, base = self._postiz_credentials()
            video = Path(self.postiz_file.text())
            caption = self.postiz_caption.toPlainText().strip()
            configs = json.loads(self.postiz_integrations.toPlainText())
            if not isinstance(configs, list):
                raise ValueError("Danh sách kênh phải là JSON array.")
            scheduled = self.postiz_date.dateTime().toPython().astimezone()
            if not video.is_file():
                raise FileNotFoundError(video)
            if "nguồn" not in caption.lower() and "source" not in caption.lower():
                raise ValueError("Mô tả phải ghi nguồn rõ ràng trước khi xuất bản.")
        except Exception as exc:
            return self.alert(exc)

        def task(report):
            with PostizClient(secret, base) as client:
                return client.schedule(video, scheduled, configs, caption)
        def done(value):
            self.log(f"Đã gửi yêu cầu lịch đăng {value['scheduled_at']} tới {value['target_count']} kênh. "
                     "Kiểm tra phản hồi Postiz và trạng thái bài trước khi xem là đã xuất bản.")
            self.log("Postiz response: " + str(value["response"])[:900])
            self.store.record_publication(None, "postiz", value["scheduled_at"],
                                          str(value["response"])[:300], "accepted_by_api")
        self.job("Đặt lịch đăng qua Postiz", task, done)

    def build_settings(self, layout):
        panel = group("API credentials · Windows Credential Manager / keyring")
        self.gemini_secret = QLineEdit()
        self.gemini_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_secret.setPlaceholderText("Nhập GEMINI_API_KEY (không commit lên GitHub)")
        save_gemini = QPushButton("Lưu Gemini API key an toàn")
        save_gemini.clicked.connect(lambda: self.on_secret("gemini", self.gemini_secret))
        self.postiz_secret = QLineEdit()
        self.postiz_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.postiz_secret.setPlaceholderText("Nhập Postiz API key")
        save_postiz = QPushButton("Lưu Postiz API key an toàn")
        save_postiz.clicked.connect(lambda: self.on_secret("postiz", self.postiz_secret))
        self.postiz_base = field("Postiz Public API URL", "https://api.postiz.com")
        panel.layout().addRow("Gemini", self.gemini_secret)
        panel.layout().addRow(save_gemini)
        panel.layout().addRow("Postiz", self.postiz_secret)
        panel.layout().addRow(save_postiz)
        panel.layout().addRow("Postiz URL", self.postiz_base)
        layout.addWidget(panel)
        status = group("Kiểm tra môi trường")
        check = QPushButton("KIỂM TRA FFMPEG / FFPROBE")
        def perform_check():
            for name in ("ffmpeg", "ffprobe"):
                try:
                    self.log(f"{name}: {find_binary(name)}")
                except FileNotFoundError as exc:
                    self.log(str(exc))
        check.clicked.connect(perform_check)
        status.layout().addRow(check)
        ytdlp_check = QPushButton("KIỂM TRA yt-dlp")
        ytdlp_check.clicked.connect(self.on_downloader_check)
        ytdlp_update = QPushButton("CẬP NHẬT yt-dlp CHÍNH THỨC · checksum SHA-256")
        ytdlp_update.clicked.connect(self.on_downloader_update)
        status.layout().addRow(ytdlp_check)
        status.layout().addRow(ytdlp_update)
        ocr_check = QPushButton("KIỂM TRA RAPIDOCR OFFLINE (không tải model)")
        ocr_check.clicked.connect(self.on_ocr_check)
        status.layout().addRow(ocr_check)
        logs_button = QPushButton("XUẤT LOG ĐÃ CHE API KEY")
        logs_button.clicked.connect(self.on_export_logs)
        status.layout().addRow(logs_button)
        private = QPushButton("XÓA dữ liệu tác giả / bằng chứng cũ trong SQLite")
        private.clicked.connect(self.on_scrub_private)
        status.layout().addRow(private)
        status.layout().addRow(QLabel("Thư mục dữ liệu: " + str(user_data_dir())))
        layout.addWidget(status)

    def on_scrub_private(self):
        confirm = QMessageBox.question(self, "Xóa dữ liệu riêng tư cũ",
             "Xóa vĩnh viễn thông tin tác giả, hợp đồng và ngày hết hạn lưu trong SQLite?\n"
             "Không xóa các video hay file JSON đã xuất ra từ các phiên bản cũ.",
             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.store.scrub_private_metadata()
            self.log("Đã xóa metadata riêng tư cũ khỏi SQLite.")
            self.refresh_sources()

    def on_downloader_check(self):
        status = downloader_status()
        message = f"Phiên bản: {status.version or 'chưa có'}\nNguồn: {status.origin}\n{status.diagnostic}"
        QMessageBox.information(self, "Kiểm tra yt-dlp", message)

    def on_downloader_update(self):
        answer = QMessageBox.question(self, "Cập nhật yt-dlp", "Tải yt-dlp.exe từ GitHub chính thức, "
                                      "xác minh 2 nguồn SHA-256 và lưu vào thư mục người dùng?\n"
                                      "Không thay đổi file .exe của Douyinhehe.",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.job("Cập nhật yt-dlp", lambda report: update_ytdlp(confirmed=True),
                     lambda status: self.log(status.diagnostic + " · " + status.version))

    def on_export_logs(self):
        target, _ = QFileDialog.getSaveFileName(self, "Lưu nhật ký an toàn",
                            str(user_data_dir() / "Douyinhehe-diagnostics.jsonl"), "JSON Lines (*.jsonl)")
        if not target:
            return
        try:
            file = export_redacted_logs(Path(target))
            self.log(f"Đã xuất log đã che khóa: {file}")
        except Exception as exc:
            self.alert(exc)

    def build_batch_queue(self, layout):
        panel = group("Hàng đợi hàng loạt · CSV/JSON hoặc video tự quay")
        panel.layout().addRow(QLabel("CSV tối thiểu: file, original_url, commercial, derivative.\n"
                                    "Không yêu cầu tác giả, hợp đồng, ngày hết hạn."))
        self.batch_manifest = field("Đường dẫn CSV/JSON")
        self.local_folder = field("Thư mục video local đã có quyền sử dụng")
        self.local_rights = QCheckBox("Tôi có quyền chỉnh sửa và khai thác thương mại những video này")
        browse = QPushButton("Chọn manifest CSV/JSON")
        browse.clicked.connect(lambda: self.chooser(self.batch_manifest,
                              filter="Manifest (*.csv *.json);;All files (*)"))
        self.batch_out = field("Thư mục xuất video", str(user_data_dir() / "exports"))
        folder_btn = QPushButton("Chọn thư mục xuất")
        folder_btn.clicked.connect(lambda: self._folder(self.batch_out))
        for label, w in (("Danh sách", self.batch_manifest), ("", browse),
                         ("Video local", self.local_folder), ("", self.local_rights),
                         ("Xuất", self.batch_out), ("", folder_btn)):
            panel.layout().addRow(label, w)
        local_btn = QPushButton("TẠO MANIFEST TỪ THƯ MỤC")
        local_btn.clicked.connect(self.on_local_manifest)
        panel.layout().addRow(local_btn)
        for title, callback in (
            ("THÊM HÀNG ĐỢI (CHỐNG TRÙNG)", self.on_enqueue_manifest),
            ("CHẠY HÀNG ĐỢI", self.on_batch_run),
            ("Thử lại các tác vụ lỗi", self.on_batch_retry),
            ("Khôi phục các tác vụ bị ngắt", self.on_batch_recover),
            ("Làm mới", self.refresh_batch),
        ):
            button = QPushButton(title)
            button.clicked.connect(callback)
            panel.layout().addRow(button)
        self.batch_view = paragraph("Hàng đợi trống", 210)
        self.batch_view.setReadOnly(True)
        panel.layout().addRow(self.batch_view)
        layout.addWidget(panel)
        self.refresh_batch()

    def on_local_manifest(self):
        try:
            target = user_data_dir() / "imports" / "local-videos.json"
            file = create_local_manifest(Path(self.local_folder.text()), target,
                                         rights_confirmed=self.local_rights.isChecked())
            self.batch_manifest.setText(str(file))
            self.log("Đã tạo manifest: " + str(file))
        except Exception as exc:
            self.alert(exc)

    def refresh_batch(self):
        lines = [f"#{j['id']} · {j['status']} · thử {j['attempts']} · "
                 f"{(j['result_path'] or j['error'] or j['job_key'][:10])[:110]}"
                 for j in self.store.render_jobs()]
        self.batch_view.setPlainText("\n".join(lines) or "Hàng đợi trống")
        self.log("Hàng đợi: " + str(self.store.render_counts()))

    def on_enqueue_manifest(self):
        try:
            added, existing = enqueue_manifest(self.store, Path(self.batch_manifest.text()))
            self.log(f"Đã xếp hàng {added} file; {existing} tác vụ trùng được bỏ qua.")
            self.refresh_batch()
        except Exception as exc:
            self.alert(exc)

    def on_batch_run(self):
        target = Path(self.batch_out.text())
        self.job("Batch Render 2.0", lambda progress: run_queue(self.store, target, progress),
                 lambda report: (self.log("Batch: " + str(report)), self.refresh_batch()))

    def on_batch_retry(self):
        self.log(f"Đã mở lại {self.store.retry_failed_renders()} tác vụ lỗi.")
        self.refresh_batch()

    def on_batch_recover(self):
        yes = QMessageBox.question(
            self, "Khôi phục tác vụ", "Chỉ chọn khi không còn phiên Douyinhehe khác đang chạy.\n"
            "Khôi phục các render bị ngắt?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if yes == QMessageBox.StandardButton.Yes:
            self.log(f"Đã khôi phục {self.store.recover_interrupted_renders()} tác vụ.")
            self.refresh_batch()

    def build_delivery_check(self, layout):
        panel = group("Kiểm tra kỹ thuật video trước khi lên lịch")
        self.delivery_file = field("Chọn video đã render để kiểm tra kỹ thuật")
        browse = QPushButton("Chọn MP4")
        browse.clicked.connect(lambda: self.chooser(self.delivery_file))
        self.delivery_platform = QComboBox()
        for key, item in DESTINATIONS.items():
            self.delivery_platform.addItem(item.label, key)
        self.delivery_credit = paragraph("Dán mô tả có nguồn video và công khai affiliate", 115)
        self.delivery_result = paragraph("Chưa kiểm tra", 210)
        self.delivery_result.setReadOnly(True)
        for label, widget in (("Video", self.delivery_file), ("", browse),
                              ("Nền tảng", self.delivery_platform),
                              ("Mô tả", self.delivery_credit),
                              ("Kết quả", self.delivery_result)):
            panel.layout().addRow(label, widget)
        run = QPushButton("KIỂM TRA VIDEO / CTA / NGUỒN")
        run.clicked.connect(self.on_delivery_check)
        panel.layout().addRow(run)
        layout.addWidget(panel)

    def on_delivery_check(self):
        path = Path(self.delivery_file.text())
        credit = self.delivery_credit.toPlainText()
        platform = self.delivery_platform.currentData()
        self.job("Kiểm tra video", lambda progress: delivery_preflight(path, credit=credit, platform=platform),
                 lambda data: self.delivery_result.setPlainText(json.dumps(data, ensure_ascii=False, indent=2)))

    def on_secret(self, key, field):
        try:
            save_secret(key, field.text())
            field.clear()
            self.log("Đã lưu bí mật trong kho thông tin đăng nhập hệ điều hành: " + key)
        except Exception as exc:
            self.alert(exc)


def launch():
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("Douyinhehe Pro")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
