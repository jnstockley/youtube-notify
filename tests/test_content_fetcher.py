import asyncio
from unittest.mock import AsyncMock

import pytest

from youtube_notify import content_fetcher


def test_get_content_returns_rss_content_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rss_result = {"rss"}
    rss_get_content = AsyncMock(return_value=rss_result)
    youtube_get_content = AsyncMock(return_value={"youtube"})

    monkeypatch.setattr(content_fetcher.rss_module, "get_content", rss_get_content)
    monkeypatch.setattr(
        content_fetcher.youtube_module, "get_content", youtube_get_content
    )

    result = asyncio.run(content_fetcher.get_content("channel-123", object()))

    assert result == rss_result
    rss_get_content.assert_called_once_with("channel-123")
    youtube_get_content.assert_not_called()


def test_get_content_falls_back_to_youtube_when_rss_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    youtube_result = {"youtube"}
    rss_get_content = AsyncMock(return_value=set())
    youtube_get_content = AsyncMock(return_value=youtube_result)
    youtube_client = object()

    monkeypatch.setattr(content_fetcher.rss_module, "get_content", rss_get_content)
    monkeypatch.setattr(
        content_fetcher.youtube_module, "get_content", youtube_get_content
    )

    result = asyncio.run(content_fetcher.get_content("channel-123", youtube_client))

    assert result == youtube_result
    rss_get_content.assert_called_once_with("channel-123")
    youtube_get_content.assert_called_once_with("channel-123", youtube_client)


def test_get_content_raises_when_rss_is_empty_and_no_youtube_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        content_fetcher.rss_module, "get_content", AsyncMock(return_value=set())
    )

    with pytest.raises(ValueError, match="youtube client is required"):
        asyncio.run(content_fetcher.get_content("channel-123"))
