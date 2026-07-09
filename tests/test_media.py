"""Basic tests for the birdbuddy.media models."""

from datetime import datetime
import time

from birdbuddy.media import Collection, Media, is_media_expired


def _signed_url(expires: int) -> str:
    return f"https://cdn.example/i.jpg?Expires={expires}&Signature=abc"


def test_is_media_expired():
    """Expiry comes from the URL Expires param; None if absent."""
    assert is_media_expired("") is None
    assert is_media_expired(_signed_url(int(time.time()) - 1000)) is True
    assert is_media_expired(_signed_url(int(time.time()) + 1000)) is False


def test_media_image_properties():
    """An image Media exposes its urls, type flag, and expiry."""
    future_url = _signed_url(int(time.time()) + 1000)
    media = Media(
        {
            "id": "m1",
            "__typename": "MediaImage",
            "createdAt": "2023-01-01T00:00:00.000Z",
            "thumbnailUrl": future_url,
            "contentUrl": "https://cdn.example/full.jpg",
        }
    )
    assert media.id == "m1"
    assert media.is_video is False
    assert media.thumbnail_url == future_url
    assert media.content_url == "https://cdn.example/full.jpg"
    assert isinstance(media.created_at, datetime)
    assert media.is_expired is False


def test_media_video_and_missing_content_url():
    """A video Media reports is_video and a None content_url when absent."""
    media = Media(
        {
            "id": "m2",
            "__typename": "MediaVideo",
            "createdAt": "2023-01-01T00:00:00.000Z",
            "thumbnailUrl": "",
        }
    )
    assert media.is_video is True
    assert media.content_url is None
    assert media.is_expired is None


def test_collection_properties():
    """Collection surfaces its species, visits, and cover media."""
    collection = Collection(
        {
            "id": "c1",
            "species": {"id": "sp1", "name": "Robin"},
            "visitsAllTime": "5",
            "visitLastTime": "2023-01-01T00:00:00.000Z",
            "coverCollectionMedia": {
                "feederName": "Backyard",
                "media": {
                    "id": "m1",
                    "__typename": "MediaImage",
                    "createdAt": "2023-01-01T00:00:00.000Z",
                    "thumbnailUrl": "https://x/t.jpg",
                },
            },
        }
    )
    assert collection.collection_id == "c1"
    assert collection.bird_name == "Robin"
    assert collection.species is not None
    assert collection.species.id == "sp1"
    assert collection.total_visits == 5
    assert isinstance(collection.last_visit, datetime)
    assert collection.feeder_name == "Backyard"
    assert collection.cover_media.id == "m1"


def test_collection_without_species():
    """A collection missing species yields None and a zero visit count."""
    collection = Collection({"id": "c2"})
    assert collection.species is None
    assert collection.bird_name is None
    assert collection.total_visits == 0
