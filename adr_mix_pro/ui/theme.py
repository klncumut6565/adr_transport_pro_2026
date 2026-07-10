"""Tema (stylesheet) yükleme yardımcısı."""

from __future__ import annotations

from ..config import DEFAULT_DARK_STYLE


def load_dark_stylesheet() -> str:
    try:
        return DEFAULT_DARK_STYLE.read_text(encoding="utf-8")
    except OSError:
        return ""
