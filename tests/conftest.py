"""Shared pytest fixtures for the birdbuddy test suite."""

from collections.abc import Iterator
import json
import pathlib
from unittest import mock
from unittest.mock import AsyncMock

import pytest

from birdbuddy.client import BirdBuddy


def load_fixture(filename: str) -> str:
    """Read a fixture file from ``tests/fixtures`` and return its text.

    Args:
        filename: The fixture file name under ``tests/fixtures``.

    Returns:
        The file contents as text.
    """
    return (
        pathlib.Path(__file__)
        .parent.joinpath("fixtures", filename)
        .read_text()
    )


def load_json_fixture(filename: str) -> dict:
    """Read and parse a JSON fixture from ``tests/fixtures``.

    Args:
        filename: The JSON fixture file name under ``tests/fixtures``.

    Returns:
        The parsed JSON object.
    """
    return json.loads(load_fixture(filename))


@pytest.fixture(name="api_payloads")
def api_payloads_fixture() -> dict:
    """Load the sanitized real API payload fixture (2026-07 capture)."""
    return load_json_fixture("api_payloads.json")


@pytest.fixture(name="collect_flow")
def collect_flow_fixture() -> dict:
    """Load the sanitized collect-flow capture (2026-07)."""
    return load_json_fixture("collect_flow.json")


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
