"""Bird Buddy client module."""

from __future__ import annotations

import asyncio
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
from birdbuddy.queries.debug import DUMP_SCHEMA
from birdbuddy.sightings import (
    PostcardSighting,
    Sighting,
    SightingCreateProgress,
    SightingFinishMod,
    SightingFinishStrategy,
    SightingReport,
)
from birdbuddy.user import BirdBuddyUser

_NO_VALUE = object()
"""Sentinel value to allow None to override a default value."""


def _redact(data: object, redacted: bool = True) -> object:
    """Return a redacted string if necessary."""
    return "**REDACTED**" if redacted else data


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
                LOGGER.warning("Audio setting is available only to owner accounts")
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
            first: Return the first N items older than ``after``.
            after: Cursor of the oldest item previously seen (pagination).
            last: Return the last N items newer than ``before``. Currently
                ignored; the backward-pagination request path is disabled.
            before: Cursor of the newest item previously seen. Currently
                ignored (see ``last``).

        Returns:
            The Feed.
        """
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

        data = await self._make_request(query=queries.me.FEED, variables=variables)
        return Feed(data["me"]["feed"])

    async def refresh_feed(
        self,
        since: datetime | str = _NO_VALUE,  # type: ignore[assignment]
    ) -> list[FeedNode]:
        """Return only feed items new since the last refresh.

        The most recent edge node timestamp is saved as the last-seen feed
        item, which becomes the new default value for ``since``. Useful to,
        for example, restore a last-seen timestamp in a new instance.

        Args:
            since: The time after which to restrict new feed items; defaults
                to the last-seen timestamp.

        Returns:
            The new feed nodes.
        """
        resolved = self._last_feed_date if since is _NO_VALUE else since
        if isinstance(resolved, str):
            resolved = FeedNode.parse_datetime(resolved)
        feed = await self.feed()
        if (newest_edge := feed.newest_edge) and (
            newest_date := newest_edge.node.created_at
        ) != self._last_feed_date:
            LOGGER.debug(
                "Updating latest seen Feed timestamp: %s -> %s",
                self._last_feed_date,
                newest_date,
            )
            self._last_feed_date = newest_date
        return feed.filter(newer_than=resolved)

    async def feed_nodes(self, node_type: FeedNodeType) -> list[FeedNode]:
        """Return all feed items of the given type.

        Args:
            node_type: The feed node type to filter by.

        Returns:
            The matching feed nodes.
        """
        feed = await self.feed()
        return feed.filter(of_type=node_type)

    async def new_postcards(self) -> list[FeedNode]:
        """Return all new 'Postcard' feed items.

        These node types are converted into sightings using
        ``sighting_from_postcard``.
        """
        return await self.feed_nodes(FeedNodeType.NewPostcard)

    async def reanalyze_postcard(
        self,
        postcard: str | FeedNode,
    ) -> dict:
        """Trigger the AI identification (reanalysis) for a postcard.

        Changes the inference execution mode from MANUAL_NOT_STARTED to
        MANUAL_COMPLETED and populates the sighting report preview.

        Args:
            postcard: A postcard feed-item id, or a ``NewPostcard`` FeedNode.

        Returns:
            The ``inferenceExternalPostcardReanalyze`` result payload.

        Raises:
            ValueError: If ``postcard`` is a FeedNode that is not a
                NewPostcard.
        """
        postcard_id: str
        if isinstance(postcard, str):
            postcard_id = postcard
        elif isinstance(postcard, FeedNode):
            if postcard.node_type != FeedNodeType.NewPostcard:
                msg = f"expected a NewPostcard, got {postcard.node_type}"
                raise ValueError(msg)
            postcard_id = postcard.node_id

        variables = {"feedItemId": postcard_id}
        result = await self._make_request(
            query=queries.birds.POSTCARD_REANALYZE,
            variables=variables,
        )
        return result["inferenceExternalPostcardReanalyze"]

    async def sighting_from_postcard(
        self,
        postcard: str | FeedNode,
    ) -> PostcardSighting:
        """Convert a postcard into a sighting report.

        Next step is to choose or confirm species and then finish the
        sighting. If the sighting type is ``SightingRecognized``, it can be
        collected with ``finish_postcard``.

        Args:
            postcard: A postcard feed-item id, or a ``NewPostcard`` FeedNode.

        Returns:
            The ``PostcardSighting`` for the postcard.

        Raises:
            ValueError: If ``postcard`` is a FeedNode that is not a
                NewPostcard.
        """
        postcard_id: str
        if isinstance(postcard, str):
            postcard_id = postcard
        elif isinstance(postcard, FeedNode):
            if postcard.node_type != FeedNodeType.NewPostcard:
                msg = f"expected a NewPostcard, got {postcard.node_type}"
                raise ValueError(msg)
            postcard_id = postcard.node_id
        variables = {
            "sightingCreateFromPostcardInput": {
                "feedItemId": postcard_id,
            }
        }
        result = await self._make_request(
            query=queries.birds.POSTCARD_TO_SIGHTING,
            variables=variables,
        )
        data = result["sightingCreateFromPostcard"]
        return PostcardSighting(data).with_postcard(postcard_id)

    async def finish_postcard(
        self,
        feed_item_id: str,
        sighting_result: PostcardSighting,
        strategy: SightingFinishStrategy = SightingFinishStrategy.RECOGNIZED,
        confidence_threshold: int | None = None,
        share_media: bool = False,
    ) -> bool:
        """Finish collecting the postcard into your collections.

        Args:
            feed_item_id: The id from ``new_postcards``.
            sighting_result: From ``sighting_from_postcard``; should contain
                sightings of type ``SightingRecognizedBird`` or
                ``SightingRecognizedBirdUnlocked``.
            strategy: One of ``RECOGNIZED``, ``BEST_GUESS``, or ``MYSTERY``.
            confidence_threshold: For ``BEST_GUESS``, accept the highest
                confidence suggestion above this threshold (defaults to 10%).
            share_media: ``True`` to share the finished media.

        Returns:
            ``True`` if the postcard was finished successfully.
        """
        if not isinstance(sighting_result, PostcardSighting):
            # See sighting_from_postcard()["sightingCreateFromPostcard"]
            LOGGER.warning("Unexpected sighting result: %s", sighting_result)
            return False

        report = sighting_result.report

        sighting: Sighting | None = None
        mod: SightingFinishMod | None = None
        for sighting, mod in report.sighting_finishing_strategies(
            confidence_threshold
        ).values():
            # if we need extra work, do it now and update `report`
            if mod.strategy == SightingFinishStrategy.RECOGNIZED:
                # Nothing to do, this will pass through as-is
                pass
            elif mod.strategy < strategy:
                # Caller chose not to allow this.
                # We will try to finish the postcard anyway.
                # This may result in losing the sighting data.
                LOGGER.info(
                    "Requested %s, but recommended strategy is %s",
                    strategy,
                    mod,
                )
            elif mod.strategy == SightingFinishStrategy.BEST_GUESS:
                # Choose the highest recommended species
                match_data = mod.data or {}
                LOGGER.debug(
                    "selecting highest confidence: %s%% for species %s",
                    match_data["confidence"],
                    match_data["speciesCode"],
                )
                new_report = await self.sighting_choose_species(
                    sighting.id,
                    match_data["speciesCode"],
                    report,
                )
                LOGGER.debug(
                    "replacing report after choosing species:\nold=%s\nnew=%s",
                    report,
                    new_report,
                )
                report = new_report
            elif mod.strategy == SightingFinishStrategy.MYSTERY:
                new_report = await self.sighting_choose_mystery(
                    sighting.id,
                    report,
                )
                LOGGER.debug(
                    "replacing report (mystery):\nold=%s\nnew=%s",
                    report,
                    new_report,
                )
                report = new_report

        variables = {
            "sightingReportPostcardFinishInput": {
                "feedItemId": feed_item_id,
                "defaultCoverMedia": [
                    s.cover_media for s in report.sightings if s.is_unlocked
                ],
                "notSelectedMediaIds": [],
                "reportToken": report.token,
            }
        }
        if video := next(iter(sighting_result.video_media), None):
            variables["sightingReportPostcardFinishInput"]["videoMediaId"] = video.id
        data = await self._make_request(
            query=queries.birds.FINISH_SIGHTING,
            variables=variables,
        )
        result = bool(data["sightingReportPostcardFinish"]["success"])
        if share_media:
            media_ids = [m.id for m in sighting_result.medias]
            try:
                share_result = await self.share_medias(media_ids, share=True)
                LOGGER.info("Sharing %d medias: %s", len(media_ids), share_result)
            except Exception as err:  # pylint: disable=broad-except  # noqa: BLE001
                LOGGER.error(
                    "Error sharing %d medias: %s",
                    len(media_ids),
                    err,
                    exc_info=err,
                )
                share_result = False
        return result

    async def share_medias(self, media_ids: list[str], share: bool = True) -> bool:
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

    async def sighting_create(
        self,
        media_ids: list[str],
    ) -> SightingCreateProgress:
        """Identify birds in media via a background process.

        Args:
            media_ids: The media ids to analyze.

        Returns:
            The initial ``SightingCreateProgress``.
        """
        variables = {
            "sightingCreateInput": {
                "mediaIds": media_ids,
            }
        }
        result = await self._make_request(
            query=queries.birds.SIGHTING_CREATE,
            variables=variables,
        )
        return SightingCreateProgress(
            result["sightingCreate"]["sightingCreateProgress"]
        )

    async def sighting_create_check_progress(
        self,
        sighting_create_id: str,
        watching_id: str,
    ) -> SightingCreateProgress | SightingReport:
        """Check the progress of a background bird identification.

        Args:
            sighting_create_id: The id from ``sighting_create``.
            watching_id: The watching id to poll.

        Returns:
            A ``SightingCreateProgress`` while pending, or a ``SightingReport``
            once identification completes.
        """
        variables = {
            "sightingCreateCheckProgressInput": {
                "sightingCreateId": sighting_create_id,
                "watchingId": watching_id,
            }
        }
        result = await self._make_request(
            query=queries.birds.SIGHTING_CREATE_PROGRESS,
            variables=variables,
        )
        data = result["sightingCreateCheckProgress"]
        if data.get("__typename") == "SightingReport":
            return SightingReport(data)
        return SightingCreateProgress(data)

    async def sighting_choose_species(
        self,
        sighting_id: str,
        species_id: str,
        sighting_data: SightingReport | str | None = None,
    ) -> SightingReport:
        """Manually assign a species to a sighting.

        Args:
            sighting_id: The sighting to update.
            species_id: The species to assign.
            sighting_data: The ``SightingReport`` or its report token.

        Returns:
            The updated ``SightingReport``.

        Raises:
            TypeError: If ``sighting_data`` is not a SightingReport or token.
        """
        token: str | None
        if isinstance(sighting_data, SightingReport):
            token = sighting_data.token
        elif isinstance(sighting_data, str):
            token = sighting_data
        else:
            msg = "sighting_data should be a SightingReport or its token"
            raise TypeError(msg)
        variables = {
            "sightingChooseSpeciesInput": {
                "sightingId": sighting_id,
                "speciesId": species_id,
                "reportToken": token,
            }
        }
        data = await self._make_request(
            query=queries.birds.SIGHTING_CHOOSE_SPECIES,
            variables=variables,
        )
        return SightingReport(data["sightingChooseSpecies"])

    async def sighting_choose_mystery(
        self,
        sighting_id: str,
        sighting_data: SightingReport | str | None = None,
    ) -> SightingReport:
        """Convert the sighting into a mystery visitor.

        Args:
            sighting_id: The sighting to convert.
            sighting_data: The ``SightingReport`` or its report token.

        Returns:
            The updated ``SightingReport``.

        Raises:
            TypeError: If ``sighting_data`` is not a SightingReport or token.
        """
        token: str | None
        if isinstance(sighting_data, SightingReport):
            token = sighting_data.token
        elif isinstance(sighting_data, str):
            token = sighting_data
        else:
            msg = "sighting_data should be a SightingReport or its token"
            raise TypeError(msg)
        variables = {
            "sightingConvertToMysteryVisitorInput": {
                "sightingId": sighting_id,
                "reportToken": token,
            }
        }
        data = await self._make_request(
            query=queries.birds.SIGHTING_CHOOSE_MYSTERY,
            variables=variables,
        )
        return SightingReport(data["sightingConvertToMysteryVisitor"])

    async def refresh_collections(self, of_type: str = "bird") -> dict[str, Collection]:
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
                LOGGER.warning("Setting Feeder options requires an owner account")
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
                LOGGER.warning("Frequency setting is available only to owner accounts")
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
        updated = {"powerProfile": result.get("feeder", {}).get("powerProfile", None)}

        if result["__typename"] == "FeederUpdatePowerProfileInProgressResult":
            # Refresh after a short delay
            # We could also poll `feederUpdatePowerProfileCheck`
            LOGGER.debug("PowerProfile update is in progress")
            await asyncio.sleep(0.25)
            await self.refresh()
            updated["powerProfile"] = self.feeders[feeder_id].power_profile.value
        else:
            self.feeders[feeder_id].update(updated)
        return updated

    async def update_firmware_start(self, feeder: Feeder | str) -> FeederUpdateStatus:
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
                LOGGER.warning("Firmware update is available only to owner accounts")
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

    async def update_firmware_check(self, feeder: Feeder | str) -> FeederUpdateStatus:
        """Check on a firmware update.

        Args:
            feeder: The Feeder or its id to check.

        Returns:
            The current firmware update status.
        """
        if isinstance(feeder, Feeder):
            if not feeder.is_owner:
                LOGGER.warning("Firmware update is available only to owner accounts")
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

    async def collection(self, collection_id: str) -> dict[str, Media]:
        """Return the media in the specified collection.

        Args:
            collection_id: The collection ``UUID``.

        Returns:
            A mapping of ``media_id`` to its ``Media``.
        """
        variables = {
            "collectionId": collection_id,
            # other inputs: first, orderBy, last, after, before
        }
        data = await self._make_request(
            query=queries.me.COLLECTIONS_MEDIA, variables=variables
        )
        # TODO: check [collection][media][pageInfo][hasNextPage]?
        return {
            (node := edge["node"]["media"])["id"]: Media(node)
            for edge in data["collection"]["media"]["edges"]
        }

    async def latest_collections(
        self,
    ) -> dict[str, Collection]:
        """Return the latest collections."""
        query = queries.me.LATEST_MEDIA  # type: ignore[attr-defined]
        return await self._make_request(query=query)

    @property
    def feeders(self) -> dict[str, Feeder]:
        """The Feeder devices associated with the account."""
        if self._needs_login():
            LOGGER.warning("BirdBuddy is not logged in. Call refresh() first")
            return {}
        return self._feeders
