"""Runtime paths shared by local development and the Docker deployment."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    data_dir: Path
    timeline_db: Path
    chat_db: Path
    reports_dir: Path
    archive_dir: Path


def runtime_paths(project_root: Path | str | None = None) -> RuntimePaths:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
    data_dir = Path(os.environ.get("DO_DATA_DIR", root / "web"))
    reports_dir = Path(os.environ.get("DO_REPORTS_DIR", root / "reports"))
    archive_dir = Path(
        os.environ.get("DO_ARCHIVE_DIR", r"D:\坚果云同步\WS\Digital-Oracle-Reports")
    )
    return RuntimePaths(
        data_dir=data_dir,
        timeline_db=Path(os.environ.get("DO_TIMELINE_DB", data_dir / "timeline.db")),
        chat_db=Path(os.environ.get("DO_CHAT_DB", data_dir / "digital_oracle.db")),
        reports_dir=reports_dir,
        archive_dir=archive_dir,
    )
