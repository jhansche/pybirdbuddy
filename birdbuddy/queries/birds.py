"""Queries related to birds and sightings."""

POSTCARD_REANALYZE = """
mutation ReanalyzePostcard($feedItemId: ID!) {
  inferenceExternalPostcardReanalyze(feedItemId: $feedItemId) {
    updatedFeedItem {
      __typename
      ... on FeedItemNewPostcard {
        id
        inferenceConfidenceLevel
        inferenceExecutionMode
        inferenceType
        reanalyzeAvailability
      }
    }
  }
}
"""

POSTCARD_TO_SIGHTING = """
mutation sightingCreateFromPostcard($sightingCreateFromPostcardInput: SightingCreateFromPostcardInput!) {
  sightingCreateFromPostcard(
    sightingCreateFromPostcardInput: $sightingCreateFromPostcardInput
  ) {
    ...SightingCreateFromPostcardFields
    __typename
  }
}
fragment SightingCreateFromPostcardFields on SightingCreateFromPostcardResult {
  feeder {
    ... on FeederForMember {
      id
      name
      state
      __typename
    }
    ... on FeederForOwner {
      id
      name
      state
      __typename
    }
    ... on FeederForPublic {
      id
      name
      __typename
    }
    ... on FeederForRemoteGuest {
      id
      name
      __typename
    }
    __typename
  }
  medias {
    ...MediaFullFields
    __typename
  }
  sightingReport {
    ...SightingsReportFields
    __typename
  }
  videoMedia {
    ...MediaFullFields
    __typename
  }
  __typename
}
fragment MediaFullFields on Media {
  id
  createdAt
  thumbnailUrl
  ... on MediaImage {
    contentUrl(size: ORIGINAL)
    __typename
  }
  ... on MediaVideo {
    contentUrl(size: ORIGINAL)
    __typename
  }
  __typename
}
fragment SightingsReportFields on SightingReport {
  reportToken
  sightings {
    ... on SightingCantDecideWhichBird {
      ...SightingCantDecideWhichBirdFields
      __typename
    }
    ... on SightingNoBird {
      ...SightingFields
      __typename
    }
    ... on SightingNoBirdRecognized {
      ...SightingFields
      __typename
    }
    ... on SightingRecognizedBird {
      ...SightingRecognizedBirdFields
      __typename
    }
    ... on SightingRecognizedBirdUnlocked {
      ...SightingRecognizedBirdUnlockedFields
      __typename
    }
    ... on SightingRecognizedMysteryVisitor {
      ...SightingRecognizedMysteryVisitorFields
      __typename
    }
    __typename
  }
  __typename
}
fragment SightingCantDecideWhichBirdFields on SightingCantDecideWhichBird {
  ...SightingFields
  suggestions {
    ...CollectionSpeciesFields
    __typename
  }
  __typename
}
fragment SightingFields on Sighting {
  id
  matchTokens
  __typename
}
fragment CollectionSpeciesFields on CollectionSpecies {
  isCollected
  media {
    ...MediaThumbnailFields
    __typename
  }
  species {
    ...SpeciesSingleFields
    __typename
  }
  __typename
}
fragment MediaThumbnailFields on Media {
  id
  createdAt
  thumbnailUrl
  __typename
}
fragment SpeciesSingleFields on Species {
  id
  description
  name
  iconUrl
  __typename
}
fragment SightingRecognizedBirdFields on SightingRecognizedBird {
  ...SightingRecognizedFields
  count
  icon
  shareableMatchTokens
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment SightingRecognizedFields on SightingRecognized {
  ...SightingFields
  color
  text
  __typename
}
fragment SpeciesAnyListFields on AnySpecies {
  ... on SpeciesBird {
    ...SpeciesListFields
    isUnofficialName
    mapUrl
    __typename
  }
  ... on SpeciesBirdFamily {
    ...SpeciesListFields
    __typename
  }
  ... on SpeciesBirdGenus {
    ...SpeciesListFields
    __typename
  }
  ... on SpeciesBirdOrder {
    ...SpeciesListFields
    __typename
  }
  __typename
}
fragment SpeciesListFields on Species {
  id
  iconUrl
  name
  __typename
}
fragment SightingRecognizedBirdUnlockedFields on SightingRecognizedBirdUnlocked {
  ...SightingFields
  ...SightingRecognizedFields
  shareableMatchTokens
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment SightingRecognizedMysteryVisitorFields on SightingRecognizedMysteryVisitor {
  ...SightingFields
  color
  count
  text
  __typename
}
""".strip()
"""This might return error code ``SIGHTING_POSTCARD_ALREADY_CLAIMED``"""

