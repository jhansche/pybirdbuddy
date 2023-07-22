"""Queries related to the logged in user"""

ME = """
query me {
  me {
    user {
      ...UserFields
      __typename
    }
    settings {
      ...SettingsFields
      __typename
    }
    feeders {
      ... on FeederForMember {
        ...ListMemberFeederFields
        __typename
      }
      ... on FeederForOwner {
        ...ListOwnerFeederFields
        __typename
      }
      ... on FeederForMemberPending {
        ...FeederForMemberPendingFields
        __typename
      }
      __typename
    }
    __typename
  }
}
fragment UserFields on User {
  avatarUrl
  email
  id
  name
  signInType
  __typename
}
fragment SettingsFields on Settings {
  notificationDisabled
  __typename
}
fragment ListMemberFeederFields on FeederForMember {
  ...ListFeederFields
  locationCity
  locationCountry
  ownerName
  __typename
}
fragment ListFeederFields on FeederForPrivate {
  battery {
    charging
    percentage
    state
    __typename
  }
  food {
    state
    __typename
  }
  id
  name
  signal {
    state
    value
    __typename
  }
  state
  temperature {
    value
    __typename
  }
  __typename
}
fragment ListOwnerFeederFields on FeederForOwner {
  ...ListFeederFields
  availableFirmwareVersion
  firmwareVersion
  serialNumber
  invitationsAvailable
  offGrid
  audioEnabled
  presenceUpdatedAt
  members {
    ...FeederMemberFields
    __typename
  }
  location {
    city
    country
    __typename
  }
  __typename
}
fragment FeederMemberFields on FeederMember {
  accessDate
  accessLocation
  confirmed
  id
  memberName
  memberEmail
  __typename
}
fragment FeederForMemberPendingFields on FeederForMemberPending {
  id
  name
  __typename
}
""".strip()

FEED = """
query meFeed($first: Int, $last: Int, $after: String, $before: String) {
  me {
    feed(first: $first, last: $last, after: $after, before: $before) {
      ...FeedConnectionFields
      __typename
    }
    __typename
  }
}
fragment FeedConnectionFields on FeedConnection {
  edges {
    cursor
    node {
      ...AnyFeedItemFields
      __typename
    }
    __typename
  }
  pageInfo {
    hasNextPage
    endCursor
    __typename
  }
  __typename
}
fragment AnyFeedItemFields on AnyFeedItem {
  ... on FeedItemFeederInvitationConfirmed {
    ...FeederInvitationConfirmedFields
    __typename
  }
  ... on FeedItemFeederInvitationDeclined {
    ...FeederInvitationDeclinedFields
    __typename
  }
  ... on FeedItemFeederMemberDeleted {
    ...FeederMemberDeletedFields
    __typename
  }
  ... on FeedItemMediaLiked {
    ...MediaLikedFields
    __typename
  }
  ... on FeedItemSpeciesSighting {
    ...SpeciesSightingFields
    __typename
  }
  ... on FeedItemSpeciesUnlocked {
    ...SpeciesUnlockedFields
    __typename
  }
  ... on FeedItemMysteryVisitorNotRecognized {
    ...MysteryVisitorNotRecognizedFields
    __typename
  }
  ... on FeedItemMysteryVisitorResolved {
    ...MysteryVisitorResolvedFields
    __typename
  }
  ... on FeedItemNewPostcard {
    ...NewPostcardFields
    __typename
  }
  __typename
}
fragment FeederInvitationConfirmedFields on FeedItemFeederInvitationConfirmed {
  ...FeedItemFields
  approvedByUsername
  feeder {
    id
    name
    __typename
  }
  __typename
}
fragment FeedItemFields on FeedItem {
  id
  createdAt
  __typename
}
fragment FeederInvitationDeclinedFields on FeedItemFeederInvitationDeclined {
  ...FeedItemFields
  declinedByUsername
  feederName
  __typename
}
fragment FeederMemberDeletedFields on FeedItemFeederMemberDeleted {
  ...FeedItemFields
  removedByUsername
  feederName
  __typename
}
fragment MediaLikedFields on FeedItemMediaLiked {
  ...FeedItemFields
  numberOfLikes
  collection {
    ...AnyCollectionMainListFields
    __typename
  }
  media {
    ...MediaFullFields
    __typename
  }
  __typename
}
fragment AnyCollectionMainListFields on AnyCollection {
  ... on CollectionBird {
    ...CollectionMainListBirdFields
    __typename
  }
  ... on CollectionMysteryVisitor {
    ...CollectionMainListFields
    __typename
  }
  __typename
}
fragment CollectionMainListBirdFields on CollectionBird {
  ...CollectionMainListFields
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment CollectionMainListFields on Collection {
  id
  coverCollectionMedia {
    ...CollectionMediaFields
    __typename
  }
  markedAsNew
  visitsAllTime
  visitLastTime
  previewMedia {
    ...GalleryPreviewImagesFields
    __typename
  }
  __typename
}
fragment CollectionMediaFields on CollectionMedia {
  id
  feederName
  liked
  likes
  isShared
  locationCity
  locationCountry
  owning
  ownerName
  origin
  media {
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
fragment GalleryPreviewImagesFields on CollectionMedia {
  media {
    thumbnailUrl
    __typename
  }
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
fragment SpeciesSightingFields on FeedItemSpeciesSighting {
  ...FeedItemFields
  collection {
    ...AnyCollectionMainListFields
    __typename
  }
  media {
    ...MediaFullFields
    __typename
  }
  __typename
}
fragment SpeciesUnlockedFields on FeedItemSpeciesUnlocked {
  ...FeedItemFields
  collection {
    ...AnyCollectionMainListFields
    __typename
  }
  media {
    ...MediaFullFields
    __typename
  }
  __typename
}
fragment MysteryVisitorNotRecognizedFields on FeedItemMysteryVisitorNotRecognized {
  ...FeedItemFields
  media {
    ...MediaFullFields
    __typename
  }
  __typename
}
fragment MysteryVisitorResolvedFields on FeedItemMysteryVisitorResolved {
  ...FeedItemFields
  media {
    ...MediaFullFields
    __typename
  }
  __typename
}
fragment NewPostcardFields on FeedItemNewPostcard {
  ...FeedItemFields
  __typename
}
""".strip()

