"""Pure mapping helpers for future IFC-to-GIS attribute transfer."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PropertyFieldMapping:
    """Maps one IFC property identifier to one GIS field name."""

    property_id: str
    field_name: str


@dataclass(frozen=True)
class AttributeUpdate:
    """One GIS attribute update prepared from an IFC property value."""

    field_name: str
    value: object


@dataclass(frozen=True)
class AttributeUpdatePlan:
    """Validated set of attribute updates to apply to a GIS feature."""

    updates: tuple[AttributeUpdate, ...]
    missing_property_ids: tuple[str, ...]
    missing_field_names: tuple[str, ...]
    field_names_to_create: tuple[str, ...]

    @property
    def can_apply(self) -> bool:
        return not self.missing_property_ids and not self.missing_field_names


def build_attribute_update_plan(
    property_values: Mapping[str, object],
    mappings: Iterable[PropertyFieldMapping],
    existing_field_names: Iterable[str],
    *,
    allow_new_fields: bool = False,
) -> AttributeUpdatePlan:
    """Build a validated GIS attribute update plan from selected IFC properties."""
    existing_fields = set(existing_field_names)
    updates: list[AttributeUpdate] = []
    missing_property_ids: list[str] = []
    missing_field_names: list[str] = []
    field_names_to_create: list[str] = []

    for mapping in mappings:
        if mapping.property_id not in property_values:
            missing_property_ids.append(mapping.property_id)
            continue

        field_exists = mapping.field_name in existing_fields
        if not field_exists and not allow_new_fields:
            missing_field_names.append(mapping.field_name)
            continue

        if not field_exists and mapping.field_name not in field_names_to_create:
            field_names_to_create.append(mapping.field_name)

        updates.append(
            AttributeUpdate(
                field_name=mapping.field_name,
                value=property_values[mapping.property_id],
            )
        )

    return AttributeUpdatePlan(
        updates=tuple(updates),
        missing_property_ids=tuple(missing_property_ids),
        missing_field_names=tuple(missing_field_names),
        field_names_to_create=tuple(field_names_to_create),
    )
