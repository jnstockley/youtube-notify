import asyncio
from calendar import timegm
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from requests import HTTPError

import rss.rss as rss_module
from models import Channel, ContentType


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
    seen: list[str] = []

    async def fake_fetch_and_parse_feed(playlist_id: str) -> set[str]:
        seen.append(playlist_id)
        return {playlist_id}

    monkeypatch.setattr(
        rss_module, "channel_id_to_playlist_ids", lambda channel_id: playlist_ids
    )
    monkeypatch.setattr(rss_module, "__fetch_and_parse_feed", fake_fetch_and_parse_feed)

    result = asyncio.run(rss_module.get_content("channel-123"))

    assert result == set(playlist_ids)
    assert seen == playlist_ids


def test_fetch_and_parse_feed_uses_to_thread_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    feed = SimpleNamespace(href="https://www.youtube.com/feeds/videos.xml?playlist_id=UULF123")
    expected = {"parsed"}

    def fake_get_feed(playlist_id: str) -> object:
        return feed

    def fake_parse_feed(value: object) -> set[str]:
        return expected

    async def fake_to_thread(fn, *args):
        calls.append((fn.__name__, args))
        return fn(*args)

    monkeypatch.setattr(rss_module, "__get_feed", fake_get_feed)
    monkeypatch.setattr(rss_module, "__parse_feed", fake_parse_feed)
    monkeypatch.setattr(rss_module.asyncio, "to_thread", fake_to_thread)

    result = asyncio.run(rss_module.__fetch_and_parse_feed("playlist-1"))

    assert result == expected
    assert calls == [("fake_get_feed", ("playlist-1",)), ("fake_parse_feed", (feed,))]


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


def test_get_feed_builds_user_agent_and_returns_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = SimpleNamespace(status=200)
    parse = Mock(return_value=response)
    monkeypatch.setattr(rss_module.feedparser, "parse", parse)
    monkeypatch.setattr(rss_module, "get_version", lambda: "1.2.3")

    result = rss_module.__get_feed("playlist-123")

    assert result is response
    parse.assert_called_once_with(
        "https://www.youtube.com/feeds/videos.xml?playlist_id=playlist-123",
        agent="youtube-notify/1.2.3",
    )


def test_get_feed_raises_for_non_200_status(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(status=404)
    monkeypatch.setattr(rss_module.feedparser, "parse", Mock(return_value=response))
    monkeypatch.setattr(rss_module, "get_version", lambda: "1.2.3")

    with pytest.raises(HTTPError, match="Status code: 404"):
        rss_module.__get_feed("playlist-123")
