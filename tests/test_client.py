"""Tests for the BirdBuddy client methods."""

from unittest.mock import ANY, AsyncMock, call, patch

import pytest

from birdbuddy.client import BirdBuddy
from birdbuddy.exceptions import NoFirmwareUpdateAvailableError, UnexpectedResponseError
from birdbuddy.feeder import Feeder
from birdbuddy.postcards import CollectedPostcard, PostcardAnalysis
from birdbuddy.sightings import PostcardSighting, SightingFinishStrategy

_POSTCARD_ID = "725af10e-8be1-5252-96fe-d49565053c44"
_SIGHTING_ID = "64af354b-3689-5df8-afcd-78ec4f987b88"
_UNLOCKED_MEDIA = "35976ed3-743e-59fb-8729-9f7ea3f3ba30"
_UNLOCKED_SPECIES = "8bfa14a1-9205-524c-81e8-0745f37ea2c9"
_BEST_GUESS_SPECIES = "419344a6-2a6e-5e60-9d47-352546eb5180"


@pytest.mark.asyncio
async def test_finish_postcard_recognized(
    bbclient: BirdBuddy,
    postcard_sighting: dict,
    graphql_mock: AsyncMock,
):
    """RECOGNIZED finishes directly, with no species-choice call."""
    graphql_mock.side_effect = [
        {"data": {"sightingReportPostcardFinish": {"success": True}}},
    ]
    result = await bbclient.finish_postcard(
        postcard_sighting["postcard"]["id"],
        PostcardSighting(postcard_sighting["sighting"]),
        strategy=SightingFinishStrategy.RECOGNIZED,
    )
    graphql_mock.assert_called_once_with(
        query=ANY,
        variables={
            "sightingReportPostcardFinishInput": {
                "defaultCoverMedia": [
                    {
                        "mediaId": _UNLOCKED_MEDIA,
                        "speciesId": _UNLOCKED_SPECIES,
                    }
                ],
                "notSelectedMediaIds": [],
                "feedItemId": _POSTCARD_ID,
                "reportToken": ANY,
            }
        },
        headers=ANY,
    )
    assert result is True


@pytest.mark.parametrize(
    ("drop_recognized", "expected_species", "expected_cover"),
    [
        pytest.param(True, _BEST_GUESS_SPECIES, [], id="best_guess"),
        pytest.param(
            False,
            _UNLOCKED_SPECIES,
            [{"mediaId": _UNLOCKED_MEDIA, "speciesId": _UNLOCKED_SPECIES}],
            id="anomaly_correction",
        ),
    ],
)
@pytest.mark.asyncio
async def test_finish_postcard_best_guess(
    bbclient: BirdBuddy,
    postcard_sighting: dict,
    graphql_mock: AsyncMock,
    drop_recognized: bool,
    expected_species: str,
    expected_cover: list,
):
    """BEST_GUESS chooses a species, then finishes.

    With the recognized sighting dropped it falls back to the highest
    confidence match; kept, it propagates the recognized species to correct
    the anomaly.
    """
    report = postcard_sighting["sighting"]["sightingReport"]
    if drop_recognized:
        report["sightings"] = [
            s
            for s in report["sightings"]
            if s["__typename"] != "SightingRecognizedBirdUnlocked"
        ]
    modified = report.copy()
    modified["reportToken"] = report["reportToken"] + ".altered"
    graphql_mock.side_effect = [
        {"data": {"sightingChooseSpecies": modified}},
        {"data": {"sightingReportPostcardFinish": {"success": True}}},
    ]
    result = await bbclient.finish_postcard(
        postcard_sighting["postcard"]["id"],
        PostcardSighting(postcard_sighting["sighting"]),
        strategy=SightingFinishStrategy.BEST_GUESS,
    )
    graphql_mock.assert_has_calls(
        calls=[
            call(
                query=ANY,
                variables={
                    "sightingChooseSpeciesInput": {
                        "reportToken": ANY,
                        "speciesId": expected_species,
                        "sightingId": _SIGHTING_ID,
                    },
                },
                headers=ANY,
            ),
            call(
                query=ANY,
                variables={
                    "sightingReportPostcardFinishInput": {
                        "defaultCoverMedia": expected_cover,
                        "notSelectedMediaIds": [],
                        "feedItemId": _POSTCARD_ID,
                        "reportToken": modified["reportToken"],
                    }
                },
                headers=ANY,
            ),
        ],
        any_order=False,
    )
    assert result is True


