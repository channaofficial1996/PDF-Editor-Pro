"""Generate app.ico for PDF Editor Pro."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath, QPen

app = QGuiApplication([])
img = QImage(256, 256, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
# page
path = QPainterPath()
path.addRoundedRect(QRectF(36, 16, 184, 224), 22, 22)
p.fillPath(path, QColor("#ffffff"))
p.setPen(QPen(QColor("#c62828"), 8))
p.drawPath(path)
# red band
band = QPainterPath()
band.addRoundedRect(QRectF(20, 120, 216, 84), 16, 16)
p.fillPath(band, QColor("#d32f2f"))
p.setPen(QColor("white"))
f = QFont("Segoe UI", 52, QFont.Black)
p.setFont(f)
p.drawText(QRectF(20, 120, 216, 84), Qt.AlignCenter, "PDF")
# lines
p.setPen(QPen(QColor("#9e9e9e"), 10, Qt.SolidLine, Qt.RoundCap))
for y in (52, 78, 104):
    p.drawLine(66, y, 190, y)
p.end()
img.save("app.ico")
print("app.ico written")
