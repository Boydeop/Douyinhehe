"""Small draggable mask preview for Douyinhehe PySide6."""
from __future__ import annotations
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget
from .studio_engine import MaskRegion, parse_regions

class MaskCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 420)
        self.setMaximumHeight(680)
        self.setToolTip("Kéo chuột trái để vẽ vùng che; chuột phải hoàn tác vùng cuối.")
        self._image = QPixmap()
        self._regions = []
        self._start = self._current = None

    def set_image(self, path):
        image = QPixmap(str(path))
        if image.isNull():
            raise ValueError("Không đọc được ảnh xem trước.")
        self._image = image
        self.update()

    def set_regions(self, regions):
        self._regions = list(parse_regions(regions))
        self.update()

    def regions(self):
        return tuple(self._regions)

    def clear_regions(self):
        self._regions.clear()
        self.update()

    def _area(self):
        ratio = 9/16 if self._image.isNull() else self._image.width()/max(self._image.height(),1)
        width = min(self.width()-14., (self.height()-14.)*ratio)
        height = width/ratio
        return QRectF((self.width()-width)/2, (self.height()-height)/2, width, height)

    def _point(self, point):
        area=self._area()
        return QPointF(max(0.,min(1.,(point.x()-area.x())/area.width())),
                       max(0.,min(1.,(point.y()-area.y())/area.height())))

    def _region(self,a,b):
        return MaskRegion(min(a.x(),b.x()), min(a.y(),b.y()),abs(a.x()-b.x()),abs(a.y()-b.y()))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.RightButton:
            if self._regions:
                self._regions.pop()
                self.update()
        elif event.button()==Qt.MouseButton.LeftButton and self._area().contains(event.position()):
            self._start=self._current=self._point(event.position())

    def mouseMoveEvent(self,event):
        if self._start is not None:
            self._current=self._point(event.position())
            self.update()

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._start is not None:
            box=self._region(self._start,self._point(event.position()))
            if box.width>.01 and box.height>.005 and len(self._regions)<12:
                self._regions.append(box)
            self._start=self._current=None
            self.update()

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor("#0c0c0c"))
        area=self._area()
        if self._image.isNull():
            p.setPen(QColor("#bbb"))
            p.drawText(area,Qt.AlignmentFlag.AlignCenter,"Xem trước video\nKéo chuột chọn vùng che")
        else:
            p.drawPixmap(area.toRect(),self._image)
        p.setPen(QPen(QColor("#ff3333"),2))
        regions=self._regions+([self._region(self._start,self._current)] if self._start and self._current else [])
        for r in regions:
            box=QRectF(area.x()+r.x*area.width(),area.y()+r.y*area.height(),r.width*area.width(),r.height*area.height())
            p.fillRect(box,QColor(255,60,60,70))
            p.drawRect(box)
        p.end()
