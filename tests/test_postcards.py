"""Unit tests for PostcardAnalysis (the identify_postcard result model)."""

from birdbuddy.postcards import PostcardAnalysis


def _analysis(**fields: object) -> PostcardAnalysis:
    """Build a PostcardAnalysis from a partial FeedItemNewPostcard payload."""
    item: dict[str, object] = {
        "id": "pc-1",
        "__typename": "FeedItemNewPostcard",
    }
    item.update(fields)
    return PostcardAnalysis(item)


def test_species_only_from_recognized_sightings():
    """Species come from Recognized/Unlocked members; others are ignored."""
    analysis = _analysis(
        sightingReportPreview={
            "sightings": [
                {
                    "__typename": "SightingRecognizedBird",
                    "species": {"id": "1", "name": "American Robin"},
                },
                {
                    "__typename": "SightingRecognizedBirdUnlocked",
                    "species": {"id": "2", "name": "Blue Jay"},
                },
                {"__typename": "SightingRecognizedMysteryVisitor"},
                {"__typename": "SightingCantDecideWhichBird"},
                {"__typename": "SightingNoBird"},
                {"__typename": "SightingNoBirdRecognized"},
            ]
        }
    )
    assert [s.name for s in analysis.species] == ["American Robin", "Blue Jay"]


def test_missing_or_empty_preview_yields_no_species():
    """No preview, or an empty sightings list, means no recognized species."""
    assert _analysis().species == []
    assert _analysis(sightingReportPreview={}).species == []
    assert _analysis(sightingReportPreview={"sightings": []}).species == []


def test_feeder_is_optional():
    """The feeder property is a Feeder when present, else None."""
    assert _analysis().feeder is None
    analysis = _analysis(
        feeder={"__typename": "FeederForOwner", "id": "f1", "name": "Yard"}
    )
    assert analysis.feeder is not None
    assert analysis.feeder.id == "f1"
    assert analysis.feeder.name == "Yard"


def test_medias_expose_content_url():
    """Image and video media both expose their content URL."""
    analysis = _analysis(
        medias=[
            {
                "__typename": "MediaImage",
                "id": "m1",
                "contentUrl": "https://c/i.jpg",
                "thumbnailUrl": "https://t/i.jpg",
            },
            {
                "__typename": "MediaVideo",
                "id": "m2",
                "contentUrl": "https://c/v.mp4",
                "thumbnailUrl": "https://t/v.jpg",
            },
        ]
    )
    assert len(analysis.medias) == 2
    assert [m.content_url for m in analysis.medias] == [
        "https://c/i.jpg",
        "https://c/v.mp4",
    ]


def test_mystery_visitor_has_media_but_no_species():
    """A mystery-visitor postcard exposes media with no recognized species."""
    analysis = _analysis(
        medias=[
            {
                "__typename": "MediaImage",
                "id": "m1",
                "contentUrl": "https://c/i.jpg",
                "thumbnailUrl": "https://t/i.jpg",
            }
        ],
        sightingReportPreview={
            "sightings": [{"__typename": "SightingRecognizedMysteryVisitor"}]
        },
    )
    assert analysis.species == []
    assert len(analysis.medias) == 1
