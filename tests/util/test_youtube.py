import pytest

from youtube_notify.models import ContentType
from youtube_notify.util.youtube import channel_id_to_playlist_ids, get_content_type


@pytest.mark.parametrize(
    ("playlist_id", "expected"),
    [
        ("UULFABCDEF123", ContentType.VIDEO),
        ("UULVABCDEF123", ContentType.LIVESTREAM),
        ("UUSHABCDEF123", ContentType.SHORT),
    ],
)
def test_get_content_type_maps_known_prefixes(
    playlist_id: str, expected: ContentType
) -> None:
    assert get_content_type(playlist_id) is expected


def test_get_content_type_rejects_unknown_prefix() -> None:
    with pytest.raises(ValueError, match="Unknown content type"):
        get_content_type("ZZZZABCDEF123")


def test_channel_id_to_playlist_ids_derives_expected_ids() -> None:
    assert channel_id_to_playlist_ids("UCABCDEF123") == {
        "UULFABCDEF123",
        "UULVABCDEF123",
        "UUSHABCDEF123",
    }
