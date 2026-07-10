"""Guard against drift between the library's queries and the GraphQL schema.

The committed ``fixtures/schema.json`` is refreshed with ``make schema``. The
input types the library's ``birdbuddy.queries`` documents reference are derived
at runtime and checked against the schema, so drift surfaces automatically as
queries change (no hand-maintained lists).
"""

import json
import pathlib
import re

import pytest

from birdbuddy import queries

_SCHEMA = pathlib.Path(__file__).parent / "fixtures" / "schema.json"
_SCALARS = frozenset({"ID", "Int", "String", "Boolean", "Float"})
_VAR_TYPE_RE = re.compile(r"\$\w+:\s*\[?(\w+)")


def _referenced_types() -> set[str]:
    """Collect the GraphQL input type names the library depends on."""
    types: set[str] = set()
    for module_name in queries.__all__:
        module = getattr(queries, module_name)
        for attr in dir(module):
            value = getattr(module, attr)
            if attr.isupper() and isinstance(value, str):
                types.update(_VAR_TYPE_RE.findall(value))
    return types - _SCALARS


@pytest.fixture(name="schema_types", scope="module")
def _schema_types() -> set[str]:
    """Return the set of type names defined in the committed schema."""
    data = json.loads(_SCHEMA.read_text())
    return {t["name"] for t in data["__schema"]["types"] if t.get("name")}


def test_referenced_types_exist(schema_types: set[str]) -> None:
    """Every GraphQL type the library's queries reference exists in schema."""
    missing = sorted(_referenced_types() - schema_types)
    assert not missing, f"types missing from schema: {missing}"
