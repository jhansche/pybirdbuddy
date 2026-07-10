"""Bird Buddy collections and media."""

from __future__ import annotations

from collections import UserDict
from datetime import datetime
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from birdbuddy.birds import Species
from birdbuddy.feed import FeedNode


class Media(UserDict[str, Any]):
    """Represents one ``MediaImage`` or ``MediaVideo`` type."""

    @property
    def id(self) -> str:
        """The media id."""
        return self["id"]

    @property
    def is_video(self) -> bool:
        """`True` if this Media is a Video item, `False` if Image."""
        return self["__typename"] == "MediaVideo"

    @property
    def created_at(self) -> datetime:
        """Creation timestamp.

        ``createdAt`` is non-null in the schema and selected by every query
        that returns Media, so it is always present.
        """
        return FeedNode.parse_datetime(self["createdAt"])

    @property
    def thumbnail_url(self) -> str:
        """Thumbnail URL."""
        return self["thumbnailUrl"]

    @property
    def content_url(self) -> str | None:
        """Large content URL."""
        return self.get("contentUrl", None)

    @property
    def is_expired(self) -> bool | None:
        """`True` if the media URL is expired."""
        return is_media_expired(self.thumbnail_url)


def is_media_expired(media_url: str) -> bool | None:
    """Report whether a signed media URL has expired.

    Args:
        media_url: A signed media URL carrying an ``Expires`` query param.

    Returns:
        ``True`` if expired, ``False`` if still valid, or ``None`` when the
        URL is empty or carries no expiry.
    """
    if not media_url:
        return None
    expires = parse_qs(urlparse(media_url).query).get("Expires")
    if not expires:
        return None
    expiry = int(expires[-1])
    if not expiry:
        return None
    now = time.time()
    return expiry < now


class Collection(UserDict[str, Any]):
    """Collection of media for a particular bird species."""

    @property
    def bird_name(self) -> str | None:
        """The bird species in this collection."""
        return self.get("species", {}).get("name", None)

    @property
    def species(self) -> Species | None:
        """The bird species of this collection."""
        if s := self.get("species", None):
            return Species(s)
        return None

    @property
    def collection_id(self) -> str:
        """The collection ``UUID``."""
        return self["id"]

    @property
    def total_visits(self) -> int:
        """Total number of visits."""
        return int(self.get("visitsAllTime", 0))

    @property
    def last_visit(self) -> datetime:
        """Most recent visit time.

        ``visitLastTime`` is non-null in the schema and selected by every
        collection query, so it is always present.
        """
        return FeedNode.parse_datetime(self["visitLastTime"])

    @property
    def feeder_name(self) -> str | None:
        """The feeder that captured this cover."""
        return self["coverCollectionMedia"].get("feederName")

    @property
    def cover_media(self) -> Media:
        """The cover media."""
        return Media(self["coverCollectionMedia"]["media"])
