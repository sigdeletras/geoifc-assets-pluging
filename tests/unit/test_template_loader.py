"""Unit tests for core/template_loader.py."""

from __future__ import annotations

import pytest

from geoifcassets.core.models import ClassMetricSpec, PropertyTemplate
from geoifcassets.core.template_loader import (
    group_order_key,
    load_template_from_dict,
)

# ── Minimal valid template dict ───────────────────────────────────────────────

_MINIMAL = {
    "template_name": "test_template",
    "extractor_version": "1.0.0",
    "description": "Test",
    "fields": [
        {"name": "file_name",    "enabled": True,  "group": "File",    "alias": "File name", "description": "IFC filename without path"},
        {"name": "project_name", "enabled": False,  "group": "Project", "alias": "Project name"},
    ],
    "class_metrics": [
        {"ifc_class": "IfcWall", "prefix": "wall", "metrics": ["count", "area"], "enabled": True},
    ],
}


def test_load_returns_property_template():
    t = load_template_from_dict(_MINIMAL)
    assert isinstance(t, PropertyTemplate)


def test_template_name_preserved():
    t = load_template_from_dict(_MINIMAL)
    assert t.template_name == "test_template"


def test_fields_count():
    t = load_template_from_dict(_MINIMAL)
    assert len(t.fields) == 2


def test_field_enabled_flag():
    t = load_template_from_dict(_MINIMAL)
    file_name_field = next(f for f in t.fields if f.name == "file_name")
    project_field = next(f for f in t.fields if f.name == "project_name")
    assert file_name_field.enabled is True
    assert project_field.enabled is False


def test_field_group_read_from_json():
    t = load_template_from_dict(_MINIMAL)
    file_name_field = next(f for f in t.fields if f.name == "file_name")
    assert file_name_field.group == "File"


def test_field_alias_read_from_json():
    t = load_template_from_dict(_MINIMAL)
    file_name_field = next(f for f in t.fields if f.name == "file_name")
    assert file_name_field.alias == "File name"


def test_field_description_read_from_json():
    t = load_template_from_dict(_MINIMAL)
    file_name_field = next(f for f in t.fields if f.name == "file_name")
    assert file_name_field.description == "IFC filename without path"


def test_custom_field_falls_back_to_custom_group():
    raw = {**_MINIMAL, "fields": [{"name": "my_custom_field", "enabled": True}]}
    t = load_template_from_dict(raw)
    assert t.fields[0].group == "Custom"
    assert t.fields[0].alias == "my_custom_field"


def test_field_group_and_alias_from_json():
    raw = {
        **_MINIMAL,
        "fields": [{"name": "file_name", "enabled": True, "group": "MyGroup", "alias": "My alias"}],
    }
    t = load_template_from_dict(raw)
    assert t.fields[0].group == "MyGroup"
    assert t.fields[0].alias == "My alias"


def test_class_metrics_parsed():
    t = load_template_from_dict(_MINIMAL)
    assert len(t.class_metrics) == 1
    spec = t.class_metrics[0]
    assert isinstance(spec, ClassMetricSpec)
    assert spec.ifc_class == "IfcWall"
    assert spec.prefix == "wall"
    assert "count" in spec.metrics
    assert "area" in spec.metrics
    assert spec.enabled is True


def test_class_metrics_invalid_metric_filtered():
    raw = {**_MINIMAL, "class_metrics": [
        {"ifc_class": "IfcWall", "prefix": "wall", "metrics": ["count", "INVALID"], "enabled": True}
    ]}
    t = load_template_from_dict(raw)
    assert "INVALID" not in t.class_metrics[0].metrics
    assert "count" in t.class_metrics[0].metrics


def test_class_metrics_prefix_defaults_to_class_lowercase():
    raw = {**_MINIMAL, "class_metrics": [
        {"ifc_class": "IfcDoor", "metrics": ["count"], "enabled": True}
    ]}
    t = load_template_from_dict(raw)
    assert t.class_metrics[0].prefix == "door"


def test_empty_fields_list():
    raw = {**_MINIMAL, "fields": []}
    t = load_template_from_dict(raw)
    assert t.fields == []


def test_empty_class_metrics_list():
    raw = {**_MINIMAL, "class_metrics": []}
    t = load_template_from_dict(raw)
    assert t.class_metrics == []


def test_malformed_field_entry_skipped():
    raw = {**_MINIMAL, "fields": [
        {"name": "file_name", "enabled": True},
        "this_is_not_a_dict",
        {"enabled": True},   # missing name
    ]}
    t = load_template_from_dict(raw)
    assert len(t.fields) == 1
    assert t.fields[0].name == "file_name"


def test_load_raises_on_non_dict_root():
    with pytest.raises(ValueError, match="JSON object"):
        load_template_from_dict([1, 2, 3])  # type: ignore[arg-type]


def test_group_order_key_known_group():
    assert group_order_key("File") < group_order_key("Project")
    assert group_order_key("Project") < group_order_key("Location")


def test_group_order_key_unknown_group_is_last():
    assert group_order_key("Custom") > group_order_key("Extraction")
    assert group_order_key("ZZZ_unknown") > group_order_key("File")


def test_ifc_core_catalog_loads():
    """The bundled ifc_core_catalog.json must load without errors."""
    from geoifcassets.core.template_loader import load_builtin_template  # noqa: PLC0415

    t = load_builtin_template("ifc_core_catalog")
    assert isinstance(t, PropertyTemplate)
    assert len(t.fields) > 0
    assert len(t.class_metrics) > 0


def test_ifc_core_catalog_loads_spanish():
    """Loading with locale='es' must override alias and group_label from i18n file."""
    from geoifcassets.core.template_loader import load_builtin_template  # noqa: PLC0415

    t = load_builtin_template("ifc_core_catalog", locale="es")
    file_name = next(f for f in t.fields if f.name == "file_name")
    assert file_name.alias == "Nombre del archivo"
    assert file_name.group_label == "Archivo"  # group "File" → "Archivo"


def test_ifc_core_catalog_group_label_spanish():
    """All groups must receive a translated group_label when locale='es'."""
    from geoifcassets.core.template_loader import load_builtin_template  # noqa: PLC0415

    t = load_builtin_template("ifc_core_catalog", locale="es")
    geometry_fields = [f for f in t.fields if f.group == "Geometry"]
    assert all(f.group_label == "Geometría" for f in geometry_fields)


def test_locale_fallback_to_english_when_file_missing():
    """Unknown locale must silently fall back to English values."""
    from geoifcassets.core.template_loader import load_builtin_template  # noqa: PLC0415

    t = load_builtin_template("ifc_core_catalog", locale="xx")
    file_name = next(f for f in t.fields if f.name == "file_name")
    assert file_name.alias == "File name"
    assert file_name.group_label == ""


def test_locale_en_no_i18n_lookup():
    """locale='en' must return base English values and empty group_label."""
    from geoifcassets.core.template_loader import load_builtin_template  # noqa: PLC0415

    t = load_builtin_template("ifc_core_catalog", locale="en")
    project_name = next(f for f in t.fields if f.name == "project_name")
    assert project_name.alias == "Project name"
    assert project_name.group_label == ""
