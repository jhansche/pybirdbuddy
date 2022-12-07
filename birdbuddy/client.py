import logging
from datetime import datetime

from python_graphql_client import GraphqlClient

import birdbuddy.queries
from birdbuddy.const import BB_URL
from birdbuddy.feeder import Feeder

_LOGGER = logging.getLogger(__name__)


class BirdBuddy:
    graphql: GraphqlClient
    _email: str
    _password: str
    _access_token: [str, None]
    _refresh_token: [str, None]
    _me: [dict, None]
    _feeders: dict[str, Feeder]

    def __init__(self, email: str, password: str):
        self.graphql = GraphqlClient(BB_URL)
        self._email = email
        self._password = password
        self._access_token = None
        self._refresh_token = None
        self._me = None
        self._feeders = {}

    def _save_me(self, me: dict):
        if not me:
            return False
        me['__last_updated'] = datetime.now()
        self._me = me
        for f in me.get('feeders', []):
            if f['id'] in self._feeders:
                # Refresh Feeder data inline
                self._feeders[f['id']].update(f)
            else:
                self._feeders[f['id']] = Feeder(f)
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
        import birdbuddy.queries.debug
        return await self.graphql.execute_async(
            query=birdbuddy.queries.debug.DUMP_SCHEMA)

    async def _login(self) -> bool:
        assert self._email and self._password
        variables = {
            "emailSignInInput": {
                "email": self._email,
                "password": self._password,
            }
        }
        data = await self.graphql.execute_async(
            query=birdbuddy.queries.auth.SignIn, variables=variables)
        if not data:
            _LOGGER.error("GraphQL had no response: {}", data)
            return False
        elif not data.get('data'):
            self._clear()
            _LOGGER.warning("GraphQL Signin failed: {}", data)
            return False

        result = data['data']['authEmailSignIn']
        self._access_token = result['accessToken']
        self._refresh_token = result['refreshToken']
        return self._save_me(result['me'])

    async def _refresh_access_token(self) -> bool:
        assert self._refresh_token
        variables = {
            "refreshTokenInput": {
                "token": self._refresh_token,
            }
        }
        data = await self.graphql.execute_async(
            query=birdbuddy.queries.auth.RefreshAuthToken,
            variables=variables)
        if not data:
            _LOGGER.warning("GraphQL had no response: {}", data)
            return False
        elif not data.get('data', {}).get('authRefreshToken'):
            _LOGGER.warning("Unexpected GraphQL response: {}", data)
            # TODO: check for expired refresh token
            self._refresh_token = None
            return False
        result = data['data']['authRefreshToken']
        self._access_token = result.get('accessToken')
        self._refresh_token = result.get('refreshToken')
        _LOGGER.debug("Refreshed access token...")
        return not self._needs_refresh()

    async def refresh(self) -> bool:
        if self._needs_login():
            return await self._login()
        elif self._needs_refresh():
            return (await self._refresh_access_token()
                    and await self.refresh())
        else:
            data = await self.graphql.execute_async(
                query=birdbuddy.queries.me.Me, headers=self._headers())
            if not data:
                # No response?
                _LOGGER.warning("GraphQL had no response: {}", data)
                return False
            if not data.get('data', {}).get('me'):
                err = data.get('errors', []).pop()
                if err and (err.get('extensions', {}).get('code') ==
                            'AUTH_TOKEN_EXPIRED_ERROR'):
                    # Access token is good for 15 minutes
                    _LOGGER.info("Access token expired -> refreshing now...")
                    self._access_token = None
                    return (await self._refresh_access_token()
                            and await self.refresh())
                _LOGGER.warning("Unexpected GraphQL response: {}", data)
                return False
            _LOGGER.debug("Feeder data refreshed successfully.")
            return self._save_me(data['data']['me'])

    @property
    def feeders(self) -> dict[str, Feeder]:
        if self._needs_login():
            _LOGGER.error("BirdBuddy is not logged in. Call refresh() first.")
            return {}
        return self._feeders
