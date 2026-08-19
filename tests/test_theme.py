"""Kiểm thử cho hệ thống chủ đề (Theme System)."""

from __future__ import annotations

from app.constants import COLORS, DARK_COLORS, LIGHT_COLORS
from app.theme.style import apply_theme, build_stylesheet, get_theme_colors, resolve_theme


def test_theme_resolution():
    assert resolve_theme("Dark") == "Dark"
    assert resolve_theme("Light") == "Light"
    assert resolve_theme("Sáng") == "Light"
    assert resolve_theme("Tối") == "Dark"


def test_theme_colors():
    dark_colors = get_theme_colors("Dark")
    light_colors = get_theme_colors("Light")

    assert dark_colors["bg"] == DARK_COLORS["bg"]
    assert light_colors["bg"] == LIGHT_COLORS["bg"]
    assert dark_colors["text"] != light_colors["text"]


def test_build_stylesheet(qapp):
    qss_dark = build_stylesheet(theme_name="Dark")
    qss_light = build_stylesheet(theme_name="Light")

    assert DARK_COLORS["bg"] in qss_dark
    assert LIGHT_COLORS["bg"] in qss_light
    assert qss_dark != qss_light


def test_apply_theme_switches_global_colors(qapp):
    apply_theme(None, "Dark")
    assert COLORS["bg"] == DARK_COLORS["bg"]

    apply_theme(None, "Light")
    assert COLORS["bg"] == LIGHT_COLORS["bg"]

    apply_theme(None, "Dark")
    assert COLORS["bg"] == DARK_COLORS["bg"]
