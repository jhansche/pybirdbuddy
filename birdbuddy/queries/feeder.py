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
""".strip()

TOGGLE_AUDIO_ENABLED = """
mutation feederToggleAudio($feederId: ID!, $feederToggleAudioInput: FeederToggleAudioInput!) {
  feederToggleAudio(
    feederId: $feederId
    feederToggleAudioInput: $feederToggleAudioInput
  ) {
    ... on FeederToggleAudioFinishedResult {
      __typename
      feeder {
        audioEnabled
      }
    }
    ... on FeederToggleAudioInProgressResult {
      __typename
      feeder {
        audioEnabled
      }
    }
  }
}
""".strip()

UPDATE_POWER_PROFILE = """
mutation feederUpdatePowerProfile($feederId: ID!, $feederUpdatePowerProfileInput: FeederUpdatePowerProfileInput!) {
  feederUpdatePowerProfile(feederId: $feederId, feederUpdatePowerProfileInput: $feederUpdatePowerProfileInput) {
    ... on FeederUpdatePowerProfileFinishedResult {
      __typename
      feeder {
        powerProfile
      }
    }
    ... on FeederUpdatePowerProfileInProgressResult {
      __typename
      feeder {
        powerProfile
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
  audioEnabled
  availableFirmwareVersion
  firmwareVersion
  offGrid
  powerProfile
  presenceUpdatedAt
  serialNumber
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
  powerProfile
  serialNumber
  temperature {
    value
    __typename
  }
  __typename
}
""".strip()

UPDATE_FIRMWARE = """
mutation feederFirmwareUpdateStart($feederId: ID!) {
  feederFirmwareUpdateStart(feederId: $feederId) {
    ... on FeederFirmwareUpdateFailedResult {
      failedReason
      __typename
    }
    ... on FeederFirmwareUpdateProgressResult {
      progress
      __typename
    }
    ... on FeederFirmwareUpdateSucceededResult {
      __typename
      feeder {
        availableFirmwareVersion
        firmwareVersion
      }
    }
  }
}
""".strip()

UPDATE_FIRMWARE_PROGRESS = """
mutation feederFirmwareUpdateCheckProgress($feederId: ID!) {
  feederFirmwareUpdateCheckProgress(feederId: $feederId) {
    ... on FeederFirmwareUpdateFailedResult {
      failedReason
      __typename
    }
    ... on FeederFirmwareUpdateProgressResult {
      feeder {
        state
      }
      progress
      __typename
    }
    ... on FeederFirmwareUpdateSucceededResult {
      __typename
      feeder {
        availableFirmwareVersion
        firmwareVersion
      }
    }
  }
}
""".strip()
