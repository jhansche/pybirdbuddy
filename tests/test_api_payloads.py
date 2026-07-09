"""Tests exercising the models against a sanitized real API payload.

``tests/fixtures/api_payloads.json`` is a sanitized capture of live responses
(2026-07): identifying values are replaced, structure and enum values are
preserved. These tests pin the current API shapes the models parse.
"""

from birdbuddy.feed import FeedNode, FeedNodeType
from birdbuddy.feeder import Feeder, FeederState, MetricState, PowerProfile


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
