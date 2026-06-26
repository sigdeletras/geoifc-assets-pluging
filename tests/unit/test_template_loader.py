"""Unit tests for core/template_loader.py."""

from __future__ import annotations

import pytest

from geoifcassets.core.models import PropertyTemplate
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
        {"name": "project_name", "enabled": False, "group": "Project", "alias": "Project name"},
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



def test_empty_fields_list():
    raw = {**_MINIMAL, "fields": []}
    t = load_template_from_dict(raw)
    assert t.fields == []



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


def test_locale_es_from_inline_i18n_block():
    """locale='es' reads translations from the JSON's top-level i18n block."""
    raw = {
        **_MINIMAL,
        "i18n": {
            "es": {
                "groups": {"File": "Archivo", "Project": "Proyecto"},
                "fields": {
                    "file_name": {"alias": "Nombre del archivo", "description": "Desc ES"},
                },
            }
        },
    }
    t = load_template_from_dict(raw, locale="es")
    file_name = next(f for f in t.fields if f.name == "file_name")
    assert file_name.alias == "Nombre del archivo"
    assert file_name.description == "Desc ES"
    assert file_name.group_label == "Archivo"


def test_locale_group_label_applied_to_all_fields_in_group():
    """Every field in a group gets the same translated group_label."""
    raw = {
        **_MINIMAL,
        "fields": [
            {"name": "file_name",    "enabled": True, "group": "File"},
            {"name": "file_path",    "enabled": True, "group": "File"},
            {"name": "project_name", "enabled": True, "group": "Project"},
        ],
        "i18n": {"es": {"groups": {"File": "Archivo"}, "fields": {}}},
    }
    t = load_template_from_dict(raw, locale="es")
    file_fields = [f for f in t.fields if f.group == "File"]
    assert all(f.group_label == "Archivo" for f in file_fields)
    project_field = next(f for f in t.fields if f.group == "Project")
    assert project_field.group_label == ""  # no translation for Project


def test_locale_unknown_falls_back_silently():
    """Locale absent from i18n block returns English values, empty group_label."""
    raw = {
        **_MINIMAL,
        "i18n": {"es": {"groups": {"File": "Archivo"}, "fields": {}}},
    }
    t = load_template_from_dict(raw, locale="xx")
    file_name = next(f for f in t.fields if f.name == "file_name")
    assert file_name.alias == "File name"
    assert file_name.group_label == ""


def test_locale_en_skips_i18n_block():
    """locale='en' never applies i18n overrides even when block exists."""
    raw = {
        **_MINIMAL,
        "i18n": {"en": {"groups": {"File": "OVERRIDDEN"}, "fields": {
            "file_name": {"alias": "OVERRIDDEN"},
        }}},
    }
    t = load_template_from_dict(raw, locale="en")
    file_name = next(f for f in t.fields if f.name == "file_name")
    assert file_name.alias == "File name"
    assert file_name.group_label == ""


def test_ifc_core_catalog_loads_spanish():
    """Bundled catalog: locale='es' resolves Spanish alias and group_label."""
    from geoifcassets.core.template_loader import load_builtin_template  # noqa: PLC0415

    t = load_builtin_template("ifc_core_catalog", locale="es")
    file_name = next(f for f in t.fields if f.name == "file_name")
    assert file_name.alias == "Nombre del archivo"
    assert file_name.group_label == "Archivo"


def test_ifc_core_catalog_group_label_geometry_spanish():
    """Bundled catalog: all Geometry fields get translated group_label."""
    from geoifcassets.core.template_loader import load_builtin_template  # noqa: PLC0415

    t = load_builtin_template("ifc_core_catalog", locale="es")
    geometry_fields = [f for f in t.fields if f.group == "Geometry"]
    assert geometry_fields, "no Geometry fields found"
    assert all(f.group_label == "Geometria" for f in geometry_fields)


def test_locale_en_no_i18n_lookup():
    """locale='en' on bundled catalog returns English values, empty group_label."""
    from geoifcassets.core.template_loader import load_builtin_template  # noqa: PLC0415

    t = load_builtin_template("ifc_core_catalog", locale="en")
    project_name = next(f for f in t.fields if f.name == "project_name")
    assert project_name.alias == "Project name"
    assert project_name.group_label == ""
