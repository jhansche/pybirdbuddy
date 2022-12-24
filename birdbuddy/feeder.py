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


class FeederState(Enum):
    """Feeder states"""

    DEEP_SLEEP = "DEEP_SLEEP"
    FIRMWARE_UPDATE = "FIRMWARE_UPDATE"
    OFFLINE = "OFFLINE"
    OFF_GRID = "OFF_GRID"
    ONLINE = "ONLINE"
    OUT_OF_FEEDER = "OUT_OF_FEEDER"
    READY_TO_STREAM = "READY_TO_STREAM"
    STREAMING = "STREAMING"
    TAKING_POSTCARDS = "TAKING_POSTCARDS"


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
    def name(self):
        """Feeder name, as set in the app"""
        return self.get("name", "Bird Buddy")

    @property
    def state(self) -> FeederState:
        """State of the Feeder"""
        return FeederState(self.get("state", "UNKNOWN"))

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
    # @incubating
    def food(self) -> MetricState:
        """
        Level of bird seed in the feeder.
        @incubating This field appears not to work currently.
        """
        LOGGER.info("birdbuddy.Feeder.food is incubating")
        return MetricState(self.get("food", {}).get("state", "UNKNOWN"))

    @property
    # @incubating
    def temperature(self) -> int:
        """
        Temperature at the feeder.
        @incubating This field appears not to work currently.
        """
        LOGGER.info("birdbuddy.Feeder.temperature is incubating")
        return self.get("temperature", {}).get("value", 0)
