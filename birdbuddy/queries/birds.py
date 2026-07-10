"""Queries related to birds and sightings."""

POSTCARD_REANALYZE = """
mutation ReanalyzePostcard($feedItemId: ID!) {
  inferenceExternalPostcardReanalyze(feedItemId: $feedItemId) {
    updatedFeedItem {
      __typename
      ... on FeedItemNewPostcard {
        id
        createdAt
        inferenceConfidenceLevel
        inferenceExecutionMode
        inferenceType
        reanalyzeAvailability
        feeder {
          __typename
          ... on Feeder {
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
        sightingReportPreview {
          sightings {
            __typename
            ... on SightingRecognizedBird {
              species {
                __typename
                ... on Species {
                  id
                  name
                }
              }
            }
            ... on SightingRecognizedBirdUnlocked {
              species {
                __typename
                ... on Species {
                  id
                  name
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

SHARE_MEDIAS = """
mutation mediaShareToggle($mediaShareToggleInput: MediaShareToggleInput!) {
  mediaShareToggle(mediaShareToggleInput: $mediaShareToggleInput) {
    success
  }
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
