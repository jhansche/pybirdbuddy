"""Bird Buddy errors"""

AUTH_TOKEN_EXPIRED_ERROR = "AUTH_TOKEN_EXPIRED_ERROR"


class NoResponseError(Exception):
    """The GraphQL request had no response"""


class GraphqlError(Exception):
    """The GraphQL response contained one or more errors"""

    response: dict

    def __init__(self, error: dict):
        self.response = error
        super().__init__(f"{self.error_code}: {error}")

    @property
    def error_code(self) -> int:
        """The Bird Buddy GraphQL error code"""
        return self.response.get("extensions", {}).get("code")

    @staticmethod
    def raise_errors(errors: list[dict]) -> None:
        """Parse and raise errors as needed"""
        converted = [GraphqlError._convert_error(err) for err in errors]
        if errs := len(converted) == 0:
            return
        if errs > 1:
            raise CompositeException(converted)
        raise converted[0]

    @staticmethod
    def _convert_error(err: dict) -> Exception:
        gqlerr = GraphqlError(err)
        if gqlerr.error_code == AUTH_TOKEN_EXPIRED_ERROR:
            return AuthTokenExpiredError(err)
        return gqlerr


class AuthTokenExpiredError(GraphqlError):
    """The auth token has expired"""


class AuthenticationFailedError(Exception):
    """The login attempt failed"""


class UnexpectedResponseError(Exception):
    """The response did not contain the expected fields"""

    def __init__(self, response: dict = None):
        Exception.__init__(self)
        self.response = response


class CompositeException(Exception):
    """Represents multiple errors"""
