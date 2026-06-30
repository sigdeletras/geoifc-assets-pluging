from __future__ import annotations

from geoifcassets.core.mapping import PropertyFieldMapping, build_attribute_update_plan, build_status_updates


def test_build_attribute_update_plan_for_existing_fields() -> None:
    plan = build_attribute_update_plan(
        {"Name": "Bridge", "Height": 12.5},
        [
            PropertyFieldMapping(property_id="Name", field_name="asset_name"),
            PropertyFieldMapping(property_id="Height", field_name="height_m"),
        ],
        ["asset_name", "height_m"],
    )

    assert plan.can_apply is True
    assert [(update.field_name, update.value) for update in plan.updates] == [
        ("asset_name", "Bridge"),
        ("height_m", 12.5),
    ]


def test_build_attribute_update_plan_reports_missing_properties() -> None:
    plan = build_attribute_update_plan(
        {"Name": "Bridge"},
        [PropertyFieldMapping(property_id="Height", field_name="height_m")],
        ["height_m"],
    )

    assert plan.can_apply is False
    assert plan.missing_property_ids == ("Height",)
    assert plan.updates == ()


def test_build_attribute_update_plan_reports_missing_fields_without_creation() -> None:
    plan = build_attribute_update_plan(
        {"Name": "Bridge"},
        [PropertyFieldMapping(property_id="Name", field_name="asset_name")],
        [],
    )

    assert plan.can_apply is False
    assert plan.missing_field_names == ("asset_name",)
    assert plan.field_names_to_create == ()


def test_build_attribute_update_plan_allows_new_fields_when_requested() -> None:
    plan = build_attribute_update_plan(
        {"Name": "Bridge"},
        [PropertyFieldMapping(property_id="Name", field_name="asset_name")],
        [],
        allow_new_fields=True,
    )

    assert plan.can_apply is True
    assert plan.missing_field_names == ()
    assert plan.field_names_to_create == ("asset_name",)
    assert plan.updates[0].value == "Bridge"


def test_build_status_updates_success_with_all_status_fields() -> None:
    updates = build_status_updates(
        ["ifc_path", "ifc_status", "ifc_updated_at", "ifc_error"],
        success=True,
        timestamp="2026-06-23T10:00:00Z",
    )
    by_field = {u.field_name: u.value for u in updates}

    assert by_field["ifc_status"] == "transferred"
    assert by_field["ifc_updated_at"] == "2026-06-23T10:00:00Z"
    assert by_field["ifc_error"] == ""


def test_build_status_updates_error_with_all_status_fields() -> None:
    updates = build_status_updates(
        ["ifc_status", "ifc_updated_at", "ifc_error"],
        success=False,
        timestamp="2026-06-23T10:00:00Z",
        error_message="Write failed",
    )
    by_field = {u.field_name: u.value for u in updates}

    assert by_field["ifc_status"] == "error"
    assert "ifc_updated_at" not in by_field
    assert by_field["ifc_error"] == "Write failed"


def test_build_status_updates_skips_absent_status_fields() -> None:
    updates = build_status_updates(
        ["ifc_path", "asset_name"],
        success=True,
        timestamp="2026-06-23T10:00:00Z",
    )

    assert updates == ()


def test_build_status_updates_partial_fields() -> None:
    updates = build_status_updates(
        ["ifc_status"],
        success=True,
        timestamp="2026-06-23T10:00:00Z",
    )
    by_field = {u.field_name: u.value for u in updates}

    assert by_field["ifc_status"] == "transferred"
    assert "ifc_updated_at" not in by_field
    assert "ifc_error" not in by_field
