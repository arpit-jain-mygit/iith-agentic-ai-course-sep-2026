"""facts.py - deterministic, pre-LLM fact gathering.

Step 1: load every mock API table once and index it for fast lookups.
"""
import json
import logging
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Folder that holds assets.json, telemetry.json, work_orders.json, ...
from settings import MOCK_API   # data location comes from DATA_ROOT in .env

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load(name: str) -> list[dict]:
    """Read mock_api/<name>.json and return its list of rows."""
    with open(MOCK_API / f"{name}.json") as f:
        return json.load(f)


def _index_by(rows: list[dict], key: str) -> dict:
    """One row per key, e.g. assets by asset_tag -> {tag: row}.
    Use when the key is unique in the table."""
    return {row[key]: row for row in rows}


def _group_by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    """Many rows per key, e.g. work_orders by asset_tag -> {tag: [row, row, ...]}.
    Use when the key repeats in the table."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return grouped


# ---------------------------------------------------------------------------
# Step 1: load lookups
# ---------------------------------------------------------------------------
def load_lookups() -> dict:
    """Load all tables once. Returns a dict of lookups the later steps use."""
    return {
        # unique key -> one row
        "assets":             _index_by(_load("assets"), "asset_tag"),
        "asset_classes":      _index_by(_load("asset_classes"), "asset_code"),
        "asset_criticality":  _index_by(_load("asset_criticality"), "asset_tag"),
        "criticality_matrix": _index_by(_load("criticality_matrix"), "criticality"),
        "work_order_details": _index_by(_load("work_order_details"), "work_order_id"),

        # repeating key -> list of rows
        "telemetry":          _group_by(_load("telemetry"), "asset_tag"),
        "telemetry_pressure": _group_by(_load("telemetry_pressure"), "asset_tag"),
        "work_orders":        _group_by(_load("work_orders"), "asset_tag"),
        "inventory":          _group_by(_load("inventory"), "asset_code"),
        "purchase_orders":    _group_by(_load("purchase_orders"), "part_number"),

        # plain list (filtered in step 12)
        "technicians":        _load("technicians"),

        # composite key -> one row
        "technician_calendar": {(r["technician_id"], r["date"]): r
                                for r in _load("technician_calendar")},
    }


# ---------------------------------------------------------------------------
# Step 2: asset lookup
#
# Why this is separate from step 1:
#
#                     Step 1: load_lookups()          Step 2: get_asset()
#   Runs              once, at startup                once per event (200 times)
#   Input             nothing; it reads files         one asset_tag from one event
#   Job               build indexes                   answer one question using an index
#   Cost              slow: 14 files, ~30,000 rows    fast: one dict lookup
#   Fails because of  missing file, bad JSON          unknown tag, wrong case, code mismatch
#
# Merging them would mean either re-reading all 14 files for every event, or
# looking up an asset at startup, before any event (and its asset_tag) exists.
#
# Keeping them separate means:
#   1. Each step is a pure function of (lookups, event fields), so it's easy to test.
#   2. The data source can change (JSON -> database -> MCP server) by editing only
#      step 1; get_asset still receives a dict.
#   3. Steps 2-12 have exactly the shape of LLM tools / MCP endpoints
#      (get_asset(tag), get_history(tag, date)); step 1 is the server's startup.
#   4. Errors stay in the right place: a missing file stops the run, an unknown
#      tag only logs a warning for that one event.
#
# In short: step 1 builds the indexes; steps 2-12 are queries against them.
# ---------------------------------------------------------------------------
ASSET_FIELDS = ("asset_code", "description", "criticality", "line",
                "installed_on", "running_hours", "last_pm_on")


def get_asset(lk: dict, asset_tag: str) -> dict | None:
    """Registry details for one machine, or None if the tag is unknown.

    Returns only the fields later steps need (ASSET_FIELDS), plus the tag
    actually matched, so callers can see if it was normalised.
    """
    # Exact match first; .get() returns None instead of raising KeyError
    matched = asset_tag
    row = lk["assets"].get(asset_tag)

    # Fall back to a normalised tag (tolerates case and whitespace differences)
    if row is None:
        matched = asset_tag.strip().upper()
        row = lk["assets"].get(matched)
        if row is not None:
            logger.warning("asset_tag %r normalised to %r", asset_tag, matched)

    if row is None:
        logger.warning("Unknown asset_tag %r", asset_tag)
        return None

    return {"asset_tag": matched, **{k: row[k] for k in ASSET_FIELDS}}


def check_asset_code(asset: dict | None, event_asset_code: str) -> bool | None:
    """Does the event's asset_code agree with the registry? None if asset unknown.

    On a mismatch the registry wins: limits and parts are looked up from it.
    """
    if asset is None:
        return None
    if asset["asset_code"] != event_asset_code:
        logger.warning("asset_code mismatch for %s: event says %r, registry says %r",
                       asset["asset_tag"], event_asset_code, asset["asset_code"])
        return False
    return True


# ---------------------------------------------------------------------------
# Step 3: missing fields
#
# A reading is "missing" only if it is null AND this asset class is expected
# to report it.
#
# Which readings are expected, from the JSON tables:
#   - asset_classes.json: every class has vibration and temperature limits;
#     pressure_nominal_bar is set only for classes with a monitored pressure
#   - telemetry.json logs vibration, temp and current for every asset;
#     telemetry_pressure.json only for assets in those pressure classes
# So: vibration, temp and current are always expected; pressure only when
# asset_classes.pressure_nominal_bar is set.
#
# missing_fields is always computed. Comparing it with the event's
# ground_truth is evaluation only (main(..., evaluate=True)).
# ---------------------------------------------------------------------------
READING_FIELDS = ("vibration_mm_s", "temp_c", "pressure_bar", "current_a")


def expected_readings(lk: dict, asset_code: str) -> list[str]:
    """Readings this asset class should report."""
    asset_class = lk["asset_classes"].get(asset_code, {})
    expects_pressure = asset_class.get("pressure_nominal_bar") is not None
    return [f for f in READING_FIELDS if f != "pressure_bar" or expects_pressure]


def get_missing_fields(lk: dict, readings: dict | None, asset_code: str) -> list[str]:
    """Expected readings that are null (or absent) in the event.

    Uses `is None`, not a truthiness test: 0.0 (e.g. current on a stopped
    machine) is a real reading, not a missing one.
    """
    readings = readings or {}
    return [f for f in expected_readings(lk, asset_code) if readings.get(f) is None]


# ---------------------------------------------------------------------------
# Step 4: trip keyword
#
# Did the machine actually trip (protection stopped it)? Deterministic only
# for machine-generated alarm strings. For human prose (operator_report,
# shift_log, inspection) return None: the LLM decides later.
#
# The result is evidence for the LLM; what a trip means for priority is
# decided by the LLM, not here.
#
# Matching rules:
#   - codes like VIB_TRIP: \bTRIP\b misses these ("_" is a word char)
#   - "tripped": past tense must match too
#   - "trip threshold" / "trip limit": names the limit, not a trip event
# ---------------------------------------------------------------------------

# Matches TRIP / TRIPPED as a word, including inside codes like VIB_TRIP or
# SAFETY_CIRCUIT_TRIP. Letter look-arounds instead of \b, because \b treats
# "_" as part of a word.
TRIP_PATTERN = re.compile(r"(?<![A-Za-z])TRIP(?:PED)?(?![A-Za-z])", re.IGNORECASE)

# "trip" used as a limit, not an event: "exceeds trip threshold", "trip limit"
TRIP_LIMIT_PATTERN = re.compile(r"TRIP\s+(?:THRESHOLD|LIMIT|SETPOINT|LEVEL)", re.IGNORECASE)


def detect_trip(source: str, raw_text: str) -> dict:
    """Return {"is_trip": True/False/None, "evidence": matched text or None}.

    True  - a sensor alarm says the machine tripped
    False - a sensor alarm with no trip (or only a trip *limit* mentioned)
    None  - human prose; left for the LLM
    """
    if source != "sensor_alarm":
        return {"is_trip": None, "evidence": None}

    # Keep only matches that are not the start of "TRIP THRESHOLD/LIMIT/..."
    real = [m for m in TRIP_PATTERN.finditer(raw_text)
            if not TRIP_LIMIT_PATTERN.match(raw_text, m.start())]

    if real:
        # Evidence = the whole whitespace-separated token, e.g. "SAFETY_CIRCUIT_TRIP"
        # rather than just "TRIP", so the reason is readable on its own
        start = raw_text.rfind(" ", 0, real[0].start()) + 1
        end = raw_text.find(" ", real[0].end())
        token = raw_text[start:end if end != -1 else None].strip(".,:;")
        return {"is_trip": True, "evidence": token}
    return {"is_trip": False, "evidence": None}


# ---------------------------------------------------------------------------
# Step 5: suspect sensors (physics checks only)
#
# A reading that breaks a law of physics cannot come from a working sensor.
# Flag it so that step 6 skips it and the LLM knows not to diagnose from it.
#
# Physical facts used:
#   - temperature cannot be at or below absolute zero (-273.15 C)
#   - vibration and current are magnitudes: they cannot be negative
#   - gauge pressure cannot be below -1 bar (a perfect vacuum)
#
# Anything physically possible, however unusual, is NOT flagged here; judging
# whether such a value is believable is left to the LLM.
# 0.0 is a valid reading (e.g. a stopped machine).
# ---------------------------------------------------------------------------
ABSOLUTE_ZERO_C = -273.15
FULL_VACUUM_BAR = -1.0   # gauge pressure
NON_NEGATIVE_FIELDS = ("vibration_mm_s", "current_a")


def check_physics(field: str, value: float) -> str | None:
    """Reason a reading is physically impossible, or None if it could be real."""
    if field == "temp_c" and value <= ABSOLUTE_ZERO_C:
        return "at or below absolute zero"
    if field == "pressure_bar" and value < FULL_VACUUM_BAR:
        return "below full vacuum"
    if field in NON_NEGATIVE_FIELDS and value < 0:
        return "negative magnitude"
    return None


def get_suspect_readings(readings: dict | None) -> dict:
    """{field: {"value": v, "reason": why}} for every physically impossible reading."""
    readings = readings or {}
    suspect = {}
    for field in READING_FIELDS:
        value = readings.get(field)
        if value is None:                     # missing readings are step 3's job
            continue
        reason = check_physics(field, value)
        if reason:
            suspect[field] = {"value": value, "reason": reason}
    return suspect


# ---------------------------------------------------------------------------
# Step 6: readings vs class limits
#
# Limits available in asset_classes.json (per asset_code):
#   vibration_mm_s : vibration_warning_mm_s, vibration_trip_mm_s
#   temp_c         : temp_warning_c, temp_trip_c
#   pressure_bar   : pressure_nominal_bar, pressure_low_alarm_bar
#                    (only for classes with a monitored pressure; there is
#                     no high-pressure limit in the table)
#   current_a      : no limits in the table
#
# For each reading present in the event:
#   - skip it if step 5 marked it suspect (a broken sensor's value is not compared)
#   - compare it with the limits the table has; where the table has none,
#     report the value with status "no_limit" and let the LLM judge it
# Missing readings (step 3) are simply absent from the result.
# ---------------------------------------------------------------------------
UPPER_LIMITS = {
    # field: (warning column, trip column) in asset_classes.json
    "vibration_mm_s": ("vibration_warning_mm_s", "vibration_trip_mm_s"),
    "temp_c": ("temp_warning_c", "temp_trip_c"),
}


def level_vs_upper(value: float, warning: float, trip: float) -> str:
    """'trip' if value >= trip, 'warning' if value >= warning, else 'normal'.
    Trip is checked first: a value above trip is also above warning."""
    if value >= trip:
        return "trip"
    if value >= warning:
        return "warning"
    return "normal"


def check_pressure(value: float, asset_class: dict) -> dict:
    """Compare pressure with the class's nominal value and low-alarm limit."""
    nominal = asset_class.get("pressure_nominal_bar")
    low = asset_class.get("pressure_low_alarm_bar")
    if nominal is None or low is None:
        return {"value": value, "status": "no_limit"}   # no monitored pressure in the table

    # No high limit in the table, so there is no "high" status; deviation_pct
    # tells the LLM how far the value is from nominal and it decides if it matters
    return {
        "value": value,
        "nominal": nominal,
        "low_alarm": low,
        "deviation_pct": round((value - nominal) / nominal * 100, 1),
        "status": "low_alarm" if value <= low else "above_low_alarm",
    }


