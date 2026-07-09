# pybirdbuddy

[![Build Status][build-status-shield]][build-status]
![Maintenance][maintenance-shield]
[![GitHub Release][releases-shield]][releases]
[![PyPI Version][pypi-shield]][pypi]
[![License][license-shield]](LICENSE)

`pybirdbuddy` is an asynchronous Python client for the undocumented GraphQL
API behind the Bird Buddy smart bird feeder. Sign in with a Bird Buddy account
to read your feeders and their state, browse your collections and media, and
collect the "postcards" the feeder captures.

It is an unofficial client for an undocumented API that can change without
notice, and is not affiliated with or endorsed by Bird Buddy.

## Installation

```bash
pip install pybirdbuddy
```

Python 3.10–3.14 is supported.

## Usage

```python
import asyncio
import pprint

from birdbuddy.client import BirdBuddy

bb = BirdBuddy("user@email.com", "Pa$$w0rd")

# Using coroutines with async/await:
async def async_test():
    await bb.refresh()
    pprint.pprint(bb.feeders)

# Without async/await, including from a top-level module:
result = asyncio.run(bb.refresh())
pprint.pprint(result)
pprint.pprint(bb.feeders)
```

Note: only password login is supported currently. Google and other SSOs are
not supported. If you've already set up your Bird Buddy with SSO, one option
could be to register a new account with a password, and then redeem an invite
code to your Bird Buddy under the new account. Some fields will be missing
(such as firmware versions and off-grid status).

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

## Translations

API responses can return translated strings by setting the client's
`language_code` property. Language codes are parsed using
[`langcodes`](https://pypi.org/project/langcodes/)

```python
from birdbuddy.client import BirdBuddy

async def main():
    bb = BirdBuddy("user@email.com", "Pa$$w0rd")
    bb.language_code = "de"

    collections = await bb.refresh_collections()
    birds = [c.species.name for c in collections.values()]
    print(birds)
```

## Breaking changes (v0.0.x → v0.1.0)

The Bird Buddy app moved entirely to the `postcardCollect` flow, and the old
sighting-report input types were dropped from the API. v0.1.0 follows suit:

- **Postcard flow replaced.** `sighting_from_postcard`, `finish_postcard`,
  `sighting_choose_species`, and `sighting_choose_mystery` are gone. Collect a
  postcard with `collect_postcard(postcard, share=False)`, which reanalyzes it
  (running inference if needed) and returns a `CollectedPostcard`. The
  `birdbuddy.sightings` module and its models (`PostcardSighting`,
  `SightingReport`, `Sighting`, and the best-guess/anomaly helpers) were
  removed; the backend now reports species and confidence directly.
- **Dead methods removed.** `sighting_create` and
  `sighting_create_check_progress` are gone — their input types no longer
  exist upstream.
- **`collection()` returns all media.** It paginates to completion instead of
  returning only the first page, and takes an optional `page_size` (1–100).
- **Feed pagination.** `refresh_feed`, `feed_nodes`, and `new_postcards` follow
  pagination; `feed(first=...)` must be 1–100.
- **`Feeder.power_profile`** returns `PowerProfile.UNKNOWN` when the feeder
  reports no profile, rather than defaulting to `STANDARD`.
- **`Feeder.location`** reads the owner feeder's nested `location` as well as
  the flat member/public fields.
- **Timestamps.** `Media.created_at` and `Collection.last_visit` return
  `datetime` (they are non-null in the schema); `FeedNode.created_at` stays
  optional.

## Development

Install [pyenv] and the pinned interpreter, then use the Makefile — every
target runs inside the project venv automatically:

```bash
pyenv install 3.10.20   # matches .python-version
make deps               # create the venv and install the [dev] extra

make check    # ruff + ruff format --check + markdownlint + pyright + pytest
make format   # auto-fix ruff issues and reformat
make test     # run the test suite
make schema   # refresh tests/fixtures/schema.json from the live API
```

Alternatively, install the tooling into an existing environment with
`pip install -e '.[dev]'`.

## Releasing

The package is published to [PyPI](https://pypi.org/project/pybirdbuddy/).
To cut a release:

1. Bump `version` in `pyproject.toml` (semantic versioning; while the package
   is pre-1.0, a breaking API change takes a minor bump).
2. `make build` — build the sdist and wheel into `dist/`.
3. `make publish` — rebuild, run `twine check`, then upload to PyPI.

`make publish` uses [Twine], which reads credentials from `~/.pypirc` or the
`TWINE_USERNAME` / `TWINE_PASSWORD` environment variables; use `__token__` as
the username and a PyPI API token (the value includes its `pypi-` prefix) as
the password.

## License

Released under the [MIT License](LICENSE).

[build-status]: https://github.com/jhansche/pybirdbuddy/actions/workflows/python-package.yml?query=branch%3Amain
[build-status-shield]: https://img.shields.io/github/actions/workflow/status/jhansche/pybirdbuddy/python-package.yml?branch=main&style=for-the-badge
[license-shield]: https://img.shields.io/github/license/jhansche/pybirdbuddy.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026?style=for-the-badge
[pyenv]: https://github.com/pyenv/pyenv
[pypi]: https://pypi.org/project/pybirdbuddy/
[pypi-shield]: https://img.shields.io/pypi/v/pybirdbuddy?style=for-the-badge
[releases]: https://github.com/jhansche/pybirdbuddy/releases
[releases-shield]: https://img.shields.io/github/v/release/jhansche/pybirdbuddy.svg?style=for-the-badge
[twine]: https://twine.readthedocs.io/
