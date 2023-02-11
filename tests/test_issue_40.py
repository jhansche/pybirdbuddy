from unittest.mock import AsyncMock, ANY, call

import pytest

from birdbuddy.client import BirdBuddy
from birdbuddy.sightings import PostcardSighting, SightingFinishStrategy


@pytest.mark.asyncio
async def test_sighting_recognized_single(
    bbclient: BirdBuddy,
    issue_40: dict,
    graphql_mock: AsyncMock,
):
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
    original_report = issue_40["sighting"]["sightingReport"]
    modified_report = original_report.copy()
    modified_report["reportToken"] = original_report["reportToken"] + ".altered"
    # with BEST_GUESS strategy, we will attempt to choose the best species match
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
                        # FIXME: This is a bad selection!
                        #  Add a way to make this species selection more intelligent.
                        #  Target species=35379866-a4c6-4991-a2af-e6da93eaec4f
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
                        "defaultCoverMedia": [
                            {
                                "mediaId": "e579818d-cb68-40d2-876c-fcfdf3483eb6",
                                "speciesId": "35379866-a4c6-4991-a2af-e6da93eaec4f",
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


@pytest.mark.skip(reason="issue#40")
@pytest.mark.asyncio
async def test_sighting_anomaly_correction(
    bbclient: BirdBuddy,
    issue_40: dict,
    graphql_mock: AsyncMock,
):
    original_report = issue_40["sighting"]["sightingReport"]
    modified_report = original_report.copy()
    modified_report["reportToken"] = original_report["reportToken"] + ".altered"
    # with BEST_GUESS strategy, we will attempt to choose the best species match
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
                                "mediaId": "e579818d-cb68-40d2-876c-fcfdf3483eb6",
                                "speciesId": "35379866-a4c6-4991-a2af-e6da93eaec4f",
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
