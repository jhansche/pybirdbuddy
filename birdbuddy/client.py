"""Bird Buddy client module"""

from datetime import datetime
from typing import Union

from python_graphql_client import GraphqlClient

from . import LOGGER, queries
from .const import BB_URL
from .exceptions import (
    AuthenticationFailedError,
    AuthTokenExpiredError,
    NoResponseError,
    GraphqlError,
    UnexpectedResponseError,
)
from .feeder import Feeder
from .media import Collection


class BirdBuddy:
    """Bird Buddy api client"""

    graphql: GraphqlClient
    _email: str
    _password: str
    _access_token: Union[str, None]
    _refresh_token: Union[str, None]
    _me: Union[dict, None]
    _feeders: dict[str, Feeder]
    _collections: dict[str, Collection]

    def __init__(self, email: str, password: str) -> None:
        self.graphql = GraphqlClient(BB_URL)
        self._email = email
        self._password = password
        self._access_token = None
        self._refresh_token = None
        self._me = None
        self._feeders = {}
        self._collections = {}

    def _save_me(self, me_data: dict):
        if not me_data:
            return False
        me_data["__last_updated"] = datetime.now()
        self._me = me_data
        # pylint: disable=invalid-name
        for f in me_data.get("feeders", []):
            if f["id"] in self._feeders:
                # Refresh Feeder data inline
                self._feeders[f["id"]].update(f)
            else:
                self._feeders[f["id"]] = Feeder(f)
        return True

    def _needs_login(self) -> bool:
        return self._refresh_token is None

    def _needs_refresh(self) -> bool:
        return self._access_token is None

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _clear(self):
        self._access_token = None
        self._refresh_token = None
        self._me = None

    async def dump_schema(self) -> dict:
        """For debugging purposes: dump the entire GraphQL schema"""
        # pylint: disable=import-outside-toplevel
        from .queries.debug import DUMP_SCHEMA

        return await self._make_request(query=DUMP_SCHEMA, auth=False)

    async def _check_auth(self) -> bool:
        if self._needs_login():
            LOGGER.debug("Login required")
            return await self._login()
        if self._needs_refresh():
            LOGGER.debug("Access token needs to be refreshed")
            await self._refresh_access_token()
        return not self._needs_login()

    async def _login(self) -> bool:
        assert self._email and self._password
        variables = {
            "emailSignInInput": {
                "email": self._email,
                "password": self._password,
            }
        }
        try:
            data = await self._make_request(
                query=queries.auth.SIGN_IN,
                variables=variables,
                auth=False,
            )
        except GraphqlError as err:
            LOGGER.exception("Error logging in: %s", err)
            raise AuthenticationFailedError(err) from err

        result = data["authEmailSignIn"]
        self._access_token = result["accessToken"]
        self._refresh_token = result["refreshToken"]
        return self._save_me(result["me"])

    async def _refresh_access_token(self) -> bool:
        assert self._refresh_token
        variables = {
            "refreshTokenInput": {
                "token": self._refresh_token,
            }
        }
        try:
            data = await self._make_request(
                query=queries.auth.REFRESH_AUTH_TOKEN,
                variables=variables,
                auth=False,
            )
        except GraphqlError as exc:
            LOGGER.exception("Error refreshing access token: %s", exc)
            self._refresh_token = None
            raise AuthenticationFailedError(exc) from exc

        tokens = data["authRefreshToken"]
        self._access_token = tokens.get("accessToken")
        self._refresh_token = tokens.get("refreshToken")
        LOGGER.info("Access token refreshed")
        return not self._needs_refresh()

    async def _make_request(
        self,
        query: str,
        variables: dict = None,
        auth: bool = True,
        reauth: bool = True,
    ) -> dict:
        """Make the request, check for errors, and return the unwrapped data"""
        if auth:
            await self._check_auth()
            headers = self._headers()
        else:
            headers = {}

        LOGGER.debug("Making GraphQL request: %s", query.partition("\n")[0])
        response = await self.graphql.execute_async(
            query=query,
            variables=variables,
            headers=headers,
        )

        if not response or not isinstance(response, dict):
            raise NoResponseError

        errors = response.get("errors", [])
        try:
            GraphqlError.raise_errors(errors)
        except AuthTokenExpiredError:
            self._access_token = None
            if auth and reauth:
                # login and try again
                return await self._make_request(
                    query=query,
                    variables=variables,
                    auth=auth,
                    reauth=False,
                )
            raise

        result = response.get("data")
        if not isinstance(result, dict):
            raise UnexpectedResponseError(response)

        return result

    async def refresh(self) -> bool:
        """Refreshes the Bird Buddy feeder data"""
        data = await self._make_request(query=queries.me.ME)
        LOGGER.debug("Feeder data refreshed successfully: %s", data)
        return self._save_me(data["me"])

    async def feed(self) -> dict:
        """Returns the Bird Buddy Feed"""
        data = await self._make_request(query=queries.me.FEED)
        return data["me"]["feed"]

    async def feed_node_types(self) -> list:
        """Returns just the node types from the Bird Buddy Feed"""
        feed = await self.feed()
        nodes = [edge["node"] for edge in feed["edges"]]
        return [node["__typename"] for node in nodes]

    async def feed_nodes(self, node_type: str) -> list[dict]:
        """Returns all feed items of type ``node_type``"""
        feed = await self.feed()
        nodes = [edge["node"] for edge in feed["edges"]]
        return [node for node in nodes if node["__typename"] == node_type]

    async def new_postcards(self) -> list[dict]:
        """Returns all new 'Postcard' feed items.

        These Postcard node types will be converted into sightings using ``sighting_from_postcard``.
        """
        return await self.feed_nodes("FeedItemNewPostcard")

    async def sighting_from_postcard(self, postcard_id: str) -> dict:
        """Convert a 'postcard' into a 'sighting report'.
        Next step is to choose or confirm species and then finish the sighting.
        """
        await self._check_auth()

        variables = {
            "sightingCreateFromPostcardInput": {
                "feedItemId": postcard_id,
            }
        }
        data = await self._make_request(
            query=queries.birds.POSTCARD_TO_SIGHTING,
            variables=variables,
        )
        # data[feeder], data[medias], data[sightingReport]
        # sightingReport.reportToken is JSON-string, containing confidence of each match
        # sightingReport.sightings[] might have types:
        #  'SightingCantDecideWhichBird',
        #  'SightingNoBird',
        #  'SightingNoBirdRecognized',
        #  'SightingRecognizedBird',
        #  'SightingRecognizedBirdUnlocked',
        #  'SightingRecognizedMysteryVisitor',
        # Next steps:
        #  - for each .sightings[]: sightingChooseSpecies()
        #  - sightingReportPostcardFinish()
        return data

    async def refresh_collections(self, of_type: str = "bird") -> dict[str, Collection]:
        """Returns the remote bird collections"""
        data = await self._make_request(query=queries.me.COLLECTIONS)
        collections = {
            (c := Collection(d)).collection_id: c
            for d in data["me"]["collections"]
            # __typename: CollectionBird
            if d["__typename"] == f"Collection{of_type.capitalize()}"
        }
        self._collections.update(collections)
        return self._collections

    @property
    def collections(self) -> dict[str, Collection]:
        if self._needs_login():
            LOGGER.warning(
                "BirdBuddy is not logged in. Call refresh_collections() first"
            )
            return {}
        return self._collections

    @property
    def feeders(self) -> dict[str, Feeder]:
        """The Feeder devices associated with the account."""
        if self._needs_login():
            LOGGER.warning("BirdBuddy is not logged in. Call refresh() first")
            return {}
        return self._feeders
