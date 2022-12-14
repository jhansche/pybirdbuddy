"""Bird Buddy collections and media"""

from collections import UserDict


class Media(UserDict):
    """Represents one ``MediaImage`` type"""

    @property
    def id(self) -> str:
        """The media id"""
        return self["id"]

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
        return self["contentUrl"]


class Collection(UserDict):
    """Collection of media for a particular bird species."""

    @property
    def bird_name(self) -> str:
        """The bird species in this collection"""
        return self["species"]["name"]

    @property
    def collection_id(self) -> str:
        """The collection ``UUID``"""
        return self["id"]

    @property
    def cover_media(self) -> Media:
        """The cover media"""
        return Media(self["coverCollectionMedia"]["media"])