FINISH_SIGHTING = """
mutation sightingReportPostcardFinish($sightingReportPostcardFinishInput: SightingReportPostcardFinishInput!) {
  sightingReportPostcardFinish(
    sightingReportPostcardFinishInput: $sightingReportPostcardFinishInput
  ) {
    success
    __typename
  }
}
""".strip()

SIGHTING_CHOOSE_SPECIES = """
mutation sightingChooseSpecies($sightingChooseSpeciesInput: SightingChooseSpeciesInput!) {
  sightingChooseSpecies(sightingChooseSpeciesInput: $sightingChooseSpeciesInput) {
    ...SightingsReportFields
    __typename
  }
}
fragment SightingsReportFields on SightingReport {
  reportToken
  sightings {
    ... on SightingCantDecideWhichBird {
      ...SightingCantDecideWhichBirdFields
      __typename
    }
    ... on SightingNoBird {
      ...SightingFields
      __typename
    }
    ... on SightingNoBirdRecognized {
      ...SightingFields
      __typename
    }
    ... on SightingRecognizedBird {
      ...SightingRecognizedBirdFields
      __typename
    }
    ... on SightingRecognizedBirdUnlocked {
      ...SightingRecognizedBirdUnlockedFields
      __typename
    }
    ... on SightingRecognizedMysteryVisitor {
      ...SightingRecognizedMysteryVisitorFields
      __typename
    }
    __typename
  }
  __typename
}
fragment SightingCantDecideWhichBirdFields on SightingCantDecideWhichBird {
  ...SightingFields
  suggestions {
    ...CollectionSpeciesFields
    __typename
  }
  __typename
}
fragment SightingFields on Sighting {
  id
  matchTokens
  __typename
}
fragment CollectionSpeciesFields on CollectionSpecies {
  isCollected
  media {
    ...MediaThumbnailFields
    __typename
  }
  species {
    ...SpeciesSingleFields
    __typename
  }
  __typename
}
fragment MediaThumbnailFields on Media {
  id
  createdAt
  thumbnailUrl
  __typename
}
fragment SpeciesSingleFields on Species {
  id
  description
  name
  iconUrl
  __typename
}
fragment SightingRecognizedBirdFields on SightingRecognizedBird {
  ...SightingRecognizedFields
  count
  icon
  shareableMatchTokens
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment SightingRecognizedFields on SightingRecognized {
  ...SightingFields
  color
  text
  __typename
}
fragment SpeciesAnyListFields on AnySpecies {
  ... on SpeciesBird {
    ...SpeciesListFields
    isUnofficialName
    mapUrl
    __typename
  }
  ... on SpeciesBirdFamily {
    ...SpeciesListFields
    __typename
  }
  ... on SpeciesBirdGenus {
    ...SpeciesListFields
    __typename
  }
  ... on SpeciesBirdOrder {
    ...SpeciesListFields
    __typename
  }
  __typename
}
fragment SpeciesListFields on Species {
  id
  iconUrl
  name
  __typename
}
fragment SightingRecognizedBirdUnlockedFields on SightingRecognizedBirdUnlocked {
  ...SightingFields
  ...SightingRecognizedFields
  shareableMatchTokens
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment SightingRecognizedMysteryVisitorFields on SightingRecognizedMysteryVisitor {
  ...SightingFields
  color
  count
  text
  __typename
}
""".strip()

