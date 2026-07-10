"""Dump real Bird Buddy payloads for building test fixtures (needs creds).

Reads ``BB_EMAIL`` and ``BB_PASSWORD`` from the environment, logs in, and
captures read-only payloads (profile, collections, feed) plus a postcard
reanalyze. It writes two files, both git-ignored:

* ``birdbuddy_payload.dump.json`` -- the raw capture (real account data).
* ``birdbuddy_payload.sanitized.json`` -- the same data with identifying
  values scrubbed, suitable for copying into ``tests/fixtures`` after review.

By default the script is non-destructive: it reads the profile, collections
and feed, and *reanalyzes* postcards (running AI inference, exactly what the
app's identify button does). It only *collects* a postcard -- a real,
irreversible change to your account -- when ``BB_COLLECT_POSTCARD_ID`` names a
specific postcard to collect.

Usage:
    BB_EMAIL=you@example.com BB_PASSWORD=... python scripts/dump_payloads.py
    # opt in to the destructive collect on ONE postcard you have chosen:
    BB_COLLECT_POSTCARD_ID=<feed-item-id> ... python scripts/dump_payloads.py
"""

import asyncio
import json
import os
from pathlib import Path
import re
from typing import Any
import uuid

from birdbuddy import queries
from birdbuddy.client import BirdBuddy

_RAW = Path(__file__).resolve().parent.parent / "birdbuddy_payload.dump.json"
_SANITIZED = _RAW.with_name("birdbuddy_payload.sanitized.json")

# How many new postcards to reanalyze (captures both inference states).
_REANALYZE_LIMIT = 3

# Capture via the LIBRARY's own queries (never hand-copied) so the fixtures
# cannot drift from what the client actually sends -- that drift is what once
# hid a malformed collect query and a metadata-only reanalyze from the tests.
_REANALYZE = queries.birds.POSTCARD_REANALYZE
_COLLECT = queries.birds.POSTCARD_COLLECT

# --- Sanitizer ------------------------------------------------------------

# Fixed namespace so UUID remapping is stable across runs (fixtures diff
# cleanly). The value is arbitrary; only its constancy matters.
_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Keys whose string values identify a person, device, or location.
_TOKEN_KEYS = {"accessToken", "refreshToken", "token", "reportToken"}
_EMAIL_KEYS = {"email", "memberEmail"}
_NAME_KEYS = {"name", "feederName", "memberName", "ownerName"}
_SERIAL_KEYS = {"serialNumber"}
_URL_KEYS = {"avatarUrl", "contentUrl", "thumbnailUrl", "iconUrl", "mediaUrl"}
_CITY_KEYS = {"city", "locationCity"}
_COUNTRY_KEYS = {"country", "locationCountry"}


def _sanitize_key(key: str) -> str:
    """Remap a dict key that is itself a UUID (e.g. keyed-by-id sections)."""
    if _UUID_RE.match(key):
        return str(uuid.uuid5(_NAMESPACE, key))
    return key


def _sanitize_str(value: str, key: str | None, keep_name: bool) -> str:
    """Scrub one string value based on its key, preserving public data.

    Args:
        value: The raw string.
        key: The dict key the string was stored under, if any.
        keep_name: True inside a species object, where ``name`` is a public
            species name and must be preserved.

    Returns:
        The scrubbed (or unchanged) string.
    """
    if key in _TOKEN_KEYS:
        return "REDACTED_TOKEN"
    if key in _EMAIL_KEYS:
        return "owner@example.invalid"
    if key in _SERIAL_KEYS:
        return "SN-TEST-0001"
    if key in _URL_KEYS:
        return "https://example.invalid/asset"
    if key in _CITY_KEYS:
        return "Testville"
    if key in _COUNTRY_KEYS:
        return "US"
    if key in _NAME_KEYS and not keep_name:
        return "Test Bird Buddy" if key in {"name", "feederName"} else "Tester"
    if _UUID_RE.match(value):
        return str(uuid.uuid5(_NAMESPACE, value))
    return value


def _sanitize(
    obj: Any, key: str | None = None, keep_name: bool = False
) -> Any:
    """Recursively scrub identifying data, preserving structure and enums.

    UUIDs are remapped deterministically and personal fields (tokens, email,
    names, serials, URLs, location) are replaced with stable fakes. Enums,
    numeric metrics, timestamps, booleans, and public species names are kept.

    Args:
        obj: The value to sanitize.
        key: The dict key ``obj`` was stored under, for context.
        keep_name: True while inside a species object (public name).

    Returns:
        The sanitized value.
    """
    if isinstance(obj, dict):
        typename = str(obj.get("__typename", ""))
        child_keep = keep_name or key == "species" or "Species" in typename
        return {
            _sanitize_key(k): _sanitize(v, k, child_keep)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_sanitize(v, key, keep_name) for v in obj]
    if isinstance(obj, str):
        return _sanitize_str(obj, key, keep_name)
    return obj


# --- Capture --------------------------------------------------------------


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
    """Log in and capture the read-only payloads (and gated collect)."""
    bb = BirdBuddy(os.environ["BB_EMAIL"], os.environ["BB_PASSWORD"])
    out: dict[str, Any] = {}

    profile = await bb._make_request(query=queries.me.ME)  # noqa: SLF001
    out["me"] = profile["me"]

    collections = await bb._make_request(  # noqa: SLF001
        query=queries.me.COLLECTIONS
    )
    out["collections"] = collections["me"]["collections"]

    postcards = await bb.new_postcards()
    out["new_postcards"] = [p.data for p in postcards]

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
    """Dump raw and sanitized payloads to git-ignored files."""
    data = asyncio.run(_collect())
    _RAW.write_text(json.dumps(data, indent=2, default=str))
    _SANITIZED.write_text(json.dumps(_sanitize(data), indent=2, default=str))
    print(f"Wrote {_RAW} (real account data; do not commit)")
    print(f"Wrote {_SANITIZED} (review, then copy into tests/fixtures)")


if __name__ == "__main__":
    main()
