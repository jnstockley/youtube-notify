from importlib import metadata


def get_version() -> str:
    try:
        return metadata.version("youtube-notify")
    except (FileNotFoundError, KeyError):
        return "unknown"
