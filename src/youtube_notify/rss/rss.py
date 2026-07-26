import asyncio
from calendar import timegm
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import feedparser
import httpx
from pydantic import HttpUrl

from ..models import Channel, Content, ContentType
from ..util.logging import logger
from ..util.version import get_version
from ..util.youtube import channel_id_to_playlist_ids, get_content_type

RSS_FEED_URL = "https://www.youtube.com/feeds/videos.xml?playlist_id={}"
RSS_FEED_TIMEOUT_SECONDS = 10.0


async def get_content(channel_id: str, client: httpx.AsyncClient) -> set[Content]:
    """Fetch and merge playlist feeds using one pooled asynchronous HTTP client.

    This is an opt-in alternative to :func:`get_content` for callers that want
    HTTP connection pooling and async request handling.  It deliberately does
    not replace the existing function so callers can compare the two paths.

    Args:
        channel_id: YouTube channel identifier used to derive playlist IDs.
        client: YouTube client object.

    Returns:
        A deduplicated set of parsed ``Content`` objects.
    """
    playlist_ids = channel_id_to_playlist_ids(channel_id)
    user_agent = f"youtube-notify/{get_version()}"
    client.headers.update({"User-Agent": user_agent})

    async with client:
        tasks: list[asyncio.Task[set[Content]]] = []
        async with asyncio.TaskGroup() as task_group:
            for playlist_id in playlist_ids:
                tasks.append(
                    task_group.create_task(__fetch_and_parse_feed(playlist_id, client))
                )

    content: set[Content] = set()
    for task in tasks:
        content.update(task.result())
    return content


async def __fetch_and_parse_feed(
    playlist_id: str, client: httpx.AsyncClient
) -> set[Content]:
    """
    Fetch a playlist feed and convert it to content.
    :param playlist_id: YouTube playlist identifier for a single feed variant.
    :param client: YouTube client to use for HTTP connections.
    :return: A set of parsed `Content` objects from the feed.
    """
    feed = await __get_feed(playlist_id, client)
    if feed is None:
        return set()
    return __parse_feed(feed)


def __parse_feed(feed: feedparser.FeedParserDict) -> set[Content]:
    """Parse a YouTube RSS feed into unique `Content` records.

    The feed is expected to contain at least one entry so the channel
    metadata can be derived from the first item.

    Args:
        feed: Parsed RSS feed returned by `feedparser`.

    Returns:
        A set of deduplicated `Content` objects.
    """
    url = urlparse(feed.href)
    playlist_id: str = str(parse_qs(url.query)["playlist_id"][0])
    content_type: ContentType = get_content_type(playlist_id)

    channel_id = feed.entries[0].yt_channelid
    channel_name = feed.entries[0].authors[0]["name"]
    channel = Channel(id=channel_id, name=channel_name)

    content: set[Content] = set()

    for entry in feed.entries:
        video_id = entry.yt_videoid
        title = entry.title
        local_timezone = datetime.now().astimezone().tzinfo
        published_at = datetime.fromtimestamp(
            timegm(entry.published_parsed), tz=local_timezone
        )
        thumbnail_url = HttpUrl(entry.media_thumbnail[0]["url"])
        description = entry.summary
        content.add(
            Content(
                id=video_id,
                title=title,
                published_at=published_at,
                thumbnail_url=thumbnail_url,
                description=description,
                content_type=content_type,
                channel=channel,
            )
        )

    return content


async def __get_feed(
    playlist_id: str, client: httpx.AsyncClient
) -> feedparser.FeedParserDict | None:
    """
    Fetch a YouTube RSS feed for the given playlist ID.
    :param playlist_id: YouTube playlist identifier.
    :param client: YouTube client object.
    :return: Parsed RSS feed returned by `feedparser`, or None if the request failed.
    """
    url = RSS_FEED_URL.format(playlist_id)
    try:
        response = await client.get(url, timeout=RSS_FEED_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError:
        logger.error("Failed to fetch RSS feed: %s.", url)
        return None

    feed = await asyncio.to_thread(
        feedparser.parse,
        response.content,
        response_headers={"content-location": str(response.url)},
    )
    # ``feedparser.parse`` receives bytes rather than a URL on this path, so
    # preserve the source URL required by ``__parse_feed``.
    feed.href = str(response.url)
    return feed
