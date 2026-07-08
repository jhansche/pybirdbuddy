"""Tests for the BirdBuddy client methods."""

from unittest.mock import ANY, AsyncMock, call

import pytest

from birdbuddy.client import BirdBuddy
from birdbuddy.sightings import (
    PostcardSighting,
    SightingCreateProgress,
    SightingFinishStrategy,
    SightingReport,
)

_POSTCARD_ID = "ea7c32bb-e95b-4fe6-a8ef-64134c1ae97e"
_SIGHTING_ID = "233000f8-ecbe-430c-9227-2c826866323f"
_UNLOCKED_MEDIA = "e579818d-cb68-40d2-876c-fcfdf3483eb6"
_UNLOCKED_SPECIES = "35379866-a4c6-4991-a2af-e6da93eaec4f"
_BEST_GUESS_SPECIES = "81a13484-a311-477d-8011-8873bd3c053c"


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
async def test_sighting_create(bbclient: BirdBuddy, graphql_mock: AsyncMock):
    """sighting_create returns a SightingCreateProgress from the response."""
    graphql_mock.side_effect = [
        {
            "data": {
                "sightingCreate": {
                    "sightingCreateProgress": {
                        "id": "test-create-id",
                        "progress": 42.5,
                        "__typename": "SightingCreateProgress",
                    }
                }
            }
        }
    ]
    result = await bbclient.sighting_create(["media-id-1", "media-id-2"])

    assert isinstance(result, SightingCreateProgress)
    assert result.id == "test-create-id"
    assert result.progress == 42.5

    graphql_mock.assert_called_once_with(
        query=ANY,
        variables={
            "sightingCreateInput": {
                "mediaIds": ["media-id-1", "media-id-2"],
            }
        },
        headers=ANY,
    )


_IN_PROGRESS = {
    "id": "test-create-id",
    "progress": 75.0,
    "__typename": "SightingCreateProgress",
}
_COMPLETED = {
    "reportToken": "test-report-token",
    "sightings": [],
    "__typename": "SightingReport",
}


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        pytest.param(_IN_PROGRESS, SightingCreateProgress, id="in_progress"),
        pytest.param(_COMPLETED, SightingReport, id="completed"),
    ],
)
@pytest.mark.asyncio
async def test_sighting_create_check_progress(
    bbclient: BirdBuddy,
    graphql_mock: AsyncMock,
    payload: dict,
    expected_type: type,
):
    """check_progress returns Progress while pending, Report once complete."""
    graphql_mock.side_effect = [
        {"data": {"sightingCreateCheckProgress": payload}}
    ]
    result = await bbclient.sighting_create_check_progress(
        sighting_create_id="test-create-id", watching_id="test-watching-id"
    )
    assert isinstance(result, expected_type)
    graphql_mock.assert_called_once_with(
        query=ANY,
        variables={
            "sightingCreateCheckProgressInput": {
                "sightingCreateId": "test-create-id",
                "watchingId": "test-watching-id",
            }
        },
        headers=ANY,
    )


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
