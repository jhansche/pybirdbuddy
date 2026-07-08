"""Data models for collected postcards (the postcardCollect flow)."""

from __future__ import annotations

from collections import UserDict
from typing import Any

from birdbuddy.birds import Species
from birdbuddy.media import Media


class CollectedPostcard(UserDict[str, Any]):
    """A postcard collected into your account.

    Wraps the ``FeedItemCollectedPostcard`` returned by
    ``BirdBuddy.collect_postcard``.
    """

    @property
    def id(self) -> str:
        """The collected feed-item id."""
        return self["id"]

    @property
    def species(self) -> list[Species]:
        """The recognized species (a postcard may hold more than one)."""
        return [Species(s) for s in self.get("species") or []]

    @property
    def medias(self) -> list[Media]:
        """The postcard media."""
        return [Media(m) for m in self.get("medias") or []]

    @property
    def has_mystery_visitor(self) -> bool:
        """Whether the postcard contains an unrecognized visitor."""
        return bool(self.get("hasMysteryVisitor"))

    @property
    def has_new_species(self) -> bool:
        """Whether the postcard unlocked a new species."""
        return bool(self.get("hasNewSpecies"))

    @property
    def inference_execution_mode(self) -> str | None:
        """The inference execution mode (e.g. ``MANUAL_COMPLETED``)."""
        return self.get("inferenceExecutionMode")

    @property
    def inference_type(self) -> str | None:
        """The inference type (e.g. ``ADVANCED``)."""
        return self.get("inferenceType")

    @property
    def species_confidence(self) -> str | None:
        """Species-name identification confidence.

        One of ``CANNOT_DECIDE`` or ``VERY_CONFIDENT``, or ``None`` when the
        backend did not report it.
        """
        return self.get("mediaSpeciesNameIdentificationConfidenceLevel")
