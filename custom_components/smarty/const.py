"""Constants for the SMARTY Energy integration."""
from datetime import timedelta

DOMAIN = "smarty"
DEFAULT_HOST = "https://www.getsmarty.nl"
STATE_PATH = "/api/v1/home-assistant/state"
# The SMARTY API rate-limits each token; 30 s matches the controller's own
# telemetry cadence closely enough and stays well under the limit.
SCAN_INTERVAL = timedelta(seconds=30)
REQUEST_TIMEOUT_S = 15
