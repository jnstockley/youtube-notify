import httpx
from googleapiclient.discovery import Resource

from .models import Content
from .rss import rss as rss_module
from .util.logging import logger
from .youtube import youtube as youtube_module


async def get_content(
    channel_id: str,
    youtube: Resource | None = None,
    rss_client: httpx.AsyncClient | None = None,
) -> set[Content]:
    """Fetch channel content from RSS, falling back to the YouTube API.

    Args:
        channel_id: YouTube channel identifier.
        youtube: Authenticated YouTube API client used only when RSS returns no items.
        rss_client: Optional asynchronous HTTP client for RSS requests. The caller owns
            its lifecycle, so one client can be shared across a batch of channels.

    Returns:
        A set of parsed `Content` objects.

    Raises:
        ValueError: Raised when RSS returns no items and no YouTube client is provided.
    """
    if rss_client is None:
        async with httpx.AsyncClient() as client:
            content = await rss_module.get_content(channel_id, client)
    else:
        content = await rss_module.get_content(channel_id, rss_client)
    if content:
        logger.debug("RSS returned %s items for channel %s", len(content), channel_id)
        return content

    logger.debug(
        "RSS returned no items for channel %s; falling back to YouTube", channel_id
    )
    if youtube is None:
        raise ValueError("youtube client is required when RSS returns no content")
    return await youtube_module.get_content(channel_id, youtube)
