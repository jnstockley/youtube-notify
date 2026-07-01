from ..models import ContentType
from .logging import logger


def get_content_type(playlist_id: str) -> ContentType:
    """Infer the content type from the playlist ID prefix.

    Args:
        playlist_id: YouTube playlist identifier.

    Returns:
        The matching `ContentType` enum value.

    Raises:
        ValueError: Raised when the playlist ID prefix is unknown.
    """
    logger.debug("Inferring content type from playlist ID %s", playlist_id)
    if playlist_id.startswith("UULF"):
        return ContentType.VIDEO
    elif playlist_id.startswith("UULV"):
        return ContentType.LIVESTREAM
    elif playlist_id.startswith("UUSH"):
        return ContentType.SHORT
    else:
        raise ValueError(f"Unknown content type for playlist ID: {playlist_id}")


def channel_id_to_playlist_ids(channel_id: str) -> set[str]:
    return {
        f"UULF{channel_id[2:]}",
        f"UULV{channel_id[2:]}",
        f"UUSH{channel_id[2:]}",
    }