@pytest.mark.asyncio
async def test_sighting_create_deprecated_and_removed(bbclient: BirdBuddy):
    """sighting_create is deprecated and raises; the API removed the mutation."""
    with pytest.deprecated_call(), pytest.raises(NotImplementedError):
        await bbclient.sighting_create(["media-id-1", "media-id-2"])


@pytest.mark.asyncio
async def test_sighting_create_check_progress_deprecated_and_removed(
    bbclient: BirdBuddy,
):
    """sighting_create_check_progress is deprecated and raises."""
    with pytest.deprecated_call(), pytest.raises(NotImplementedError):
        await bbclient.sighting_create_check_progress(
            sighting_create_id="x", watching_id="y"
        )


@pytest.mark.asyncio
async def test_reanalyze_postcard(bbclient: BirdBuddy, graphql_mock: AsyncMock):
    """reanalyze_postcard is deprecated but still returns the raw payload."""
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
    with pytest.deprecated_call():
        result = await bbclient.reanalyze_postcard("postcard-id-1")

    assert isinstance(result, dict)
    assert result["updatedFeedItem"]["id"] == "postcard-id-1"

    graphql_mock.assert_called_once_with(
        query=ANY,
        variables={"feedItemId": "postcard-id-1"},
        headers=ANY,
    )


@pytest.mark.asyncio
async def test_identify_postcard_rejects_bad_type(bbclient: BirdBuddy):
    """A non-str/FeedNode postcard raises TypeError before any request."""
    with pytest.raises(TypeError):
        await bbclient.identify_postcard(123)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_identify_postcard(bbclient: BirdBuddy, graphql_mock: AsyncMock):
    """identify_postcard parses the feed item into a PostcardAnalysis."""
    graphql_mock.side_effect = [
        {
            "data": {
                "inferenceExternalPostcardReanalyze": {
                    "updatedFeedItem": {
                        "__typename": "FeedItemNewPostcard",
                        "id": "postcard-id-1",
                        "inferenceExecutionMode": "MANUAL_COMPLETED",
                        "sightingReportPreview": {
                            "sightings": [
                                {
                                    "__typename": "SightingRecognizedBird",
                                    "species": {
                                        "id": "s1",
                                        "name": "American Robin",
                                    },
                                }
                            ]
                        },
                    }
                }
            }
        }
    ]
    result = await bbclient.identify_postcard("postcard-id-1")

    assert isinstance(result, PostcardAnalysis)
    assert result.id == "postcard-id-1"
    assert result.inference_execution_mode == "MANUAL_COMPLETED"
    assert [s.name for s in result.species] == ["American Robin"]

    graphql_mock.assert_called_once_with(
        query=ANY,
        variables={"feedItemId": "postcard-id-1"},
        headers=ANY,
    )


def _collection_page(media_id: str, *, has_next: bool, cursor: str | None) -> dict:
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
async def test_collection_paginates(bbclient: BirdBuddy, graphql_mock: AsyncMock):
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


@pytest.mark.asyncio
async def test_latest_collections_delegates_and_warns(bbclient: BirdBuddy):
    """latest_collections is deprecated and forwards to refresh_collections.

    The former implementation referenced an undefined query and raised
    AttributeError; it now delegates to the working method.
    """
    cached = {"col-1": ANY}
    with (
        patch.object(
            bbclient, "refresh_collections", AsyncMock(return_value=cached)
        ) as refresh,
        pytest.deprecated_call(),
    ):
        result = await bbclient.latest_collections()
    refresh.assert_awaited_once_with()
    assert result is cached


def _fts(minute: int) -> str:
    """A feed timestamp; a larger minute is a more recent item."""
    return f"2026-07-08T10:{minute:02d}:00+00:00"


def _feed_page(
    nodes: list[tuple[str, str, int]], *, has_next: bool, cursor: str | None
) -> dict:
    """Build one meFeed page from (id, __typename, minute) node tuples."""
    return {
        "data": {
            "me": {
                "feed": {
                    "edges": [
                        {
                            "node": {
                                "id": node_id,
                                "__typename": typename,
                                "createdAt": _fts(minute),
                            }
                        }
                        for node_id, typename, minute in nodes
                    ],
                    "pageInfo": {
                        "hasNextPage": has_next,
                        "endCursor": cursor,
                    },
                }
            }
        }
    }


_POSTCARD = "FeedItemNewPostcard"


