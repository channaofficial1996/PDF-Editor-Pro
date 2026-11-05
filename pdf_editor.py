"""PDF Editor Pro - a full-featured desktop PDF editor (PySide6 + PyMuPDF).

Features: view/zoom/thumbnails, edit existing text, add text (Khmer supported),
highlight/underline/strikeout, freehand draw, shapes, arrows, notes, images,
signatures, whiteout, redaction, links, crop, find & replace, page
rotate/delete/insert/duplicate/reorder/extract/split/merge, watermarks,
page numbers / headers / footers, bookmarks, form filling, flatten,
password protection, metadata, optimize, export images/text, images to PDF,
print, undo/redo. Dark/light theme, Khmer/English interface.
"""
import html
import os
import re
import sys
import threading
import traceback

import pymupdf as fitz
from PySide6.QtCore import (QBuffer, QIODevice, QLineF, QObject, QPointF, QRectF, QSettings, QSize, Qt, QTimer,
                            QUrl, Signal)
from PySide6.QtGui import (QAction, QBrush, QColor, QDesktopServices, QFont, QIcon, QImage, QIntValidator, QKeySequence, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox,
                               QGridLayout,
                               QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame,
                               QGraphicsScene, QGraphicsView, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QProgressDialog, QPushButton, QRadioButton, QScrollArea, QSizePolicy,
                               QSpinBox, QSplitter, QStackedWidget, QStyle, QStyledItemDelegate, QTabWidget,
                               QTableWidget, QTableWidgetItem, QToolButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

import i18n
import theme
import updater
from version import COMPANY, COPYRIGHT, RELEASE_DATE, UPDATE_REPO, VERSION
from i18n import tr

APP_NAME = "PDF Editor Pro"
PDF_FILTER = "PDF files (*.pdf)"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp")
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)"
FONT_DIRS = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]
REDACT_IMG_NONE = getattr(fitz, "PDF_REDACT_IMAGE_NONE", 0)
REDACT_ART_NONE = getattr(fitz, "PDF_REDACT_LINE_ART_NONE", 0)

# key -> (label, hint, shortcut)
TOOLS = {
    "hand": ("Pan", "Drag to scroll the page. Ctrl + mouse wheel to zoom.", "H"),
    "select": ("Select", "Click an object to select it, drag to move, Delete to remove, double-click to edit.", "V"),
    "edittext": ("Edit Text", "Click on existing text to change it.", "E"),
    "text": ("Add Text", "Click, or drag a box, to add new text. Khmer is supported.", "T"),
    "copytext": ("Copy Text", "Drag over text to copy it to the clipboard.", "C"),
    "highlight": ("Highlight", "Drag over text to highlight it.", "Y"),
    "underline": ("Underline", "Drag over text to underline it.", "U"),
    "strikeout": ("Strikeout", "Drag over text to strike it out.", "K"),
    "pen": ("Draw", "Draw freely on the page.", "D"),
    "rect": ("Rectangle", "Drag to draw a rectangle.", "R"),
    "ellipse": ("Ellipse", "Drag to draw an ellipse.", "O"),
    "line": ("Line", "Drag to draw a line.", "L"),
    "arrow": ("Arrow", "Drag to draw an arrow.", "A"),
    "note": ("Note", "Click to add a sticky note.", "N"),
    "image": ("Image", "Click, or drag a box, to place the image.", "I"),
    "signature": ("Sign", "Click, or drag a box, to place your signature.", "S"),
    "link": ("Link", "Drag a box to link to a website or a page.", ""),
    "whiteout": ("Whiteout", "Drag to cover content with white.", "W"),
    "redact": ("Redact", "Drag to permanently remove content (black box).", ""),
    "crop": ("Crop", "Drag a box to crop the current page.", ""),
}
TOOL_GROUPS = [("NAVIGATE", ["hand", "select"]), ("TEXT", ["edittext", "text", "copytext"]),
               ("MARKUP", ["highlight", "underline", "strikeout"]),
               ("DRAW", ["pen", "rect", "ellipse", "line", "arrow"]),
               ("INSERT", ["note", "image", "signature", "link"]), ("PAGE EDIT", ["whiteout", "redact", "crop"])]
RECT_TOOLS = {"text", "copytext", "highlight", "underline", "strikeout", "rect", "image", "signature",
              "whiteout", "redact", "link", "crop"}
# which property controls each tool shows
TOOL_PROPS = {
    "text": {"color", "opacity", "font", "size"},
    "highlight": {"color", "opacity"}, "underline": {"color", "opacity"}, "strikeout": {"color", "opacity"},
    "pen": {"color", "width", "opacity"}, "line": {"color", "width", "opacity"},
    "arrow": {"color", "width", "opacity"},
    "rect": {"color", "fill", "width", "opacity"}, "ellipse": {"color", "fill", "width", "opacity"},
    "note": {"color"},
}
TOOL_COLORS = {"highlight": "#ffd400", "underline": "#2f6bff", "strikeout": "#e5484d", "text": "#111111",
               "note": "#ffc53d"}
DEFAULT_COLOR = "#e5484d"


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def has_khmer(s):
    return any("\u1780" <= ch <= "\u17ff" or "\u19e0" <= ch <= "\u19ff" for ch in s)


def to_rgb(c):
    return (c.redF(), c.greenF(), c.blueF())


def from_rgb(seq, default="black"):
    if not seq:
        return QColor(default)
    return QColor.fromRgbF(*[float(x) for x in seq[:3]])


def from_int(v):
    return QColor((v >> 16) & 255, (v >> 8) & 255, v & 255)


def pix_to_qimage(pix):
    fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
    return QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()


def unrotated_rect(page):
    """Page rectangle in unrotated page coordinates (the space used for inserting content)."""
    return (page.rect * page.derotation_matrix).normalize()


def parse_ranges(text, n):
    pages = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a) if a else 1
            b = int(b) if b else n
            step = 1 if b >= a else -1
            pages += list(range(a, b + step, step))
        else:
            pages.append(int(part))
    out = [p - 1 for p in pages if 1 <= p <= n]
    if not out:
        raise ValueError("No valid pages in: " + text)
    return out


def find_fonts():
    candidates = [("Arial", "arial.ttf", "arialbd.ttf"), ("Times New Roman", "times.ttf", "timesbd.ttf"),
                  ("Courier New", "cour.ttf", "courbd.ttf"), ("Calibri", "calibri.ttf", "calibrib.ttf"),
                  ("Segoe UI", "segoeui.ttf", "segoeuib.ttf"), ("Tahoma", "tahoma.ttf", "tahomabd.ttf"),
                  ("Verdana", "verdana.ttf", "verdanab.ttf"), ("Georgia", "georgia.ttf", "georgiab.ttf"),
                  ("Khmer UI", "KhmerUI.ttf", "KhmerUIb.ttf"), ("Leelawadee UI", "LeelawUI.ttf", "LeelaUIb.ttf")]
    fonts = {}
    for name, reg, bold in candidates:
        for d in FONT_DIRS:
            p = os.path.join(d, reg)
            if os.path.exists(p):
                b = os.path.join(d, bold)
                fonts[name] = (p, b if os.path.exists(b) else p)
                break
    for d in FONT_DIRS:  # any other installed Khmer fonts (Khmer OS, Battambang, ...)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            lf = f.lower()
            if lf.endswith((".ttf", ".otf")) and ("khmer" in lf or "battambang" in lf or "siemreap" in lf
                                                   or "moul" in lf or "hanuman" in lf or "nokora" in lf):
                if not lf.startswith("khmerui"):
                    p = os.path.join(d, f)
                    fonts.setdefault(os.path.splitext(f)[0], (p, p))
    if not fonts:
        fonts["Helvetica"] = (None, None)
    return fonts


FONTS = {}


def default_family(text=""):
    if has_khmer(text):
        for k in FONTS:
            if "khmer" in k.lower():
                return k
    return "Arial" if "Arial" in FONTS else next(iter(FONTS))


def insert_rich_text(page, rect, text, family, size, color, bold=False, italic=False, align="left",
                     opacity=1.0, rotate=0):
    """Insert text with full shaping (Khmer, etc.) using an HTML box."""
    reg, bd = FONTS.get(family, (None, None))
    body = html.escape(text)
    if bold:
        body = f"<b>{body}</b>"
    if italic:
        body = f"<i>{body}</i>"
    style = (f"font-size:{size}px; color:{color.name()}; text-align:{align}; white-space:pre-wrap; "
             f"line-height:1.15;")
    if reg:
        arch = fitz.Archive()
        for d in {os.path.dirname(reg), os.path.dirname(bd)}:
            arch.add(d)
        css = (f'@font-face {{font-family: UF; src: url("{os.path.basename(reg)}");}}\n'
               f'@font-face {{font-family: UF; src: url("{os.path.basename(bd)}"); font-weight: bold;}}\n'
               f"* {{font-family: UF; {style}}}")
    else:
        arch = None
        css = f"* {{font-family: sans-serif; {style}}}"
    return page.insert_htmlbox(rect, body, css=css, archive=arch, opacity=opacity, rotate=rotate)


ORIGINAL_FONT = "(Original font)"


def span_font_buffer(page, span):
    """Return the embedded font program used by a text span, or None."""
    want = span["font"].split("+")[-1]
    for f in page.get_fonts(full=True):
        if f[3].split("+")[-1] == want:
            try:
                _, ext, _, buf = page.parent.extract_font(f[0])
            except Exception:
                return None
            return buf if buf and ext != "n/a" else None
    return None


def font_covers(buf, text):
    """True if the font has a glyph for every character (including spaces) of text."""
    if not buf:
        return False
    try:
        font = fitz.Font(fontbuffer=buf)
    except Exception:
        return False
    return all(font.has_glyph(ord(c)) for c in set(text) if c != "\n")


def _first_char_origin(page):
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                for ch in s["chars"]:
                    return fitz.Point(ch["origin"])
    return None


def fix_tounicode(page, fontname):
    """Fonts like Arial share one glyph for space/no-break space and hyphen/soft hyphen; MuPDF records the
    latter, so copied or searched text gets odd characters. Map those glyphs back to space and hyphen."""
    doc = page.parent
    for f in page.get_fonts(full=True):
        if f[4] != fontname:
            continue
        kind, val = doc.xref_get_key(f[0], "ToUnicode")
        if kind != "xref":
            continue
        tx = int(val.split()[0])
        data = doc.xref_stream(tx)
        # only touch the Unicode side of "<glyph> <unicode>" pairs
        fixed = re.sub(rb"(?<=> )<00[aA]0>", b"<0020>", re.sub(rb"(?<=> )<00[aA][dD]>", b"<002d>", data))
        if fixed != data:
            doc.update_stream(tx, fixed)


def free_font_name(page, base):
    """A resource name not yet on this page. insert_text/insert_font silently reuse a font already registered
    under the same name, and in a saved file that font is a subset without the new letters (they render as boxes)."""
    used = {f[4] for f in page.get_fonts(full=True)}
    name, n = base, 1
    while name in used:
        n += 1
        name = f"{base}N{n}"
    return name


def place_text(page, origin, text, family, size, color, bold=False, italic=False, fontbuffer=None, max_x=None):
    """Write text so its first character sits exactly on `origin` (the baseline start point)."""
    bounds = unrotated_rect(page)
    if fontbuffer:  # reuse the document's own font: identical glyph widths and spacing
        fname = free_font_name(page, f"OF{abs(hash(fontbuffer)) % 10 ** 8}")
        page.insert_font(fontname=fname, fontbuffer=fontbuffer)  # insert_text has no fontbuffer argument
        page.insert_text(origin, text, fontsize=size, fontname=fname,
                         color=to_rgb(color), lineheight=1.15)
        return
    reg, bd = FONTS.get(family, (None, None))
    complex_script = any(ord(c) >= 0x0590 for c in text)
    if reg and not complex_script and not italic:
        # simple scripts: write directly on the baseline
        name = free_font_name(page, ("B" if bold else "R") + "".join(ch for ch in family if ch.isalnum())[:20])
        page.insert_text(origin, text, fontsize=size, fontname=name, fontfile=bd if bold else reg,
                         color=to_rgb(color), lineheight=1.15)
        fix_tounicode(page, name)
        return
    width = max((max_x or bounds.x1 - 2) - origin.x, size * 3)
    # complex scripts (Khmer...) need HTML shaping: lay the text out on a scratch page to learn where its first baseline lands, then shift it into place
    tmp = fitz.open()
    tp = tmp.new_page(width=width + 400, height=max(2000, size * 80))
    probe = fitz.Rect(100, 100, 100 + width, tp.rect.height - 10)
    insert_rich_text(tp, probe, text, family, size, color, bold, italic)
    fo = _first_char_origin(tp)
    dx, dy = (fo.x - 100, fo.y - 100) if fo else (0, size * 0.9)
    box = fitz.Rect(origin.x - dx, origin.y - dy, origin.x - dx + width, max(bounds.y1, origin.y + size * 40))
    insert_rich_text(page, box, text, family, size, color, bold, italic)


# --------------------------------------------------------------------------------------------
# Small widgets & dialogs
# --------------------------------------------------------------------------------------------
class UpdateSignals(QObject):
    """Carries results from the update worker threads back to the main window."""
    checked = Signal(object, bool)
    check_failed = Signal(str, bool)
    progress = Signal("qint64", "qint64")
    downloaded = Signal(str)
    download_failed = Signal(str)


