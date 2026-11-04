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
from .downloader import download_authorized, parse_douyin_urls, is_channel_url
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
        self.setWindowTitle("Douyinhehe Studio 3.0 · Affiliate Video Editor")
        self.setMinimumSize(1160, 780)
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
        sidebar.setFixedWidth(210)
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
        heading = QLabel("Thư viện · Studio · Xuất bản")
        heading.setObjectName("heading")
        body.addWidget(heading)
        intro = QLabel("Douyinhehe 3.0  |  Tải hàng loạt  |  Biên tập bằng FFmpeg")
        intro.setObjectName("subheading")
        body.addWidget(intro)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumHeight(85)
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
            layout.addStretch()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            self.pages.addWidget(scroll)
            self.nav.addItem(title)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(2)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0f0f0f; color: #f1f1f1; font-family: 'Segoe UI'; font-size: 12px; }
            QFrame#sidebar, QListWidget#navigation { background: #171717; border: none; }
            QLabel#brand { font-size: 19px; font-weight: 800; color: #ff3333; padding: 5px 0 16px 0; }
            QLabel#heading { font-size: 22px; font-weight: 700; padding: 3px 0; }
            QLabel#subheading { font-size: 11px; color: #aaaaaa; padding-bottom: 8px; }
            QListWidget#navigation::item { padding: 12px 12px; margin: 2px 0; border-radius: 8px; color: #cccccc; }
            QListWidget#navigation::item:selected { background: #3a2020; color: #ffffff; border-left: 3px solid #ff3333; }
            QListWidget#navigation::item:hover { background: #292929; }
            QGroupBox { border: 1px solid #343434; border-radius: 12px; margin-top: 18px; padding: 12px; font-weight: 600; background: #1a1a1a; }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 7px; color: #f1f1f1; }
            QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateTimeEdit {
                background: #222; border: 1px solid #414141; border-radius: 8px; padding: 9px; color: #f1f1f1;
            }
            QLineEdit:focus, QPlainTextEdit:focus { border-color: #ff4444; }
            QPushButton { background: #373737; color: white; border: 1px solid #4a4a4a; border-radius: 18px; padding: 10px 15px; font-weight: 600; }
            QPushButton:hover { background: #505050; }
            QPushButton:pressed { background: #bb1f1f; }
            QPushButton:disabled { background: #242424; color: #6f6f6f; }
            QCheckBox { padding: 6px; }
            QScrollArea { border: none; }
            QSlider::groove:horizontal { height: 6px; background: #474747; border-radius: 3px; }
            QSlider::handle:horizontal { background: #ff4545; width: 14px; margin: -5px 0; border-radius: 7px; }
        """)
        self.log("Khởi động thành công. Chưa có API hay quyền đăng nào được kích hoạt mặc định.")

    def log(self, msg):
        line = redact(str(msg))[:1500]
        self.logs.appendPlainText(line)
        try:
            write_event("desktop", line)
        except OSError:
            pass

    def job(self, title, fn, on_done=None):
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
        panel = group("Tải Douyin hàng loạt · video có giấy phép")
        self.download_urls = paragraph("Dán link Douyin (mỗi dòng 1 link hoặc nguyên nội dung chia sẻ)", 120)
        panel.layout().addRow("Nguồn video", self.download_urls)
        self.down_creator = field("Tác giả/chủ sở hữu nội dung")
        self.down_evidence = field("Mã hợp đồng hoặc tham chiếu bằng chứng cấp phép")
        self.down_evidence_file = field("File bằng chứng (tùy chọn, tính SHA-256)")
        self.down_expiry = field("Hết hạn giấy phép YYYY-MM-DD (bỏ trống nếu không có)")
        self.down_folder = field("Thư mục lưu file", str(user_data_dir() / "downloads"))
        folder_btn = QPushButton("Chọn thư mục")
        folder_btn.clicked.connect(lambda: self._folder(self.down_folder))
        self.down_niche = QComboBox()
        self.down_niche.addItems(KEYWORDS.keys())
        self.down_limit = QSpinBox()
        self.down_limit.setRange(1, 200)
        self.down_limit.setValue(30)
        self.check_commercial = QCheckBox("Tôi có quyền khai thác thương mại / affiliate")
        self.check_derivative = QCheckBox("Tôi có quyền sửa, tái đăng và phân phối theo giấy phép")
        panel.layout().addRow("Tác giả", self.down_creator)
        panel.layout().addRow("Bằng chứng", self.down_evidence)
        panel.layout().addRow("File bằng chứng", self.down_evidence_file)
        panel.layout().addRow("Hết hạn", self.down_expiry)
        panel.layout().addRow("Ngách", self.down_niche)
        panel.layout().addRow("Thư mục", self.down_folder)
        panel.layout().addRow(folder_btn)
        panel.layout().addRow("Tối đa/link", self.down_limit)
        panel.layout().addRow(self.check_commercial)
        panel.layout().addRow(self.check_derivative)
        go = QPushButton("TẢI HÀNG LOẠT (chỉ nội dung được cấp phép)")
        go.clicked.connect(self.on_download)
        panel.layout().addRow(go)
        layout.addWidget(panel)

    def _folder(self, entry):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục", entry.text())
        if folder:
            entry.setText(folder)

    def on_download(self):
        try:
            urls = parse_douyin_urls(self.download_urls.toPlainText())
            grants = [LicenseGrant(url, self.down_creator.text().strip(), self.down_evidence.text().strip(),
                                  self.check_commercial.isChecked(), self.check_derivative.isChecked(),
                                  expires_on=self.down_expiry.text().strip(),
                                  evidence_file=self.down_evidence_file.text().strip()) for url in urls]
            for grant in grants:
                grant.validate()
            folder = Path(self.down_folder.text())
            limit = self.down_limit.value()
            niche = self.down_niche.currentText()
        except Exception as exc:
            return self.alert(exc)

        def task(report):
            count = 0
            for grant in grants:
                self.store.save_source(grant, niche)
                files = download_authorized(grant.original_url, folder, grant, self.store, limit, report)
                count += len(files)
            return count
        self.job("Tải Douyin", task, lambda n: (self.log(f"Đã tải {n} file"), self.refresh_sources()))

    def build_editor(self, layout):
        panel = group("Chỉnh sửa hàng loạt bằng FFmpeg (offline)")
        self.edit_files = paragraph("Mỗi dòng là đường dẫn video MP4/MOV trong máy", 115)
        files_btn = QPushButton("Chọn nhiều video")
        files_btn.clicked.connect(self.choose_edit_files)
        self.edit_out = field("Thư mục xuất", str(user_data_dir() / "exports"))
        out_btn = QPushButton("Chọn thư mục xuất")
        out_btn.clicked.connect(lambda: self._folder(self.edit_out))
        self.edit_creator = field("Tên tác giả gốc để ghi nguồn")
        self.edit_url = field("URL Douyin gốc (hiện trong metadata)")
        self.edit_evidence = field("Bằng chứng có quyền chỉnh sửa và dùng cho affiliate")
        self.edit_expiry = field("Hết hạn giấy phép YYYY-MM-DD (tùy chọn)")
        self.edit_evidence_file = field("File bằng chứng cấp phép (tùy chọn)")
        self.edit_authorized = QCheckBox("Xác nhận video đã được cấp quyền biên tập và sử dụng thương mại")
        self.edit_fit = QComboBox()
        self.edit_fit.addItems(["crop", "pad", "blur"])
        self.edit_bright = QDoubleSpinBox()
        self.edit_bright.setRange(-.5, .5)
        self.edit_bright.setSingleStep(.05)
        self.edit_contrast = QDoubleSpinBox()
        self.edit_contrast.setRange(.5, 2)
        self.edit_contrast.setSingleStep(.1)
        self.edit_contrast.setValue(1)
        self.edit_saturation = QDoubleSpinBox()
        self.edit_saturation.setRange(0, 2)
        self.edit_saturation.setSingleStep(.1)
        self.edit_saturation.setValue(1)
        self.edit_cta = field("Ví dụ: Link sản phẩm nằm ở trang cá nhân")
        self.cta_name = field("Tên preset CTA", "Gia dụng")
        self.cta_position = QComboBox()
        self.cta_position.addItems(["bottom", "center"])
        self.cta_background = field("Màu nền #RRGGBB", "#101827")
        self.cta_foreground = field("Màu chữ #RRGGBB", "#FFFFFF")
        self.cta_font_size = QSpinBox()
        self.cta_font_size.setRange(18, 90)
        self.cta_font_size.setValue(40)
        save_cta = QPushButton("Lưu preset CTA")
        save_cta.clicked.connect(self.on_save_cta)
        load_cta = QPushButton("Nạp preset CTA")
        load_cta.clicked.connect(self.on_load_cta)
        self.edit_srt = field("Phụ đề .srt tùy chọn (đã dịch sang Việt)")
        srt_btn = QPushButton("Chọn SRT")
        srt_btn.clicked.connect(lambda: self.chooser(self.edit_srt, filter="SRT (*.srt)"))
        self.edit_narration = field("File giọng đọc .wav/.mp3 tùy chọn (thay audio gốc)")
        narration_btn = QPushButton("Chọn audio")
        narration_btn.clicked.connect(lambda: self.chooser(self.edit_narration, filter="Audio (*.wav *.mp3)"))
        for label, value in (("Video", self.edit_files), ("", files_btn), ("Xuất", self.edit_out),
                             ("", out_btn), ("Tác giả", self.edit_creator), ("URL nguồn", self.edit_url),
                             ("Bằng chứng", self.edit_evidence), ("File bằng chứng", self.edit_evidence_file),
                             ("Hết hạn", self.edit_expiry), ("", self.edit_authorized),
                             ("Kiểu khung 9:16", self.edit_fit), ("Độ sáng", self.edit_bright),
                             ("Tương phản", self.edit_contrast), ("Bão hòa", self.edit_saturation),
                             ("CTA", self.edit_cta), ("Preset CTA", self.cta_name),
                             ("Vị trí CTA", self.cta_position), ("Màu nền", self.cta_background),
                             ("Màu chữ", self.cta_foreground), ("Cỡ chữ", self.cta_font_size),
                             ("", save_cta), ("", load_cta), ("Phụ đề", self.edit_srt), ("", srt_btn),
                             ("Thuyết minh", self.edit_narration), ("", narration_btn)):
            panel.layout().addRow(label, value)
        subtitle_check = QPushButton("KIỂM TRA PHỤ ĐỀ · tốc độ đọc / số dòng")
        subtitle_check.clicked.connect(self.on_check_srt)
        preview = QPushButton("XEM TRƯỚC 5 GIÂY CÓ PHỤ ĐỀ")
        preview.clicked.connect(self.on_subtitle_preview)
        panel.layout().addRow(subtitle_check)
        panel.layout().addRow(preview)
        go = QPushButton("RENDER HÀNG LOẠT 1080 × 1920 MP4")
        go.clicked.connect(self.on_render)
        panel.layout().addRow(go)
        layout.addWidget(panel)

    def choose_edit_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn nhiều video", "", "Video (*.mp4 *.mov)")
        if files:
            self.edit_files.setPlainText("\n".join(files))

    def on_render(self):
        try:
            files = [Path(x.strip()) for x in self.edit_files.toPlainText().splitlines() if x.strip()]
            if not files or not all(f.is_file() for f in files):
                raise ValueError("Đường dẫn video nguồn phải tồn tại.")
            if not self.edit_authorized.isChecked() or not self.edit_evidence.text().strip():
                raise PermissionError("Chưa xác nhận quyền sử dụng thương mại và bằng chứng cấp phép.")
            LicenseGrant(self.edit_url.text().strip(), self.edit_creator.text().strip(),
                         self.edit_evidence.text().strip(), True, True,
                         expires_on=self.edit_expiry.text().strip(),
                         evidence_file=self.edit_evidence_file.text().strip()).validate()
            preset = EditPreset(fit=self.edit_fit.currentText(), brightness=self.edit_bright.value(),
                                contrast=self.edit_contrast.value(), saturation=self.edit_saturation.value(),
                                creator=self.edit_creator.text().strip(), original_url=self.edit_url.text().strip(),
                                cta=self.edit_cta.text(),
                                cta_position=self.cta_position.currentText(),
                                cta_background=self.cta_background.text(),
                                cta_foreground=self.cta_foreground.text(),
                                cta_font_size=self.cta_font_size.value(),
                                subtitle=Path(self.edit_srt.text()) if self.edit_srt.text() else None,
                                narration=Path(self.edit_narration.text()) if self.edit_narration.text() else None)
            preset.validate()
            if preset.subtitle:
                issues = audit_srt(preset.subtitle)
                if any(issue.severity == "error" for issue in issues):
                    raise ValueError("Phụ đề bị lỗi timecode. Hãy sửa trước khi render.")
                if issues:
                    msg = "Có %d cảnh báo phụ đề, vẫn tiếp tục render?\n%s" % (
                        len(issues), "\n".join(x.detail for x in issues[:5]))
                    answer = QMessageBox.question(self, "Kiểm tra phụ đề", msg,
                                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if answer != QMessageBox.StandardButton.Yes:
                        return
            output = Path(self.edit_out.text())
        except Exception as exc:
            return self.alert(exc)

        def task(report):
            result = []
            for i, path in enumerate(files, 1):
                report(f"[{i}/{len(files)}] {path.name}")
                dest = output / f"{path.stem}_douyinhehe.mp4"
                if dest.resolve() == path.resolve():
                    raise ValueError("Đầu ra không được trùng đầu vào.")
                result.append(render_video(path, dest, preset, report))
            return result
        self.job("Render video", task, lambda result: self.log(f"Đã xuất {len(result)} video vào {output}"))

    def on_save_cta(self):
        try:
            style = CTAStyle(self.cta_position.currentText(), self.cta_background.text(),
                             self.cta_foreground.text(), self.cta_font_size.value())
            path = save_preset(self.cta_name.text().strip(), style)
            self.log(f"Đã lưu CTA preset: {path}")
        except Exception as exc:
            self.alert(exc)

    def on_load_cta(self):
        try:
            style = load_preset(self.cta_name.text().strip())
            self.cta_position.setCurrentText(style.position)
            self.cta_background.setText(style.background)
            self.cta_foreground.setText(style.foreground)
            self.cta_font_size.setValue(style.font_size)
        except Exception as exc:
            self.alert(exc)

    def on_check_srt(self):
        try:
            path = Path(self.edit_srt.text())
            issues = audit_srt(path)
            message = ("Phụ đề đạt kiểm tra độ dài và tốc độ đọc." if not issues else
                       "\n".join(f"Câu {x.item}: {x.detail}" for x in issues[:30]))
            QMessageBox.information(self, "Kiểm tra phụ đề", message)
        except Exception as exc:
            self.alert(exc)

    def on_subtitle_preview(self):
        try:
            video = next(Path(v.strip()) for v in self.edit_files.toPlainText().splitlines() if v.strip())
            subtitle = Path(self.edit_srt.text())
            target = user_data_dir() / "previews" / (video.stem + "-5s.mp4")
        except (ValueError, StopIteration) as exc:
            return self.alert(exc)
        self.job("Xem trước 5 giây", lambda report: preview_five_seconds(video, subtitle, target),
                 lambda file: QDesktopServices.openUrl(QUrl.fromLocalFile(str(file))))

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
        logs_button = QPushButton("XUẤT LOG ĐÃ CHE API KEY")
        logs_button.clicked.connect(self.on_export_logs)
        status.layout().addRow(logs_button)
        status.layout().addRow(QLabel("Thư mục dữ liệu: " + str(user_data_dir())))
        layout.addWidget(status)

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
        panel = group("Batch 2.0 · Danh sách CSV/JSON · Kiểm soát nguồn cho từng video")
        panel.layout().addRow(QLabel(
            "Bắt buộc: file, original_url, creator, evidence, commercial=true, derivative=true.\n"
            "Có thể thêm: niche, platforms, fit, cta, subtitle, brightness, contrast, saturation."
        ))
        self.batch_manifest = field("Đường dẫn CSV/JSON có giấy phép riêng cho mỗi video")
        self.local_folder = field("Thư mục video tự quay / đã có quyền sử dụng")
        self.local_creator = field("Chủ sở hữu video local")
        self.local_evidence = field("Bằng chứng quyền dùng video local")
        self.local_expiry = field("Hết hạn YYYY-MM-DD (tùy chọn)")
        self.local_rights = QCheckBox("Tôi xác nhận quyền thương mại và chỉnh sửa các file video local")
        browse = QPushButton("Chọn manifest CSV/JSON")
        browse.clicked.connect(lambda: self.chooser(
            self.batch_manifest, filter="Manifests (*.csv *.json);;All files (*)"))
        self.batch_out = field("Thư mục xuất video và bản ghi nguồn", str(user_data_dir() / "exports"))
        folder = QPushButton("Chọn thư mục xuất")
        folder.clicked.connect(lambda: self._folder(self.batch_out))
        for key, w in (("Manifest", self.batch_manifest), ("", browse),
                       ("Thư mục local", self.local_folder), ("Tác giả local", self.local_creator),
                       ("Bằng chứng local", self.local_evidence), ("Hết hạn", self.local_expiry),
                       ("", self.local_rights),
                       ("Output", self.batch_out), ("", folder)):
            panel.layout().addRow(key, w)
        make_local = QPushButton("TẠO MANIFEST VIDEO LOCAL")
        make_local.clicked.connect(self.on_local_manifest)
        panel.layout().addRow(make_local)
        enqueue = QPushButton("THÊM VÀO HÀNG ĐỢI (loại trùng)")
        enqueue.clicked.connect(self.on_enqueue_manifest)
        process = QPushButton("CHẠY HÀNG ĐỢI · không ghi đè file hợp lệ khi thất bại")
        process.clicked.connect(self.on_batch_run)
        retry = QPushButton("Thử lại các tác vụ lỗi")
        retry.clicked.connect(self.on_batch_retry)
        recovery = QPushButton("Khôi phục tác vụ bị ngắt sau khi thoát ứng dụng")
        recovery.clicked.connect(self.on_batch_recover)
        refresh = QPushButton("Làm mới danh sách")
        refresh.clicked.connect(self.refresh_batch)
        for btn in (enqueue, process, retry, recovery, refresh):
            panel.layout().addRow(btn)
        self.batch_view = paragraph("Hàng đợi trống", 240)
        self.batch_view.setReadOnly(True)
        panel.layout().addRow(self.batch_view)
        layout.addWidget(panel)
        self.refresh_batch()

    def on_local_manifest(self):
        try:
            target = user_data_dir() / "imports" / "local-videos.json"
            file = create_local_manifest(Path(self.local_folder.text()), target,
                                         creator=self.local_creator.text(),
                                         evidence=self.local_evidence.text(),
                                         rights_confirmed=self.local_rights.isChecked(),
                                         expires_on=self.local_expiry.text().strip())
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
