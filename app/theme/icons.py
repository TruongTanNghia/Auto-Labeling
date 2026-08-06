"""Bo icon vector dung noi tuyen (khong can file rieng).

Icon duoc dinh nghia bang du lieu path SVG kieu 24x24 stroke, render qua
QSvgRenderer va cache lai theo (ten, mau, kich thuoc).
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.constants import COLORS

# Moi entry: danh sach cac phan tu SVG (path/circle/line/rect...)
ICONS: dict[str, str] = {
    "dashboard": '<rect x="3" y="3" width="7" height="8" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/>'
                 '<rect x="14" y="11" width="7" height="10" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/>',
    "import": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>',
    "film": '<rect x="2.5" y="4" width="19" height="16" rx="2"/><path d="M7 4v16M17 4v16M2.5 12h19M2.5 8h4.5M2.5 16h4.5M17 8h4.5M17 16h4.5"/>',
    "video": '<path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/>',
    "wand": '<path d="M15 4V2M15 16v-2M8 9h2M20 9h2M17.8 11.8L19 13M17.8 6.2L19 5M3 21l9-9M12.2 6.2L11 5"/>',
    "pen": '<path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>'
                '<path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "chart": '<path d="M3 3v18h18"/><rect x="7" y="11" width="3" height="6" rx="1"/>'
             '<rect x="12.5" y="7" width="3" height="10" rx="1"/><rect x="18" y="13" width="3" height="4" rx="1"/>',
    "pie": '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
    "cpu": '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/>'
           '<path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83'
                'l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4'
                'a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3'
                'a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06'
                'a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33'
                'l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09'
                'a1.65 1.65 0 0 0-1.51 1z"/>',
    "play": '<path d="M6 3.5l14 8.5-14 8.5z"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "folder_open": '<path d="M4 20h14a2 2 0 0 0 1.9-1.4L22 11H8.5a2 2 0 0 0-1.9 1.4L4 20z"/>'
                   '<path d="M4 20V6a2 2 0 0 1 2-2h4l2 3h5a2 2 0 0 1 2 2v2"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.6"/>'
             '<path d="M21 15l-5-5L5 21"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "check_circle": '<circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/>',
    "close": '<path d="M18 6L6 18M6 6l12 12"/>',
    "alert": '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>'
             '<path d="M12 9v4M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>',
    "undo": '<path d="M3 7v6h6"/><path d="M3.5 13a9 9 0 1 1 2.1 5.9"/>',
    "redo": '<path d="M21 7v6h-6"/><path d="M20.5 13a9 9 0 1 0-2.1 5.9"/>',
    "zoom_in": '<circle cx="10.5" cy="10.5" r="7"/><path d="M21 21l-5.6-5.6M10.5 7.5v6M7.5 10.5h6"/>',
    "zoom_out": '<circle cx="10.5" cy="10.5" r="7"/><path d="M21 21l-5.6-5.6M7.5 10.5h6"/>',
    "hand": '<path d="M18 11V6a1.5 1.5 0 0 0-3 0M15 11V4.5a1.5 1.5 0 0 0-3 0V11M12 11V5.5a1.5 1.5 0 0 0-3 0V13"/>'
            '<path d="M9 13V9.5a1.5 1.5 0 0 0-3 0V15a7 7 0 0 0 7 7h1a7 7 0 0 0 7-7v-4"/>',
    "polygon": '<path d="M12 2.5l9 6.5-3.5 10.5h-11L3 9z"/><circle cx="12" cy="2.5" r="1.6" fill="currentColor"/>'
               '<circle cx="21" cy="9" r="1.6" fill="currentColor"/><circle cx="3" cy="9" r="1.6" fill="currentColor"/>'
               '<circle cx="17.5" cy="19.5" r="1.6" fill="currentColor"/><circle cx="6.5" cy="19.5" r="1.6" fill="currentColor"/>',
    "brush": '<path d="M9.5 14.5L3 21s3.5.5 5-1 1-3.5 1-3.5"/>'
             '<path d="M11 12.5L18.8 4.7a2.4 2.4 0 0 1 3.4 3.4L14.4 16"/><path d="M9.5 14.5l4.9 1.5"/>',
    "eraser": '<path d="M20 20H8.5L3 14.5a2 2 0 0 1 0-2.8l8-8a2 2 0 0 1 2.8 0l6.5 6.5a2 2 0 0 1 0 2.8L14 20"/>'
              '<path d="M7 10l7 7"/>',
    "split": '<path d="M3 6h4l10 12h4M14 3l3 3-3 3M3 18h4"/>',
    "merge": '<path d="M8 3v6a4 4 0 0 0 4 4h9M18 10l3 3-3 3M8 21v-6"/>',
    "trash": '<path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/>'
             '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "chevron_left": '<path d="M15 18l-6-6 6-6"/>',
    "chevron_right": '<path d="M9 18l6-6-6-6"/>',
    "chevron_down": '<path d="M6 9l6 6 6-6"/>',
    "chevron_up": '<path d="M18 15l-6-6-6 6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
            '<path d="M17 21v-8H7v8M7 3v5h8"/>',
    "eye": '<path d="M1.5 12S5 5 12 5s10.5 7 10.5 7-3.5 7-10.5 7S1.5 12 1.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M9.9 5.2A9.9 9.9 0 0 1 12 5c7 0 10.5 7 10.5 7a17 17 0 0 1-3.4 4.3M6.6 6.6A17 17 0 0 0 1.5 12'
               'S5 19 12 19a9.7 9.7 0 0 0 4.5-1.1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="M2 2l20 20"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "layers": '<path d="M12 2.5l9.5 5-9.5 5-9.5-5z"/><path d="M2.5 16.5l9.5 5 9.5-5"/><path d="M2.5 12l9.5 5 9.5-5"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4" fill="currentColor"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>'
            '<path d="M8 13h8M8 17h5"/>',
    "sliders": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/>'
               '<path d="M1 14h6M9 8h6M17 16h6"/>',
    "maximize": '<path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M16 21h3a2 2 0 0 0 2-2v-3M8 21H5a2 2 0 0 1-2-2v-3"/>',
    "minimize": '<path d="M4 12h16"/>',
    "restore": '<rect x="3" y="8" width="13" height="13" rx="2"/><path d="M8 8V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-3"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>'
            '<rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "filter": '<path d="M22 3H2l8 9.5V19l4 2v-8.5z"/>',
    "sparkle": '<path d="M12 2l2.2 5.8L20 10l-5.8 2.2L12 18l-2.2-5.8L4 10l5.8-2.2z"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z"/>',
    "puzzle": '<path d="M19 11h-1a2 2 0 0 1 0-4h1V5a2 2 0 0 0-2-2h-2V2a2 2 0 0 0-4 0v1H8a2 2 0 0 0-2 2v2H5a2 2 0 0 0 0 4h1v2'
              'a2 2 0 0 0 2 2h2v1a2 2 0 0 0 4 0v-1h2a2 2 0 0 0 2-2z"/>',
    "keyboard": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M18 13h.01M9 13h6"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.2 9.2a2.8 2.8 0 0 1 5.5.8c0 1.9-2.7 2.5-2.7 2.5"/><path d="M12 17h.01"/>',
    "star": '<path d="M12 2.5l3 6.2 6.8 1-4.9 4.8 1.2 6.8L12 18.1 5.9 21.3l1.2-6.8L2.2 9.7l6.8-1z"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "crop": '<path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M2 6h14a2 2 0 0 1 2 2v14"/>',
    "move": '<path d="M12 2v20M2 12h20M9 5l3-3 3 3M9 19l3 3 3-3M5 9l-3 3 3 3M19 9l3 3-3 3"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "scissors": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4L8.1 15.9M14.5 14.5L20 20M8.1 8.1L12 12"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    "logo": '<circle cx="12" cy="12" r="9.2"/><path d="M12 7.2l4.4 2.5v5l-4.4 2.5-4.4-2.5v-5z"/>'
            '<circle cx="12" cy="12" r="1.8" fill="currentColor"/>',
}

_ALIASES = {
    "autolabel": "wand",
    "editor": "pen",
    "dataset": "database",
    "stats": "chart",
    "train": "cpu",
    "extract": "film",
}


def _svg(name: str, color: str, stroke: float) -> bytes:
    body = ICONS.get(_ALIASES.get(name, name))
    if body is None:
        body = ICONS["help"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    ).encode("utf-8")


@lru_cache(maxsize=1024)
def pixmap(name: str, color: str = None, size: int = 20, stroke: float = 1.9,
           dpr: float = 2.0) -> QPixmap:
    color = color or COLORS["text_dim"]
    renderer = QSvgRenderer(QByteArray(_svg(name, color, stroke)))
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing, True)
    # QPainter tren pixmap co devicePixelRatio nhan doi toa do san,
    # nen vung ve phai la kich thuoc LOGIC (size), khong phai size * dpr.
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return px


@lru_cache(maxsize=1024)
def icon(name: str, color: str = None, size: int = 20, stroke: float = 1.9) -> QIcon:
    """QIcon co san 2 trang thai mau: binh thuong / disabled."""
    color = color or COLORS["text_dim"]
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size, stroke), QIcon.Normal)
    ic.addPixmap(pixmap(name, COLORS["text_mute"], size, stroke), QIcon.Disabled)
    return ic


def colored(name: str, color: str, size: int = 20, stroke: float = 1.9) -> QIcon:
    return icon(name, color, size, stroke)


def tint(base: str, factor: float) -> str:
    """Lam sang (factor>1) hoac lam toi (factor<1) mot mau hex."""
    c = QColor(base)
    h, s, v, a = c.getHsv()
    v = max(0, min(255, int(v * factor)))
    c.setHsv(h, s, v, a)
    return c.name()


def with_alpha(base: str, alpha: float) -> QColor:
    c = QColor(base)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c
