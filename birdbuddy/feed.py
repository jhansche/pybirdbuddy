"""Bird Buddy Feed models"""

from __future__ import annotations
from collections import UserDict
from datetime import datetime
from enum import Enum
from functools import cached_property

from . import LOGGER


class FeedNodeType(Enum):
    """Known Feed node types"""

    GlobalImportant = "FeedGlobalImportantItem"
    GlobalRegular = "FeedGlobalRegularItem"
    InvitationConfirmed = "FeedItemFeederInvitationConfirmed"
    InvitationDeclined = "FeedItemFeederInvitationDeclined"
    MemberDeleted = "FeedItemFeederMemberDeleted"
    MediaLiked = "FeedItemMediaLiked"
    MysteryVisitorNotRecognized = "FeedItemMysteryVisitorNotRecognized"
    MysteryVisitorResolved = "FeedItemMysteryVisitorResolved"
    NewPostcard = "FeedItemNewPostcard"
    SpeciesSighting = "FeedItemSpeciesSighting"
    SpeciesUnlocked = "FeedItemSpeciesUnlocked"

    Unknown = "Unknown"
    """Sentinel value for an unexpected feed type."""

    @classmethod
    def _missing_(cls, value: str):
        LOGGER.warning("Unexpected Feed type: %s", value)
        return FeedNodeType.Unknown


class FeedNode(UserDict[str, any]):
    """A single Feed edge node."""

    _DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
    """The format string of GraphQL timestamps. This is not guaranteed to conform to
    :func:`datetime.fromisoformat()`, so it has to be parsed manually."""

    @staticmethod
    def parse_datetime(timestr: str) -> datetime:
        """Convert a time string into `datetime`."""
        if len(timestr) == 24:
            # The known expected datetime format in the BirdBuddy feed
            return datetime.strptime(timestr, FeedNode._DATETIME_FORMAT)
        return datetime.fromisoformat(timestr)

    @property
    def node_id(self) -> str:
        """The Feed node id"""
        return self["id"]

    @property
    def node_type(self) -> FeedNodeType:
        """The feed node type"""
        return FeedNodeType(self.get("__typename"))

    @property
    def created_at(self) -> datetime:
        """The `datetime` when the FeedNode item was created."""
        return FeedNode.parse_datetime(self.get("createdAt"))


class FeedEdge(UserDict[str, any]):
    """A single Feed edge"""

    @property
    def cursor(self) -> str:
        """Feed edge cursor"""
        return self.get("cursor")

    @property
    def node(self) -> FeedNode:
        """Feed edge node"""
        return FeedNode(self.get("node"))


class Feed(UserDict[str, any]):
    """Representation of the Bird Buddy Feed items"""

    @property
    def edges(self) -> list[FeedEdge]:
        """Returns all edges of the Feed"""
        return (FeedEdge(edge) for edge in self.get("edges", []))

    @property
    def nodes(self) -> list[FeedNode]:
        """Returns all nodes of the Feed edges"""
        return (edge.node for edge in self.edges)

    @property
    def page_end_cursor(self) -> str:
        """The cursor used to access the next (older) page of feed items."""
        return self.get("pageInfo", {}).get("endCursor", None)

    @cached_property
    def newest_edge(self) -> FeedEdge | None:
        """Returns the newest `FeedEdge`, by `FeedNode.created_at`"""
        return max(self.edges, key=lambda edge: edge.node.created_at, default=None)

    def filter(
        self,
        of_type: FeedNodeType | list[FeedNodeType] = None,
        newer_than: datetime = None,
    ) -> list[FeedNode]:
        """Filter the feed by type or time"""
        if isinstance(of_type, FeedNodeType):
            of_type = [of_type]
        return list(
            node
            for node in self.nodes
            if (of_type is None or node.node_type in of_type)
            and (newer_than is None or node.created_at > newer_than)
        )
