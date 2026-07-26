"""Dump real Bird Buddy payloads for building test fixtures (needs creds).

Reads ``BB_EMAIL`` and ``BB_PASSWORD`` (a local ``.env`` is loaded via
python-dotenv), logs in, and captures the feeders, new postcards, and the
postcard -> sighting flow. Each risky call is captured so a server error
(e.g. the postcard ``INTERNAL_SERVER_ERROR``) lands in the dump rather than
aborting the run. It writes two git-ignored files:

* ``birdbuddy_payload.dump.json`` -- the raw capture (real account data).
* ``birdbuddy_payload.sanitized.json`` -- the same data with identifying
  values scrubbed, suitable for copying into ``tests/fixtures`` after review.

Usage:
    Copy ``.env.example`` to ``.env`` and fill in your credentials (or export
    BB_EMAIL / BB_PASSWORD), then run:
        python scripts/dump_payloads.py
"""

import asyncio
import base64
import json
import os
from pathlib import Path
import re
from typing import Any
import uuid

from dotenv import load_dotenv

from birdbuddy.client import BirdBuddy

_RAW = Path(__file__).resolve().parent.parent / "birdbuddy_payload.dump.json"
_SANITIZED = _RAW.with_name("birdbuddy_payload.sanitized.json")

# Fixed namespace so UUID remapping is stable across runs (fixtures diff
# cleanly). The value is arbitrary; only its constancy matters.
_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Opaque auth tokens, replaced wholesale. The report token is scrubbed in
# place (see _sanitize_report_token) so dumps stay usable as test fixtures.
_TOKEN_KEYS = {"accessToken", "refreshToken", "token"}
_EMAIL_KEYS = {"email", "memberEmail"}
_NAME_KEYS = {"name", "feederName", "memberName", "ownerName"}
_SERIAL_KEYS = {"serialNumber"}
_URL_KEYS = {"avatarUrl", "contentUrl", "thumbnailUrl", "iconUrl", "mediaUrl"}
_CITY_KEYS = {"city", "locationCity"}
_COUNTRY_KEYS = {"country", "locationCountry"}


def _sanitize_key(key: str) -> str:
    """Remap a dict key that is itself a UUID (e.g. keyed-by-id sections).

    Args:
        key: The dict key to inspect.

    Returns:
        The deterministically remapped UUID when ``key`` is a UUID, otherwise
        the original key unchanged.
    """
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
    if key == "reportToken":
        return _sanitize_report_token(value)
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


def _sanitize(obj: Any, key: str | None = None, keep_name: bool = False) -> Any:
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
        return {_sanitize_key(k): _sanitize(v, k, child_keep) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v, key, keep_name) for v in obj]
    if isinstance(obj, str):
        return _sanitize_str(obj, key, keep_name)
    return obj


def _sanitize_report_token(value: str) -> str:
    """Scrub a report token in place, keeping it decodable.

    Signed tokens (``header.payload.signature``) are decoded, their embedded
    report is sanitized, and they are re-encoded with a placeholder signature
    (the library never verifies it). Plain JSON tokens are scrubbed directly.
    A malformed token raises, so a changed token format is caught rather than
    silently blanked.

    Args:
        value: The raw report token, signed or plain JSON.

    Returns:
        The token with account ids remapped, still decodable.
    """
    if value.count(".") == 2:
        header, b64payload, _sig = value.split(".")
        payload = json.loads(base64.b64decode(b64payload + "==", validate=False))
        inner = payload.get("reportToken")
        if isinstance(inner, str):
            payload["reportToken"] = json.dumps(_sanitize(json.loads(inner)))
        repacked = base64.urlsafe_b64encode(json.dumps(payload).encode())
        return f"{header}.{repacked.rstrip(b'=').decode()}.REDACTED_SIGNATURE"
    return json.dumps(_sanitize(json.loads(value)))


async def _capture(label: str, coro: Any, out: dict[str, Any]) -> Any:
    """Await ``coro``, storing its payload or error under ``label``.

    Args:
        label: The key to store the result (or error) under in ``out``.
        coro: The awaitable API call to run.
        out: The dump dict the payload or error is written into.

    Returns:
        The awaited result, or ``None`` if the call raised.
    """
    try:
        result = await coro
    except Exception as err:  # noqa: BLE001
        out[label] = {"error": repr(err)}
        return None
    out[label] = result.data if hasattr(result, "data") else result
    return result


async def _collect() -> dict[str, Any]:
    """Log in and collect the postcard/sighting payloads.

    Returns:
        A dict mapping each captured step (feeders, new_postcards,
        reanalyze_postcard, sighting_from_postcard, sighting_create) to its
        payload, or an ``{"error": ...}`` entry when that step failed.
    """
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
    """Dump raw and sanitized payloads to git-ignored files."""
    load_dotenv()
    data = asyncio.run(_collect())
    _RAW.write_text(json.dumps(data, indent=2, default=str))
    _SANITIZED.write_text(json.dumps(_sanitize(data), indent=2, default=str))
    print(f"Wrote {_RAW} (real account data; do not commit)")
    print(f"Wrote {_SANITIZED} (review, then copy into tests/fixtures)")


if __name__ == "__main__":
    main()
