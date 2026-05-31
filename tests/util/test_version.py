from unittest.mock import Mock, mock_open

import util.version as version_module


def test_get_version_reads_project_version(monkeypatch) -> None:
    monkeypatch.setattr("builtins.open", mock_open())
    monkeypatch.setattr(
        version_module.tomllib,
        "load",
        Mock(return_value={"project": {"version": "1.2.3"}}),
    )

    assert version_module.get_version() == "1.2.3"


def test_get_version_falls_back_to_unknown(monkeypatch) -> None:
    def fake_open(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("builtins.open", fake_open)

    assert version_module.get_version() == "unknown"
