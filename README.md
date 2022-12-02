# pybirdbuddy

```python
import pprint

from birdbuddy.client import BirdBuddy

bb = BirdBuddy("user@email.com", "Pa$$w0rd")

# BirdBuddy.feeders will initiate login if not already, but will not automatically refresh
pprint.pprint(bb.feeders)
# refresh() will update feeder data, including login if needed and/or refreshing access token if needed.
bb.refresh()
```

Note: only password login is supported currently. Google and other SSOs are not supported. If
you've already set up your Bird Buddy with SSO, one option could be to register a new account with
a password, and then redeem an invite code to your Bird Buddy under the new account. Some fields
will be missing (such as firmware versions and off-grid status).

The `feeders` property will be an array of feeders with the following fields:

```graphql
fragment ListFeederFields on FeederForPrivate {
  battery {
    charging    # Boolean
    percentage  # Int (93)
    state       # String (enum: "HIGH")
  }
  food {
    state       # String (enum: "LOW")
  }
  id            # String (UUID)
  name          # String
  signal {
    state       # String (enum: "HIGH")
    value       # Int (rssi: -41)
  }
  state         # String (enum: "READY_TO_STREAM")
  temperature {
    value       # Int
  }
}
```