def check_readings(lk: dict, readings: dict | None, asset_code: str, suspect: dict) -> dict:
    """{field: {...comparison...}} for every present, non-suspect reading."""
    readings = readings or {}
    asset_class = lk["asset_classes"].get(asset_code, {})
    result = {}
    for field in READING_FIELDS:
        value = readings.get(field)
        if value is None or field in suspect:
            continue

        if field in UPPER_LIMITS:
            warn_col, trip_col = UPPER_LIMITS[field]
            warning, trip = asset_class.get(warn_col), asset_class.get(trip_col)
            if warning is None or trip is None:
                result[field] = {"value": value, "status": "no_limit"}
            else:
                result[field] = {"value": value, "warning": warning, "trip": trip,
                                 "status": level_vs_upper(value, warning, trip)}
        elif field == "pressure_bar":
            result[field] = check_pressure(value, asset_class)
        else:   # current_a: no limits in the table
            result[field] = {"value": value, "status": "no_limit"}
    return result


# ---------------------------------------------------------------------------
# Step 7: event time -> telemetry hour index
#
# IN SHORT: converts the event's received_at (a date-time) into a telemetry
# hour_index, so step 8 can pick the telemetry hours just BEFORE the event.
#   input : event received_at + anchor (hour 719 = latest received_at, floored)
#   output: event_hour_index = 719 - hours between event and anchor
#           (negative = before telemetry starts; fractional = mid-hour)
#
# Two kinds of data, from two different systems:
#
#   Intake event (records.jsonl)          Telemetry (telemetry.json)
#   "something happened, please look"     "what the machine did all along"
#   occasional message, messy text        every machine, every hour, numbers
#   one snapshot of readings              30 days of history (trends)
#   has a real time: received_at          has NO time, only hour_index 0..719
#   the job to triage                     background evidence for that job
#
# Like a patient in the ER (the event) and their smartwatch log (telemetry):
# to judge the complaint you look at the log from just BEFORE they came in.
#
# The problem: the two files share no time key. An event says
# "2026-07-20 10:00", telemetry says "hour 427". Which telemetry rows were
# recorded just before the event? This step lines the two up.
#
# How: fix one point, then count back.
#   - Anchor: hour 719 (the last telemetry hour) = the latest received_at
#     across all intake events, rounded down to the hour.
#     ASSUMPTION: both files end at the same "now". Computed once per run.
#   - hour_index(event) = 719 - (hours between the event and the anchor)
#
#   hour_index:  0 ............. 427 ............. 719
#   calendar:    anchor - 719h   event             anchor
#                                 └─ its last 24 h = hours 403..426
#
# Why it matters: without this, every event would use the LAST 24 hours of
# the file, which for an older event are readings taken days AFTER it
# (look-ahead / data leakage: the LLM would see data that did not exist yet).
#
# The result can be:
#   - negative   -> event happened before telemetry starts (no history)
#   - fractional -> event happened part-way through an hour
# Step 8 uses it to pick the right telemetry rows.
# ---------------------------------------------------------------------------
LAST_HOUR = 719   # last hour_index in telemetry.json


