"""Bird Buddy feeder models."""

from __future__ import annotations

from collections import UserDict
from enum import Enum
from typing import Any

from birdbuddy import LOGGER


class MetricState(Enum):
    """Feeder metric states."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> MetricState:
        LOGGER.warning("Unexpected metric state: %s", value)
        return MetricState.UNKNOWN


class PowerProfile(Enum):
    """Feeder power profiles."""

    FRENZY = "FRENZY_MODE"
    ULTRA_FRENZY = "ULTRA_FRENZY_MODE"
    POWER_SAVE = "POWER_SAVER_MODE"
    STANDARD = "STANDARD_MODE"

    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> PowerProfile:
        LOGGER.warning("Unexpected power profile: %s", value)
        return PowerProfile.UNKNOWN


class FeederState(Enum):
    """Feeder states."""

    DEEP_SLEEP = "DEEP_SLEEP"
    FACTORY_RESET = "FACTORY_RESET"
    FIRMWARE_UPDATE = "FIRMWARE_UPDATE"
    OFFLINE = "OFFLINE"
    OFF_GRID = "OFF_GRID"
    ONLINE = "ONLINE"
    OUT_OF_FEEDER = "OUT_OF_FEEDER"
    PENDING_FACTORY_RESET = "PENDING_FACTORY_RESET"
    PENDING_REMOVAL = "PENDING_REMOVAL"
    READY_TO_STREAM = "READY_TO_STREAM"
    STREAMING = "STREAMING"
    TAKING_POSTCARDS = "TAKING_POSTCARDS"

    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> FeederState:
        LOGGER.warning("Unexpected feeder.state: %s", value)
        return FeederState.UNKNOWN


class Signal(UserDict[str, Any]):
    """Wifi signal metrics."""

    @property
    def rssi(self) -> int:
        """Signal strength."""
        return self.get("value", -1)

    @property
    def state(self) -> MetricState:
        """Signal strength."""
        return MetricState(self.get("state", "UNKNOWN"))


class Battery(UserDict[str, Any]):
    """Battery info."""

    @property
    def percentage(self) -> int:
        """Percentage of battery remaining."""
        return self.get("percentage", 0)

    @property
    def is_charging(self) -> bool:
        """Whether the battery is charging."""
        return self.get("charging", False)

    @property
    def state(self) -> MetricState:
        """The state (low, medium, high) of the battery."""
        return MetricState(self.get("state", "UNKNOWN"))


class Feeder(UserDict[str, Any]):
    """Represents one Bird Buddy device."""

    def __str__(self) -> str:
        """Return a string representation of the Feeder."""
        return (
            f"<Feeder: {self.name}, {self.state}, {self.battery.percentage}%>"
        )

    @property
    def id(self) -> str:
        """UUID."""
        return self["id"]

    @property
    def serial(self) -> str:
        """Feeder SN."""
        return self["serialNumber"]

    @property
    def name(self) -> str:
        """Feeder name, as set in the app."""
        return self.get("name", "Bird Buddy")

    @property
    def is_owner(self) -> bool:
        """Whether the logged in user is the owner of this feeder."""
        return self.get("__typename") == "FeederForOwner"

    @property
    def is_pending(self) -> bool:
        """``True`` if waiting for the owner account to approve access."""
        return self.get("__typename") == "FeederForMemberPending"

    @property
    def is_public(self) -> bool:
        """Whether this is a public feeder."""
        return self.get("__typename") == "FeederForPublic"

    @property
    def version(self) -> str | None:
        """Firmware version (owner only)."""
        return self.get("firmwareVersion")

    @property
    def version_update_available(self) -> str | None:
        """Firmware update version (owner only)."""
        return self.get("availableFirmwareVersion", None)

    @property
    def state(self) -> FeederState:
        """State of the Feeder."""
        return FeederState(self.get("state", "UNKNOWN"))

    @property
    def is_off_grid(self) -> bool | None:
        """Whether `state` is `FeederState.OFF_GRID`."""
        return self.get("offGrid", None)

    @property
    def is_audio_enabled(self) -> bool | None:
        """Whether videos will contain audio."""
        return self.get("audioEnabled", None)

    @property
    def owner(self) -> str | None:
        """The username who first paired the Feeder."""
        return self.get("ownerName")

    @property
    def battery(self) -> Battery:
        """Battery metrics."""
        return Battery(self.get("battery", {}))

    @property
    def signal(self) -> Signal:
        """(wifi) signal metrics."""
        return Signal(self.get("signal", {}))

    @property
    def location(self) -> tuple[str | None, str | None]:
        """Configured location of the Feeder."""
        # TODO(roger): the schema diverges by feeder type -- FeederForOwner
        # nests location{city,country} while FeederForMember/Public expose
        # flat locationCity/locationCountry (neither deprecated). This reads
        # only the flat keys, so an owner feeder yields (None, None). Handle
        # both shapes in a later release.
        return (self.get("locationCity"), self.get("locationCountry"))

    @property
    def frequency(self) -> MetricState:
        """Configured frequency of the Feeder."""
        LOGGER.warning(
            "Feeder.frequency is deprecated. Use power_profile instead"
        )
        return MetricState(self.get("frequency", "UNKNOWN"))

    @property
    def power_profile(self) -> PowerProfile:
        """Configured power profile of the Feeder.

        Returns ``UNKNOWN`` when the feeder does not report a power profile
        (e.g. non-owner feeders); only owner responses carry the field.
        """
        value = self.get("powerProfile")
        return PowerProfile(value) if value else PowerProfile.UNKNOWN

    @property
    # @incubating
    def food(self) -> MetricState:
        """Level of bird seed in the feeder.

        @incubating This field appears not to work currently.
        """
        LOGGER.debug("birdbuddy.Feeder.food is incubating")
        return MetricState(self.get("food", {}).get("state", "UNKNOWN"))

    @property
    # @incubating
    def temperature(self) -> int:
        """Temperature at the feeder.

        @incubating This field appears not to work currently.
        """
        LOGGER.debug("birdbuddy.Feeder.temperature is incubating")
        return self.get("temperature", {}).get("value", 0)


class FeederUpdateStatus(UserDict[str, Any]):
    """Feeder update status."""

    @property
    def feeder(self) -> Feeder:
        """Returns a partial Feeder result."""
        return Feeder(self["feeder"])

    @property
    def is_complete(self) -> bool:
        """`True` if the firmware update was successfully completed."""
        return self["__typename"] == "FeederFirmwareUpdateSucceededResult"

    @property
    def is_in_progress(self) -> bool:
        """`True` if the firmware update is in progress."""
        return (
            self["__typename"] == "FeederFirmwareUpdateProgressResult"
            and self.get("progress", None) is not None
        )

    @property
    def is_failed(self) -> bool:
        """`True` if the firmware update has failed."""
        return self["__typename"] == "FeederFirmwareUpdateFailedResult"

    @property
    def failure_reason(self) -> str | None:
        """Failure reason, or `None` if no failure."""
        return self.get("failedReason", None)

    @property
    def progress(self) -> int | None:
        """Current firmware installation progress."""
        return self.get("progress", None)
