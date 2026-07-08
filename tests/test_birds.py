"""Basic tests for the birdbuddy.birds Species model."""

from birdbuddy.birds import Species


def test_species_exposes_id_and_name():
    """Species reads its id and name from the backing dict."""
    species = Species({"id": "sp1", "name": "American Robin"})
    assert species.id == "sp1"
    assert species.name == "American Robin"
