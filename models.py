from pydantic import BaseModel
from typing import Optional


class Readings(BaseModel):
    vibration_mm_s: Optional[float]
    temp_c: Optional[float]
    pressure_bar: Optional[float]
    current_a: Optional[float]


class Ground_Truth(BaseModel):
    priority: str
    probable_fault: str
    safety_critical: bool
    requires_permit: bool
    missing_fields: list[str]


class MaintenanceEvent(BaseModel):
    event_id: str
    source: str
    received_at: str
    raw_text: str
    asset_code: str
    asset_tag: str
    readings: Optional[Readings]
    ground_truth: Ground_Truth
    record_id: str


class TelemetryReading(BaseModel):
    asset_tag: str
    hour_index: int
    vibration_mm_s: float
    temp_c: float
    current_a: float
    seeded_fault: bool
