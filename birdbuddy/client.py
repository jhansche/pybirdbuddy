"""Bird Buddy client module"""

from __future__ import annotations

import asyncio
from datetime import datetime

import langcodes
from python_graphql_client import GraphqlClient

from . import LOGGER, VERBOSE, queries
from .const import BB_URL
from .exceptions import (
    AuthenticationFailedError,
    AuthTokenExpiredError,
    NoResponseError,
    GraphqlError,
    UnexpectedResponseError,
)
from .feed import Feed, FeedNode, FeedNodeType
from .feeder import Feeder, FeederUpdateStatus, MetricState
from .media import Collection, Media
from .sightings import (
    PostcardSighting,
    Sighting,
    SightingFinishMod,
    SightingFinishStrategy,
    SightingReport,
)
from .user import BirdBuddyUser

_NO_VALUE = object()
"""Sentinel value to allow None to override a default value."""


def _redact(data, redacted: bool = True):
    """Returns a redacted string if necessary."""
    return "**REDACTED**" if redacted else data


class BirdBuddy:
    """Bird Buddy api client"""

    graphql: GraphqlClient
    _email: str | None
    _password: str | None
    _access_token: str | None
    _refresh_token: str | None
    _language_code: str
    _me: BirdBuddyUser | None
    _feeders: dict[str, Feeder]
    _collections: dict[str, Collection]
    _last_feed_date: datetime

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        /,
        refresh_token: str | None = None,
        access_token: str | None = None,
    ) -> None:
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

    def _save_me(self, me_data: dict):
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

        should_redact = query in [queries.auth.REFRESH_AUTH_TOKEN, queries.auth.SIGN_IN]
        LOGGER.debug(
            "> GraphQL %s, vars=%s",
            query.partition("\n")[0],  # First line of query
            _redact(variables, should_redact),
        )
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

        LOGGER.log(VERBOSE, "< response: %s", _redact(result, should_redact))

        return result

    @property
    def user(self) -> None | BirdBuddyUser:
        """The logged in user data"""
        return self._me

    @property
    def language_code(self) -> str:
        """The current language code"""
        return self._language_code

    @language_code.setter
    def language_code(self, language_code: str):
        """Override the language used in API requests.

        This is useful to get localized responses, including translated
        bird species names.
        """
        self._language_code = langcodes.standardize_tag(language_code)

    async def refresh(self) -> bool:
        """Refreshes the Bird Buddy feeder data"""
        data = await self._make_request(query=queries.me.ME)
        LOGGER.debug("Feeder data refreshed successfully: %s", data)
        return self._save_me(data["me"])

    async def toggle_off_grid(
        self,
        feeder: Feeder | str,
        is_off_grid: bool,
    ) -> Feeder:
        """Toggle the feeder's off-grid status.

        Available to Owner account only."""
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
            assert await self.refresh()
            new_off_grid = self.feeders[feeder_id].is_off_grid
        return self.feeders[feeder_id]


    async def toggle_audio_enabled(
        self,
        feeder: Feeder | str,
        is_audio_enabled: bool,
    ) -> Feeder:
        """Toggle the feeder's audio-enabled setting.

        Available to Owner account only."""
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
            assert await self.refresh()
            new_setting = self.feeders[feeder_id].is_audio_enabled
        return self.feeders[feeder_id]

    async def feed(
        self,
        first: int = 20,
        after: str = None,
        last: int = None,
        before: str = None,
    ) -> Feed:
        """Returns the Bird Buddy Feed.

        The returned dictionary contains a `"pageInfo"` key for pagination/cursor data; and an
        `"edges"` key containing a list of FeedEdge nodes, most recent items listed first.

        :param first: Return the first N items older than `after`
        :param after: The cursor of the oldest item previously seen, to allow pagination of very long feeds
        :param last: Return the last N items newer than `before`
        :param before: The cursor of the newest item previously seen, to allow pagination of very long feeds
        :param newer_than: `datetime` or `str` of the most recent feed item previously seen
        """
        variables = {
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
            # Not implemented: birdbuddy.exceptions.GraphqlError: 501: 'Not Implemented'
            #  variables["before"] = before
            #  variables["last"] = last if last else 20
            pass

        data = await self._make_request(query=queries.me.FEED, variables=variables)
        return Feed(data["me"]["feed"])

    async def refresh_feed(self, since: datetime | str = _NO_VALUE) -> list[FeedNode]:
        """Get only fresh feed items, new since the last Feed refresh.

        The most recent edge node timestamp will be saved as the last seen feed item,
        which will become the new default value for `since`. This can be useful to,
        for example, restore a last-seen timestamp in a new instance.

        :param since: The `datetime` after which to restrict new feed items."""
        if since == _NO_VALUE:
            since = self._last_feed_date
        if isinstance(since, str):
            since = FeedNode.parse_datetime(since)
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
        return feed.filter(newer_than=since)

    async def feed_nodes(self, node_type: str) -> list[FeedNode]:
        """Returns all feed items of type ``node_type``"""
        feed = await self.feed()
        return feed.filter(of_type=node_type)

    async def new_postcards(self) -> list[FeedNode]:
        """Returns all new 'Postcard' feed items.

        These Postcard node types will be converted into sightings using ``sighting_from_postcard``.
        """
        return await self.feed_nodes(FeedNodeType.NewPostcard)

    async def sighting_from_postcard(
        self,
        postcard: str | FeedNode,
    ) -> PostcardSighting:
        """Convert a 'postcard' into a 'sighting report'.

        Next step is to choose or confirm species and then finish the sighting.
        If the sighting type is ``SightingRecognized``, we can collect the sighting with
        ``finish_postcard``.
        """
        postcard_id: str
        if isinstance(postcard, str):
            postcard_id = postcard
        elif isinstance(postcard, FeedNode):
            assert postcard.node_type == FeedNodeType.NewPostcard
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
        return PostcardSighting(data).with_postcard(postcard)

    async def finish_postcard(
        self,
        feed_item_id: str,
        sighting_result: PostcardSighting,
        strategy: SightingFinishStrategy = SightingFinishStrategy.RECOGNIZED,
        confidence_threshold: int = None,
        share_media: bool = False,
    ) -> bool:
        """Finish collecting the postcard in your collections.

        :param feed_item_id the id from ``new_postcards``
        :param sighting_result from ``sighting_from_postcard``, should contain sightings of type
        ``SightingRecognizedBird`` or `SightingRecognizedBirdUnlocked``.
        :param strategy Finishing strategy, one of `RECOGNIZED`, `BEST_GUESS`, or `MYSTERY`
        :param confidence_threshold Threshold for `BEST_GUESS` strategy to accept the highest
        confidence suggestion above this threshold. Defaults to 10 (%).
        :param share_media ``True`` to automatically share finished media to the community.
        Defaults to ``False``.
        """
        if not isinstance(sighting_result, PostcardSighting):
            # See sighting_from_postcard()["sightingCreateFromPostcard"]
            LOGGER.warning("Unexpected sighting result: %s", sighting_result)
            return False

        report = sighting_result.report

        sighting: Sighting = None
        mod: SightingFinishMod = None
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
                LOGGER.debug(
                    "selecting highest confidence: %s%% for species %s",
                    mod.data["confidence"],
                    mod.data["speciesCode"],
                )
                new_report = await self.sighting_choose_species(
                    sighting.id,
                    mod.data["speciesCode"],
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
                    "replacing report after converting to mystery:\nold=%s\nnew=%s",
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
            except Exception as err:  # pylint: disable=broad-except
                LOGGER.error(
                    "Error sharing %d medias: %s",
                    len(media_ids),
                    err,
                    exc_info=err,
                )
                share_result = False
        return result

    async def share_medias(self, media_ids: list[str], share: bool = True) -> bool:
        """Toggle media sharing"""
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

    async def sighting_choose_species(
        self,
        sighting_id: str,
        species_id: str,
        sighting_data: SightingReport | str = None,
    ) -> SightingReport:
        """Manually assign a species to a sighting."""
        token: str
        if isinstance(sighting_data, SightingReport):
            token = sighting_data.token
        elif isinstance(sighting_data, str):
            token = sighting_data
        else:
            raise ValueError(
                "sighting_data should be the `SightingReport` or `SightingReport.token`"
            )
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
        sighting_data: SightingReport | str = None,
    ) -> SightingReport:
        """Convert the sighting into a mystery visitor."""
        token: str
        if isinstance(sighting_data, SightingReport):
            token = sighting_data.token
        elif isinstance(sighting_data, str):
            token = sighting_data
        else:
            raise ValueError(
                "sighting_data should be the `SightingReport` or `SightingReport.token`"
            )
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

    async def set_frequency(self, feeder: Feeder | str, frequency: MetricState) -> dict:
        """Update Feeder frequency state"""
        if isinstance(feeder, Feeder):
            feeder_id = feeder.id
            if not feeder.is_owner:
                LOGGER.warning("Frequency setting is available only to owner accounts")
        else:
            feeder_id = feeder
        variables = {
            "feederId": feeder_id,
            "feederUpdateInput": {
                "frequency": frequency.value,
                # "lowBatteryNotification"
                # "lowFoodNotification"
                # "name"
                # "offGrid"
                # "offlineMode"
            },
        }
        result = await self._make_request(
            query=queries.feeder.SET_OPTIONS,
            variables=variables,
        )
        updated = {"frequency": result["feederUpdate"].get("frequency", None)}
        self.feeders[feeder_id].update(updated)
        return updated

    async def update_firmware_start(self, feeder: Feeder | str) -> FeederUpdateStatus:
        """Start a firmware update."""
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

    async def update_firmware_check(self, feeder: Feeder | str):
        """Check on a firmware update."""
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
        """Returns the last seen cached Collections.

        Note that this may be outdated.

        See also :func:`BirdBuddy.refresh_collections()`"""
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
        """Returns the media in the specified collection.

        The keys will be the ``media_id``, and values
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

    @property
    def feeders(self) -> dict[str, Feeder]:
        """The Feeder devices associated with the account."""
        if self._needs_login():
            LOGGER.warning("BirdBuddy is not logged in. Call refresh() first")
            return {}
        return self._feeders
