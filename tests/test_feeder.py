"""Basic tests for the birdbuddy.feeder models."""

import logging

import pytest

from birdbuddy.feeder import (
    Battery,
    Feeder,
    FeederState,
    FeederUpdateStatus,
    MetricState,
    PowerProfile,
    Signal,
)


@pytest.mark.parametrize(
    ("enum_cls", "value", "member"),
    [
        (MetricState, "HIGH", MetricState.HIGH),
        (PowerProfile, "FRENZY_MODE", PowerProfile.FRENZY),
        (PowerProfile, "ULTRA_FRENZY_MODE", PowerProfile.ULTRA_FRENZY),
        (FeederState, "READY_TO_STREAM", FeederState.READY_TO_STREAM),
    ],
)
def test_feeder_enum_known_value(enum_cls, value, member):
    """A known raw value resolves to its enum member."""
    assert enum_cls(value) is member


@pytest.mark.parametrize(
    ("enum_cls", "unknown"),
    [
        (MetricState, MetricState.UNKNOWN),
        (PowerProfile, PowerProfile.UNKNOWN),
        (FeederState, FeederState.UNKNOWN),
    ],
)
def test_feeder_enum_unknown_falls_back(enum_cls, unknown):
    """An unrecognized value falls back to the UNKNOWN member."""
    assert enum_cls("NOT_A_REAL_VALUE") is unknown


def test_signal_and_battery():
    """Signal and Battery read their metrics and state."""
    signal = Signal({"value": -41, "state": "HIGH"})
    assert signal.rssi == -41
    assert signal.state is MetricState.HIGH

    battery = Battery({"percentage": 93, "charging": True, "state": "HIGH"})
    assert battery.percentage == 93
    assert battery.is_charging is True
    assert battery.state is MetricState.HIGH


def test_signal_and_battery_defaults():
    """Empty Signal/Battery payloads use their documented defaults."""
    assert Signal({}).rssi == -1
    assert Signal({}).state is MetricState.UNKNOWN
    assert Battery({}).percentage == 0
    assert Battery({}).is_charging is False


def test_feeder_properties():
    """Feeder exposes identity, ownership, state, and nested metrics."""
    feeder = Feeder(
        {
            "id": "f1",
            "serialNumber": "SN123",
            "name": "Backyard",
            "__typename": "FeederForOwner",
            "state": "READY_TO_STREAM",
            "battery": {"percentage": 80, "state": "HIGH"},
            "signal": {"value": -50, "state": "MEDIUM"},
            "powerProfile": "POWER_SAVER_MODE",
            "locationCity": "Portland",
            "locationCountry": "US",
        }
    )
    assert feeder.id == "f1"
    assert feeder.serial == "SN123"
    assert feeder.name == "Backyard"
    assert feeder.is_owner is True
    assert feeder.is_public is False
    assert feeder.state is FeederState.READY_TO_STREAM
    assert feeder.battery.percentage == 80
    assert feeder.signal.rssi == -50
    assert feeder.power_profile is PowerProfile.POWER_SAVE
    assert feeder.location == ("Portland", "US")


def test_feeder_defaults():
    """A sparse Feeder payload falls back for name, state, and power profile.

    A Feeder without a powerProfile reports UNKNOWN (only owner responses
    carry the field).
    """
    feeder = Feeder({"id": "f2"})
    assert feeder.name == "Bird Buddy"
    assert feeder.is_owner is False
    assert feeder.state is FeederState.UNKNOWN
    assert feeder.power_profile is PowerProfile.UNKNOWN
    assert str(feeder).startswith("<Feeder:")


def test_feeder_update_status():
    """FeederUpdateStatus classifies an in-progress firmware update."""
    status = FeederUpdateStatus(
        {
            "__typename": "FeederFirmwareUpdateProgressResult",
            "progress": 42,
            "feeder": {"id": "f1"},
        }
    )
    assert status.is_in_progress is True
    assert status.is_complete is False
    assert status.is_failed is False
    assert status.progress == 42
    assert status.feeder.id == "f1"


def test_power_profile_missing_logs_no_warning(caplog):
    """A feeder without a powerProfile is UNKNOWN and logs no warning.

    The old "STANDARD" default fed an unknown value into PowerProfile, which
    logged a spurious "Unexpected power profile" warning; this asserts it no
    longer does.
    """
    with caplog.at_level(logging.WARNING, logger="birdbuddy"):
        assert Feeder({"id": "f"}).power_profile is PowerProfile.UNKNOWN
    assert "power profile" not in caplog.text.lower()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {"location": {"city": "Testville", "country": "US"}},
            id="owner_nested",
        ),
        pytest.param(
            {"locationCity": "Testville", "locationCountry": "US"},
            id="member_flat",
        ),
    ],
)
def test_feeder_location_both_shapes(payload):
    """Owner (nested) and member/public (flat) location both resolve."""
    assert Feeder(payload).location == ("Testville", "US")


def test_feeder_location_absent():
    """A feeder with no location yields (None, None)."""
    assert Feeder({"id": "f"}).location == (None, None)