class ColorButton(QPushButton):
    changed = Signal(QColor)

    def __init__(self, color, tip=""):
        super().__init__()
        self.setFixedSize(26, 26)
        self.setToolTip(tip)
        self.setCursor(Qt.PointingHandCursor)
        self.set_color(QColor(color))
        self.clicked.connect(self.pick)

    def set_color(self, c):
        self.color = QColor(c)
        self.setStyleSheet(f"QPushButton{{background:{self.color.name()}; border:2px solid rgba(128,128,128,0.55);"
                           f"border-radius:13px; padding:0;}} QPushButton:hover{{border-color:#4c7dff;}}")

    def pick(self):
        c = QColorDialog.getColor(self.color, self, tr("Color"))
        if c.isValid():
            self.set_color(c)
            self.changed.emit(c)


def ok_cancel(dlg, layout):
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    if isinstance(layout, QFormLayout):
        layout.addRow(bb)
    else:
        layout.addWidget(bb)


def form_dialog(parent, title):
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(420)
    form = QFormLayout(dlg)
    form.setContentsMargins(20, 18, 20, 16)
    form.setVerticalSpacing(10)
    form.setHorizontalSpacing(14)
    return dlg, form


class TextDialog(QDialog):
    def __init__(self, parent, title, text="", family=None, size=12.0, color=QColor("black"), bold=False,
                 italic=False, extra_fonts=()):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 360)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        self.edit = QPlainTextEdit(text)
        lay.addWidget(self.edit)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.font = QComboBox()
        self.font.addItems(list(extra_fonts) + list(FONTS))
        self.font.setCurrentText(family or default_family(text))
        self.size = QDoubleSpinBox()
        self.size.setRange(3, 400)
        self.size.setValue(size)
        self.color = ColorButton(color, tr("Color"))
        if ORIGINAL_FONT in extra_fonts:
            self.font.setToolTip("Original font = the font embedded in this PDF (best match for spacing)")
        self.bold = QCheckBox(tr("Bold"))
        self.bold.setChecked(bold)
        self.italic = QCheckBox(tr("Italic"))
        self.italic.setChecked(italic)
        self.align = QComboBox()
        self.align.addItems(["left", "center", "right", "justify"])
        for w in (QLabel(tr("Font")), self.font, QLabel(tr("Size")), self.size, self.color, self.bold, self.italic,
                  QLabel(tr("Align")), self.align):
            row.addWidget(w)
        row.addStretch()
        lay.addLayout(row)
        ok_cancel(self, lay)
        self.edit.textChanged.connect(self._auto_font)
        self.font.currentTextChanged.connect(self._preview)
        self._preview()
        self.edit.setFocus()

    def _auto_font(self):
        t = self.edit.toPlainText()
        if has_khmer(t) and "khmer" not in self.font.currentText().lower():
            self.font.setCurrentText(default_family(t))

    def _preview(self):
        f = QFont(self.font.currentText())
        f.setPointSize(14)
        self.edit.setFont(f)

    def values(self):
        return dict(text=self.edit.toPlainText(), family=self.font.currentText(), size=self.size.value(),
                    color=self.color.color, bold=self.bold.isChecked(), italic=self.italic.isChecked(),
                    align=self.align.currentText())


