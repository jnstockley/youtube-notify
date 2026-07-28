from __future__ import annotations

import asyncio

import httpx
import pytest

from youtube_notify.rss import rss as rss_module

pytestmark = pytest.mark.integration


def test_rss_get_content_returns_mocked_content(
    integration_channel_id: str,
) -> None:
    async def get_content() -> set:
        return await rss_module.get_content(integration_channel_id, httpx.AsyncClient())

    content = asyncio.run(get_content())

    assert len(content) == 3
    assert {item.channel.id for item in content} == {integration_channel_id}
    assert {item.id for item in content} == {
        "rss-video-1",
        "rss-video-2",
        "rss-video-3",
    }
    assert all(item.title for item in content)
    assert all(item.description is not None for item in content)
    assert all(item.thumbnail_url.scheme == "https" for item in content)
    assert all(item.published_at.tzinfo is not None for item in content)
