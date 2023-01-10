"""Feeder queries"""

TOGGLE_OFF_GRID = """
mutation feederToggleOffGrid($feederId: ID!, $feederToggleOffGridInput: FeederToggleOffGridInput!) {
  feederToggleOffGrid(
    feederId: $feederId
    feederToggleOffGridInput: $feederToggleOffGridInput
  ) {
    ... on FeederToggleOffGridFinishedResult {
      feeder {
        offGrid
      }
    }
    ... on FeederToggleOffGridInProgressResult {
      feeder {
        offGrid
      }
    }
  }
}
"""

SET_OPTIONS = """
mutation feederUpdate($feederId: ID!, $feederUpdateInput: FeederUpdateInput!) {
  feederUpdate(feederId: $feederId, feederUpdateInput: $feederUpdateInput) {
    ... on FeederForOwner {
      ...ListOwnerFeederFields
      ...SingleOwnerFeederAdditionalFields
    }
  }
}
fragment ListOwnerFeederFields on FeederForOwner {
  ...ListFeederFields
  availableFirmwareVersion
  firmwareVersion
  offGrid
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
fragment SingleOwnerFeederAdditionalFields on FeederForOwner {
  frequency
  lowBatteryNotification
  lowFoodNotification
  offGrid
  serialNumber
  temperature {
    value
    __typename
  }
  __typename
}
"""

UPDATE_FIRMWARE = """
mutation feederFirmwareUpdateStart($feederId: ID!) {
  feederFirmwareUpdateStart(feederId: $feederId) {
    ... on FeederFirmwareUpdateFailedResult {
      failedReason
    }
    ... on FeederFirmwareUpdateProgressResult {
      progress
    }
    ... on FeederFirmwareUpdateSucceededResult {
      feeder {
        availableFirmwareVersion
        firmwareVersion
      }
    }
  }
}
"""

UPDATE_FIRMWARE_PROGRESS = """
mutation feederFirmwareUpdateCheckProgress($feederId: ID!) {
  feederFirmwareUpdateCheckProgress(feederId: $feederId) {
    ... on FeederFirmwareUpdateFailedResult {
      failedReason
    }
    ... on FeederFirmwareUpdateProgressResult {
      feeder {
        state
      }
      progress
    }
    ... on FeederFirmwareUpdateSucceededResult {
      feeder {
        availableFirmwareVersion
        firmwareVersion
      }
    }
  }
}
"""
