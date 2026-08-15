"""Tests exercising the models against a sanitized real API payload.

``tests/fixtures/api_payloads.json`` is a sanitized capture of live responses
(2026-07) produced by ``scripts/dump_payloads.py``: identifying values are
replaced, structure and enum values are preserved. These tests pin the current
API shapes the models parse.
"""

from birdbuddy.feed import FeedNode, FeedNodeType
from birdbuddy.feeder import Feeder, FeederState, MetricState, PowerProfile
from birdbuddy.postcards import PostcardAnalysis


def test_owner_feeder_parses_from_real_payload(api_payloads):
    """The owner feeder in the ME payload parses into the model values."""
    feeder = Feeder(api_payloads["me"]["feeders"][0])
    assert feeder.is_owner is True
    assert feeder.name == "Test Bird Buddy"
    assert feeder.state is FeederState.READY_TO_STREAM
    assert feeder.battery.percentage == 94
    assert feeder.battery.state is MetricState.HIGH
    assert feeder.signal.rssi == -64
    assert feeder.signal.state is MetricState.MEDIUM
    assert feeder.power_profile is PowerProfile.STANDARD
    # FeederForOwner nests location as location{city,country}.
    assert feeder.location == ("Testville", "US")


def test_new_postcards_parse_as_feed_nodes(api_payloads):
    """The captured new-postcard feed items parse as NewPostcard nodes."""
    postcards = api_payloads["new_postcards"]
    assert len(postcards) == 5
    node = FeedNode(postcards[0])
    assert node.node_type is FeedNodeType.NewPostcard
    assert node.created_at is not None


def test_identify_postcard_parses_analysis(collect_flow):
    """An identified postcard yields species + media WITHOUT collecting.

    The ``reanalyze`` block is captured with the library's own
    ``POSTCARD_REANALYZE`` query, so this pins the exact shape
    ``identify_postcard`` returns.
    """
    entry = next(iter(collect_flow["reanalyze"].values()))
    item = entry["inferenceExternalPostcardReanalyze"]["updatedFeedItem"]
    analysis = PostcardAnalysis(item)
    # Recognized species come from the sighting-report preview (no collect).
    assert analysis.species
    assert all(s.name for s in analysis.species)
    # Media resolves a content URL (a sanitized placeholder in the fixture).
    assert analysis.medias
    assert analysis.medias[0].content_url
    # Feeder attribution + inference metadata are present.
    assert analysis.feeder is not None
    assert analysis.feeder.id
    assert analysis.inference_execution_mode == "MANUAL_COMPLETED"
