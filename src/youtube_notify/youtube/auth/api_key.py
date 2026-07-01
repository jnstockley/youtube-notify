from googleapiclient.discovery import Resource
import googleapiclient.discovery


def authenticate(api_key: str) -> Resource:
    """Build and return a YouTube Data API client using an API key.

    Args:
        api_key: YouTube API key used for unauthenticated client access.

    Returns:
        A configured Google API client for the YouTube Data API v3.
    """
    return googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
