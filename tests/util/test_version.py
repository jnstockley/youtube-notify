from unittest.mock import Mock, mock_open

import youtube_notify.util.version as version_module


def test_get_version_reads_project_version(monkeypatch) -> None:
    monkeypatch.setattr(
        version_module.metadata,
        "version",
        Mock(side_effect=version_module.metadata.PackageNotFoundError),
    )
    monkeypatch.setattr("builtins.open", mock_open())
    monkeypatch.setattr(
        version_module.tomllib,
        "load",
        Mock(return_value={"project": {"version": "1.2.3"}}),
    )

    assert version_module.get_version() == "1.2.3"


def test_get_version_falls_back_to_unknown(monkeypatch) -> None:
    monkeypatch.setattr(
        version_module.metadata,
        "version",
        Mock(side_effect=version_module.metadata.PackageNotFoundError),
    )

    def fake_open(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("builtins.open", fake_open)

    assert version_module.get_version() == "unknown"
