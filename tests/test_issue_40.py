"""Tests for postcard finishing strategies (regression for issue #40)."""

from unittest.mock import ANY, AsyncMock, call

import pytest

from birdbuddy.client import BirdBuddy
from birdbuddy.sightings import PostcardSighting, SightingFinishStrategy


@pytest.mark.asyncio
async def test_sighting_recognized_single(
    bbclient: BirdBuddy,
    issue_40: dict,
    graphql_mock: AsyncMock,
):
    """RECOGNIZED strategy finishes without extra identification calls."""
    # By default, no extra identification happens
    graphql_mock.side_effect = [
        # sightingReportPostcardFinish
        {"data": {"sightingReportPostcardFinish": {"success": True}}},
    ]
    result = await bbclient.finish_postcard(
        issue_40["postcard"]["id"],
        PostcardSighting(issue_40["sighting"]),
        strategy=SightingFinishStrategy.RECOGNIZED,
    )
    graphql_mock.assert_called_once_with(
        query=ANY,
        variables={
            "sightingReportPostcardFinishInput": {
                "defaultCoverMedia": [
                    {
                        "mediaId": "e579818d-cb68-40d2-876c-fcfdf3483eb6",
                        "speciesId": "35379866-a4c6-4991-a2af-e6da93eaec4f",
                    }
                ],
                "notSelectedMediaIds": [],
                # postcard.id
                "feedItemId": "ea7c32bb-e95b-4fe6-a8ef-64134c1ae97e",
                "reportToken": ANY,
            }
        },
        headers=ANY,
    )
    assert result is True


@pytest.mark.asyncio
async def test_sighting_best_guess(
    bbclient: BirdBuddy,
    issue_40: dict,
    graphql_mock: AsyncMock,
):
    """BEST_GUESS chooses the highest-confidence species, then finishes."""
    original_report = issue_40["sighting"]["sightingReport"]
    # Drop the recognized sighting to exercise the no-recognized fallback.
    original_report["sightings"] = [
        s
        for s in original_report["sightings"]
        if s["__typename"] != "SightingRecognizedBirdUnlocked"
    ]
    modified_report = original_report.copy()
    modified_report["reportToken"] = original_report["reportToken"] + ".altered"
    # BEST_GUESS attempts to choose the best species match.
    graphql_mock.side_effect = [
        # sightingChooseSpecies
        {
            "data": {
                # new report data
                "sightingChooseSpecies": modified_report
            }
        },
        # sightingReportPostcardFinish
        {"data": {"sightingReportPostcardFinish": {"success": True}}},
    ]
    result = await bbclient.finish_postcard(
        issue_40["postcard"]["id"],
        PostcardSighting(issue_40["sighting"]),
        strategy=SightingFinishStrategy.BEST_GUESS,
    )
    graphql_mock.assert_has_calls(
        calls=[
            call(
                query=ANY,  # sightingChooseSpecies
                variables={
                    "sightingChooseSpeciesInput": {
                        "reportToken": ANY,
                        "speciesId": "81a13484-a311-477d-8011-8873bd3c053c",
                        "sightingId": "233000f8-ecbe-430c-9227-2c826866323f",
                    },
                },
                headers=ANY,
            ),
            call(
                query=ANY,  # sightingReportPostcardFinish
                variables={
                    "sightingReportPostcardFinishInput": {
                        "defaultCoverMedia": [],
                        "notSelectedMediaIds": [],
                        # postcard.id
                        "feedItemId": "ea7c32bb-e95b-4fe6-a8ef-64134c1ae97e",
                        "reportToken": modified_report["reportToken"],
                    }
                },
                headers=ANY,
            ),
        ],
        any_order=False,
    )
    assert result is True


@pytest.mark.asyncio
async def test_sighting_anomaly_correction(
    bbclient: BirdBuddy,
    issue_40: dict,
    graphql_mock: AsyncMock,
):
    """A recognized species is propagated to correct an anomaly."""
    original_report = issue_40["sighting"]["sightingReport"]
    modified_report = original_report.copy()
    modified_report["reportToken"] = original_report["reportToken"] + ".altered"
    # BEST_GUESS attempts to choose the best species match.
    graphql_mock.side_effect = [
        # sightingChooseSpecies
        {"data": {"sightingChooseSpecies": modified_report}},
        # sightingReportPostcardFinish
        {"data": {"sightingReportPostcardFinish": {"success": True}}},
    ]
    result = await bbclient.finish_postcard(
        issue_40["postcard"]["id"],
        PostcardSighting(issue_40["sighting"]),
        strategy=SightingFinishStrategy.BEST_GUESS,
    )
    graphql_mock.assert_has_calls(
        calls=[
            call(
                query=ANY,  # sightingChooseSpecies
                variables={
                    "sightingChooseSpeciesInput": {
                        "reportToken": ANY,
                        # anomaly correction replaces the anomaly (Fish Crow)
                        # with expected (Carolina Wren)
                        "speciesId": "35379866-a4c6-4991-a2af-e6da93eaec4f",
                        "sightingId": "233000f8-ecbe-430c-9227-2c826866323f",
                    },
                },
                headers=ANY,
            ),
            call(
                query=ANY,  # sightingReportPostcardFinish
                variables={
                    "sightingReportPostcardFinishInput": {
                        "defaultCoverMedia": [
                            {
                                "mediaId": "e579818d-cb68-40d2-876c-fcfdf3483eb6",  # noqa: E501
                                "speciesId": "35379866-a4c6-4991-a2af-e6da93eaec4f",  # noqa: E501
                            }
                        ],
                        "notSelectedMediaIds": [],
                        # postcard.id
                        "feedItemId": "ea7c32bb-e95b-4fe6-a8ef-64134c1ae97e",
                        "reportToken": modified_report["reportToken"],
                    }
                },
                headers=ANY,
            ),
        ],
        any_order=False,
    )
    assert result is True