class SignaturePad(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(600, 240)
        self.paths = []
        self.color = QColor("#0b2a8a")
        self.setCursor(Qt.CrossCursor)

    def clear(self):
        self.paths = []
        self.update()

    def mousePressEvent(self, e):
        self.paths.append(QPainterPath(e.position()))
        self.update()

    def mouseMoveEvent(self, e):
        if self.paths:
            self.paths[-1].lineTo(e.position())
            self.update()

    def _draw(self, p, offset=QPointF(0, 0)):
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(self.color, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.translate(-offset)
        for path in self.paths:
            p.drawPath(path)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.white)
        p.drawRoundedRect(QRectF(self.rect()), 12, 12)
        p.setPen(QPen(QColor("#c4c8ce"), 1.2, Qt.DashLine))
        p.drawLine(30, self.height() - 50, self.width() - 30, self.height() - 50)
        p.setPen(QColor("#9aa0a8"))
        p.drawText(30, self.height() - 26, "✕")
        self._draw(p)

    def png_bytes(self):
        if not self.paths:
            return None
        br = QRectF()
        for path in self.paths:
            br = br.united(path.boundingRect())
        br = br.adjusted(-6, -6, 6, 6)
        scale = 3
        img = QImage(int(br.width() * scale), int(br.height() * scale), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.scale(scale, scale)
        self._draw(p, br.topLeft())
        p.end()
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        return bytes(buf.data())


class SignatureDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("Draw your signature"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        self.pad = SignaturePad()
        lay.addWidget(self.pad)
        row = QHBoxLayout()
        col = ColorButton(self.pad.color, tr("Ink"))
        col.changed.connect(lambda c: (setattr(self.pad, "color", c), self.pad.update()))
        clear = QPushButton(tr("Clear"))
        clear.clicked.connect(self.pad.clear)
        load = QPushButton(tr("Load image instead…"))
        load.clicked.connect(self._load)
        row.addWidget(QLabel(tr("Ink")))
        row.addWidget(col)
        row.addSpacing(10)
        row.addWidget(clear)
        row.addWidget(load)
        row.addStretch()
        lay.addLayout(row)
        ok_cancel(self, lay)
        self.data = None

    def _load(self):
        f, _ = QFileDialog.getOpenFileName(self, tr("Choose image"), "", IMAGE_FILTER)
        if f:
            with open(f, "rb") as fh:
                self.data = fh.read()
            self.accept()

    def result_bytes(self):
        return self.data or self.pad.png_bytes()


class AnnotDialog(QDialog):
    def __init__(self, parent, annot):
        super().__init__(parent)
        self.setWindowTitle(annot.type[1])
        form = QFormLayout(self)
        form.setContentsMargins(20, 18, 20, 16)
        form.setVerticalSpacing(10)
        self.content = QPlainTextEdit(annot.info.get("content", ""))
        self.content.setMaximumHeight(110)
        cols = annot.colors
        self.stroke = ColorButton(from_rgb(cols.get("stroke")), tr("Color"))
        self.fill_on = QCheckBox(tr("Fill"))
        self.fill_on.setChecked(bool(cols.get("fill")))
        self.fill = ColorButton(from_rgb(cols.get("fill"), "white"), tr("Fill"))
        self.width = QDoubleSpinBox()
        self.width.setRange(0, 50)
        self.width.setValue(float((annot.border or {}).get("width", 1) or 1))
        self.opacity = QSpinBox()
        self.opacity.setRange(5, 100)
        self.opacity.setSuffix(" %")
        op = annot.opacity
        self.opacity.setValue(int((op if op is not None and op >= 0 else 1) * 100))
        form.addRow(tr("Comment"), self.content)
        form.addRow(tr("Color"), self.stroke)
        fr = QHBoxLayout()
        fr.addWidget(self.fill_on)
        fr.addWidget(self.fill)
        fr.addStretch()
        form.addRow(tr("Fill"), fr)
        form.addRow(tr("Line width"), self.width)
        form.addRow(tr("Opacity"), self.opacity)
        ok_cancel(self, form)


class FormsDialog(QDialog):
    def __init__(self, parent, doc):
        super().__init__(parent)
        self.setWindowTitle(tr("Fill form fields"))
        self.resize(760, 500)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr("Page"), tr("Field"), tr("Type"), tr("Value")])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        lay.addWidget(self.table)
        self.rows = []
        for page in doc:
            for w in page.widgets():
                r = self.table.rowCount()
                self.table.insertRow(r)
                for c, txt in enumerate([str(page.number + 1), w.field_name or "", w.field_type_string]):
                    it = QTableWidgetItem(txt)
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(r, c, it)
                ft = w.field_type
                if ft in (fitz.PDF_WIDGET_TYPE_CHECKBOX, fitz.PDF_WIDGET_TYPE_RADIOBUTTON):
                    ed = QCheckBox()
                    ed.setChecked(w.field_value not in (False, "Off", "", None))
                    self.table.setCellWidget(r, 3, ed)
                elif ft in (fitz.PDF_WIDGET_TYPE_COMBOBOX, fitz.PDF_WIDGET_TYPE_LISTBOX):
                    ed = QComboBox()
                    ed.setEditable(True)
                    for ch in w.choice_values or []:
                        ed.addItem(ch[1] if isinstance(ch, (list, tuple)) else str(ch))
                    ed.setCurrentText(str(w.field_value or ""))
                    self.table.setCellWidget(r, 3, ed)
                elif ft == fitz.PDF_WIDGET_TYPE_TEXT:
                    ed = QTableWidgetItem(str(w.field_value or ""))
                    self.table.setItem(r, 3, ed)
                else:
                    ed = None
                    it = QTableWidgetItem("—")
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(r, 3, it)
                self.rows.append((page.number, w.xref, ft, ed))
        if not self.rows:
            lay.addWidget(QLabel(tr("This document has no form fields.")))
        ok_cancel(self, lay)

    def apply(self, doc):
        for pno, xref, ft, ed in self.rows:
            if ed is None:
                continue
            page = doc[pno]  # keep the page alive while the widget is updated
            w = next((x for x in page.widgets() if x.xref == xref), None)
            if w is None:
                continue
            if isinstance(ed, QCheckBox):
                w.field_value = w.on_state() if ed.isChecked() else "Off"
            elif isinstance(ed, QComboBox):
                w.field_value = ed.currentText()
            else:
                w.field_value = ed.text()
            w.update()


# --------------------------------------------------------------------------------------------
# Page view
# --------------------------------------------------------------------------------------------
class PageView(QGraphicsView):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.sc = QGraphicsScene(self)
        self.setScene(self.sc)
        self.setFrameShape(QFrame.NoFrame)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setAlignment(Qt.AlignCenter)
        self.pix = None
        self.start = None
        self.temp = None
        self.pts = []
        self.overlays = []
        self.moving = None

    def show_pixmap(self, qpix):
        self.sc.clear()
        self.overlays = []
        self.temp = None
        self.moving = None
        dpr = qpix.devicePixelRatio()
        w, h = qpix.width() / dpr, qpix.height() / dpr
        for grow, alpha in ((10, 10), (6, 18), (3, 28), (1, 40)):  # soft shadow
            self.sc.addRect(QRectF(-grow, -grow + 3, w + 2 * grow, h + 2 * grow), QPen(Qt.NoPen),
                            QBrush(QColor(0, 0, 0, alpha)))
        self.pix = self.sc.addPixmap(qpix)
        self.sc.setSceneRect(QRectF(-24, -24, w + 48, h + 48))

    def clear_scene(self):
        self.sc.clear()
        self.pix = None
        self.overlays = []

    def add_overlay(self, rect, color, alpha=60, dashed=False):
        pen = QPen(color, 1.5)
        if dashed:
            pen.setStyle(Qt.DashLine)
        fc = QColor(color)
        fc.setAlpha(alpha)
        it = self.sc.addRect(rect, pen, QBrush(fc))
        it.setZValue(10)
        self.overlays.append(it)
        return it

    def clear_overlays(self):
        for it in self.overlays:
            self.sc.removeItem(it)
        self.overlays = []

    def _pos(self, e):
        return self.mapToScene(e.position().toPoint())

    def mousePressEvent(self, e):
        tool = self.win.tool
        if self.pix is None or e.button() != Qt.LeftButton or tool == "hand":
            return super().mousePressEvent(e)
        p = self._pos(e)
        self.start = p
        self.pts = [p]
        if tool == "select":
            self.moving = self.win.select_annot_at(p)
            return
        color = QColor(self.win.stroke_btn.color)
        accent = QColor(self.win.theme["accent"])
        dash = QPen(accent, 1.4, Qt.DashLine)
        fill = QColor(accent)
        fill.setAlpha(35)
        if tool == "pen":
            self.temp = self.sc.addPath(QPainterPath(p), QPen(color, max(1.0, self.win.width_spin.value() *
                                                                       self.win.zoom), Qt.SolidLine,
                                                               Qt.RoundCap, Qt.RoundJoin))
        elif tool in ("line", "arrow"):
            self.temp = self.sc.addLine(QLineF(p, p), QPen(color, 2))
        elif tool == "ellipse":
            self.temp = self.sc.addEllipse(QRectF(p, p), dash, QBrush(fill))
        elif tool in RECT_TOOLS:
            self.temp = self.sc.addRect(QRectF(p, p), dash, QBrush(fill))
        if self.temp:
            self.temp.setZValue(20)

    def mouseMoveEvent(self, e):
        if self.start is None:
            return super().mouseMoveEvent(e)
        p = self._pos(e)
        tool = self.win.tool
        if tool == "select":
            if self.moving is not None:
                self.moving.setPos(p - self.start)
            return
        if self.temp is None:
            return
        if tool == "pen":
            self.pts.append(p)
            path = self.temp.path()
            path.lineTo(p)
            self.temp.setPath(path)
        elif tool in ("line", "arrow"):
            self.temp.setLine(QLineF(self.start, p))
        else:
            self.temp.setRect(QRectF(self.start, p).normalized())

    def mouseReleaseEvent(self, e):
        if self.start is None:
            return super().mouseReleaseEvent(e)
        p = self._pos(e)
        start, self.start = self.start, None
        if self.temp is not None:
            self.sc.removeItem(self.temp)
            self.temp = None
        tool = self.win.tool
        if tool == "select":
            moving, self.moving = self.moving, None
            if moving is not None and (p - start).manhattanLength() > 3:
                self.win.move_selected(p - start)
            return
        self.win.apply_tool(tool, start, p, list(self.pts))

    def mouseDoubleClickEvent(self, e):
        if self.pix is not None and self.win.tool == "select" and e.button() == Qt.LeftButton:
            self.win.double_click(self._pos(e))
        else:
            super().mouseDoubleClickEvent(e)

    def wheelEvent(self, e):
        if self.win.doc is None:
            return super().wheelEvent(e)
        d = e.angleDelta().y()
        if e.modifiers() & Qt.ControlModifier:
            self.win.zoom_by(1.15 if d > 0 else 1 / 1.15)
            return
        vb = self.verticalScrollBar()
        if d < 0 and vb.value() >= vb.maximum() and self.win.cur < self.win.doc.page_count - 1:
            self.win.goto(self.win.cur + 1)
            return
        if d > 0 and vb.value() <= vb.minimum() and self.win.cur > 0:
            self.win.goto(self.win.cur - 1, bottom=True)
            return
        super().wheelEvent(e)


THUMB_W, THUMB_MAX_H = 118, 168


class ThumbDelegate(QStyledItemDelegate):
    """Draws a page thumbnail as a card with the page number below it."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win

    def sizeHint(self, opt, idx):
        sz = idx.data(Qt.UserRole + 2) or QSize(THUMB_W, 150)
        return QSize(THUMB_W + 40, sz.height() + 46)

    def paint(self, p, opt, idx):
        t = self.win.theme
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = opt.rect
        sel = bool(opt.state & QStyle.State_Selected)
        hover = bool(opt.state & QStyle.State_MouseOver)
        sz = idx.data(Qt.UserRole + 2) or QSize(THUMB_W, 150)
        x = r.x() + (r.width() - sz.width()) / 2
        y = r.y() + 10
        frame = QRectF(x, y, sz.width(), sz.height())
        if sel or hover:
            bg = QColor(t["accent"] if sel else t["hover"])
            if sel:
                bg.setAlpha(45)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(r).adjusted(6, 2, -6, -2), 10, 10)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawRect(frame.translated(0, 2))
        pm = idx.data(Qt.UserRole + 1)
        if pm is not None:
            p.drawPixmap(frame.toRect(), pm)
        else:
            p.fillRect(frame, QColor("white"))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(t["accent"]), 2.5) if sel else QPen(QColor(t["thumb_border"]), 1))
        p.drawRect(frame)
        num = str(idx.row() + 1)
        nr = QRectF(r.x(), frame.bottom() + 7, r.width(), 20)
        f = p.font()
        f.setPointSizeF(9)
        f.setBold(sel)
        p.setFont(f)
        if sel:
            pill = QRectF(nr.center().x() - 16, nr.y(), 32, 20)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t["accent"]))
            p.drawRoundedRect(pill, 10, 10)
            p.setPen(QColor("white"))
        else:
            p.setPen(QColor(t["muted"]))
        p.drawText(nr, Qt.AlignCenter, num)
        p.restore()


class ThumbList(QListWidget):
    reordered = Signal(list)

    def __init__(self, win):
        super().__init__()
        self.setViewMode(QListView.ListMode)
        self.setItemDelegate(ThumbDelegate(win))
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def dropEvent(self, e):
        super().dropEvent(e)
        order = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        if order != sorted(order):
            self.reordered.emit(order)


def vsep():
    s = QFrame()
    s.setObjectName("VSep")
    s.setFixedSize(1, 24)
    return s


# --------------------------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("PDFEditorPro", "PDFEditorPro")
        self.theme_name = self.settings.value("theme", "dark")
        self.theme = theme.THEMES.get(self.theme_name, theme.DARK)
        self.doc = None
        self.path = None
        self.cur = 0
        self.zoom = 1.0
        self.tool = "hand"
        self.modified = False
        self.undo_stack = []
        self.redo_stack = []
        self.password = None
        self.owner_password = None
        self.sel_xref = None
        self.pending_image = None
        self.search_hits = []
        self.search_idx = -1
        self._thumb_gen = 0
        self._thumb_queue = []
        self._icons = []  # (widget/action, icon name, on-color?)
        self.tool_colors = dict(TOOL_COLORS)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource("app.ico")))
        self.resize(1440, 900)
        self.setAcceptDrops(True)

        self._build_actions()
        self._build_menus()
        self._build_body()
        self._build_statusbar()
        self.apply_theme()
        self.set_tool("hand")
        self.update_ui()
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)

    # ---------------------------------------------------------------- icons / theme
    def reg_icon(self, obj, name, on_color=None):
        self._icons.append((obj, name, on_color))
        obj.setIcon(theme.make_icon(name, self.theme, on_color))
        return obj

    def apply_theme(self):
        self.theme = theme.THEMES[self.theme_name]
        app = QApplication.instance()
        app.setPalette(theme.palette(self.theme))
        app.setStyleSheet(theme.stylesheet(self.theme))
        for obj, name, on in self._icons:
            obj.setIcon(theme.make_icon(name, self.theme, on))
        for key, section in self._tool_section.items():
            tint = theme.GROUP_TINTS[section][self.theme_name]
            self.tool_buttons[key].setIcon(theme.make_icon(key, self.theme, "#ffffff", tint))
        for lbl, section in self._section_labels:
            tint = theme.GROUP_TINTS[section][self.theme_name]
            lbl.setText(f'<span style="color:{tint}">●</span>&nbsp; {html.escape(tr(section))}')
        self.view.setBackgroundBrush(QColor(self.theme["canvas"]))
        self.thumbs.viewport().update()
        self.theme_btn.setIcon(theme.make_icon("sun" if self.theme_name == "dark" else "moon", self.theme))
        self.prop_icon.setPixmap(theme.make_icon(self.tool if self.tool in theme.ICONS else "hand",
                                                 self.theme).pixmap(20, 20))

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.settings.setValue("theme", self.theme_name)
        self.apply_theme()
        self.render()

    # ---------------------------------------------------------------- UI construction
    def act(self, text, fn, shortcut=None, icon=None):
        a = QAction(tr(text), self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
            a.setToolTip(f"{tr(text).rstrip('…')}  ({QKeySequence(shortcut).toString(QKeySequence.NativeText)})")
        else:
            a.setToolTip(tr(text).rstrip("…"))
        if icon:
            self.reg_icon(a, icon)
        a.triggered.connect(lambda checked=False: fn())
        return a

    def _build_actions(self):
        self.a_new = self.act("New blank PDF", self.new_doc, "Ctrl+N", "new")
        self.a_open = self.act("Open…", self.open_dialog, "Ctrl+O", "open")
        self.a_save = self.act("Save", self.save, "Ctrl+S", "save")
        self.a_saveas = self.act("Save As…", self.save_as, "Ctrl+Shift+S")
        self.a_print = self.act("Print…", self.print_doc, "Ctrl+P", "print")
        self.a_undo = self.act("Undo", self.undo, "Ctrl+Z", "undo")
        self.a_redo = self.act("Redo", self.redo, "Ctrl+Y", "redo")
        self.a_find = self.act("Find…", self.show_find, "Ctrl+F", "search")
        self.a_del = self.act("Delete selected annotation", self.delete_selected, "Del", "trash")
        self.a_prev = self.act("Previous page", lambda: self.goto(self.cur - 1), "PgUp", "left")
        self.a_next = self.act("Next page", lambda: self.goto(self.cur + 1), "PgDown", "right")
        self.a_zin = self.act("Zoom in", lambda: self.zoom_by(1.2), "Ctrl+=", "zoomin")
        self.a_zout = self.act("Zoom out", lambda: self.zoom_by(1 / 1.2), "Ctrl+-", "zoomout")
        self.a_fitw = self.act("Fit width", self.fit_width, "Ctrl+1", "fitw")
        self.a_fitp = self.act("Fit page", self.fit_page, "Ctrl+2", "fitp")
        self.a_rotl = self.act("Rotate page left", lambda: self.rotate_pages(-90), "Ctrl+L", "rotl")
        self.a_rotr = self.act("Rotate page right", lambda: self.rotate_pages(90), "Ctrl+R", "rotr")
        self.doc_actions = [self.a_save, self.a_saveas, self.a_print, self.a_find, self.a_del, self.a_prev,
                            self.a_next, self.a_zin, self.a_zout, self.a_fitw, self.a_fitp, self.a_rotl,
                            self.a_rotr]
        for a in self.doc_actions + [self.a_undo, self.a_redo]:
            self.addAction(a)

    def _build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu(tr("&File"))
        m.addActions([self.a_new, self.a_open])
        m.addSeparator()
        m.addActions([self.a_save, self.a_saveas])
        self._add(m, [self.act("Save optimized (compress)…", self.save_optimized), None,
                      self.act("Merge / append PDFs or images…", self.merge_files, icon="merge"),
                      self.act("Export pages as images…", self.export_images, icon="export"),
                      self.act("Export text…", self.export_text)])
        m.addAction(self.act("Images to PDF…", self.images_to_pdf, icon="images"))
        m.addSeparator()
        self._add(m, [self.act("Document properties…", self.edit_metadata, icon="info"),
                      self.act("Set password…", self.set_password, icon="lock"),
                      self.act("Remove password", self.remove_password), None])
        m.addAction(self.a_print)
        m.addSeparator()
        m.addAction(self.act("Exit", self.close, "Ctrl+Q"))

        m = mb.addMenu(tr("&Edit"))
        m.addActions([self.a_undo, self.a_redo])
        m.addSeparator()
        m.addAction(self.a_find)
        self._add(m, [self.act("Find && replace text…", self.find_replace, "Ctrl+H"), None])
        m.addAction(self.a_del)
        self._add(m, [self.act("Delete all annotations on page", self.delete_page_annots)])

        m = mb.addMenu(tr("&View"))
        m.addActions([self.a_zin, self.a_zout, self.a_fitw, self.a_fitp])
        m.addSeparator()
        m.addActions([self.a_prev, self.a_next])
        self._add(m, [self.act("Go to page…", self.goto_dialog, "Ctrl+G"),
                      self.act("First page", lambda: self.goto(0), "Home"),
                      self.act("Last page", lambda: self.goto(self.doc.page_count - 1), "End")])
        m.addSeparator()
        self.a_sidebar = self.act("Show sidebar", self.toggle_sidebar, "F4", "sidebar")
        m.addAction(self.a_sidebar)
        m.addAction(self.act("Toggle dark / light theme", self.toggle_theme, "Ctrl+Shift+T", "moon"))

        m = mb.addMenu(tr("&Page"))
        m.addActions([self.a_rotl, self.a_rotr])
        self._add(m, [
            self.act("Rotate all pages right", lambda: self.rotate_pages(90, all_pages=True)), None,
            self.act("Insert blank page after", self.insert_blank, "Ctrl+Shift+N", "plus"),
            self.act("Insert pages from file…", self.insert_from_file),
            self.act("Duplicate page", self.duplicate_page, "Ctrl+D", "copytext"),
            self.act("Delete page(s)", self.delete_pages, "Ctrl+Del", "trash"), None,
            self.act("Move page up", lambda: self.move_page(-1), "Ctrl+Up", "up"),
            self.act("Move page down", lambda: self.move_page(1), "Ctrl+Down", "down"),
            self.act("Reverse page order", self.reverse_pages), None,
            self.act("Extract pages to new PDF…", self.extract_pages, icon="export"),
            self.act("Split PDF…", self.split_pdf, icon="split"), None,
            self.act("Reset crop", self.reset_crop),
        ])

        m = mb.addMenu(tr("&Tools"))
        self._add(m, [
            self.act("Add watermark…", self.add_watermark, icon="stamp"),
            self.act("Page numbers / header / footer…", self.add_page_numbers, icon="hash"), None,
            self.act("Fill form fields…", self.fill_forms, icon="form"),
            self.act("Flatten annotations && forms", self.flatten), None,
            self.act("Add bookmark for this page", self.bookmark_add, "Ctrl+B", "bookmark"),
        ])

        m = mb.addMenu(tr("&Help"))
        m.addAction(self.act("Check for updates…", self.check_updates, icon="update"))
        auto = QAction(tr("Check for updates automatically"), self, checkable=True)
        auto.setChecked(self.settings.value("auto_update_check", True, type=bool))
        auto.toggled.connect(lambda on: self.settings.setValue("auto_update_check", on))
        m.addAction(auto)
        m.addSeparator()
        m.addAction(self.act("About", self.about, icon="info"))

    def _add(self, menu, items):
        for a in items:
            if a is None:
                menu.addSeparator()
            else:
                menu.addAction(a)
                self.doc_actions.append(a)

    def tbtn(self, action, text=False):
        b = QToolButton()
        b.setDefaultAction(action)
        b.setIconSize(QSize(19, 19))
        b.setCursor(Qt.PointingHandCursor)
        if text:
            b.setObjectName("TextBtn")
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setText(action.text().rstrip("…").replace("&", ""))
        return b

    def _build_header(self):
        head = QFrame()
        head.setObjectName("Header")
        h = QHBoxLayout(head)
        h.setContentsMargins(10, 6, 10, 6)
        h.setSpacing(4)
        h.addWidget(self.tbtn(self.a_open, text=True))
        h.addWidget(self.tbtn(self.a_save, text=True))
        h.addWidget(self.tbtn(self.a_print))
        h.addWidget(vsep())
        h.addWidget(self.tbtn(self.a_undo))
        h.addWidget(self.tbtn(self.a_redo))
        h.addStretch(1)

        # page navigation pill
        pill = QFrame()
        pill.setObjectName("Pill")
        pl = QHBoxLayout(pill)
        pl.setContentsMargins(4, 2, 4, 2)
        pl.setSpacing(0)
        pl.addWidget(self.tbtn(self.a_prev))
        self.page_edit = QLineEdit("1")
        self.page_edit.setFixedWidth(42)
        self.page_edit.setAlignment(Qt.AlignCenter)
        self.page_edit.setValidator(QIntValidator(1, 999999))
        self.page_edit.editingFinished.connect(self._page_from_edit)
        pl.addWidget(self.page_edit)
        self.page_lbl = QLabel("/ 0")
        self.page_lbl.setObjectName("Muted")
        self.page_lbl.setMinimumWidth(40)
        pl.addWidget(self.page_lbl)
        pl.addWidget(self.tbtn(self.a_next))
        h.addWidget(pill)
        h.addSpacing(8)

        # zoom pill
        zp = QFrame()
        zp.setObjectName("Pill")
        zl = QHBoxLayout(zp)
        zl.setContentsMargins(4, 2, 4, 2)
        zl.setSpacing(0)
        zl.addWidget(self.tbtn(self.a_zout))
        self.zoom_box = QComboBox()
        self.zoom_box.setEditable(True)
        self.zoom_box.addItems(["50%", "75%", "100%", "125%", "150%", "200%", "300%", "400%"])
        self.zoom_box.setFixedWidth(84)
        self.zoom_box.lineEdit().setAlignment(Qt.AlignCenter)
        self.zoom_box.lineEdit().returnPressed.connect(self._zoom_from_box)
        self.zoom_box.activated.connect(lambda _: self._zoom_from_box())
        zl.addWidget(self.zoom_box)
        zl.addWidget(self.tbtn(self.a_zin))
        h.addWidget(zp)
        h.addWidget(self.tbtn(self.a_fitw))
        h.addWidget(self.tbtn(self.a_fitp))
        h.addWidget(vsep())
        h.addWidget(self.tbtn(self.a_rotl))
        h.addWidget(self.tbtn(self.a_rotr))
        h.addStretch(1)

        # search
        sp = QFrame()
        sp.setObjectName("Pill")
        sl = QHBoxLayout(sp)
        sl.setContentsMargins(8, 2, 4, 2)
        sl.setSpacing(2)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText(tr("Search in document…"))
        self.find_edit.setFixedWidth(220)
        self.find_edit.setClearButtonEnabled(True)
        self.reg_icon(self.find_edit.addAction(QIcon(), QLineEdit.LeadingPosition), "search")
        self.find_edit.returnPressed.connect(self.find_next)
        self.find_edit.textChanged.connect(lambda _: self._clear_search())
        sl.addWidget(self.find_edit)
        self.find_lbl = QLabel("")
        self.find_lbl.setObjectName("Muted")
        sl.addWidget(self.find_lbl)
        for icon, tip, fn in (("up", "Previous match", lambda: self.find_next(-1)),
                              ("down", "Next match", self.find_next)):
            b = QToolButton()
            b.setToolTip(tr(tip))
            b.clicked.connect(fn)
            self.reg_icon(b, icon)
            sl.addWidget(b)
        h.addWidget(sp)
        h.addWidget(vsep())
        sb = QToolButton()
        sb.setDefaultAction(self.a_sidebar)
        h.addWidget(sb)
        self.theme_btn = QToolButton()
        self.theme_btn.setToolTip(tr("Toggle dark / light theme"))
        self.theme_btn.clicked.connect(self.toggle_theme)
        h.addWidget(self.theme_btn)
        return head

    def _build_tool_panel(self):
        panel = QFrame()
        panel.setObjectName("ToolPanel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 4, 12, 8)
        v.setSpacing(2)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons = {}
        self._tool_section = {}
        self._section_labels = []
        for section, keys in TOOL_GROUPS:
            lbl = QLabel()
            lbl.setObjectName("Section")
            v.addWidget(lbl)
            self._section_labels.append((lbl, section))
            grid = QGridLayout()
            grid.setSpacing(4)
            for col in range(3):
                grid.setColumnStretch(col, 1)
            v.addLayout(grid)
            for i, key in enumerate(keys):
                label, hint, sc = TOOLS[key]
                b = QToolButton()
                b.setObjectName("ToolBtn")
                b.setCheckable(True)
                b.setText(tr(label))
                b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                b.setIconSize(QSize(20, 20))
                b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                b.setMinimumWidth(58)
                b.setFixedHeight(52)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(f"<b>{tr(label)}</b>{f'  ({sc})' if sc else ''}<br>{tr(hint)}")
                self._tool_section[key] = section
                b.clicked.connect(lambda checked=False, k=key: self.set_tool(k))
                self.tool_group.addButton(b)
                self.tool_buttons[key] = b
                grid.addWidget(b, i // 3, i % 3)
                if sc:
                    a = QAction(self)
                    a.setShortcut(QKeySequence(sc))
                    a.triggered.connect(lambda checked=False, k=key: self.doc is not None and self.set_tool(k))
                    self.addAction(a)
        v.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("ToolScroll")
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        credit_box = QFrame()
        credit_box.setObjectName("CreditBox")
        cb = QVBoxLayout(credit_box)
        cb.setContentsMargins(8, 8, 8, 8)
        cb.addWidget(self._credit_label(f"© 2026 <b>{COMPANY}</b><br>Licensed under AGPL-3.0"))
        dock = QFrame()
        dock.setObjectName("ToolDock")
        dock.setFixedWidth(226)
        dl = QVBoxLayout(dock)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(0)
        dl.addWidget(scroll, 1)
        dl.addWidget(credit_box)
        return dock

    def _credit_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("Credit")
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    def _build_prop_bar(self):
        bar = QFrame()
        bar.setObjectName("PropBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(14, 6, 14, 6)
        h.setSpacing(8)
        self.prop_icon = QLabel()
        self.prop_title = QLabel()
        self.prop_title.setObjectName("PropTitle")
        self.prop_hint = QLabel()
        self.prop_hint.setObjectName("Hint")
        h.addWidget(self.prop_icon)
        h.addWidget(self.prop_title)
        h.addSpacing(6)
        h.addWidget(self.prop_hint, 1)
        self.prop_groups = {}

        def group(key, label, *widgets):
            w = QWidget()
            gl = QHBoxLayout(w)
            gl.setContentsMargins(8, 0, 0, 0)
            gl.setSpacing(6)
            if label:
                lb = QLabel(tr(label))
                lb.setObjectName("Muted")
                gl.addWidget(lb)
            for x in widgets:
                gl.addWidget(x)
            self.prop_groups[key] = w
            h.addWidget(w)

        self.stroke_btn = ColorButton(DEFAULT_COLOR, tr("Color"))
        self.stroke_btn.changed.connect(lambda c: self.tool_colors.__setitem__(self.tool, c.name()))
        group("color", "Color", self.stroke_btn)
        self.fill_chk = QCheckBox(tr("Fill"))
        self.fill_btn = ColorButton("#ffe680", tr("Fill"))
        self.fill_btn.changed.connect(lambda _: self.fill_chk.setChecked(True))
        group("fill", None, self.fill_chk, self.fill_btn)
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 30)
        self.width_spin.setValue(2)
        self.width_spin.setFixedWidth(74)
        group("width", "Width", self.width_spin)
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(5, 100)
        self.opacity_spin.setValue(100)
        self.opacity_spin.setSuffix(" %")
        self.opacity_spin.setFixedWidth(80)
        group("opacity", "Opacity", self.opacity_spin)
        self.font_box = QComboBox()
        self.font_box.addItems(list(FONTS))
        self.font_box.setCurrentText(default_family())
        self.font_box.setMinimumWidth(150)
        group("font", "Font", self.font_box)
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(3, 400)
        self.size_spin.setValue(12)
        self.size_spin.setFixedWidth(74)
        group("size", "Size", self.size_spin)
        return bar

    def _build_welcome(self):
        page = QWidget()
        page.setObjectName("Welcome")
        page.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(page)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(560)
        v = QVBoxLayout(card)
        v.setContentsMargins(40, 36, 40, 32)
        v.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(QIcon(resource("app.ico")).pixmap(72, 72))
        logo.setAlignment(Qt.AlignCenter)
        v.addWidget(logo)
        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)
        ver = QLabel(f"Version {VERSION}")
        ver.setObjectName("Muted")
        ver.setAlignment(Qt.AlignCenter)
        v.addWidget(ver)
        sub = QLabel(tr("Edit, sign and organise your PDF files"))
        sub.setObjectName("Subtitle")
        sub.setAlignment(Qt.AlignCenter)
        v.addWidget(sub)
        v.addSpacing(10)
        b1 = QPushButton(tr("Open PDF"))
        b1.setObjectName("Primary")
        b1.setCursor(Qt.PointingHandCursor)
        self.reg_icon(b1, "open", on_color=None)
        b1.clicked.connect(self.open_dialog)
        v.addWidget(b1)
        r2 = QHBoxLayout()
        for text, icon, fn in (("New blank PDF", "new", self.new_doc), ("Images → PDF", "images",
                                                                         lambda: self.images_to_pdf())):
            b = QPushButton(tr(text))
            b.setObjectName("Big")
            b.setCursor(Qt.PointingHandCursor)
            self.reg_icon(b, icon)
            b.clicked.connect(fn)
            r2.addWidget(b)
        v.addLayout(r2)
        drop = QLabel(tr("or drag & drop a PDF file anywhere in this window"))
        drop.setObjectName("DropZone")
        drop.setAlignment(Qt.AlignCenter)
        v.addWidget(drop)
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(0)
        v.addLayout(self.recent_box)
        v.addWidget(self._credit_label(COPYRIGHT))
        row.addWidget(card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        b1.setIcon(theme.make_icon("open", dict(self.theme, text="#ffffff")))
        self._icons = [(o, n, c) for o, n, c in self._icons if o is not b1]
        return page

    def refresh_recent(self):
        while self.recent_box.count():
            it = self.recent_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        files = [f for f in (self.settings.value("recent", []) or []) if os.path.exists(f)][:6]
        if not files:
            return
        lbl = QLabel(tr("RECENT FILES"))
        lbl.setObjectName("Section")
        self.recent_box.addWidget(lbl)
        for f in files:
            b = QPushButton(f"{os.path.basename(f)}    —    {os.path.dirname(f)}")
            b.setObjectName("Recent")
            b.setIcon(theme.make_icon("new", self.theme))
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(f)
            b.clicked.connect(lambda checked=False, p=f: self.open_path(p))
            self.recent_box.addWidget(b)

    def add_recent(self, path):
        files = [f for f in (self.settings.value("recent", []) or []) if f != path]
        self.settings.setValue("recent", [path] + files[:9])

    def _build_body(self):
        self.view = PageView(self)
        self.thumbs = ThumbList(self)
        self.thumbs.currentRowChanged.connect(lambda r: r >= 0 and r != self.cur and self.goto(r))
        self.thumbs.reordered.connect(self.reorder_pages)
        self.thumbs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.thumbs.customContextMenuRequested.connect(self.thumb_menu)

        self.toc_tree = QTreeWidget()
        self.toc_tree.setHeaderHidden(True)
        self.toc_tree.setColumnCount(2)
        self.toc_tree.setFrameShape(QFrame.NoFrame)
        self.toc_tree.itemClicked.connect(self._toc_clicked)
        toc_box = QWidget()
        tl = QVBoxLayout(toc_box)
        tl.setContentsMargins(6, 6, 6, 6)
        tl.addWidget(self.toc_tree)
        tb = QHBoxLayout()
        for label, fn in (("Add", self.bookmark_add), ("Rename", self.bookmark_rename),
                          ("Delete", self.bookmark_delete)):
            b = QPushButton(tr(label))
            b.clicked.connect(fn)
            tb.addWidget(b)
        tl.addLayout(tb)

        self.side = QTabWidget()
        self.side.setObjectName("SidePanel")
        self.side.setAttribute(Qt.WA_StyledBackground, True)
        self.side.addTab(self.thumbs, tr("Pages"))
        self.side.addTab(toc_box, tr("Bookmarks"))
        self.side.setMinimumWidth(170)

        viewer = QWidget()
        vl = QVBoxLayout(viewer)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.addWidget(self._build_prop_bar())
        vl.addWidget(self.view, 1)

        self.split = QSplitter()
        self.split.setHandleWidth(1)
        self.split.addWidget(self.side)
        self.split.addWidget(viewer)
        self.split.setStretchFactor(1, 1)
        self.split.setCollapsible(1, False)
        self.split.setSizes([200, 1100])

        self.tool_panel = self._build_tool_panel()
        work = QWidget()
        wl = QHBoxLayout(work)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addWidget(self.tool_panel)
        wl.addWidget(self.split, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_welcome())
        self.stack.addWidget(work)

        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self._build_header())
        cl.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def _build_statusbar(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.st_saved = QLabel()
        self.st_page = QLabel()
        self.st_zoom = QLabel()
        st_ver = QLabel(f"v{VERSION}  ·  © 2026 {COMPANY}")
        st_ver.setToolTip(f"{APP_NAME} version {VERSION} ({RELEASE_DATE})")
        self.st_update = QToolButton()
        self.st_update.setText(tr("Update"))
        self.st_update.setToolTip(tr("Check for updates"))
        self.st_update.setCursor(Qt.PointingHandCursor)
        self.st_update.clicked.connect(lambda: self.check_updates())
        for w in (self.st_saved, self.st_page, self.st_zoom, self.st_update, st_ver):
            sb.addPermanentWidget(w)
        self.update_info = None
        self.update_busy = False
        self.update_sig = UpdateSignals(self)
        self.update_sig.checked.connect(self._update_checked)
        self.update_sig.check_failed.connect(self._update_check_failed)
        self.update_sig.progress.connect(self._update_progress)
        self.update_sig.downloaded.connect(self._update_downloaded)
        self.update_sig.download_failed.connect(self._update_download_failed)
        if self.settings.value("auto_update_check", True, type=bool):
            QTimer.singleShot(3000, lambda: self.check_updates(silent=True))

    # ---------------------------------------------------------------- state helpers
    def page(self):
        # keep one Page object alive so annotations obtained from it stay bound
        key = (id(self.doc), self.cur)
        if getattr(self, "_page_key", None) != key:
            self._page_key, self._page = key, self.doc[self.cur]
        return self._page

    def invalidate_page(self):
        self._page_key = self._page = None

    def update_ui(self):
        has = self.doc is not None
        for a in self.doc_actions:
            a.setEnabled(has)
        for b in self.tool_buttons.values():
            b.setEnabled(has)
        self.find_edit.setEnabled(has)
        self.a_undo.setEnabled(bool(self.undo_stack))
        self.a_redo.setEnabled(bool(self.redo_stack))
        self.stack.setCurrentIndex(1 if has else 0)
        if not has:
            self.refresh_recent()
        n = self.doc.page_count if has else 0
        if not self.page_edit.hasFocus():
            self.page_edit.setText(str(self.cur + 1 if has else 0))
        self.page_lbl.setText(f"/ {n}")
        if not self.zoom_box.lineEdit().hasFocus():
            self.zoom_box.setEditText(f"{round(self.zoom * 100)}%")
        name = os.path.basename(self.path) if self.path else ("Untitled.pdf" if has else "")
        self.setWindowTitle((f"{'● ' if self.modified else ''}{name} — " if has else "") + f"{APP_NAME} {VERSION}")
        self.st_page.setText(f"{tr('Page')} {self.cur + 1} / {n}" if has else "")
        self.st_zoom.setText(f"{round(self.zoom * 100)}%" if has else "")
        self.st_saved.setText(("● " + tr("Unsaved changes")) if (has and self.modified) else
                              ("✓ " + tr("All changes saved")) if has else "")

    def set_tool(self, key):
        if key in ("image", "signature") and self.doc is not None:
            data = self._ask_image(key)
            if not data:
                key = "hand"
            else:
                self.pending_image = data
        self.tool = key
        self.tool_buttons[key].setChecked(True)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag if key == "hand" else QGraphicsView.NoDrag)
        cursors = {"hand": Qt.OpenHandCursor, "select": Qt.ArrowCursor, "edittext": Qt.IBeamCursor,
                   "text": Qt.IBeamCursor, "copytext": Qt.IBeamCursor}
        self.view.viewport().setCursor(cursors.get(key, Qt.CrossCursor))
        if key != "select":
            self.sel_xref = None
            self.view.clear_overlays()
        label, hint, sc = TOOLS[key]
        self.prop_icon.setPixmap(theme.make_icon(key, self.theme).pixmap(20, 20))
        self.prop_title.setText(tr(label))
        self.prop_hint.setText(tr(hint))
        props = TOOL_PROPS.get(key, set())
        for k, w in self.prop_groups.items():
            w.setVisible(k in props)
        self.stroke_btn.set_color(self.tool_colors.get(key, DEFAULT_COLOR))

    def toggle_sidebar(self):
        self.side.setVisible(not self.side.isVisible())

    def _ask_image(self, key):
        if key == "signature":
            dlg = SignatureDialog(self)
            return dlg.result_bytes() if dlg.exec() else None
        f, _ = QFileDialog.getOpenFileName(self, tr("Choose image"), "", IMAGE_FILTER)
        if not f:
            return None
        with open(f, "rb") as fh:
            return fh.read()

    def toast(self, msg, ms=5000):
        self.statusBar().showMessage(msg, ms)

    def checkpoint(self):
        self.undo_stack.append((self.doc.tobytes(), self.cur))
        self.undo_stack = self.undo_stack[-40:]
        self.redo_stack.clear()
        self.modified = True

    def changed(self, structural=False):
        self.invalidate_page()
        self.cur = max(0, min(self.cur, self.doc.page_count - 1))
        if structural:
            self.rebuild_thumbs()
            self.rebuild_toc()
            self._clear_search()
        else:
            self.update_thumb(self.cur)
        self.render()
        self.update_ui()

    def _restore(self, data, cur):
        self.doc = fitz.open("pdf", data)
        self.cur = cur
        self.sel_xref = None
        self.changed(structural=True)

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append((self.doc.tobytes(), self.cur))
        self.modified = True
        self._restore(*self.undo_stack.pop())

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append((self.doc.tobytes(), self.cur))
        self.modified = True
        self._restore(*self.redo_stack.pop())

    # ---------------------------------------------------------------- coordinates
    def scene_to_pdf(self, p):
        return fitz.Point(p.x() / self.zoom, p.y() / self.zoom) * self.page().derotation_matrix

    def scene_rect_to_pdf(self, a, b):
        return fitz.Rect(self.scene_to_pdf(a), self.scene_to_pdf(b)).normalize()

    def pdf_rect_to_scene(self, r):
        r = (fitz.Rect(r) * self.page().rotation_matrix).normalize() * self.zoom
        return QRectF(r.x0, r.y0, r.width, r.height)

    # ---------------------------------------------------------------- file handling
    def confirm_discard(self):
        if not (self.doc and self.modified):
            return True
        r = QMessageBox.question(self, APP_NAME, tr("Save changes to the current document?"),
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def new_doc(self):
        if not self.confirm_discard():
            return
        d = fitz.open()
        d.new_page(width=595, height=842)
        self.set_document(d, None)
        self.modified = True
        self.update_ui()

    def open_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, tr("Open PDF"), "", f"{PDF_FILTER};;{IMAGE_FILTER};;All files (*)")
        if f:
            self.open_path(f)

    def open_path(self, path):
        if path.lower().endswith(IMAGE_EXTS):
            return self.images_to_pdf([path])
        if not self.confirm_discard():
            return
        with open(path, "rb") as fh:
            data = fh.read()
        d = fitz.open(stream=data, filetype="pdf")
        pw = None
        if d.needs_pass:
            while True:
                pw, ok = QInputDialog.getText(self, tr("Password required"),
                                              f"{os.path.basename(path)}\n{tr('Password:')}", QLineEdit.Password)
                if not ok:
                    return
                if d.authenticate(pw):
                    break
                QMessageBox.warning(self, APP_NAME, tr("Wrong password."))
        if d.is_encrypted or pw:
            d = fitz.open("pdf", d.tobytes(encryption=fitz.PDF_ENCRYPT_NONE))
        self.set_document(d, path)
        self.password = pw or None
        self.owner_password = None
        self.add_recent(os.path.abspath(path))

    def set_document(self, d, path):
        self.doc = d
        self.invalidate_page()
        self.path = path
        self.cur = 0
        self.modified = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.sel_xref = None
        self.password = None
        self.update_ui()
        self.rebuild_thumbs()
        self.rebuild_toc()
        self._clear_search()
        QApplication.processEvents()
        self.fit_width()
        self.update_ui()
        self.set_tool(self.tool if self.tool not in ("image", "signature") else "hand")

    def _pdf_bytes(self, optimize=False):
        kw = dict(garbage=4 if optimize else 3, deflate=True)
        if optimize:
            kw.update(clean=True, deflate_images=True, deflate_fonts=True)
        if self.password or self.owner_password:
            kw.update(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=self.password or "",
                      owner_pw=self.owner_password or self.password,
                      permissions=int(fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY |
                                      fitz.PDF_PERM_ANNOTATE | fitz.PDF_PERM_FORM | fitz.PDF_PERM_PRINT_HQ))
        # shrink embedded fonts on a copy: the open document keeps full fonts so later edits can reuse them
        out = fitz.open("pdf", self.doc.tobytes())
        try:
            out.subset_fonts()
        except Exception:
            pass
        return out.tobytes(**kw)

    def _write(self, path, optimize=False):
        data = self._pdf_bytes(optimize)
        with open(path, "wb") as fh:
            fh.write(data)
        self.path = path
        self.modified = False
        self.add_recent(os.path.abspath(path))
        self.update_ui()
        self.toast(f"✓ {tr('Saved')}: {path} ({len(data) / 1024:.0f} KB)", 6000)
        return True

    def save(self):
        if self.doc is None:
            return False
        if not self.path:
            return self.save_as()
        return self._write(self.path)

    def save_as(self):
        start = self.path or os.path.join(os.path.expanduser("~"), "Documents", "Untitled.pdf")
        f, _ = QFileDialog.getSaveFileName(self, tr("Save As…"), start, PDF_FILTER)
        if not f:
            return False
        if not f.lower().endswith(".pdf"):
            f += ".pdf"
        return self._write(f)

    def save_optimized(self):
        start = (os.path.splitext(self.path)[0] + "_compressed.pdf") if self.path else "compressed.pdf"
        f, _ = QFileDialog.getSaveFileName(self, tr("Save optimized (compress)…"), start, PDF_FILTER)
        if not f:
            return
        before = len(self.doc.tobytes())
        self._write(f, optimize=True)
        after = os.path.getsize(f)
        QMessageBox.information(self, APP_NAME, f"{before / 1024:.0f} KB  →  {after / 1024:.0f} KB")

    def closeEvent(self, e):
        if self.confirm_discard():
            self.settings.setValue("geometry", self.saveGeometry())
            e.accept()
        else:
            e.ignore()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        pdfs = [f for f in files if f.lower().endswith(".pdf")]
        imgs = [f for f in files if f.lower().endswith(IMAGE_EXTS)]
        if pdfs and self.doc is not None:
            r = QMessageBox.question(self, APP_NAME, "Append the dropped file(s) to the current document?\n"
                                                     "(No = open the first file instead)",
                                     QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if r == QMessageBox.Yes:
                return self.merge_files(pdfs + imgs)
            if r == QMessageBox.Cancel:
                return
        if pdfs:
            self.open_path(pdfs[0])
        elif imgs:
            if self.doc is not None:
                self.merge_files(imgs)
            else:
                self.images_to_pdf(imgs)

    # ---------------------------------------------------------------- rendering & navigation
    def render(self):
        if self.doc is None:
            self.view.clear_scene()
            return
        page = self.page()
        dpr = self.devicePixelRatioF()
        pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom * dpr, self.zoom * dpr), annots=True)
        qp = QPixmap.fromImage(pix_to_qimage(pix))
        qp.setDevicePixelRatio(dpr)
        self.view.show_pixmap(qp)
        self.draw_search_overlays()
        if self.sel_xref:
            a = self.selected_annot()
            if a:
                self.view.add_overlay(self.pdf_rect_to_scene(a.rect), QColor(self.theme["accent"]), 30, dashed=True)
            else:
                self.sel_xref = None

    def goto(self, n, bottom=False):
        if self.doc is None:
            return
        n = max(0, min(n, self.doc.page_count - 1))
        if n != self.cur:
            self.sel_xref = None
        self.cur = n
        self.render()
        vb = self.view.verticalScrollBar()
        vb.setValue(vb.maximum() if bottom else vb.minimum())
        self.thumbs.blockSignals(True)
        self.thumbs.setCurrentRow(n)
        self.thumbs.blockSignals(False)
        self.update_ui()

    def _page_from_edit(self):
        try:
            self.goto(int(self.page_edit.text()) - 1)
        except ValueError:
            self.update_ui()

    def goto_dialog(self):
        n, ok = QInputDialog.getInt(self, tr("Go to page"), tr("Page:"), self.cur + 1, 1, self.doc.page_count)
        if ok:
            self.goto(n - 1)

    def set_zoom(self, z):
        self.zoom = max(0.1, min(z, 8.0))
        self.render()
        self.update_ui()

    def zoom_by(self, f):
        if self.doc:
            self.set_zoom(self.zoom * f)

    def _zoom_from_box(self):
        try:
            self.set_zoom(float(self.zoom_box.currentText().strip().rstrip("%")) / 100)
        except ValueError:
            self.update_ui()
        self.view.setFocus()

    def fit_width(self):
        if self.doc:
            self.set_zoom((self.view.viewport().width() - 60) / self.page().rect.width)

    def fit_page(self):
        if self.doc:
            r = self.page().rect
            vp = self.view.viewport()
            self.set_zoom(min((vp.width() - 60) / r.width, (vp.height() - 60) / r.height))

    @staticmethod
    def _thumb_size(page):
        r = page.rect
        z = min(THUMB_W / r.width, THUMB_MAX_H / r.height)
        return QSize(max(1, round(r.width * z)), max(1, round(r.height * z))), z

    def rebuild_thumbs(self):
        self._thumb_gen += 1
        gen = self._thumb_gen
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        if self.doc is not None:
            for i, page in enumerate(self.doc):
                it = QListWidgetItem()
                it.setData(Qt.UserRole, i)
                it.setData(Qt.UserRole + 2, self._thumb_size(page)[0])
                it.setFlags(it.flags() | Qt.ItemIsDragEnabled)
                self.thumbs.addItem(it)
            self.thumbs.setCurrentRow(self.cur)
            self._thumb_queue = list(range(self.doc.page_count))
            QTimer.singleShot(0, lambda: self._thumb_step(gen))
        self.thumbs.blockSignals(False)

    def _thumb_step(self, gen):
        if gen != self._thumb_gen or self.doc is None:
            return
        for _ in range(6):
            if not self._thumb_queue:
                return
            self.update_thumb(self._thumb_queue.pop(0))
        QTimer.singleShot(1, lambda: self._thumb_step(gen))

    def update_thumb(self, i):
        it = self.thumbs.item(i)
        if it is None or i >= self.doc.page_count:
            return
        page = self.doc[i]
        size, z = self._thumb_size(page)
        dpr = 2.0
        pm = QPixmap.fromImage(pix_to_qimage(page.get_pixmap(matrix=fitz.Matrix(z * dpr, z * dpr))))
        it.setData(Qt.UserRole + 2, size)
        it.setData(Qt.UserRole + 1, pm)

    def thumb_menu(self, pos):
        if self.doc is None:
            return
        m = QMenu(self)
        for label, icon, fn in (("Rotate right", "rotr", lambda: self.rotate_pages(90)),
                                ("Rotate left", "rotl", lambda: self.rotate_pages(-90)),
                                ("Duplicate", "copytext", self.duplicate_page),
                                ("Insert blank page after", "plus", self.insert_blank),
                                ("Extract selected…", "export", lambda: self.extract_pages(self.selected_pages())),
                                ("Delete", "trash", self.delete_pages)):
            a = m.addAction(theme.make_icon(icon, self.theme), tr(label))
            a.triggered.connect(fn)
        m.exec(self.thumbs.mapToGlobal(pos))

    def selected_pages(self):
        rows = sorted(self.thumbs.row(i) for i in self.thumbs.selectedItems())
        return rows or [self.cur]

    # ---------------------------------------------------------------- tools
    def apply_tool(self, tool, a, b, pts):
        if self.doc is None:
            return
        page = self.page()
        click = (b - a).manhattanLength() < 5
        r = self.scene_rect_to_pdf(a, b)
        pt = self.scene_to_pdf(a)
        color = self.stroke_btn.color
        rgb = to_rgb(color)
        fill = to_rgb(self.fill_btn.color) if self.fill_chk.isChecked() else None
        width = self.width_spin.value()
        opacity = self.opacity_spin.value() / 100
        bounds = unrotated_rect(page)

        if tool == "edittext":
            return self.edit_text_at(a)
        if tool == "copytext":
            if click:
                return
            txt = page.get_textbox(r).strip()
            QApplication.clipboard().setText(txt)
            self.toast(f"✓ {tr('Copied to clipboard.')} ({len(txt)})")
            return
        if tool == "text":
            dlg = TextDialog(self, tr("Add text"), family=self.font_box.currentText(), size=self.size_spin.value(),
                             color=color)
            if not dlg.exec() or not dlg.values()["text"].strip():
                return
            v = dlg.values()
            box = r if not click and r.width > 10 else fitz.Rect(pt.x, pt.y, max(bounds.x1 - 10, pt.x + 50),
                                                                   bounds.y1 - 5)
            self.checkpoint()
            spare, _ = insert_rich_text(page, box, v["text"], v["family"], v["size"], v["color"], v["bold"],
                                        v["italic"], v["align"], opacity, rotate=0)
            if spare < 0:
                self.toast("Text did not fit in the box – try a bigger box.", 6000)
            self.font_box.setCurrentText(v["family"])
            self.size_spin.setValue(v["size"])
            return self.changed()
        if tool == "note":
            txt, ok = QInputDialog.getMultiLineText(self, tr("Sticky note"), tr("Note text:"))
            if not ok:
                return
            self.checkpoint()
            an = page.add_text_annot(pt, txt, icon="Comment")
            an.set_colors(stroke=rgb)
            an.update()
            return self.changed()

        if click and tool not in ("image", "signature", "pen"):
            return
        self.checkpoint()
        if tool in ("highlight", "underline", "strikeout"):
            words = [fitz.Rect(w[:4]) for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(r)]
            quads = [w.quad for w in words] or [r.quad]
            an = {"highlight": page.add_highlight_annot, "underline": page.add_underline_annot,
                  "strikeout": page.add_strikeout_annot}[tool](quads=quads)
            an.set_colors(stroke=rgb)
            an.set_opacity(opacity)
            an.update()
        elif tool in ("rect", "ellipse"):
            an = page.add_rect_annot(r) if tool == "rect" else page.add_circle_annot(r)
            an.set_colors(stroke=rgb, fill=fill)
            an.set_border(width=width)
            an.set_opacity(opacity)
            an.update()
        elif tool in ("line", "arrow"):
            an = page.add_line_annot(self.scene_to_pdf(a), self.scene_to_pdf(b))
            if tool == "arrow":
                an.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_CLOSED_ARROW)
            an.set_colors(stroke=rgb, fill=rgb)
            an.set_border(width=width)
            an.set_opacity(opacity)
            an.update()
        elif tool == "pen":
            stroke = [tuple(self.scene_to_pdf(p)) for p in pts]
            if len(stroke) < 2:
                stroke.append((stroke[0][0] + 0.5, stroke[0][1] + 0.5))
            an = page.add_ink_annot([stroke])
            an.set_colors(stroke=rgb)
            an.set_border(width=width)
            an.set_opacity(opacity)
            an.update()
        elif tool == "whiteout":
            page.draw_rect(r, color=None, fill=(1, 1, 1), width=0, overlay=True)
        elif tool == "redact":
            page.add_redact_annot(r, fill=(0, 0, 0))
            page.apply_redactions()
        elif tool == "link":
            target, ok = QInputDialog.getText(self, tr("Create link"), tr("Web address (https://…) or page number:"))
            if not ok or not target.strip():
                self.undo_stack.pop()
                return
            target = target.strip()
            if target.isdigit():
                lk = {"kind": fitz.LINK_GOTO, "from": r, "page": max(0, min(int(target) - 1,
                                                                            self.doc.page_count - 1))}
            else:
                if "://" not in target and not target.startswith("mailto:"):
                    target = "https://" + target
                lk = {"kind": fitz.LINK_URI, "from": r, "uri": target}
            page.insert_link(lk)
            an = page.add_rect_annot(r)  # visible hint around the link
            an.set_colors(stroke=(0, 0.35, 0.9))
            an.set_border(width=0.6, dashes=[2, 2])
            an.update()
        elif tool == "crop":
            cb = page.cropbox
            nr = fitz.Rect(r.x0 + cb.x0, r.y0 + cb.y0, r.x1 + cb.x0, r.y1 + cb.y0) & page.mediabox
            page.set_cropbox(nr)
            self.set_tool("hand")
        elif tool in ("image", "signature"):
            if not self.pending_image:
                self.undo_stack.pop()
                return
            if click:
                img = QImage.fromData(self.pending_image)
                w = 160 if tool == "signature" else 220
                h = w * img.height() / max(1, img.width())
                r = fitz.Rect(pt.x, pt.y, pt.x + w, pt.y + h)
            page.insert_image(r, stream=self.pending_image, keep_proportion=True, overlay=True)
        self.changed()

    def span_at(self, page, pt):
        d = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)
        best = None
        for b in d["blocks"]:
            for ln in b.get("lines", []):
                for s in ln["spans"]:
                    if s["text"].strip() and fitz.Rect(s["bbox"]).contains(pt):
                        return s
                    if s["text"].strip() and best is None and (fitz.Rect(s["bbox"]) + (-2, -2, 2, 2)).contains(pt):
                        best = s
        return best

    @staticmethod
    def guess_family(span):
        f = span["font"].lower()
        if has_khmer(span["text"]):
            return default_family(span["text"])
        for key, fam in (("times", "Times New Roman"), ("courier", "Courier New"), ("calibri", "Calibri"),
                         ("segoe", "Segoe UI"), ("tahoma", "Tahoma"), ("verdana", "Verdana"),
                         ("georgia", "Georgia")):
            if key in f and fam in FONTS:
                return fam
        return default_family()

    def edit_text_at(self, scene_pt):
        page = self.page()
        s = self.span_at(page, self.scene_to_pdf(scene_pt))
        if not s:
            self.toast(tr("No editable text here (scanned pages need OCR)."))
            return
        r = fitz.Rect(s["bbox"])
        hl = self.view.add_overlay(self.pdf_rect_to_scene(r), QColor(self.theme["accent"]), 40)
        font = s["font"].lower()
        buf = span_font_buffer(page, s)
        orig_ok = font_covers(buf, s["text"])
        dlg = TextDialog(self, tr("Edit text"), text=s["text"].replace("\x00", ""),
                         family=ORIGINAL_FONT if orig_ok else self.guess_family(s), size=round(s["size"], 2),
                         color=from_int(s["color"]), bold=bool(s["flags"] & 16) or "bold" in font,
                         italic=bool(s["flags"] & 2) or "italic" in font,
                         extra_fonts=[ORIGINAL_FONT] if orig_ok else [])
        accepted = dlg.exec()
        self.view.sc.removeItem(hl)
        self.view.overlays.remove(hl)
        if not accepted:
            return
        v = dlg.values()
        self.checkpoint()
        self._replace_span(page, s, v, buf)
        self.changed()

    def _replace_span(self, page, s, v, fontbuffer=None):
        r = fitz.Rect(s["bbox"])
        h = r.height
        page.add_redact_annot(fitz.Rect(r.x0, r.y0 + h * 0.18, r.x1, r.y1 - h * 0.18), fill=False)
        page.apply_redactions(images=REDACT_IMG_NONE, graphics=REDACT_ART_NONE)
        text = v["text"]
        if not text:
            return
        family, use_buf = v["family"], None
        if family == ORIGINAL_FONT:
            if font_covers(fontbuffer, text):
                use_buf = fontbuffer
            else:  # the embedded (often subset) font lacks some of the new characters
                family = self.guess_family(dict(s, text=text))
                self.toast(f"The original font doesn't contain all new characters – used {family}.", 7000)
        place_text(page, fitz.Point(s["origin"]), text, family, v["size"], v["color"], v["bold"], v["italic"],
                   fontbuffer=use_buf)

    def find_replace(self):
        dlg, form = form_dialog(self, tr("Find & replace"))
        f = QLineEdit(self.find_edit.text())
        rep = QLineEdit()
        allp = QCheckBox(tr("All pages"))
        allp.setChecked(True)
        form.addRow(tr("Find"), f)
        form.addRow(tr("Replace with"), rep)
        form.addRow("", allp)
        ok_cancel(dlg, form)
        if not dlg.exec() or not f.text():
            return
        needle, new = f.text(), rep.text()
        pages = range(self.doc.page_count) if allp.isChecked() else [self.cur]
        self.checkpoint()
        count = 0
        for pno in pages:
            page = self.doc[pno]
            hits = page.search_for(needle)
            if not hits:
                continue
            jobs = []
            for hr in hits:
                s = self.span_at(page, fitz.Point((hr.x0 + hr.x1) / 2, (hr.y0 + hr.y1) / 2))
                size = s["size"] if s else hr.height * 0.8
                jobs.append(dict(bbox=tuple(hr), origin=(hr.x0, s["origin"][1] if s else hr.y1 - hr.height * 0.2),
                                 size=size, color=s["color"] if s else 0, font=s["font"] if s else "",
                                 flags=s["flags"] if s else 0, buf=span_font_buffer(page, s) if s else None))
            for j in jobs:
                jr = fitz.Rect(j["bbox"])
                h = jr.height
                page.add_redact_annot(fitz.Rect(jr.x0, jr.y0 + h * 0.18, jr.x1, jr.y1 - h * 0.18), fill=False)
            page.apply_redactions(images=REDACT_IMG_NONE, graphics=REDACT_ART_NONE)
            for j in jobs:
                if new:
                    buf = j["buf"] if font_covers(j["buf"], new) else None
                    place_text(page, fitz.Point(j["origin"]), new, self.guess_family(dict(font=j["font"], text=new)),
                               j["size"], from_int(j["color"]), bool(j["flags"] & 16) or "bold" in j["font"].lower(),
                               bool(j["flags"] & 2), fontbuffer=buf)
                count += 1
        if not count:
            self.undo_stack.pop()
            QMessageBox.information(self, APP_NAME, f'"{needle}" — {tr("No matches")}')
            return
        self.changed(structural=True)
        QMessageBox.information(self, APP_NAME, f"✓ {count}")

    # ---------------------------------------------------------------- annotations
    def annot_at(self, page, pt):
        hit = None
        for a in page.annots():
            if (a.rect + (-3, -3, 3, 3)).contains(pt):
                hit = a
        return hit

    def select_annot_at(self, scene_pt):
        page = self.page()
        self.view.clear_overlays()
        a = self.annot_at(page, self.scene_to_pdf(scene_pt))
        self.sel_xref = a.xref if a else None
        if not a:
            return None
        self.toast(f"{a.type[1]} — Delete / drag / double-click")
        return self.view.add_overlay(self.pdf_rect_to_scene(a.rect), QColor(self.theme["accent"]), 30, dashed=True)

    def selected_annot(self):
        if not self.sel_xref:
            return None
        page = self.page()
        return next((a for a in page.annots() if a.xref == self.sel_xref), None)

    def move_selected(self, delta):
        a = self.selected_annot()
        if a is None:
            return
        p0, p1 = self.scene_to_pdf(QPointF(0, 0)), self.scene_to_pdf(delta)
        dx, dy = p1.x - p0.x, p1.y - p0.y
        t = a.type[0]
        if t in (fitz.PDF_ANNOT_HIGHLIGHT, fitz.PDF_ANNOT_UNDERLINE, fitz.PDF_ANNOT_STRIKE_OUT,
                 fitz.PDF_ANNOT_SQUIGGLY):
            self.toast("Text markups can't be moved – delete and re-create instead.")
            return self.render()
        self.checkpoint()
        page = self.page()
        if t in (fitz.PDF_ANNOT_INK, fitz.PDF_ANNOT_LINE, fitz.PDF_ANNOT_POLYGON, fitz.PDF_ANNOT_POLY_LINE):
            verts = a.vertices
            cols, border, op = a.colors, a.border or {}, a.opacity
            content = a.info.get("content", "")
            if t == fitz.PDF_ANNOT_INK:
                new = page.add_ink_annot([[(x + dx, y + dy) for x, y in st] for st in verts])
            else:
                moved = [(x + dx, y + dy) for x, y in verts]
                if t == fitz.PDF_ANNOT_LINE:
                    new = page.add_line_annot(moved[0], moved[-1])
                    new.set_line_ends(*a.line_ends)
                elif t == fitz.PDF_ANNOT_POLYGON:
                    new = page.add_polygon_annot(moved)
                else:
                    new = page.add_polyline_annot(moved)
            new.set_colors(stroke=cols.get("stroke") or None, fill=cols.get("fill") or None)
            new.set_border(width=border.get("width", 1) or 1)
            if op is not None and op >= 0:
                new.set_opacity(op)
            new.set_info(content=content)
            new.update()
            page.delete_annot(a)
            self.sel_xref = new.xref
        else:
            r = a.rect
            a.set_rect(fitz.Rect(r.x0 + dx, r.y0 + dy, r.x1 + dx, r.y1 + dy))
            a.update()
        self.changed()

    def double_click(self, scene_pt):
        page = self.page()
        a = self.annot_at(page, self.scene_to_pdf(scene_pt))
        if a is None:
            return self.edit_text_at(scene_pt)
        dlg = AnnotDialog(self, a)
        if not dlg.exec():
            return
        self.checkpoint()
        a = self.selected_annot() or self.annot_at(page, self.scene_to_pdf(scene_pt))
        a.set_info(content=dlg.content.toPlainText())
        t = a.type[0]
        fill_ok = t in (fitz.PDF_ANNOT_SQUARE, fitz.PDF_ANNOT_CIRCLE, fitz.PDF_ANNOT_POLYGON, fitz.PDF_ANNOT_LINE)
        if fill_ok:
            a.set_colors(stroke=to_rgb(dlg.stroke.color),
                         fill=to_rgb(dlg.fill.color) if dlg.fill_on.isChecked() else [])
        elif t != fitz.PDF_ANNOT_FREE_TEXT:
            a.set_colors(stroke=to_rgb(dlg.stroke.color))
        if t not in (fitz.PDF_ANNOT_TEXT, fitz.PDF_ANNOT_HIGHLIGHT):
            a.set_border(width=dlg.width.value())
        a.set_opacity(dlg.opacity.value() / 100)
        a.update()
        self.changed()

    def delete_selected(self):
        a = self.selected_annot()
        if a is None:
            self.toast(tr(TOOLS["select"][1]))
            return
        self.checkpoint()
        self.page().delete_annot(a)
        self.sel_xref = None
        self.changed()

    def delete_page_annots(self):
        page = self.page()
        annots = list(page.annots())
        if not annots:
            return
        self.checkpoint()
        for a in annots:
            page.delete_annot(a)
        self.sel_xref = None
        self.changed()

    # ---------------------------------------------------------------- search
    def show_find(self):
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def _clear_search(self):
        had = bool(self.search_hits)
        self.search_hits = []
        self.search_idx = -1
        self.find_lbl.setText("")
        if had and self.doc is not None:
            self.render()

    def find_next(self, step=1):
        text = self.find_edit.text()
        if not text or self.doc is None:
            return
        if not self.search_hits:
            for page in self.doc:
                for r in page.search_for(text):
                    self.search_hits.append((page.number, r))
            if not self.search_hits:
                self.find_lbl.setText(tr("No matches"))
                return
            after = [i for i, (p, _) in enumerate(self.search_hits) if p >= self.cur]
            self.search_idx = (after[0] if after else 0) - step
        self.search_idx = (self.search_idx + step) % len(self.search_hits)
        pno, r = self.search_hits[self.search_idx]
        self.find_lbl.setText(f"{self.search_idx + 1}/{len(self.search_hits)}")
        if pno != self.cur:
            self.goto(pno)
        else:
            self.render()
        self.view.centerOn(self.pdf_rect_to_scene(r).center())

    def draw_search_overlays(self):
        for i, (pno, r) in enumerate(self.search_hits):
            if pno == self.cur:
                cur = i == self.search_idx
                self.view.add_overlay(self.pdf_rect_to_scene(r), QColor(255, 120, 0) if cur else QColor(255, 210, 0),
                                      110 if cur else 70)

    # ---------------------------------------------------------------- page operations
    def rotate_pages(self, deg, all_pages=False):
        pages = range(self.doc.page_count) if all_pages else self.selected_pages()
        self.checkpoint()
        for i in pages:
            p = self.doc[i]
            p.set_rotation((p.rotation + deg) % 360)
        self.changed(structural=True)

    def insert_blank(self):
        r = self.page().rect
        self.checkpoint()
        self.doc.new_page(self.cur + 1, width=r.width, height=r.height)
        self.cur += 1
        self.changed(structural=True)

    def duplicate_page(self):
        self.checkpoint()
        to = self.cur + 1 if self.cur + 1 < self.doc.page_count else -1
        self.doc.fullcopy_page(self.cur, to)
        self.cur += 1
        self.changed(structural=True)

    def delete_pages(self):
        pages = self.selected_pages()
        if len(pages) >= self.doc.page_count:
            QMessageBox.warning(self, APP_NAME, tr("A PDF must keep at least one page."))
            return
        if QMessageBox.question(self, APP_NAME, f"{tr('Delete the selected page(s)?')}  ({len(pages)})") \
                != QMessageBox.Yes:
            return
        self.checkpoint()
        self.doc.delete_pages(pages)
        self.cur = min(pages[0], self.doc.page_count - 1)
        self.changed(structural=True)

    def reorder_pages(self, order):
        self.checkpoint()
        cur_old = self.cur
        self.doc.select(order)
        self.cur = order.index(cur_old)
        self.changed(structural=True)

    def move_page(self, d):
        n = self.cur + d
        if not 0 <= n < self.doc.page_count:
            return
        order = list(range(self.doc.page_count))
        order[self.cur], order[n] = order[n], order[self.cur]
        self.reorder_pages(order)

    def reverse_pages(self):
        self.reorder_pages(list(range(self.doc.page_count))[::-1])

    def reset_crop(self):
        self.checkpoint()
        p = self.page()
        p.set_cropbox(p.mediabox)
        self.changed(structural=True)

    def _ask_range(self, title, default):
        txt, ok = QInputDialog.getText(self, title, tr("Pages (e.g. 1-3, 5, 8-):"), text=default)
        if not ok:
            return None
        try:
            return parse_ranges(txt, self.doc.page_count)
        except ValueError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return None

    def extract_pages(self, pages=None):
        if pages is None:
            pages = self._ask_range(tr("Extract pages"), f"{self.cur + 1}")
        if not pages:
            return
        base = os.path.splitext(self.path)[0] if self.path else "document"
        f, _ = QFileDialog.getSaveFileName(self, tr("Extract pages"), f"{base}_extract.pdf", PDF_FILTER)
        if not f:
            return
        out = fitz.open()
        for p in pages:
            out.insert_pdf(self.doc, from_page=p, to_page=p)
        out.save(f, garbage=3, deflate=True)
        self.toast(f"✓ {len(pages)} → {f}", 6000)

    def split_pdf(self):
        dlg, form = form_dialog(self, tr("Split PDF"))
        every = QRadioButton(tr("Every N pages"))
        every.setChecked(True)
        n = QSpinBox()
        n.setRange(1, max(1, self.doc.page_count))
        ranges_rb = QRadioButton(tr("Custom ranges (separate files with ;)"))
        ranges = QLineEdit("1-2; 3-")
        form.addRow(every, n)
        form.addRow(ranges_rb, ranges)
        ok_cancel(dlg, form)
        if not dlg.exec():
            return
        total = self.doc.page_count
        try:
            if every.isChecked():
                k = n.value()
                groups = [list(range(i, min(i + k, total))) for i in range(0, total, k)]
            else:
                groups = [parse_ranges(g, total) for g in ranges.text().split(";") if g.strip()]
        except ValueError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        folder = QFileDialog.getExistingDirectory(self, tr("Choose output folder"),
                                                  os.path.dirname(self.path) if self.path else "")
        if not folder:
            return
        base = os.path.splitext(os.path.basename(self.path))[0] if self.path else "document"
        for gi, g in enumerate(groups, 1):
            out = fitz.open()
            for p in g:
                out.insert_pdf(self.doc, from_page=p, to_page=p)
            out.save(os.path.join(folder, f"{base}_part{gi}.pdf"), garbage=3, deflate=True)
        QMessageBox.information(self, APP_NAME, f"✓ {len(groups)} PDF\n{folder}")

    def _file_to_pdf(self, f):
        if f.lower().endswith(IMAGE_EXTS):
            img = fitz.open(f)
            return fitz.open("pdf", img.convert_to_pdf())
        with open(f, "rb") as fh:
            d = fitz.open(stream=fh.read(), filetype="pdf")
        if d.needs_pass:
            pw, ok = QInputDialog.getText(self, tr("Password required"), f"{os.path.basename(f)}\n{tr('Password:')}",
                                          QLineEdit.Password)
            if not ok or not d.authenticate(pw):
                raise ValueError(f"Cannot open protected file {f}")
        return d

    def merge_files(self, files=None, at=None):
        if self.doc is None:
            return
        if files is None:
            files, _ = QFileDialog.getOpenFileNames(self, tr("Merge / append PDFs or images…"), "",
                                                    "PDF and images (*.pdf *.png *.jpg *.jpeg *.bmp *.gif *.tif "
                                                    "*.tiff *.webp)")
        if not files:
            return
        self.checkpoint()
        pos = self.doc.page_count if at is None else at
        start = pos
        for f in files:
            src = self._file_to_pdf(f)
            self.doc.insert_pdf(src, start_at=pos)
            pos += src.page_count
        self.cur = start if start < self.doc.page_count else self.cur
        self.changed(structural=True)
        self.toast(f"✓ +{pos - start} {tr('Pages')}", 6000)

    def insert_from_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr("Insert pages from file…"), "",
                                                "PDF and images (*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if files:
            self.merge_files(files, at=self.cur + 1)

    # ---------------------------------------------------------------- conversions
    def images_to_pdf(self, files=None):
        if files is None:
            files, _ = QFileDialog.getOpenFileNames(self, tr("Images to PDF…"), "", IMAGE_FILTER)
        if not files or not self.confirm_discard():
            return
        out = fitz.open()
        for f in files:
            out.insert_pdf(self._file_to_pdf(f))
        self.set_document(out, None)
        self.modified = True
        self.update_ui()

    def export_images(self):
        dpi, ok = QInputDialog.getInt(self, tr("Export as images"), tr("Resolution (DPI):"), 150, 36, 600)
        if not ok:
            return
        fmt, ok = QInputDialog.getItem(self, tr("Export as images"), tr("Format:"), ["png", "jpg"], 0, False)
        if not ok:
            return
        folder = QFileDialog.getExistingDirectory(self, tr("Choose output folder"))
        if not folder:
            return
        base = os.path.splitext(os.path.basename(self.path))[0] if self.path else "page"
        prog = QProgressDialog("…", "Cancel", 0, self.doc.page_count, self)
        prog.setWindowModality(Qt.WindowModal)
        for i, page in enumerate(self.doc):
            if prog.wasCanceled():
                break
            prog.setValue(i)
            QApplication.processEvents()
            page.get_pixmap(dpi=dpi).save(os.path.join(folder, f"{base}_{i + 1:03d}.{fmt}"))
        prog.setValue(self.doc.page_count)
        self.toast(f"✓ {folder}", 6000)

    def export_text(self):
        base = os.path.splitext(self.path)[0] if self.path else "document"
        f, _ = QFileDialog.getSaveFileName(self, tr("Export text…"), base + ".txt", "Text (*.txt)")
        if not f:
            return
        with open(f, "w", encoding="utf-8") as fh:
            for page in self.doc:
                fh.write(f"===== Page {page.number + 1} =====\n{page.get_text()}\n")
        self.toast(f"✓ {f}", 6000)

    # ---------------------------------------------------------------- stamps
    def add_watermark(self):
        dlg, form = form_dialog(self, tr("Add watermark"))
        text = QLineEdit("CONFIDENTIAL")
        size = QSpinBox()
        size.setRange(8, 300)
        size.setValue(72)
        color = ColorButton("#c0392b")
        op = QSpinBox()
        op.setRange(5, 100)
        op.setValue(25)
        op.setSuffix(" %")
        angle = QSpinBox()
        angle.setRange(-180, 180)
        angle.setValue(45)
        allp = QCheckBox(tr("All pages"))
        allp.setChecked(True)
        for lbl, w in (("Text", text), ("Font size", size), ("Color", color), ("Opacity", op),
                       ("Angle (Khmer: 0/90 only)", angle), ("", allp)):
            form.addRow(tr(lbl), w)
        ok_cancel(dlg, form)
        if not dlg.exec() or not text.text().strip():
            return
        t, fs, col, opacity, ang = text.text(), size.value(), color.color, op.value() / 100, angle.value()
        self.checkpoint()
        for i in (range(self.doc.page_count) if allp.isChecked() else [self.cur]):
            page = self.doc[i]
            b = unrotated_rect(page)
            c = fitz.Point(b.width / 2, b.height / 2)
            if has_khmer(t):
                rot = (round(ang / 90) * 90) % 360
                box = fitz.Rect(0, c.y - fs, b.width, c.y + fs * 1.5) if rot in (0, 180) else \
                    fitz.Rect(c.x - fs, 0, c.x + fs * 1.5, b.height)
                insert_rich_text(page, box, t, default_family(t), fs, col, bold=True, align="center",
                                 opacity=opacity, rotate=rot)
            else:
                tl = fitz.get_text_length(t, fontname="hebo", fontsize=fs)
                page.insert_text(fitz.Point(c.x - tl / 2, c.y + fs * 0.35), t, fontsize=fs, fontname="hebo",
                                 color=to_rgb(col), fill_opacity=opacity, morph=(c, fitz.Matrix(ang)),
                                 overlay=True)
        self.changed(structural=True)

    def add_page_numbers(self):
        dlg, form = form_dialog(self, tr("Page numbers / header / footer"))
        fmt = QLineEdit("Page {n} of {total}" if i18n.LANG == "en" else "ទំព័រ {n} / {total}")
        pos = QComboBox()
        for p in ("Bottom center", "Bottom right", "Bottom left", "Top center", "Top right", "Top left"):
            pos.addItem(tr(p), p)
        size = QDoubleSpinBox()
        size.setRange(5, 72)
        size.setValue(10)
        fam = QComboBox()
        fam.addItems(list(FONTS))
        fam.setCurrentText(default_family(fmt.text()))
        fmt.textChanged.connect(lambda s: has_khmer(s) and fam.setCurrentText(default_family(s)))
        color = ColorButton("#333333")
        margin = QSpinBox()
        margin.setRange(0, 200)
        margin.setValue(24)
        start = QSpinBox()
        start.setRange(-9999, 99999)
        start.setValue(1)
        rng = QLineEdit(f"1-{self.doc.page_count}")
        for lbl, w in (("Text ({n} = number, {total} = count)", fmt), ("Position", pos), ("Font", fam),
                       ("Size", size), ("Color", color), ("Margin", margin), ("First number", start),
                       ("Apply to pages", rng)):
            form.addRow(tr(lbl), w)
        ok_cancel(dlg, form)
        if not dlg.exec():
            return
        try:
            pages = parse_ranges(rng.text(), self.doc.page_count)
        except ValueError as e:
            return QMessageBox.warning(self, APP_NAME, str(e))
        vpos, hpos = pos.currentData().lower().split()
        fs, m = size.value(), margin.value()
        self.checkpoint()
        for k, i in enumerate(pages):
            page = self.doc[i]
            b = unrotated_rect(page)
            box = fitz.Rect(m, m, b.width - m, m + fs * 2.2) if vpos == "top" else \
                fitz.Rect(m, b.height - m - fs * 2.2, b.width - m, b.height - m)
            txt = fmt.text().replace("{n}", str(start.value() + k)).replace("{total}", str(len(pages)))
            insert_rich_text(page, box, txt, fam.currentText(), fs, color.color, align=hpos)
        self.changed(structural=True)

    # ---------------------------------------------------------------- forms, bookmarks, metadata, security
    def fill_forms(self):
        dlg = FormsDialog(self, self.doc)
        if dlg.exec() and dlg.rows:
            self.checkpoint()
            dlg.apply(self.doc)
            self.changed(structural=True)

    def flatten(self):
        if QMessageBox.question(self, APP_NAME, tr("Flatten annotations && forms").replace("&&", "&") + "?") \
                != QMessageBox.Yes:
            return
        self.checkpoint()
        self.doc.bake(annots=True, widgets=True)
        self.sel_xref = None
        self.changed(structural=True)

    def rebuild_toc(self):
        self.toc_tree.clear()
        if self.doc is None:
            return
        parents = {}
        for i, (lvl, title, pno) in enumerate(self.doc.get_toc(simple=True)):
            it = QTreeWidgetItem([title, str(pno)])
            it.setData(0, Qt.UserRole, i)
            it.setForeground(1, QColor(self.theme["muted"]))
            parent = parents.get(lvl - 1)
            if parent is not None and lvl > 1:
                parent.addChild(it)
            else:
                self.toc_tree.addTopLevelItem(it)
            parents[lvl] = it
        self.toc_tree.expandAll()
        self.toc_tree.resizeColumnToContents(0)

    def _toc_clicked(self, item, _col):
        try:
            self.goto(int(item.text(1)) - 1)
        except ValueError:
            pass

    def bookmark_add(self):
        if self.doc is None:
            return
        title, ok = QInputDialog.getText(self, tr("Add bookmark"), tr("Title:"), text=f"{tr('Page')} {self.cur + 1}")
        if not ok or not title:
            return
        toc = self.doc.get_toc(simple=True)
        idx = next((i for i, (lvl, _, p) in enumerate(toc) if lvl == 1 and p > self.cur + 1), len(toc))
        toc.insert(idx, [1, title, self.cur + 1])
        self.checkpoint()
        self.doc.set_toc(toc)
        self.rebuild_toc()
        self.update_ui()
        self.side.setCurrentIndex(1)

    def _toc_selected(self):
        it = self.toc_tree.currentItem()
        return None if it is None else it.data(0, Qt.UserRole)

    def bookmark_rename(self):
        i = self._toc_selected()
        if i is None:
            return
        toc = self.doc.get_toc(simple=True)
        title, ok = QInputDialog.getText(self, tr("Rename bookmark"), tr("Title:"), text=toc[i][1])
        if ok and title:
            toc[i][1] = title
            self.checkpoint()
            self.doc.set_toc(toc)
            self.rebuild_toc()
            self.update_ui()

    def bookmark_delete(self):
        i = self._toc_selected()
        if i is None:
            return
        toc = self.doc.get_toc(simple=True)
        lvl = toc[i][0]
        j = i + 1
        while j < len(toc) and toc[j][0] > lvl:
            j += 1
        del toc[i:j]
        self.checkpoint()
        self.doc.set_toc(toc)
        self.rebuild_toc()
        self.update_ui()

    def edit_metadata(self):
        meta = self.doc.metadata or {}
        dlg, form = form_dialog(self, tr("Document properties"))
        fields = {}
        for key in ("title", "author", "subject", "keywords", "creator", "producer"):
            fields[key] = QLineEdit(meta.get(key) or "")
            form.addRow(key.capitalize(), fields[key])
        info = QLabel(f"Pages: {self.doc.page_count}    Format: {meta.get('format', '')}\n"
                      f"Created: {meta.get('creationDate', '')}\nModified: {meta.get('modDate', '')}")
        info.setObjectName("Muted")
        form.addRow(info)
        ok_cancel(dlg, form)
        if dlg.exec():
            self.checkpoint()
            new = dict(meta)
            new.update({k: w.text() for k, w in fields.items()})
            self.doc.set_metadata({k: v for k, v in new.items() if k in (
                "title", "author", "subject", "keywords", "creator", "producer", "creationDate", "modDate")})
            self.update_ui()

    def set_password(self):
        dlg, form = form_dialog(self, tr("Protect with password (AES-256)"))
        user, user2, owner = QLineEdit(), QLineEdit(), QLineEdit()
        for w in (user, user2, owner):
            w.setEchoMode(QLineEdit.Password)
        form.addRow(tr("Open password"), user)
        form.addRow(tr("Confirm"), user2)
        form.addRow(tr("Owner password (optional)"), owner)
        note = QLabel(tr("The password is applied when you save."))
        note.setObjectName("Muted")
        form.addRow(note)
        ok_cancel(dlg, form)
        if not dlg.exec():
            return
        if user.text() != user2.text():
            return QMessageBox.warning(self, APP_NAME, tr("Passwords do not match."))
        if not user.text() and not owner.text():
            return
        self.password = user.text() or None
        self.owner_password = owner.text() or None
        self.modified = True
        self.update_ui()
        self.toast(tr("The password is applied when you save."), 6000)

    def remove_password(self):
        self.password = self.owner_password = None
        self.modified = True
        self.update_ui()
        self.toast(tr("Remove password") + " — " + tr("Save"), 6000)

    # ---------------------------------------------------------------- print & about
    def print_doc(self):
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        dlg.setMinMax(1, self.doc.page_count)
        dlg.setFromTo(1, self.doc.page_count)
        if not dlg.exec():
            return
        a, b = printer.fromPage(), printer.toPage()
        if a == 0:
            a, b = 1, self.doc.page_count
        painter = QPainter(printer)
        try:
            for k, i in enumerate(range(a - 1, b)):
                if k:
                    printer.newPage()
                img = pix_to_qimage(self.doc[i].get_pixmap(dpi=200, annots=True))
                vp = painter.viewport()
                sz = img.size().scaled(vp.size(), Qt.KeepAspectRatio)
                target = QRectF(vp.x() + (vp.width() - sz.width()) / 2, vp.y() + (vp.height() - sz.height()) / 2,
                                sz.width(), sz.height())
                painter.drawImage(target, img)
        finally:
            painter.end()

    # ---------------------------------------------------------------- updates
    def check_updates(self, silent=False):
        if self.update_busy:
            return
        if self.update_info and not silent:
            self._offer_update()
            return
        self.update_busy = True
        if not silent:
            self.toast(tr("Checking for updates…"))

        def work():
            try:
                self.update_sig.checked.emit(updater.fetch_latest(), silent)
            except Exception as e:
                self.update_sig.check_failed.emit(str(e), silent)

        threading.Thread(target=work, daemon=True).start()

    def _update_checked(self, info, silent):
        self.update_busy = False
        if info and updater.is_newer(info["version"]):
            self.update_info = info
            self.st_update.setText(f"{tr('Update to')} v{info['version']}")
            self.st_update.setToolTip(tr("A new version is available. Click to install."))
            self.st_update.setStyleSheet(f"QToolButton {{ background: {self.theme['accent']}; color: white; "
                                         f"border-radius: 4px; padding: 1px 8px; }}")
            if not silent:
                self._offer_update()
        elif not silent:
            QMessageBox.information(self, APP_NAME, f"{tr('You have the latest version')} (v{VERSION}).")

    def _update_check_failed(self, msg, silent):
        self.update_busy = False
        if not silent:
            QMessageBox.warning(self, APP_NAME, f"{tr('Could not check for updates.')}\n\n{msg}")

    def _offer_update(self):
        info = self.update_info
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Information)
        box.setText(f"{tr('Version')} {info['version']} {tr('is available')} ({tr('you have')} {VERSION}).")
        box.setInformativeText(info["notes"][:1500])
        now = box.addButton(tr("Update now"), QMessageBox.AcceptRole)
        box.addButton(tr("Later"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not now:
            return
        if not updater.can_self_update():
            QDesktopServices.openUrl(QUrl(updater.RELEASES_URL))
            return
        if not self.confirm_discard():
            return
        self.update_busy = True
        self.update_cancel = threading.Event()
        self.update_dlg = QProgressDialog(tr("Downloading update…"), tr("Cancel"), 0, 100, self)
        self.update_dlg.setWindowTitle(APP_NAME)
        self.update_dlg.setWindowModality(Qt.WindowModal)
        self.update_dlg.setAutoClose(False)
        self.update_dlg.setAutoReset(False)
        self.update_dlg.setMinimumDuration(0)
        self.update_dlg.canceled.connect(self.update_cancel.set)
        self.update_dlg.show()

        def work():
            try:
                path = updater.download(info, updater.download_path(),
                                        lambda d, t: self.update_sig.progress.emit(d, t), self.update_cancel)
                try:
                    updater.verify_runs(path)
                except Exception:
                    os.remove(path)
                    raise
                self.update_sig.downloaded.emit(path)
            except updater.Cancelled:
                self.update_sig.download_failed.emit("")
            except Exception as e:
                self.update_sig.download_failed.emit(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _update_progress(self, done, total):
        self.update_dlg.setValue(int(done * 100 / total) if total else 0)

    def _update_download_failed(self, msg):
        self.update_busy = False
        self.update_dlg.close()
        if msg:
            self._update_failed(msg)

    def _update_failed(self, msg):
        r = QMessageBox.warning(self, APP_NAME,
                                f"{tr('Could not install the update.')}\n\n{msg}\n\n"
                                f"{tr('Open the download page?')}", QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(updater.RELEASES_URL))

    def _update_downloaded(self, path):
        self.update_dlg.close()
        self.update_busy = False
        try:
            updater.install_and_launch(path, [self.path] if self.path and os.path.exists(self.path) else [])
        except Exception as e:
            try:
                os.remove(path)
            except OSError:
                pass
            self._update_failed(str(e))
            return
        self.modified = False  # the user already chose to save or discard before the download
        self.close()

    def about(self):
        QMessageBox.about(self, APP_NAME,
                          f"<h3>{APP_NAME}</h3><p><b>Version {VERSION}</b> &nbsp;·&nbsp; {RELEASE_DATE}</p>"
                          f"<p>{tr('Edit, sign and organise your PDF files')}</p>"
                          f"<p>Developed by <b>{COMPANY}</b></p><p>{COPYRIGHT}</p>"
                          f'<p>Source code: <a href="https://github.com/{UPDATE_REPO}">'
                          f"github.com/{UPDATE_REPO}</a></p>"
                          f"<p>Engine: PyMuPDF {fitz.VersionBind} · Qt</p>")


def excepthook(etype, value, tb):
    traceback.print_exception(etype, value, tb)
    app = QApplication.instance()
    if app:
        QMessageBox.critical(app.activeWindow(), APP_NAME, f"Error:\n\n{value}")


def main():
    if updater.SELF_TEST_ARG in sys.argv:  # the old version checks that this EXE can start before installing it
        return
    sys.excepthook = excepthook
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    i18n.LANG = "en"  # English-only interface
    FONTS.update(find_fonts())
    updater.cleanup_previous()
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        QTimer.singleShot(50, lambda: w.open_path(sys.argv[1]))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
