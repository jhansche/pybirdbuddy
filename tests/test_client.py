"""Tests for the BirdBuddy client methods."""

from unittest.mock import ANY, AsyncMock, call

import pytest

from birdbuddy.client import BirdBuddy
from birdbuddy.postcards import CollectedPostcard


@pytest.mark.asyncio
async def test_reanalyze_postcard(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """reanalyze_postcard returns the updated feed item payload."""
    graphql_mock.side_effect = [
        {
            "data": {
                "inferenceExternalPostcardReanalyze": {
                    "updatedFeedItem": {
                        "__typename": "FeedItemNewPostcard",
                        "id": "postcard-id-1",
                        "inferenceExecutionMode": "MANUAL_COMPLETED",
                    }
                }
            }
        }
    ]
    result = await bbclient.reanalyze_postcard("postcard-id-1")

    assert isinstance(result, dict)
    assert result["updatedFeedItem"]["id"] == "postcard-id-1"

    graphql_mock.assert_called_once_with(
        query=ANY,
        variables={"feedItemId": "postcard-id-1"},
        headers=ANY,
    )


@pytest.mark.asyncio
async def test_reanalyze_postcard_rejects_bad_type(bbclient: BirdBuddy):
    """A non-str/FeedNode postcard raises TypeError before any request."""
    with pytest.raises(TypeError):
        await bbclient.reanalyze_postcard(123)  # type: ignore[arg-type]


_PID = "postcard-1"
_REANALYZED = {
    "data": {
        "inferenceExternalPostcardReanalyze": {
            "updatedFeedItem": {
                "__typename": "FeedItemNewPostcard",
                "id": _PID,
                "inferenceExecutionMode": "MANUAL_COMPLETED",
                "reanalyzeAvailability": "ALREADY_REANALYZED",
            }
        }
    }
}


@pytest.mark.asyncio
async def test_collect_postcard(
    bbclient: BirdBuddy,
    graphql_mock: AsyncMock,
    collect_flow: dict,
):
    """collect_postcard reanalyzes, then collects into a CollectedPostcard."""
    collected = collect_flow["postcard_collect"]["postcardCollect"]
    graphql_mock.side_effect = [
        _REANALYZED,
        {"data": {"postcardCollect": collected}},
    ]
    result = await bbclient.collect_postcard(_PID)
    assert isinstance(result, CollectedPostcard)
    assert result.has_mystery_visitor is False
    assert [s.name for s in result.species] == ["California Scrub-Jay"]
    assert result.medias
    graphql_mock.assert_has_calls(
        calls=[
            call(query=ANY, variables={"feedItemId": _PID}, headers=ANY),
            call(
                query=ANY,
                variables={
                    "feedItemId": _PID,
                    "postcardCollectInput": {"share": False},
                },
                headers=ANY,
            ),
        ],
        any_order=False,
    )


def _collection_page(
    media_id: str, *, has_next: bool, cursor: str | None
) -> dict:
    """Build one meCollectionsMedia page carrying a single media edge."""
    return {
        "data": {
            "collection": {
                "media": {
                    "edges": [
                        {
                            "node": {
                                "media": {
                                    "id": media_id,
                                    "__typename": "MediaImage",
                                }
                            }
                        }
                    ],
                    "pageInfo": {
                        "hasNextPage": has_next,
                        "endCursor": cursor,
                    },
                }
            }
        }
    }


@pytest.mark.asyncio
async def test_collection_paginates(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """collection() follows pageInfo.endCursor until hasNextPage is false."""
    graphql_mock.side_effect = [
        _collection_page("m1", has_next=True, cursor="cursor-1"),
        _collection_page("m2", has_next=False, cursor=None),
    ]
    result = await bbclient.collection("col-1")

    assert set(result) == {"m1", "m2"}
    assert graphql_mock.call_count == 2
    first, second = graphql_mock.call_args_list
    # First page must omit `after` entirely: the API errors on `after: null`.
    assert "after" not in first.kwargs["variables"]
    assert first.kwargs["variables"]["first"] == 50
    assert second.kwargs["variables"]["after"] == "cursor-1"


@pytest.mark.parametrize("page_size", [0, -1, 101, 1000])
@pytest.mark.asyncio
async def test_collection_rejects_bad_page_size(
    bbclient: BirdBuddy, graphql_mock: AsyncMock, page_size: int
):
    """A page_size outside 1-100 raises before any request is made.

    The API returns an internal error above 100 (observed limit); the
    guard rejects it client-side instead of round-tripping to fail.
    """
    with pytest.raises(ValueError, match="between 1 and"):
        await bbclient.collection("col-1", page_size=page_size)
    graphql_mock.assert_not_called()


@pytest.mark.asyncio
async def test_collection_stops_on_null_cursor(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """hasNextPage=True with a null endCursor terminates instead of looping.

    Only one page is queued; if the cursor guard failed, the loop would
    re-request and exhaust side_effect (StopIteration) rather than hang.
    """
    graphql_mock.side_effect = [
        _collection_page("m1", has_next=True, cursor=None),
    ]
    result = await bbclient.collection("col-1")

    assert set(result) == {"m1"}
    assert graphql_mock.call_count == 1


@pytest.mark.asyncio
async def test_collection_stops_on_repeated_cursor(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """A non-advancing (repeated) endCursor stops the loop after that page."""
    graphql_mock.side_effect = [
        _collection_page("m1", has_next=True, cursor="c1"),
        _collection_page("m2", has_next=True, cursor="c1"),
    ]
    result = await bbclient.collection("col-1")

    assert set(result) == {"m1", "m2"}
    assert graphql_mock.call_count == 2
