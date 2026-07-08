"""Characterization tests for the birdbuddy.sightings model logic.

These pin the *current* behavior of the sighting-report logic (the code the
postcard finishing flow depends on) so a later rewrite has a safety net.
"""

import base64
import json

import pytest

from birdbuddy.sightings import (
    SightingFinishStrategy,
    SightingReport,
    SightingType,
)


def test_sighting_type_unknown_falls_back():
    """An unrecognized __typename maps to UNKNOWN."""
    assert SightingType("NotARealType") is SightingType.UNKNOWN


@pytest.mark.parametrize(
    ("typename", "recognized", "unlocked"),
    [
        ("SightingRecognizedBird", True, False),
        ("SightingRecognizedBirdUnlocked", True, True),
        ("SightingCantDecideWhichBird", False, False),
        ("SightingRecognizedMysteryVisitor", False, False),
    ],
)
def test_sighting_type_flags(typename, recognized, unlocked):
    """is_recognized / is_unlocked classify the sighting types."""
    st = SightingType(typename)
    assert st.is_recognized is recognized
    assert st.is_unlocked is unlocked


def test_token_json_plain():
    """A plain (undotted) reportToken is parsed as JSON."""
    report = SightingReport({"reportToken": json.dumps({"reportItems": []})})
    assert report.token_json == {"reportItems": []}


def test_token_json_missing_or_bad():
    """A missing token yields {}, and undecodable JSON is swallowed to {}."""
    assert SightingReport({}).token_json == {}
    assert SightingReport({"reportToken": "not json"}).token_json == {}


def test_decode_signed_token():
    """A 3-part signed token decodes to its nested reportToken."""

    def b64(obj: object) -> str:
        raw = json.dumps(obj).encode() if not isinstance(obj, bytes) else obj
        return base64.b64encode(raw).decode().rstrip("=")

    inner = json.dumps({"reportItems": [{"matchToken": "m1"}]})
    header = b64({"alg": "none"})
    payload = b64({"reportToken": inner})
    signed = f"{header}.{payload}.{b64(b'x')}"
    report = SightingReport({"reportToken": signed})
    assert report.token_json == {"reportItems": [{"matchToken": "m1"}]}


def _report(sightings: list[dict], token: object = None) -> SightingReport:
    return SightingReport(
        {"reportToken": json.dumps(token or {}), "sightings": sightings}
    )


def test_finishing_strategy_recognized():
    """A recognized sighting is finished as RECOGNIZED."""
    report = _report(
        [
            {
                "id": "s1",
                "__typename": "SightingRecognizedBird",
                "species": {"id": "sp1"},
            }
        ]
    )
    _, mod = report.sighting_finishing_strategies()["s1"]
    assert mod.strategy is SightingFinishStrategy.RECOGNIZED


def test_finishing_strategy_propagates_recognized_species():
    """A recognized species is propagated to a can't-decide sighting."""
    report = _report(
        [
            {
                "id": "s1",
                "__typename": "SightingRecognizedBird",
                "species": {"id": "sp1"},
            },
            {"id": "s2", "__typename": "SightingCantDecideWhichBird"},
        ]
    )
    _, mod = report.sighting_finishing_strategies()["s2"]
    assert mod.strategy is SightingFinishStrategy.BEST_GUESS
    assert mod.data == {
        "confidence": 100,
        "speciesCode": "sp1",
        "type": "BIRD",
    }


def test_finishing_strategy_mystery_fallback():
    """With nothing recognized or matched, a sighting falls back to MYSTERY."""
    report = _report([{"id": "s3", "__typename": "SightingNoBird"}])
    _, mod = report.sighting_finishing_strategies()["s3"]
    assert mod.strategy is SightingFinishStrategy.MYSTERY


def test_highest_confidence_matches_from_token():
    """Match tokens map to the highest-confidence BIRD item in the token."""
    token = {
        "reportItems": [
            {
                "matchToken": "m1",
                "items": [
                    {"type": "BIRD", "confidence": 40, "speciesCode": "a"},
                    {"type": "BIRD", "confidence": 90, "speciesCode": "b"},
                    {"type": "NOISE", "confidence": 99, "speciesCode": "x"},
                ],
            }
        ]
    }
    matches = _report([], token=token).highest_confidence_matches
    match = matches["m1"]
    assert match is not None
    assert match["speciesCode"] == "b"
    assert match["confidence"] == 90
