"""Dump real Bird Buddy payloads for debugging (requires account creds).

Reads ``BB_EMAIL`` and ``BB_PASSWORD`` from the environment, logs in, and
writes the feed, new postcards, and the postcard -> sighting flow to a local,
git-ignored file. Each risky call is captured so a server error (e.g. the
postcard ``INTERNAL_SERVER_ERROR``) shows up in the dump rather than aborting.

The output holds real account data, so it is git-ignored; sanitize it before
reusing it as a test fixture.

Usage:
    BB_EMAIL=you@example.com BB_PASSWORD=... python scripts/dump_payloads.py
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from birdbuddy.client import BirdBuddy

_OUTPUT = (
    Path(__file__).resolve().parent.parent / "birdbuddy_payload.dump.json"
)


async def _capture(label: str, coro: Any, out: dict[str, Any]) -> Any:
    """Await ``coro``, storing its payload or error under ``label``."""
    try:
        result = await coro
    except Exception as err:  # noqa: BLE001
        out[label] = {"error": repr(err)}
        return None
    out[label] = result.data if hasattr(result, "data") else result
    return result


async def _collect() -> dict[str, Any]:
    """Log in and collect the postcard/sighting payloads."""
    bb = BirdBuddy(os.environ["BB_EMAIL"], os.environ["BB_PASSWORD"])
    out: dict[str, Any] = {}
    await bb.refresh()
    out["feeders"] = {k: v.data for k, v in bb.feeders.items()}

    postcards = await bb.new_postcards()
    out["new_postcards"] = [p.data for p in postcards]
    if not postcards:
        return out

    postcard = postcards[0]
    # Reanalyze first (PR #35), then convert; capture either path's error.
    await _capture("reanalyze_postcard", bb.reanalyze_postcard(postcard), out)
    sighting = await _capture(
        "sighting_from_postcard", bb.sighting_from_postcard(postcard), out
    )
    if sighting is not None and sighting.medias:
        media_ids = [m.id for m in sighting.medias]
        await _capture("sighting_create", bb.sighting_create(media_ids), out)
    return out


def main() -> None:
    """Dump payloads to the git-ignored output file."""
    data = asyncio.run(_collect())
    _OUTPUT.write_text(json.dumps(data, indent=2, default=str))
    print(f"Wrote {_OUTPUT} (contains PII; do not commit)")


if __name__ == "__main__":
    main()
