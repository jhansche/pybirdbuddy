"""Bird Buddy collections and media"""

from collections import UserDict
from datetime import datetime
import time
from urllib.parse import urlparse, parse_qs

from birdbuddy.feed import FeedNode


class Media(UserDict):
    """Represents one ``MediaImage`` or ``MediaVideo`` type"""

    @property
    def id(self) -> str:
        """The media id"""
        return self["id"]

    @property
    def is_video(self) -> bool:
        """`True` if this Media is a Video item, `False` if Image."""
        return self["__typename"] == "MediaVideo"

    @property
    def created_at(self) -> str:
        """Creation timestamp"""
        return self["createdAt"]

    @property
    def thumbnail_url(self) -> str:
        """Thumbnail URL"""
        return self["thumbnailUrl"]

    @property
    def content_url(self) -> str:
        """Large content URL"""
        return self.get("contentUrl", None)

    @property
    def is_expired(self) -> bool:
        """`True` if the media URL is expired"""
        if not self.thumbnail_url:
            return None
        expiry = int(
            parse_qs(urlparse(self.thumbnail_url).query).get("Expires", None).pop()
        )
        if not expiry:
            return None
        now = time.time()
        return expiry < now


class Collection(UserDict):
    """Collection of media for a particular bird species."""

    @property
    def bird_name(self) -> str:
        """The bird species in this collection"""
        return self.get("species", {}).get("name", None)

    @property
    def collection_id(self) -> str:
        """The collection ``UUID``"""
        return self["id"]

    @property
    def total_visits(self) -> int:
        """Total number of visits"""
        return int(self.get("visitsAllTime", 0))

    @property
    def last_visit(self) -> datetime:
        """Most recent visit time"""
        return FeedNode.parse_datetime(self["visitLastTime"])

    @property
    def cover_media(self) -> Media:
        """The cover media"""
        return Media(self["coverCollectionMedia"]["media"])
