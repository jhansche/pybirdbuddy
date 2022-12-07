import logging
from collections import UserDict
from enum import Enum
from typing import Mapping, Optional

_LOGGER = logging.getLogger(__package__)


class MetricState(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FeederState(Enum):
    OFFLINE = "OFFLINE"
    OFF_GRID = "OFF_GRID"
    ONLINE = "ONLINE"
    OUT_OF_FEEDER = "OUT_OF_FEEDER"
    READY_TO_STREAM = "READY_TO_STREAM"
    STREAMING = "STREAMING"
    TAKING_POSTCARDS = "TAKING_POSTCARDS"


class Signal(UserDict[str, any]):
    """Wifi signal metrics"""

    def __init__(self, signal: Mapping[str, any]) -> None:
        super().__init__(signal)

    @property
    def rssi(self) -> int:
        return self.get("value", -1)

    @property
    def state(self) -> MetricState:
        return MetricState(self.get("state", "UNKNOWN"))


class Battery(UserDict[str, any]):
    """Battery info"""

    def __init__(self, battery: Mapping[str, any]) -> None:
        super().__init__(battery)

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

    def __init__(self, feeder: Mapping[str, any]) -> None:
        super().__init__(feeder)

    def __str__(self):
        return (f"<Feeder: {self.name}, {self.state}, "
                f"{self.battery.percentage}%>")

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
        return (self.get("locationCity"),
                self.get("locationCountry"))

    @property
    # @incubating
    def food(self) -> MetricState:
        """
        Level of bird seed in the feeder.
        @incubating This field appears not to work currently.
        """
        _LOGGER.info("birdbuddy.Feeder.food is incubating")
        return MetricState(self.get("food", {}).get("state", "UNKNOWN"))

    @property
    # @incubating
    def temperature(self) -> int:
        """
        Temperature at the feeder.
        @incubating This field appears not to work currently.
        """
        _LOGGER.info("birdbuddy.Feeder.temperature is incubating")
        return self.get("temperature", {}).get("value", 0)
