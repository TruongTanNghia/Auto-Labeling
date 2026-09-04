"""Cua so chinh: title bar tuy bien, sidebar, stack cac trang, toast."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import (
    APP_NAME,
    APP_TAGLINE,
    COLORS,
    NAV_ITEMS,
    PAGE_AUTOLABEL,
    PAGE_DASHBOARD,
    PAGE_DATASET,
    PAGE_EDITOR,
    PAGE_EXTRACT,
    PAGE_IMPORT,
    PAGE_SETTINGS,
    PAGE_STATS,
    PAGE_TRAIN,
)
from app.controllers.app_controller import AppController
from app.i18n import tr
from app.theme import icons
from app.utils.logger import get_logger
from app.views.pages.autolabel_page import AutoLabelPage
from app.views.pages.dashboard_page import DashboardPage
from app.views.pages.dataset_page import DatasetPage
from app.views.pages.editor_page import EditorPage
from app.views.pages.extract_page import ExtractPage
from app.views.pages.import_page import ImportPage
from app.views.pages.settings_page import SettingsPage
from app.views.pages.stats_page import StatsPage
from app.views.pages.train_page import TrainPage
from app.views.sidebar import Sidebar
from app.views.widgets.common import ToastManager, label

log = get_logger(__name__)

RESIZE_MARGIN = 6


class TitleBar(QWidget):
    """Thanh tieu de tuy bien (frameless): keo de di chuyen, nut cua so."""

    def __init__(self, window: QMainWindow, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)
        self._window = window
        self._drag_pos: QPoint | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 8, 0)
        lay.setSpacing(9)

        logo = QLabel()
        logo.setPixmap(icons.pixmap("logo", COLORS["accent_hi"], 17, stroke=1.8))
        logo.setFixedSize(19, 19)
        lay.addWidget(logo)

        self.title = QLabel(f"{APP_NAME} — {APP_TAGLINE}")
        self.title.setObjectName("TitleBarTitle")
        lay.addWidget(self.title)
        lay.addStretch(1)

        self.project_label = label("", size=11.5, color=COLORS["text_mute"])
        lay.addWidget(self.project_label)
        lay.addSpacing(10)

        self.min_btn = self._btn("minimize", window.showMinimized)
        self.max_btn = self._btn("stop", self._toggle_max)
        self.close_btn = self._btn("close", window.close, close=True)
        for b in (self.min_btn, self.max_btn, self.close_btn):
            lay.addWidget(b)

    def _btn(self, icon_name: str, slot, close: bool = False) -> QPushButton:
        b = QPushButton()
        b.setObjectName("WinBtnClose" if close else "WinBtn")
        b.setIcon(icons.icon(icon_name, COLORS["text_dim"], 15))
        b.setIconSize(QSize(15, 15))
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def _toggle_max(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
            self.max_btn.setIcon(icons.icon("stop", COLORS["text_dim"], 15))
        else:
            self._window.showMaximized()
            self.max_btn.setIcon(icons.icon("restore", COLORS["text_dim"], 15))

    def set_project(self, text: str) -> None:
        self.project_label.setText(text)

    # ------------------------------------------------------------- keo tha --
    def mousePressEvent(self, ev) -> None:  # noqa: D102
        if ev.button() == Qt.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev) -> None:  # noqa: D102
        if self._drag_pos is None or not (ev.buttons() & Qt.LeftButton):
            return
        if self._window.isMaximized():
            # Bo maximize va giu con tro o dung vi tri tuong doi
            ratio = ev.globalPosition().x() / max(1, self._window.width())
            self._window.showNormal()
            self.max_btn.setIcon(icons.icon("stop", COLORS["text_dim"], 15))
            new_x = int(ev.globalPosition().x() - self._window.width() * ratio)
            self._drag_pos = QPoint(int(self._window.width() * ratio), 20)
            self._window.move(new_x, int(ev.globalPosition().y()) - 20)
            return
        self._window.move(ev.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, ev) -> None:  # noqa: D102
        self._drag_pos = None

    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: D102
        self._toggle_max()


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.ctrl = controller
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(1180, 720)
        self._resize_dir = None
        self._resize_start = None

        self._build_ui()
        self._install_shortcuts()
        self._connect()
        self.toasts = ToastManager(self)
        self.setAcceptDrops(True)
        self._restore_geometry()
        self.go_to_page(PAGE_DASHBOARD)
        QTimer.singleShot(200, self._refresh_device)
        QTimer.singleShot(120, self._auto_open_recent)

    # ================================================================= BUILD ==
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("RootFrame")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar(self)
        outer.addWidget(self.title_bar)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.pageRequested.connect(self.go_to_page)
        body_lay.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        body_lay.addWidget(self.stack, 1)
        outer.addWidget(body, 1)

        self.setCentralWidget(root)

        # --- cac trang ---
        self.pages: dict[str, object] = {
            PAGE_DASHBOARD: DashboardPage(self.ctrl),
            PAGE_IMPORT: ImportPage(self.ctrl),
            PAGE_EXTRACT: ExtractPage(self.ctrl),
            PAGE_AUTOLABEL: AutoLabelPage(self.ctrl),
            PAGE_EDITOR: EditorPage(self.ctrl),
            PAGE_DATASET: DatasetPage(self.ctrl),
            PAGE_STATS: StatsPage(self.ctrl),
            PAGE_TRAIN: TrainPage(self.ctrl),
            PAGE_SETTINGS: SettingsPage(self.ctrl),
        }
        self._order = list(self.pages)
        for page in self.pages.values():
            self.stack.addWidget(page)

        # --- lien ket giua cac trang ---
        self.pages[PAGE_DASHBOARD].navigate.connect(self.go_to_page)
        self.pages[PAGE_IMPORT].navigate.connect(self.go_to_page)
        self.pages[PAGE_IMPORT].videosSelected.connect(self.pages[PAGE_EXTRACT].set_videos)
        self.pages[PAGE_EXTRACT].navigate.connect(self.go_to_page)
        # Cat frame xong -> chuyen dung loat anh vua cat sang buoc gan nhan
        self.pages[PAGE_EXTRACT].batchReady.connect(
            lambda b: self.pages[PAGE_AUTOLABEL].set_batch(b, auto_start=True)
        )
        self.pages[PAGE_DATASET].navigate.connect(self.go_to_page)

        # goc duoi de keo doi kich thuoc
        self.grip = QSizeGrip(root)
        self.grip.setFixedSize(16, 16)

        self._current = ""

    def _install_shortcuts(self) -> None:
        def sc(seq, fn):
            s = QShortcut(QKeySequence(seq), self)
            s.activated.connect(fn)
            return s

        for i, (key, _t, _i) in enumerate(NAV_ITEMS):
            sc(f"Ctrl+{i + 1}", lambda k=key: self.go_to_page(k))
        sc("Ctrl+N", lambda: self.pages[PAGE_DASHBOARD].create_project_dialog())
        sc("Ctrl+O", lambda: self.pages[PAGE_DASHBOARD].open_project_dialog())
        sc("Ctrl+S", self._save)
        sc("F5", self._quick_autolabel)
        sc("F11", self._toggle_fullscreen)
        sc("Ctrl+Q", self.close)

    def _connect(self) -> None:
        self.ctrl.statusMessage.connect(self._on_status)
        self.ctrl.projectOpened.connect(self._on_project_opened)
        self.ctrl.projectClosed.connect(self._on_project_closed)
        self.ctrl.projectChanged.connect(self._update_project_label)
        self.ctrl.modelChanged.connect(self._refresh_device)

    # ============================================================ DIEU HUONG ==
    def go_to_page(self, key: str) -> None:
        if key not in self.pages:
            return
        if self._current == key:
            return
        old = self.pages.get(self._current)
        if old is not None and hasattr(old, "on_hide"):
            old.on_hide()

        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        self._current = key
        page.on_show()
        self._fade_in(page)

    def _fade_in(self, widget: QWidget) -> None:
        """Hieu ung mo dan khi doi trang.

        Phai dung animation cu trươc khi tao effect moi: setGraphicsEffect() huy
        effect dang gan, neu animation cu con chay se tro toi vung nho da giai
        phong (nguoi dung bam chuyen trang that nhanh).
        """
        self._stop_fade(widget)

        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(190)
        anim.setStartValue(0.4)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda w=widget: self._stop_fade(w))
        widget._fade_anim = anim
        anim.start()

    @staticmethod
    def _stop_fade(widget: QWidget) -> None:
        anim = getattr(widget, "_fade_anim", None)
        widget._fade_anim = None
        if anim is not None:
            try:
                anim.stop()
                anim.deleteLater()
            except RuntimeError:
                pass
        try:
            widget.setGraphicsEffect(None)
        except RuntimeError:
            pass

    # =============================================================== SU KIEN ==
    def _on_status(self, text: str, kind: str) -> None:
        self.toasts.show(text, kind)

    def _on_project_opened(self, repo) -> None:
        self._update_project_label()
        for key in (
            PAGE_DASHBOARD,
            PAGE_IMPORT,
            PAGE_EXTRACT,
            PAGE_AUTOLABEL,
            PAGE_EDITOR,
            PAGE_DATASET,
            PAGE_STATS,
            PAGE_TRAIN,
        ):
            page = self.pages.get(key)
            if page is not None:
                if hasattr(page, "on_project_changed"):
                    page.on_project_changed()
                if getattr(page, "_built", False):
                    page.refresh()

    def _on_project_closed(self) -> None:
        from app.i18n import tr

        self.title_bar.set_project("")
        self.sidebar.set_project(tr("main.no_project", "Chưa mở project"))
        for key, page in self.pages.items():
            if hasattr(page, "on_project_changed"):
                page.on_project_changed()
            if getattr(page, "_built", False):
                page.refresh()

    def _update_project_label(self) -> None:
        from app.i18n import tr

        repo = self.ctrl.repo
        if repo is None:
            self.title_bar.set_project("")
            self.sidebar.set_project(tr("main.no_project", "Chưa mở project"))
            return
        info = repo.refresh_stats()
        self.title_bar.set_project(
            f"{info.name}   ·   "
            + tr("main.images_count", "{count} ảnh", count=f"{info.n_images:,}")
        )
        self.sidebar.set_project(
            f"{info.name}\n"
            + tr(
                "main.labeled_images_count",
                "{labeled}/{total} ảnh đã gán nhãn",
                labeled=f"{info.n_labeled:,}",
                total=f"{info.n_images:,}",
            )
        )

    def _refresh_device(self) -> None:
        self.ctrl.refresh_device()
        d = self.ctrl.device
        text = f"{d['name']}" if d["cuda"] else "CPU mode"
        if d["cuda"]:
            text += f"  {d['total_gb']:.0f}GB"
        self.sidebar.set_device(text, d["cuda"])

    # ------------------------------------------------------- PROJECT ENTRY ==
    def start_new_project(self) -> None:
        """Mo hop thoai tao project - goi duoc tu bat ky trang nao."""
        dash = self.pages[PAGE_DASHBOARD]
        if not getattr(dash, "_built", False):
            dash.on_show()
        dash.create_project_dialog()

    def open_existing_project(self) -> None:
        dash = self.pages[PAGE_DASHBOARD]
        if not getattr(dash, "_built", False):
            dash.on_show()
        dash.open_project_dialog()

    def _auto_open_recent(self) -> None:
        """Mo lai project dung gan nhat de khong phai bat dau tu man hinh trong."""
        if self.ctrl.has_project or not cfg.get("general.reopen_last_project", True):
            return
        recent = self.ctrl.recent_projects()
        if recent:
            self.ctrl.open_project(recent[0]["path"])

    # --------------------------------------------------------- KEO THA FILE ==
    def dragEnterEvent(self, ev) -> None:  # noqa: D102
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev) -> None:  # noqa: D102
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev) -> None:  # noqa: D102
        """Tha file o BAT KY dau trong cua so cung nhan."""
        paths = [u.toLocalFile() for u in ev.mimeData().urls() if u.isLocalFile()]
        if not paths:
            return
        ev.acceptProposedAction()

        # Tha file project thi mo luon
        for p in paths:
            if p.lower().endswith(".alsdb"):
                self.ctrl.open_project(p)
                return

        page = self.pages[PAGE_IMPORT]
        if not getattr(page, "_built", False):
            page.on_show()
        self.go_to_page(PAGE_IMPORT)
        page.accept_paths(paths)

    def _save(self) -> None:
        page = self.pages.get(self._current)
        if hasattr(page, "save_current"):
            page.save_current(toast=True)
        else:
            self.ctrl.save_project()

    def _quick_autolabel(self) -> None:
        self.go_to_page(PAGE_AUTOLABEL)
        self.pages[PAGE_AUTOLABEL].start()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # =========================================================== FRAMELESS ====
    def resizeEvent(self, ev) -> None:  # noqa: D102
        super().resizeEvent(ev)
        if hasattr(self, "grip"):
            self.grip.move(
                self.width() - self.grip.width() - 2, self.height() - self.grip.height() - 2
            )
            self.grip.raise_()

    def mousePressEvent(self, ev) -> None:  # noqa: D102
        if ev.button() == Qt.LeftButton and not self.isMaximized():
            self._resize_dir = self._edge_at(ev.position().toPoint())
            if self._resize_dir:
                self._resize_start = (ev.globalPosition().toPoint(), self.geometry())
                ev.accept()
                return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev) -> None:  # noqa: D102
        if self._resize_dir and self._resize_start:
            self._do_resize(ev.globalPosition().toPoint())
            return
        if not self.isMaximized():
            self._update_cursor(self._edge_at(ev.position().toPoint()))
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:  # noqa: D102
        self._resize_dir = None
        self._resize_start = None
        self.unsetCursor()
        super().mouseReleaseEvent(ev)

    def _edge_at(self, pos: QPoint):
        m = RESIZE_MARGIN
        left = pos.x() <= m
        right = pos.x() >= self.width() - m
        top = pos.y() <= m
        bottom = pos.y() >= self.height() - m
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bottom and left:
            return "bl"
        if bottom and right:
            return "br"
        if left:
            return "l"
        if right:
            return "r"
        if top:
            return "t"
        if bottom:
            return "b"
        return None

    def _update_cursor(self, direction) -> None:
        cursors = {
            "l": Qt.SizeHorCursor,
            "r": Qt.SizeHorCursor,
            "t": Qt.SizeVerCursor,
            "b": Qt.SizeVerCursor,
            "tl": Qt.SizeFDiagCursor,
            "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor,
            "bl": Qt.SizeBDiagCursor,
        }
        if direction:
            self.setCursor(cursors[direction])
        else:
            self.unsetCursor()

    def _do_resize(self, global_pos: QPoint) -> None:
        start_pos, start_geo = self._resize_start
        delta = global_pos - start_pos
        geo = QRect(start_geo)
        d = self._resize_dir
        if "l" in d:
            geo.setLeft(start_geo.left() + delta.x())
        if "r" in d:
            geo.setRight(start_geo.right() + delta.x())
        if "t" in d:
            geo.setTop(start_geo.top() + delta.y())
        if "b" in d:
            geo.setBottom(start_geo.bottom() + delta.y())
        if geo.width() >= self.minimumWidth() and geo.height() >= self.minimumHeight():
            self.setGeometry(geo)

    # ============================================================= GEOMETRY ===
    def _restore_geometry(self) -> None:
        saved = cfg.get("general.window_geometry", "")
        if saved:
            try:
                x, y, w, h = (int(v) for v in saved.split(","))
                screen = QGuiApplication.primaryScreen().availableGeometry()
                if w > 400 and h > 300 and screen.intersects(QRect(x, y, w, h)):
                    self.setGeometry(x, y, w, h)
                    return
            except Exception:
                pass
        screen = QGuiApplication.primaryScreen().availableGeometry()
        w = min(1560, int(screen.width() * 0.9))
        h = min(940, int(screen.height() * 0.9))
        self.setGeometry(screen.center().x() - w // 2, screen.center().y() - h // 2, w, h)

    def _save_geometry(self) -> None:
        if self.isMaximized() or self.isFullScreen():
            return
        g = self.geometry()
        cfg.set("general.window_geometry", f"{g.x()},{g.y()},{g.width()},{g.height()}")

    # ================================================================= CLOSE ==
    def closeEvent(self, ev) -> None:  # noqa: D102
        if self.ctrl.busy:
            ret = QMessageBox.question(
                self,
                tr("common.confirm", "Xác nhận"),
                tr(
                    "main.tasks_running_confirm",
                    "Vẫn còn tác vụ nền đang chạy. Thoát và huỷ tác vụ?",
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                ev.ignore()
                return
        elif cfg.get("general.confirm_on_exit", True):
            ret = QMessageBox.question(
                self,
                tr("common.confirm", "Xác nhận"),
                tr(
                    "main.close_confirm",
                    tr("common.close", "Đóng") + " {app_name}?",
                    app_name=APP_NAME,
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if ret != QMessageBox.Yes:
                ev.ignore()
                return

        editor = self.pages.get(PAGE_EDITOR)
        if editor is not None and getattr(editor, "_dirty", False):
            try:
                editor.save_current()
            except Exception:
                pass
        try:
            self.pages[PAGE_DATASET].gallery.stop()
        except Exception:
            pass

        self._save_geometry()
        cfg.save()
        self.ctrl.shutdown()
        ev.accept()
