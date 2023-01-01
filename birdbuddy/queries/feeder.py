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
