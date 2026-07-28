import asyncio
from calendar import timegm
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from youtube_notify.models import Channel, ContentType
from youtube_notify.rss import rss as rss_module


def _feed_entry(video_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        yt_channelid="channel-123",
        yt_videoid=video_id,
        title=f"Launch Video {video_id}",
        published_parsed=(2026, 5, 30, 17, 28, 38, 5, 150, 0),
        media_thumbnail=[{"url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"}],
        summary="A sample description.",
        authors=[{"name": "Example Channel"}],
    )


def test_get_content_merges_playlist_results(monkeypatch: pytest.MonkeyPatch) -> None:
    playlist_ids = ["playlist-1", "playlist-2", "playlist-3"]
    seen: list[tuple[str, object]] = []

    class FakeAsyncClient:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

    async def fake_fetch_and_parse_feed(playlist_id: str, client: object) -> set[str]:
        seen.append((playlist_id, client))
        return {playlist_id}

    monkeypatch.setattr(
        rss_module, "channel_id_to_playlist_ids", lambda channel_id: playlist_ids
    )
    monkeypatch.setattr(rss_module, "__fetch_and_parse_feed", fake_fetch_and_parse_feed)

    client = FakeAsyncClient()
    result = asyncio.run(rss_module.get_content("channel-123", client))

    assert result == set(playlist_ids)
    assert client.headers == {"User-Agent": "youtube-notify/0.1.0"}
    assert seen == [(playlist_id, client) for playlist_id in playlist_ids]


def test_fetch_and_parse_feed_uses_feed_getter_and_parses_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    feed = SimpleNamespace(
        href="https://www.youtube.com/feeds/videos.xml?playlist_id=UULF123"
    )
    expected = {"parsed"}

    async def fake_get_feed(playlist_id: str, client: object) -> object:
        calls.append(("get_feed", (playlist_id, client)))
        return feed

    def fake_parse_feed(value: object) -> set[str]:
        return expected

    monkeypatch.setattr(rss_module, "__get_feed", fake_get_feed)
    monkeypatch.setattr(rss_module, "__parse_feed", fake_parse_feed)

    client = object()
    result = asyncio.run(rss_module.__fetch_and_parse_feed("playlist-1", client))

    assert result == expected
    assert calls == [("get_feed", ("playlist-1", client))]


def test_get_feed_downloads_and_parses_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    playlist_id = "UULF123"
    url = "https://www.youtube.com/feeds/videos.xml?playlist_id=UULF123"
    parsed_feed = SimpleNamespace(href=None)
    parse = Mock(return_value=parsed_feed)
    calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    class FakeResponse:
        content = b"<feed />"

        def __init__(self, response_url: str) -> None:
            self.url = response_url

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        async def get(self, value: str, *, timeout: float) -> FakeResponse:
            assert value == url
            assert timeout == rss_module.RSS_FEED_TIMEOUT_SECONDS
            return FakeResponse(url)

    async def fake_to_thread(fn, *args, **kwargs):
        calls.append((fn, args, kwargs))
        return fn(*args, **kwargs)

    monkeypatch.setattr(rss_module.feedparser, "parse", parse)
    monkeypatch.setattr(rss_module.asyncio, "to_thread", fake_to_thread)

    result = asyncio.run(rss_module.__get_feed(playlist_id, FakeAsyncClient()))

    assert result is parsed_feed
    assert parsed_feed.href == url
    assert calls == [
        (
            parse,
            (b"<feed />",),
            {"response_headers": {"content-location": url}},
        )
    ]


def test_get_feed_returns_none_when_request_times_out() -> None:
    class FailingAsyncClient:
        async def get(self, value: str, *, timeout: float) -> None:
            assert timeout == rss_module.RSS_FEED_TIMEOUT_SECONDS
            raise rss_module.httpx.ReadTimeout("request timed out")

    result = asyncio.run(rss_module.__get_feed("UULF123", FailingAsyncClient()))

    assert result is None


def test_parse_feed_parses_entries_into_content() -> None:
    feed = SimpleNamespace(
        href="https://www.youtube.com/feeds/videos.xml?playlist_id=UULFABCDEF123",
        entries=[_feed_entry("video-1"), _feed_entry("video-2")],
    )

    result = rss_module.__parse_feed(feed)

    assert len(result) == 2
    content = next(item for item in result if item.id == "video-1")
    assert content.title == "Launch Video video-1"
    assert content.published_at == datetime.fromtimestamp(
        timegm(feed.entries[0].published_parsed),
        tz=content.published_at.tzinfo,
    )
    assert str(content.thumbnail_url) == "https://i.ytimg.com/vi/video-1/hqdefault.jpg"
    assert content.description == "A sample description."
    assert content.content_type is ContentType.VIDEO
    assert content.channel == Channel(id="channel-123", name="Example Channel")
