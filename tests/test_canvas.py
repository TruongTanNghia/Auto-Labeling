"""Kiem thu AnnotationCanvas (polygon, brush, eraser, split, merge, undo/redo)."""
from __future__ import annotations

from PySide6.QtCore import QPointF
from app.models.repository import ProjectRepository
from app.views.widgets.canvas import (
    TOOL_BRUSH,
    TOOL_ERASER,
    TOOL_POLYGON,
    TOOL_SPLIT,
    AnnotationCanvas,
)


def test_canvas_operations(qapp, repo: ProjectRepository):
    cv = AnnotationCanvas()
    cv.resize(800, 600)
    im = repo.images()[0]
    assert cv.load_image(im.path, repo.annotations(im.id)) is True

    cv.set_classes(repo.classes())
    cv.active_class_id = repo.classes()[0].id

    # Add polygon
    n0 = len(cv.annotations)
    cv.set_tool(TOOL_POLYGON)
    cv._draft = [QPointF(10, 10), QPointF(90, 12), QPointF(80, 95), QPointF(12, 88)]
    cv._finish_polygon()
    assert len(cv.annotations) == n0 + 1

    # Brush expand
    cv.selected = {len(cv.annotations) - 1}
    cv.set_tool(TOOL_BRUSH)
    cv.brush_size = 14
    before = cv.annotations[-1].area
    cv._brush_path = [QPointF(85, 50), QPointF(130, 50), QPointF(150, 60)]
    cv._apply_brush()
    assert cv.annotations[-1].area > before

    # Eraser shrink
    cv.set_tool(TOOL_ERASER)
    before = cv.annotations[-1].area
    cv._brush_path = [QPointF(30, 30), QPointF(50, 50)]
    cv._apply_brush()
    assert cv.annotations[-1].area < before

    # Split
    cv.selected = {len(cv.annotations) - 1}
    cv.set_tool(TOOL_SPLIT)
    n_before = len(cv.annotations)
    cv._split_line = [QPointF(0, 55), QPointF(300, 55)]
    cv._apply_split()
    assert len(cv.annotations) >= n_before

    # Merge and Undo/Redo
    cv.selected = {0, 1}
    cv.merge_selected()
    n = len(cv.annotations)
    cv.undo()
    cv.redo()
    assert len(cv.annotations) == n

    # Fit and zoom
    cv.fit_to_view()
    cv.zoom_by(1.4)
    assert cv.viewport_image_rect().width() > 0
