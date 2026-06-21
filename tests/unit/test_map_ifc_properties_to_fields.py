import pytest

from geoifcassets.application.dto.property_mapping import PropertyFieldMapping
from geoifcassets.application.use_cases.map_ifc_properties_to_fields import (
    MapIfcPropertiesToFieldsUseCase,
)
from geoifcassets.domain.value_objects.ifc_property import IfcProperty


def test_map_ifc_properties_to_fields_returns_validated_mappings():
    mapping = PropertyFieldMapping(
        source_property=IfcProperty(name="Reference", value="A-01", property_set="Pset"),
        target_field="ifc_ref",
        target_type="text",
    )

    result = MapIfcPropertiesToFieldsUseCase().execute([mapping])

    assert result == [mapping]


def test_map_ifc_properties_to_fields_rejects_duplicate_targets():
    mappings = [
        PropertyFieldMapping(IfcProperty(name="A", value=1), "same_field", "integer"),
        PropertyFieldMapping(IfcProperty(name="B", value=2), "same_field", "integer"),
    ]

    with pytest.raises(ValueError, match="Duplicate target fields"):
        MapIfcPropertiesToFieldsUseCase().execute(mappings)
