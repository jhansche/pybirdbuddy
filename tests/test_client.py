"""Tests for the BirdBuddy client methods."""

import copy
from unittest.mock import ANY, AsyncMock, call

import pytest

from birdbuddy.client import BirdBuddy
from birdbuddy.exceptions import (
    NoFirmwareUpdateAvailableError,
    UnexpectedResponseError,
)
from birdbuddy.feeder import Feeder, PowerProfile
from birdbuddy.postcards import CollectedPostcard, PostcardAnalysis


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


@pytest.mark.asyncio
async def test_identify_postcard_rejects_bad_type(bbclient: BirdBuddy):
    """A non-str/FeedNode postcard raises TypeError before any request."""
    with pytest.raises(TypeError):
        await bbclient.identify_postcard(123)  # type: ignore[arg-type]


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
async def test_refresh_populates_user_and_feeders(
    bbclient: BirdBuddy, graphql_mock: AsyncMock, api_payloads: dict
):
    """refresh() parses the ME payload into the user and feeder cache."""
    graphql_mock.side_effect = [{"data": {"me": api_payloads["me"]}}]
    assert await bbclient.refresh() is True
    assert bbclient.user is not None
    fid = api_payloads["me"]["feeders"][0]["id"]
    assert fid in bbclient.feeders
    assert bbclient.feeders[fid].is_owner is True


@pytest.mark.asyncio
async def test_login_parses_auth_and_profile(
    graphql_mock: AsyncMock, api_payloads: dict
):
    """A fresh client signs in, stores tokens, and saves the profile."""
    bb = BirdBuddy("user@email", "passw0rd")  # no tokens -> login required
    sign_in = {
        "data": {
            "authEmailSignIn": {
                "__typename": "Auth",
                "accessToken": "acc",
                "refreshToken": "ref",
                "me": api_payloads["me"],
            }
        }
    }
    graphql_mock.side_effect = [sign_in, {"data": {"me": api_payloads["me"]}}]
    assert await bb.refresh() is True
    assert bb._access_token == "acc"  # noqa: SLF001
    assert bb.user is not None
    assert len(bb.feeders) == 1
    assert graphql_mock.call_count == 2


@pytest.mark.asyncio
async def test_refresh_access_token_exchanges_refresh_token(
    graphql_mock: AsyncMock, api_payloads: dict
):
    """With only a refresh token, the client exchanges it before requesting."""
    bb = BirdBuddy("user@email", "passw0rd", refresh_token="old-refresh")
    refreshed = {
        "data": {
            "authRefreshToken": {
                "accessToken": "new-acc",
                "refreshToken": "new-ref",
            }
        }
    }
    graphql_mock.side_effect = [
        refreshed,
        {"data": {"me": api_payloads["me"]}},
    ]
    await bb.refresh()
    assert bb._access_token == "new-acc"  # noqa: SLF001
    assert bb._refresh_token == "new-ref"  # noqa: SLF001


@pytest.mark.asyncio
async def test_refresh_collections_keeps_only_birds(
    bbclient: BirdBuddy, graphql_mock: AsyncMock, api_payloads: dict
):
    """refresh_collections keeps CollectionBird and keys by collection id."""
    graphql_mock.side_effect = [
        {"data": {"me": {"collections": api_payloads["collections"]}}}
    ]
    result = await bbclient.refresh_collections()
    # The fixture holds 4 CollectionBird + 1 CollectionMysteryVisitor.
    assert len(result) == 4
    assert all(c["__typename"] == "CollectionBird" for c in result.values())


