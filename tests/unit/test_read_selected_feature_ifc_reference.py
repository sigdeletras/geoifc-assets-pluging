from geoifcassets.application.dto.selected_feature import SelectedFeatureIfcReference
from geoifcassets.application.use_cases.read_selected_feature_ifc_reference import (
    ReadSelectedFeatureIfcReferenceUseCase,
)


class FakeFeatureReader:
    def read_selected_feature(self):
        return SelectedFeatureIfcReference(
            layer_id="layer-1",
            layer_name="Assets",
            feature_id="10",
            ifc_path="model.ifc",
        )


def test_read_selected_feature_ifc_reference_returns_reader_result():
    result = ReadSelectedFeatureIfcReferenceUseCase(FakeFeatureReader()).execute()

    assert result.layer_id == "layer-1"
    assert result.layer_name == "Assets"
    assert result.feature_id == "10"
    assert result.ifc_path == "model.ifc"
    assert result.has_ifc_reference is True
