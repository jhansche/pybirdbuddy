"""Bird Buddy client module."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

import langcodes
from python_graphql_client import GraphqlClient

from birdbuddy import LOGGER, VERBOSE, queries
from birdbuddy.const import BB_URL
from birdbuddy.exceptions import (
    AuthenticationFailedError,
    AuthTokenExpiredError,
    GraphqlError,
    NoResponseError,
    UnexpectedResponseError,
)
from birdbuddy.feed import Feed, FeedNode, FeedNodeType
from birdbuddy.feeder import Feeder, FeederUpdateStatus, PowerProfile
from birdbuddy.media import Collection, Media
from birdbuddy.postcards import CollectedPostcard
from birdbuddy.queries.debug import DUMP_SCHEMA
from birdbuddy.user import BirdBuddyUser

_NO_VALUE = object()
"""Sentinel value to allow None to override a default value."""

_MAX_PAGE_SIZE = 100
"""The largest page size the API accepts; a larger ``first`` errors server
side (HTTP 200 with a GraphQL ``INTERNAL_SERVER_ERROR``)."""


def _redact(data: object, redacted: bool = True) -> object:
    """Return a redacted string if necessary."""
    return "**REDACTED**" if redacted else data


def _require_page_size(page_size: int) -> None:
    """Validate a pagination page size.

    Args:
        page_size: The requested per-page item count.

    Raises:
        ValueError: If ``page_size`` is not between 1 and the API's limit.
    """
    if not 1 <= page_size <= _MAX_PAGE_SIZE:
        msg = f"page size must be between 1 and {_MAX_PAGE_SIZE}"
        raise ValueError(msg)


class BirdBuddy:
    """Bird Buddy api client."""

    graphql: GraphqlClient
    _email: str | None
    _password: str | None
    _access_token: str | None
    _refresh_token: str | None
    _language_code: str
    _me: BirdBuddyUser | None
    _feeders: dict[str, Feeder]
    _collections: dict[str, Collection]
    _last_feed_date: datetime | None

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        /,
        refresh_token: str | None = None,
        access_token: str | None = None,
    ) -> None:
        """Initialize the Bird Buddy client.

        Args:
            email: Account email, for password login.
            password: Account password, for password login.
            refresh_token: An existing refresh token, to skip password login.
            access_token: An existing access token.
        """
        self._email = email
        self._password = password
        self._refresh_token = refresh_token
        self._access_token = access_token

        self.graphql = GraphqlClient(BB_URL)
        self._me = None
        self._last_feed_date = None
        self._feeders = {}
        self._collections = {}
        self.language_code = "en"

    def _save_me(self, me_data: dict) -> bool:
        if not me_data:
            return False
        me_data["__last_updated"] = datetime.now()
        self._me = BirdBuddyUser(me_data["user"])
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
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept-Language": self._language_code,
        }

    def _clear(self) -> None:
        self._access_token = None
        self._refresh_token = None
        self._me = None

    async def dump_schema(self) -> dict:
        """For debugging purposes: dump the entire GraphQL schema."""
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
        """Sign in with email/password and store the tokens.

        Returns:
            ``True`` if the user profile was saved.

        Raises:
            AuthenticationFailedError: If credentials are missing or the
                sign-in request fails.
        """
        if not (self._email and self._password):
            msg = "email and password are required to sign in"
            raise AuthenticationFailedError(msg)
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
        """Exchange the refresh token for a new access token.

        Returns:
            ``True`` once a new access token is set.

        Raises:
            AuthenticationFailedError: If no refresh token is set or the
                refresh request fails.
        """
        if not self._refresh_token:
            msg = "a refresh token is required to refresh the access token"
            raise AuthenticationFailedError(msg)
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
        variables: dict | None = None,
        auth: bool = True,
        reauth: bool = True,
        subscript: str | None = None,
    ) -> dict:
        """Execute a GraphQL request and return the unwrapped ``data``.

        Args:
            query: The GraphQL query or mutation string.
            variables: GraphQL variables, if any.
            auth: Whether to attach auth headers (refreshing tokens first).
            reauth: Whether to retry once after an expired-token error.
            subscript: If set, return ``data[subscript]`` instead of ``data``.

        Returns:
            The response ``data`` dict, or ``data[subscript]`` when given.

        Raises:
            NoResponseError: If the response was empty or not a dict.
            UnexpectedResponseError: If the response carried no ``data``.
            GraphqlError: If the response reported one or more errors.
        """
        if auth:
            await self._check_auth()
            headers = self._headers()
        else:
            headers = {}

        should_redact = query in [
            queries.auth.REFRESH_AUTH_TOKEN,
            queries.auth.SIGN_IN,
        ]
        LOGGER.debug(
            "> GraphQL %s, vars=%s",
            query.partition("\n")[0],  # First line of query
            _redact(variables, should_redact),
        )
        response = await self.graphql.execute_async(
            query=query,
            variables=variables or {},
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

        LOGGER.log(VERBOSE, "< response: %s", _redact(result, should_redact))
        if subscript:
            return result[subscript]
        return result

    async def _iter_pages(
        self,
        query: str,
        variables: dict[str, Any],
        connection: Callable[[dict], dict],
    ) -> AsyncIterator[dict]:
        """Yield successive pages of a Relay connection, following the cursor.

        Requests ``query`` repeatedly, advancing ``after`` by the previous
        page's ``endCursor`` until ``hasNextPage`` is false. Terminates
        defensively if the server reports another page but returns no usable
        cursor (missing, null, or one already seen), rather than looping
        forever on a stuck cursor.

        Args:
            query: The GraphQL query text; it must accept an ``after`` cursor
                and select ``pageInfo { hasNextPage endCursor }``.
            variables: Base variables sent with every page (e.g. ``first``);
                ``after`` is injected per page.
            connection: Extracts the connection object (the one carrying
                ``edges`` and ``pageInfo``) from a response ``data`` dict.

        Yields:
            Each page's connection object, oldest cursor first.
        """
        after: str | None = None
        seen: set[str] = set()
        while True:
            page_vars = dict(variables)
            if after is not None:
                # The API errors on an explicit ``after: null``; omit it for
                # the first page and only send a real cursor.
                page_vars["after"] = after
            data = await self._make_request(query=query, variables=page_vars)
            page = connection(data)
            yield page

            page_info = page.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                return
            cursor = page_info.get("endCursor")
            if not cursor or cursor in seen:
                # Defensive: the server claims another page but gave no new
                # cursor to advance with. Stop instead of re-requesting.
                LOGGER.debug(
                    "Pagination stopped: hasNextPage but cursor did not "
                    "advance (endCursor=%r)",
                    cursor,
                )
                return
            seen.add(cursor)
            after = cursor

    @property
    def user(self) -> None | BirdBuddyUser:
        """The logged in user data."""
        return self._me

    @property
    def language_code(self) -> str:
        """The current language code."""
        return self._language_code

    @language_code.setter
    def language_code(self, language_code: str) -> None:
        """Set the language used in API requests.

        Useful for localized responses, including translated bird species
        names.

        Args:
            language_code: A BCP 47 language tag (e.g. ``"de"``), normalized
                via ``langcodes.standardize_tag``.
        """
        self._language_code = langcodes.standardize_tag(language_code)

    async def refresh(self) -> bool:
        """Refresh the Bird Buddy feeder data."""
        data = await self._make_request(query=queries.me.ME)
        LOGGER.debug("Feeder data refreshed successfully: %s", data)
        return self._save_me(data["me"])

    async def toggle_off_grid(
        self,
        feeder: Feeder | str,
        is_off_grid: bool,
    ) -> Feeder:
        """Toggle the feeder's off-grid status.

        Available to the owner account only.

        Args:
            feeder: The Feeder or its id to update.
            is_off_grid: Whether to enable off-grid mode.

        Returns:
            The Feeder once the status has updated.
        """
        if isinstance(feeder, Feeder):
            feeder_id = feeder.id
            if not feeder.is_owner:
                LOGGER.warning("Off-grid is available only to owner accounts")
                # The request will fail
        else:
            # We cannot check the owner status if we only have an id
            feeder_id = feeder
        variables = {
            "feederId": feeder_id,
            "feederToggleOffGridInput": {
                "offGrid": is_off_grid,
            },
        }
        result = await self._make_request(
            query=queries.feeder.TOGGLE_OFF_GRID,
            variables=variables,
        )
        LOGGER.debug("Off-grid result: %s", result)
        # The off-grid status doesn't get updated right away.

        new_off_grid = result["feederToggleOffGrid"]["feeder"]["offGrid"]

        while new_off_grid != is_off_grid:
            LOGGER.debug("waiting for off-grid to update")
            await asyncio.sleep(1)
            await self.refresh()
            new_off_grid = self.feeders[feeder_id].is_off_grid
        return self.feeders[feeder_id]

    async def toggle_audio_enabled(
        self,
        feeder: Feeder | str,
        is_audio_enabled: bool,
    ) -> Feeder:
        """Toggle the feeder's audio-enabled setting.

        Available to the owner account only.

        Args:
            feeder: The Feeder or its id to update.
            is_audio_enabled: Whether videos should include audio.

        Returns:
            The Feeder once the setting has updated.
        """
        if isinstance(feeder, Feeder):
            feeder_id = feeder.id
            if not feeder.is_owner:
                LOGGER.warning(
                    "Audio setting is available only to owner accounts"
                )
                # The request will fail
        else:
            # We cannot check the owner status if we only have an id
            feeder_id = feeder
        variables = {
            "feederId": feeder_id,
            "feederToggleAudioInput": {
                "audioEnabled": is_audio_enabled,
            },
        }
        result = await self._make_request(
            query=queries.feeder.TOGGLE_AUDIO_ENABLED,
            variables=variables,
        )
        LOGGER.debug("Audio toggle result: %s", result)
        # The status doesn't get updated right away.

        new_setting = result["feederToggleAudio"]["feeder"]["audioEnabled"]

        while new_setting != is_audio_enabled:
            LOGGER.debug("waiting for audio setting to update")
            await asyncio.sleep(1)
            await self.refresh()
            new_setting = self.feeders[feeder_id].is_audio_enabled
        return self.feeders[feeder_id]

    async def feed(
        self,
        first: int = 20,
        after: str | None = None,
        last: int | None = None,  # noqa: ARG002
        before: str | None = None,
    ) -> Feed:
        """Return the Bird Buddy Feed.

        The result contains a ``"pageInfo"`` key for pagination/cursor data
        and an ``"edges"`` key with FeedEdge nodes, newest first.

        Args:
            first: Return the first N items older than ``after``. Must be
                1-100; the API returns an internal error for larger values.
            after: Cursor of the oldest item previously seen (pagination).
            last: Return the last N items newer than ``before``. Currently
                ignored; the backward-pagination request path is disabled.
            before: Cursor of the newest item previously seen. Currently
                ignored (see ``last``).

        Returns:
            The Feed.

        Raises:
            ValueError: If ``first`` is not between 1 and 100.
        """
        _require_page_size(first)
        variables: dict[str, Any] = {
            # $first: Int,
            # $after: String,
            # $last: Int,
            # $before: String,
            "first": first,
        }

        if after:
            # $after actually looks for _older_ items
            variables["after"] = after

        if before:
            # Not implemented server-side (GraphqlError 501).
            #  variables["before"] = before
            #  variables["last"] = last if last else 20
            pass

        data = await self._make_request(
            query=queries.me.FEED, variables=variables
        )
        return Feed(data["me"]["feed"])

    def _feed_pages(self) -> AsyncIterator[dict]:
        """Iterate feed connection pages, newest first, one per request."""
        return self._iter_pages(
            query=queries.me.FEED,
            variables={"first": _MAX_PAGE_SIZE},
            connection=lambda data: data["me"]["feed"],
        )

    def _note_newest_feed_date(self, feed: Feed) -> None:
        """Advance the saved last-seen timestamp to a page's newest item.

        Args:
            feed: A feed page; its newest edge sets the last-seen timestamp.
        """
        if not (newest_edge := feed.newest_edge):
            return
        newest_date = newest_edge.node.created_at
        if newest_date is not None and newest_date != self._last_feed_date:
            LOGGER.debug(
                "Updating latest seen Feed timestamp: %s -> %s",
                self._last_feed_date,
                newest_date,
            )
            self._last_feed_date = newest_date

    async def refresh_feed(
        self,
        since: datetime | str = _NO_VALUE,  # type: ignore[assignment]
    ) -> list[FeedNode]:
        """Return only feed items new since the last refresh.

        Pages backward through the feed (newest first) until it reaches
        items no newer than ``since``, so more than one page of new items is
        returned rather than truncated at the first page. The newest item's
        timestamp is saved as the last-seen feed item, the new default for
        ``since``.

        With no ``since`` and no prior refresh there is no lower bound to
        page toward, so only the most recent page is returned; this avoids
        replaying the entire history on a first refresh.

        Args:
            since: The time after which to restrict new feed items; defaults
                to the last-seen timestamp.

        Returns:
            The new feed nodes, newest first.
        """
        resolved = self._last_feed_date if since is _NO_VALUE else since
        if isinstance(resolved, str):
            resolved = FeedNode.parse_datetime(resolved)

        if resolved is None:
            feed = await self.feed()
            self._note_newest_feed_date(feed)
            return feed.filter(newer_than=None)

        new_nodes: list[FeedNode] = []
        noted = False
        async for page in self._feed_pages():
            feed = Feed(page)
            if not noted:
                self._note_newest_feed_date(feed)
                noted = True
            new_nodes.extend(feed.filter(newer_than=resolved))
            oldest = min(
                (n.created_at for n in feed.nodes if n.created_at),
                default=None,
            )
            if oldest is not None and oldest <= resolved:
                # Reached items no newer than the cutoff; older pages hold
                # nothing new.
                break
        return new_nodes

    async def feed_nodes(self, node_type: FeedNodeType) -> list[FeedNode]:
        """Return all feed items of the given type across every page.

        Args:
            node_type: The feed node type to filter by.

        Returns:
            The matching feed nodes, newest first.
        """
        nodes: list[FeedNode] = []
        async for page in self._feed_pages():
            nodes.extend(Feed(page).filter(of_type=node_type))
        return nodes

    async def new_postcards(self) -> list[FeedNode]:
        """Return all new 'Postcard' feed items.

        These can be collected with ``collect_postcard``.
        """
        return await self.feed_nodes(FeedNodeType.NewPostcard)

    def _postcard_id(self, postcard: str | FeedNode) -> str:
        """Resolve a postcard argument to its feed-item id.

        Args:
            postcard: A postcard feed-item id, or a ``NewPostcard`` FeedNode.

        Returns:
            The feed-item id.

        Raises:
            ValueError: If ``postcard`` is a FeedNode that is not a
                NewPostcard.
            TypeError: If ``postcard`` is neither a str nor a FeedNode.
        """
        if isinstance(postcard, str):
            return postcard
        if isinstance(postcard, FeedNode):
            if postcard.node_type != FeedNodeType.NewPostcard:
                msg = f"expected a NewPostcard, got {postcard.node_type}"
                raise ValueError(msg)
            return postcard.node_id
        msg = f"postcard must be a str or FeedNode, got {type(postcard)}"
        raise TypeError(msg)

    async def reanalyze_postcard(
        self,
        postcard: str | FeedNode,
    ) -> dict:
        """Trigger the AI identification (reanalysis) for a postcard.

        Changes the inference execution mode from MANUAL_NOT_STARTED to
        MANUAL_COMPLETED and populates the sighting report preview. It is
        idempotent: an already-analyzed postcard returns MANUAL_COMPLETED
        with reanalyzeAvailability ALREADY_REANALYZED.

        Args:
            postcard: A postcard feed-item id, or a ``NewPostcard`` FeedNode.

        Returns:
            The ``inferenceExternalPostcardReanalyze`` result payload.

        Raises:
            ValueError: If ``postcard`` is a FeedNode that is not a
                NewPostcard.
        """
        variables = {"feedItemId": self._postcard_id(postcard)}
        result = await self._make_request(
            query=queries.birds.POSTCARD_REANALYZE,
            variables=variables,
        )
        return result["inferenceExternalPostcardReanalyze"]

    async def collect_postcard(
        self,
        postcard: str | FeedNode,
        *,
        share: bool = False,
    ) -> CollectedPostcard:
        """Collect a postcard into your account.

        Reanalyzes the postcard first (idempotent, so it is safe whether or
        not inference has already run), then collects it with the species the
        backend recognized.

        Args:
            postcard: A postcard feed-item id, or a ``NewPostcard`` FeedNode.
            share: Whether to share the collected media.

        Returns:
            The collected postcard.

        Raises:
            ValueError: If ``postcard`` is a FeedNode that is not a
                NewPostcard.
            TypeError: If ``postcard`` is neither a str nor a FeedNode.
        """
        postcard_id = self._postcard_id(postcard)
        await self.reanalyze_postcard(postcard_id)
        result = await self._make_request(
            query=queries.birds.POSTCARD_COLLECT,
            variables={
                "feedItemId": postcard_id,
                "postcardCollectInput": {"share": share},
            },
        )
        return CollectedPostcard(
            result["postcardCollect"]["collectedPostcard"]
        )

    async def share_medias(
        self, media_ids: list[str], share: bool = True
    ) -> bool:
        """Toggle sharing for the given media.

        Args:
            media_ids: The media ids to update.
            share: ``True`` to share, ``False`` to unshare.

        Returns:
            ``True`` if the toggle succeeded.
        """
        variables = {
            "mediaShareToggleInput": {
                "mediaIds": media_ids,
                "share": share,
            }
        }
        result = await self._make_request(
            query=queries.birds.SHARE_MEDIAS,
            variables=variables,
        )
        return bool(result["mediaShareToggle"]["success"])

    async def refresh_collections(
        self, of_type: str = "bird"
    ) -> dict[str, Collection]:
        """Fetch and cache the remote collections.

        Args:
            of_type: The collection type to keep (e.g. ``"bird"``).

        Returns:
            The cached collections, keyed by collection id.
        """
        data = await self._make_request(query=queries.me.COLLECTIONS)
        collections = {
            (c := Collection(d)).collection_id: c
            for d in data["me"]["collections"]
            # __typename: CollectionBird
            if d["__typename"] == f"Collection{of_type.capitalize()}"
        }
        self._collections.update(collections)
        return self._collections

    async def set_feeder_options(
        self, feeder: Feeder | str, **kwargs: bool | str
    ) -> dict:
        """Update Feeder options.

        Args:
            feeder: The Feeder or its id to update.
            **kwargs: Feeder options to set. Recognized keys:
                ``lowBatteryNotification`` (bool), ``lowFoodNotification``
                (bool), ``name`` (str), ``offGrid`` (bool), ``offlineMode``
                (bool).

        Returns:
            The updated feeder-options payload.
        """
        if isinstance(feeder, Feeder):
            feeder_id = feeder.id
            if not feeder.is_owner:
                LOGGER.warning(
                    "Setting Feeder options requires an owner account"
                )
        else:
            feeder_id = feeder
        variables = {
            "feederId": feeder_id,
            "feederUpdateInput": {
                k: v
                for (k, v) in kwargs.items()
                if k
                in [
                    "lowBatteryNotification",
                    "lowFoodNotification",
                    "name",
                    "offGrid",
                    "offlineMode",
                ]
            },
        }
        updated = await self._make_request(
            query=queries.feeder.SET_OPTIONS,
            variables=variables,
            subscript="feederUpdate",
        )
        self.feeders[feeder_id].update(updated)
        return updated

    async def set_power_profile(
        self, feeder: Feeder | str, profile: PowerProfile
    ) -> dict:
        """Update the feeder's power profile.

        Args:
            feeder: The Feeder or its id to update.
            profile: The power profile to set.

        Returns:
            A dict with the resulting ``powerProfile``.
        """
        if isinstance(feeder, Feeder):
            feeder_id = feeder.id
            if not feeder.is_owner:
                LOGGER.warning(
                    "Frequency setting is available only to owner accounts"
                )
        else:
            feeder_id = feeder
        variables = {
            "feederId": feeder_id,
            "feederUpdatePowerProfileInput": {
                "powerProfile": profile.value,
            },
        }
        result = await self._make_request(
            query=queries.feeder.UPDATE_POWER_PROFILE,
            variables=variables,
            subscript="feederUpdatePowerProfile",
        )
        # May raise GraphqlError `PAYMENTS_SUBSCRIPTION_IS_NOT_ACTIVE`,
        # implying that `FRENZY_MODE` is a paid feature.
        updated = {
            "powerProfile": result.get("feeder", {}).get("powerProfile", None)
        }

        if result["__typename"] == "FeederUpdatePowerProfileInProgressResult":
            # Refresh after a short delay
            # We could also poll `feederUpdatePowerProfileCheck`
            LOGGER.debug("PowerProfile update is in progress")
            await asyncio.sleep(0.25)
            await self.refresh()
            updated["powerProfile"] = self.feeders[
                feeder_id
            ].power_profile.value
        else:
            self.feeders[feeder_id].update(updated)
        return updated

    async def update_firmware_start(
        self, feeder: Feeder | str
    ) -> FeederUpdateStatus:
        """Start a firmware update.

        Args:
            feeder: The Feeder or its id to update.

        Returns:
            The firmware update status.
        """
        current_status = await self.update_firmware_check(feeder)

        if current_status.is_in_progress:
            # There's already an update in progress
            return current_status

        feeder_id: str
        if isinstance(feeder, Feeder):
            if not feeder.is_owner:
                LOGGER.warning(
                    "Firmware update is available only to owner accounts"
                )
                # The request will fail
            feeder_id = feeder.id
        else:
            feeder_id = feeder
        variables = {"feederId": feeder_id}
        try:
            data = await self._make_request(
                query=queries.feeder.UPDATE_FIRMWARE,
                variables=variables,
            )
        except GraphqlError as err:
            if err.error_code == "FEEDER_FIRMWARE_UPGRADE_ALREADY_IN_PROGRESS":
                # Should have been handled above.
                return current_status
            raise
        LOGGER.debug("start firmware update response: %s", data)
        result = FeederUpdateStatus(data["feederFirmwareUpdateStart"])
        if result.is_complete:
            # After completion, update the Feeder state
            self.feeders[feeder_id].update(result.get("feeder", {}))
        return result

    async def update_firmware_check(
        self, feeder: Feeder | str
    ) -> FeederUpdateStatus:
        """Check on a firmware update.

        Args:
            feeder: The Feeder or its id to check.

        Returns:
            The current firmware update status.
        """
        if isinstance(feeder, Feeder):
            if not feeder.is_owner:
                LOGGER.warning(
                    "Firmware update is available only to owner accounts"
                )
                # The request will fail
            feeder_id = feeder.id
        else:
            feeder_id = feeder
        variables = {"feederId": feeder_id}
        data = await self._make_request(
            query=queries.feeder.UPDATE_FIRMWARE_PROGRESS,
            variables=variables,
        )
        result = FeederUpdateStatus(data["feederFirmwareUpdateCheckProgress"])
        if result.is_complete:
            self.feeders[feeder_id].update(result.get("feeder", {}))
        return result

    @property
    def collections(self) -> dict[str, Collection]:
        """Return the last seen cached Collections.

        Note that this may be outdated.

        See also :func:`BirdBuddy.refresh_collections()`
        """
        if self._needs_login():
            LOGGER.warning(
                "BirdBuddy is not logged in. Call refresh_collections() first"
            )
            return {}

        for collection in list(self._collections.values()):
            if collection.cover_media.is_expired:
                del self._collections[collection.collection_id]
        return self._collections

    async def collection(
        self, collection_id: str, page_size: int = 50
    ) -> dict[str, Media]:
        """Return all media in the specified collection.

        Follows pagination so collections larger than one page are fully
        retrieved (not truncated to the first page).

        Args:
            collection_id: The collection ``UUID``.
            page_size: How many media to request per page. Must be 1-100; the
                API returns an internal error for larger page sizes.

        Returns:
            A mapping of ``media_id`` to its ``Media``.

        Raises:
            ValueError: If ``page_size`` is not between 1 and 100.
        """
        _require_page_size(page_size)
        result: dict[str, Media] = {}
        variables = {"collectionId": collection_id, "first": page_size}
        pages = self._iter_pages(
            query=queries.me.COLLECTIONS_MEDIA,
            variables=variables,
            connection=lambda data: data["collection"]["media"],
        )
        async for media in pages:
            for edge in media["edges"]:
                node = edge["node"]["media"]
                result[node["id"]] = Media(node)
        return result

    async def latest_collections(
        self,
    ) -> dict[str, Collection]:
        """Return the latest collections."""
        # TODO(roger): queries.me has no LATEST_MEDIA, so this raises
        # AttributeError at runtime.
        query = queries.me.LATEST_MEDIA  # type: ignore[attr-defined]
        return await self._make_request(query=query)

    @property
    def feeders(self) -> dict[str, Feeder]:
        """The Feeder devices associated with the account."""
        if self._needs_login():
            LOGGER.warning("BirdBuddy is not logged in. Call refresh() first")
            return {}
        return self._feeders
