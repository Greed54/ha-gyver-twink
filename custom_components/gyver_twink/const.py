"""Constants for the GyverTwink integration."""

from datetime import timedelta

DOMAIN = "gyver_twink"
DEFAULT_NAME = "GyverTwink"

# Stock firmware cannot push changes, poll often.
SCAN_INTERVAL_POLL = timedelta(seconds=15)
# Firmware 1.3 pushes changes; polling only renews the subscription.
SCAN_INTERVAL_PUSH = timedelta(seconds=60)
# How often to check whether stock firmware was replaced by 1.3.
EXT_PROBE_INTERVAL = timedelta(minutes=10)

ATTR_SCALE = "scale"
ATTR_SPEED = "speed"
ATTR_FAVORITE = "favorite"
ATTR_EFFECT = "effect"
