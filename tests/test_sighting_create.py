from unittest.mock import AsyncMock, ANY
import pytest

from birdbuddy.client import BirdBuddy
from birdbuddy.sightings import SightingCreateProgress, SightingReport


@pytest.mark.asyncio
async def test_sighting_create(bbclient: BirdBuddy, graphql_mock: AsyncMock):
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


@pytest.mark.asyncio
async def test_sighting_create_check_progress_in_progress(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    graphql_mock.side_effect = [
        {
            "data": {
                "sightingCreateCheckProgress": {
                    "id": "test-create-id",
                    "progress": 75.0,
                    "__typename": "SightingCreateProgress",
                }
            }
        }
    ]
    result = await bbclient.sighting_create_check_progress(
        sighting_create_id="test-create-id", watching_id="test-watching-id"
    )

    assert isinstance(result, SightingCreateProgress)
    assert result.id == "test-create-id"
    assert result.progress == 75.0

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
async def test_sighting_create_check_progress_completed(
    bbclient: BirdBuddy, graphql_mock: AsyncMock
):
    graphql_mock.side_effect = [
        {
            "data": {
                "sightingCreateCheckProgress": {
                    "reportToken": "test-report-token",
                    "sightings": [
                        {
                            "id": "sighting-id-1",
                            "__typename": "SightingRecognizedBird",
                            "species": {
                                "id": "species-id-1",
                                "name": "Northern Cardinal",
                                "__typename": "SpeciesBird",
                            },
                        }
                    ],
                    "__typename": "SightingReport",
                }
            }
        }
    ]
    result = await bbclient.sighting_create_check_progress(
        sighting_create_id="test-create-id", watching_id="test-watching-id"
    )

    assert isinstance(result, SightingReport)
    assert result.token == "test-report-token"
    assert len(result.sightings) == 1
    assert result.sightings[0].id == "sighting-id-1"
    assert result.sightings[0].species.name == "Northern Cardinal"

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
async def test_reanalyze_postcard(bbclient: BirdBuddy, graphql_mock: AsyncMock):
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
    assert result["updatedFeedItem"]["inferenceExecutionMode"] == "MANUAL_COMPLETED"

    graphql_mock.assert_called_once_with(
        query=ANY,
        variables={
            "feedItemId": "postcard-id-1",
        },
        headers=ANY,
    )

