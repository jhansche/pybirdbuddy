"""Bird Buddy collections and media"""

from collections import UserDict


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
    def cover_media(self) -> dict[str, any]:
        """The cover media"""
        return self["coverCollectionMedia"]
