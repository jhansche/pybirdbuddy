"""Basic tests for the birdbuddy.feed models."""

from datetime import datetime, timezone

from birdbuddy.feed import Feed, FeedNode, FeedNodeType
from birdbuddy.queries.me import FEED


def test_feed_node_type_known_and_unknown():
    """A known __typename resolves; an unknown one falls back to Unknown."""
    assert FeedNodeType("FeedItemNewPostcard") is FeedNodeType.NewPostcard
    assert FeedNodeType("NopeNotReal") is FeedNodeType.Unknown


def test_parse_datetime_formats():
    """parse_datetime handles the 24-char feed format and ISO strings."""
    assert FeedNode.parse_datetime("2023-01-01T00:00:00.000Z").year == 2023
    assert FeedNode.parse_datetime("2023-06-15T12:30:00+00:00").month == 6


def test_feed_node_created_at_absent_is_none():
    """A feed node without createdAt reports None (union member gap)."""
    node = FeedNode({"id": "x", "__typename": "FeedItemEditorsChoice"})
    assert node.created_at is None


def test_feed_node_properties():
    """FeedNode exposes its id, type, and parsed creation time."""
    node = FeedNode(
        {
            "id": "n1",
            "__typename": "FeedItemNewPostcard",
            "createdAt": "2023-01-01T00:00:00.000Z",
        }
    )
    assert node.node_id == "n1"
    assert node.node_type is FeedNodeType.NewPostcard
    assert node.created_at is not None


def _feed(*timestamps: str) -> Feed:
    edges = [
        {
            "cursor": f"c{i}",
            "node": {
                "id": f"n{i}",
                "__typename": "FeedItemNewPostcard",
                "createdAt": ts,
            },
        }
        for i, ts in enumerate(timestamps)
    ]
    return Feed({"edges": edges, "pageInfo": {"endCursor": "END"}})


def test_feed_edges_nodes_and_cursor():
    """Feed yields edges/nodes and exposes the page-end cursor."""
    feed = _feed("2023-01-01T00:00:00.000Z")
    edge = next(iter(feed.edges))
    assert edge.cursor == "c0"
    assert edge.node.node_id == "n0"
    assert [n.node_id for n in feed.nodes] == ["n0"]
    assert feed.page_end_cursor == "END"


def test_feed_newest_edge_and_filter():
    """newest_edge picks the latest node; filter narrows by type and time."""
    feed = _feed(
        "2023-01-01T00:00:00.000Z",
        "2023-03-01T00:00:00.000Z",
    )
    newest = feed.newest_edge
    assert newest is not None
    assert newest.node.node_id == "n1"

    assert len(feed.filter(of_type=FeedNodeType.NewPostcard)) == 2
    assert feed.filter(of_type=FeedNodeType.MediaLiked) == []

    cutoff = datetime(2023, 2, 1, tzinfo=timezone.utc)
    recent = feed.filter(newer_than=cutoff)
    assert [n.node_id for n in recent] == ["n1"]


def _feed_from_nodes(nodes: list[dict]) -> Feed:
    """Build a Feed from raw node dicts (each may omit createdAt)."""
    edges = [{"cursor": f"c{i}", "node": node} for i, node in enumerate(nodes)]
    return Feed({"edges": edges, "pageInfo": {"endCursor": "END"}})


_NEW = "FeedItemNewPostcard"
# A union member the query does not enumerate: it returns only __typename,
# hence no createdAt -- the condition behind issue #24.
_UNDATED = "FeedItemEditorsChoice"


def test_newest_edge_skips_nodes_without_created_at():
    """newest_edge ignores createdAt-less nodes and picks the newest dated."""
    feed = _feed_from_nodes(
        [
            {
                "id": "old",
                "__typename": _NEW,
                "createdAt": "2023-01-01T00:00:00.000Z",
            },
            {"id": "undated", "__typename": _UNDATED},
            {
                "id": "new",
                "__typename": _NEW,
                "createdAt": "2023-03-01T00:00:00.000Z",
            },
        ]
    )
    newest = feed.newest_edge
    assert newest is not None
    assert newest.node.node_id == "new"


def test_newest_edge_all_undated_returns_none():
    """When no node carries createdAt, newest_edge is None (no crash)."""
    feed = _feed_from_nodes(
        [
            {"id": "u1", "__typename": _UNDATED},
            {"id": "u2", "__typename": _UNDATED},
        ]
    )
    assert feed.newest_edge is None


def test_filter_newer_than_tolerates_missing_created_at():
    """filter(newer_than=...) does not raise on a createdAt-less node.

    Regression for issue #24: "'>' not supported between instances of
    'NoneType' and 'datetime.datetime'". A feed item with no created_at must
    be skipped by the recency comparison rather than crashing it.
    """
    feed = _feed_from_nodes(
        [
            {"id": "undated", "__typename": _UNDATED},
            {
                "id": "dated",
                "__typename": _NEW,
                "createdAt": "2023-03-01T00:00:00.000Z",
            },
        ]
    )
    cutoff = datetime(2023, 2, 1, tzinfo=timezone.utc)
    result = feed.filter(newer_than=cutoff)  # must not raise
    assert [n.node_id for n in result] == ["dated"]


def test_filter_without_cutoff_keeps_undated_nodes():
    """Filtering with no newer_than keeps matching nodes even when undated."""
    feed = _feed_from_nodes(
        [
            {"id": "undated", "__typename": _NEW},
            {
                "id": "dated",
                "__typename": _NEW,
                "createdAt": "2023-03-01T00:00:00.000Z",
            },
        ]
    )
    result = feed.filter(of_type=FeedNodeType.NewPostcard)
    assert {n.node_id for n in result} == {"undated", "dated"}


def test_feed_query_requests_created_at_for_all_union_members():
    """The FEED query selects createdAt on the FeedItem interface.

    AnyFeedItem is a union whose members all implement FeedItem{id,createdAt}.
    An interface inline fragment makes every member -- including types not
    individually enumerated -- return createdAt, fixing the issue #24 root
    cause at the source rather than only guarding it downstream.
    """
    assert "... on FeedItem {" in FEED
    interface = FEED.split("... on FeedItem {", 1)[1].split("}", 1)[0]
    assert "createdAt" in interface
