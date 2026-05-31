import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

import youtube.youtube as youtube_module
from models import Channel, Content, ContentType


def _api_item(
    video_id: str,
    *,
    public: bool = True,
) -> dict:
    return {
        "snippet": {
            "playlistId": "UULFABCDEF123",
            "channelId": "channel-123",
            "channelTitle": "Example Channel",
            "resourceId": {"videoId": video_id},
            "title": f"Launch Video {video_id}",
            "publishedAt": "2026-05-30T17:28:38Z",
            "thumbnails": {
                "maxres": {
                    "url": f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
                }
            },
            "description": "A sample description.",
        },
        "status": {"privacyStatus": "public" if public else "private"},
    }


def test_get_content_merges_results_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    playlist_ids = ["playlist-1", "playlist-2", "playlist-3"]
    expected = Content(
        id="video-123",
        title="Launch Video",
        published_at=datetime(2026, 5, 30, 17, 28, 38, tzinfo=timezone.utc),
        thumbnail_url="https://i.ytimg.com/vi/video-123/maxresdefault.jpg",
        description="A sample description.",
        content_type=ContentType.VIDEO,
        channel=Channel(id="channel-123", name="Example Channel"),
    )
    seen: list[str] = []

    async def fake_fetch_and_parse_api_response(
        playlist_id: str, youtube: object
    ) -> set[Content]:
        seen.append(playlist_id)
        return {expected}

    monkeypatch.setattr(
        youtube_module, "channel_id_to_playlist_ids", lambda channel_id: playlist_ids
    )
    monkeypatch.setattr(
        youtube_module,
        "__fetch_and_parse_api_response",
        fake_fetch_and_parse_api_response,
    )

    result = asyncio.run(youtube_module.get_content("channel-123", object()))

    assert result == {expected}
    assert seen == playlist_ids


def test_fetch_and_parse_api_response_uses_to_thread_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    youtube_client = object()
    feed = [_api_item("video-123")]
    expected = {
        Content.model_validate(
            {
                "id": "video-123",
                "title": "Launch Video",
                "published_at": datetime(2026, 5, 30, 17, 28, 38, tzinfo=timezone.utc),
                "thumbnail_url": "https://i.ytimg.com/vi/video-123/maxresdefault.jpg",
                "description": "A sample description.",
                "content_type": ContentType.VIDEO,
                "channel": Channel(id="channel-123", name="Example Channel"),
            }
        )
    }

    def fake_get_api_response(playlist_id: str, youtube: object) -> list[dict]:
        return feed

    def fake_parse_api_response(items: list[dict]) -> set[Content]:
        return expected

    async def fake_to_thread(fn, *args):
        calls.append((fn.__name__, args))
        return fn(*args)

    monkeypatch.setattr(youtube_module, "__get_api_response", fake_get_api_response)
    monkeypatch.setattr(youtube_module, "__parse_api_response", fake_parse_api_response)
    monkeypatch.setattr(youtube_module.asyncio, "to_thread", fake_to_thread)

    result = asyncio.run(
        youtube_module.__fetch_and_parse_api_response("playlist-1", youtube_client)
    )

    assert result == expected
    assert calls == [
        ("fake_get_api_response", ("playlist-1", youtube_client)),
        ("fake_parse_api_response", (feed,)),
    ]


def test_parse_api_response_returns_empty_set_for_no_items(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("DEBUG", logger=youtube_module.logger.name):
        result = youtube_module.__parse_api_response([])

    assert result == set()
    assert "No playlist items returned from the YouTube API response" in caplog.text


def test_parse_api_response_parses_public_items_and_stops_after_ten(
    caplog: pytest.LogCaptureFixture,
) -> None:
    items = [_api_item("video-1")]
    items.append(_api_item("video-2", public=False))
    items.extend(_api_item(f"video-{index}") for index in range(3, 13))

    with caplog.at_level("WARNING"):
        result = youtube_module.__parse_api_response(items)

    assert len(result) == 10
    assert {content.id for content in result} == {
        "video-1",
        "video-3",
        "video-4",
        "video-5",
        "video-6",
        "video-7",
        "video-8",
        "video-9",
        "video-10",
        "video-11",
    }
    assert "Skipping non-public video with ID: video-2" in caplog.text

    parsed = next(content for content in result if content.id == "video-1")
    assert parsed.title == "Launch Video video-1"
    assert (
        parsed.published_at
        == datetime.fromisoformat("2026-05-30T17:28:38+00:00").astimezone()
    )
    assert str(parsed.thumbnail_url) == (
        "https://i.ytimg.com/vi/video-1/maxresdefault.jpg"
    )
    assert parsed.description == "A sample description."
    assert parsed.content_type is ContentType.VIDEO
    assert parsed.channel == Channel(id="channel-123", name="Example Channel")


def test_parse_api_response_returns_short_public_feed_without_breaking() -> None:
    items = [_api_item("video-1"), _api_item("video-2")]

    result = youtube_module.__parse_api_response(items)

    assert {content.id for content in result} == {"video-1", "video-2"}


def test_get_api_response_requests_playlist_items() -> None:
    response = {"items": [_api_item("video-123")]}
    request = Mock()
    request.execute.return_value = response
    playlist_items = Mock()
    playlist_items.list.return_value = request
    youtube = Mock()
    youtube.playlistItems.return_value = playlist_items

    result = youtube_module.__get_api_response("playlist-123", youtube)

    youtube.playlistItems.assert_called_once_with()
    playlist_items.list.assert_called_once_with(
        playlistId="playlist-123",
        part="snippet,status",
        maxResults=20,
    )
    request.execute.assert_called_once_with()
    assert result == response["items"]
