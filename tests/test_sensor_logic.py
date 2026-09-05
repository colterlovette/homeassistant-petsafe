import harness
from harness import TZ, _FROZEN
import datetime, importlib

S = importlib.import_module("petsafe_integration.SensorEntities")
F = S.PetSafeFeederSensorEntity
D = datetime.datetime

ok = fail = 0
def check(label, got, want):
    global ok, fail
    if got == want:
        ok += 1; print(f"  PASS  {label}")
    else:
        fail += 1; print(f"  FAIL  {label}\n          got={got!r}\n         want={want!r}")

class Feeder:
    def __init__(self, paused=False, batteries=False, voltage=29100):
        self.is_paused = paused
        self.data = {"is_batteries_installed": batteries,
                     "battery_voltage": voltage}
    @property
    def battery_level(self):
        mn, mx = 22755, 29100
        return round(max((100 * (int(self.data["battery_voltage"]) - mn)) / (mx - mn), 0))

def feed_msg(ts, kind="FEED_DONE"):
    return {"message_type": kind, "payload": {"time": ts}}

print("\n--- DEFECT 1: empty schedule list is a valid permanent state ---")
check("no schedules -> None",        F._next_feeding(Feeder(), []), None)
check("schedules None -> None",      F._next_feeding(Feeder(), None), None)
check("all times unparseable -> None",
      F._next_feeding(Feeder(), [{"time": "not-a-time"}, {"time": None}]), None)
check("schedule missing 'time' key -> None", F._next_feeding(Feeder(), [{}]), None)
check("non-dict schedule entries -> None", F._next_feeding(Feeder(), ["20:00"]), None)

print("\n--- DEFECT 1b: the working path must not regress ---")
_FROZEN["now"] = D(2026, 9, 5, 17, 0, tzinfo=TZ)      # 17:00 local
check("next later today",
      F._next_feeding(Feeder(), [{"time": "20:00"}]), D(2026, 9, 5, 20, 0, tzinfo=TZ))
check("earliest of several today",
      F._next_feeding(Feeder(), [{"time": "22:00"}, {"time": "18:30"}, {"time": "20:00"}]),
      D(2026, 9, 5, 18, 30, tzinfo=TZ))
check("all past today -> first tomorrow",
      F._next_feeding(Feeder(), [{"time": "08:00"}, {"time": "16:00"}]),
      D(2026, 9, 6, 8, 0, tzinfo=TZ))
check("Chewi's real twice-daily schedule",
      F._next_feeding(Feeder(), [{"time": "08:00"}, {"time": "20:00"}]),
      D(2026, 9, 5, 20, 0, tzinfo=TZ))
check("paused feeder -> None (no confidently-wrong timestamp)",
      F._next_feeding(Feeder(paused=True), [{"time": "20:00"}]), None)
check("one bad entry does not discard the good ones",
      F._next_feeding(Feeder(), [{"time": "oops"}, {"time": "20:00"}]),
      D(2026, 9, 5, 20, 0, tzinfo=TZ))

print("\n--- DEFECT 1c: DST correctness on the 'tomorrow' branch ---")
# Denver springs forward 02:00 -> 03:00 on 2026-03-08.
_FROZEN["now"] = D(2026, 3, 7, 23, 0, tzinfo=TZ)
got = F._next_feeding(Feeder(), [{"time": "08:00"}])
check("08:00 the morning of a spring-forward day", got, D(2026, 3, 8, 8, 0, tzinfo=TZ))
check("  ...and its UTC offset is MDT (-6), not MST (-7)",
      got.utcoffset(), datetime.timedelta(hours=-6))
_FROZEN["now"] = None

print("\n--- DEFECT 3: last_feeding must be the NEWEST feed, not the oldest ---")
# Real shape: API returns oldest-first over a rolling 7-day window.
UTC = datetime.timezone.utc
def ep(y, mo, d, h, mi, s):            # epoch seconds, computed not guessed
    return D(y, mo, d, h, mi, s, tzinfo=UTC).timestamp()
oldest_first = [feed_msg(ep(2026, 8, 29, 2, 0, 7)),   # what it actually reported
                feed_msg(ep(2026, 8, 31, 2, 0, 7)),
                feed_msg(ep(2026, 9, 4, 2, 0, 7))]    # the true latest
newest = D(2026, 9, 4, 2, 0, 7, tzinfo=UTC)
check("oldest-first list -> newest entry", F._last_feeding(oldest_first), newest)
check("newest-first list -> same answer (order-independent)",
      F._last_feeding(list(reversed(oldest_first))), newest)
check("ignores non-FEED_DONE messages",
      F._last_feeding([feed_msg(ep(2027, 1, 1, 0, 0, 0), "FOOD_LOW"), feed_msg(ep(2026, 9, 4, 2, 0, 7))]), newest)
check("no messages -> None", F._last_feeding([]), None)
check("None -> None", F._last_feeding(None), None)
check("no FEED_DONE present -> None", F._last_feeding([feed_msg(ep(2026, 9, 1, 0, 0, 0), "FOOD_LOW")]), None)
check("malformed payloads skipped",
      F._last_feeding([{"message_type": "FEED_DONE"},
                       {"message_type": "FEED_DONE", "payload": {}},
                       {"message_type": "FEED_DONE", "payload": {"time": "x"}},
                       feed_msg(ep(2026, 9, 4, 2, 0, 7))]), newest)

# Demonstrate the old behaviour on the same data, to prove the bug is real.
def old_get_last_feeding(messages):
    for m in messages:
        if m["message_type"] == "FEED_DONE":
            return m
    return None
old = old_get_last_feeding(oldest_first)["payload"]["time"]
check("(old code on same data returned the 7-day-old entry)",
      datetime.datetime.fromtimestamp(old, datetime.timezone.utc),
      D(2026, 8, 29, 2, 0, 7, tzinfo=UTC))

print("\n--- DEFECT 4: 0% vs 'no cells fitted' ---")
check("no backup cells -> None (unknown)", F._battery_level(Feeder(batteries=False)), None)
check("cells fitted, full -> 100", F._battery_level(Feeder(batteries=True, voltage=29100)), 100)
check("cells fitted, flat -> 0", F._battery_level(Feeder(batteries=True, voltage=22755)), 0)
check("missing key treated as not installed", F._battery_level(type("X",(),{"data":{}})()), None)

print(f"\n{'='*52}\n  {ok} passed, {fail} failed\n{'='*52}")
raise SystemExit(1 if fail else 0)
