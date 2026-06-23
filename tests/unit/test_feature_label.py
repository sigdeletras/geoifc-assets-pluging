from __future__ import annotations

from geoifcassets.adapters.qgis.plugin import _feature_label


class FakeFeature:
    def __init__(self, attributes: dict[str, object], fid: int = 1) -> None:
        self._attributes = attributes
        self._fid = fid

    def __getitem__(self, field_name: str) -> object:
        if field_name not in self._attributes:
            raise KeyError(field_name)
        return self._attributes[field_name]

    def id(self) -> int:
        return self._fid


def test_returns_name_field_when_present() -> None:
    feature = FakeFeature({"name": "Building A"})
    assert _feature_label(feature) == "Building A"


def test_returns_nombre_field_when_name_absent() -> None:
    feature = FakeFeature({"nombre": "Edificio B"})
    assert _feature_label(feature) == "Edificio B"


def test_returns_ifc_filename_when_no_name_field() -> None:
    feature = FakeFeature({})
    assert _feature_label(feature, r"D:\models\edificio_A.ifc") == "edificio_A.ifc"


def test_returns_ifc_filename_from_url_when_no_name_field() -> None:
    feature = FakeFeature({})
    assert _feature_label(feature, "https://example.test/bridge_model.ifc") == "bridge_model.ifc"


def test_falls_back_to_feature_id_when_no_name_and_no_source() -> None:
    feature = FakeFeature({}, fid=7)
    label = _feature_label(feature)
    assert "7" in label


def test_ignores_empty_name_field_and_uses_ifc_filename() -> None:
    feature = FakeFeature({"name": ""})
    assert _feature_label(feature, "structure.ifc") == "structure.ifc"
