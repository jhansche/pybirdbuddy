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
