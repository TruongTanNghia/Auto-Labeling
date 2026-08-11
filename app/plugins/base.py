"""He thong plugin cho auto annotation.

Moi plugin ke thua `AnnotatorPlugin` va cai dat `annotate()`. Plugin duoc nap tu:
  1. app/plugins/builtin/*.py   (di kem ung dung)
  2. <user_data>/plugins/*.py   (nguoi dung tu them)

Plugin co the:
  - sinh annotation moi tu prompt van ban (Grounding DINO, Florence-2)
  - tinh chinh annotation san co thanh mask sac net (SAM2, FastSAM)
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.inference import Detection
from app.i18n import tr
from app.utils.logger import get_logger
from app.utils.paths import plugins_dir

log = get_logger(__name__)


@dataclass
class PluginParam:
    key: str
    label: str
    type: str  # "int" | "float" | "bool" | "str" | "choice"
    default: Any
    description: str = ""
    min_value: float | int | None = None
    max_value: float | int | None = None
    options: list[str] = field(default_factory=list)

    @property
    def min(self) -> float | int | None:
        return self.min_value

    @property
    def max(self) -> float | int | None:
        return self.max_value


@dataclass
class PluginInfo:
    key: str = ""
    name: str = ""
    version: str = "1.0"
    author: str = ""
    description: str = ""
    requires: list[str] = field(default_factory=list)
    kind: str = "refine"  # "generate" | "refine"
    accepts_prompt: bool = False
    homepage: str = ""


@dataclass
class PluginContext:
    """Du lieu truyen vao plugin khi chay."""

    image_path: str = ""
    # ndarray BGR (co the None -> plugin tu doc file tu image_path).
    # Bat buoc phai co annotation, neu khong dataclass se coi day la bien lop
    # chu khong phai field va PluginContext(image=...) se bao loi.
    image: Any = None
    detections: list[Detection] = field(default_factory=list)
    class_names: list[str] = field(default_factory=list)
    prompt: str = ""
    device: str = "auto"
    confidence: float = 0.35
    extra: dict = field(default_factory=dict)


class AnnotatorPlugin(ABC):
    """Lop co so cho moi plugin annotation."""

    info: PluginInfo = PluginInfo()

    def __init__(self) -> None:
        self._loaded = False
        self._model = None

    # --------------------------------------------------------- vong doi ---
    def is_available(self) -> tuple[bool, str]:
        """Kiem tra thu vien phu thuoc da duoc cai chua."""
        missing = [m for m in self.info.requires if importlib.util.find_spec(m) is None]
        if missing:
            return False, tr("plugins.missing_packages", "Thieu goi: ") + ", ".join(missing)
        return True, tr("plugins.available", "Sẵn sàng")

    def load(self, ctx: PluginContext | None = None, log_cb=None) -> None:
        """Nap model. Mac dinh khong lam gi - plugin ghi de neu can."""
        self._loaded = True

    def unload(self) -> None:
        self._model = None
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------ nghiep vu --
    @abstractmethod
    def annotate(self, ctx: PluginContext) -> list[Detection]:
        """Tra ve danh sach Detection moi (hoac da tinh chinh)."""

    # -------------------------------------------------------------- cau hinh --
    def config_schema(self) -> list[PluginParam]:
        return []

    def default_config(self) -> dict:
        schema = self.config_schema()
        if schema:
            return {p.key: p.default for p in schema}
        return {}

    def configure(self, config: dict) -> None:
        self._config = dict(config or {})

    def config(self, key: str, default=None):
        if not hasattr(self, "_config"):
            self.configure(self.default_config())
        return getattr(self, "_config", {}).get(key, default)


# ================================================================ REGISTRY ===
class PluginRegistry:
    def __init__(self) -> None:
        self._classes: dict[str, type[AnnotatorPlugin]] = {}
        self._instances: dict[str, AnnotatorPlugin] = {}
        self._errors: dict[str, str] = {}
        self._discovered = False

    # -------------------------------------------------------------- khai bao --
    def register(self, cls: type[AnnotatorPlugin]) -> None:
        key = cls.info.key or cls.__name__.lower()
        self._classes[key] = cls

    def discover(self, force: bool = False) -> None:
        if self._discovered and not force:
            return
        self._discovered = True
        self._load_builtin()
        self._load_user()
        log.info("Plugin da nap: %s", ", ".join(self._classes) or "(khong co)")

    def _load_builtin(self) -> None:
        try:
            from app.plugins import builtin
        except Exception as exc:
            log.warning("Khong nap duoc plugin builtin: %s", exc)
            return
        for mod in pkgutil.iter_modules(builtin.__path__):
            name = f"app.plugins.builtin.{mod.name}"
            try:
                module = importlib.import_module(name)
                self._scan_module(module)
            except Exception as exc:
                self._errors[mod.name] = str(exc)
                log.warning("Loi nap plugin %s: %s", name, exc)

    def _load_user(self) -> None:
        folder = plugins_dir()
        for path in sorted(Path(folder).glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"als_plugin_{path.stem}", path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._scan_module(module)
            except Exception as exc:
                self._errors[path.stem] = str(exc)
                log.warning("Loi nap plugin nguoi dung %s: %s", path.name, exc)

    def _scan_module(self, module) -> None:
        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, AnnotatorPlugin)
                and attr is not AnnotatorPlugin
            ):
                self.register(attr)

    # ---------------------------------------------------------------- truy van --
    def keys(self) -> list[str]:
        self.discover()
        return sorted(self._classes)

    def infos(self) -> list[PluginInfo]:
        self.discover()
        return [cls.info for cls in self._classes.values()]

    def get(self, key: str) -> AnnotatorPlugin | None:
        self.discover()
        inst = self._instances.get(key)
        if inst is not None:
            self._apply_user_config(key, inst)
            return inst
        cls = self._classes.get(key)
        if cls is None:
            return None
        try:
            inst = cls()
            self._apply_user_config(key, inst)
        except Exception as exc:
            self._errors[key] = str(exc)
            log.error("Khong khoi tao duoc plugin %s: %s", key, exc)
            return None
        self._instances[key] = inst
        return inst

    def _apply_user_config(self, key: str, inst: AnnotatorPlugin) -> None:
        try:
            from app.config import cfg

            effective = dict(inst.default_config())
            user_cfg = cfg.get(f"plugins.config.{key}", {})
            if isinstance(user_cfg, dict):
                effective.update(user_cfg)
            inst.configure(effective)
        except Exception as exc:
            log.warning("Loi nap config cho plugin %s: %s", key, exc)

    def status(self, key: str) -> tuple[bool, str]:
        plugin = self.get(key)
        if plugin is None:
            return False, self._errors.get(key, "Khong tim thay plugin")
        try:
            return plugin.is_available()
        except Exception as exc:
            return False, str(exc)

    def errors(self) -> dict[str, str]:
        return dict(self._errors)

    def unload_all(self) -> None:
        for inst in self._instances.values():
            try:
                inst.unload()
            except Exception:
                pass
        self._instances.clear()


registry = PluginRegistry()
