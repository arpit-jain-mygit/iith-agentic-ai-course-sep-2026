import json
import logging
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from models import MaintenanceEvent
from settings import RECORDS_PATH   # data location comes from DATA_ROOT in .env

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def load_events(path=RECORDS_PATH) -> list[MaintenanceEvent]:
    """Read records.jsonl and return one validated MaintenanceEvent per valid line."""
    logger.info("Loading events from %s", path)
    events = []
    skipped = 0
    with open(path) as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(MaintenanceEvent.model_validate(json.loads(line)))
            except (json.JSONDecodeError, ValidationError) as e:
                skipped += 1
                logger.warning("Skipping line %d: %s", line_no, e)
    logger.info("Loaded %d events (%d skipped)", len(events), skipped)
    return events


def summarize(events: list[MaintenanceEvent]) -> dict:
    """Count events by source and asset_code."""
    summary = {
        "total": len(events),
        "by_source": dict(Counter(e.source for e in events)),
        "by_asset_code": dict(Counter(e.asset_code for e in events)),
    }
    logger.info("Summary: %s", summary)
    return summary


def main() -> list[MaintenanceEvent]:
    events = load_events()
    summarize(events)
    return events


if __name__ == "__main__":
    events = main()