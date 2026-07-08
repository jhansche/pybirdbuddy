"""Dump real Bird Buddy payloads for debugging (requires account creds).

Reads ``BB_EMAIL`` and ``BB_PASSWORD`` from the environment, logs in, and
captures the postcard-collection flow to a local, git-ignored file. Operation
text is embedded here (not imported from birdbuddy.queries) so the script is
self-contained while the library's collect queries are still being built.

By default the script is non-destructive: it reads the feed and *reanalyzes*
postcards (running AI inference, exactly what the app's identify button does).
It only *collects* a postcard -- a real, irreversible change to your account --
when ``BB_COLLECT_POSTCARD_ID`` names a specific postcard to collect.

The output holds real account data, so it is git-ignored; sanitize it before
reusing it as a test fixture.

Usage:
    BB_EMAIL=you@example.com BB_PASSWORD=... python scripts/dump_payloads.py
    # opt in to the destructive collect on ONE postcard you have chosen:
    BB_COLLECT_POSTCARD_ID=<feed-item-id> ... python scripts/dump_payloads.py
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

# How many new postcards to reanalyze (captures both inference states).
_REANALYZE_LIMIT = 3

# Rich reanalyze: capture a postcard's full analyzed state (inference mode,
# confidence levels, assigned species, preview) -- fields verified against the
# 2026-07 schema.
_REANALYZE = """
mutation reanalyze($feedItemId: ID!) {
  inferenceExternalPostcardReanalyze(feedItemId: $feedItemId) {
    updatedFeedItem {
      __typename
      ... on FeedItemNewPostcard {
        id
        inferenceExecutionMode
        inferenceType
        inferenceConfidenceLevel
        reanalyzeAvailability
        mediaSpeciesNameIdentificationConfidenceLevel
        mediaSpeciesNameAssignmentAvailability
        mediaSpeciesStateDisplay { state }
        medias { __typename id createdAt }
        mediaSpeciesAssignedName { id name markedAsNew species { id name } }
        sightingReportPreview { sightings { __typename } }
      }
    }
  }
}
"""

# Destructive: collect the postcard into the account. Only sent when opted in.
_COLLECT = """
mutation postcardCollect(
  $feedItemId: ID!, $postcardCollectInput: PostcardCollectInput
) {
  postcardCollect(feedItemId: $feedItemId, input: $postcardCollectInput) {
    collectedPostcard {
      __typename
      id
      species { id name }
      hasMysteryVisitor
      hasNewSpecies
      inferenceExecutionMode
      mediaSpeciesAssignedName { id name species { id name } }
      medias { __typename id }
    }
    postcardCollectedDetails { isFirstCollectedPostcard }
  }
}
"""


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
    """Log in and capture the postcard-collection payloads."""
    bb = BirdBuddy(os.environ["BB_EMAIL"], os.environ["BB_PASSWORD"])
    out: dict[str, Any] = {}
    await bb.refresh()
    out["feeders"] = {k: v.data for k, v in bb.feeders.items()}

    postcards = await bb.new_postcards()
    out["new_postcards"] = [p.data for p in postcards]
    if not postcards:
        return out

    # Reanalyze the first few postcards (non-destructive AI inference); the
    # response reveals each one's prior inference state + confidence + preview.
    out["reanalyze"] = {}
    for postcard in postcards[:_REANALYZE_LIMIT]:
        await _capture(
            postcard.node_id,
            bb._make_request(  # noqa: SLF001
                query=_REANALYZE, variables={"feedItemId": postcard.node_id}
            ),
            out["reanalyze"],
        )

    # Destructive collect: only when a specific postcard id is opted in.
    collect_id = os.environ.get("BB_COLLECT_POSTCARD_ID")
    if collect_id:
        await _capture(
            "postcard_collect",
            bb._make_request(  # noqa: SLF001
                query=_COLLECT,
                variables={
                    "feedItemId": collect_id,
                    "postcardCollectInput": {"share": False},
                },
            ),
            out,
        )
    return out


def main() -> None:
    """Dump payloads to the git-ignored output file."""
    data = asyncio.run(_collect())
    _OUTPUT.write_text(json.dumps(data, indent=2, default=str))
    print(f"Wrote {_OUTPUT} (real account data; do not commit)")


if __name__ == "__main__":
    main()
