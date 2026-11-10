"""Colors, stylesheet and line icons for PDF Editor Pro."""
import re
import sys

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer

DARK = dict(bg="#0f1117", surface="#171a23", surface2="#1f2330", input="#12141c", border="#2a2f3d",
            hover="#252a38", pressed="#2f3547", text="#eef0f6", muted="#98a0b3", muted2="#596075",
            accent="#6366f1", accent2="#8b5cf6", accent_hover="#818cf8", canvas="#1c1f2a", scroll="#3a4052",
            thumb_border="#333a4c")
LIGHT = dict(bg="#f3f4fb", surface="#ffffff", surface2="#f5f6fb", input="#ffffff", border="#e2e5f0",
             hover="#eef0fa", pressed="#e3e6f5", text="#1a1d2b", muted="#616880", muted2="#b4b9c9",
             accent="#4f46e5", accent2="#7c3aed", accent_hover="#6366f1", canvas="#e8eaf3", scroll="#c5c9d8",
             thumb_border="#d6d9e6")
THEMES = {"dark": DARK, "light": LIGHT}
# Tool group -> icon tint, one each for the dark and light themes
GROUP_TINTS = {"NAVIGATE": {"dark": "#7dd3fc", "light": "#0284c7"}, "TEXT": {"dark": "#a5b4fc", "light": "#4f46e5"},
               "MARKUP": {"dark": "#fcd34d", "light": "#b45309"}, "DRAW": {"dark": "#6ee7b7", "light": "#047857"},
               "INSERT": {"dark": "#f9a8d4", "light": "#be185d"}, "PAGE EDIT": {"dark": "#fca5a5", "light": "#dc2626"}}

