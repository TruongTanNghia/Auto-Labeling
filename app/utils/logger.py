"""Logging tap trung: ghi file xoay vong + phat tin hieu Qt cho UI."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QObject, Signal

from app.utils.paths import log_dir

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"


class LogBridge(QObject):
    """Cau noi giua logging cua Python va UI (thread-safe qua Qt signal)."""

    message = Signal(str, str)  # level, text


bridge = LogBridge()


class _QtHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            bridge.message.emit(record.levelname, self.format(record))
        except Exception:  # pragma: no cover - khong bao gio duoc lam sap app
            pass


_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    file_handler = RotatingFileHandler(
        log_dir() / "autolabel.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
    stream.setLevel(level)
    root.addHandler(stream)

    qt_handler = _QtHandler()
    qt_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", _DATE_FORMAT))
    qt_handler.setLevel(logging.INFO)
    root.addHandler(qt_handler)

    # Bot nhieu tu thu vien ngoai
    for noisy in ("PIL", "matplotlib", "urllib3", "git"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