def parse_time(ts: str) -> datetime:
    """ISO-8601 string -> timezone-aware datetime ('Z' means UTC).
    fromisoformat on older Pythons does not accept a trailing 'Z'."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def telemetry_anchor(events: list) -> datetime:
    """Clock time of hour_index LAST_HOUR: latest received_at, floored to the hour."""
    latest = max(parse_time(e.received_at) for e in events)
    return latest.replace(minute=0, second=0, microsecond=0)


def event_hour_index(received_at: str, anchor: datetime) -> float:
    """Where the event sits on the telemetry hour scale (can be < 0 or fractional)."""
    hours_before = (anchor - parse_time(received_at)).total_seconds() / 3600
    return round(LAST_HOUR - hours_before, 2)


# ---------------------------------------------------------------------------
# Step 8: telemetry summary (the hours just BEFORE the event)
#
# IN SHORT: picks this asset's telemetry rows from the WINDOW_HOURS before the
# event (using step 7's hour index) and summarises them per sensor.
#   input : asset_tag, asset_code, event_hour_index (step 7)
#   output: window, how many hours were available, and per sensor:
#           min / max / avg / first / last / change (last - first),
#           plus a status vs the class limits in asset_classes.json
#
# Step 7 vs step 8: step 7 FINDS WHERE to look; step 8 LOOKS and reports.
#
#                  Step 7                          Step 8
#   question       WHEN did the event happen,      WHAT was the machine doing in
#                  on the telemetry hour scale?    the hours before that?
#   input          received_at + anchor            asset + step 7's hour index
#   output         one number (event_hour_index)   a summary per sensor
#   reads rows?    no, only times                  yes, the sensor rows
#   smartwatch     finding the PAGE in the log     READING those pages
#
# Why step 8 exists:
#   1. Context the event alone lacks: one snapshot vs a history that shows
#      SUDDEN (flat, then spike) or GRADUAL (rising for hours) behaviour.
#   2. Confirm or contradict the event: steady normal history behind a
#      "high" alarm hints at a sensor glitch; hours already in warning mean a
#      real, growing problem.
#   3. A summary, not raw data: a few numbers per sensor instead of every
#      row, computed in code so the LLM never does arithmetic.
#   4. Honest about gaps: coverage none / partial tells the LLM how much
#      history really existed.
#
# Which rows: hour_index <= event hour (a reading taken at or before the event)
#   end   = floor(event_hour_index)
#   start = end - WINDOW_HOURS + 1, but never below 0
#
# Three cases:
#   end < 0                  -> no telemetry before the event: say so, no stats
#   fewer than WINDOW_HOURS  -> partial history: report how many hours were used
#   otherwise                -> full window
#
# seeded_fault is NEVER returned: it is the answer label, not a reading.
# ---------------------------------------------------------------------------
WINDOW_HOURS = 24          # look-back window (design choice)
TELEMETRY_CHANNELS = ("vibration_mm_s", "temp_c", "current_a")


def window_bounds(event_hour: float) -> tuple[int, int] | None:
    """(start, end) hour_index of the look-back window, or None if no history."""
    end = math.floor(event_hour)
    if end < 0:
        return None
    return (max(0, end - WINDOW_HOURS + 1), end)


def summarise(rows: list[dict], channel: str) -> dict:
    """min / max / avg / first / last / change for one sensor channel.
    rows must be sorted by hour_index (oldest first) so first/last are right."""
    values = [r[channel] for r in rows]
    return {
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 2),
        "first": values[0],
        "last": values[-1],
        "change": round(values[-1] - values[0], 2),
    }


def _rows_in_window(rows: list[dict], start: int, end: int) -> list[dict]:
    """Rows with start <= hour_index <= end, oldest first."""
    return sorted((r for r in rows if start <= r["hour_index"] <= end),
                  key=lambda r: r["hour_index"])


def get_telemetry_summary(lk: dict, asset_tag: str, asset_code: str, event_hour: float) -> dict:
    """Summary of the WINDOW_HOURS of telemetry before the event."""
    no_history = {"window": None, "hours": 0, "coverage": "none",
                  "note": "no telemetry before the event"}

    bounds = window_bounds(event_hour)
    if bounds is None:
        return no_history
    start, end = bounds

    rows = _rows_in_window(lk["telemetry"].get(asset_tag, []), start, end)
    if not rows:                       # unknown asset or no data in the window
        return no_history

    summary = {"window": [start, end], "hours": len(rows),
               "coverage": "full" if len(rows) == WINDOW_HOURS else "partial"}

    # Sensors with warning/trip limits get a status for the window's max
    # (same limits and rule as step 6, applied to the history)
    asset_class = lk["asset_classes"].get(asset_code, {})
    for channel in TELEMETRY_CHANNELS:
        stats = summarise(rows, channel)
        if channel in UPPER_LIMITS:
            warn_col, trip_col = UPPER_LIMITS[channel]
            warning, trip = asset_class.get(warn_col), asset_class.get(trip_col)
            if warning is not None and trip is not None:
                stats["status"] = level_vs_upper(stats["max"], warning, trip)
        summary[channel] = stats

    # Pressure only exists for some assets
    prows = _rows_in_window(lk["telemetry_pressure"].get(asset_tag, []), start, end)
    if prows:
        stats = summarise(prows, "pressure_bar")
        low = asset_class.get("pressure_low_alarm_bar")
        if low is not None:
            stats["status"] = "low_alarm" if stats["min"] <= low else "above_low_alarm"
        summary["pressure_bar"] = stats
    return summary


# ---------------------------------------------------------------------------
# Step 9: work-order history (what was done to this machine BEFORE the event)
#
# IN SHORT: collects this asset's work orders raised on or before the event
# date, joins each to its details, and summarises the history.
#   input : asset_tag, event received_at
#   output: total count, the RECENT_LIMIT most recent work orders (with details),
#           past failure modes, counts by type, and jobs still open at event time
#
# Always called, for every event. If the asset has no work orders before the
# event (or is unknown), the result is simply empty (total 0).
#
# Why step 9 exists:
#   1. Repeat faults: the same failure_mode coming back points to a root cause
#      that was never fixed.
#   2. Backlog: maintenance still open or deferred at event time is context
#      (an overdue job may be why the machine is failing now).
#   3. Recent work: a job done just before the event may have caused it
#      (e.g. a part fitted wrongly).
#   4. Same rule as step 8: only what existed at event time (no look-ahead).
#
# Work orders are per MACHINE; a part is just one attribute of a work order:
#
#   asset (asset_tag)
#     └── work_orders.json              many per asset          key: asset_tag
#           └── work_order_details.json one per work order      key: work_order_id
#                 └── part_number       zero or ONE part per work order (+ part_quantity)
#                       └── inventory.json  parts fit an asset CLASS (asset_code)
#
#   - step 9 (here): which parts has THIS MACHINE used?   (history of use)
#   - step 11      : which parts fit this KIND of machine, are they in stock?
#                                                        (availability)
#
# Time rules:
#   - raised_on is a DATE; the event has a date-time. Compare dates:
#     raised_on <= event date. (A job raised the same day might be after the
#     event; with dates only we cannot tell, so it is included.)
#   - status in work_orders.json is TODAY's status, not the status at event
#     time. A job closed after the event was still open when it happened, so
#     status_at_event is derived from completed_on:
#       completed_on present and <= event date  -> "closed"
#       otherwise                               -> "open_at_event"
#   - ISO dates ("YYYY-MM-DD") compare correctly as plain strings.
# ---------------------------------------------------------------------------
RECENT_LIMIT = 5      # how many recent work orders to return (design choice)

WO_FIELDS = ("work_order_id", "raised_on", "type", "priority", "downtime_minutes",
             "permit_required", "technician_id")
DETAIL_FIELDS = ("failure_mode", "part_number", "part_quantity", "permit_type",
                 "downtime_cost_inr", "completed_on")


def status_at_event(details: dict, event_day: str) -> str:
    """'closed' if the job was completed on or before the event date, else 'open_at_event'."""
    completed = details.get("completed_on")
    return "closed" if completed and completed <= event_day else "open_at_event"


def with_details(lk: dict, wo: dict, event_day: str) -> dict:
    """One work order joined to its details, plus its status at event time."""
    details = lk["work_order_details"].get(wo["work_order_id"], {})
    return {
        **{k: wo[k] for k in WO_FIELDS},
        **{k: details.get(k) for k in DETAIL_FIELDS},
        "status_at_event": status_at_event(details, event_day),
    }


def get_history(lk: dict, asset_tag: str, received_at: str) -> dict:
    """Work-order history of one asset, as it stood at the event date."""
    event_day = received_at[:10]

    orders = sorted((w for w in lk["work_orders"].get(asset_tag, []) if w["raised_on"] <= event_day),
                    key=lambda w: w["raised_on"], reverse=True)      # newest first
    detailed = [with_details(lk, w, event_day) for w in orders]

    return {
        "total": len(detailed),
        "recent": detailed[:RECENT_LIMIT],
        # from ALL orders, not just recent: an old repeat fault still matters
        "failure_modes": [{"raised_on": w["raised_on"], "failure_mode": w["failure_mode"]}
                          for w in detailed if w["failure_mode"]],
        "by_type": dict(Counter(w["type"] for w in detailed)),
        "open_at_event": [w["work_order_id"] for w in detailed
                          if w["status_at_event"] == "open_at_event"],
    }


# ---------------------------------------------------------------------------
# Step 10: downtime cost (cost per hour of this machine standing still)
#
# IN SHORT: looks up what one hour of THIS machine being stopped costs.
#   input : asset_tag, asset criticality (step 2)
#   output: cost_per_hour_inr and where the number came from (rate_source)
#
# Always called, for every event.
#
# Why step 10 exists:
#   Every hour a machine is stopped, the factory loses money, and that amount
#   differs a lot between machines. When two events compete for the same
#   technician, the one losing more per hour of waiting should go first.
#   The rate gives the event a price tag: urgency in money, not just words.
#
# Two ways to compare machines without forecasting how long a repair takes:
#
#   Option 1 (CHOSEN): the hourly rate
#     asset_criticality.json  downtime_cost_per_hour_inr
#     "every extra hour this machine waits costs X". Enough to rank urgency,
#     and needs no assumption about repair length.
#
#   Option 2 (not used): actual past stoppage costs
#     work_order_details.json  downtime_cost_inr  (summed / averaged over the
#     machine's past unplanned work orders). Real history, but it describes
#     past repairs, not this event.
#
#   Dropped: rate x average past hours. That is a FORECAST: it assumes this
#   stoppage lasts as long as past ones, which depends on the fault (not yet
#   diagnosed). If a forecast is needed, the LLM makes it after diagnosis,
#   using the rate from here.
#
# Fallback: if the machine has no row in asset_criticality.json, use the
# class default from criticality_matrix.json
# (default_downtime_cost_inr_per_hour for the asset's criticality).
# rate_source always says which one was used.
# ---------------------------------------------------------------------------


def get_downtime(lk: dict, asset_tag: str, criticality: str | None) -> dict:
    """Cost per hour of this machine being stopped, and where it came from."""
    # 1. This machine's own rate
    row = lk["asset_criticality"].get(asset_tag)
    if row is not None:
        return {"cost_per_hour_inr": row["downtime_cost_per_hour_inr"],
                "rate_source": "asset_criticality"}

    # 2. Fallback: the class default for the asset's criticality
    #    (criticality is None if step 2 found no asset; "" safely matches nothing)
    class_row = lk["criticality_matrix"].get(criticality or "", {})
    rate = class_row.get("default_downtime_cost_inr_per_hour")
    if rate is not None:
        return {"cost_per_hour_inr": rate, "rate_source": "criticality_matrix_default"}

    # 3. Unknown: None, not 0 (0 would claim the stoppage costs nothing)
    return {"cost_per_hour_inr": None, "rate_source": "none"}


# ---------------------------------------------------------------------------
# Step 11: inventory check (spare parts for this KIND of machine)
#
# IN SHORT: lists every spare part that fits this asset class, flags stock
# problems, shows purchase orders that were open at event time, and marks the
# parts this machine has used before.
#   input : asset_tag, asset_code, event received_at
#   output: summary lists (out_of_stock, below_reorder, used_before) and, per
#           part: stock, reorder point, lead time, cost, flags, open POs
#
# Always called, for every event.
#
# Why step 11 exists:
#   Once the LLM knows the fault, the next question is "can we fix it now?"
#   A repair is only as fast as its slowest part: a part out of stock with a
#   long lead time can turn a short repair into a long stoppage. Step 11 lays
#   out what is available, so the LLM can pick parts and spot gaps.
#
# Parts fit a CLASS, not one machine (inventory.json is keyed by asset_code):
#   - step 9 : which parts has THIS MACHINE used?            (history of use)
#   - step 11: which parts fit this KIND of machine, are they in stock?
#   used_before links the two: parts in this class that this machine's past
#   work orders used (work_order_details.part_number).
#   Which part the CURRENT fault needs is decided by the LLM, not here.
#
# Flags (per part, from inventory.json columns):
#   out_of_stock  = on_hand == 0
#   below_reorder = on_hand <= reorder_point
#
# Purchase orders open AT EVENT TIME (same no-look-ahead rule as steps 8-9):
#   raised_on <= event date
#   AND not received by then (received_on is None or received_on > event date)
#   AND status != "cancelled"   (no cancellation date exists, so a cancelled
#                                PO is treated as never open: design choice)
#
# Limitation: on_hand / reorder_point are TODAY's values; the JSON has no
# stock history, so stock at event time cannot be reconstructed. The output
# says so, so the LLM does not over-trust the numbers.
# ---------------------------------------------------------------------------
PART_FIELDS = ("part_number", "description", "on_hand", "reorder_point",
               "lead_time_days", "unit_cost_inr", "supplier_tier", "criticality")
PO_FIELDS = ("po_id", "quantity", "status", "raised_on", "expected_delivery_on")


def po_open_at_event(po: dict, event_day: str) -> bool:
    """Was this purchase order raised, and not yet received, at the event date?"""
    if po["status"] == "cancelled":
        return False
    if po["raised_on"] > event_day:          # did not exist yet
        return False
    received = po.get("received_on")
    return received is None or received > event_day   # still on its way


def parts_used_by_asset(lk: dict, asset_tag: str, event_day: str) -> set[str]:
    """part_numbers this machine's work orders used, up to the event date."""
    used = set()
    for wo in lk["work_orders"].get(asset_tag, []):
        if wo["raised_on"] > event_day:
            continue
        part = lk["work_order_details"].get(wo["work_order_id"], {}).get("part_number")
        if part is not None:
            used.add(part)
    return used


