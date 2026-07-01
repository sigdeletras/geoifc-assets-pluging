from __future__ import annotations

from geoifcassets.adapters.qgis.viewer import (
    classify_subprocess_stdout_line,
    iter_subprocess_stdout_lines,
)


def test_iter_subprocess_stdout_lines_splits_buffered_output() -> None:
    raw = b"QT_BINDING:PyQt5\nREADY:12345\n"
    assert iter_subprocess_stdout_lines(raw) == ["QT_BINDING:PyQt5", "READY:12345"]


def test_classify_subprocess_stdout_line_binding() -> None:
    kind, payload = classify_subprocess_stdout_line("QT_BINDING:PyQt5")
    assert kind == "binding"
    assert payload == "PyQt5"


def test_classify_subprocess_stdout_line_ready() -> None:
    kind, payload = classify_subprocess_stdout_line("READY:12345")
    assert kind == "ready"
    assert payload == "12345"


def test_classify_subprocess_stdout_line_binding_error() -> None:
    kind, payload = classify_subprocess_stdout_line("QT_BINDING_ERROR:PyQt5 unavailable")
    assert kind == "binding_error"
    assert payload == "PyQt5 unavailable"
