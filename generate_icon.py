"""Script tao app.ico cho AutoLabel Studio AI."""
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# SVG Logo tu app/theme/icons.py
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#7C5CFF" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
<rect width="24" height="24" fill="#0E0F17" rx="5"/>
<circle cx="12" cy="12" r="9.2" stroke="#7C5CFF" stroke-width="1.6"/>
<path d="M12 7.2l4.4 2.5v5l-4.4 2.5-4.4-2.5v-5z" stroke="#7C5CFF" stroke-width="1.6"/>
<circle cx="12" cy="12" r="1.8" fill="#7C5CFF"/>
</svg>"""

def build_ico(output_path: str = "app.ico") -> None:
    from PIL import Image

    renderer = QSvgRenderer(QByteArray(LOGO_SVG.encode("utf-8")))
    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for s in sizes:
        px = QPixmap(s, s)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        renderer.render(p, QRectF(0, 0, s, s))
        p.end()

        qimg = px.toImage().convertToFormat(QImage.Format_RGBA8888)
        width = qimg.width()
        height = qimg.height()
        ptr = qimg.constBits()
        # Doc bytes tu QImage sang PIL Image
        pil_img = Image.frombytes("RGBA", (width, height), bytes(ptr), "raw", "BGRA")
        images.append(pil_img)

    images[0].save(output_path, format="ICO", sizes=[(im.width, im.height) for im in images], append_images=images[1:])
    print(f"Da tao {output_path} thanh cong.")

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    build_ico("app.ico")
