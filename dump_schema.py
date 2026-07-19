"""Dump the Bird Buddy GraphQL schema to schema.json."""

import asyncio
import json
from pathlib import Path

from birdbuddy.client import BirdBuddy

bb = BirdBuddy()
with Path("schema.json").open("w") as f:
    json.dump(asyncio.run(bb.dump_schema()), f, indent=2)
