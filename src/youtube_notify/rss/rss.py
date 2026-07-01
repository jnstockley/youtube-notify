import asyncio
import feedparser
from calendar import timegm
from datetime import datetime
from requests import HTTPError
from urllib.parse import urlparse, parse_qs

from pydantic import HttpUrl

from ..models import Channel, Content, ContentType
from ..util.logging import logger
from ..util.version import get_version
from ..util.youtube import channel_id_to_playlist_ids, get_content_type


async def get_content(channel_id: str) -> set[Content]:
    """Fetch and merge all playlist feeds for a channel.

    The work is fanned out across the three RSS playlist variants for the
    channel, then deduplicated into a single set of `Content` records.

    Args:
        channel_id: YouTube channel identifier used to derive playlist IDs.

    Returns:
        A deduplicated set of parsed `Content` objects.
    """
    playlist_ids = channel_id_to_playlist_ids(channel_id)

    tasks: list[asyncio.Task[set[Content]]] = []
    async with asyncio.TaskGroup() as task_group:
        for playlist_id in playlist_ids:
            tasks.append(task_group.create_task(__fetch_and_parse_feed(playlist_id)))

    content: set[Content] = set()
    for task in tasks:
        content.update(task.result())
    return content


async def __fetch_and_parse_feed(playlist_id: str) -> set[Content]:
    """Fetch a playlist feed in a worker thread and parse it into content.

    Args:
        playlist_id: YouTube playlist identifier for a single feed variant.

    Returns:
        A set of parsed `Content` objects from the feed.
    """
    feed = await asyncio.to_thread(__get_feed, playlist_id)
    return await asyncio.to_thread(__parse_feed, feed)


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
    playlist_id = parse_qs(url.query)["playlist_id"][0]
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


def __get_feed(playlist_id: str) -> feedparser.FeedParserDict:
    """Fetch a YouTube RSS feed for the given playlist ID.

    Args:
        playlist_id: YouTube playlist identifier used to build the feed URL.

    Returns:
        The parsed RSS feed response.

    Raises:
        HTTPError: Raised when YouTube returns a non-200 status code.
    """
    url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"

    logger.debug("Fetching RSS feed: %s", url)
    version = get_version()
    user_agent = f"youtube-notify/{version}"
    feed = feedparser.parse(url, agent=user_agent)
    status_code: int = feed.status
    logger.debug("Retrieved RSS feed: %s with status code: %s", url, status_code)
    if status_code != 200:
        logger.error("Failed to fetch RSS feed: %s.", url)
        logger.debug("Feed response: %r", feed)
        raise HTTPError(f"Failed to fetch RSS feed. Status code: {status_code}")
    return feed
