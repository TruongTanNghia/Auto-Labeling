"""Module i18n cho phep chuyen doi va tra cuu chuoi ban dich (Tieng Viet / Tieng Anh)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

I18N_DIR = Path(__file__).resolve().parent

LANG_VI = "vi"
LANG_EN = "en"

# Map cac ten hien thi sang ma ngon ngu
LANG_MAP = {
    "vi": LANG_VI,
    "en": LANG_EN,
    "Tiếng Việt": LANG_VI,
    "Tieng Viet": LANG_VI,
    "English": LANG_EN,
    "Tiếng Anh": LANG_EN,
}


class Translator:
    """Class quan ly va tra cuu chuoi da ngon ngu tu file JSON."""

    _instance: Translator | None = None

    def __init__(self) -> None:
        self._current_lang: str = LANG_VI
        self._translations: dict[str, dict[str, str]] = {}
        self._listeners: list[Callable[[str], None]] = []
        self.reload()

    @classmethod
    def instance(cls) -> Translator:
        if cls._instance is None:
            cls._instance = Translator()
        return cls._instance

    def reload(self) -> None:
        """Nap lai cac file json ban dich."""
        for lang in (LANG_VI, LANG_EN):
            file_path = I18N_DIR / f"{lang}.json"
            if file_path.exists():
                try:
                    with open(file_path, encoding="utf-8") as fh:
                        self._translations[lang] = json.load(fh)
                except Exception:
                    self._translations[lang] = {}
            else:
                self._translations[lang] = {}

    @property
    def current_language(self) -> str:
        return self._current_lang

    def set_language(self, lang_name_or_code: str) -> None:
        """Dat ngon ngu hien tai (vi / en hoặc Tiếng Việt / English)."""
        code = LANG_MAP.get(lang_name_or_code, LANG_VI)
        if self._current_lang != code:
            self._current_lang = code
            for callback in self._listeners:
                try:
                    callback(code)
                except Exception:
                    pass

    def add_listener(self, callback: Callable[[str], None]) -> None:
        """Dang ky ham nhan thong bao khi doi ngon ngu."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str], None]) -> None:
        """Huy dang ky ham nhan thong bao."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def translate(self, key: str, default: str | None = None, **kwargs: Any) -> str:
        """Tra cuu va dinh dang chuoi theo ngon ngu hien tai."""
        lang_dict = self._translations.get(self._current_lang, {})
        text = lang_dict.get(key)

        if text is None:
            # Thu fallback ve tieng Viet neu dang o tieng Anh mà khong co key
            if self._current_lang != LANG_VI:
                text = self._translations.get(LANG_VI, {}).get(key)
            if text is None:
                text = default if default is not None else key

        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError, IndexError):
                pass

        return text


_translator = Translator.instance()


def set_language(lang: str) -> None:
    _translator.set_language(lang)


def get_language() -> str:
    return _translator.current_language


def tr(key: str, default: str | None = None, **kwargs: Any) -> str:
    return _translator.translate(key, default=default, **kwargs)
