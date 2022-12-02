import logging
from datetime import datetime

from python_graphql_client import GraphqlClient

import birdbuddy.queries.auth
import birdbuddy.queries.me
from birdbuddy.const import BB_URL

_LOGGER = logging.getLogger(__name__)


class BirdBuddy:
    def __init__(self, email, password):
        self.graphql = GraphqlClient(BB_URL)
        self._email = email
        self._password = password
        self._access_token = None
        self._refresh_token = None
        self._me = None

    def _save_me(self, me):
        if not me:
            return False
        me['__last_updated'] = datetime.now()
        self._me = me
        return True

    def _needs_login(self) -> bool:
        return self._refresh_token is None

    def _needs_refresh(self) -> bool:
        return self._access_token is None

    def _headers(self) -> dict:
        return {"Authorization": "Bearer " + self._access_token}

    def _clear(self):
        self._access_token = None
        self._refresh_token = None
        self._me = None

    def _login(self) -> bool:
        assert self._email and self._password
        variables = {
            "emailSignInInput": {
                "email": self._email,
                "password": self._password,
            }
        }
        data = self.graphql.execute(query=birdbuddy.queries.auth.SignIn, variables=variables)
        if not data:
            _LOGGER.error("GraphQL had no response: {}", data)
            return False
        elif not data.get('data'):
            self._clear()
            _LOGGER.warning("GraphQL Signin failed: {}", data)
            return False

        self._access_token = data['data']['authEmailSignIn']['accessToken']
        self._refresh_token = data['data']['authEmailSignIn']['refreshToken']
        # TODO: check for Problem
        return self._save_me(data['data']['authEmailSignIn']['me'])

    def _refresh_access_token(self) -> bool:
        assert self._refresh_token
        variables = {
            "refreshTokenInput": {
                "token": self._refresh_token,
            }
        }
        data = self.graphql.execute(query=birdbuddy.queries.auth.RefreshAuthToken, variables=variables)
        if not data:
            _LOGGER.warning("GraphQL had no response: {}", data)
            return False
        elif not data.get('data'):
            _LOGGER.warning("GraphQL had no response: {}", data)
            # TODO: check for expired refresh token
            self._refresh_token = None
            return False
        self._access_token = data['data']['authRefreshToken']['accessToken']
        self._refresh_token = data['data']['authRefreshToken']['refreshToken']
        _LOGGER.debug("Refreshed access token...")
        return not self._needs_refresh()

    def refresh(self) -> bool:
        if self._needs_login():
            return self._login()
        elif self._needs_refresh():
            return self._refresh_access_token() and self.refresh()
        else:
            data = self.graphql.execute(query=birdbuddy.queries.me.Me, headers=self._headers())
            if not data:
                # No response?
                _LOGGER.warning("GraphQL had no response: {}", data)
                return False
            if not data.get('data'):
                err = data.get('errors', []).pop()
                if err and err.get('extensions', {}).get('code') == 'AUTH_TOKEN_EXPIRED_ERROR':
                    # Access token is good for 15 minutes
                    _LOGGER.info("Access token expired -> refreshing now...")
                    self._access_token = None
                    return self._refresh_access_token() and self.refresh()
                _LOGGER.warning("Unexpected GraphQL response: {}", data)
                return False
            _LOGGER.debug("Feeder data refreshed successfully.")
            return self._save_me(data['data']['me'])

    @property
    def feeders(self):
        if self._needs_login():
            # FIXME: do not block property access
            _LOGGER.debug("BirdBuddy.feeders access triggering login...")
            assert self._login()
        assert self._me is not None
        return self._me.get('feeders', [])
