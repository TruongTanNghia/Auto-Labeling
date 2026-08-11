"""AutoLabel Studio AI - diem khoi chay ung dung."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# Cho phep chay truc tiep `python main.py` tu bat ky thu muc nao
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("YOLO_VERBOSE", "False")
# QUAN TRONG: cam Ultralytics tu dong `pip install` de nang cap goi.
# Neu bat, no co the thay the ban torch CUDA cua ban bang ban CPU tu PyPI.
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from app.config import cfg  # noqa: E402
from app.constants import APP_NAME, APP_VERSION, COLORS, ORG_NAME  # noqa: E402
from app.controllers.app_controller import AppController  # noqa: E402
from app.i18n import tr  # noqa: E402
from app.theme import icons  # noqa: E402
from app.theme.style import apply_theme  # noqa: E402
from app.utils.logger import get_logger, setup_logging  # noqa: E402


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    """Khong de ung dung tat im lang khi co loi khong bat duoc."""
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    get_logger("crash").error("Loi khong bat duoc:\n%s", text)
    try:
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(tr("common.error_occurred", "Đã xảy ra lỗi"))
        box.setText(f"{exc_type.__name__}: {exc_value}")
        box.setDetailedText(text)
        box.exec()
    except Exception:
        print(text, file=sys.stderr)


def main() -> int:
    setup_logging()
    log = get_logger("main")
    log.info("Khoi dong %s v%s", APP_NAME, APP_VERSION)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)

    apply_theme(app, cfg.get("general.theme", "Dark"), cfg.get("general.accent"))

    def _on_color_scheme_changed():
        if cfg.get("general.theme", "Dark") in ("System", "Theo hệ thống", "system"):
            apply_theme(app)

    app.styleHints().colorSchemeChanged.connect(_on_color_scheme_changed)

    app.setWindowIcon(QIcon(icons.pixmap("logo", COLORS["accent_hi"], 64, stroke=1.6)))

    font = QFont("Segoe UI Variable Display")
    if not font.exactMatch():
        font = QFont("Segoe UI")
    font.setPointSize(9)
    app.setFont(font)

    sys.excepthook = _excepthook

    # Ep Ultralytics dung thu muc weights rieng cua ung dung
    try:
        from app.core.inference import configure_ultralytics

        configure_ultralytics()
    except Exception as exc:
        log.debug("configure_ultralytics: %s", exc)

    # Nap plugin o nen de khong lam cham khoi dong
    try:
        from app.plugins.base import registry

        registry.discover()
    except Exception as exc:
        log.warning("Khong nap duoc plugin: %s", exc)

    controller = AppController()

    from app.views.main_window import MainWindow

    window = MainWindow(controller)
    window.show()

    # Mo lai project gan nhat neu duong dan truyen vao dong lenh
    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        controller.open_project(sys.argv[1])

    # Dung cho kiem thu tu dong: tu dong dong sau N mili giay
    autoclose = os.environ.get("ALS_AUTOCLOSE_MS")
    if autoclose:
        from PySide6.QtCore import QTimer

        cfg.set("general.confirm_on_exit", False)
        QTimer.singleShot(int(autoclose), app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
