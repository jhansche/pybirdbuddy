import pathlib
from unittest import mock
from unittest.mock import AsyncMock

import pytest
import yaml

from birdbuddy.client import BirdBuddy


def load_fixture(filename: str) -> str:
    return pathlib.Path(__file__).parent.joinpath("fixtures", filename).read_text()


@pytest.fixture(name="issue_40")
def issue_40_yaml_fixture() -> dict:
    return yaml.load(load_fixture("issue-40.yaml"), Loader=yaml.Loader)


@pytest.fixture(name="bbclient")
def logged_in_client() -> BirdBuddy:
    client = BirdBuddy("user@email", "passw0rd", refresh_token="refresh", access_token="access")
    return client


@pytest.fixture(name="graphql_mock")
def mock_graphql() -> AsyncMock:
    with mock.patch('python_graphql_client.graphql_client.GraphqlClient.execute_async') as method:
        yield method