SIGHTING_CHOOSE_MYSTERY = """
mutation sightingConvertToMysteryVisitor($sightingConvertToMysteryVisitorInput: SightingConvertToMysteryVisitorInput!) {
  sightingConvertToMysteryVisitor(
    sightingConvertToMysteryVisitorInput: $sightingConvertToMysteryVisitorInput
  ) {
    ...SightingsReportFields
    __typename
  }
}
fragment SightingsReportFields on SightingReport {
  reportToken
  sightings {
    ... on SightingCantDecideWhichBird {
      ...SightingCantDecideWhichBirdFields
      __typename
    }
    ... on SightingNoBird {
      ...SightingFields
      __typename
    }
    ... on SightingNoBirdRecognized {
      ...SightingFields
      __typename
    }
    ... on SightingRecognizedBird {
      ...SightingRecognizedBirdFields
      __typename
    }
    ... on SightingRecognizedBirdUnlocked {
      ...SightingRecognizedBirdUnlockedFields
      __typename
    }
    ... on SightingRecognizedMysteryVisitor {
      ...SightingRecognizedMysteryVisitorFields
      __typename
    }
    __typename
  }
  __typename
}
fragment SightingCantDecideWhichBirdFields on SightingCantDecideWhichBird {
  ...SightingFields
  suggestions {
    ...CollectionSpeciesFields
    __typename
  }
  __typename
}
fragment SightingFields on Sighting {
  id
  matchTokens
  __typename
}
fragment CollectionSpeciesFields on CollectionSpecies {
  isCollected
  media {
    ...MediaThumbnailFields
    __typename
  }
  species {
    ...SpeciesSingleFields
    __typename
  }
  __typename
}
fragment MediaThumbnailFields on Media {
  id
  createdAt
  thumbnailUrl
  __typename
}
fragment SpeciesSingleFields on Species {
  id
  description
  name
  iconUrl
  __typename
}
fragment SightingRecognizedBirdFields on SightingRecognizedBird {
  ...SightingRecognizedFields
  count
  icon
  shareableMatchTokens
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment SightingRecognizedFields on SightingRecognized {
  ...SightingFields
  color
  text
  __typename
}
fragment SpeciesAnyListFields on AnySpecies {
  ... on SpeciesBird {
    ...SpeciesListFields
    isUnofficialName
    mapUrl
    __typename
  }
  ... on SpeciesBirdFamily {
    ...SpeciesListFields
    __typename
  }
  ... on SpeciesBirdGenus {
    ...SpeciesListFields
    __typename
  }
  ... on SpeciesBirdOrder {
    ...SpeciesListFields
    __typename
  }
  __typename
}
fragment SpeciesListFields on Species {
  id
  iconUrl
  name
  __typename
}
fragment SightingRecognizedBirdUnlockedFields on SightingRecognizedBirdUnlocked {
  ...SightingFields
  ...SightingRecognizedFields
  shareableMatchTokens
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment SightingRecognizedMysteryVisitorFields on SightingRecognizedMysteryVisitor {
  ...SightingFields
  color
  count
  text
  __typename
}
""".strip()

SHARE_MEDIAS = """
mutation mediaShareToggle($mediaShareToggleInput: MediaShareToggleInput!) {
  mediaShareToggle(mediaShareToggleInput: $mediaShareToggleInput) {
    success
  }
}
""".strip()


SIGHTING_CREATE = """
mutation sightingCreate($sightingCreateInput: SightingCreateInput!) {
  sightingCreate(sightingCreateInput: $sightingCreateInput) {
    sightingCreateProgress {
      id
      progress
    }
  }
}
""".strip()


