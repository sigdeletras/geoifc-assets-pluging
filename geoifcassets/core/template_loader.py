"""Load and validate property extraction templates from JSON files.

Templates follow the schema defined in ``geoifcassets/templates/``.  Each
template contains a ``fields`` list (scalar IFC properties) and a
``class_metrics`` list (per-class count/length/area/volume).

Translations are stored in separate files under ``templates/i18n/``
named ``{template_stem}_{locale}.json``.  The base JSON is always English.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from geoifcassets.core.models import PropertyTemplate, TemplateField

_log = logging.getLogger("geoifcassets")

BUILTIN_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Ordered group list used to sort fields in the UI (canonical English keys)
_GROUP_ORDER: list[str] = [
    "File",
    "IFC Header",
    "Project",
    "Location",
    "Domain",
    "Spatial Structure",
    "Model Statistics",
    "Geometry",
    "Materials",
    "Asset",
    "Classification",
    "BIM Quality",
    "Indicators",
    "Extraction",
    "Custom",
]


def load_builtin_template(name: str, locale: str = "en") -> PropertyTemplate:
    """Load a built-in template by filename stem.

    When ``locale`` is not "en" and a matching ``i18n/{name}_{locale}.json``
    exists, field aliases, descriptions, and group labels are overridden from
    that file.  Falls back to English when the locale file is absent.
    """
    path = BUILTIN_TEMPLATES_DIR / f"{name}.json"
    return load_template_from_path(path, locale=locale)


def load_template_from_path(path: Path | str, locale: str = "en") -> PropertyTemplate:
    """Load and validate a template JSON from any file path."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load template from {path}: {exc}") from exc
    return _parse_template(raw, source=str(path), template_stem=path.stem, locale=locale)


def load_template_from_dict(raw: dict[str, Any], locale: str = "en") -> PropertyTemplate:
    """Parse a template from an already-decoded dict (e.g. from a test fixture)."""
    return _parse_template(raw, source="<dict>", template_stem="", locale=locale)


def list_builtin_templates() -> list[str]:
    """Return stem names of all built-in JSON templates."""
    if not BUILTIN_TEMPLATES_DIR.exists():
        return []
    return sorted(p.stem for p in BUILTIN_TEMPLATES_DIR.glob("*.json"))


def group_order_key(group: str) -> int:
    """Return a sort key for a group name so groups appear in canonical order."""
    try:
        return _GROUP_ORDER.index(group)
    except ValueError:
        return len(_GROUP_ORDER)


# ── Internal ─────────────────────────────────────────────────────────────────


def _load_i18n(raw: dict[str, Any], locale: str) -> tuple[dict, dict]:
    """Extract field and group translations from the template dict's ``i18n`` block.

    Returns ``(fields_dict, groups_dict)`` — both empty when the locale is absent.
    ``fields_dict`` is keyed by field name; ``groups_dict`` by English group key.
    """
    if not locale or locale == "en":
        return {}, {}
    loc = raw.get("i18n", {}).get(locale, {})
    return loc.get("fields", {}), loc.get("groups", {})


def _parse_template(
    raw: dict[str, Any],
    source: str,
    template_stem: str = "",
    locale: str = "en",
) -> PropertyTemplate:
    if not isinstance(raw, dict):
        raise ValueError(f"Template {source}: expected a JSON object at root")

    i18n_fields, i18n_groups = _load_i18n(raw, locale)
    fields = _parse_fields(raw.get("fields", []), source, i18n_fields, i18n_groups)

    return PropertyTemplate(
        template_name=str(raw.get("template_name", source)),
        extractor_version=str(raw.get("extractor_version", "1.0.0")),
        description=str(raw.get("description", "")),
        fields=fields,
    )


def _parse_fields(
    raw_fields: Any,
    source: str,
    i18n_fields: dict,
    i18n_groups: dict,
) -> list[TemplateField]:
    if not isinstance(raw_fields, list):
        _log.warning("template_loader: %s — 'fields' is not a list, ignored", source)
        return []

    result: list[TemplateField] = []
    for entry in raw_fields:
        if not isinstance(entry, dict) or "name" not in entry:
            _log.debug("template_loader: skipping malformed field entry: %s", entry)
            continue
        name = str(entry["name"])
        enabled = bool(entry.get("enabled", True))
        group = str(entry.get("group", "Custom"))
        alias = str(entry.get("alias", name))
        description = str(entry.get("description", ""))
        ifc_source = str(entry.get("ifc_source") or "")
        aggregate = str(entry.get("aggregate", "count"))
        source_type = str(entry.get("source_type", "computed"))
        computed = bool(entry.get("computed", False))

        # Apply locale overrides from external i18n dicts
        loc_field = i18n_fields.get(name, {})
        if loc_field:
            alias = str(loc_field.get("alias") or alias)
            description = str(loc_field.get("description") or description)
        group_label = str(i18n_groups.get(group, ""))

        result.append(TemplateField(
            name=name,
            enabled=enabled,
            group=group,
            alias=alias,
            description=description,
            ifc_source=ifc_source,
            aggregate=aggregate,
            group_label=group_label,
            source_type=source_type,
            computed=computed,
        ))
    return result


