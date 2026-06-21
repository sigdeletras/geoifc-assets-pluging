from __future__ import annotations

from geoifcassets.adapters.qgis.messages import QgisMessageService


class FakeMessageBar:
    def __init__(self) -> None:
        self.messages: list[tuple[object, ...]] = []

    def pushMessage(self, *args: object) -> None:  # noqa: N802
        self.messages.append(args)


class FakeIface:
    def __init__(self, message_bar: FakeMessageBar | None) -> None:
        self._message_bar = message_bar

    def messageBar(self) -> FakeMessageBar | None:  # noqa: N802
        return self._message_bar


def test_qgis_message_service_uses_positional_push_message_arguments() -> None:
    message_bar = FakeMessageBar()
    service = QgisMessageService(FakeIface(message_bar), "GeoIFC Assets")

    service.info("Panel opened")

    assert message_bar.messages == [("GeoIFC Assets", "Panel opened", "Info", 5)]


def test_qgis_message_service_ignores_missing_message_bar() -> None:
    service = QgisMessageService(FakeIface(None), "GeoIFC Assets")

    service.warning("No layer")
