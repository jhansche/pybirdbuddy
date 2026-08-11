"""Bird Buddy Feed models."""

from __future__ import annotations

from collections import UserDict
from collections.abc import Iterator
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from propcache import cached_property

if TYPE_CHECKING:
    from birdbuddy.media import Media

from birdbuddy import LOGGER


class FeedNodeType(Enum):
    """Known Feed node types."""

    CollectedPostcard = "FeedItemCollectedPostcard"
    EditorsChoice = "FeedItemEditorsChoice"
    InvitationAccepted = "FeedItemFeederInvitationAccepted"
    InvitationConfirmed = "FeedItemFeederInvitationConfirmed"
    InvitationDeclined = "FeedItemFeederInvitationDeclined"
    LivestreamAccessRequest = "FeedItemFeederLivestreamAccessRequest"
    MemberDeleted = "FeedItemFeederMemberDeleted"
    MemberJoined = "FeedItemFeederMemberJoined"
    MediaLiked = "FeedItemMediaLiked"
    MysteryVisitorNotRecognized = "FeedItemMysteryVisitorNotRecognized"
    MysteryVisitorResolved = "FeedItemMysteryVisitorResolved"
    NewPostcard = "FeedItemNewPostcard"
    ReferralCodeUsed = "FeedItemReferralCodeUsed"
    RemoteFeederConnectionExpired = "FeedItemRemoteFeederConnectionExpired"
    RemoteFeederUnlocked = "FeedItemRemoteFeederUnlocked"
    SpeciesSighting = "FeedItemSpeciesSighting"
    SpeciesUnlocked = "FeedItemSpeciesUnlocked"

    Unknown = "Unknown"
    """Sentinel value for an unexpected feed type."""

    @classmethod
    def _missing_(cls, value: object) -> FeedNodeType:
        """Fall back to ``Unknown`` for an unrecognized feed type.

        Args:
            value: The raw value that matched no enum member.

        Returns:
            ``FeedNodeType.Unknown``.
        """
        LOGGER.warning("Unexpected Feed type: %s", value)
        return FeedNodeType.Unknown


class FeedNode(UserDict[str, Any]):
    """A single Feed edge node."""

    _DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
    """The format string of GraphQL timestamps. Not guaranteed to conform to
    :func:`datetime.fromisoformat()`, so it has to be parsed manually."""

    @staticmethod
    def parse_datetime(timestr: str | None) -> datetime | None:
        """Parse a GraphQL timestamp string into a datetime.

        Args:
            timestr: The timestamp string, or ``None``.

        Returns:
            The parsed ``datetime``, or ``None`` when ``timestr`` is ``None``.
        """
        if timestr is None:
            return None
        if len(timestr) == 24:
            # The known expected datetime format in the BirdBuddy feed
            return datetime.strptime(timestr, FeedNode._DATETIME_FORMAT)
        return datetime.fromisoformat(timestr)

    @property
    def node_id(self) -> str:
        """The Feed node id."""
        return self["id"]

    @property
    def node_type(self) -> FeedNodeType:
        """The feed node type."""
        return FeedNodeType(self.get("__typename"))

    @property
    def created_at(self) -> datetime | None:
        """The `datetime` when the FeedNode item was created."""
        return FeedNode.parse_datetime(self.get("createdAt"))

    @property
    def feeder_id(self) -> str | None:
        """The id of the feeder this item belongs to, when the item has one."""
        return (self.get("feeder") or {}).get("id")

    @property
    def medias(self) -> list[Media]:
        """The media attached to this feed item, newest first.

        ``FeedItemNewPostcard`` and ``FeedItemCollectedPostcard`` both carry
        their own media, so a caller does not need to convert a postcard into
        a sighting just to get at its images.
        """
        # Imported here rather than at module scope: media.py imports FeedNode
        # from this module, so a top-level import would be circular.
        from birdbuddy.media import Media  # noqa: PLC0415

        return sorted(
            (Media(m) for m in self.get("medias") or []),
            key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    @property
    def images(self) -> list[Media]:
        """The still images attached to this feed item, newest first."""
        return [m for m in self.medias if not m.is_video]


class FeedEdge(UserDict[str, Any]):
    """A single Feed edge."""

    @property
    def cursor(self) -> str | None:
        """Feed edge cursor."""
        return self.get("cursor")

    @property
    def node(self) -> FeedNode:
        """Feed edge node."""
        return FeedNode(self.get("node"))


class Feed(UserDict[str, Any]):
    """Representation of the Bird Buddy Feed items."""

    @property
    def edges(self) -> Iterator[FeedEdge]:
        """Returns all edges of the Feed."""
        return (FeedEdge(edge) for edge in self.get("edges", []))

    @property
    def nodes(self) -> Iterator[FeedNode]:
        """Returns all nodes of the Feed edges."""
        return (edge.node for edge in self.edges)

    @property
    def page_end_cursor(self) -> str | None:
        """The cursor used to access the next (older) page of feed items."""
        return self.get("pageInfo", {}).get("endCursor", None)

    @cached_property
    def newest_edge(self) -> FeedEdge | None:
        """Returns the newest `FeedEdge`, by `FeedNode.created_at`."""
        return max(
            (e for e in self.edges if e.node.created_at),
            key=lambda edge: cast(datetime, edge.node.created_at),
            default=None,
        )

    def filter(
        self,
        of_type: FeedNodeType | list[FeedNodeType] | None = None,
        newer_than: datetime | None = None,
    ) -> list[FeedNode]:
        """Filter the feed by node type and/or recency.

        Args:
            of_type: Only include nodes of this type (or types); ``None``
                includes all types.
            newer_than: Only include nodes created after this time; ``None``
                includes all times.

        Returns:
            The matching feed nodes.
        """
        if isinstance(of_type, FeedNodeType):
            of_type = [of_type]
        return [
            node
            for node in self.nodes
            if (of_type is None or node.node_type in of_type)
            and (
                newer_than is None or (node.created_at and node.created_at > newer_than)
            )
        ]
