"""Versioned machine-readable contract for future DO reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from typing import Any


DIRECTIONS = {"strong_bullish", "bullish", "neutral", "bearish", "strong_bearish", "insufficient"}
HORIZONS = {"short", "swing", "medium"}
BLOCK_RE = re.compile(r"```do-trend\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)


class ContractError(ValueError):
    """A structured trend block is missing or invalid."""


@dataclass(frozen=True)
class HorizonSnapshot:
    direction: str
    confidence: int
    summary: str
    probabilities: tuple[dict[str, Any], ...] = ()
    levels: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class SubjectSnapshot:
    subject_id: str
    subject_name: str
    instrument: str
    quote_currency: str
    quote_unit: str
    horizons: dict[str, HorizonSnapshot] = field(default_factory=dict)


@dataclass(frozen=True)
class TrendContract:
    schema_version: str
    analysis_id: str
    analysis_at: str
    data_as_of: str
    subjects: tuple[SubjectSnapshot, ...]


def _required(obj: dict, key: str, path: str):
    value = obj.get(key)
    if value is None or value == "":
        raise ContractError(f"{path}.{key} is required")
    return value


def _iso(value: str, path: str) -> str:
    try:
        datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{path} must be an ISO datetime") from exc
    return value


def extract_trend_block(report: str) -> TrendContract:
    blocks = BLOCK_RE.findall(report)
    if not blocks:
        raise ContractError("report must contain one do-trend block")
    if len(blocks) != 1:
        raise ContractError("report must contain exactly one do-trend block")
    try:
        raw = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid do-trend JSON: {exc.msg}") from exc
    if raw.get("schema_version") != "1.0":
        raise ContractError("schema_version must be 1.0")
    subjects_raw = _required(raw, "subjects", "root")
    if not isinstance(subjects_raw, list) or not subjects_raw:
        raise ContractError("root.subjects must be a non-empty array")
    subjects = []
    for index, item in enumerate(subjects_raw):
        path = f"subjects[{index}]"
        horizons_raw = item.get("horizons", {})
        if not isinstance(horizons_raw, dict):
            raise ContractError(f"{path}.horizons must be an object")
        unknown = set(horizons_raw) - HORIZONS
        if unknown:
            raise ContractError(f"{path}.horizons has unsupported keys: {sorted(unknown)}")
        horizons = {}
        for name, value in horizons_raw.items():
            hpath = f"{path}.horizons.{name}"
            direction = _required(value, "direction", hpath)
            if direction not in DIRECTIONS:
                raise ContractError(f"{hpath}.direction is invalid")
            confidence = _required(value, "confidence", hpath)
            if isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
                raise ContractError(f"{hpath}.confidence must be an integer from 0 to 100")
            horizons[name] = HorizonSnapshot(
                direction=direction,
                confidence=confidence,
                summary=str(_required(value, "summary", hpath)),
                probabilities=tuple(value.get("probabilities", ())),
                levels=tuple(value.get("levels", ())),
            )
        subjects.append(SubjectSnapshot(
            subject_id=str(_required(item, "subject_id", path)).strip().lower(),
            subject_name=str(_required(item, "subject_name", path)).strip(),
            instrument=str(_required(item, "instrument", path)).strip(),
            quote_currency=str(_required(item, "quote_currency", path)).strip().upper(),
            quote_unit=str(_required(item, "quote_unit", path)).strip(),
            horizons=horizons,
        ))
    return TrendContract(
        schema_version="1.0",
        analysis_id=str(_required(raw, "analysis_id", "root")),
        analysis_at=_iso(_required(raw, "analysis_at", "root"), "analysis_at"),
        data_as_of=_iso(_required(raw, "data_as_of", "root"), "data_as_of"),
        subjects=tuple(subjects),
    )
