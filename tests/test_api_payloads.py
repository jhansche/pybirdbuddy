"""Tests exercising the models against a sanitized real API payload.

``tests/fixtures/api_payloads.json`` is a sanitized capture of live responses
(2026-07): identifying values are replaced, structure and enum values are
preserved. These tests pin the current API shapes the models parse.
"""

from birdbuddy.feed import FeedNode, FeedNodeType
from birdbuddy.feeder import Feeder, FeederState, MetricState, PowerProfile
from birdbuddy.sightings import (
    PostcardSighting,
    SightingFinishStrategy,
    SightingType,
)


def test_owner_feeder_parses_from_real_payload(api_payloads):
    """An owner feeder payload parses into the expected model values.

    The real response carries powerProfile, so power_profile resolves
    correctly (the "STANDARD" default quirk never applies here).
    """
    feeder = Feeder(next(iter(api_payloads["feeders"].values())))
    assert feeder.is_owner is True
    assert feeder.name == "Test Bird Buddy"
    assert feeder.state is FeederState.DEEP_SLEEP
    assert feeder.battery.percentage == 92
    assert feeder.battery.state is MetricState.HIGH
    assert feeder.signal.rssi == -70
    assert feeder.power_profile is PowerProfile.STANDARD
    # FeederForOwner nests location as location{city,country}; this property
    # reads flat locationCity/locationCountry (the member/public shape), so an
    # owner feeder yields (None, None). Pinned here; see the feeder.py TODO.
    assert feeder.location == (None, None)


def test_new_postcards_parse_as_feed_nodes(api_payloads):
    """The captured new-postcard feed items parse as NewPostcard nodes."""
    postcards = api_payloads["new_postcards"]
    assert len(postcards) == 20
    node = FeedNode(postcards[0])
    assert node.node_type is FeedNodeType.NewPostcard
    assert node.created_at is not None


def test_postcard_sighting_parses_from_real_payload(api_payloads):
    """A real sighting_from_postcard payload parses into the models."""
    sighting = PostcardSighting(api_payloads["sighting_from_postcard"])
    assert sighting.feeder["name"] == "Test Bird Buddy"
    assert len(sighting.medias) == 10
    assert all(not m.is_video for m in sighting.medias)
    assert len(sighting.video_media) == 1
    assert sighting.video_media[0].is_video is True

    report = sighting.report
    assert len(report.sightings) == 1
    only = report.sightings[0]
    assert only.sighting_type is SightingType.SPECIES_RECOGNIZED
    assert only.is_recognized is True
    assert only.species.name == "Northern Cardinal"

    # A single recognized sighting finishes as RECOGNIZED.
    _, mod = report.sighting_finishing_strategies()[only.id]
    assert mod.strategy is SightingFinishStrategy.RECOGNIZED


def test_sighting_create_error_documents_current_drift(api_payloads):
    """The captured sighting_create call fails: the input type is gone.

    This pins the live schema drift behind pybirdbuddy #29: the API no
    longer defines SightingCreateInput, so sighting_create is broken.
    """
    error = api_payloads["sighting_create"]["error"]
    assert "SightingCreateInput" in error
    assert "GRAPHQL_VALIDATION_FAILED" in error

    reanalyze = api_payloads["reanalyze_postcard"]["updatedFeedItem"]
    assert reanalyze["inferenceExecutionMode"] == "MANUAL_COMPLETED"