def get_inventory_check(lk: dict, asset_tag: str, asset_code: str, received_at: str) -> dict:
    """Every part for this asset class, flagged, with POs open at event time."""
    event_day = received_at[:10]
    used = parts_used_by_asset(lk, asset_tag, event_day)

    parts = []
    for p in lk["inventory"].get(asset_code, []):
        open_pos = [{k: po[k] for k in PO_FIELDS}
                    for po in lk["purchase_orders"].get(p["part_number"], [])
                    if po_open_at_event(po, event_day)]
        parts.append({
            **{k: p[k] for k in PART_FIELDS},
            "out_of_stock": p["on_hand"] == 0,
            "below_reorder": p["on_hand"] <= p["reorder_point"],
            "used_before": p["part_number"] in used,
            "open_purchase_orders": open_pos,
        })

    return {
        "total_parts": len(parts),
        "out_of_stock": [p["part_number"] for p in parts if p["out_of_stock"]],
        "below_reorder": [p["part_number"] for p in parts if p["below_reorder"]],
        "used_before": [p["part_number"] for p in parts if p["used_before"]],
        "stock_note": "on_hand is today's value; stock at event time is not available",
        "parts": parts,
    }


# ---------------------------------------------------------------------------
# Step 12: technician pool (who could work on this machine)
#
# IN SHORT: finds technicians whose trade matches this asset class, shows
# their level, line and certifications, and their calendar on the event date.
#   input : asset_code, asset line (step 2), event received_at
#   output: required skills, whether the calendar covers the event date,
#           and a ranked list of candidate technicians
#
# Always called, for every event.
#
# Why step 12 exists:
#   A diagnosis is only useful if someone qualified can act on it. Step 12
#   narrows the whole crew to the ones with the right trade and shows what
#   the LLM / planner needs to pick one: seniority, line, certifications,
#   availability.
#
# Where the data comes from (JSON only):
#   - required trade: asset_classes.json  primary_skill (secondary_skill too)
#   - technicians.json: primary_skill, secondary_skill, skill_level,
#     years_experience, home_line, loto_authorised, *_certified columns
#   - technician_calendar.json keyed by (technician_id, date): status,
#     shift, available_hours
#
# Matching (design choice):
#   a technician is a candidate if their primary OR secondary skill equals the
#   class's primary_skill or secondary_skill. match says which:
#     "primary"   -> technician holds the class's primary trade
#     "secondary" -> technician holds only the class's secondary trade
#
# NOT done here: filtering on loto_authorised or certifications. Whether the
# job needs them depends on the diagnosis (LLM). The fields are passed through
# so the post-LLM step can filter.
#
# Ranking (design choice), best first:
#   1. match == "primary"
#   2. same line as the asset (home_line == asset line)
#   3. higher skill_level (L3 > L2 > L1)
#   4. more years_experience
#
# Availability: the calendar row for (technician, event date). If there is no
# row (the calendar does not cover that date), availability is None = unknown,
# NOT "available": the LLM must not assign someone on an assumption.
# ---------------------------------------------------------------------------
TECH_FIELDS = ("technician_id", "name", "primary_skill", "secondary_skill", "skill_level",
               "years_experience", "home_line", "loto_authorised")
