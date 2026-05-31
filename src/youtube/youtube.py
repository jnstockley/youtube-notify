import asyncio
from datetime import datetime

from googleapiclient.discovery import Resource
from pydantic import HttpUrl

from models import Content, ContentType, Channel
from util.logging import logger
from util.youtube import get_content_type, channel_id_to_playlist_ids


async def get_content(channel_id: str, youtube: Resource) -> set[Content]:
    """Fetch and merge all playlist feeds for a YouTube channel.

    The work is fanned out across the three playlist variants for the channel,
    then deduplicated into a single set of `Content` records.

    Args:
        channel_id: YouTube channel identifier used to derive playlist IDs.
        youtube: Authenticated YouTube API client.

    Returns:
        A deduplicated set of parsed `Content` objects.
    """
    playlist_ids = channel_id_to_playlist_ids(channel_id)
    logger.debug(
        "Fetching content for channel %s using playlists: %s",
        channel_id,
        ", ".join(playlist_ids),
    )

    tasks: list[asyncio.Task[set[Content]]] = []
    async with asyncio.TaskGroup() as task_group:
        for playlist_id in playlist_ids:
            tasks.append(
                task_group.create_task(
                    __fetch_and_parse_api_response(playlist_id, youtube)
                )
            )

    content: set[Content] = set()
    for task in tasks:
        content.update(task.result())
    logger.debug(
        "Parsed %s unique content items for channel %s", len(content), channel_id
    )
    return content


async def __fetch_and_parse_api_response(
    playlist_id: str, youtube: Resource
) -> set[Content]:
    """Fetch one playlist feed in a worker thread and parse it into content.

    Args:
        playlist_id: YouTube playlist identifier for a single feed variant.
        youtube: Authenticated YouTube API client.

    Returns:
        A set of parsed `Content` objects from the feed.
    """
    logger.debug("Fetching playlist items for %s", playlist_id)
    feed = await asyncio.to_thread(__get_api_response, playlist_id, youtube)
    logger.debug("Fetched %s playlist items for %s", len(feed), playlist_id)
    parsed = await asyncio.to_thread(__parse_api_response, feed)
    logger.debug("Parsed %s content items from %s", len(parsed), playlist_id)
    return parsed


def __parse_api_response(items: list[dict]) -> set[Content]:
    """Convert a YouTube playlistItems response into unique `Content` records.

    The response is expected to contain at least one item so the channel and
    playlist metadata can be derived from the first element.

    Args:
        items: Raw `playlistItems().list(...).execute()["items"]` payload.

    Returns:
        A set of deduplicated `Content` objects.
    """
    if not items:
        logger.debug("No playlist items returned from the YouTube API response")
        return set()

    content_type: ContentType = get_content_type(items[0]["snippet"]["playlistId"])
    logger.debug(
        "Parsing playlist items for content type %s from playlist %s",
        content_type,
        items[0]["snippet"]["playlistId"],
    )

    channel_id: str = items[0]["snippet"]["channelId"]
    channel_name: str = items[0]["snippet"]["channelTitle"]
    channel = Channel(id=channel_id, name=channel_name)

    content: set[Content] = set()

    for item in items:
        video_id = item["snippet"]["resourceId"]["videoId"]
        if item["status"]["privacyStatus"] == "public":
            title = item["snippet"]["title"]
            published_at = datetime.fromisoformat(
                item["snippet"]["publishedAt"].replace("Z", "+00:00")
            ).astimezone()
            thumbnail_url = HttpUrl(item["snippet"]["thumbnails"]["maxres"]["url"])
            description = item["snippet"]["description"]
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
            if len(content) >= 10:
                break
        else:
            logger.warning("Skipping non-public video with ID: %s", video_id)

    return content


def __get_api_response(playlist_id: str, youtube: Resource) -> list[dict]:
    """Fetch playlist items for a single YouTube playlist.

    Args:
        playlist_id: YouTube playlist identifier to fetch.
        youtube: Authenticated YouTube API client.

    Returns:
        The raw `items` list from the YouTube API response.
    """
    logger.debug("Requesting playlist items for %s", playlist_id)
    request = youtube.playlistItems().list(
        playlistId=playlist_id,
        part="snippet,status",
        maxResults=20,
    )

    response = request.execute()
    items: list[dict] = response["items"]
    logger.debug("YouTube API returned %s items for %s", len(items), playlist_id)
    return items
