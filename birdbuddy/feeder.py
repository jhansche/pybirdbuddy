"""Bird Buddy feeder models"""

from collections import UserDict
from enum import Enum
from typing import Optional

from . import LOGGER


class MetricState(Enum):
    """Feeder metric states"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: str):
        LOGGER.warning("Unexpected metric state: %s", value)
        return MetricState.UNKNOWN


class FeederState(Enum):
    """Feeder states"""

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
    def _missing_(cls, value: str):
        LOGGER.warning("Unexpected feeder.state: %s", value)
        return FeederState.UNKNOWN


class Signal(UserDict[str, any]):
    """Wifi signal metrics"""

    @property
    def rssi(self) -> int:
        """Signal strength"""
        return self.get("value", -1)

    @property
    def state(self) -> MetricState:
        """Signal strength"""
        return MetricState(self.get("state", "UNKNOWN"))


class Battery(UserDict[str, any]):
    """Battery info"""

    @property
    def percentage(self) -> int:
        """Percentage of battery remaining"""
        return self.get("percentage", 0)

    @property
    def is_charging(self) -> bool:
        """Whether the battery is charging"""
        return self.get("charging", False)

    @property
    def state(self) -> MetricState:
        """The state (low, medium, high) of the battery"""
        return MetricState(self.get("state", "UNKNOWN"))


class Feeder(UserDict[str, any]):
    """Represents one Bird Buddy device"""

    def __str__(self):
        return f"<Feeder: {self.name}, {self.state}, " f"{self.battery.percentage}%>"

    @property
    def id(self):
        """UUID"""
        return self["id"]

    @property
    def serial(self):
        """Feeder SN"""
        return self["serialNumber"]

    @property
    def name(self):
        """Feeder name, as set in the app"""
        return self.get("name", "Bird Buddy")

    @property
    def is_owner(self):
        """Whether the logged in user is the owner of this feeder."""
        return self.get("__typename") == "FeederForOwner"

    @property
    def is_pending(self):
        """``True`` if waiting for the owner account to approve access to the Feeder."""
        return self.get("__typename") == "FeederForMemberPending"

    @property
    def is_public(self):
        """Whether this is a public feeder."""
        return self.get("__typename") == "FeederForPublic"

    @property
    def version(self) -> str:
        """Firmware version (owner only)"""
        return self.get("firmwareVersion")

    @property
    def version_update_available(self) -> str:
        """Firmware update version (owner only)"""
        return self.get("availableFirmwareVersion", None)

    @property
    def state(self) -> FeederState:
        """State of the Feeder"""
        return FeederState(self.get("state", "UNKNOWN"))

    @property
    def is_off_grid(self) -> bool:
        """Whether `state` is `FeederState.OFF_GRID`."""
        return self.get("offGrid", None)

    @property
    def is_audio_enabled(self) -> bool:
        """Whether videos will contain audio."""
        return self.get("audioEnabled", None)

    @property
    def owner(self) -> str:
        """The username who first paired the Feeder"""
        return self.get("ownerName")

    @property
    def battery(self) -> Battery:
        """battery metrics"""
        return Battery(self.get("battery", {}))

    @property
    def signal(self) -> Signal:
        """(wifi) signal metrics"""
        return Signal(self.get("signal", {}))

    @property
    def location(self) -> tuple[Optional[str], Optional[str]]:
        """Configured location of the Feeder"""
        return (self.get("locationCity"), self.get("locationCountry"))

    @property
    def frequency(self) -> MetricState:
        """Configured frequency of the Feeder."""
        # Presumably this is a setting for preferred frequency of postcards?
        return MetricState(self.get("frequency", "UNKNOWN"))

    @property
    # @incubating
    def food(self) -> MetricState:
        """
        Level of bird seed in the feeder.
        @incubating This field appears not to work currently.
        """
        LOGGER.debug("birdbuddy.Feeder.food is incubating")
        return MetricState(self.get("food", {}).get("state", "UNKNOWN"))

    @property
    # @incubating
    def temperature(self) -> int:
        """
        Temperature at the feeder.
        @incubating This field appears not to work currently.
        """
        LOGGER.debug("birdbuddy.Feeder.temperature is incubating")
        return self.get("temperature", {}).get("value", 0)


class FeederUpdateStatus(UserDict[str, any]):
    """Feeder update status"""

    @property
    def feeder(self) -> Feeder:
        """Returns a partial Feeder result"""
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
    def failure_reason(self) -> str:
        """Failure reason, or `None` if no failure."""
        return self.get("failedReason", None)

    @property
    def progress(self) -> int:
        """Current firmware installation progress."""
        return self.get("progress", None)
