"""Data models relating to Species, Sightings, etc"""

from __future__ import annotations
from collections import UserDict
from enum import Enum
import json

from . import LOGGER
from .media import Media


class SightingFinishStrategy(Enum):
    """Best option for finishing a sighting"""

    RECOGNIZED = "recognized"
    BEST_GUESS = "best_guess"
    MYSTERY = "mystery"


class Species(UserDict[str, str]):
    """Species"""

    @property
    def id(self) -> str:
        """Species id or code"""
        return self["id"]

    @property
    def name(self) -> str:
        """Species name"""
        return self["name"]


class SightingType(Enum):
    """Machine-inferred sighting type."""

    CANNOT_DECIDE = "SightingCantDecideWhichBird"
    NO_BIRD = "SightingNoBird"
    NO_BIRD_RECOGNIZED = "SightingNoBirdRecognized"
    SPECIES_RECOGNIZED = "SightingRecognizedBird"
    SPECIES_UNLOCKED = "SightingRecognizedBirdUnlocked"
    MYSTERY_VISITOR = "SightingRecognizedMysteryVisitor"

    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: str) -> SightingType:
        LOGGER.warning("Unexpected Sighting type: %s", value)
        return SightingType.UNKNOWN

    @property
    def is_recognized(self) -> bool:
        """Whether this sighting type is confidently recognized."""
        return self in [
            SightingType.SPECIES_RECOGNIZED,
            SightingType.SPECIES_UNLOCKED,
            SightingType.MYSTERY_VISITOR,
        ]

    @property
    def is_unlocked(self) -> bool:
        """Whether this is the first sighting of a species (unlocked a new species)."""
        return self == SightingType.SPECIES_UNLOCKED


class Sighting(UserDict[str, any]):
    """A sighting from a postcard sighting report."""

    def __str__(self) -> str:
        return (
            f"Sighting<type={self.sighting_type}, recognized={self.is_recognized}, "
            f"unlocked={self.is_unlocked}, species={self.species}>"
        )

    def __repr__(self) -> str:
        return f"{__class__.__name__}({super().__repr__()})"

    @property
    def sighting_type(self) -> SightingType:
        """The type of sighting."""
        return SightingType(self.get("__typename"))

    @property
    def is_recognized(self) -> bool:
        """Whether the sighting is confidently recognized."""
        return self.sighting_type.is_recognized

    @property
    def is_unlocked(self) -> bool:
        """Whether the sighting unlocks a new bird species."""
        return self.sighting_type.is_unlocked

    @property
    def species(self) -> Species:
        """Species"""
        return Species(self["species"])

    @property
    def suggestions(self) -> list[Species]:
        """Suggested species"""
        return [
            Species(s["species"])
            for s in self.get("suggestions", [])
            if s["__typename"] == "CollectionSpecies"
            and s["species"]["__typename"] == "SpeciesBird"
        ]

    @property
    def match_tokens(self) -> list[str]:
        """Match tokens for reporting."""
        return self.get("matchTokens", [])

    @property
    def cover_media(self) -> dict:
        """Cover media used for collecting a new unlocked species."""
        return {
            "speciesId": self.species.id,
            "mediaId": self.match_tokens[0],
        }


class SightingReport(UserDict[str, any]):
    """Sighting Report object"""

    _BEST_GUESS_CONFIDENCE = 10
    """The minimum confidence necessary to finish by best-guess."""

    def __str__(self) -> str:
        return (
            f"SightingReport<sightings={len(self.sightings)}:{str(self.sightings[0])}, "
            f"recognized={self.all_sightings_recognized}>"
        )

    def __repr__(self) -> str:
        return f"{__class__.__name__}({super().__repr__()})"

    @property
    def sightings(self) -> list[Sighting]:
        """List of sightings within this report."""
        return [Sighting(s) for s in self.get("sightings", [])]

    @property
    def all_sightings_recognized(self) -> bool:
        """Returns `True` if all `sightings` are `Sighting.is_recognized`."""
        return all(s.is_recognized for s in self.sightings)

    @property
    def token(self) -> str:
        """Sighting reportToken, to allow the server to associate the sighting data."""
        return self.get("reportToken", None)

    @property
    def token_json(self) -> dict:
        """sightingReport.reportToken, parsed from a JSON string."""
        return json.loads(self.token)

    @property
    def finishing_strategy(self) -> SightingFinishStrategy:
        """Recommended finishing strategy:

        - `SightingRecognized` can be finished automatically by accepting recognized species.
        - `CannotDecide` can be finished by choosing the highest-confidence species, as long
          as they all have a high enough confidence.
        - Last resort, we can report it as a 'Mystery Visitor'"""
        if self.all_sightings_recognized:
            return SightingFinishStrategy.RECOGNIZED

        if all(
            x["confidence"] >= SightingReport._BEST_GUESS_CONFIDENCE
            for x in self.highest_confidence_matches.values()
        ):
            return SightingFinishStrategy.BEST_GUESS

        return SightingFinishStrategy.MYSTERY

    @property
    def highest_confidence_matches(self) -> dict[str, dict[str, any]]:
        """Returns the `$matchToken`: `{$confidence, $speciesCode}` mapping for the highest
        confidence.

        This can be used to select the highest confidence species match for each match token.
        These match tokens will correspond to 'CannotDecide' sighting types."""
        matches = {
            # items should already be sorted by confidence
            i["matchToken"]: max(i["items"], key=lambda x: x["confidence"])
            for i in self.token_json["reportItems"]
        }
        return matches


class PostcardSighting(UserDict[str, any]):
    """Represents a bird sighting from a postcard.

    See also `FeedNodeType.NewPostcard`, `BirdBuddy.sighting_from_postcard()`."""

    postcard_id: str = None

    def __repr__(self) -> str:
        return f"{__class__.__name__}({super().__repr__()})"

    def __str__(self) -> str:
        return f"PostcardSighting<feeder={self.feeder['name']}, report={self.report}>"

    @property
    def feeder(self) -> dict:
        """Describes the Feeder this sighting happened at"""
        return self.get("feeder", {})

    @property
    def medias(self) -> list[Media]:
        """List of medias for the sighting"""
        return [Media(m) for m in self.get("medias", [])]

    @property
    def report(self) -> SightingReport:
        """Sighting report"""
        return SightingReport(self.get("sightingReport", {}))

    def with_postcard(self, postcard_id: str) -> PostcardSighting:
        """Initialize the source postcard id"""
        self.postcard_id = postcard_id
        return self