QSS = """
* {{ font-family: "Segoe UI", "Khmer UI"; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {bg}; }}
QWidget {{ color: {text}; }}
QMenuBar {{ background: {bg}; padding: 3px 6px; border: none; }}
QMenuBar::item {{ padding: 5px 11px; border-radius: 6px; background: transparent; }}
QMenuBar::item:selected {{ background: {hover}; }}
QMenu {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 30px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {accent}; color: white; }}
QMenu::item:disabled {{ color: {muted2}; }}
QMenu::icon {{ padding-left: 8px; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 5px 8px; }}

#Header, #PropBar {{ background: {surface}; border-bottom: 1px solid {border}; }}
#SidePanel {{ background: {surface}; border-right: 1px solid {border}; }}
#ToolDock {{ background: {surface}; border-right: 1px solid {border}; }}
#ToolScroll, #ToolPanel {{ background: transparent; border: none; }}
#Section {{ color: {muted}; font-size: 8pt; font-weight: 600; padding: 8px 14px 2px 14px; }}
#ToolPanel #Section {{ padding: 8px 2px 2px 2px; }}
#CreditBox {{ border-top: 1px solid {border}; }}
#Credit {{ color: {muted}; font-size: 8pt; }}
#PropTitle {{ font-weight: 600; font-size: 10.5pt; }}
#Muted, #Hint {{ color: {muted}; }}
#Pill {{ background: {surface2}; border: 1px solid {border}; border-radius: 10px; }}
#VSep {{ background: {border}; }}

QToolButton {{ background: transparent; border: none; border-radius: 7px; padding: 6px; }}
QToolButton:hover {{ background: {hover}; }}
QToolButton:pressed {{ background: {pressed}; }}
QToolButton:disabled {{ color: {muted2}; }}
QToolButton#ToolBtn {{ padding: 5px 1px 4px 1px; border-radius: 11px; color: {muted}; font-size: 8pt; }}
QToolButton#ToolBtn:hover {{ color: {text}; }}
QToolButton#ToolBtn:checked {{ color: white; font-weight: 600; background: qlineargradient(
    x1:0, y1:0, x2:1, y2:1, stop:0 {accent}, stop:1 {accent2}); }}
QToolButton#TextBtn {{ padding: 6px 12px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {input}; border: 1px solid {border}; border-radius: 7px; padding: 4px 8px;
    selection-background-color: {accent}; selection-color: white; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {accent}; }}
#Pill QLineEdit, #Pill QComboBox {{ background: transparent; border: none; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0; border: none; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: {surface}; border: 1px solid {border}; outline: 0;
    selection-background-color: {accent}; selection-color: white; padding: 4px; }}

QPushButton {{ background: {surface2}; border: 1px solid {border}; border-radius: 8px; padding: 7px 16px; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {pressed}; }}
QPushButton#Primary {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {accent}, stop:1 {accent2});
    color: white; border: none; font-weight: 600; padding: 11px 26px; }}
QPushButton#Primary:hover {{ background: {accent_hover}; }}
QPushButton#Big {{ padding: 11px 22px; }}
QPushButton#Recent {{ text-align: left; background: transparent; border: none; padding: 8px 12px; }}
QPushButton#Recent:hover {{ background: {hover}; }}

QTabWidget::pane {{ border: none; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{ background: transparent; padding: 9px 14px; color: {muted}; border: none;
    border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {accent}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {text}; }}

QListWidget, QTreeWidget, QTableWidget {{ background: {surface}; border: none; outline: 0; }}
QTreeWidget::item {{ padding: 5px 2px; border-radius: 6px; }}
QTreeWidget::item:selected, QTableWidget::item:selected {{ background: {accent}; color: white; }}
QTreeWidget::item:hover {{ background: {hover}; }}
QHeaderView::section {{ background: {surface2}; border: none; padding: 6px; color: {muted}; }}
QTableWidget {{ gridline-color: {border}; }}

QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle {{ background: {scroll}; border-radius: 4px; min-height: 32px; min-width: 32px; }}
QScrollBar::handle:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QStatusBar {{ background: {surface}; border-top: 1px solid {border}; color: {muted}; }}
QStatusBar QLabel {{ color: {muted}; padding: 0 10px; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: {border}; }}
QToolTip {{ background: #1f2228; color: #f1f3f4; border: 1px solid #3a3e46; padding: 6px 9px; border-radius: 6px; }}
QProgressDialog {{ background: {surface}; }}

#Welcome {{ background: {canvas}; }}
#Card {{ background: {surface}; border: 1px solid {border}; border-radius: 18px; }}
#Title {{ font-size: 22pt; font-weight: 700; }}
#Subtitle {{ color: {muted}; font-size: 11pt; }}
#DropZone {{ border: 2px dashed {border}; border-radius: 12px; color: {muted}; padding: 16px; }}
"""
if sys.platform == "darwin":
    # macOS has no Segoe UI / Khmer UI, and Qt there counts 72 points per inch instead of 96, so the
    # same pt size would look a quarter smaller than on Windows
    QSS = QSS.replace('"Segoe UI", "Khmer UI"', '"Helvetica Neue", "Khmer Sangam MN"')
    QSS = re.sub(r"(\d+(?:\.\d+)?)pt", lambda m: f"{float(m.group(1)) * 4 / 3:g}pt", QSS)


def stylesheet(t):
    return QSS.format(**t)