SIGHTING_CREATE_PROGRESS = """
query sightingCreateCheckProgress($sightingCreateCheckProgressInput: SightingCreateCheckProgressInput!) {
  sightingCreateCheckProgress(
    sightingCreateCheckProgressInput: $sightingCreateCheckProgressInput
  ) {
    ... on SightingCreateProgress {
      id
      progress
      __typename
    }
    ... on SightingReport {
      ...SightingsReportFields
      __typename
    }
    __typename
  }
}
fragment SightingsReportFields on SightingReport {
  reportToken
  sightings {
    ... on SightingCantDecideWhichBird {
      ...SightingCantDecideWhichBirdFields
      __typename
    }
    ... on SightingNoBird {
      ...SightingFields
      __typename
    }
    ... on SightingNoBirdRecognized {
      ...SightingFields
      __typename
    }
    ... on SightingRecognizedBird {
      ...SightingRecognizedBirdFields
      __typename
    }
    ... on SightingRecognizedBirdUnlocked {
      ...SightingRecognizedBirdUnlockedFields
      __typename
    }
    ... on SightingRecognizedMysteryVisitor {
      ...SightingRecognizedMysteryVisitorFields
      __typename
    }
    __typename
  }
  __typename
}
fragment SightingCantDecideWhichBirdFields on SightingCantDecideWhichBird {
  ...SightingFields
  suggestions {
    ...CollectionSpeciesFields
    __typename
  }
  __typename
}
fragment SightingFields on Sighting {
  id
  matchTokens
  __typename
}
fragment CollectionSpeciesFields on CollectionSpecies {
  isCollected
  media {
    ...MediaThumbnailFields
    __typename
  }
  species {
    ...SpeciesSingleFields
    __typename
  }
  __typename
}
fragment MediaThumbnailFields on Media {
  id
  createdAt
  thumbnailUrl
  __typename
}
fragment SpeciesSingleFields on Species {
  id
  description
  name
  iconUrl
  __typename
}
fragment SightingRecognizedBirdFields on SightingRecognizedBird {
  ...SightingRecognizedFields
  count
  icon
  shareableMatchTokens
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment SightingRecognizedFields on SightingRecognized {
  ...SightingFields
  color
  text
  __typename
}
fragment SpeciesAnyListFields on AnySpecies {
  ... on SpeciesBird {
    ...SpeciesListFields
    isUnofficialName
    mapUrl
    __typename
  }
  ... on SpeciesBirdFamily {
    ...SpeciesListFields
    __typename
  }
  ... on SpeciesBirdGenus {
    ...SpeciesListFields
    __typename
  }
  ... on SpeciesBirdOrder {
    ...SpeciesListFields
    __typename
  }
  __typename
}
fragment SpeciesListFields on Species {
  id
  iconUrl
  name
  __typename
}
fragment SightingRecognizedBirdUnlockedFields on SightingRecognizedBirdUnlocked {
  ...SightingFields
  ...SightingRecognizedFields
  shareableMatchTokens
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment SightingRecognizedMysteryVisitorFields on SightingRecognizedMysteryVisitor {
  ...SightingFields
  color
  count
  text
  __typename
}
""".strip()


_COLLECTED_POSTCARD_FIELDS = """
fragment CollectedPostcardFields on FeedItemCollectedPostcard {
  __typename
  id
  createdAt
  hasMysteryVisitor
  hasNewSpecies
  inferenceExecutionMode
  inferenceType
  mediaSpeciesNameIdentificationConfidenceLevel
  species {
    id
    name
  }
  mediaSpeciesAssignedName {
    id
    name
    markedAsNew
    species {
      id
      name
    }
  }
  medias {
    __typename
    id
    createdAt
    thumbnailUrl
    ... on MediaImage {
      contentUrl(size: ORIGINAL)
      __typename
    }
    ... on MediaVideo {
      contentUrl(size: ORIGINAL)
      __typename
    }
  }
}
"""


POSTCARD_COLLECT = (
    """
mutation postcardCollect(
  $feedItemId: ID!, $postcardCollectInput: PostcardCollectInput
) {
  postcardCollect(feedItemId: $feedItemId, input: $postcardCollectInput) {
    postcardCollectedDetails {
      isFirstCollectedPostcard
    }
    collectedPostcard {
      ...CollectedPostcardFields
    }
  }
}
"""
    + _COLLECTED_POSTCARD_FIELDS
).strip()
