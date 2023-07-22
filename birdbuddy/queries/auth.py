"""Authentication queries"""

SIGN_IN = """
mutation emailSignIn($emailSignInInput: EmailSignInInput!) {
  authEmailSignIn(emailSignInInput: $emailSignInInput) {
    ... on Auth {
      ...AuthInitFields
      __typename
    }
    ... on Problem {
      ...ProblemFields
      __typename
    }
    __typename
  }
}

fragment AuthInitFields on Auth {
  ...AuthFields
  me {
    ...MeInitFields
    __typename
  }
  __typename
}

fragment AuthFields on Auth {
  accessToken
  refreshToken
  __typename
}

fragment MeInitFields on Me {
  user {
    ...UserFields
    __typename
  }
  feeders {
    ... on FeederForMember {
      ...ListMemberFeederFields
      __typename
    }
    ... on FeederForOwner {
      ...MeFeederForOwnerFields
      __typename
    }
    ... on FeederForMemberPending {
      ...FeederForMemberPendingFields
      __typename
    }
    __typename
  }
  ...MeHaveCollectionsFields
  __typename
}

fragment UserFields on User {
  avatarUrl
  email
  id
  name
  signInType
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

fragment MeFeederForOwnerFields on FeederForOwner {
  ...ListOwnerFeederFields
  ...SingleOwnerFeederAdditionalFields
  __typename
}

fragment ListOwnerFeederFields on FeederForOwner {
  ...ListFeederFields
  availableFirmwareVersion
  firmwareVersion
  invitationsAvailable
  offGrid
  audioEnabled
  presenceUpdatedAt
  serialNumber
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

fragment SingleOwnerFeederAdditionalFields on FeederForOwner {
  frequency
  lowBatteryNotification
  lowFoodNotification
  invitations {
    ...FeederInvitationFields
    __typename
  }
  offGrid
  serialNumber
  temperature {
    value
    __typename
  }
  __typename
}

fragment FeederInvitationFields on FeederInvitation {
  id
  token
  __typename
}

fragment FeederForMemberPendingFields on FeederForMemberPending {
  id
  name
  __typename
}

fragment MeHaveCollectionsFields on Me {
  haveCollections
  __typename
}

fragment ProblemFields on Problem {
  items {
    field
    kind
    __typename
  }
  __typename
}
""".strip()

REFRESH_AUTH_TOKEN = """
mutation authRefreshToken($refreshTokenInput: RefreshTokenInput!) {
  authRefreshToken(refreshTokenInput: $refreshTokenInput) {
    ...AuthFields
    __typename
  }
}
fragment AuthFields on Auth {
  accessToken
  refreshToken
  __typename
}
""".strip()