def palette(t):
    p = QPalette()
    c = lambda k: QColor(t[k])
    for role, key in ((QPalette.Window, "bg"), (QPalette.WindowText, "text"), (QPalette.Base, "input"),
                      (QPalette.AlternateBase, "surface2"), (QPalette.Text, "text"), (QPalette.Button, "surface2"),
                      (QPalette.ButtonText, "text"), (QPalette.Highlight, "accent"), (QPalette.ToolTipBase, "surface2"),
                      (QPalette.ToolTipText, "text"), (QPalette.PlaceholderText, "muted"), (QPalette.Mid, "border"),
                      (QPalette.Light, "surface2"), (QPalette.Dark, "border")):
        p.setColor(role, c(key))
    p.setColor(QPalette.HighlightedText, QColor("white"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c("muted2"))
    return p


# Line icons (24x24, stroke based – in the style of Lucide)
ICONS = {
    "open": '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/>',
    "print": '<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
    "undo": '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>',
    "redo": '<path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"/>',
    "left": '<path d="m15 18-6-6 6-6"/>', "right": '<path d="m9 18 6-6-6-6"/>',
    "up": '<path d="m18 15-6-6-6 6"/>', "down": '<path d="m6 9 6 6 6-6"/>',
    "zoomin": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6M8 11h6"/>',
    "zoomout": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/><path d="M8 11h6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    "fitw": '<path d="M21 12H3"/><path d="m7 8-4 4 4 4"/><path d="m17 8 4 4-4 4"/>',
    "fitp": '<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>',
    "rotl": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "rotr": '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
    "hand": '<path d="M18 11V6a2 2 0 0 0-4 0"/><path d="M14 10V4a2 2 0 0 0-4 0v2"/><path d="M10 10.5V6a2 2 0 0 0-4 0v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>',
    "select": '<path d="m4 4 7.07 17 2.51-7.39L21 11.07z"/>',
    "edittext": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "text": '<path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/>',
    "copytext": '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "highlight": '<path d="m9 11-6 6v3h9l3-3"/><path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/>',
    "underline": '<path d="M6 4v6a6 6 0 0 0 12 0V4"/><path d="M4 20h16"/>',
    "strikeout": '<path d="M16 4H9a3 3 0 0 0-2.83 4"/><path d="M14 12a4 4 0 0 1 0 8H6"/><path d="M4 12h16"/>',
    "pen": '<path d="M3 17c3-6 5-9 7-9s1 6 3 6 3-4 5-4 2 3 3 3"/>',
    "rect": '<rect x="3" y="5" width="18" height="14" rx="2"/>',
    "ellipse": '<circle cx="12" cy="12" r="9"/>',
    "line": '<path d="M5 19 19 5"/>',
    "arrow": '<path d="M7 17 17 7"/><path d="M7 7h10v10"/>',
    "note": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21"/>',
    "signature": '<path d="M3 16c2-2 3.5-6 5-6s0 5 2 5 3-4 4.5-4 1 3 2.5 3 2-1 3-2"/><path d="M3 21h18"/>',
    "whiteout": '<path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/><path d="M22 21H7"/><path d="m5 11 9 9"/>',
    "redact": '<rect x="3" y="9" width="18" height="6" rx="1" fill="currentColor"/><path d="M3 4h18"/><path d="M3 20h11"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "crop": '<path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/>',
    "new": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><path d="M14 2v6h6"/><path d="M12 18v-6"/><path d="M9 15h6"/>',
    "images": '<rect x="7" y="3" width="14" height="14" rx="2"/><path d="M3 7v12a2 2 0 0 0 2 2h12"/><circle cx="12" cy="8" r="1.5"/><path d="m21 13-3-3-6 6"/>',
    "merge": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "sidebar": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "stamp": '<path d="M5 22h14"/><path d="M19.27 13.73A2.5 2.5 0 0 0 17.5 13h-11A2.5 2.5 0 0 0 4 15.5V17a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-1.5c0-.66-.26-1.3-.73-1.77Z"/><path d="M14 13V8.5C14 7 15 7 15 5a3 3 0 0 0-6 0c0 2 1 2 1 3.5V13"/>',
    "hash": '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    "form": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    "split": '<path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M12 22v-8.3a4 4 0 0 0-1.17-2.83L3 3"/><path d="m15 9 6-6"/>',
    "export": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>', "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "update": '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
    "bookmark": '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
}

_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{}</svg>')


def _pixmap(name, color, size):
    r = QSvgRenderer(QByteArray(_SVG.format(ICONS[name]).replace("currentColor", color).encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p)
    p.end()
    return pm


def make_icon(name, t, on_color=None, tint=None):
    icon = QIcon()
    for s in (20, 40):
        icon.addPixmap(_pixmap(name, tint or t["text"], s), QIcon.Normal, QIcon.Off)
        icon.addPixmap(_pixmap(name, t["muted2"], s), QIcon.Disabled, QIcon.Off)
        if on_color:
            icon.addPixmap(_pixmap(name, on_color, s), QIcon.Normal, QIcon.On)
            icon.addPixmap(_pixmap(name, on_color, s), QIcon.Active, QIcon.On)
    return icon