@pytest.mark.parametrize("first", [0, -1, 101, 500])
@pytest.mark.asyncio
async def test_feed_rejects_bad_first(
    bbclient: BirdBuddy, graphql_mock: AsyncMock, first: int
):
    """feed(first=) outside 1-100 raises before any request (server cap)."""
    with pytest.raises(ValueError, match="between 1 and"):
        await bbclient.feed(first=first)
    graphql_mock.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_feed_paginates_to_cutoff(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """refresh_feed accumulates new items across pages up to `since`."""
    graphql_mock.side_effect = [
        _feed_page(
            [("n7", _POSTCARD, 7), ("n6", _POSTCARD, 6), ("n5", _POSTCARD, 5)],
            has_next=True,
            cursor="c1",
        ),
        _feed_page(
            [("n4", _POSTCARD, 4), ("n3", _POSTCARD, 3), ("n2", _POSTCARD, 2)],
            has_next=False,
            cursor=None,
        ),
    ]
    result = await bbclient.refresh_feed(since=_fts(3))

    # Everything strictly newer than minute 3, spanning both pages.
    assert {n.node_id for n in result} == {"n7", "n6", "n5", "n4"}
    assert graphql_mock.call_count == 2
    # The second page carries the first page's endCursor.
    assert graphql_mock.call_args_list[1].kwargs["variables"]["after"] == "c1"


@pytest.mark.asyncio
async def test_refresh_feed_stops_early_at_cutoff(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """refresh_feed stops once a page reaches items no newer than `since`."""
    graphql_mock.side_effect = [
        _feed_page(
            [("n7", _POSTCARD, 7), ("n3", _POSTCARD, 3)],
            has_next=True,
            cursor="c1",
        ),
    ]
    result = await bbclient.refresh_feed(since=_fts(5))

    # Page 1 already reaches minute 3 (<= cutoff), so no second request.
    assert {n.node_id for n in result} == {"n7"}
    assert graphql_mock.call_count == 1


@pytest.mark.asyncio
async def test_refresh_feed_without_since_returns_one_page(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """With no prior refresh, refresh_feed returns only the newest page."""
    graphql_mock.side_effect = [
        _feed_page(
            [("n7", _POSTCARD, 7), ("n6", _POSTCARD, 6)],
            has_next=True,
            cursor="c1",
        ),
    ]
    result = await bbclient.refresh_feed()

    assert {n.node_id for n in result} == {"n7", "n6"}
    assert graphql_mock.call_count == 1


@pytest.mark.asyncio
async def test_new_postcards_paginates_all_pages(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """new_postcards collects NewPostcard items across every page."""
    graphql_mock.side_effect = [
        _feed_page(
            [("p1", _POSTCARD, 7), ("x1", "FeedItemMediaLiked", 6)],
            has_next=True,
            cursor="c1",
        ),
        _feed_page(
            [("p2", _POSTCARD, 5)],
            has_next=False,
            cursor=None,
        ),
    ]
    result = await bbclient.new_postcards()

    assert {n.node_id for n in result} == {"p1", "p2"}
    assert graphql_mock.call_count == 2


@pytest.mark.asyncio
async def test_update_firmware_start_guards_when_up_to_date(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """update_firmware_start refuses to start when no update is available.

    Verified live: starting an update on an up-to-date feeder errors server
    side, so the client guards on the versions the check reported and raises
    instead of round-tripping.
    """
    fid = "f1"
    bbclient._feeders[fid] = Feeder({"id": fid, "__typename": "FeederForOwner"})
    graphql_mock.side_effect = [
        {
            "data": {
                "feederFirmwareUpdateCheckProgress": {
                    "__typename": "FeederFirmwareUpdateSucceededResult",
                    "feeder": {
                        "availableFirmwareVersion": "1.8.1",
                        "firmwareVersion": "1.8.1",
                    },
                }
            }
        }
    ]
    with pytest.raises(NoFirmwareUpdateAvailableError):
        await bbclient.update_firmware_start(fid)
    # Only the check ran; the start mutation was never sent.
    assert graphql_mock.call_count == 1


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


@pytest.mark.asyncio
async def test_identify_postcard_unexpected_response(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """Missing reanalyze fields raise UnexpectedResponseError."""
    graphql_mock.side_effect = [{"data": {}}]
    with pytest.raises(UnexpectedResponseError):
        await bbclient.identify_postcard("postcard-id-1")


@pytest.mark.asyncio
async def test_collect_postcard_unexpected_response(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    """Missing collect fields raise UnexpectedResponseError."""
    graphql_mock.side_effect = [_REANALYZED, {"data": {}}]
    with pytest.raises(UnexpectedResponseError):
        await bbclient.collect_postcard(_PID)
