"""Initial IFC reader adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from geoifcassets.core.models import IfcModelSummary

FILE_SCHEMA_PATTERN = re.compile(
    r"FILE_SCHEMA\s*\(\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


class IfcReadStatus(StrEnum):
    """Possible results when reading an IFC source."""

    OK = "ok"
    EMPTY_SOURCE = "empty_source"
    NOT_LOCAL_FILE = "not_local_file"
    FILE_NOT_FOUND = "file_not_found"
    NOT_IFC_FILE = "not_ifc_file"
    READ_ERROR = "read_error"


@dataclass(frozen=True)
class IfcReadResult:
    """Result of reading minimal IFC metadata."""

    status: IfcReadStatus
    summary: IfcModelSummary | None = None
    error_message: str | None = None


class IfcReader:
    """Initial IFC reader boundary."""

    def can_open(self, source: str) -> bool:
        return bool(source.strip())

    def read_summary(self, source: str) -> IfcReadResult:
        clean_source = source.strip()
        if not clean_source:
            return IfcReadResult(status=IfcReadStatus.EMPTY_SOURCE)

        if _looks_like_url(clean_source):
            return IfcReadResult(status=IfcReadStatus.NOT_LOCAL_FILE)

        path = Path(clean_source)
        if not path.exists() or not path.is_file():
            return IfcReadResult(status=IfcReadStatus.FILE_NOT_FOUND)

        try:
            if not _looks_like_ifc_file(path):
                return IfcReadResult(status=IfcReadStatus.NOT_IFC_FILE)
            schema = _read_schema(path)
        except OSError as exc:
            return IfcReadResult(status=IfcReadStatus.READ_ERROR, error_message=str(exc))

        return IfcReadResult(
            status=IfcReadStatus.OK,
            summary=IfcModelSummary(source=str(path), schema=schema),
        )


def _looks_like_url(source: str) -> bool:
    return source.lower().startswith(("http://", "https://"))


def _looks_like_ifc_file(path: Path) -> bool:
    probe = path.read_text(encoding="utf-8", errors="ignore")[:4096].lstrip("\ufeff\r\n\t ")
    if not probe:
        return False
    if probe.lower().startswith(("<!doctype html", "<html")):
        return False
    return probe.startswith("ISO-10303-21") or "FILE_SCHEMA" in probe


def _read_schema(path: Path) -> str | None:
    with path.open("r", encoding="utf-8", errors="ignore") as ifc_file:
        for index, line in enumerate(ifc_file):
            match = FILE_SCHEMA_PATTERN.search(line)
            if match:
                return match.group(1)
            if index >= 1000:
                break
    return None
