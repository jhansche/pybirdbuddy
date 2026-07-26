"""Dump the Bird Buddy GraphQL schema to the committed fixture."""

import asyncio
import json
from pathlib import Path

from birdbuddy.client import BirdBuddy

_FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "schema.json"


def main() -> None:
    """Fetch the schema via introspection and write it to the fixture."""
    schema = asyncio.run(BirdBuddy().dump_schema())
    _FIXTURE.write_text(json.dumps(schema, indent=2))
    print(f"Wrote {_FIXTURE}")


if __name__ == "__main__":
    main()