@pytest.mark.asyncio
async def test_set_feeder_options_filters_unknown_keys(
    bbclient: BirdBuddy, graphql_mock: AsyncMock, api_payloads: dict
):
    """set_feeder_options sends only recognized keys and caches the result.

    Response shape matches the SET_OPTIONS selection set (FeederForOwner).
    """
    feeder_data = api_payloads["me"]["feeders"][0]
    fid = feeder_data["id"]
    bbclient._feeders[fid] = Feeder(feeder_data)  # noqa: SLF001
    updated = {"id": fid, "name": "Renamed", "__typename": "FeederForOwner"}
    graphql_mock.side_effect = [{"data": {"feederUpdate": updated}}]
    result = await bbclient.set_feeder_options(fid, name="Renamed", bogus="x")
    assert result == updated
    variables = graphql_mock.call_args_list[0].kwargs["variables"]
    assert variables["feederId"] == fid
    assert variables["feederUpdateInput"] == {"name": "Renamed"}
    assert bbclient.feeders[fid]["name"] == "Renamed"


@pytest.mark.asyncio
async def test_share_medias(bbclient: BirdBuddy, graphql_mock: AsyncMock):
    """share_medias posts the media ids and returns the success flag."""
    graphql_mock.side_effect = [
        {"data": {"mediaShareToggle": {"success": True}}}
    ]
    assert await bbclient.share_medias(["m1", "m2"], share=True) is True
    variables = graphql_mock.call_args_list[0].kwargs["variables"]
    assert variables["mediaShareToggleInput"] == {
        "mediaIds": ["m1", "m2"],
        "share": True,
    }


@pytest.mark.asyncio
async def test_set_power_profile_refreshes_after_async_change(
    bbclient: BirdBuddy, graphql_mock: AsyncMock, api_payloads: dict
):
    """set_power_profile refreshes to read the applied profile.

    Verified live: the mutation returns InProgressResult with the *old*
    profile (the change applies asynchronously), so the client refreshes and
    reads the new value from the updated feeder.
    """
    feeder_data = api_payloads["me"]["feeders"][0]
    fid = feeder_data["id"]
    bbclient._feeders[fid] = Feeder(feeder_data)  # noqa: SLF001
    in_progress = {
        "data": {
            "feederUpdatePowerProfile": {
                "__typename": "FeederUpdatePowerProfileInProgressResult",
                # Stale value: the change has not applied yet.
                "feeder": {"powerProfile": "STANDARD_MODE"},
            }
        }
    }
    me_after = copy.deepcopy(api_payloads["me"])
    me_after["feeders"][0]["powerProfile"] = "POWER_SAVER_MODE"
    graphql_mock.side_effect = [in_progress, {"data": {"me": me_after}}]

    result = await bbclient.set_power_profile(fid, PowerProfile.POWER_SAVE)
    assert result == {"powerProfile": "POWER_SAVER_MODE"}
    sent = graphql_mock.call_args_list[0].kwargs["variables"]
    assert sent["feederUpdatePowerProfileInput"] == {
        "powerProfile": "POWER_SAVER_MODE"
    }


@pytest.mark.asyncio
async def test_update_firmware_check_up_to_date(
    bbclient: BirdBuddy, graphql_mock: AsyncMock, api_payloads: dict
):
    """update_firmware_check parses an up-to-date firmware status.

    Verified live: a feeder already on the latest firmware returns
    SucceededResult with matching firmwareVersion/availableFirmwareVersion,
    which is_complete, so the client refreshes its cached feeder.
    """
    feeder_data = api_payloads["me"]["feeders"][0]
    fid = feeder_data["id"]
    bbclient._feeders[fid] = Feeder(feeder_data)  # noqa: SLF001
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
    status = await bbclient.update_firmware_check(fid)
    assert status.is_complete is True
    assert status.is_in_progress is False
    assert status.feeder.version == "1.8.1"


@pytest.mark.asyncio
async def test_update_firmware_start_guards_when_up_to_date(
    bbclient: BirdBuddy, graphql_mock: AsyncMock, api_payloads: dict
):
    """update_firmware_start refuses to start when no update is available.

    Verified live: starting an update on an up-to-date feeder errors server
    side, so the client guards on the versions the check reported and raises
    instead of round-tripping.
    """
    feeder_data = api_payloads["me"]["feeders"][0]
    fid = feeder_data["id"]
    bbclient._feeders[fid] = Feeder(feeder_data)  # noqa: SLF001
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
