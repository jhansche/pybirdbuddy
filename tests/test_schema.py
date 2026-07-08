"""Guard against drift between the library's queries and the GraphQL schema.

The committed ``fixtures/schema.json`` is refreshed with ``make schema``. The
GraphQL types the library uses are derived at runtime -- input types from the
``birdbuddy.queries`` documents and object types from the ``SightingType``
enum -- and checked against the schema, so drift surfaces automatically as
queries change (no hand-maintained lists).
"""

import json
import pathlib
import re

import pytest

from birdbuddy import queries
from birdbuddy.sightings import SightingType

_SCHEMA = pathlib.Path(__file__).parent / "fixtures" / "schema.json"
_SCALARS = frozenset({"ID", "Int", "String", "Boolean", "Float"})
_VAR_TYPE_RE = re.compile(r"\$\w+:\s*\[?(\w+)")

# Input types the library still references but the API has dropped. The
# generic sightingCreate flow was removed with no equivalent; the current app
# collects via postcardCollect instead. sighting_create and
# sighting_create_check_progress are therefore non-functional against the live
# API (confirmed: GRAPHQL_VALIDATION_FAILED, "Unknown type SightingCreateInput"
# / no "sightingCreate" mutation) but are retained for backwards
# compatibility. See jhansche/pybirdbuddy#29 (schema drift).
# TODO(roger): migrate the postcard flow to postcardCollect.
_KNOWN_MISSING = frozenset(
    {"SightingCreateInput", "SightingCreateCheckProgressInput"}
)


def _referenced_types() -> set[str]:
    """Collect the GraphQL type names the library depends on."""
    types: set[str] = set()
    for module_name in queries.__all__:
        module = getattr(queries, module_name)
        for attr in dir(module):
            value = getattr(module, attr)
            if attr.isupper() and isinstance(value, str):
                types.update(_VAR_TYPE_RE.findall(value))
    types.update(
        t.value for t in SightingType if t is not SightingType.UNKNOWN
    )
    return types - _SCALARS


@pytest.fixture(name="schema_types", scope="module")
def _schema_types() -> set[str]:
    """Return the set of type names defined in the committed schema."""
    data = json.loads(_SCHEMA.read_text())
    return {t["name"] for t in data["__schema"]["types"] if t.get("name")}


def test_referenced_types_exist(schema_types: set[str]) -> None:
    """Every GraphQL type the library uses exists in the schema.

    Types known to be dropped by the API are exempted via ``_KNOWN_MISSING``.
    """
    missing = sorted(_referenced_types() - schema_types - _KNOWN_MISSING)
    assert not missing, f"types missing from schema: {missing}"
