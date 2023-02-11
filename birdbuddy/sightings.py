"""Data models relating to bird Sightings"""

from __future__ import annotations
import base64
from collections import UserDict
from dataclasses import dataclass
from enum import Enum
import json
import logging

from . import LOGGER
from .birds import Species
from .media import Collection, Media


class SightingFinishStrategy(Enum):
    """Best option for finishing a sighting"""

    RECOGNIZED = "recognized"
    BEST_GUESS = "best_guess"
    MYSTERY = "mystery"

    def finish(self, data: dict = None) -> SightingFinishMod:
        """Wrap the strategy with additional metadata if needed"""
        if self == SightingFinishStrategy.BEST_GUESS:
            return SightingFinishMod(self, data)
        return SightingFinishMod(self)

    def __lt__(self, other):
        if self.__class__ is not other.__class__:
            return NotImplemented
        if self == SightingFinishStrategy.RECOGNIZED:
            return False
        if self == SightingFinishStrategy.BEST_GUESS:
            return other == SightingFinishStrategy.RECOGNIZED
        return True


@dataclass
class SightingFinishMod:
    """Simple wrapper for SightingFinishStrategy that includes additional data"""

    strategy: SightingFinishStrategy
    data: dict | None = None


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
    def id(self) -> str:
        """Sighting ID"""
        return self["id"]

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
    def species(self) -> Species | None:
        """Species"""
        return Species(self.get("species", {}))

    @property
    def suggestions(self) -> list[Collection]:
        """Suggested species"""
        return [
            Collection(s)
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
            f"SightingReport<sightings[{len(self.sightings)}]: "
            f"modes={ {s.id: f for (s, f) in self.sighting_finishing_strategies().values()} }>"
        )

    def __repr__(self) -> str:
        return f"{__class__.__name__}({super().__repr__()})"

    @property
    def sightings(self) -> list[Sighting]:
        """List of sightings within this report."""
        return [Sighting(s) for s in self.get("sightings", [])]

    @property
    def token(self) -> str:
        """Sighting reportToken, to allow the server to associate the sighting data."""
        return self.get("reportToken", None)

    def _decode_signed_token(self, signed: str) -> str:
        # This is a signed payload. The string is made up of:
        # "<base64-encoded signing header>.<base64-encoded json payload>.<base64-encoded signature bytes>"
        # We ignore the header and signature, and decode payload as JSON.
        (header, b64payload, _sig) = signed.split(".")
        if LOGGER.isEnabledFor(logging.DEBUG):
            header = base64.b64decode(header + "==", validate=False)
            LOGGER.debug("Got signed reportToken: %s", header)
        # Decode the payload section to a json string
        payload_json = base64.b64decode(b64payload + "==", validate=False).decode(
            "utf-8", "ignore"
        )
        # Then decode the JSON string so we can extract the nested reportToken
        payload = json.loads(payload_json)
        if not (token := payload.get("reportToken", None)):
            return {}
        return token

    @property
    def token_json(self) -> dict:
        """sightingReport.reportToken, parsed from a JSON string."""
        if not (token := self.token):
            return {}
        if token.count(".") == 2:
            token = self._decode_signed_token(token)
        try:
            return json.loads(token)
        except (ValueError, TypeError) as err:
            LOGGER.warning("Unable to decode report token: %s", err)
            return {}

    def sighting_finishing_strategies(
        self,
        confidence_threshold: int = None,
    ) -> dict[str, tuple[Sighting, SightingFinishMod]]:
        """Determine best finishing strategy for each sighting in this report.

        Response will be a dictionary with the `Sighting` as the key, and the
        best `SightingFinishMod` for that `Sighting`.
        """
        if confidence_threshold is None:
            confidence_threshold = SightingReport._BEST_GUESS_CONFIDENCE
        strategies = {}
        matches = self.highest_confidence_matches
        # pylint: disable=invalid-name
        for s in self.sightings:
            if s.is_recognized:
                strategies[s.id] = (s, SightingFinishStrategy.RECOGNIZED.finish())
            else:
                # Match sightings to highest confidence
                for m, item in matches.items():
                    if (
                        m in s.match_tokens
                        and item["confidence"] >= confidence_threshold
                        and item["type"] == "BIRD"
                    ):
                        strategies[s.id] = (
                            s,
                            SightingFinishStrategy.BEST_GUESS.finish(item),
                        )
                        break
            strategies.setdefault(s.id, (s, SightingFinishStrategy.MYSTERY.finish()))
        return strategies

    @property
    def highest_confidence_matches(self) -> dict[str, dict[str, any]]:
        """Returns the `$matchToken`: `{$confidence, $speciesCode}` mapping for the highest
        confidence.

        This can be used to select the highest confidence species match for each match token.
        These match tokens will correspond to 'CannotDecide' sighting types."""
        token = self.token_json
        if not token:
            LOGGER.warning("Cannot decode reportToken, falling back on .suggestions")
            return {
                match_token: {
                    "confidence": SightingReport._BEST_GUESS_CONFIDENCE,
                    "speciesCode": collection.species.id,
                    "type": "BIRD",
                }
                for s in self.sightings
                if (match_token := next(iter(s.match_tokens), None))
                and (collection := next(iter(s.suggestions), None))
            }

        matches = {
            # items should already be sorted by confidence, but make sure we only return BIRD items
            i["matchToken"]: max(
                (ii for ii in i["items"] if ii["type"] == "BIRD"),
                key=lambda x: x["confidence"],
            )
            for i in token.get("reportItems", [])
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
        """List of media for the sighting"""
        return [Media(m) for m in self.get("medias", [])]

    @property
    def video_media(self) -> list[Media]:
        """List of Video media for the sighting"""
        return [Media(v)] if (v := self.get("videoMedia")) else []

    @property
    def report(self) -> SightingReport:
        """Sighting report"""
        return SightingReport(self.get("sightingReport", {}))

    def with_postcard(self, postcard_id: str) -> PostcardSighting:
        """Initialize the source postcard id"""
        self.postcard_id = postcard_id
        return self
