"""Constants for the Irish Rail Commute integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "irish_rail_commute"

# ---------------------------
# Config keys
# ---------------------------
CONF_ORIGIN: Final = "origin"
CONF_DESTINATION: Final = "destination"
CONF_ORIGIN_NAME: Final = "origin_name"
CONF_DESTINATION_NAME: Final = "destination_name"
CONF_COMMUTE_NAME: Final = "commute_name"
CONF_TIME_WINDOW: Final = "time_window"
CONF_NUM_SERVICES: Final = "num_services"
CONF_NIGHT_UPDATES: Final = "night_updates"
CONF_SEVERE_DELAY_THRESHOLD: Final = "severe_delay_threshold"
CONF_MAJOR_DELAY_THRESHOLD: Final = "major_delay_threshold"
CONF_MINOR_DELAY_THRESHOLD: Final = "minor_delay_threshold"
CONF_DEPARTED_TRAIN_GRACE_PERIOD: Final = "departed_train_grace_period"

# ---------------------------
# Defaults
# ---------------------------
DEFAULT_NAME: Final = "Irish Rail Commute"
DEFAULT_TIME_WINDOW: Final = 60
DEFAULT_NUM_SERVICES: Final = 3
DEFAULT_NIGHT_UPDATES: Final = False
DEFAULT_DEPARTED_TRAIN_GRACE_PERIOD: Final = 5
DEFAULT_SEVERE_DELAY_THRESHOLD: Final = 30
DEFAULT_MAJOR_DELAY_THRESHOLD: Final = 15
DEFAULT_MINOR_DELAY_THRESHOLD: Final = 3

# Minimum allowed delay threshold
MIN_DELAY_THRESHOLD: Final = 0

# ---------------------------
# Status constants
# ---------------------------
STATUS_NORMAL: Final = "Normal"
STATUS_ON_TIME: Final = "On Time"
STATUS_DELAYED: Final = "Delayed"
STATUS_MINOR_DELAYS: Final = "Minor Delays"
STATUS_MAJOR_DELAYS: Final = "Major Delays"
STATUS_SEVERE_DISRUPTION: Final = "Severe Disruption"
STATUS_CRITICAL: Final = "Critical"

# ---------------------------
# Time windows
# ---------------------------
NIGHT_HOURS: Final = (0, 5)  # 00:00–05:00
PEAK_HOURS: Final = [
    (6, 10),   # Morning peak
    (16, 19),  # Evening peak
]

# ---------------------------
# Update intervals
# ---------------------------
UPDATE_INTERVAL_NIGHT: Final = timedelta(minutes=15)
UPDATE_INTERVAL_OFF_PEAK: Final = timedelta(minutes=5)
UPDATE_INTERVAL_PEAK: Final = timedelta(minutes=2)