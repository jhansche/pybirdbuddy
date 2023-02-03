"""Queries related to birds and sightings"""

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
    ...FeederFields
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
fragment FeederFields on Feeder {
  id
  name
  state
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
