from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import pytest

os.environ["LOG_DIR"] = str(Path(__file__).resolve().parents[2] / "logs")

from youtube_notify.rss import rss as rss_module
from youtube_notify.util.youtube import channel_id_to_playlist_ids
from youtube_notify.youtube import youtube as youtube_module

INTEGRATION_CHANNEL_ID = "UC1234567890ABCDEFXYZ12"
CHANNEL_TITLE = "Example Channel"
PUBLISHED_AT = datetime(2026, 5, 30, 17, 28, 38, tzinfo=timezone.utc)


def _build_rss_feed(playlist_id: str, video_id: str) -> feedparser.FeedParserDict:
    return feedparser.FeedParserDict(
        {
            "href": f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}",
            "entries": [
                feedparser.FeedParserDict(
                    {
                        "yt_channelid": INTEGRATION_CHANNEL_ID,
                        "authors": [{"name": CHANNEL_TITLE}],
                        "yt_videoid": video_id,
                        "title": f"Launch Video {video_id}",
                        "published_parsed": PUBLISHED_AT.timetuple(),
                        "media_thumbnail": [
                            {
                                "url": (
                                    "https://i.ytimg.com/vi/"
                                    f"{video_id}/maxresdefault.jpg"
                                )
                            }
                        ],
                        "summary": "A sample description.",
                    }
                )
            ],
        }
    )


def _build_youtube_item(playlist_id: str, video_id: str) -> dict:
    return {
        "snippet": {
            "playlistId": playlist_id,
            "channelId": INTEGRATION_CHANNEL_ID,
            "channelTitle": CHANNEL_TITLE,
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
        "status": {"privacyStatus": "public"},
    }


@pytest.fixture(scope="session")
def integration_channel_id() -> str:
    return INTEGRATION_CHANNEL_ID


@pytest.fixture(scope="session")
def mock_rss_feeds() -> dict[str, feedparser.FeedParserDict]:
    feeds: dict[str, feedparser.FeedParserDict] = {}
    for index, playlist_id in enumerate(
        sorted(channel_id_to_playlist_ids(INTEGRATION_CHANNEL_ID)), start=1
    ):
        feeds[playlist_id] = _build_rss_feed(playlist_id, f"rss-video-{index}")
    return feeds


@pytest.fixture(scope="session")
def mock_youtube_items() -> dict[str, list[dict]]:
    items: dict[str, list[dict]] = {}
    for index, playlist_id in enumerate(
        sorted(channel_id_to_playlist_ids(INTEGRATION_CHANNEL_ID)), start=1
    ):
        items[playlist_id] = [_build_youtube_item(playlist_id, f"api-video-{index}")]
    return items


@pytest.fixture(scope="session")
def mock_youtube_client() -> object:
    return object()


@pytest.fixture(autouse=True)
def mock_external_youtube_calls(
    monkeypatch: pytest.MonkeyPatch,
    mock_rss_feeds: dict[str, feedparser.FeedParserDict],
    mock_youtube_items: dict[str, list[dict]],
) -> None:
    def fake_get_feed(playlist_id: str) -> feedparser.FeedParserDict:
        return mock_rss_feeds[playlist_id]

    def fake_get_api_response(playlist_id: str, youtube: object) -> list[dict]:
        return mock_youtube_items[playlist_id]

    monkeypatch.setattr(rss_module, "__get_feed", fake_get_feed)
    monkeypatch.setattr(youtube_module, "__get_api_response", fake_get_api_response)
