"""Lop co so cho moi trang: header + vung noi dung (cuon duoc tuy chon)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from app.controllers.app_controller import AppController
from app.views.widgets.common import EmptyState, PageHeader


class BasePage(QWidget):
    """Khung chung cua mot trang trong QStackedWidget."""

    TITLE = ""
    SUBTITLE = ""
    ICON = ""
    NEEDS_PROJECT = True

    def __init__(self, controller: AppController, parent=None,
                 scrollable: bool = True) -> None:
        super().__init__(parent)
        self.ctrl = controller
        self._built = False
        self._scrollable = scrollable

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(15)

        self.header = PageHeader(self.TITLE, self.SUBTITLE, self.ICON)
        outer.addWidget(self.header)

        self.stack_host = QWidget()
        host_layout = QVBoxLayout(self.stack_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)
        outer.addWidget(self.stack_host, 1)

        # Vung noi dung that su
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(15)

        if scrollable:
            self.scroll = QScrollArea()
            self.scroll.setWidgetResizable(True)
            self.scroll.setFrameShape(QScrollArea.NoFrame)
            self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.scroll.setWidget(self.content)
            host_layout.addWidget(self.scroll)
        else:
            host_layout.addWidget(self.content)

        # Man hinh yeu cau mo project - PHAI co loi thoat that su
        from app.i18n import tr
        self.no_project = EmptyState(
            "folder_open", tr("main.no_project", "Chưa mở project nào"),
            tr("page.no_project_desc", "Mọi thao tác đều nằm trong một project. Hãy tạo project mới hoặc mở project có sẵn để bắt đầu."),
            action_text=tr("main.new_project", "Tạo project mới"),
            action2_text=tr("main.open_project", "Mở project có sẵn"),
        )
        self.no_project.action.connect(self._request_new_project)
        self.no_project.action2.connect(self._request_open_project)
        self.no_project.hide()
        host_layout.addWidget(self.no_project)

        self.ctrl.projectOpened.connect(lambda *_: self._on_project_state())
        self.ctrl.projectClosed.connect(self._on_project_state)

    # ------------------------------------------------------------ lifecycle --
    def build(self) -> None:
        """Lop con ghi de de dung giao dien (goi lazy o lan hien dau tien)."""

    def refresh(self) -> None:
        """Duoc goi moi khi trang duoc hien thi hoac du lieu thay doi."""

    def ensure_built(self) -> None:
        """Dựng giao diện ngay nếu chưa dựng.

        Các trang dựng lazy ở lần mở đầu tiên. Bất kỳ hàm công khai nào có thể
        bị gọi TỪ TRANG KHÁC (nhận dữ liệu, nhận file kéo thả…) đều phải gọi
        hàm này trước khi đụng tới widget, nếu không sẽ lỗi AttributeError.
        """
        if not self._built:
            self.build()
            self._built = True

    def on_show(self) -> None:
        self.ensure_built()
        self._on_project_state()
        if not self.NEEDS_PROJECT or self.ctrl.has_project:
            self.refresh()

    def on_hide(self) -> None:
        pass

    # -------------------------------------------------------------- helper --
    def ensure_project(self) -> bool:
        """Chưa có project thì mời tạo ngay, thay vì im lặng không làm gì."""
        if self.ctrl.has_project:
            return True
        from PySide6.QtWidgets import QMessageBox
        from app.i18n import tr
        ret = QMessageBox.question(
            self, tr("main.no_project", "Chưa có project"),
            tr("page.create_project_prompt", "Mọi dữ liệu đều nằm trong một project. Tạo project mới ngay bây giờ?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if ret != QMessageBox.Yes:
            return False
        self._request_new_project()
        return self.ctrl.has_project

    def _request_new_project(self) -> None:
        win = self.window()
        if hasattr(win, "start_new_project"):
            win.start_new_project()

    def _request_open_project(self) -> None:
        win = self.window()
        if hasattr(win, "open_existing_project"):
            win.open_existing_project()

    def _on_project_state(self) -> None:
        need = self.NEEDS_PROJECT and not self.ctrl.has_project
        if self._scrollable:
            self.scroll.setVisible(not need)
        else:
            self.content.setVisible(not need)
        self.no_project.setVisible(need)

    def add(self, widget_or_layout, stretch: int = 0) -> None:
        if isinstance(widget_or_layout, QWidget):
            self.content_layout.addWidget(widget_or_layout, stretch)
        else:
            self.content_layout.addLayout(widget_or_layout, stretch)

    def add_stretch(self, n: int = 1) -> None:
        self.content_layout.addStretch(n)

    def toast(self, text: str, kind: str = "info") -> None:
        self.ctrl.statusMessage.emit(text, kind)

    @property
    def repo(self):
        return self.ctrl.repo
