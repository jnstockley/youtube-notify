from datetime import datetime

import pytest
from pydantic import HttpUrl, ValidationError

from youtube_notify.models import Channel, Content, ContentType


def test_channel_repr_and_validation() -> None:
    channel = Channel(id="channel-123", name="Example Channel")

    assert repr(channel) == "Channel(id=channel-123, name=Example Channel)"

    with pytest.raises(ValidationError):
        Channel.model_validate({"id": "", "name": "Example Channel"})

    with pytest.raises(ValidationError):
        Channel.model_validate(
            {"id": "channel-123", "name": "Example Channel", "extra": "nope"}
        )


def test_content_repr_hashability_and_validation() -> None:
    channel = Channel(id="channel-123", name="Example Channel")
    local_tz = datetime.now().astimezone().tzinfo
    published_at = datetime(2026, 5, 30, 17, 28, 38, tzinfo=local_tz)
    content = Content(
        id="video-123",
        title="Launch Video",
        published_at=published_at,
        thumbnail_url=HttpUrl("https://i.ytimg.com/vi/video-123/maxresdefault.jpg"),
        description="A sample description.",
        content_type=ContentType.VIDEO,
        channel=channel,
    )

    assert repr(content).startswith(
        f"Content(id=video-123, title=Launch Video, published_at={published_at}"
    )
    assert len({content, content}) == 1

    with pytest.raises(ValidationError):
        Content.model_validate(
            {
                "id": "video-123",
                "title": "Launch Video",
                "published_at": published_at.replace(tzinfo=None),
                "thumbnail_url": HttpUrl(
                    "https://i.ytimg.com/vi/video-123/maxresdefault.jpg"
                ),
                "description": "A sample description.",
                "content_type": ContentType.VIDEO,
                "channel": channel,
            }
        )

    with pytest.raises(ValidationError):
        Content.model_validate(
            {
                "id": "video-123",
                "title": "Launch Video",
                "published_at": published_at,
                "thumbnail_url": "not-a-url",
                "description": "A sample description.",
                "content_type": ContentType.VIDEO,
                "channel": channel,
            }
        )
