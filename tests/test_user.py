"""Basic tests for the birdbuddy.user model."""

from birdbuddy.user import BirdBuddyUser


def test_user_maps_id_name_and_avatar():
    """BirdBuddyUser exposes id, name, and the camelCase avatarUrl."""
    user = BirdBuddyUser({"id": "u1", "name": "Ada", "avatarUrl": "https://x/a.png"})
    assert user.id == "u1"
    assert user.name == "Ada"
    assert user.avatar_url == "https://x/a.png"
