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
