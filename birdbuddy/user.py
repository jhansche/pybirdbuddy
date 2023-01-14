"""Bird Buddy user"""

from collections import UserDict


class BirdBuddyUser(UserDict):
    """Bird Buddy user"""

    @property
    def id(self) -> str:
        """User UUID"""
        return self["id"]

    @property
    def name(self) -> str:
        """User name"""
        return self["name"]

    @property
    def avatar_url(self) -> str:
        """User avatar"""
        return self["avatarUrl"]
