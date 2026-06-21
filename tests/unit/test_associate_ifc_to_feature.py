import pytest

from geoifcassets.application.use_cases.associate_ifc_to_feature import (
    AssociateIfcToFeatureUseCase,
)


def test_associate_ifc_to_feature_with_path():
    association = AssociateIfcToFeatureUseCase().execute(
        layer_id="assets",
        feature_id="1",
        ifc_path="model.ifc",
    )

    assert association.layer_id == "assets"
    assert association.feature_id == "1"
    assert association.ifc_path == "model.ifc"


def test_associate_ifc_to_feature_requires_ifc_reference():
    with pytest.raises(ValueError, match="ifc_path or ifc_url is required"):
        AssociateIfcToFeatureUseCase().execute(layer_id="assets", feature_id="1")
