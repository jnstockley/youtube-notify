from __future__ import annotations

import asyncio

import pytest

from youtube_notify.youtube import youtube as youtube_module

pytestmark = pytest.mark.integration


def test_youtube_api_get_content_returns_mocked_content(
    integration_channel_id: str, mock_youtube_client: object
) -> None:
    content = asyncio.run(
        youtube_module.get_content(integration_channel_id, mock_youtube_client)
    )

    assert len(content) == 3
    assert {item.channel.id for item in content} == {integration_channel_id}
    assert {item.id for item in content} == {
        "api-video-1",
        "api-video-2",
        "api-video-3",
    }
    assert all(item.title for item in content)
    assert all(item.description is not None for item in content)
    assert all(item.thumbnail_url.scheme == "https" for item in content)
    assert all(item.published_at.tzinfo is not None for item in content)