COLLECTIONS = """
query meCollections {
  me {
    collections {
      ...AnyCollectionMainListFields
      __typename
    }
    __typename
  }
}
fragment AnyCollectionMainListFields on AnyCollection {
  ... on CollectionBird {
    ...CollectionMainListBirdFields
    __typename
  }
  ... on CollectionMysteryVisitor {
    ...CollectionMainListFields
    __typename
  }
  __typename
}
fragment CollectionMainListBirdFields on CollectionBird {
  ...CollectionMainListFields
  species {
    ...SpeciesAnyListFields
    __typename
  }
  __typename
}
fragment CollectionMainListFields on Collection {
  id
  coverCollectionMedia {
    ...CollectionMediaFields
    __typename
  }
  markedAsNew
  visitsAllTime
  visitLastTime
  previewMedia {
    ...GalleryPreviewImagesFields
    __typename
  }
  __typename
}
fragment CollectionMediaFields on CollectionMedia {
  id
  feederName
  liked
  likes
  isShared
  locationCity
  locationCountry
  owning
  ownerName
  origin
  media {
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
fragment GalleryPreviewImagesFields on CollectionMedia {
  media {
    thumbnailUrl
    __typename
  }
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
""".strip()

COLLECTIONS_MEDIA = """
query meCollectionsMedia($collectionId: ID!, $first: Int, $orderBy: MediaOrderByInput, $last: Int, $after: String, $before: String) {
  collection(collectionId: $collectionId) {
    ... on CollectionBird {
      id
      media(
        first: $first
        orderBy: $orderBy
        last: $last
        after: $after
        before: $before
      ) {
        ...CollectionMediaConnectionFields
      }
    }
    ... on CollectionMysteryVisitor {
      id
      media(
        first: $first
        orderBy: $orderBy
        last: $last
        after: $after
        before: $before
      ) {
        ...CollectionMediaConnectionFields
      }
    }
  }
}
fragment CollectionMediaConnectionFields on CollectionMediaConnection {
  edges {
    node {
      ...CollectionMediaFields
    }
  }
  pageInfo {
    hasNextPage
    endCursor
  }
}
fragment CollectionMediaFields on CollectionMedia {
  id
  feederName
  liked
  likes
  isShared
  locationCity
  locationCountry
  owning
  ownerName
  origin
  media {
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
""".strip()
