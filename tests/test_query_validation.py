"""Validate every library GraphQL query against the committed schema.

``tests/test_schema.py`` only checks that the *input types* referenced by the
queries exist; it cannot catch a malformed field selection or a missing field
argument. This module parses each query string in ``birdbuddy.queries`` and
runs graphql-core's ``validate()`` against the introspection schema in
``tests/fixtures/schema.json``, so an invalid selection fails ``make check``.
"""

import json
import pathlib

from graphql import build_client_schema, parse, validate
import pytest

from birdbuddy import queries

_SCHEMA = pathlib.Path(__file__).parent / "fixtures" / "schema.json"


def _query_constants() -> list[tuple[str, str]]:
    """Collect ``(label, query)`` for every query string in birdbuddy.queries.

    Returns:
        Pairs of ``"module.NAME"`` and the query text, for each uppercase
        string constant that looks like a GraphQL document.
    """
    found: list[tuple[str, str]] = []
    for module_name in queries.__all__:
        module = getattr(queries, module_name)
        for attr in dir(module):
            value = getattr(module, attr)
            # Public UPPER_CASE constants are complete operations; skip the
            # leading-underscore fragment building blocks (e.g.
            # _COLLECTED_POSTCARD_FIELDS), which are invalid standalone.
            if (
                attr.isupper()
                and not attr.startswith("_")
                and isinstance(value, str)
                and "{" in value
            ):
                found.append((f"{module_name}.{attr}", value))
    return found


_QUERIES = _query_constants()


@pytest.fixture(name="schema", scope="module")
def _schema():
    """Build the client schema from the committed introspection JSON."""
    return build_client_schema(json.loads(_SCHEMA.read_text()))


@pytest.mark.parametrize(
    ("label", "query"),
    _QUERIES,
    ids=[label for label, _ in _QUERIES],
)
def test_query_validates_against_schema(label, query, schema):
    """Each library query is valid GraphQL against the current schema."""
    errors = validate(schema, parse(query))
    assert not errors, f"{label}: {[e.message for e in errors]}"
