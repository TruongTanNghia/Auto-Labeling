"""Lop co so cho moi tac vu nen - dam bao UI khong bao gio bi khoa."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QThread, Signal

from app.utils.logger import get_logger

log = get_logger(__name__)


class BaseWorker(QThread):
    """QThread co san tin hieu tien do / log / ket qua / loi va co che huy."""

    progress = Signal(int, int, str)  # current, total, message
    message = Signal(str)  # dong log
    finished_ok = Signal(object)  # ket qua
    failed = Signal(str)  # thong bao loi
    stage = Signal(str)  # ten giai doan hien tai
    cancelled_done = Signal()  # phat khi tac vu da dung an toan sau khi huy

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cancelled = False
        self.result = None

    # ---------------------------------------------------------------- API ---
    def cancel(self) -> None:
        self._cancelled = True
        self.message.emit("Dang huy tac vu ...")
        self.on_cancel()

    def on_cancel(self) -> None:
        """Lop con ghi de de dung cac doi tuong core dang chay."""

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def emit_progress(self, cur: int, total: int, msg: str = "") -> None:
        self.progress.emit(int(cur), int(max(1, total)), msg)

    def emit_log(self, msg: str) -> None:
        self.message.emit(str(msg))

    # ------------------------------------------------------------- QThread --
    def run(self) -> None:  # noqa: D102
        try:
            self.result = self.execute()
            if not self._cancelled:
                self.finished_ok.emit(self.result)
            else:
                self.cancelled_done.emit()
        except Exception as exc:  # pragma: no cover
            if not self._cancelled:
                log.exception("Worker %s loi", self.__class__.__name__)
                self.failed.emit(f"{type(exc).__name__}: {exc}")
                self.message.emit(traceback.format_exc(limit=4))
            else:
                log.info("Worker %s da dung an toan sau khi huy.", self.__class__.__name__)
                self.cancelled_done.emit()

    def execute(self):
        """Lop con cai dat phan viec thuc te."""
        raise NotImplementedError

    # ------------------------------------------------------------- tien ich --
    def stop_and_wait(self, timeout_ms: int = 5000) -> None:
        if self.isRunning():
            self.cancel()
            if not self.wait(timeout_ms):
                self.terminate()
                self.wait(1000)
