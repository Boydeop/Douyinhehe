"""PySide6 Vietnamese desktop interface. All blocking work runs off the UI thread."""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QDateTime, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateTimeEdit, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from .affiliate import Metrics
from .core import KEYWORDS, LicenseGrant, Store, opportunity_score, user_data_dir
from .credentials import get_secret, save_secret
from .downloader import download_authorized, parse_douyin_urls
from .media import EditPreset, find_binary, render_video
from .publisher import PostizClient
from .subtitles import transcribe_to_srt, translate_srt, text_to_voice


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
        self.setWindowTitle("Douyinhehe Pro 0.1 · Affiliate Video Studio")
        self.setMinimumSize(1050, 760)
        self.store = Store()
        self.pool = QThreadPool.globalInstance()
        self._workers = set()
        root = QWidget()
        outer = QVBoxLayout(root)
        heading = QLabel("DOUYINHEHE  /  AFFILIATE STUDIO")
        heading.setObjectName("heading")
        outer.addWidget(heading)
        intro = QLabel("Tìm nguồn · Tải video được cấp phép · Việt hóa · Dựng video · Affiliate · Lên lịch")
        intro.setObjectName("subheading")
        outer.addWidget(intro)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumHeight(115)
        self.logs.setPlaceholderText("Nhật ký tác vụ (không ghi API key)")
        outer.addWidget(self.logs)
        self.setCentralWidget(root)
        for title, builder in [
            ("01  Khám phá", self.build_research),
            ("02  Tải Douyin", self.build_download),
            ("03  Batch Editor", self.build_editor),
            ("04  Dịch & giọng", self.build_translation),
            ("05  Affiliate", self.build_affiliate),
            ("06  Lên lịch", self.build_publish),
            ("07  Cài đặt", self.build_settings),
        ]:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            builder(layout)
            layout.addStretch()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            self.tabs.addTab(scroll, title)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #101827; color: #edf4ff; font-family: 'Segoe UI'; font-size: 12px; }
            QLabel#heading { font-weight: 800; font-size: 23px; color: #f7ffff; margin-top: 8px; }
            QLabel#subheading { color: #90a9bc; margin-bottom: 6px; }
            QTabBar::tab { color: #b3c9de; padding: 11px 13px; background: #192538; margin: 2px; border-radius: 6px; }
            QTabBar::tab:selected { background: #1d6075; color: white; }
            QGroupBox { border: 1px solid #334960; border-radius: 12px; margin-top: 17px; padding: 12px; font-weight: 700; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #73d3dc; }
            QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateTimeEdit {
                background: #18283c; border: 1px solid #3b5872; color: white; border-radius: 7px; padding: 8px;
            }
            QPushButton { background: #137b90; color: white; border-radius: 8px; padding: 10px; font-weight: 700; }
            QPushButton:hover { background: #1a96aa; }
            QPushButton:disabled { background: #3b5261; }
            QCheckBox { padding: 7px; }
            QScrollArea { border: none; }
        """)
        self.log("Khởi động thành công. Chưa có API hay quyền đăng nào được kích hoạt mặc định.")

    def log(self, msg):
        self.logs.appendPlainText(str(msg)[:1500])

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
            QMessageBox.warning(self, title, err[:1400])

        work.signals.completed.connect(success)
        work.signals.failed.connect(failure)
        self.log(f"▶ {title}")
        self.pool.start(work)

    def alert(self, error):
        self.log("Lỗi đầu vào: " + str(error))
        QMessageBox.warning(self, "Dữ liệu chưa hợp lệ", str(error))

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
            f"#{v['id']} · {v['creator']} · {v['niche'] or 'Chưa chọn ngách'} · {v['url']}"
            for v in self.store.sources()) or "Chưa lưu nguồn")

    def build_download(self, layout):
        panel = group("Tải Douyin hàng loạt · video có giấy phép")
        self.download_urls = paragraph("Dán link Douyin (mỗi dòng 1 link hoặc nguyên nội dung chia sẻ)", 120)
        panel.layout().addRow("Nguồn video", self.download_urls)
        self.down_creator = field("Tác giả/chủ sở hữu nội dung")
        self.down_evidence = field("Mã hợp đồng, URL hoặc đường dẫn lưu bằng chứng cấp phép")
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
                                  self.check_commercial.isChecked(), self.check_derivative.isChecked()) for url in urls]
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
        self.edit_srt = field("Phụ đề .srt tùy chọn (đã dịch sang Việt)")
        srt_btn = QPushButton("Chọn SRT")
        srt_btn.clicked.connect(lambda: self.chooser(self.edit_srt, filter="SRT (*.srt)"))
        self.edit_narration = field("File giọng đọc .wav/.mp3 tùy chọn (thay audio gốc)")
        narration_btn = QPushButton("Chọn audio")
        narration_btn.clicked.connect(lambda: self.chooser(self.edit_narration, filter="Audio (*.wav *.mp3)"))
        for label, value in (("Video", self.edit_files), ("", files_btn), ("Xuất", self.edit_out),
                             ("", out_btn), ("Tác giả", self.edit_creator), ("URL nguồn", self.edit_url),
                             ("Bằng chứng", self.edit_evidence), ("", self.edit_authorized),
                             ("Kiểu khung 9:16", self.edit_fit), ("Độ sáng", self.edit_bright),
                             ("Tương phản", self.edit_contrast), ("Bão hòa", self.edit_saturation),
                             ("CTA", self.edit_cta), ("Phụ đề", self.edit_srt), ("", srt_btn),
                             ("Thuyết minh", self.edit_narration), ("", narration_btn)):
            panel.layout().addRow(label, value)
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
            preset = EditPreset(fit=self.edit_fit.currentText(), brightness=self.edit_bright.value(),
                                contrast=self.edit_contrast.value(), saturation=self.edit_saturation.value(),
                                creator=self.edit_creator.text().strip(), original_url=self.edit_url.text().strip(),
                                cta=self.edit_cta.text(),
                                subtitle=Path(self.edit_srt.text()) if self.edit_srt.text() else None,
                                narration=Path(self.edit_narration.text()) if self.edit_narration.text() else None)
            preset.validate()
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
        browse_srt = QPushButton("Chọn SRT nguồn")
        browse_srt.clicked.connect(lambda: self.chooser(self.translate_src, filter="SRT (*.srt)"))
        for l, w in (("Nguồn", self.translate_src), ("", browse_srt), ("Đích", self.translate_dest),
                     ("Model", self.translate_model), ("", self.translate_confirm)):
            trans.layout().addRow(l, w)
        btn = QPushButton("DỊCH BẰNG GEMINI (không tự trả phí)")
        btn.clicked.connect(self.on_translate)
        trans.layout().addRow(btn)
        layout.addWidget(trans)
        voice = group("Lồng tiếng offline · Windows SAPI")
        self.voice_text = paragraph("Dán lời thoại tiếng Việt (cần Windows cài giọng tiếng Việt)", 100)
        self.voice_dest = field("Đường dẫn WAV đích", str(user_data_dir() / "voice.wav"))
        voice.layout().addRow("Lời thoại", self.voice_text)
        voice.layout().addRow("Xuất", self.voice_dest)
        voice_btn = QPushButton("TẠO GIỌNG ĐỌC VIỆT (.wav)")
        voice_btn.clicked.connect(self.on_voice)
        voice.layout().addRow(voice_btn)
        layout.addWidget(voice)

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
        except Exception as exc:
            return self.alert(exc)
        self.job("Dịch phụ đề Gemini", lambda report: translate_srt(source, target, self.store,
                     api_key=secret, model_name=model, confirmed_free_tier=confirmed),
                 lambda path: (self.log(f"Đã dịch: {path}"), self.edit_srt.setText(str(path))))

    def on_voice(self):
        text = self.voice_text.toPlainText()
        target = Path(self.voice_dest.text())
        self.job("Giọng đọc Việt", lambda report: text_to_voice(text, target),
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
        self.refresh_products()

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
        status.layout().addRow(QLabel("Thư mục dữ liệu: " + str(user_data_dir())))
        layout.addWidget(status)

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
