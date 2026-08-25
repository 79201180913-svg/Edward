from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(slots=True)
class ApplicationSettings:
    storage_path: str


class ApplicationSettingsStore:
    """Persists global Edward application settings outside the selected data folder."""

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "Edward"
            config_path = base / "settings.json"
        self.config_path = Path(config_path)

    def _default_storage_path(self) -> str:
        return str((Path.cwd() / "data").resolve())

    def load(self) -> ApplicationSettings:
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            path = str(raw.get("storage_path", "")).strip()
            if path:
                return ApplicationSettings(storage_path=path)
        except (OSError, ValueError, TypeError):
            pass
        return ApplicationSettings(storage_path=self._default_storage_path())

    def save(self, settings: ApplicationSettings) -> None:
        path = Path(settings.storage_path).expanduser().resolve()
        if not path:
            raise ValueError("Storage path cannot be empty")
        path.mkdir(parents=True, exist_ok=True)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.config_path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(ApplicationSettings(str(path))), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.config_path)
