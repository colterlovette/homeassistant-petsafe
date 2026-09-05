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
