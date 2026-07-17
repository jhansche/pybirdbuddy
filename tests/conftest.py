"""Shared pytest fixtures for the birdbuddy test suite."""

from collections.abc import Iterator
import pathlib
from unittest import mock
from unittest.mock import AsyncMock

import pytest
import yaml

from birdbuddy.client import BirdBuddy


def load_fixture(filename: str) -> str:
    """Read a fixture file from ``tests/fixtures`` and return its text.

    Args:
        filename: The fixture file name under ``tests/fixtures``.

    Returns:
        The file contents as text.
    """
    return pathlib.Path(__file__).parent.joinpath("fixtures", filename).read_text()


@pytest.fixture(name="issue_40")
def issue_40_yaml_fixture() -> dict:
    """Load the issue-40 postcard sighting fixture."""
    return yaml.load(load_fixture("issue-40.yaml"), Loader=yaml.Loader)


@pytest.fixture(name="bbclient")
def logged_in_client() -> BirdBuddy:
    """Return a BirdBuddy client pre-seeded with fake tokens."""
    return BirdBuddy(
        "user@email",
        "passw0rd",
        refresh_token="refresh",
        access_token="access",
    )


@pytest.fixture(name="graphql_mock")
def mock_graphql() -> Iterator[AsyncMock]:
    """Patch GraphqlClient.execute_async and yield the mock."""
    with mock.patch(
        "python_graphql_client.graphql_client.GraphqlClient.execute_async"
    ) as method:
        yield method
