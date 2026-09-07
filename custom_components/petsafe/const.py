"""Constants for the PetSafe Integration integration."""

DOMAIN = "petsafe"
CONF_REFRESH_TOKEN = "refresh_token"
MANUFACTURER = "PetSafe"
FEEDER_MODEL_GEN1 = "SmartFeed_1.0"
FEEDER_MODEL_GEN2 = "SmartFeed_2.0"

SERVICE_ADD_SCHEDULE = "add_schedule"
SERVICE_DELETE_SCHEDULE = "delete_schedule"
SERVICE_DELETE_ALL_SCHEDULES = "delete_all_schedules"
SERVICE_MODIFY_SCHEDULE = "modify_schedule"
SERVICE_FEED = "feed"
SERVICE_PRIME = "prime"

ATTR_TIME = "time"
ATTR_AMOUNT = "amount"
ATTR_SLOW_FEED = "slow_feed"

RAKE_FINISHED = "RAKE_FINISHED"
CAT_IN_BOX = "CAT_IN_BOX"
ERROR_SENSOR_BLOCKED = "ERROR_SENSOR_BLOCKED"
RAKE_BUTTON_DETECTED = "RAKE_BUTTON_DETECTED"
RAKE_NOW = "RAKE_NOW"
RAKE_COUNTER_RESET = "RAKE_COUNTER_RESET"

FEED_DONE = "FEED_DONE"

# How often the coordinator refreshes the "extra" per-device data that needs a
# dedicated API call (feeding schedules, message history, litterbox activity).
# This data changes at most a couple of times a day, so there is nothing to be
# gained by fetching it on every coordinator tick.
DETAILS_UPDATE_INTERVAL = 300

# How many days of message history to request when looking for the last feeding.
MESSAGE_LOOKBACK_DAYS = 7

# Format PetSafe uses for scheduled feeding times (local wall-clock, 24 hour).
SCHEDULE_TIME_FORMAT = "%H:%M"

# Portion buttons. The feeder dispenses in 1/8-cup increments, so a cup value
# is only meaningful on a 0.125 boundary -- that is the step, min and hardware
# granularity all at once.
PORTION_MEAL = "meal"
PORTION_SNACK = "snack"

CUP_STEP = 0.125
MIN_FEED_EIGHTHS = 1
MAX_FEED_EIGHTHS = 32

# Starting portions. Deliberately adjustable per feeder rather than fixed:
# a household can have a big dog on a full cup and a small one on an eighth,
# and a hardcoded "meal" would be wrong (and potentially harmful) on the latter.
DEFAULT_MEAL_CUPS = 1.0
DEFAULT_SNACK_CUPS = 0.125
