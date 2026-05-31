from unittest.mock import Mock

import youtube.auth.api_key as api_key_module


def test_authenticate_builds_youtube_client(monkeypatch) -> None:
    build = Mock(return_value={"client": "youtube"})
    monkeypatch.setattr(api_key_module.googleapiclient.discovery, "build", build)

    result = api_key_module.authenticate("api-key-123")

    assert result == {"client": "youtube"}
    build.assert_called_once_with("youtube", "v3", developerKey="api-key-123")
