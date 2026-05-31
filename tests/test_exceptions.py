"""Tests for birdbuddy/exceptions.py."""
import pytest

from birdbuddy.exceptions import (
    CompositeException,
    GraphqlError,
)


def _err(code: str = "INTERNAL_SERVER_ERROR", message: str = "boom") -> dict:
    """Build the dict shape that GraphqlError / raise_errors expect.

    GraphqlError.error_code reads `extensions.code`; the rest of the dict
    is stored verbatim on `self.response`.
    """
    return {
        "message": message,
        "path": ["someField"],
        "extensions": {"code": code},
    }


def test_raise_errors_empty_list_returns_none() -> None:
    """No errors → return without raising."""
    assert GraphqlError.raise_errors([]) is None


def test_raise_errors_single_error_raises_graphqlerror() -> None:
    """One error → raise it directly as GraphqlError, not CompositeException."""
    errors = [_err()]
    with pytest.raises(GraphqlError) as exc_info:
        GraphqlError.raise_errors(errors)
    # Must be the base GraphqlError (or a subclass), but importantly NOT a
    # CompositeException — that would mean the multi-error branch fired
    # incorrectly for a single error.
    assert not isinstance(exc_info.value, CompositeException)
    assert exc_info.value.error_code == "INTERNAL_SERVER_ERROR"
    assert exc_info.value.response["message"] == "boom"


def test_raise_errors_multiple_errors_raises_compositeexception() -> None:
    """Regression: with the old `if errs := len(converted) == 0:` walrus-
    precedence bug, `errs` was a bool and `errs > 1` was always False, so
    the CompositeException branch was dead code and the function silently
    raised only the first error (dropping the rest). This test fails against
    the buggy code and passes against the fix."""
    errors = [_err(message="first"), _err(message="second")]
    with pytest.raises(CompositeException) as exc_info:
        GraphqlError.raise_errors(errors)
    # CompositeException wraps the list of converted errors as its first arg.
    converted = exc_info.value.args[0]
    assert len(converted) == 2
    assert all(isinstance(e, GraphqlError) for e in converted)
    assert [e.response["message"] for e in converted] == ["first", "second"]


def test_raise_errors_three_errors_also_raises_compositeexception() -> None:
    """Confirm the multi-error branch isn't a 2-only special case."""
    errors = [_err(message=f"err{i}") for i in range(3)]
    with pytest.raises(CompositeException) as exc_info:
        GraphqlError.raise_errors(errors)
    assert len(exc_info.value.args[0]) == 3
