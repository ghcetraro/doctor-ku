from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.models import NodeCheckResult

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path(os.getenv("STATE_PATH", "/data/state.json"))


class PersistedState(BaseModel):
    failure_counts: dict[str, int] = Field(default_factory=dict)
    last_results: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    last_run_at: dict[str, str] = Field(default_factory=dict)


def load_state(path: Path | None = None) -> PersistedState:
    state_path = path or DEFAULT_STATE_PATH
    if not state_path.is_file():
        return PersistedState()
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        return PersistedState.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("estado no legible en %s: %s", state_path, exc)
        return PersistedState()


def save_state(state: PersistedState, path: Path | None = None) -> None:
    state_path = path or DEFAULT_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = state_path.with_suffix(".tmp")
    temp_path.write_text(
        state.model_dump_json(indent=2),
        encoding="utf-8",
    )
    temp_path.replace(state_path)
    logger.info("estado guardado en %s", state_path)


def serialize_results(results: list[NodeCheckResult]) -> list[dict[str, Any]]:
    return [item.model_dump() for item in results]


def now_iso(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).isoformat()