CERT_FIELDS = ("hot_work_certified", "confined_space_certified", "work_at_height_certified",
               "high_voltage_certified", "pressure_system_certified")


def skill_match(tech: dict, primary: str | None, secondary: str | None) -> str | None:
    """'primary', 'secondary' or None: does this technician hold the class's trade?"""
    tech_skills = {tech["primary_skill"], tech["secondary_skill"]}   # secondary may be None
    if primary and primary in tech_skills:
        return "primary"
    if secondary and secondary in tech_skills:
        return "secondary"
    return None


def availability(lk: dict, technician_id: str, event_day: str) -> dict | None:
    """The technician's calendar on the event date, or None if not in the calendar."""
    row = lk["technician_calendar"].get((technician_id, event_day))
    if row is None:
        return None
    return {"status": row["status"], "shift": row["shift"],
            "available_hours": row["available_hours"]}


def get_technician_pool(lk: dict, asset_code: str, line: str | None, received_at: str) -> dict:
    """Ranked technicians whose trade matches this asset class."""
    event_day = received_at[:10]
    asset_class = lk["asset_classes"].get(asset_code, {})
    primary, secondary = asset_class.get("primary_skill"), asset_class.get("secondary_skill")

    candidates = []
    for t in lk["technicians"]:
        match = skill_match(t, primary, secondary)
        if match is None:
            continue
        candidates.append({
            **{k: t[k] for k in TECH_FIELDS},
            "certifications": {k: t[k] for k in CERT_FIELDS},
            "match": match,
            "same_line": line is not None and t["home_line"] == line,
            "availability": availability(lk, t["technician_id"], event_day),
        })

    # Best first: primary match, same line, higher level ("L3"[1:] -> 3), more experience
    candidates.sort(key=lambda c: (c["match"] != "primary", not c["same_line"],
                                   -int(c["skill_level"][1:]), -c["years_experience"]))

    return {
        "required_skills": {"primary": primary, "secondary": secondary},
        "calendar_covers_event_date": any(c["availability"] is not None for c in candidates),
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Step 13: prepare facts for the LLM (compact copy + safety guard)
#
# IN SHORT: builds prompt_facts, a compact copy of facts for the prompt, and
# checks that no answer labels leak into either.
#   input : the event, the full facts dict (steps 2-12)
#   output: prompt_facts (what the LLM sees); facts stays unchanged for the
#           post-LLM steps (they look up full part / technician details there)
#
# Always called, for every event, as the last step before the LLM.
#
# Why step 13 exists:
#   1. Size: the full parts and technician lists are long. Every extra token
#      costs money and dilutes the model's attention.
#   2. Focus: send summaries plus only the items worth attention; the full
#      details stay in facts for the code that runs after the LLM.
#   3. The event itself: the LLM needs the raw text and readings it is
#      triaging (source, raw_text, readings), but never ground_truth.
#   4. Safety: answer labels (ground_truth, seeded_fault) must never reach
#      the model; a final scan fails loudly if they do.
#
# What goes into prompt_facts (design choices):
#   event       : record_id, event_id, source, received_at, raw_text,
#                 asset_tag, asset_code, readings        (NO ground_truth)
#   unchanged   : asset, missing_fields, trip, suspect_readings,
#                 readings_check, event_hour_index, telemetry, history, downtime
#   inventory   : summary lists + only parts that are out_of_stock,
#                 below_reorder or used_before (compact fields)
#   technicians : required_skills, calendar_covers_event_date,
#                 top PROMPT_TECH_LIMIT candidates (compact fields)
#
# The event part is built from an ALLOW-list of fields (not by deleting
# ground_truth): any label field added to the event model later stays out.
# ---------------------------------------------------------------------------
PROMPT_TECH_LIMIT = 5                     # design choice
FORBIDDEN_KEYS = ("ground_truth", "seeded_fault")
EVENT_PROMPT_FIELDS = ("record_id", "event_id", "source", "received_at", "raw_text",
                       "asset_tag", "asset_code", "readings")
UNCHANGED_KEYS = ("asset", "missing_fields", "trip", "suspect_readings", "readings_check",
                  "event_hour_index", "telemetry", "history", "downtime")
PROMPT_PART_FIELDS = ("part_number", "description", "on_hand", "reorder_point",
                      "lead_time_days", "out_of_stock", "below_reorder", "used_before",
                      "open_purchase_orders")
PROMPT_TECH_FIELDS = ("technician_id", "primary_skill", "secondary_skill", "skill_level",
                      "home_line", "match", "same_line", "loto_authorised",
                      "certifications", "availability")


def find_forbidden_keys(obj, path: str = "") -> list[str]:
    """Paths of any FORBIDDEN_KEYS anywhere inside a nested dict / list."""
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else key
            if key in FORBIDDEN_KEYS:
                found.append(here)
            found += find_forbidden_keys(value, here)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found += find_forbidden_keys(item, f"{path}[{i}]")
    return found


def compact_inventory(inventory: dict) -> dict:
    """Summary lists + only the parts worth the LLM's attention."""
    keep = [{k: p[k] for k in PROMPT_PART_FIELDS}
            for p in inventory["parts"]
            if p["out_of_stock"] or p["below_reorder"] or p["used_before"]]
    return {
        "total_parts": inventory["total_parts"],
        "out_of_stock": inventory["out_of_stock"],
        "below_reorder": inventory["below_reorder"],
        "used_before": inventory["used_before"],
        "stock_note": inventory["stock_note"],
        "flagged_parts": keep,
    }


def compact_technicians(technicians: dict) -> dict:
    """Required skills + the top PROMPT_TECH_LIMIT candidates."""
    top = [{k: c[k] for k in PROMPT_TECH_FIELDS}
           for c in technicians["candidates"][:PROMPT_TECH_LIMIT]]
    return {
        "required_skills": technicians["required_skills"],
        "calendar_covers_event_date": technicians["calendar_covers_event_date"],
        "total_candidates": len(technicians["candidates"]),
        "top_candidates": top,
    }


def build_prompt_facts(event, facts: dict) -> dict:
    """Compact, label-free view of the event + facts for the LLM prompt."""
    # Pydantic allow-list: only these fields are copied, so ground_truth never is
    event_part = event.model_dump(include=set(EVENT_PROMPT_FIELDS))

    prompt_facts = {
        "event": event_part,
        **{k: facts[k] for k in UNCHANGED_KEYS},
        "inventory": compact_inventory(facts["inventory"]),
        "technicians": compact_technicians(facts["technicians"]),
    }

    # Guard BOTH: facts feeds the post-LLM steps, prompt_facts feeds the model
    leaks = find_forbidden_keys(facts) + find_forbidden_keys(prompt_facts)
    if leaks:
        raise ValueError(f"answer labels leaked into facts: {leaks}")

    full_size, prompt_size = len(json.dumps(facts)), len(json.dumps(prompt_facts))
    logger.info("facts %d chars -> prompt_facts %d chars (%.0f%%)",
                full_size, prompt_size, 100 * prompt_size / full_size)
    return prompt_facts


# ---------------------------------------------------------------------------
# Check step 1: table sizes for the default seed (42)
# ---------------------------------------------------------------------------
EXPECTED_SIZES = {
    "assets": 28,
    "asset_classes": 8,
    "asset_criticality": 28,
    "criticality_matrix": 3,
    "work_order_details": 400,
    "telemetry": 28,              # 28 asset tags, 720 rows each
    "telemetry_pressure": 12,     # only 12 assets have pressure
    "work_orders": 28,            # 28 asset tags
    "inventory": 8,               # 8 asset codes
    "purchase_orders": 97,        # 97 distinct parts on order
    "technicians": 40,
    "technician_calendar": 1120,  # 40 technicians x 28 days
}


def check_lookups(lk: dict) -> None:
    """Log any table whose size differs from the default seed."""
    for name, expected in EXPECTED_SIZES.items():
        actual = len(lk[name])
        if actual != expected:
            logger.warning("Lookup %s has %d entries (expected %d)", name, actual, expected)
    logger.info("Loaded %d lookups", len(lk))


# ---------------------------------------------------------------------------
# Run the steps for one event: `python3 facts.py [record_id | event_id] [--evaluate]`
# (no id -> first event in records.jsonl)
# --evaluate compares the outputs with the event's ground truth (scoring only;
# ground_truth never goes into facts)
# ---------------------------------------------------------------------------
def main(event_id: str | None = None, evaluate: bool = False) -> dict:
    from intake import load_events   # imported here so the steps above don't depend on intake

    lk = load_lookups()
    check_lookups(lk)

    # event_id is not guaranteed unique in records.jsonl; record_id is.
    # Accept either; an ambiguous event_id stops with the record_ids to choose from.
    events = load_events()
    anchor = telemetry_anchor(events)          # step 7: computed once for the whole run
    logger.info("Telemetry anchor (hour %d) = %s", LAST_HOUR, anchor.isoformat())

    if event_id is None:
        event = events[0]
    else:
        matches = [e for e in events if event_id in (e.record_id, e.event_id)]
        if not matches:
            raise SystemExit(f"{event_id} not found")
        if len(matches) > 1:
            choices = ", ".join(f"{e.record_id} ({e.asset_tag})" for e in matches)
            raise SystemExit(f"event_id {event_id} is not unique; pass a record_id: {choices}")
        event = matches[0]
    logger.info("Event %s / %s: %s / %s", event.record_id, event.event_id, event.asset_tag, event.asset_code)

    # Step 2
    asset = get_asset(lk, event.asset_tag)
    asset_code_ok = check_asset_code(asset, event.asset_code)

    facts = {
        "record_id": event.record_id,
        "event_id": event.event_id,
        "received_at": event.received_at,      # event time: post-LLM steps need it (P2 dates)
        "asset": asset,
        "asset_code_matches_registry": asset_code_ok,
    }

    # Step 3 (always computed: missing_fields is a graded output)
    readings = event.readings.model_dump() if event.readings else None   # Pydantic model -> dict
    asset_code = asset["asset_code"] if asset else event.asset_code       # registry wins (step 2)
    facts["missing_fields"] = get_missing_fields(lk, readings, asset_code)

    # Step 4
    facts["trip"] = detect_trip(event.source, event.raw_text)

    # Step 5
    facts["suspect_readings"] = get_suspect_readings(readings)

    # Step 6
    facts["readings_check"] = check_readings(lk, readings, asset_code, facts["suspect_readings"])

    # Step 7
    facts["event_hour_index"] = event_hour_index(event.received_at, anchor)

    # Step 8 (use the matched tag from step 2: telemetry is keyed by the registry tag)
    tag = asset["asset_tag"] if asset else event.asset_tag
    facts["telemetry"] = get_telemetry_summary(lk, tag, asset_code, facts["event_hour_index"])

    # Step 9
    facts["history"] = get_history(lk, tag, event.received_at)

    # Step 10
    facts["downtime"] = get_downtime(lk, tag, asset["criticality"] if asset else None)

    # Step 11
    facts["inventory"] = get_inventory_check(lk, tag, asset_code, event.received_at)

    # Step 12
    facts["technicians"] = get_technician_pool(lk, asset_code, asset["line"] if asset else None,
                                               event.received_at)

    # Generic sanity checks, true for any event
    if asset is not None:
        assert set(asset) == {"asset_tag", *ASSET_FIELDS}   # no extra fields leak through
        assert asset["asset_tag"] in lk["assets"]           # matched tag is a real asset
    assert set(facts["missing_fields"]) <= set(expected_readings(lk, asset_code))

    # Optional: score against ground truth (evaluation only, not part of facts)
    if evaluate:
        truth = sorted(f.removeprefix("readings.") for f in event.ground_truth.missing_fields)
        ours = sorted(facts["missing_fields"])
        if ours == truth:
            logger.info("EVAL missing_fields: match %s", ours)
        else:
            logger.warning("EVAL missing_fields: ours=%s truth=%s", ours, truth)

    # Step 13 (last step before the LLM)
    prompt_facts = build_prompt_facts(event, facts)
    return {"facts": facts, "prompt_facts": prompt_facts}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gather pre-LLM facts for one intake event")
    parser.add_argument("event_id", nargs="?",
                        help="record_id or (unique) event_id to process (default: first event)")
    parser.add_argument("--evaluate", action="store_true", help="compare outputs with ground truth")
    parser.add_argument("--full", action="store_true",
                        help="print the full facts too (default: only prompt_facts, what the LLM sees)")
    args = parser.parse_args()
    result = main(args.event_id, evaluate=args.evaluate)
    print(json.dumps(result if args.full else result["prompt_facts"], indent=2))
