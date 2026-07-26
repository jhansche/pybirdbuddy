"""Basic tests for the birdbuddy.feed models."""

from datetime import datetime, timezone

from birdbuddy.feed import Feed, FeedNode, FeedNodeType


def test_feed_node_type_known_and_unknown():
    """A known __typename resolves; an unknown one falls back to Unknown."""
    assert FeedNodeType("FeedItemNewPostcard") is FeedNodeType.NewPostcard
    assert FeedNodeType("NopeNotReal") is FeedNodeType.Unknown


def test_parse_datetime_none_and_formats():
    """parse_datetime handles None, the 24-char feed format, and ISO."""
    assert FeedNode.parse_datetime(None) is None
    feed_fmt = FeedNode.parse_datetime("2023-01-01T00:00:00.000Z")
    assert feed_fmt is not None
    assert feed_fmt.year == 2023
    iso = FeedNode.parse_datetime("2023-06-15T12:30:00+00:00")
    assert iso is not None
    assert iso.month == 6


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
    """Build a Feed of NewPostcard edges, one per given timestamp."""
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
