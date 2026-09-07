# homeassistant-petsafe

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

PetSafe Integration for Home Assistant.

Integrate your PetSafe Smartfeed feeders and Scoopfree litter boxes into Home Assistant.

> **This is a maintained fork of [dcmeglio/homeassistant-petsafe](https://github.com/dcmeglio/homeassistant-petsafe).**
> Install it as a HACS *custom repository*, not from the HACS default store.
> The domain is still `petsafe` and all `unique_id`s are unchanged, so it is a
> drop-in replacement: existing config entries, entity IDs and history survive.

## Why this fork exists

Upstream's last commit was January 2025. These are the defects this fork fixes.

### It span-polled the PetSafe API roughly every 10.7 seconds

Not a misconfigured interval — a feedback loop:

```
coordinator tick
  -> _handle_coordinator_update()
  -> schedule_update_ha_state(True)
  -> async_update()
  -> super().async_update()  ==  CoordinatorEntity.async_update()
  -> coordinator.async_request_refresh()
  -> coordinator tick ...
```

Every tick requested the next one, so the coordinator's 30s `update_interval`
and the sensor platform's 60s `SCAN_INTERVAL` were both bypassed. The observed
period is Home Assistant's `REQUEST_REFRESH_DEFAULT_COOLDOWN` (10s) plus the API
round trips. Buttons, selects and switches fed the same loop through
`_attr_should_poll = True` and the base `CoordinatorEntity.async_update`.

Entities are now pure consumers of coordinator data — no polling, no I/O in the
update callback. Data needing its own API call (messages, schedules, litterbox
activity) moved into the coordinator behind a 5 minute TTL, invalidated by the
services that change it. On a three-feeder account that is roughly **56,000 API
calls/day down to about 7,500**.

### An empty feeding schedule crashed the next_feeding sensor forever

`_get_next_feeding_time` indexed `[0]` on an empty list, so a feeder with no
schedule raised `IndexError` on every cycle and filled the error log. An empty
schedule is a valid permanent state — a feeder fed only on demand has no
schedule and never will — and now yields `None`. A paused feeder does too,
rather than advertising a time it will not act on.

Schedule times are also combined with each date separately instead of adding a
day to an aware datetime, which was wrong across DST transitions.

### last_feeding reported a feeding from exactly 7 days ago

`petsafe`'s `get_last_feeding()` returns the *first* `FEED_DONE` in the message
list, and the API returns messages oldest-first over a rolling 7 day window — so
the sensor reported the oldest feeding in the window and stepped forward one day
at a time as the window slid. This fork selects with `max()`, which is correct
whatever order the API returns.

### battery_level reported 0% when no backup batteries are fitted

These feeders run on mains with optional D-cell backup. `0` is indistinguishable
from a flat battery and pins low-battery automations on. Reports `unknown`
instead — absent is not empty.

### Other reliability fixes

* A 401/403 below the reauth threshold fell out of `_async_update_data` and
  returned `None`, setting `coordinator.data = None` and making every entity
  raise on the next update. Now raises `UpdateFailed` so the last good data is
  kept.
* Device lookups no longer raise `StopIteration` inside a callback when a device
  drops out of the account payload; shadow and payload reads tolerate missing or
  null keys.
* The first refresh runs before platforms are forwarded, so entities are built
  with data present.
* `petsafe` 2.0.6 -> 2.0.7, for its 403 retry-with-refresh.
* Worked around `petsafe` storing the token expiry on `token_expires_time` while
  reading `_token_expires_time`, which left it at `0` and forced a full Cognito
  re-auth before *every single request*. The workaround is fully guarded and
  no-ops against a library that fixes the typo.

## Additions

### Meal and Snack buttons, with adjustable portions

Each feeder has exactly two feed buttons, so the portion is chosen by which
button you press rather than by a service call:

| Entity | Dispenses |
|---|---|
| `button.<feeder>_meal` | the feeder's **Meal portion** |
| `button.<feeder>_snack` | the feeder's **Snack portion** |

Upstream's stock `button.<feeder>_feed` was **removed in 1.7.0**. It dispensed a
fixed 1/8 cup, which is the default Snack portion, so it was a third button
doing what Snack already does. Anything referencing `button.<feeder>_feed` must
move to one of the two above — including a `petsafe.feed` call that used it
merely to identify the feeder.

Portions are per feeder, set in cups under the device's Configuration section:

| Entity | Default |
|---|---|
| `number.<feeder>_meal_portion` | 1 cup |
| `number.<feeder>_snack_portion` | 1/8 cup |

They are **deliberately adjustable rather than fixed**. A household can have a
big dog on a full cup and a small one on an eighth, so a hardcoded "meal" would
be wrong — and potentially harmful — on the smaller animal. Range is 1/8 to 4
cups in 1/8-cup steps, matching what the hardware can actually dispense; the
value is restored across restarts.

Because these are real entities on the device, they appear automatically in the
device page's Controls card and in auto-generated dashboards under the feeder's
area — no dashboard editing and no helper scripts.

Pressing any feeder or litterbox button now also invalidates the cached message
history, so `last_feeding` / `last_cleaning` reflect the action on the next
coordinator cycle instead of up to the detail TTL later.

## Known upstream library bugs

These live in the `petsafe` PyPI package, not in this integration, and are still
present in 2.0.7. This fork works around all three.

| Location | Bug |
|---|---|
| `devices.py` `get_last_feeding()` | Returns the first `FEED_DONE`, not the most recent |
| `client.py:182` vs `:300` | Sets `token_expires_time`, reads `_token_expires_time` |
| `devices.py` `battery_level` | Returns `0` when no batteries are installed |

## Installation

HACS -> Integrations -> ⋮ -> Custom repositories

* Repository: `colterlovette/homeassistant-petsafe`
* Category: `Integration`

Then install, and restart Home Assistant.

## Tests

The decision logic is covered without needing a Home Assistant install:

```bash
cd tests && python3 test_sensor_logic.py
```

## Credits

Original integration by [@dcmeglio](https://github.com/dcmeglio), with
contributions from @cmccambridge, @hanscats, @ireneybean and @seganku.
