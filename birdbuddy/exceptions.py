"""Bird Buddy errors."""

AUTH_TOKEN_EXPIRED_ERROR = "AUTH_TOKEN_EXPIRED_ERROR"


class NoResponseError(Exception):
    """The GraphQL request had no response."""


class GraphqlError(Exception):
    """The GraphQL response contained one or more errors."""

    response: dict

    def __init__(self, error: dict) -> None:
        """Store the GraphQL error payload.

        Args:
            error: A single GraphQL error dict from the response.
        """
        self.response = error
        super().__init__(f"{self.error_code}: {error}")

    @property
    def error_code(self) -> str | None:
        """The Bird Buddy GraphQL error code."""
        return self.response.get("extensions", {}).get("code")

    @staticmethod
    def raise_errors(errors: list[dict]) -> None:
        """Raise the appropriate exception for a list of GraphQL errors.

        Args:
            errors: The ``errors`` list from a GraphQL response.

        Raises:
            GraphqlError: If exactly one error is present (as the most
                specific subclass, e.g. ``AuthTokenExpiredError``).
            CompositeException: If more than one error is present.
        """
        converted = [GraphqlError._convert_error(err) for err in errors]
        if (n := len(converted)) == 0:
            return
        if n > 1:
            raise CompositeException(converted)
        raise converted[0]

    @staticmethod
    def _convert_error(err: dict) -> Exception:
        """Convert a GraphQL error dict to the most specific exception.

        Args:
            err: A single GraphQL error dict.

        Returns:
            An ``AuthTokenExpiredError`` for expired-token codes, otherwise a
            ``GraphqlError``.
        """
        gqlerr = GraphqlError(err)
        if gqlerr.error_code == AUTH_TOKEN_EXPIRED_ERROR:
            return AuthTokenExpiredError(err)
        return gqlerr


class AuthTokenExpiredError(GraphqlError):
    """The auth token has expired."""


class AuthenticationFailedError(Exception):
    """The login attempt failed."""


class UnexpectedResponseError(Exception):
    """The response did not contain the expected fields."""

    def __init__(self, response: dict | None = None) -> None:
        """Store the unexpected response.

        Args:
            response: The raw GraphQL response, if available.
        """
        Exception.__init__(self)
        self.response = response


class CompositeException(Exception):  # noqa: N818
    """Represents multiple errors.

    Named without an ``Error`` suffix for backwards compatibility; it is part
    of the public API consumed by downstream packages.
    """
